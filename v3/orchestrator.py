"""orchestrator.py — wires ONE pipeline + ONE evaluator over the chosen
questions and saves the result.

Why it's here: the run entry point. Also the home of the SHARED generator, so
every arm answers with the identical model (the fairness control). It routes
corpus -> pipeline and truth -> evaluator. No retrieval/scoring logic of its own
(the arms retrieve, the evaluators score).
"""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import abort
import jsonl
import provenance
from progress import progress
import questions
from contract import (
    ArmOutput, EvalManifest, ModelUsage, RunManifest, generator_messages,
    generator_usage_from_nim, model_usage_from_dict, model_usage_from_telemetry,
)

_HERE = Path(__file__).parent
DEFAULT_CORPUS = _HERE / "data" / "corpus" / "Salesforce__HERB"
DEFAULT_OUTPUT = _HERE / "output"
GRAPH_BUILD_DIR = DEFAULT_OUTPUT / "graph_build"
# A run is filed under what cuts its depth: a count of retrieval units (top-k) or
# a character total (char_budget). One root per family, so the caches and the
# id-set files keep output/ to themselves and neither family buries the other.
CHUNKS_ROOT = DEFAULT_OUTPUT / "k=chunks"
CHARS_ROOT = DEFAULT_OUTPUT / "k=chars"
DEFAULT_TOP_K = 50
# Questions answer concurrently; generation is the slow leg, so overlapping calls
# ride up to nim.py's shared rate cap (which is what actually bounds throughput).
DEFAULT_WORKERS = 2
# A run that racks up this many failures in a row aborts loud — that many
# back-to-back failures means the backend is down, so grinding the rest just
# burns the rate budget for nothing.
MAX_CONSECUTIVE_FAILURES = 10

# The shared generator on NVIDIA NIM. ONE model, built once here and injected into
# every arm, so the only variable across arms is retrieval, never the LLM. Transport
# is nim.post (NIM speaks the OpenAI REST API).
GENERATOR_MODEL = "claude-sonnet-5"

# OpenAI-format structured output: the model returns exactly {answer} under a strict
# schema, not free text. The answer is the only thing the generator owns — retrieved
# ids, contexts, timings and token counts are all recorded by the harness around the
# call, so the model is never asked to restate them.
_ANSWER_SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}


# --- questions ---------------------------------------------------------------

def load_chosen_questions(ids_file, questions_path=None):
    """Load the full question set (truth hydrated from raw via questions.jsonl)
    and keep those whose id is listed in `ids_file`, in file order. `ids_file=None`
    -> the whole set. An id in `ids_file` with no matching question raises (fail
    loud — the id scheme is exact).
    linked to: questions.load_questions; contract.QuestionWithTruth
    """
    all_q = (questions.load_questions(questions_path) if questions_path
             else questions.load_questions())
    if ids_file is None:
        return all_q
    chosen = _read_ids(ids_file)
    by_id = {q.id: q for q in all_q}
    missing = [i for i in chosen if i not in by_id]
    if missing:
        raise KeyError(
            f"{len(missing)} chosen id(s) absent from the question set, "
            f"e.g. {missing[:5]}"
        )
    return [by_id[i] for i in chosen]


def _read_ids(ids_file):
    """Ids from a jsonl id-set file (output/question_ids.jsonl, gold100.jsonl,
    or a failures.jsonl): each non-blank line is a JSON object carrying an "id".
    Order preserved; a line that isn't such an object fails loud, naming file +
    line + content."""
    ids = []
    for n, line in enumerate(Path(ids_file).read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            ids.append(json.loads(line)["id"])
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise ValueError(
                f"{ids_file} line {n}: not a JSON object with an 'id' ({line!r})"
            ) from e
    return ids


# --- corpus ------------------------------------------------------------------

def open_corpus(corpus_root):
    """Handle onto the RAG-safe corpus — the only data a pipeline sees. Validates
    the products dir exists (fail loud) and hands back the path the arm ingests.
    linked to: pipeline.prepare_over_corpus
    """
    root = Path(corpus_root)
    if not (root / "products").is_dir():
        raise FileNotFoundError(f"no products/ under corpus root {root}")
    return root


# --- shared generator --------------------------------------------------------

def build_shared_generator(config):
    """Build the ONE generator (on NIM) injected into every arm.
    Returns a callable generate(question_text, contexts) -> (answer, telemetry),
    where telemetry = {calls, tokens_in, tokens_out, time} fills the arm's generator ModelUsage.
    `config['retrieval_only']` -> None (smoke: retrieval without generation).
    linked to: every arm's answer_one_question (the `generate` argument)
    """
    if config.get("retrieval_only"):
        return None

    import nim

    nim.require_key()  # fail loud now, before the run starts — not mid-loop
    model = config.get("generator_model", GENERATOR_MODEL)

    def generate(question, contexts):
        nim.reset_timing()
        t0 = time.perf_counter()
        resp = nim.post("/chat/completions", {
            "model": model,
            "temperature": 0,  # deterministic — eval reproducibility
            # Non-thinking: enable_thinking is NIM's authoritative switch (it overrides the
            # /no_think prompt token), so the answer is direct and reproducible and the
            # guided JSON stays well-formed. NIM defaults this model off; this pins it.
            "chat_template_kwargs": {"enable_thinking": False},
            # Output budget. Unset, NIM applies its own low default and long answers
            # come back truncated (finish_reason=length); the 262k context leaves ample room.
            "max_tokens": 8192,
            # Force >=1 generated token; Qwen otherwise greedily emits end-of-turn first
            # for some prompts (null content, finish_reason=stop) — same guard the judge uses.
            "min_tokens": 1,
            "messages": generator_messages(question, contexts),
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "answer", "schema": _ANSWER_SCHEMA},
            },
        }, timeout=480.0)  # the hosted model queues under load; a try must outlast the queue
        elapsed = time.perf_counter() - t0
        transport = nim.take_timing()
        choices = resp.get("choices") or []
        if not choices:
            raise RuntimeError("generator returned no choices")
        content = (choices[0].get("message") or {}).get("content")
        if content is None:  # length cap / filter / tool turn — never a silent null answer
            raise RuntimeError(
                f"generator returned null content "
                f"(finish_reason={choices[0].get('finish_reason')})"
            )
        try:
            answer = json.loads(content)["answer"]
            if not isinstance(answer, str):
                raise TypeError(f"answer is {type(answer).__name__}, not str")
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise RuntimeError(
                f"generator did not honour the answer schema "
                f"(finish_reason={choices[0].get('finish_reason')}): {content!r}") from e
        tokens_in, tokens_out = generator_usage_from_nim(resp.get("usage"))
        return answer, {"calls": 1, "tokens_in": tokens_in, "tokens_out": tokens_out,
                        "cached_input_tokens": int(
                            (resp.get("usage") or {}).get("cached_input_tokens") or 0),
                        "time": elapsed, **transport}

    return generate


# --- run ---------------------------------------------------------------------

def to_arm_question(question):
    """Strip the truth: hand the arm the question's id + text ONLY, as the (id,
    text) tuple the arms accept. The quarantine, in code — ground_truth/citations
    are physically not in what the arm receives.
    linked to: pipeline.answer_one_question
    """
    return question.id, question.question


def _done_ids(records_path):
    """Ids already answered — one per line in arm_outputs.jsonl. This is the resume
    set: a re-run skips these, so finished work is never redone or lost. A killed
    write can leave the last line torn; that answer never finished, so it is
    dropped here and re-answered (jsonl.load)."""
    return {rec["id"] for rec in jsonl.load(records_path)}


def _n_exhausted(records_path):
    """How many answered questions ran their ranking out before the character
    budget — the arm records that case per answer as meta.char_budget.exhausted,
    and a run whose arms could not fill the budget it names is only legible if
    the count is carried where the totals are read."""
    return sum(1 for rec in jsonl.load(records_path)
               if ((rec.get("meta") or {}).get("char_budget") or {}).get("exhausted"))


def _rehydrate(rec):
    """A persisted arm-output record (dict) -> contract.ArmOutput, so the scorer
    reads answers off disk rather than only this session's in-memory ones."""
    return ArmOutput(rec["answer"], rec["contexts"], rec["context_ids"],
                     rec["search_time_s"], model_usage_from_dict(rec["generator"]),
                     model_usage_from_dict(rec["retrieval"]))


def run_one_pipeline(pipeline, chosen, corpus, generate, out_dir, k=DEFAULT_TOP_K,
                     workers=DEFAULT_WORKERS,
                     max_consecutive_failures=MAX_CONSECUTIVE_FAILURES,
                     char_budget=None):
    """Prepare the arm once, then answer the questions concurrently, writing each
    answer to out_dir/arm_outputs.jsonl AS IT LANDS (flushed) — so a crash or an
    abort never loses finished work. Resumes by skipping ids already in that file.
    The model rate cap lives in nim.py, so `workers` only sets how many calls
    overlap. `char_budget` (fill-to-budget retrieval) passes through to the arm's
    answer_one_question only when set, so an arm without the mode fails loud on
    the unknown keyword.

    A question whose answer raises is collected in `failures`, skipped, and written
    to out_dir/failures.jsonl the instant it lands (flushed) — so failures can be
    watched live and the run killed if they pile up. `max_consecutive_failures` in a
    row stops the run itself (sets `aborted`): the backend is down, and grinding on
    only burns the rate budget. Answers are written in submission order (the gather
    loop is single-threaded), so both files are ordered.
    -> (ran, failures, aborted, build_stats); `aborted` is None or a reason string.
    linked to: pipeline.prepare_over_corpus + pipeline.answer_one_question
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    records_path = out / "arm_outputs.jsonl"
    failures_path = out / "failures.jsonl"
    # A killed write can leave a fragment with no newline. Appending onto it would
    # weld two records into one unparseable line and the folder could never resume
    # again, so the fragment is cut before the append handle opens.
    jsonl.heal(records_path)
    done = _done_ids(records_path)
    todo = [q for q in chosen if q.id not in done]

    prepared = pipeline.prepare_over_corpus(corpus)
    ran, failures, aborted, consecutive = [], [], None, 0
    # arm_outputs.jsonl is append (resume keeps prior answers); failures.jsonl is
    # truncated fresh each leg and gets each failure live as it lands. On an abort
    # the unreached tail past the break is neither answered nor recorded — a resume
    # re-attempts it (it's still absent from arm_outputs.jsonl).
    with records_path.open("a", encoding="utf-8") as fh, \
            failures_path.open("w", encoding="utf-8") as ffh, \
            ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        extra = {} if char_budget is None else {"char_budget": char_budget}
        futures = [ex.submit(pipeline.answer_one_question,
                             to_arm_question(q), prepared, generate, k, **extra)
                   for q in todo]
        for q, fut in progress(list(zip(todo, futures)), desc="answering", unit="q"):
            if abort.aborted():
                for f in futures:
                    f.cancel()
                aborted = "user aborted (pressed q)"
                break
            try:
                out_obj = fut.result()
            except abort.Aborted:  # q pressed mid-call — stop, don't log it as a failure
                for f in futures:
                    f.cancel()
                aborted = "user aborted (pressed q)"
                break
            except Exception as e:
                failures.append((q, repr(e)))
                ffh.write(json.dumps({"id": q.id, "error": repr(e)},
                                     ensure_ascii=False) + "\n")
                ffh.flush()  # live — a failure shows up the moment it happens
                consecutive += 1
                if consecutive >= max_consecutive_failures:
                    for f in futures:
                        f.cancel()
                    aborted = (f"{consecutive} consecutive failures "
                               f"(generation backend likely down) - last: {e!r}")
                    break
            else:
                # answered_at makes a resumed folder legible: which answers came from
                # which leg, and how much of the elapsed span was the machine idle
                # between them rather than work.
                fh.write(json.dumps(
                    {"id": q.id, "question": q.question,
                     "answered_at": datetime.now(timezone.utc).isoformat(),
                     **asdict(out_obj)},
                    ensure_ascii=False) + "\n")
                fh.flush()
                os.fsync(fh.fileno())  # durable per answer — survives a power cut, not just a kill
                ran.append(q)
                consecutive = 0
    return ran, failures, aborted, getattr(prepared, "build_stats", None)


def run_one_evaluator(evaluator, outputs, chosen, arm="", corpus=None, results_path=None,
                      workers=1, retrieval_only=False):
    """-> list[contract.EvalResult]. The arm label + corpus (so an evaluator can
    dereference gold citations to text), results_path (so the scorer writes each
    question's cells as they land — crash-safe + resumable), workers (questions
    scored concurrently — the same knob generation uses), and retrieval_only (score
    only the judge-free, embed-free metrics when no generator ran) pass through.
    linked to: evaluator.score_outputs"""
    return evaluator.score_outputs(outputs, chosen, arm=arm, corpus=corpus,
                                   results_path=results_path, workers=workers,
                                   retrieval_only=retrieval_only)


def graph_identity(database):
    """The manifest's graph block for the Neo4j database the arm queried: the
    resolved name plus the graph's build RECORD as read at manifest-write time —
    when GRAPH_BUILD_DIR/<database>/build_manifest.json exists, its
    graph_version and graph_census_sha256 (what the graph holds, so one database
    name rebuilt into a different shape reads as a different graph),
    removed_tags_sha256, build timestamp and source_database (the parent the
    build copied from, so the run folder keeps its lineage even without
    graph_build/). A database with no readable build record carries a null
    identity — the lookup is a read-only file read and never fails a run.
    `database=None` (an arm that queries no graph) -> None: no invented
    provenance.
    linked to: build_run_manifest; build_entity_graph.py writes the record
    """
    if database is None:
        return None
    version = census = sha = built = source = None
    try:
        record = json.loads((GRAPH_BUILD_DIR / database / "build_manifest.json")
                            .read_text(encoding="utf-8"))
        version = record.get("graph_version")
        census = record.get("graph_census_sha256")
        sha = record.get("removed_tags_sha256")
        built = record.get("timestamp")
        source = record.get("source_database")
    except (OSError, ValueError, AttributeError):
        pass
    return {"database": database, "graph_version": version,
            "graph_census_sha256": census, "removed_tags_sha256": sha,
            "build_timestamp": built, "source_database": source}


def _merged_graph(prior, current):
    """The graph block a manifest rewrite records. A matching prior passes
    `current` through; a difference means the folder's answers span more than
    one graph build, and the block becomes {"mixed_builds": [oldest, …,
    newest]} so a mixed run is visibly mixed to every reader — a resume never
    restamps earlier answers with a newer build's identity. An already-mixed
    prior extends. A prior that carries no usable identity — `None` from a
    manifest written before the field, or a malformed `mixed_builds` — is an
    unknown build and records as the `None` head of the mix, because less
    knowledge about the earlier answers can never print as more.
    linked to: run() (the manifest rewrite on resume)"""
    if prior == current:
        return current
    if isinstance(prior, dict) and "mixed_builds" in prior:
        builds = prior["mixed_builds"]
        if not isinstance(builds, list) or not builds:
            builds = [None]
    else:
        builds = [prior]
    if builds[-1] == current:
        return {"mixed_builds": builds}
    return {"mixed_builds": builds + [current]}


def build_run_manifest(config, arm, build_stats, n_questions, n_ran, n_failed,
                       n_exhausted=None):
    """Provenance for the generation side -> contract.RunManifest (timestamp now,
    UTC). Records the run split (chosen / ran / failed) so the run folder is
    self-documenting — no need to count jsonl lines to see what failed — plus how
    many answers ran their ranking out before the character budget
    (`n_exhausted`, None on a depth run), and the graph identity when the arm
    queries Neo4j (config['graph_database'], resolved off the pipeline module in
    run())."""
    return RunManifest(
        arm=arm,
        generator_model=(None if config.get("retrieval_only")
                         else config.get("generator_model", GENERATOR_MODEL)),
        interpreter_model=config.get("interpreter_model"),
        top_k=config.get("top_k", DEFAULT_TOP_K),
        char_budget=config.get("char_budget"),
        questions_file=str(config.get("questions_path") or questions.QUESTIONS),
        n_questions=n_questions,
        n_ran=n_ran,
        n_failed=n_failed,
        n_exhausted=n_exhausted,
        timestamp=datetime.now(timezone.utc).isoformat(),
        build_stats=build_stats,
        retrieval_flags=config.get("retrieval_flags"),
        graph=graph_identity(config.get("graph_database")),
        code_version=provenance.code_version(),
        environment=provenance.environment(),
        inputs=provenance.inputs(
            questions_file=config.get("questions_path") or questions.QUESTIONS,
            ids_file=config.get("ids_file"),
            corpus_root=config.get("corpus_root", DEFAULT_CORPUS)),
    )


def _accumulated_judge(prior, manifest):
    """The judge block a manifest rewrite records.

    A resumed eval scores only the cells the previous leg left, so its usage is a
    PART of what the folder cost, never a replacement for it. Each leg is kept in
    `judge_legs` and the totals are the sum of that list, so a resumed folder
    still states its true cost, the total stays decomposable, and a leg scored by
    a different judge is visible rather than folded into one anonymous number. A
    leg that made no judge call adds nothing — a re-run that finds every cell
    already scored leaves the record as it was.
    linked to: run() (the manifest rewrite on resume)
    """
    legs = list((prior or {}).get("judge_legs") or [])
    if not legs and prior and (prior.get("judge_usage") or prior.get("judge_elapsed_s")):
        # a manifest written before legs were kept still carries its own totals
        legs.append({"timestamp": prior.get("timestamp"),
                     "judge_model": prior.get("judge_model"),
                     "judge_backend": prior.get("judge_backend"),
                     "usage": prior.get("judge_usage"),
                     "elapsed_s": prior.get("judge_elapsed_s")})

    usage = manifest.judge_usage
    if usage is not None and usage.calls:
        legs.append({"timestamp": manifest.timestamp,
                     "judge_model": manifest.judge_model,
                     "judge_backend": manifest.judge_backend,
                     "usage": asdict(usage),
                     "elapsed_s": manifest.judge_elapsed_s})

    if not legs:
        return manifest

    total = ModelUsage()
    elapsed = 0.0
    for leg in legs:
        u = model_usage_from_dict(leg.get("usage") or {})
        total.calls += u.calls
        total.tokens_in += u.tokens_in
        total.cached_input_tokens += u.cached_input_tokens
        total.tokens_out += u.tokens_out
        total.reasoning_tokens += u.reasoning_tokens
        total.time_s += u.time_s
        total.attempts += u.attempts
        total.request_s += u.request_s
        total.wait_s += u.wait_s
        total.retry_s += u.retry_s
        elapsed += float(leg.get("elapsed_s") or 0.0)
    manifest.judge_usage = total
    manifest.judge_elapsed_s = elapsed
    manifest.judge_legs = legs
    return manifest


def build_eval_manifest(config, scorer, arm, source_run):
    """Provenance for the eval side -> contract.EvalManifest (timestamp now, UTC).
    The judge block is what the scoring leg actually invoked — model, backend,
    reasoning effort, aggregate usage and wall time — so a folder's scores can be
    priced and compared against another judge's without rerunning anything."""
    usage = config.get("judge_usage")
    return EvalManifest(
        scorer=scorer,
        judge_model=config.get("judge_model"),
        source_run=str(source_run),
        arm=arm,
        timestamp=datetime.now(timezone.utc).isoformat(),
        judge_backend=config.get("judge_backend"),
        judge_effort=config.get("judge_effort"),
        judge_usage=model_usage_from_dict(asdict(usage)) if usage is not None else None,
        judge_elapsed_s=config.get("judge_elapsed_s"),
    )


def _arm_name(module):
    """'pipelines.lucene' / 'eval.ragas' -> 'lucene' / 'ragas' (run + output label)."""
    return module.__name__.rsplit(".", 1)[-1]


def run(pipeline, evaluator, ids_file, config=None):
    """TOP ENTRY. Generation writes each answer to out_dir/arm_outputs.jsonl as it
    lands (resumable + crash-safe); then — unless the run aborts — the evaluator
    scores the FULL persisted set. Re-running with the same out_dir resumes: ids
    already on disk are skipped, the rest are answered and appended.
    -> {out_dir, n_questions, n_ran, n_failed, n_exhausted, n_results}.
    linked to: all of the above; run.py is the CLI over this.
    """
    config = dict(config or {})
    config.setdefault("ids_file", ids_file)  # digested into the manifest's inputs block
    arm = _arm_name(pipeline)
    config.setdefault("interpreter_model", getattr(pipeline, "INTERPRET_MODEL", None))
    config.setdefault("retrieval_flags", getattr(pipeline, "RETRIEVAL_FLAGS", None))
    config.setdefault("graph_database", getattr(pipeline, "DATABASE", None))
    evname = _arm_name(evaluator) if evaluator is not None else "gen"

    chosen = load_chosen_questions(ids_file, config.get("questions_path"))
    corpus = open_corpus(config.get("corpus_root", DEFAULT_CORPUS))
    generate = build_shared_generator(config)
    root = CHUNKS_ROOT if config.get("char_budget") is None else CHARS_ROOT
    out = Path(config.get("out_dir") or root / f"{arm}__{evname}")

    ran, _, aborted, build_stats = run_one_pipeline(
        pipeline, chosen, corpus, generate, out,
        config.get("top_k", DEFAULT_TOP_K), config.get("workers", DEFAULT_WORKERS),
        char_budget=config.get("char_budget"))

    # run_one_pipeline wrote each answer to arm_outputs.jsonl and each failure to
    # failures.jsonl as they landed; here we only record provenance off the durable
    # files. Both counts read from disk so they reconcile across resumes:
    # n_ran + n_failed == n_questions (n_failed = chosen not yet answered).
    # A leg that generated nothing (an eval-only resume) leaves the manifest
    # alone — it describes the generation run, and its config (e.g. the
    # generator model) belongs to the leg that produced the answers.
    done = _done_ids(out / "arm_outputs.jsonl")
    n_failed = len(chosen) - len(done)
    n_exhausted = (None if config.get("char_budget") is None
                   else _n_exhausted(out / "arm_outputs.jsonl"))
    manifest_path = out / "run_manifest.json"
    if ran or not manifest_path.is_file():
        manifest = build_run_manifest(
            config, arm, build_stats, len(chosen), len(done), n_failed, n_exhausted)
        if manifest_path.is_file():
            # a resume rewrite: the answers already on disk may predate a rebuild
            # of the same database, so a graph identity differing from the one
            # recorded stays visible as a mix, never restamped with the new build
            try:
                prior = json.loads(
                    manifest_path.read_text(encoding="utf-8")).get("graph")
            except (OSError, ValueError, AttributeError):
                prior = None  # unreadable prior: the earlier answers' build is unknown
            manifest.graph = _merged_graph(prior, manifest.graph)
        manifest_path.write_text(
            json.dumps(asdict(manifest), ensure_ascii=False, indent=2),
            encoding="utf-8")

    if aborted:  # loud — but every finished answer is already on disk; resume continues
        raise RuntimeError(f"aborted run at {out}: {aborted}")

    if evaluator is None:  # arm run — answers only, no scoring
        return {"out_dir": str(out), "n_questions": len(chosen),
                "n_ran": len(done), "n_failed": n_failed,
                "n_exhausted": n_exhausted}

    # eval scores the FULL persisted set, re-hydrating ArmOutput from the records
    # (so a resumed run scores everything, not just the last leg); truth joins by id.
    by_id = {q.id: q for q in chosen}
    recs = jsonl.load(out / "arm_outputs.jsonl")
    eval_path = out / "eval_results.jsonl"
    results = run_one_evaluator(
        evaluator, [_rehydrate(r) for r in recs], [by_id[r["id"]] for r in recs],
        arm, corpus, eval_path, config.get("workers", DEFAULT_WORKERS),
        config.get("retrieval_only", False))
    config["judge_model"] = getattr(evaluator, "LAST_JUDGE_MODEL", None)
    config["judge_backend"] = getattr(evaluator, "LAST_JUDGE_BACKEND", None)
    config["judge_effort"] = getattr(evaluator, "LAST_JUDGE_REASONING_EFFORT", None)
    config["judge_usage"] = getattr(evaluator, "LAST_JUDGE_USAGE", None)
    config["judge_elapsed_s"] = getattr(evaluator, "LAST_JUDGE_WALL_TIME_S", None)
    eval_manifest_path = out / "eval_manifest.json"
    eval_manifest = build_eval_manifest(config, evname, arm, out)
    if eval_manifest_path.is_file():
        # this leg scored only what the last one left, so its cost adds to the
        # folder's rather than replacing it
        try:
            prior = json.loads(eval_manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            prior = None  # unreadable prior: this leg's cost is all that can be stated
        eval_manifest = _accumulated_judge(prior, eval_manifest)
    eval_manifest_path.write_text(
        json.dumps(asdict(eval_manifest), ensure_ascii=False, indent=2),
        encoding="utf-8")
    # the evaluator wrote each question's cells to eval_path as they finished (resumable),
    # so count from disk — a resumed run reports the full set, not just this leg.
    n_results = (sum(1 for x in eval_path.read_text(encoding="utf-8").splitlines() if x.strip())
                 if eval_path.is_file() else len(results or []))
    return {"out_dir": str(out), "n_questions": len(chosen), "n_ran": len(done),
            "n_failed": n_failed, "n_exhausted": n_exhausted, "n_results": n_results}


# --- self-check --------------------------------------------------------------

def _selfcheck():
    """Wiring check with fakes — no NIM, no bm25s, no disk questions. Verifies the
    truth quarantine, incremental + resumable writing, submission-order alignment,
    the circuit breaker, record re-hydration, and the manifests."""
    import tempfile
    import threading
    import types
    from contract import BuildStats, EvalResult, QuestionWithTruth

    prepared = types.SimpleNamespace(build_stats=BuildStats(0.1, ModelUsage(), []))
    seen = {}

    def fake_generate(text, contexts):
        seen["gen_text"] = text  # the arm must pass ONLY the question text
        return "ans", {"calls": 1, "tokens_in": 3, "tokens_out": 4, "time": 0.0}

    def answer_one_question(q, prep, generate, k):
        assert isinstance(q, tuple) and len(q) == 2, f"truth not stripped: {q!r}"
        a, tel = generate(q[1], ["ctx"])
        return ArmOutput(a, ["ctx"], ["cit1"], 0.0,
                         model_usage_from_telemetry(tel), ModelUsage())

    fake = types.SimpleNamespace(
        __name__="pipelines.fake", prepare_over_corpus=lambda c: prepared,
        answer_one_question=answer_one_question)
    qs = [QuestionWithTruth(f"p::a::{i}", f"q{i}?", "person", ["eid_x"], ["cit1"])
          for i in range(2)]

    assert to_arm_question(qs[0]) == ("p::a::0", "q0?")  # quarantine

    def _rows(d, name="arm_outputs.jsonl"):
        return [json.loads(x) for x in
                (Path(d) / name).read_text(encoding="utf-8").splitlines()
                if x.strip()]

    with tempfile.TemporaryDirectory() as d:
        # incremental write: each answer is on disk, oracle-free + self-identifying
        ran, fails, aborted, bs = run_one_pipeline(fake, qs, "c/", fake_generate, d, workers=1)
        assert aborted is None and [q.id for q in ran] == ["p::a::0", "p::a::1"] and fails == []
        assert bs is prepared.build_stats and seen["gen_text"] == "q1?"
        r = _rows(d)
        assert [x["id"] for x in r] == ["p::a::0", "p::a::1"] and r[0]["answer"] == "ans"
        assert "tokens_in" in r[0]["generator"] and "tokens_out" in r[0]["generator"]
        assert _rows(d, "failures.jsonl") == []  # clean leg: file exists, empty

        # resume: same folder -> the two already done are skipped, no duplicates
        ran2, _, _, _ = run_one_pipeline(fake, qs, "c/", fake_generate, d, workers=1)
        assert ran2 == [] and len(_rows(d)) == 2

    # ordering under concurrency: reverse completion, file still in submission order
    with tempfile.TemporaryDirectory() as d:
        q3 = [QuestionWithTruth(f"o::a::{i}", f"o{i}?", "person", [], []) for i in range(3)]

        def slow(q, prep, generate, k):
            idx = int(q[0].rsplit("::", 1)[1])
            time.sleep(0.02 * (3 - idx))  # 0 finishes last
            return ArmOutput(q[0], [], [], 0.0, ModelUsage(), ModelUsage())

        sp = types.SimpleNamespace(__name__="pipelines.slow",
                                   prepare_over_corpus=lambda c: prepared, answer_one_question=slow)
        run_one_pipeline(sp, q3, "c/", fake_generate, d, workers=3)
        assert [x["id"] for x in _rows(d)] == ["o::a::0", "o::a::1", "o::a::2"]

    # circuit breaker: enough consecutive failures -> aborted set, nothing falsely saved
    with tempfile.TemporaryDirectory() as d:
        def dead(q, prep, generate, k):
            raise RuntimeError("nim down")

        dp = types.SimpleNamespace(__name__="pipelines.dead",
                                   prepare_over_corpus=lambda c: prepared, answer_one_question=dead)
        many = [QuestionWithTruth(f"d::a::{i}", f"d{i}?", "person", [], []) for i in range(20)]
        _, _, aborted, _ = run_one_pipeline(dp, many, "c/", fake_generate, d, workers=2,
                                            max_consecutive_failures=3)
        assert aborted and "consecutive failures" in aborted
        assert not (Path(d) / "arm_outputs.jsonl").read_text(encoding="utf-8").strip()
        f = _rows(d, "failures.jsonl")  # failures written live, before the abort
        assert f and all("nim down" in x["error"] for x in f)

    # the breaker truly STOPS work (doesn't just stop recording): with real latency
    # per failing call, the pending tail is cancelled, not executed — so far fewer
    # than all 60 run before the abort (the down-backend case, where it matters).
    with tempfile.TemporaryDirectory() as d:
        calls, clk = {"n": 0}, threading.Lock()

        def slow_dead(q, prep, generate, k):
            with clk:
                calls["n"] += 1
            time.sleep(0.03)
            raise RuntimeError("nim down")

        sdp = types.SimpleNamespace(__name__="pipelines.sdead",
                                    prepare_over_corpus=lambda c: prepared,
                                    answer_one_question=slow_dead)
        big = [QuestionWithTruth(f"s::a::{i}", f"s{i}?", "person", [], []) for i in range(60)]
        _, _, ab, _ = run_one_pipeline(sdp, big, "c/", fake_generate, d, workers=4,
                                       max_consecutive_failures=6)
        assert ab and calls["n"] <= 24, calls["n"]  # ~12 ran, the rest cancelled

    # rehydrate: a persisted record reconstructs the ArmOutput the scorer sees
    o = ArmOutput("a", ["c"], ["id1"], 1.0,
                  ModelUsage(calls=1, tokens_in=1, tokens_out=2, time_s=3.0), ModelUsage())
    assert _rehydrate({"id": "x", "question": "q", **asdict(o)}) == o

    # fill-to-budget passthrough: the arm sees char_budget only when set
    with tempfile.TemporaryDirectory() as d:
        got = {}

        def budget_arm(q, prep, generate, k, char_budget=None):
            got["char_budget"] = char_budget
            return ArmOutput("a", ["ctx"], ["cit1"], 0.0, ModelUsage(), ModelUsage())

        bp = types.SimpleNamespace(__name__="pipelines.budget",
                                   prepare_over_corpus=lambda c: prepared,
                                   answer_one_question=budget_arm)
        run_one_pipeline(bp, qs[:1], "c/", fake_generate, d, workers=1, char_budget=9)
        assert got["char_budget"] == 9

    # manifests carry the run split + provenance
    rm = build_run_manifest({}, "fake", prepared.build_stats, 10, 7, 3)
    assert rm.arm == "fake" and rm.generator_model == GENERATOR_MODEL
    assert rm.interpreter_model is None
    assert rm.char_budget is None
    assert rm.graph is None  # no graph_database: an arm that queries no graph
    assert (rm.n_questions, rm.n_ran, rm.n_failed) == (10, 7, 3)
    assert build_run_manifest({"char_budget": 72000}, "fake",
                              prepared.build_stats, 1, 1, 0).char_budget == 72000

    # graph identity: a Neo4j arm's manifest names the database it queried, and
    # carries the build record when graph_build/<db>/build_manifest.json has one
    with tempfile.TemporaryDirectory() as d:
        global GRAPH_BUILD_DIR
        saved, GRAPH_BUILD_DIR = GRAPH_BUILD_DIR, Path(d)
        try:
            def _graph_of(db):
                return build_run_manifest({"graph_database": db}, "fake",
                                          prepared.build_stats, 1, 1, 0).graph

            built = Path(d) / "eval-v9"
            built.mkdir()
            (built / "build_manifest.json").write_text(json.dumps(
                {"graph_version": "copy+entities", "graph_census_sha256": "cd34",
                 "removed_tags_sha256": "ab12", "timestamp": "2026-08-12T20:38:00Z",
                 "source_database": "eval-v8"}), encoding="utf-8")
            assert _graph_of("eval-v9") == {
                "database": "eval-v9", "graph_version": "copy+entities",
                "graph_census_sha256": "cd34", "removed_tags_sha256": "ab12",
                "build_timestamp": "2026-08-12T20:38:00Z",
                "source_database": "eval-v8"}
            assert _graph_of("bare-db") == {  # no build record: name + null identity
                "database": "bare-db", "graph_version": None,
                "graph_census_sha256": None, "removed_tags_sha256": None,
                "build_timestamp": None, "source_database": None}
            (built / "build_manifest.json").write_text("{broken", encoding="utf-8")
            assert _graph_of("eval-v9") == {  # corrupt record: null identity, no crash
                "database": "eval-v9", "graph_version": None,
                "graph_census_sha256": None, "removed_tags_sha256": None,
                "build_timestamp": None, "source_database": None}
        finally:
            GRAPH_BUILD_DIR = saved

    # a manifest rewrite never restamps another build's answers: a differing
    # graph identity becomes a visible mix, and an already-mixed block extends
    ga = {"database": "db", "graph_version": "v1", "graph_census_sha256": "c1",
          "removed_tags_sha256": "A", "build_timestamp": "t1",
          "source_database": "src"}
    gb = {**ga, "graph_version": "v2", "graph_census_sha256": "c2",
          "removed_tags_sha256": "B", "build_timestamp": "t2"}
    assert _merged_graph(None, None) is None
    assert _merged_graph(ga, ga) == ga
    assert _merged_graph(ga, gb) == {"mixed_builds": [ga, gb]}
    assert _merged_graph({"mixed_builds": [ga, gb]}, gb) == {"mixed_builds": [ga, gb]}
    assert _merged_graph({"mixed_builds": [ga, gb]}, ga) == {"mixed_builds": [ga, gb, ga]}
    assert _merged_graph(None, ga) == {"mixed_builds": [None, ga]}  # pre-field manifest
    for malformed in ({"mixed_builds": []}, {"mixed_builds": "A"}, {"mixed_builds": 7}):
        assert _merged_graph(malformed, ga) == {"mixed_builds": [None, ga]}

    # run() end to end: the graph database resolves off the pipeline module's
    # DATABASE, and a resume after a rebuild of that database records the mix
    # in run_manifest.json on disk
    with tempfile.TemporaryDirectory() as d:
        droot = Path(d)
        saved, GRAPH_BUILD_DIR = GRAPH_BUILD_DIR, droot / "graph_build"
        try:
            (droot / "corpus" / "products").mkdir(parents=True)
            (droot / "q.jsonl").write_text("".join(
                json.dumps({"id": f"g::a::{i}", "question": f"g{i}?",
                            "type": "person", "ground_truth": [],
                            "citations": []}) + "\n" for i in range(2)),
                encoding="utf-8")
            bdir = GRAPH_BUILD_DIR / "fake-db"
            bdir.mkdir(parents=True)
            gp = types.SimpleNamespace(
                __name__="pipelines.graphfake", DATABASE="fake-db",
                prepare_over_corpus=lambda c: prepared,
                answer_one_question=lambda q, prep, generate, k:
                    ArmOutput("", ["ctx"], ["cit1"], 0.0, ModelUsage(), ModelUsage()))

            def _record(sha):
                (bdir / "build_manifest.json").write_text(json.dumps(
                    {"graph_version": f"shape-{sha}",
                     "graph_census_sha256": f"census-{sha}",
                     "removed_tags_sha256": sha, "timestamp": f"t-{sha}",
                     "source_database": "parent-db"}), encoding="utf-8")

            def _leg(n_ids):
                ids = droot / "ids.jsonl"
                ids.write_text("".join(json.dumps({"id": f"g::a::{i}"}) + "\n"
                                       for i in range(n_ids)), encoding="utf-8")
                run(gp, None, ids, {"questions_path": droot / "q.jsonl",
                                    "corpus_root": droot / "corpus",
                                    "out_dir": str(droot / "run"),
                                    "retrieval_only": True})
                return json.loads((droot / "run" / "run_manifest.json")
                                  .read_text(encoding="utf-8"))["graph"]

            _record("A")
            first = _leg(1)
            assert first == {"database": "fake-db", "graph_version": "shape-A",
                             "graph_census_sha256": "census-A",
                             "removed_tags_sha256": "A", "build_timestamp": "t-A",
                             "source_database": "parent-db"}
            _record("B")  # the same database name, rebuilt between the legs
            second = {"database": "fake-db", "graph_version": "shape-B",
                      "graph_census_sha256": "census-B",
                      "removed_tags_sha256": "B", "build_timestamp": "t-B",
                      "source_database": "parent-db"}
            assert _leg(2) == {"mixed_builds": [first, second]}

            # a torn prior manifest is an unknown build, never the current one
            (droot / "run" / "run_manifest.json").write_text("{torn",
                                                             encoding="utf-8")
            (droot / "run" / "arm_outputs.jsonl").unlink()
            assert _leg(2) == {"mixed_builds": [None, second]}
        finally:
            GRAPH_BUILD_DIR = saved

    em = build_eval_manifest({}, "herb", "fake", "src")
    assert (em.scorer, em.arm, em.source_run) == ("herb", "fake", "src")

    # the fake evaluator still satisfies run_one_evaluator's kw contract
    fake_eval = types.SimpleNamespace(
        __name__="eval.fake",
        score_outputs=lambda outs, ch, **kw: [
            EvalResult(q.id, q.type, "fake", "f1", 1.0, "ok", {}, None) for q in ch])
    assert len(run_one_evaluator(fake_eval, [o], qs, "fake")) == 2
    print("orchestrator self-check OK")


if __name__ == "__main__":
    _selfcheck()

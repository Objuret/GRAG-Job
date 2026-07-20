"""orchestrator.py — wires ONE pipeline + ONE evaluator over the chosen
questions and saves the result.

Why it's here: the run entry point. Also the home of the SHARED generator, so
every arm answers with the identical model (the fairness control). It routes
corpus -> pipeline and truth -> evaluator. No retrieval/scoring logic of its own
(the arms retrieve, the evaluators score).
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import abort
from progress import progress
import questions
from contract import (
    ArmOutput, EvalManifest, ModelUsage, RunManifest, generator_messages,
    generator_usage_from_nim, model_usage_from_dict, model_usage_from_telemetry,
)

_HERE = Path(__file__).parent
DEFAULT_CORPUS = _HERE / "data" / "corpus" / "Salesforce__HERB"
DEFAULT_OUTPUT = _HERE / "output"
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
GENERATOR_MODEL = "qwen/qwen3.5-397b-a17b"

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
                        "time": elapsed}

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
    set: a re-run skips these, so finished work is never redone or lost."""
    p = Path(records_path)
    if not p.is_file():
        return set()
    return {json.loads(x)["id"]
            for x in p.read_text(encoding="utf-8").splitlines() if x.strip()}


def _rehydrate(rec):
    """A persisted arm-output record (dict) -> contract.ArmOutput, so the scorer
    reads answers off disk rather than only this session's in-memory ones."""
    return ArmOutput(rec["answer"], rec["contexts"], rec["context_ids"],
                     rec["search_time_s"], model_usage_from_dict(rec["generator"]),
                     model_usage_from_dict(rec["retrieval"]))


def run_one_pipeline(pipeline, chosen, corpus, generate, out_dir, k=DEFAULT_TOP_K,
                     workers=DEFAULT_WORKERS,
                     max_consecutive_failures=MAX_CONSECUTIVE_FAILURES):
    """Prepare the arm once, then answer the questions concurrently, writing each
    answer to out_dir/arm_outputs.jsonl AS IT LANDS (flushed) — so a crash or an
    abort never loses finished work. Resumes by skipping ids already in that file.
    The model rate cap lives in nim.py, so `workers` only sets how many calls
    overlap.

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
        futures = [ex.submit(pipeline.answer_one_question,
                             to_arm_question(q), prepared, generate, k)
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
                fh.write(json.dumps(
                    {"id": q.id, "question": q.question, **asdict(out_obj)},
                    ensure_ascii=False) + "\n")
                fh.flush()  # durable per answer — a kill keeps what finished
                ran.append(q)
                consecutive = 0
    return ran, failures, aborted, getattr(prepared, "build_stats", None)


def run_one_evaluator(evaluator, outputs, chosen, arm="", corpus=None, results_path=None,
                      workers=1):
    """-> list[contract.EvalResult]. The arm label + corpus (so an evaluator can
    dereference gold citations to text), results_path (so the scorer writes each
    question's cells as they land — crash-safe + resumable), and workers (questions
    scored concurrently — the same knob generation uses) pass through.
    linked to: evaluator.score_outputs"""
    return evaluator.score_outputs(outputs, chosen, arm=arm, corpus=corpus,
                                   results_path=results_path, workers=workers)


def build_run_manifest(config, arm, build_stats, n_questions, n_ran, n_failed):
    """Provenance for the generation side -> contract.RunManifest (timestamp now,
    UTC). Records the run split (chosen / ran / failed) so the run folder is
    self-documenting — no need to count jsonl lines to see what failed."""
    return RunManifest(
        arm=arm,
        generator_model=(None if config.get("retrieval_only")
                         else config.get("generator_model", GENERATOR_MODEL)),
        top_k=config.get("top_k", DEFAULT_TOP_K),
        questions_file=str(config.get("questions_path") or questions.QUESTIONS),
        n_questions=n_questions,
        n_ran=n_ran,
        n_failed=n_failed,
        timestamp=datetime.now(timezone.utc).isoformat(),
        build_stats=build_stats,
    )


def build_eval_manifest(config, scorer, arm, source_run):
    """Provenance for the eval side -> contract.EvalManifest (timestamp now, UTC)."""
    return EvalManifest(
        scorer=scorer,
        judge_model=config.get("judge_model"),
        source_run=str(source_run),
        arm=arm,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _arm_name(module):
    """'pipelines.lucene' / 'eval.ragas' -> 'lucene' / 'ragas' (run + output label)."""
    return module.__name__.rsplit(".", 1)[-1]


def run(pipeline, evaluator, ids_file, config=None):
    """TOP ENTRY. Generation writes each answer to out_dir/arm_outputs.jsonl as it
    lands (resumable + crash-safe); then — unless the run aborts — the evaluator
    scores the FULL persisted set. Re-running with the same out_dir resumes: ids
    already on disk are skipped, the rest are answered and appended.
    -> {out_dir, n_questions, n_ran, n_failed, n_results}.
    linked to: all of the above; run.py is the CLI over this.
    """
    config = config or {}
    arm = _arm_name(pipeline)
    evname = _arm_name(evaluator) if evaluator is not None else "gen"

    chosen = load_chosen_questions(ids_file, config.get("questions_path"))
    corpus = open_corpus(config.get("corpus_root", DEFAULT_CORPUS))
    generate = build_shared_generator(config)
    out = Path(config.get("out_dir") or DEFAULT_OUTPUT / f"{arm}__{evname}")

    ran, _, aborted, build_stats = run_one_pipeline(
        pipeline, chosen, corpus, generate, out,
        config.get("top_k", DEFAULT_TOP_K), config.get("workers", DEFAULT_WORKERS))

    # run_one_pipeline wrote each answer to arm_outputs.jsonl and each failure to
    # failures.jsonl as they landed; here we only record provenance off the durable
    # files. Both counts read from disk so they reconcile across resumes:
    # n_ran + n_failed == n_questions (n_failed = chosen not yet answered).
    # A leg that generated nothing (an eval-only resume) leaves the manifest
    # alone — it describes the generation run, and its config (e.g. the
    # generator model) belongs to the leg that produced the answers.
    done = _done_ids(out / "arm_outputs.jsonl")
    n_failed = len(chosen) - len(done)
    manifest_path = out / "run_manifest.json"
    if ran or not manifest_path.is_file():
        manifest_path.write_text(
            json.dumps(asdict(build_run_manifest(
                config, arm, build_stats, len(chosen), len(done), n_failed)),
                ensure_ascii=False, indent=2), encoding="utf-8")

    if aborted:  # loud — but every finished answer is already on disk; resume continues
        raise RuntimeError(f"aborted run at {out}: {aborted}")

    if evaluator is None:  # arm run — answers only, no scoring
        return {"out_dir": str(out), "n_questions": len(chosen),
                "n_ran": len(done), "n_failed": n_failed}

    # eval scores the FULL persisted set, re-hydrating ArmOutput from the records
    # (so a resumed run scores everything, not just the last leg); truth joins by id.
    by_id = {q.id: q for q in chosen}
    recs = [json.loads(x) for x in
            (out / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    eval_path = out / "eval_results.jsonl"
    results = run_one_evaluator(
        evaluator, [_rehydrate(r) for r in recs], [by_id[r["id"]] for r in recs],
        arm, corpus, eval_path, config.get("workers", DEFAULT_WORKERS))
    config["judge_backend"] = getattr(evaluator, "LAST_JUDGE_BACKEND", None)
    config["judge_effort"] = getattr(evaluator, "LAST_JUDGE_REASONING_EFFORT", None)
    config["judge_usage"] = getattr(evaluator, "LAST_JUDGE_USAGE", None)
    config["judge_elapsed_s"] = getattr(evaluator, "LAST_JUDGE_WALL_TIME_S", None)
    (out / "eval_manifest.json").write_text(
        json.dumps(asdict(build_eval_manifest(config, evname, arm, out)),
                   ensure_ascii=False, indent=2), encoding="utf-8")
    # the evaluator wrote each question's cells to eval_path as they finished (resumable),
    # so count from disk — a resumed run reports the full set, not just this leg.
    n_results = (sum(1 for x in eval_path.read_text(encoding="utf-8").splitlines() if x.strip())
                 if eval_path.is_file() else len(results or []))
    return {"out_dir": str(out), "n_questions": len(chosen), "n_ran": len(done),
            "n_failed": n_failed, "n_results": n_results}


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

    # manifests carry the run split + provenance
    rm = build_run_manifest({}, "fake", prepared.build_stats, 10, 7, 3)
    assert rm.arm == "fake" and rm.generator_model == GENERATOR_MODEL
    assert (rm.n_questions, rm.n_ran, rm.n_failed) == (10, 7, 3)
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

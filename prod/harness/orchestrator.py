from __future__ import annotations

import json
import os
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from harness import abort
from harness import capture
from harness import fields
from harness import jsonl
from harness import provenance
from harness.progress import progress
from harness import questions
from harness.contract import (
    ArmOutput, EvalManifest, ModelUsage, RunManifest, generator_messages,
    generator_usage_from_chat, model_usage_from_dict, model_usage_from_telemetry,
)

_HERE = Path(__file__).parent.parent.parent
DEFAULT_CORPUS = _HERE / "data" / "corpus" / "Salesforce__HERB"
DEFAULT_OUTPUT = _HERE / "output"
GRAPH_BUILD_DIR = DEFAULT_OUTPUT / "graph_build"
CHUNKS_ROOT = DEFAULT_OUTPUT / "k=chunks"
CHARS_ROOT = DEFAULT_OUTPUT / "k=chars"
DEFAULT_TOP_K = 50
DEFAULT_WORKERS = 2
MAX_CONSECUTIVE_FAILURES = 10

GENERATOR_MODEL = "claude-sonnet-5"

_ANSWER_SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}


def load_chosen_questions(ids_file, questions_path=None):
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


def open_corpus(corpus_root):
    root = Path(corpus_root)
    if not (root / "products").is_dir():
        raise FileNotFoundError(f"no products/ under corpus root {root}")
    return root


# What the answer call asks of the model. The lane applies what the CLI and the model let it and
# records the rest as not applied (chat.call_settings): thinking off and the 8,192 cap go through;
# claude-sonnet-5 refuses any temperature; min_tokens has no counterpart in this lane.
_GENERATOR_SETTINGS = {
    "temperature": 0,
    "chat_template_kwargs": {"enable_thinking": False},
    "max_tokens": 8192,
    "min_tokens": 1,
}


def build_shared_generator(config):
    if config.get("retrieval_only"):
        return None

    from harness import chat
    model = config.get("generator_model", GENERATOR_MODEL)

    def generate(question, contexts):
        chat.reset_timing()
        t0 = time.perf_counter()
        resp = chat.post("/chat/completions", {
            "model": model,
            **_GENERATOR_SETTINGS,
            "messages": generator_messages(question, contexts),
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "answer", "schema": _ANSWER_SCHEMA},
            },
        }, timeout=480.0)
        elapsed = time.perf_counter() - t0
        transport = chat.take_timing()
        choices = resp.get("choices") or []
        if not choices:
            raise RuntimeError("generator returned no choices")
        content = (choices[0].get("message") or {}).get("content")
        if content is None:
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
        tokens_in, tokens_out = generator_usage_from_chat(resp.get("usage"))
        return answer, {"calls": 1, "tokens_in": tokens_in, "tokens_out": tokens_out,
                        "cached_input_tokens": int(
                            (resp.get("usage") or {}).get("cached_input_tokens") or 0),
                        "time": elapsed, **transport}

    return generate


def generator_info(config):
    """What every answer call of a run is given, once, for its manifest."""
    if config.get("retrieval_only"):
        return None
    from harness import chat
    model = config.get("generator_model", GENERATOR_MODEL)
    call = chat.call_settings({"model": model, **_GENERATOR_SETTINGS})
    return {"model": model,
            "system": generator_messages("", [])[0]["content"],
            "user_template": "Documents:\\n<the contexts, a blank line between them>"
                             "\\n\\nQuestion: <the question>",
            "schema": _ANSWER_SCHEMA,
            # asked is what the harness asks for; applied and not_applied say what the call carries
            "payload": dict(_GENERATOR_SETTINGS),
            "applied": call["applied"], "not_applied": call["not_applied"],
            "env_set": call["env_set"], "env_unset": call["env_unset"],
            "timeout_s": 480.0}


def to_arm_question(question):
    return question.id, question.question


def _done_ids(records_path):
    return {rec["id"] for rec in jsonl.iter_records(records_path)}


def _n_exhausted(records_path):
    return sum(1 for rec in jsonl.iter_records(records_path)
               if ((rec.get("meta") or {}).get("char_budget") or {}).get("exhausted"))


def _rehydrate(rec):
    return ArmOutput(rec["answer"], rec["contexts"], rec["context_ids"],
                     rec["search_time_s"], model_usage_from_dict(rec["generator"]),
                     model_usage_from_dict(rec["retrieval"]))


def run_one_pipeline(pipeline, chosen, corpus, generate, out_dir, k=DEFAULT_TOP_K,
                     workers=DEFAULT_WORKERS,
                     max_consecutive_failures=MAX_CONSECUTIVE_FAILURES,
                     char_budget=None, leg=None, telemetry=None):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    records_path = out / "arm_outputs.jsonl"
    failures_path = out / "failures.jsonl"
    jsonl.heal(records_path)
    jsonl.heal(failures_path)
    done = _done_ids(records_path)
    todo = [q for q in chosen if q.id not in done]

    p0 = time.perf_counter()
    prepared = pipeline.prepare_over_corpus(corpus)
    if telemetry is not None:
        telemetry.update(prepare_s=time.perf_counter() - p0, n_todo=len(todo),
                         prepared=prepared)
    extra = {} if char_budget is None else {"char_budget": char_budget}

    def _one(q):
        # one question = one run: everything it calls while this capture is open is kept
        cap, token = capture.start()
        try:
            out_obj = pipeline.answer_one_question(
                to_arm_question(q), prepared, generate, k, **extra)
        except BaseException as e:
            e.herb_capture = cap.close()
            raise
        finally:
            capture.stop(token)
        return out_obj, cap.close()

    ran, failures, aborted, consecutive = [], [], None, 0
    # failures.jsonl is appended, never wiped: a failed try and what it spent stay on record
    # across resumes; whether a question is still unanswered is the manifest's n_failed
    with records_path.open("a", encoding="utf-8") as fh, \
            failures_path.open("a", encoding="utf-8") as ffh, \
            ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futures = [ex.submit(_one, q) for q in todo]
        for q, fut in progress(list(zip(todo, futures)), desc="answering", unit="q"):
            if abort.aborted():
                for f in futures:
                    f.cancel()
                aborted = "user aborted (pressed q)"
                break
            try:
                out_obj, kept = fut.result()
            except abort.Aborted:
                for f in futures:
                    f.cancel()
                aborted = "user aborted (pressed q)"
                break
            except Exception as e:
                failures.append((q, repr(e)))
                ffh.write(json.dumps(
                    {"id": q.id, "error": repr(e),
                     "failed_at": datetime.now(timezone.utc).isoformat(), "leg": leg,
                     "traceback": "".join(traceback.format_exception(type(e), e, e.__traceback__)),
                     **(getattr(e, "herb_capture", None) or {})},
                    ensure_ascii=False, default=repr) + "\n")
                ffh.flush()
                os.fsync(ffh.fileno())
                consecutive += 1
                if consecutive >= max_consecutive_failures:
                    for f in futures:
                        f.cancel()
                    aborted = (f"{consecutive} consecutive failures "
                               f"(generation backend likely down) - last: {e!r}")
                    break
            else:
                fh.write(json.dumps(
                    {"id": q.id, "question": q.question,
                     "answered_at": datetime.now(timezone.utc).isoformat(),
                     **asdict(out_obj), "leg": leg, **kept},
                    ensure_ascii=False, default=repr) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
                ran.append(q)
                consecutive = 0
    return ran, failures, aborted, getattr(prepared, "build_stats", None)


def run_one_evaluator(evaluator, outputs, chosen, arm="", corpus=None, results_path=None,
                      workers=1, retrieval_only=False):
    return evaluator.score_outputs(outputs, chosen, arm=arm, corpus=corpus,
                                   results_path=results_path, workers=workers,
                                   retrieval_only=retrieval_only)


def graph_identity(database):
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
        flags=config.get("flags"),
        graph=graph_identity(config.get("graph_database")),
        code_version=config.get("code_version") or provenance.code_version(),
        environment=provenance.environment(),
        inputs=provenance.inputs(
            questions_file=config.get("questions_path") or questions.QUESTIONS,
            ids_file=config.get("ids_file"),
            corpus_root=config.get("corpus_root", DEFAULT_CORPUS)),
        legs=config.get("legs"),
        workers=config.get("workers"),
        lane=config.get("lane"),
        generator=config.get("generator_info"),
        index=config.get("index"),
        code_state=config.get("code_state"),
        env=provenance.settings_env(),
    )


def _accumulated_judge(prior, manifest):
    legs = list((prior or {}).get("judge_legs") or [])
    if not legs and prior and (prior.get("judge_usage") or prior.get("judge_elapsed_s")):
        legs.append({"timestamp": prior.get("timestamp"),
                     "judge_model": prior.get("judge_model"),
                     "judge_backend": prior.get("judge_backend"),
                     "usage": prior.get("judge_usage"),
                     "elapsed_s": prior.get("judge_elapsed_s"),
                     "settings": prior.get("judge_settings")})

    usage = manifest.judge_usage
    # every scoring leg is kept, a leg without a judge call too: its stamps, settings and
    # embedding work are part of what the evaluation cost
    if usage is not None and (usage.calls or manifest.judge_settings):
        legs.append({"timestamp": manifest.timestamp,
                     "judge_model": manifest.judge_model,
                     "judge_backend": manifest.judge_backend,
                     "usage": asdict(usage),
                     "elapsed_s": manifest.judge_elapsed_s,
                     "settings": manifest.judge_settings})

    if manifest.judge_model is None:
        # a start that made no judge call names no model: the one the kept scores were judged
        # by stands
        named = [leg.get("judge_model") for leg in legs if leg.get("judge_model")]
        manifest.judge_model = named[-1] if named else (prior or {}).get("judge_model")

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
        judge_settings=config.get("judge_settings"),
    )


def _arm_name(module):
    return module.__name__.rsplit(".", 1)[-1]


def _rewrite_fields(out):
    """FIELDS.md again, now that the folder holds its manifest. The one written at the start
    stands if this fails: the run's data is on disk and is not put at risk for it."""
    try:
        fields.write(out)
    except Exception as e:
        print(f"FIELDS.md was not rewritten ({e!r}); the one written at the start stands",
              flush=True)


def run(pipeline, evaluator, ids_file, config=None):
    config = dict(config or {})
    config.setdefault("ids_file", ids_file)
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

    # what the folder's files and fields mean, in the folder itself; written first, so a
    # start that cannot write it stops before it asks a model anything
    out.mkdir(parents=True, exist_ok=True)
    fields.write(out)

    # one leg per start or resume of this folder, so its time can be joined or discounted
    manifest_path = out / "run_manifest.json"
    try:
        prior_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        prior_manifest = None
    prior_legs = list((prior_manifest or {}).get("legs") or []) \
        if isinstance(prior_manifest, dict) else []
    leg_no = len(prior_legs) + 1
    leg_started, leg_t0, leg_cpu0 = capture.now(), time.perf_counter(), time.process_time()
    workers = config.get("workers", DEFAULT_WORKERS)
    config["workers"] = workers

    # the code this start runs on is read before it answers anything: read afterwards, an edit
    # made in the repo during the run would be recorded as the code that ran
    code_version = provenance.code_version()
    state = provenance.code_state()
    diff = state.pop("diff", None)
    if diff:
        # named by its hash: legs run on the same uncommitted code share one file. Written as
        # bytes, so the file's own sha256 is diff_sha256 and `git apply` takes it
        state["diff_file"] = f"code.{state['diff_sha256'][:16]}.diff"
        out.mkdir(parents=True, exist_ok=True)
        if not (out / state["diff_file"]).is_file():
            (out / state["diff_file"]).write_bytes(diff)

    telemetry = {}
    ran, _, aborted, build_stats = run_one_pipeline(
        pipeline, chosen, corpus, generate, out,
        config.get("top_k", DEFAULT_TOP_K), workers,
        char_budget=config.get("char_budget"), leg=leg_no, telemetry=telemetry)

    done = _done_ids(out / "arm_outputs.jsonl")
    n_failed = len(chosen) - len(done)
    n_exhausted = (None if config.get("char_budget") is None
                   else _n_exhausted(out / "arm_outputs.jsonl"))
    info = getattr(pipeline, "index_info", None)
    try:
        index = info(telemetry.get("prepared")) if callable(info) else None
    except Exception as e:
        index = {"error": repr(e)}
    if generate is not None or evaluator is not None:
        from harness import chat
        lane = chat.lane_info()
    else:
        lane = None
    from harness import embed
    leg = {"leg": leg_no, "started_at": leg_started, "finished_at": capture.now(),
           "wall_s": time.perf_counter() - leg_t0,
           "process_cpu_s": time.process_time() - leg_cpu0, "workers": workers,
           "argv": list(sys.argv), "pid": os.getpid(), "python_executable": sys.executable,
           "ids_file": None if ids_file is None else str(ids_file),
           "n_chosen": len(chosen), "n_todo": telemetry.get("n_todo"),
           "n_answered": len(ran), "n_unanswered_after": n_failed, "aborted": aborted,
           "prepare_s": telemetry.get("prepare_s"), "embedder_load_s": embed.LOAD_S,
           "retrieval_only": bool(config.get("retrieval_only")), "evaluator": evname,
           "peak_memory_bytes": provenance.peak_memory_bytes(),
           "code_version": code_version, "code_state": state,
           "flags": config.get("flags"), "lane": lane, "index": index}
    config.update(legs=prior_legs + [leg], lane=lane, index=index, code_state=state,
                  code_version=code_version, generator_info=generator_info(config))

    if ran or not manifest_path.is_file():
        manifest = build_run_manifest(
            config, arm, build_stats, len(chosen), len(done), n_failed, n_exhausted)
        if isinstance(prior_manifest, dict):
            manifest.graph = _merged_graph(prior_manifest.get("graph"), manifest.graph)
        elif manifest_path.is_file():
            manifest.graph = _merged_graph(None, manifest.graph)
        manifest_path.write_text(
            json.dumps(asdict(manifest), ensure_ascii=False, indent=2, default=repr),
            encoding="utf-8")
    elif isinstance(prior_manifest, dict):
        # nothing was answered in this leg: the manifest of the answers stands, the leg is added
        prior_manifest["legs"] = config["legs"]
        manifest_path.write_text(
            json.dumps(prior_manifest, ensure_ascii=False, indent=2, default=repr),
            encoding="utf-8")

    _rewrite_fields(out)
    if aborted:
        raise RuntimeError(f"aborted run at {out}: {aborted}")

    if evaluator is None:
        return {"out_dir": str(out), "n_questions": len(chosen),
                "n_ran": len(done), "n_failed": n_failed,
                "n_exhausted": n_exhausted}

    by_id = {q.id: q for q in chosen}
    recs = jsonl.load(out / "arm_outputs.jsonl")
    eval_path = out / "eval_results.jsonl"
    # a scoring leg that is cut short still writes its manifest: what it spent is not dropped
    results, cut_short = None, None
    try:
        results = run_one_evaluator(
            evaluator, [_rehydrate(r) for r in recs], [by_id[r["id"]] for r in recs],
            arm, corpus, eval_path, config.get("workers", DEFAULT_WORKERS),
            config.get("retrieval_only", False))
    except BaseException as e:
        cut_short = e
    config["judge_model"] = getattr(evaluator, "LAST_JUDGE_MODEL", None)
    config["judge_backend"] = getattr(evaluator, "LAST_JUDGE_BACKEND", None)
    config["judge_effort"] = getattr(evaluator, "LAST_JUDGE_REASONING_EFFORT", None)
    config["judge_usage"] = getattr(evaluator, "LAST_JUDGE_USAGE", None)
    config["judge_elapsed_s"] = getattr(evaluator, "LAST_JUDGE_WALL_TIME_S", None)
    config["judge_settings"] = getattr(evaluator, "LAST_JUDGE_SETTINGS", None)
    eval_manifest_path = out / "eval_manifest.json"
    eval_manifest = build_eval_manifest(config, evname, arm, out)
    prior = None
    if eval_manifest_path.is_file():
        try:
            prior = json.loads(eval_manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            prior = None
    # from the first scoring leg on: each leg is written with its own settings, so a later leg
    # never replaces what an earlier one ran under
    eval_manifest = _accumulated_judge(prior, eval_manifest)
    eval_manifest_path.write_text(
        json.dumps(asdict(eval_manifest), ensure_ascii=False, indent=2, default=repr),
        encoding="utf-8")
    _rewrite_fields(out)
    if cut_short is not None:
        raise cut_short
    n_results = (sum(1 for x in eval_path.read_text(encoding="utf-8").splitlines() if x.strip())
                 if eval_path.is_file() else len(results or []))
    return {"out_dir": str(out), "n_questions": len(chosen), "n_ran": len(done),
            "n_failed": n_failed, "n_exhausted": n_exhausted, "n_results": n_results}


def _selfcheck():
    import tempfile
    import threading
    import types
    from harness.contract import BuildStats, EvalResult, QuestionWithTruth

    prepared = types.SimpleNamespace(build_stats=BuildStats(0.1, ModelUsage(), []))
    seen = {}

    def fake_generate(text, contexts):
        seen["gen_text"] = text
        return "ans", {"calls": 1, "tokens_in": 3, "tokens_out": 4, "time": 0.0}

    def answer_one_question(q, prep, generate, k):
        assert isinstance(q, tuple) and len(q) == 2, f"truth not stripped: {q!r}"
        a, tel = generate(q[1], ["ctx"])
        return ArmOutput(a, ["ctx"], ["cit1"], 0.0,
                         model_usage_from_telemetry(tel), ModelUsage())

    fake = types.SimpleNamespace(
        __name__="arms.fake", prepare_over_corpus=lambda c: prepared,
        answer_one_question=answer_one_question)
    qs = [QuestionWithTruth(f"p::a::{i}", f"q{i}?", "person", ["eid_x"], ["cit1"])
          for i in range(2)]

    assert to_arm_question(qs[0]) == ("p::a::0", "q0?")

    def _rows(d, name="arm_outputs.jsonl"):
        return [json.loads(x) for x in
                (Path(d) / name).read_text(encoding="utf-8").splitlines()
                if x.strip()]

    with tempfile.TemporaryDirectory() as d:
        ran, fails, aborted, bs = run_one_pipeline(fake, qs, "c/", fake_generate, d, workers=1)
        assert aborted is None and [q.id for q in ran] == ["p::a::0", "p::a::1"] and fails == []
        assert bs is prepared.build_stats and seen["gen_text"] == "q1?"
        r = _rows(d)
        assert [x["id"] for x in r] == ["p::a::0", "p::a::1"] and r[0]["answer"] == "ans"
        assert "tokens_in" in r[0]["generator"] and "tokens_out" in r[0]["generator"]
        assert _rows(d, "failures.jsonl") == []

        ran2, _, _, _ = run_one_pipeline(fake, qs, "c/", fake_generate, d, workers=1)
        assert ran2 == [] and len(_rows(d)) == 2

    with tempfile.TemporaryDirectory() as d:
        q3 = [QuestionWithTruth(f"o::a::{i}", f"o{i}?", "person", [], []) for i in range(3)]

        def slow(q, prep, generate, k):
            idx = int(q[0].rsplit("::", 1)[1])
            time.sleep(0.02 * (3 - idx))
            return ArmOutput(q[0], [], [], 0.0, ModelUsage(), ModelUsage())

        sp = types.SimpleNamespace(__name__="arms.slow",
                                   prepare_over_corpus=lambda c: prepared, answer_one_question=slow)
        run_one_pipeline(sp, q3, "c/", fake_generate, d, workers=3)
        assert [x["id"] for x in _rows(d)] == ["o::a::0", "o::a::1", "o::a::2"]

    with tempfile.TemporaryDirectory() as d:
        def dead(q, prep, generate, k):
            raise RuntimeError("lane down")

        dp = types.SimpleNamespace(__name__="arms.dead",
                                   prepare_over_corpus=lambda c: prepared, answer_one_question=dead)
        many = [QuestionWithTruth(f"d::a::{i}", f"d{i}?", "person", [], []) for i in range(20)]
        _, _, aborted, _ = run_one_pipeline(dp, many, "c/", fake_generate, d, workers=2,
                                            max_consecutive_failures=3)
        assert aborted and "consecutive failures" in aborted
        assert not (Path(d) / "arm_outputs.jsonl").read_text(encoding="utf-8").strip()
        f = _rows(d, "failures.jsonl")
        assert f and all("lane down" in x["error"] for x in f)

    with tempfile.TemporaryDirectory() as d:
        calls, clk = {"n": 0}, threading.Lock()

        def slow_dead(q, prep, generate, k):
            with clk:
                calls["n"] += 1
            time.sleep(0.03)
            raise RuntimeError("lane down")

        sdp = types.SimpleNamespace(__name__="arms.sdead",
                                    prepare_over_corpus=lambda c: prepared,
                                    answer_one_question=slow_dead)
        big = [QuestionWithTruth(f"s::a::{i}", f"s{i}?", "person", [], []) for i in range(60)]
        _, _, ab, _ = run_one_pipeline(sdp, big, "c/", fake_generate, d, workers=4,
                                       max_consecutive_failures=6)
        assert ab and calls["n"] <= 24, calls["n"]

    o = ArmOutput("a", ["c"], ["id1"], 1.0,
                  ModelUsage(calls=1, tokens_in=1, tokens_out=2, time_s=3.0), ModelUsage())
    assert _rehydrate({"id": "x", "question": "q", **asdict(o)}) == o

    with tempfile.TemporaryDirectory() as d:
        got = {}

        def budget_arm(q, prep, generate, k, char_budget=None):
            got["char_budget"] = char_budget
            return ArmOutput("a", ["ctx"], ["cit1"], 0.0, ModelUsage(), ModelUsage())

        bp = types.SimpleNamespace(__name__="arms.budget",
                                   prepare_over_corpus=lambda c: prepared,
                                   answer_one_question=budget_arm)
        run_one_pipeline(bp, qs[:1], "c/", fake_generate, d, workers=1, char_budget=9)
        assert got["char_budget"] == 9

    rm = build_run_manifest({}, "fake", prepared.build_stats, 10, 7, 3)
    assert rm.arm == "fake" and rm.generator_model == GENERATOR_MODEL
    assert rm.interpreter_model is None
    assert rm.char_budget is None
    assert rm.graph is None
    assert (rm.n_questions, rm.n_ran, rm.n_failed) == (10, 7, 3)
    assert build_run_manifest({"char_budget": 72000}, "fake",
                              prepared.build_stats, 1, 1, 0).char_budget == 72000

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
            assert _graph_of("bare-db") == {
                "database": "bare-db", "graph_version": None,
                "graph_census_sha256": None, "removed_tags_sha256": None,
                "build_timestamp": None, "source_database": None}
            (built / "build_manifest.json").write_text("{broken", encoding="utf-8")
            assert _graph_of("eval-v9") == {
                "database": "eval-v9", "graph_version": None,
                "graph_census_sha256": None, "removed_tags_sha256": None,
                "build_timestamp": None, "source_database": None}
        finally:
            GRAPH_BUILD_DIR = saved

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
    assert _merged_graph(None, ga) == {"mixed_builds": [None, ga]}
    for malformed in ({"mixed_builds": []}, {"mixed_builds": "A"}, {"mixed_builds": 7}):
        assert _merged_graph(malformed, ga) == {"mixed_builds": [None, ga]}

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
                __name__="arms.graphfake", DATABASE="fake-db",
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
            _record("B")
            second = {"database": "fake-db", "graph_version": "shape-B",
                      "graph_census_sha256": "census-B",
                      "removed_tags_sha256": "B", "build_timestamp": "t-B",
                      "source_database": "parent-db"}
            assert _leg(2) == {"mixed_builds": [first, second]}

            (droot / "run" / "run_manifest.json").write_text("{torn",
                                                             encoding="utf-8")
            (droot / "run" / "arm_outputs.jsonl").unlink()
            assert _leg(2) == {"mixed_builds": [None, second]}
        finally:
            GRAPH_BUILD_DIR = saved

    em = build_eval_manifest({}, "herb", "fake", "src")
    assert (em.scorer, em.arm, em.source_run) == ("herb", "fake", "src")

    fake_eval = types.SimpleNamespace(
        __name__="eval.fake",
        score_outputs=lambda outs, ch, **kw: [
            EvalResult(q.id, q.type, "fake", "f1", 1.0, "ok", {}, None) for q in ch])
    assert len(run_one_evaluator(fake_eval, [o], qs, "fake")) == 2
    print("orchestrator self-check OK")


if __name__ == "__main__":
    _selfcheck()

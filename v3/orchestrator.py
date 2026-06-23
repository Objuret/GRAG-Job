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
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import questions
from contract import EvalManifest, RunManifest

_HERE = Path(__file__).parent
DEFAULT_CORPUS = _HERE / "data" / "corpus" / "Salesforce__HERB"
DEFAULT_OUTPUT = _HERE / "output"
DEFAULT_TOP_K = 10

# The shared generator: Mistral Large on NVIDIA NIM. ONE model, built once here
# and injected into every arm, so the only variable across arms is retrieval,
# never the LLM. Transport is nim.post (NIM speaks the OpenAI REST API).
GENERATOR_MODEL = "mistralai/mistral-large-3-675b-instruct-2512"

# ponytail: the answer instructions are a tunable knob, NOT settled design. Kept
# minimal + explicit — grounded QA plus a fixed abstention string for HERB's
# unanswerables. Tune the wording / abstention token once the scorers land and
# the user signs off the generation contract.
_SYSTEM = (
    "You answer the question using ONLY the numbered context passages. "
    "If the passages do not contain the answer, reply exactly: I don't know. "
    "Be concise and factual. Never invent ids, names, URLs, or numbers."
)


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
    """Ids from a jsonl id-set file (output/question_ids.jsonl, gold100.jsonl):
    each non-blank line is a JSON object carrying an "id". Order preserved; a
    line that isn't such an object fails loud, naming file + line + content."""
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
    """Build the ONE generator (Mistral Large on NIM) injected into every arm.
    Returns a callable generate(question_text, contexts) -> (answer, telemetry),
    where telemetry = {calls, tokens, time} fills the arm's generator ModelUsage.
    `config['retrieval_only']` -> None (smoke: retrieval without generation).
    linked to: every arm's answer_one_question (the `generate` argument)
    """
    if config.get("retrieval_only"):
        return None

    import nim

    nim.require_key()  # fail loud now, before the run starts — not mid-loop
    model = config.get("generator_model", GENERATOR_MODEL)

    def generate(question, contexts):
        ctx = "\n\n".join(f"[{i + 1}] {c}" for i, c in enumerate(contexts)) or "(none)"
        t0 = time.perf_counter()
        resp = nim.post("/chat/completions", {
            "model": model,
            "temperature": 0,  # deterministic — eval reproducibility
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": f"Context:\n{ctx}\n\nQuestion: {question}"},
            ],
        })
        elapsed = time.perf_counter() - t0
        tokens = int((resp.get("usage") or {}).get("total_tokens", 0) or 0)
        choices = resp.get("choices") or []
        if not choices:
            raise RuntimeError("generator returned no choices")
        content = (choices[0].get("message") or {}).get("content")
        if content is None:  # length cap / filter / tool turn — never a silent null answer
            raise RuntimeError(
                f"generator returned null content "
                f"(finish_reason={choices[0].get('finish_reason')})"
            )
        return content, {"calls": 1, "tokens": tokens, "time": elapsed}

    return generate


# --- run ---------------------------------------------------------------------

def to_arm_question(question):
    """Strip the truth: hand the arm the question's id + text ONLY, as the (id,
    text) tuple the arms accept. The quarantine, in code — ground_truth/citations
    are physically not in what the arm receives.
    linked to: pipeline.answer_one_question
    """
    return question.id, question.question


def run_one_pipeline(pipeline, chosen, corpus, generate, k=DEFAULT_TOP_K):
    """Prepare the arm once, then per question: to_arm_question -> answer.
    -> (list[contract.ArmOutput], contract.BuildStats).
    linked to: pipeline.prepare_over_corpus + pipeline.answer_one_question
    """
    prepared = pipeline.prepare_over_corpus(corpus)
    outputs = [
        pipeline.answer_one_question(to_arm_question(q), prepared, generate, k)
        for q in chosen
    ]
    return outputs, getattr(prepared, "build_stats", None)


def run_one_evaluator(evaluator, outputs, chosen):
    """-> list[contract.EvalResult]. linked to: evaluator.score_outputs"""
    return evaluator.score_outputs(outputs, chosen)


def build_run_manifest(config, arm, build_stats, n_questions):
    """Provenance for the generation side -> contract.RunManifest (timestamp now, UTC)."""
    return RunManifest(
        arm=arm,
        generator_model=(None if config.get("retrieval_only")
                         else config.get("generator_model", GENERATOR_MODEL)),
        top_k=config.get("top_k", DEFAULT_TOP_K),
        questions_file=str(config.get("questions_path") or questions.QUESTIONS),
        n_questions=n_questions,
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


def save_run(arm_outputs, eval_results, run_manifest, eval_manifest, out_dir):
    """Persist arm outputs + eval results + both manifests under out_dir. Raw
    per-record jsonl, nothing pre-aggregated, nothing dropped.
    linked to: output/ ; contract.RunManifest / EvalManifest
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out / "arm_outputs.jsonl", (asdict(o) for o in arm_outputs))
    # eval_results may be None while the evaluators are still stubs — record [].
    _write_jsonl(out / "eval_results.jsonl", (asdict(r) for r in (eval_results or [])))
    (out / "run_manifest.json").write_text(
        json.dumps(asdict(run_manifest), ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "eval_manifest.json").write_text(
        json.dumps(asdict(eval_manifest), ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def _write_jsonl(path, rows):
    with Path(path).open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def _arm_name(module):
    """'pipelines.lucene' / 'eval.herb' -> 'lucene' / 'herb' (run + output label)."""
    return module.__name__.rsplit(".", 1)[-1]


def run(pipeline, evaluator, ids_file, config=None):
    """TOP ENTRY: load questions -> open corpus -> build generator -> run the arm
    -> run the evaluator -> save. -> {out_dir, n_questions, n_results}.
    linked to: all of the above; smoke.run_smoke calls a trimmed version.
    """
    config = config or {}
    arm, evname = _arm_name(pipeline), _arm_name(evaluator)

    chosen = load_chosen_questions(ids_file, config.get("questions_path"))
    corpus = open_corpus(config.get("corpus_root", DEFAULT_CORPUS))
    generate = build_shared_generator(config)

    outputs, build_stats = run_one_pipeline(
        pipeline, chosen, corpus, generate, config.get("top_k", DEFAULT_TOP_K))
    results = run_one_evaluator(evaluator, outputs, chosen)

    out_dir = config.get("out_dir") or DEFAULT_OUTPUT / f"{arm}__{evname}"
    run_manifest = build_run_manifest(config, arm, build_stats, len(chosen))
    eval_manifest = build_eval_manifest(config, evname, arm, out_dir)
    save_run(outputs, results, run_manifest, eval_manifest, out_dir)
    return {"out_dir": str(out_dir), "n_questions": len(chosen),
            "n_results": len(results or [])}


# --- self-check --------------------------------------------------------------

def _selfcheck():
    """Wiring check with fake arm/evaluator/generator — no NIM, no bm25s, no disk
    questions. Verifies the truth quarantine, the once-prepare-then-loop routing,
    and the save round-trip."""
    import tempfile
    import types
    from contract import ArmOutput, BuildStats, EvalResult, ModelUsage, QuestionWithTruth

    qs = [QuestionWithTruth(f"p::a::{i}", f"q{i}?", "person", ["eid_x"], ["cit1"])
          for i in range(2)]

    seen = {}

    def fake_generate(text, contexts):
        seen["gen_text"] = text  # the arm must pass ONLY the question text
        return "ans", {"calls": 1, "tokens": 7, "time": 0.0}

    prepared = types.SimpleNamespace(build_stats=BuildStats(0.1, ModelUsage(), []))

    def answer_one_question(q, prep, generate, k):
        assert isinstance(q, tuple) and len(q) == 2, f"truth not stripped: {q!r}"
        a, tel = generate(q[1], ["ctx"])
        return ArmOutput(a, ["ctx"], ["cit1"], 0.0,
                         ModelUsage(tel["calls"], tel["tokens"], tel["time"]), ModelUsage())

    fake_pipeline = types.SimpleNamespace(
        __name__="pipelines.fake",
        prepare_over_corpus=lambda corpus: prepared,
        answer_one_question=answer_one_question)
    fake_eval = types.SimpleNamespace(
        __name__="eval.fake",
        score_outputs=lambda outs, ch: [
            EvalResult(q.id, q.type, "fake", "f1", 1.0, "ok", {}, None) for q in ch])

    # quarantine: the stripped question is a bare (id, text) tuple, no truth on it
    assert to_arm_question(qs[0]) == ("p::a::0", "q0?")

    outs, bs = run_one_pipeline(fake_pipeline, qs, "corpus/", fake_generate, k=5)
    assert len(outs) == 2 and bs is prepared.build_stats
    assert seen["gen_text"] == "q1?"  # generator saw only question text

    results = run_one_evaluator(fake_eval, outs, qs)
    rm = build_run_manifest({}, _arm_name(fake_pipeline), bs, len(qs))
    em = build_eval_manifest({}, _arm_name(fake_eval), _arm_name(fake_pipeline), "src")
    assert rm.arm == "fake" and rm.generator_model == GENERATOR_MODEL and rm.n_questions == 2
    assert em.scorer == "fake" and em.arm == "fake"

    with tempfile.TemporaryDirectory() as d:
        out = save_run(outs, results, rm, em, d)
        rows = (out / "arm_outputs.jsonl").read_text(encoding="utf-8").strip().splitlines()
        assert len(rows) == 2 and json.loads(rows[0])["answer"] == "ans"
        meta = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
        assert meta["build_stats"]["build_time_s"] == 0.1
    print("orchestrator self-check OK")


if __name__ == "__main__":
    _selfcheck()

"""ragas.py — multidimensional answer/evidence quality via the RAGAS library.

Scores each (arm output, question) on the metrics ragas_catalog.metrics_to_run()
selects: the deterministic backbone (id-based context precision/recall, n-gram and
string scores) plus the judged metrics (faithfulness, answer relevance, the LLM/NV
context metrics, factual correctness, ...). Judge = the shared Qwen on NIM;
embedder = llama-nemotron-embed on NIM — both through nim.post, the same transport every other
model call in the harness uses. Emits raw per-question contract.EvalResult (tidy
long), one row per (question, metric); nothing pre-aggregated.

Built on RAGAS's legacy metric classes (ragas.metrics). The newer
ragas.metrics.collections API is an architectural rewrite still missing the id-based
and non-LLM context metrics — the exact, judge-free retrieval scores the gold
citations make possible, which are the headline retrieval signal. Pin ragas==0.4.3
so the legacy implementation is frozen and reproducible.

References (the evaluation library + its metric definitions — the canonical RAGAS
sources; consult these for any RAGAS question, not blogs):
  - Es, S., James, J., Espinosa-Anke, L. & Schockaert, S. (2024). RAGAs: Automated
    Evaluation of Retrieval Augmented Generation. Proc. EACL 2024: System
    Demonstrations, 150-158. doi:10.18653/v1/2024.eacl-demo.16 ; arXiv:2309.15217 —
    the framework and its reference-free faithfulness / answer-relevance /
    context-relevance metrics.
  - Official docs (metric definitions; matches the pinned ragas==0.4.3 behaviour):
    https://docs.ragas.io
      Context Precision — mean of Precision@k over the retrieved list (no separate
      @k cutoff parameter; the list length IS K, so cut the list to score at depth):
      https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/
      Context Recall:
      https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_recall/
  - NVIDIA metrics (AnswerAccuracy / ContextRelevance / ResponseGroundedness), the
    ragas._nv_metrics used here:
      https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/nvidia_metrics/
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
import warnings
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

import abort
import nim
from progress import progress
from contract import EvalResult
from eval.ragas_catalog import metrics_to_run

# The decided eval model stack: the shared Qwen generator doubles as the judge,
# llama-nemotron-embed is the dense embedder — same models, same NIM transport as the arms.
JUDGE_MODEL = "qwen/qwen3.5-397b-a17b"
EMBED_MODEL = "nvidia/llama-nemotron-embed-1b-v2"
JUDGE_TIMEOUT_S = max(120.0, float(os.environ.get("RAGAS_JUDGE_TIMEOUT_S", "120")))
JUDGE_MAX_TRIES = max(3, int(os.environ.get("RAGAS_JUDGE_MAX_TRIES", "3")))
EMBED_TIMEOUT_S = float(os.environ.get("RAGAS_EMBED_TIMEOUT_S", "45"))
EMBED_MAX_TRIES = int(os.environ.get("RAGAS_EMBED_MAX_TRIES", "1"))
MAX_JUDGE_CONTEXT_CHARS = int(os.environ.get("RAGAS_MAX_JUDGE_CONTEXT_CHARS", "60000"))

# Eval circuit breaker: N consecutive questions with most NIM-pass cells errored means
# the judge backend is down — stop loud rather than grind the rest into NaNs; whatever an
# outage touches re-scores on resume. High enough that a short outage passes under it and
# only a sustained one trips. (A judge-side or full outage trips it; an embedder-only
# outage errors just 2 of the 5 cells, so it won't — those NaNs re-score on resume.)
MAX_CONSECUTIVE_FAILED_QUESTIONS = 10

# RAGAS's specific metric classes sit behind a deprecation shim (its public future is
# ragas.metrics.collections, which lacks the id-based retrieval metrics). Silence the
# shim warning; the version is pinned so the legacy path is stable.
warnings.filterwarnings(
    "ignore", message=r"Importing .* from 'ragas\.metrics' is deprecated",
    category=DeprecationWarning)

from langchain_core.outputs import Generation, LLMResult  # noqa: E402
from ragas.dataset_schema import SingleTurnSample  # noqa: E402
from ragas.embeddings.base import BaseRagasEmbeddings  # noqa: E402
from ragas.llms.base import BaseRagasLLM  # noqa: E402
from ragas.run_config import RunConfig  # noqa: E402
from ragas.metrics import (  # noqa: E402
    AnswerCorrectness,
    BleuScore,
    ChrfScore,
    ContextEntityRecall,
    ExactMatch,
    Faithfulness,
    FactualCorrectness,
    IDBasedContextPrecision,
    IDBasedContextRecall,
    LLMContextPrecisionWithoutReference,
    LLMContextPrecisionWithReference,
    LLMContextRecall,
    NonLLMContextPrecisionWithReference,
    NonLLMContextRecall,
    NonLLMStringSimilarity,
    NoiseSensitivity,
    ResponseRelevancy,
    RougeScore,
    SemanticSimilarity,
    StringPresence,
)
from ragas.metrics._nv_metrics import (  # noqa: E402
    AnswerAccuracy,
    ContextRelevance,
    ResponseGroundedness,
)


# --- NIM-backed judge + embedder (RAGAS drivers over nim.post) ----------------


@dataclass
class _NimJudge(BaseRagasLLM):
    """RAGAS LLM driven by nim.post — the shared Qwen, same transport as the
    generator. Implements the three BaseRagasLLM hooks; structured-output parsing is
    RAGAS's own (it appends format instructions to the prompt)."""

    model: str = JUDGE_MODEL

    def _post(self, text, temperature, stop):
        resp = nim.post("/chat/completions", {
            "model": self.model,
            "temperature": float(temperature),
            # enable_thinking is NIM's authoritative thinking switch (it overrides the
            # /no_think prompt token); off keeps the verdict a direct structured 0/1.
            "chat_template_kwargs": {"enable_thinking": False},
            # Output budget for the verdict JSON; NIM's low default truncates it and the
            # RAGAS parser then fails the cell. The 262k context has room.
            "max_tokens": 4096,
            # Force >=1 generated token; this model otherwise emits end-of-turn as token 1
            # for some prompts, yielding an empty verdict.
            "min_tokens": 1,
            "messages": [{"role": "user", "content": text}],
            **({"stop": stop} if stop else {}),
        }, timeout=JUDGE_TIMEOUT_S, max_tries=JUDGE_MAX_TRIES,
            give_up_after_s=JUDGE_TIMEOUT_S * JUDGE_MAX_TRIES)
        choices = resp.get("choices") or []
        content = (choices[0].get("message") or {}).get("content") if choices else None
        finish = choices[0].get("finish_reason") if choices else "no choices"
        return resp, content, finish

    def _verdict(self, text, temperature, stop):
        # Retry on empty content: the model occasionally leaks into thinking mode even
        # with enable_thinking=False, emitting reasoning_content but zero content tokens.
        # min_tokens=1 doesn't prevent it (NIM counts reasoning tokens toward the
        # minimum); a fresh call usually escapes the leak.
        for _ in range(3):
            resp, content, finish = self._post(text, float(temperature or 0), stop)
            if content and content.strip():
                return content
        usage = resp.get("usage") or {}
        message = (resp.get("choices") or [{}])[0].get("message") or {}
        raise RuntimeError(
            f"NIM judge returned empty content (finish_reason={finish}, "
            f"completion_tokens={usage.get('completion_tokens')}, message_keys={sorted(message)})")

    def _complete(self, text, n, temperature, stop):
        return LLMResult(generations=[[
            Generation(text=self._verdict(text, temperature, stop)) for _ in range(max(1, n))]])

    def generate_text(self, prompt, n=1, temperature=1e-8, stop=None, callbacks=None):
        return self._complete(prompt.to_string(), n, temperature, stop)

    async def agenerate_text(self, prompt, n=1, temperature=1e-8, stop=None, callbacks=None):
        # A direct, blocking NIM call. Each question owns its event loop and runs one
        # sequential metric chain, so the loop has nothing else to advance — blocking it
        # here makes an eval worker hit NIM exactly like a generation worker (a plain
        # nim.post in its pool thread), instead of bouncing every call through a second
        # executor thread. The worker pool still gives cross-question concurrency; the
        # shared pacer still bounds the rate.
        return self._complete(prompt.to_string(), n, temperature, stop)

    def is_finished(self, response) -> bool:
        return True


class _NimEmbedder(BaseRagasEmbeddings):
    """RAGAS embeddings driven by nim.post — llama-nemotron-embed, asymmetric: questions embed
    as "query", contexts as "passage" (the side matters for retrieval-QA)."""

    def __init__(self, model: str = EMBED_MODEL, run_config: RunConfig = None):
        super().__init__()
        self.model = model
        self.run_config = run_config or RunConfig()

    def _embed(self, texts, input_type):
        resp = nim.post("/embeddings", {
            "model": self.model,
            "input": [t or " " for t in texts],
            "input_type": input_type,
            "truncate": "NONE",
        }, timeout=EMBED_TIMEOUT_S, max_tries=EMBED_MAX_TRIES,
            give_up_after_s=EMBED_TIMEOUT_S * EMBED_MAX_TRIES)
        data = resp.get("data")
        if not data:
            raise RuntimeError(f"NIM /embeddings returned no data (keys={list(resp)})")
        return [d["embedding"] for d in sorted(data, key=lambda d: d.get("index", 0))]

    def embed_query(self, text):
        return self._embed([text], "query")[0]

    def embed_documents(self, texts):
        return self._embed(texts, "passage")

    async def aembed_query(self, text):
        return self.embed_query(text)        # direct blocking call — see _NimJudge.agenerate_text

    async def aembed_documents(self, texts):
        return self.embed_documents(texts)


# --- catalog name -> RAGAS class + what it needs ------------------------------

_LLM, _EMB = "llm", "emb"

_REGISTRY = {
    "context_precision_id":      (IDBasedContextPrecision, ()),
    "context_recall_id":         (IDBasedContextRecall, ()),
    "context_precision_nonllm":  (NonLLMContextPrecisionWithReference, ()),
    "context_recall_nonllm":     (NonLLMContextRecall, ()),
    "context_precision_llm":     (LLMContextPrecisionWithoutReference, (_LLM,)),
    "context_precision_llm_ref": (LLMContextPrecisionWithReference, (_LLM,)),
    "context_recall_llm":        (LLMContextRecall, (_LLM,)),
    "context_entity_recall":     (ContextEntityRecall, (_LLM,)),
    "context_relevance_nv":      (ContextRelevance, (_LLM,)),
    "noise_sensitivity":         (NoiseSensitivity, (_LLM,)),
    "faithfulness":              (Faithfulness, (_LLM,)),
    "answer_relevancy":          (ResponseRelevancy, (_LLM, _EMB)),
    "response_groundedness_nv":  (ResponseGroundedness, (_LLM,)),
    "answer_accuracy_nv":        (AnswerAccuracy, (_LLM,)),
    "factual_correctness":       (FactualCorrectness, (_LLM,)),
    "answer_correctness":        (AnswerCorrectness, (_LLM, _EMB)),
    "semantic_similarity":       (SemanticSimilarity, (_EMB,)),
    "string_similarity":         (NonLLMStringSimilarity, ()),
    "bleu":                      (BleuScore, ()),
    "rouge":                     (RougeScore, ()),
    "chrf":                      (ChrfScore, ()),
    "exact_match":               (ExactMatch, ()),
    "string_presence":           (StringPresence, ()),
}

# These LLM metrics judge each retrieved context independently — ~one model call per
# context (so ~k calls/question). They get their own pass, run last, so they never hold
# up the cheap metrics.
_PER_CONTEXT = {"context_precision_llm", "context_precision_llm_ref"}
_CONTEXT_HEAVY_LLM = {
    "context_precision_llm",
    "context_precision_llm_ref",
    "context_recall_llm",
    "context_relevance_nv",
    "faithfulness",
    "response_groundedness_nv",
}


def _build_metrics(names, judge, embedder, run_config):
    """Instantiate each selected metric with the wrappers it needs, then init() it —
    RAGAS's lifecycle step (run by evaluate(), which we bypass by calling
    single_turn_ascore directly). init() wires sub-components RAGAS builds lazily there,
    e.g. AnswerCorrectness's AnswerSimilarity from the embedder, and stamps the run
    config; without it those stay unset and the metric asserts. A name with no builder is
    a hard failure (ragas_catalog drifted from this registry)."""
    built = {}
    for name in names:
        if name not in _REGISTRY:
            raise KeyError(
                f"no RAGAS builder for metric {name!r} — ragas_catalog.metrics_to_run "
                "lists a metric ragas.py doesn't map")
        cls, needs = _REGISTRY[name]
        kw = {}
        if _LLM in needs:
            kw["llm"] = judge
        if _EMB in needs:
            kw["embeddings"] = embedder
        metric = cls(**kw)
        metric.init(run_config)
        built[name] = metric
    return built


# --- sample construction ------------------------------------------------------

_ARTIFACT_TYPES = ("slack", "documents", "meeting_transcripts", "meeting_chats", "urls", "prs")


def _string_leaves(value) -> str:
    """Every string leaf of an artifact record, joined — a faithful text rendering of
    the artifact for the gold-context-text metrics. Arm-agnostic on purpose (the
    string-sim metrics only need comparable gold text, not an arm's exact rendering)."""
    parts: list = []

    def walk(v):
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, dict):
            for w in v.values():
                walk(w)
        elif isinstance(v, list):
            for w in v:
                walk(w)

    walk(value)
    return " ".join(parts).strip()


def corpus_gold_text(corpus_root) -> dict:
    """artifact id -> its text. The non-LLM context metrics score retrieved text
    against gold *context text*, so the gold citation ids must dereference to text.
    The evaluator may read the corpus for this — it is scoring against truth, not
    retrieving. First occurrence of an id wins (ids are globally unique in HERB).
    linked to: _to_sample (fills reference_contexts)"""
    root = Path(corpus_root)
    out: dict = {}
    for pf in sorted((root / "products").glob("*.json")):
        data = json.loads(pf.read_text(encoding="utf-8"))
        for kind in _ARTIFACT_TYPES:
            for rec in data.get(kind, []) or []:
                aid = rec.get("id")
                if aid is None or aid in out:
                    continue
                out[aid] = _string_leaves(rec)
    return out


def _to_sample(out, q, gold_text) -> SingleTurnSample:
    """One contract pair -> a RAGAS SingleTurnSample. reference = the gold answer
    (joined); reference_context_ids = gold citations; reference_contexts = those
    citations' text (when the corpus was supplied)."""
    gold = [str(g) for g in (q.ground_truth or [])]
    cites = [str(c) for c in (q.citations or [])]
    ref_ctx = [gold_text[c] for c in cites if c in gold_text]
    return SingleTurnSample(
        user_input=q.question,
        response=out.answer or "",
        retrieved_contexts=list(out.contexts or []),
        retrieved_context_ids=[str(c) for c in (out.context_ids or [])],
        reference=" ".join(gold),
        reference_context_ids=cites,
        reference_contexts=ref_ctx or None,
    )


# --- scoring ------------------------------------------------------------------

def score_outputs(outputs, questions, arm="", corpus=None, results_path=None, workers=1):
    """ENTRY: per (output, question) score every metric in metrics_to_run() ->
    list[contract.EvalResult] (one row per question per metric). judge = Qwen on
    NIM, embedder = llama-nemotron-embed on NIM. `corpus` (root path) lets the gold-context-text
    metrics dereference citations to text; the orchestrator supplies it.

    `workers` scores that many questions concurrently (the same knob generation uses);
    every call still funnels through nim.py's one shared rate cap, so concurrency only
    overlaps the model latency, it never bursts past the limit.

    If `results_path` is given, each question's full set of cells is appended there and
    flushed the moment that question finishes — so a crash or q-abort keeps every
    finished question, and a re-run over the same path skips the questions already
    scored (the eval resumes, like generation does). The return is this leg's rows.
    linked to: orchestrator.run_one_evaluator; ragas_catalog.metrics_to_run"""
    # nim.post owns retry + the global rate-limit backoff; cap RAGAS's own retry at a
    # single attempt so it never stacks its default 10x on top of each judge/embed call.
    # That nesting turned one 429 into minutes of dead retries and, under concurrency,
    # starved the shared pacer so parallel ran slower than serial.
    run_config = RunConfig(max_retries=1)
    judge, embedder = _NimJudge(run_config=run_config), _NimEmbedder(run_config=run_config)
    metrics = _build_metrics(metrics_to_run(), judge, embedder, run_config)
    print(f"ragas judge: {JUDGE_MODEL} timeout={JUDGE_TIMEOUT_S:g}s tries={JUDGE_MAX_TRIES}")
    gold_text = corpus_gold_text(corpus) if corpus else {}
    results = _score_all(outputs, questions, arm, metrics, gold_text,
                         results_path, workers)
    _print_status_summary(results)
    return results


def _load_rows(results_path) -> list:
    """Parsed rows already in results_path. A torn trailing line from a killed write
    is dropped (that question re-scores on resume); a non-trailing parse error is real
    corruption and raises loud."""
    p = Path(results_path) if results_path else None
    if not p or not p.is_file():
        return []
    lines = [x for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    rows = []
    for i, x in enumerate(lines):
        try:
            rows.append(json.loads(x))
        except json.JSONDecodeError:
            if i == len(lines) - 1:
                break  # torn last line from a killed write — drop it, re-score that q
            raise
    return rows


def _check_judge_context_budget(outputs, questions, metrics) -> None:
    """Context-heavy judged metrics concatenate all retrieved contexts into one prompt."""
    heavy = sorted(set(metrics) & _CONTEXT_HEAVY_LLM)
    if not heavy or MAX_JUDGE_CONTEXT_CHARS <= 0:
        return

    sizes = [
        (getattr(q, "id", "?"),
         sum(len(c or "") for c in (getattr(out, "contexts", None) or [])),
         len(getattr(out, "contexts", None) or []))
        for out, q in zip(outputs, questions)
    ]
    over = [row for row in sizes if row[1] > MAX_JUDGE_CONTEXT_CHARS]
    if not over:
        return

    over.sort(key=lambda row: row[1], reverse=True)
    worst = "\n".join(
        f"  {qid}: {n_ctx} contexts, {chars:,} chars"
        for qid, chars, n_ctx in over[:8]
    )
    print(
        "ragas warning: context-heavy judged metrics will create huge k50 judge prompts.\n"
        f"metrics: {', '.join(heavy)}\n"
        f"warning threshold: {MAX_JUDGE_CONTEXT_CHARS:,} retrieved-context chars per question\n"
        f"over-threshold questions: {len(over)}/{len(sizes)}\n"
        f"{worst}\n"
        "continuing the run; this is expected to be slow."
    )


def _score_all(outputs, questions, arm, metrics, gold_text, results_path=None,
               workers=1) -> list:
    """Score every (question, metric) cell -> list[EvalResult], in ordered passes: the
    deterministic metrics first (no model call — instant, the id-based retrieval scores are
    the headline signal), then the cheap NIM judge/embed metrics, then the per-context
    metrics last (~1 call per retrieved context — the slow tail), so every cheap score
    lands before the slow pass grinds alone. An abort or throttle still leaves every
    finished pass on disk, and a pass only touches the metrics it owns.
    Each pass scores up to `workers` questions at once, one per thread — each in its OWN
    event loop (asyncio.run), because RAGAS bridges sync<->async with nest_asyncio and
    sharing one running loop across questions deadlocks it. The shared nim.py pacer (a
    threading lock) caps the call rate across the threads; the main thread collects each
    question as it finishes and writes it (no write lock), so the bar tracks real completion.

    Resume (results_path): tracked per CELL. A (question, metric) is done only if it has an
    ok row on disk; errored or missing cells re-score, and ONLY those — never an already-ok
    cell, even when a pass-mate of it failed. The compaction below keeps every ok cell and
    drops the rest. Each errored cell is also appended live to eval_failures.jsonl (truncated
    fresh each leg) so failures can be watched mid-run, like generation's."""
    passes = [(lbl, m) for lbl, m in (
        ("scoring - offline (free)",
         {n: m for n, m in metrics.items() if _REGISTRY[n][1] == ()}),
        ("scoring - judge + embed (NIM)",
         {n: m for n, m in metrics.items() if _REGISTRY[n][1] != () and n not in _PER_CONTEXT}),
        ("scoring - context precision (1 call/context, slow)",
         {n: m for n, m in metrics.items() if n in _PER_CONTEXT}),
    ) if m]
    prior = _load_rows(results_path)
    selected = set(metrics)
    # Resume is per CELL: a (question, metric) is done only if it has an ok row for a
    # still-selected metric. Build the ok-cell set per question and, in the same pass, the
    # rows to keep (each selected ok cell, once). Errored, missing, duplicate, and
    # now-deselected cells all fall away — re-scored if still selected, else just dropped.
    done_ok = defaultdict(set)
    kept = []
    for r in prior:
        if (r["status"] != "ok" or r["metric"] not in selected
                or r["metric"] in done_ok[r["question_id"]]):
            continue
        done_ok[r["question_id"]].add(r["metric"])
        kept.append(r)

    if results_path and len(kept) != len(prior):
        # keep every selected ok cell; drop the rest. Atomic temp+rename so a crash
        # mid-rewrite can't lose kept rows.
        dst = Path(results_path)
        tmp = dst.with_name(dst.name + ".tmp")
        tmp.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept), encoding="utf-8")
        os.replace(tmp, dst)

    sample_of = {q.id: (q, _to_sample(out, q, gold_text))
                 for out, q in zip(outputs, questions)
                 if selected - done_ok[q.id]}

    fh = open(results_path, "a", encoding="utf-8") if results_path else None
    ffh = (open(Path(results_path).parent / "eval_failures.jsonl", "w", encoding="utf-8")
           if results_path else None)
    results = []

    def _score_question(q, sample, todo, on_cell):
        """Score this question's still-needed metrics (`todo`: name -> metric) in this
        worker thread's OWN event loop, ticking the bar as each cell lands — so progress
        tracks real work, not whole-question completions that bunch up under many workers."""
        async def _go():
            rows = []
            for name, metric in todo.items():
                value, status, comp = await _score_one(metric, sample)
                rows.append(EvalResult(q.id, q.type, arm, name, value, status, comp, None))
                on_cell()
            return rows
        return asyncio.run(_go())

    def _run_pass(pass_metrics, pass_samples, label) -> str:
        """Score this pass's questions, up to `workers` at a time in a thread pool,
        writing each question's rows the moment it FINISHES. The cheap passes tick the
        bar per cell as each metric lands; the per-context pass tracks NIM calls (one
        cell is ~k calls, so even per-cell would crawl). Either way the bar moves within
        seconds, not when whole questions bunch up. Rows are self-identifying by
        question_id, so the file is free to follow completion order.
        -> 'ok' | 'user_abort' | 'backend_down'."""
        if not pass_metrics or not pass_samples:
            return "ok"
        # The per-context metrics make ~one judge call per retrieved context, so a single
        # question is ~k calls before its one cell lands — a per-cell bar would sit at 0%
        # for minutes. For that pass, size and drive the bar by NIM calls instead, so it
        # climbs every couple seconds; other passes stay per-cell with a call-count postfix.
        per_context = bool(set(pass_metrics) & _PER_CONTEXT)
        if per_context:
            expected_calls = sum(len(s.retrieved_contexts or []) * len(todo) for _, s, todo in pass_samples)
            bar = progress(total=max(1, expected_calls), desc=label, unit="call")
        else:
            bar = progress(total=sum(len(todo) for _, _, todo in pass_samples), desc=label, unit="cell")
        bar_lock = threading.Lock()

        def _tick_cell():  # per-context: the heartbeat drives the bar by NIM calls instead
            if not per_context:
                with bar_lock:
                    bar.update(1)

        start_calls, stop = nim.completed_calls(), threading.Event()

        def _heartbeat():
            while not stop.wait(1.0):
                with bar_lock:
                    done = nim.completed_calls() - start_calls
                    if per_context:
                        bar.n = min(bar.total, done)
                        bar.refresh()
                    else:
                        bar.set_postfix_str(f"{done} nim calls", refresh=True)

        threading.Thread(target=_heartbeat, daemon=True).start()
        consecutive_failed, outcome = 0, None
        try:
            with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
                futs = [ex.submit(_score_question, q, sample, todo, _tick_cell)
                        for q, sample, todo in pass_samples]
                for fut in as_completed(futs):
                    if abort.aborted():
                        for f in futs:
                            f.cancel()
                        outcome = "user_abort"
                        bar.write("[q] eval aborted - every finished question is saved")
                        break
                    try:
                        rows = fut.result()  # an unexpected raise (e.g. disk full) propagates loud
                    except abort.Aborted:  # q pressed mid-fan-out — stop; this q writes no cell
                        for f in futs:
                            f.cancel()
                        outcome = "user_abort"
                        bar.write("[q] eval aborted - every finished question is saved")
                        break
                    if ffh:
                        for r in rows:
                            if r.status == "error":
                                ffh.write(json.dumps(
                                    {"question_id": r.question_id, "metric": r.metric,
                                     "error": (r.components or {}).get("error", "")},
                                    ensure_ascii=False) + "\n")
                        ffh.flush()  # live — errored cells show up the moment they land
                    if fh:
                        fh.write("".join(json.dumps(asdict(r), ensure_ascii=False) + "\n" for r in rows))
                        fh.flush()  # whole question at once — durable + resumable
                    results.extend(rows)
                    # circuit breaker: a question with most cells errored counts as failed;
                    # that many in a row means the backend is down.
                    errored_cells = sum(1 for r in rows if r.status == "error")
                    consecutive_failed = consecutive_failed + 1 if errored_cells * 2 >= len(rows) else 0
                    if consecutive_failed >= MAX_CONSECUTIVE_FAILED_QUESTIONS:
                        for f in futs:
                            f.cancel()
                        outcome = "backend_down"
                        bar.write(f"[abort] {consecutive_failed} questions in a row mostly errored "
                                  "- judge/embed backend likely down")
                        break
        finally:
            stop.set()
            if per_context and outcome is None:  # finished clean — show the full bar
                with bar_lock:
                    bar.n = bar.total
                    bar.refresh()
            bar.close()
        return outcome or "ok"

    try:
        status = "ok"
        for label, pass_metrics in passes:
            pass_samples = []
            for q in questions:
                if q.id not in sample_of:
                    continue
                todo = {n: m for n, m in pass_metrics.items() if n not in done_ok[q.id]}
                if todo:
                    pass_samples.append((q, sample_of[q.id][1], todo))
            status = _run_pass(pass_metrics, pass_samples, label)
            if status != "ok":
                break
    finally:
        if fh:
            fh.close()
        if ffh:
            ffh.close()
    # fail loud like the generation leg — finished questions are on disk, resume continues.
    if status == "user_abort":
        raise RuntimeError("eval aborted (pressed q) - finished questions saved; resume to continue")
    if status == "backend_down":
        raise RuntimeError(
            f"eval stopped: {MAX_CONSECUTIVE_FAILED_QUESTIONS} questions in a row mostly errored "
            "(judge/embed backend likely down) - finished questions saved, resume when it recovers")
    return results


def _print_status_summary(results):
    """One line per metric that produced any non-ok cell, so failures are visible at
    a glance instead of buried in the jsonl."""
    bad = Counter((r.metric, r.status) for r in results if r.status != "ok")
    if not bad:
        print(f"ragas: all {len(results)} cells ok")
        return
    print("ragas non-ok cells:")
    for (metric, status), n in sorted(bad.items()):
        print(f"  {metric:<26} {status:<6} x{n}")


async def _score_one(metric, sample) -> tuple:
    """Score one metric on one sample. A per-cell failure is recorded LOUD (status +
    message in the row), not swallowed — one metric erroring on one item must not sink
    the other 22 x N. The caller surfaces the error tally."""
    try:
        value = float(await metric.single_turn_ascore(sample))
    except abort.Aborted:
        raise  # control flow, not a scored failure — unwinds the pass, writes no cell
    except Exception as e:
        return float("nan"), "error", {"error": f"{type(e).__name__}: {e}"}
    if value != value:  # NaN: the metric ran but produced no number for this item
        return value, "nan", {}
    return value, "ok", {}

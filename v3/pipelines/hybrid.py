"""hybrid.py — late-fusion baseline: the lucene (BM25) and vector (dense) arms
combined into one ranking.

Why it's here: a hybrid-retrieval control arm — the standard sparse+dense blend
the artefact's structured retrieval is also measured against.

Composition, not reimplementation: this arm owns no index and no scoring of its
own. It prepares BOTH baseline arms over the same corpus, asks each for its ranked
(id, score) list per question, and fuses those two rankings. BM25 lives in
lucene.py, dense cosine in vector.py; neither is touched here.

In -> out: question -> lucene ranked (id, bm25) + vector ranked (id, cosine),
each over-fetched -> min-max fusion -> top-k artifact ids -> shared generator ->
answer.

Fusion: each arm's scores min-max to [0, 1] over its own returned list, and the
fused score is ALPHA * vector_norm + (1 - ALPHA) * lucene_norm. An id is a candidate
only through an arm carrying positive weight, so ALPHA (env HERB_HYBRID_ALPHA,
default 0.5) is the weight on the dense arm: 1.0 ranks on the vector arm alone, 0.0
on the lucene arm alone, a value between fuses both arms' union.

Retrieval unit = one whole HERB artifact under its native `id` — the units both
baseline arms return — so `context_ids` land in the same id space as the gold
citations (which the citation-based context metrics compare against).

Contract fit: prepare returns a Prepared holding both arms' Prepared indexes and a
contract.BuildStats that sums the two builds; answer_one_question returns a
contract.ArmOutput. The question is read for its `id` + `question` ONLY —
ground_truth / citations are never touched.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Callable, Optional

from contract import ArmOutput, BuildStats, ModelUsage, unpack_generation


def _env_float(name: str, default: float) -> float:
    """A run-tunable coefficient read from the environment, `default` when unset or
    blank. A non-numeric value fails loud rather than silently reverting."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


# Fusion weight on the dense arm: ALPHA 1.0 ranks on the vector arm alone, 0.0 on
# the lucene arm alone, 0.5 an even blend. Read once at import so a run documents
# and sweeps its own value.
ALPHA = _env_float("HERB_HYBRID_ALPHA", 0.5)
if not 0.0 <= ALPHA <= 1.0:
    raise ValueError(f"HERB_HYBRID_ALPHA must be in [0, 1], got {ALPHA!r}")

# Each arm is over-fetched to this multiple of k, so the fusion has candidates one
# arm can lift past the other's pure top-k.
OVERFETCH = 4
DEFAULT_TOP_K = 10

# Manifest provenance: the fusion weight, recorded by the runner in run_manifest.json.
RETRIEVAL_FLAGS = {"HERB_HYBRID_ALPHA": ALPHA}

# The shared generator the orchestrator injects (fairness control); handed straight
# to the shared unpack_generation, exactly as the baseline arms do.
Generator = Callable[[str, list], object]


@dataclass
class Prepared:
    """Handle returned by prepare(); fed back into answer_one_question. Holds each
    baseline arm's own Prepared index plus the summed BuildStats for run provenance."""

    lucene: object
    vector: object
    build_stats: Optional[BuildStats] = None


# --- prepare -----------------------------------------------------------------

def _sum_usage(*usages: ModelUsage) -> ModelUsage:
    """Add ModelUsage fields across arms (calls / tokens / time)."""
    total = ModelUsage()
    for u in usages:
        total.calls += u.calls
        total.tokens_in += u.tokens_in
        total.cached_input_tokens += u.cached_input_tokens
        total.tokens_out += u.tokens_out
        total.reasoning_tokens += u.reasoning_tokens
        total.time_s += u.time_s
    return total


def prepare_over_corpus(corpus) -> Prepared:
    """Uniform prepare entry the orchestrator drives: build BOTH baseline indexes
    over the same corpus and hold them side by side. Each arm reads and indexes the
    corpus with its own code; the fusion adds no index of its own. The BuildStats is
    the two arms' summed — build time, embedder cost, and model ids together.
    linked to: lucene.prepare_over_corpus + vector.prepare_over_corpus
    """
    from pipelines import lucene, vector

    print("hybrid: building lucene index", flush=True)
    lucene_prepared = lucene.prepare_over_corpus(corpus)
    print("hybrid: building vector index", flush=True)
    vector_prepared = vector.prepare_over_corpus(corpus)

    lb, vb = lucene_prepared.build_stats, vector_prepared.build_stats
    build_stats = BuildStats(
        build_time_s=lb.build_time_s + vb.build_time_s,
        model=_sum_usage(lb.model, vb.model),
        models=list(lb.models) + list(vb.models),
    )
    return Prepared(lucene=lucene_prepared, vector=vector_prepared, build_stats=build_stats)


# --- fuse --------------------------------------------------------------------

def _qid_text(question) -> tuple:
    """(id, question_text) from a QuestionWithTruth, dict, (id, text) tuple, or a
    bare string. Reads ONLY id + question — truth fields are never touched."""
    if hasattr(question, "question") and hasattr(question, "id"):
        return question.id, question.question
    if isinstance(question, dict):
        return question.get("id", ""), question.get("question", "")
    if isinstance(question, (tuple, list)) and len(question) == 2:
        return question[0], question[1]
    return "", str(question)


def _minmax(scores: dict) -> dict:
    """Min-max one arm's scores to [0, 1] over its own returned ids. One distinct
    value (or a single id) maps every id to 1.0; an empty pool stays empty."""
    if not scores:
        return {}
    lo, hi = min(scores.values()), max(scores.values())
    if hi == lo:
        return {i: 1.0 for i in scores}
    span = hi - lo
    return {i: (s - lo) / span for i, s in scores.items()}


def fuse(lucene_ranked: list, vector_ranked: list, alpha: float, k: int) -> list:
    """Late-fuse the two arms' ranked (id, score) lists into the top-k artifact ids,
    best first. Each arm's scores min-max to [0, 1] over its own returned list; the
    fused score is alpha * vector_norm + (1 - alpha) * lucene_norm, an id in one arm
    only carrying just that arm's term.

    An id is a candidate only through an arm carrying positive weight, so an arm
    zeroed out contributes none of its ids: alpha 1.0 ranks on the vector arm alone,
    0.0 on the lucene arm alone (each exactly that arm's ranking), a value between
    fuses both arms' union. Ties break on the id (ascending), so the order is
    deterministic."""
    vector_norm = _minmax(dict(vector_ranked))
    lucene_norm = _minmax(dict(lucene_ranked))
    ids = set()
    if alpha > 0.0:
        ids |= set(vector_norm)
    if alpha < 1.0:
        ids |= set(lucene_norm)
    fused = {i: alpha * vector_norm.get(i, 0.0) + (1.0 - alpha) * lucene_norm.get(i, 0.0)
             for i in ids}
    return sorted(fused, key=lambda i: (-fused[i], i))[:k]


# --- answer ------------------------------------------------------------------

def answer_one_question(
    question, prepared: Prepared, generate: Optional[Generator], k: int = DEFAULT_TOP_K
) -> ArmOutput:
    """ENTRY: retrieve from both arms -> fuse -> ids + text -> generate -> ArmOutput.

    `generate` is the SHARED generator injected by the orchestrator so generation is
    identical across arms. If None (retrieval-only smoke), the answer is left empty
    and model telemetry is zero.
    linked to: orchestrator; lucene/vector retrieve_top_k_units; shared `generate`
    """
    from pipelines import lucene, vector

    _, text = _qid_text(question)
    fetch = OVERFETCH * k

    t0 = time.perf_counter()
    lucene_units = lucene.retrieve_top_k_units(question, prepared.lucene, fetch)
    vector_units, retrieval = vector.retrieve_top_k_units(question, prepared.vector, fetch)
    # search_time_s is both arms' in-process retrieval; the vector query-embed wall
    # (offline here) lives in `retrieval`, subtracted out to keep this comparable to
    # the baseline arms' pure search time.
    search_time_s = (time.perf_counter() - t0) - retrieval.time_s

    lucene_ranked = [(u["id"], u["score"]) for u in lucene_units]
    vector_ranked = [(u["id"], u["score"]) for u in vector_units]
    context_ids = fuse(lucene_ranked, vector_ranked, ALPHA, k)

    # One text per fused id, taken from the arm's own reader — the vector arm's when
    # both retrieved it. Every fused id is in the union, so the lookup never misses.
    text_by_id = {u["id"]: u["text"] for u in lucene_units}
    text_by_id.update({u["id"]: u["text"] for u in vector_units})
    contexts = [text_by_id[i] for i in context_ids]

    if generate is None:
        answer, gen_usage = "", ModelUsage()
    else:
        g0 = time.perf_counter()
        result = generate(text, contexts)
        answer, gen_usage = unpack_generation(result, time.perf_counter() - g0)

    return ArmOutput(
        answer=answer,
        contexts=contexts,
        context_ids=context_ids,
        search_time_s=search_time_s,
        generator=gen_usage,
        retrieval=retrieval,  # summed retrieval-time model cost — lucene: none, vector: the query embed
    )

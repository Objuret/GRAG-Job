from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Callable, Optional

from harness.contract import ArmOutput, BuildStats, ModelUsage, unpack_generation


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


ALPHA = _env_float("HERB_HYBRID_ALPHA", 0.5)
if not 0.0 <= ALPHA <= 1.0:
    raise ValueError(f"HERB_HYBRID_ALPHA must be in [0, 1], got {ALPHA!r}")

OVERFETCH = 4
DEFAULT_TOP_K = 10

RETRIEVAL_FLAGS = {"HERB_HYBRID_ALPHA": ALPHA}

Generator = Callable[[str, list], object]


@dataclass
class Prepared:

    lucene: object
    vector: object
    build_stats: Optional[BuildStats] = None


def _sum_usage(*usages: ModelUsage) -> ModelUsage:
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
    from arms import lucene, vector

    if lucene.METADATA_ON or vector.METADATA_ON:
        raise RuntimeError(
            "HERB_BASELINE_METADATA is set: this arm fuses on the unit id and puts the "
            "fused ids straight into context_ids, so a directory record would enter the "
            "citation id space. The fusion's own handling of a directory unit is not "
            "designed; run the lucene and vector arms directly.")

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


def _qid_text(question) -> tuple:
    if hasattr(question, "question") and hasattr(question, "id"):
        return question.id, question.question
    if isinstance(question, dict):
        return question.get("id", ""), question.get("question", "")
    if isinstance(question, (tuple, list)) and len(question) == 2:
        return question[0], question[1]
    return "", str(question)


def _minmax(scores: dict) -> dict:
    if not scores:
        return {}
    lo, hi = min(scores.values()), max(scores.values())
    if hi == lo:
        return {i: 1.0 for i in scores}
    span = hi - lo
    return {i: (s - lo) / span for i, s in scores.items()}


def fuse(lucene_ranked: list, vector_ranked: list, alpha: float, k: int) -> list:
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


def answer_one_question(
    question, prepared: Prepared, generate: Optional[Generator], k: int = DEFAULT_TOP_K
) -> ArmOutput:
    from arms import lucene, vector

    _, text = _qid_text(question)
    fetch = OVERFETCH * k

    t0 = time.perf_counter()
    lucene_units = lucene.retrieve_top_k_units(question, prepared.lucene, fetch)
    vector_units, retrieval = vector.retrieve_top_k_units(question, prepared.vector, fetch)
    search_time_s = (time.perf_counter() - t0) - retrieval.time_s

    lucene_ranked = [(u["id"], u["score"]) for u in lucene_units]
    vector_ranked = [(u["id"], u["score"]) for u in vector_units]
    context_ids = fuse(lucene_ranked, vector_ranked, ALPHA, k)

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
        retrieval=retrieval,
    )

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from artefact.index import (
    PreparedIndex,
    chunk_artifact_ids,
    load_artefact_index,
    resolve_chunk_text,
)
from artefact.interpreter import interpret
from harness.contract import ArmOutput, BuildStats, ModelUsage, unpack_generation
from harness.embed import EMBED_MODEL, _embed

log = logging.getLogger("arms.artefact")

DEFAULT_TOP_K = 10
PRODUCT_LITERAL_BOOST = 1.0
TODAY = "2026-06-28"

Generator = Callable[[str, list], object]


@dataclass
class Prepared:

    index: PreparedIndex
    data_root: Path
    key_path: Path
    build_stats: Optional[BuildStats] = None


_KEY_PATH = Path(__file__).resolve().parent.parent / "artefact" / "keys" / "Salesforce__HERB.yaml"


def prepare_over_corpus(corpus) -> Prepared:
    corpus_root = Path(corpus)
    data_root = corpus_root.parent
    t0 = time.perf_counter()
    index = load_artefact_index(data_root, _KEY_PATH)
    build_stats = BuildStats(
        build_time_s=time.perf_counter() - t0,
        model=ModelUsage(),
        models=[EMBED_MODEL],
    )
    return Prepared(index=index, data_root=data_root, key_path=_KEY_PATH, build_stats=build_stats)


def _qid_text(question) -> tuple:
    if hasattr(question, "question") and hasattr(question, "id"):
        return question.id, question.question
    if isinstance(question, dict):
        return question.get("id", ""), question.get("question", "")
    if isinstance(question, (tuple, list)) and len(question) == 2:
        return question[0], question[1]
    return "", str(question)


def _embed_facet_phrases(phrases: list[str]) -> tuple:
    if not phrases:
        return np.zeros((0, 0), dtype=np.float32), 0, 0, 0, 0.0
    return _embed(phrases, "query", bar=False)


def _phrase_weights(index: PreparedIndex, query_vecs: "np.ndarray") -> "np.ndarray":
    if query_vecs.shape[0] == 0:
        return np.zeros(index.matrix.shape[0], dtype=np.float32)
    q = query_vecs.astype(np.float32) - index.mean_vector.astype(np.float32)
    norms = np.linalg.norm(q, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    q = q / norms
    scores = index.matrix @ q.T
    return scores.max(axis=1).astype(np.float32)


def _chunk_scores(index: PreparedIndex, phrase_weight: "np.ndarray") -> "np.ndarray":
    scores = np.zeros(len(index.chunk_ids), dtype=np.float32)
    for j, rows in enumerate(index.chunk_tag_rows):
        if rows:
            scores[j] = float(phrase_weight[rows].sum())
    return scores


def _apply_literal_boosts(index: PreparedIndex, chunk_score: "np.ndarray",
                          literals: list) -> "np.ndarray":
    boosted = chunk_score.copy()
    for lit in literals:
        if lit.get("polarity") != "wanted" or lit.get("kind") != "product":
            continue
        name = (lit.get("token") or "").strip()
        if not name:
            continue
        needle = f"products/{name}.json"
        for j, cid in enumerate(index.chunk_ids):
            chunk = index.chunks_by_id.get(cid)
            if chunk is not None and needle in chunk.relpath:
                boosted[j] += PRODUCT_LITERAL_BOOST
    return boosted


def retrieve_top_k_chunks(question, prepared: Prepared, k: int = DEFAULT_TOP_K) -> tuple:
    _, text = _qid_text(question)
    t0 = time.perf_counter()
    interp, interp_usage = interpret(text, current_date=TODAY)
    interp_time = float(interp_usage.get("time", 0.0))
    interp_tokens = int(interp_usage.get("tokens", 0) or 0)

    qmat, emb_calls, emb_in, emb_out, emb_time = _embed_facet_phrases(interp["facet_phrases"])

    phrase_weight = _phrase_weights(prepared.index, qmat)
    base = _chunk_scores(prepared.index, phrase_weight)
    boosted = _apply_literal_boosts(prepared.index, base, interp.get("literals", []))

    k_eff = min(k, len(prepared.index.chunk_ids))
    if k_eff <= 0:
        return [], interp, interp_usage, (emb_calls, emb_in, emb_out, emb_time), 0.0
    top = np.argsort(-boosted, kind="stable")[:k_eff]
    chunks = [prepared.index.chunks_by_id[prepared.index.chunk_ids[int(i)]] for i in top]
    retrieve_wall = time.perf_counter() - t0
    return chunks, interp, interp_usage, (emb_calls, emb_in, emb_out, emb_time), retrieve_wall


def answer_one_question(
    question, prepared: Prepared, generate: Optional[Generator], k: int = DEFAULT_TOP_K
) -> ArmOutput:
    _, text = _qid_text(question)

    chunks, interp, interp_usage, emb_telem, retrieve_wall = retrieve_top_k_chunks(
        question, prepared, k)

    if interp.get("answer_shape") == "aggregate":
        log.warning(
            "answer_shape=aggregate for question %r — aggregation path not built; "
            "returning top-k chunks (the cap cuts, no structured aggregation)",
            _qid_text(question)[0])

    doc_cache: dict = {}
    context_ids: list[str] = []
    seen: set[str] = set()
    contexts: list[str] = []
    for chunk in chunks:
        for aid in chunk_artifact_ids(chunk, prepared.data_root, cache=doc_cache):
            if aid not in seen:
                seen.add(aid)
                context_ids.append(aid)
        contexts.append(resolve_chunk_text(chunk, prepared.data_root, cache=doc_cache))

    interp_time = float(interp_usage.get("time", 0.0))
    interp_in = int(interp_usage.get("tokens_in", 0) or 0)
    interp_out = int(interp_usage.get("tokens_out", 0) or 0)
    if not interp_in and not interp_out:
        legacy = int(interp_usage.get("tokens", 0) or 0)
        interp_in, interp_out = legacy, 0
    emb_calls, emb_in, emb_out, emb_time = emb_telem
    search_time_s = max(0.0, retrieve_wall - interp_time - emb_time)
    retrieval_usage = ModelUsage(
        calls=1 + int(emb_calls),
        tokens_in=interp_in + int(emb_in),
        tokens_out=interp_out + int(emb_out),
        time_s=interp_time + float(emb_time),
    )

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
        retrieval=retrieval_usage,
    )

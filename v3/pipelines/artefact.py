"""artefact.py — the ARTEFACT arm: interpreter → facet-channel retrieval → answer.

The system under test. The query engine fuses three already-built pieces — the
in-memory tag index (`artefact.index.PreparedIndex`), the query interpreter
(`artefact.interpreter.interpret`), and the literal pre-pass
(`artefact.prepass.prepass`) — into a working retrieval arm scored against the
lucene + vector baselines.

Retrieval math (pass 1 — corpus-relative geometry, DESIGN §13/§14):

  1. `interpret(prompt)` → `facet_phrases` (the graded cluster centers) +
     `literals` + `date_range` + `answer_shape`.
  2. Embed `facet_phrases` as `input_type="query"` (nv-embedqa's asymmetric
     query side) → `Q ∈ [n_facets, d]`, L2-normalised.
  3. Mean-center the query against the corpus mean carried by the index:
     `Q_c = Q - mean_vector`, then re-L2-normalise — the same transform the
     tag matrix went through at load, so query and tags share one geometry.
  4. Cosine of every tag phrase against every facet phrase:
     `S = matrix_centered @ Q_c.T` → `[n_phrases, n_facets]`. A phrase's
     weight is its MAX cosine across the facet phrases (one pooled facet set
     in pass 1; per-facet-axis splitting is a later build step):
     `phrase_weight[i] = max_j S[i, j]`.
  5. Chunk score = ACCUMULATE (DESIGN §14.3 — accumulate, not max) the phrase
     weights over the chunk's tag rows: `chunk_score[j] = Σ_{i∈tag_rows[j]}
     phrase_weight[i]`. No per-chunk-size normalisation in pass 1 — the cap
     already bounds chunk-size variance, and a true size control needs the
     §14.3 sweep's evidence first.

Structural boosts (pass 1 — minimal; DESIGN §14.4: NO hard filters anywhere,
boosts only, the cap cuts):

  - For each `literals` entry with `polarity=wanted` and `kind=product`,
    add a fixed `+1.0` to every chunk whose `relpath` contains
    `products/<name>.json`. Additive (not multiplicative) so non-matching
    chunks are not zeroed — a multiplicative boost on a zero semantic score
    would be a hard filter in disguise. The magnitude (~1.0) is roughly one
    strong facet-phrase match, so a named product lifts its file's chunks
    above the semantic floor without erasing it.
  - `excluded` literals get NO boost (never a removal — §14.4).
  - `person` / `org` literals have no chunk-attribute join yet — they ride
    the semantic layer (the facet_phrases carry the name in context).
  - `date_range` is logged but not applied (chunk date attributes aren't
    extracted yet).
  - `answer_shape=aggregate` is logged but still returns top-k chunks — the
    aggregation path is a later build step.

`context_ids` come from `artefact.index.chunk_artifact_ids` (each retrieved
chunk → the artifact `id` of every record its refs cover, deduped) — same id
space the gold citations and the other arms' context_ids use, so RAGAS's
citation-based metrics compare like-for-like.

Contract fit (mirrors vector/lucene): `prepare_over_corpus(corpus) -> Prepared`
loads the artefact index once and returns a `Prepared` carrying it +
`BuildStats`; `answer_one_question(question, prepared, generate, k) ->
ArmOutput` runs the combinator + the shared generator per question. The
question is read for `id` + `question` ONLY — truth fields are never touched.
"""
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
from contract import ArmOutput, BuildStats, ModelUsage, unpack_generation
from pipelines.vector import EMBED_MODEL, _embed

log = logging.getLogger("pipelines.artefact")

DEFAULT_TOP_K = 10
PRODUCT_LITERAL_BOOST = 1.0
TODAY = "2026-06-28"  # the run's reference date; relative date phrases resolve against it

Generator = Callable[[str, list], object]


@dataclass
class Prepared:
    """Handle returned by prepare(); fed back into answer_one_question.
    Carries the loaded `PreparedIndex` + the `BuildStats` for run provenance +
    the `data_root` the resolver needs to turn retrieved chunks into artifact
    ids and source text."""

    index: PreparedIndex
    data_root: Path
    key_path: Path
    build_stats: Optional[BuildStats] = None


# --- prepare ------------------------------------------------------------------

_KEY_PATH = Path(__file__).resolve().parent.parent / "artefact" / "keys" / "Salesforce__HERB.yaml"


def prepare_over_corpus(corpus) -> Prepared:
    """Load the artefact index once. `corpus` is the corpus root the
    orchestrator passes (the dataset dir — `data/corpus/Salesforce__HERB` by
    default, with `products/` under it). The index loader wants the
    `data_root` that contains the dataset dir (so it can resolve
    `data_root / chunk.relpath`), so we hand it `corpus.parent`.

    The tag embeddings were built ahead of time by `embed_tags.py`; that build
    cost is already incurred and not re-run here. `BuildStats.model` is
    therefore zero at prepare time — no model is called in this function — and
    `models` records the embedder the index was built with, so the run
    manifest still names it honestly."""
    corpus_root = Path(corpus)
    data_root = corpus_root.parent
    t0 = time.perf_counter()
    index = load_artefact_index(data_root, _KEY_PATH)
    build_stats = BuildStats(
        build_time_s=time.perf_counter() - t0,
        model=ModelUsage(),  # no model call at prepare; tag-embed cost was incurred by embed_tags.py
        models=[EMBED_MODEL],
    )
    return Prepared(index=index, data_root=data_root, key_path=_KEY_PATH, build_stats=build_stats)


# --- retrieve -----------------------------------------------------------------

def _qid_text(question) -> tuple:
    """(id, question_text) from a QuestionWithTruth, dict, (id, text) tuple, or
    a bare string. Reads ONLY id + question — truth fields are never touched."""
    if hasattr(question, "question") and hasattr(question, "id"):
        return question.id, question.question
    if isinstance(question, dict):
        return question.get("id", ""), question.get("question", "")
    if isinstance(question, (tuple, list)) and len(question) == 2:
        return question[0], question[1]
    return "", str(question)


def _embed_facet_phrases(phrases: list[str]) -> tuple:
    """Embed facet phrases as the query side of nv-embedqa -> (matrix
    [n, d] L2-normalised float32, calls, tokens, seconds). Reuses the vector
    arm's `_embed` so the embedder + batching + token-cap split logic is one
    shared code path. Empty `phrases` returns an empty matrix and zero
    telemetry — the caller skips scoring in that case."""
    if not phrases:
        return np.zeros((0, 0), dtype=np.float32), 0, 0, 0, 0.0
    return _embed(phrases, "query")


def _phrase_weights(index: PreparedIndex, query_vecs: "np.ndarray") -> "np.ndarray":
    """Cosine of every tag phrase against every facet phrase, pooled by max ->
    `phrase_weight ∈ [n_phrases]`. Both `index.matrix` (centered) and the
    query vectors are L2-normalised, so the dot product IS cosine."""
    if query_vecs.shape[0] == 0:
        return np.zeros(index.matrix.shape[0], dtype=np.float32)
    # Mean-center the query against the same corpus mean the tag matrix was
    # centered against, then re-L2-normalise. A zero-norm row (the query sat
    # exactly on the mean) is left at zero — no direction to point in.
    q = query_vecs.astype(np.float32) - index.mean_vector.astype(np.float32)
    norms = np.linalg.norm(q, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    q = q / norms
    scores = index.matrix @ q.T  # [n_phrases, n_facets]
    return scores.max(axis=1).astype(np.float32)


def _chunk_scores(index: PreparedIndex, phrase_weight: "np.ndarray") -> "np.ndarray":
    """Accumulate phrase weights over each chunk's tag rows (DESIGN §14.3) ->
    `chunk_score ∈ [n_chunks]`. A chunk with no tags scores 0."""
    scores = np.zeros(len(index.chunk_ids), dtype=np.float32)
    for j, rows in enumerate(index.chunk_tag_rows):
        if rows:
            scores[j] = float(phrase_weight[rows].sum())
    return scores


def _apply_literal_boosts(index: PreparedIndex, chunk_score: "np.ndarray",
                          literals: list) -> "np.ndarray":
    """Add a fixed `PRODUCT_LITERAL_BOOST` to every chunk whose relpath
    contains `products/<name>.json`, for each wanted product literal. No
    `excluded` handling (never a removal — §14.4). Person/org literals ride
    the semantic layer. Mutates a copy and returns it."""
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
    """interpret → embed facet phrases → phrase weights → chunk scores →
    structural boosts → top-k chunks -> (chunks list-of-Chunk best first,
    interp_parsed, interp_usage, embed_usage, retrieve_wall_s).

    The interpreter + embed calls are timed separately so `answer_one_question`
    can subtract them from the retrieval wall when reporting `search_time_s`
    (the in-process combinator cost, comparable to lucene's pure-in-process
    search time)."""
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


# --- answer -------------------------------------------------------------------


def answer_one_question(
    question, prepared: Prepared, generate: Optional[Generator], k: int = DEFAULT_TOP_K
) -> ArmOutput:
    """ENTRY: interpret → retrieve top-k chunks → resolve artifact ids + chunk
    text → generate → ArmOutput.

    `generate` is the SHARED generator injected by the orchestrator so
    generation is identical across arms. If None (retrieval-only smoke), the
    answer is left empty and generator telemetry is zero.
    """
    _, text = _qid_text(question)

    chunks, interp, interp_usage, emb_telem, retrieve_wall = retrieve_top_k_chunks(
        question, prepared, k)

    if interp.get("answer_shape") == "aggregate":
        log.warning(
            "answer_shape=aggregate for question %r — aggregation path not built; "
            "returning top-k chunks (the cap cuts, no structured aggregation)",
            _qid_text(question)[0])

    # One per-question doc cache: every retrieved chunk's refs are sliced out
    # of in-memory parsed product JSON, hash-verified once per file per
    # question — so k chunks with N refs into the same file cost one read, not
    # k×N. Lives only for this question (no cross-question growth).
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
    # search_time_s = the in-process combinator only (matrix-dot, ranking, id +
    # text resolution). The model-call walls (interpreter + embed) live in
    # `retrieval`, so subtracting them keeps this comparable to lucene's
    # pure-in-process search time.
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

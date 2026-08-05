"""artefact_v1.py — the ARTEFACT-V1 arm: query-relative fuzzy cluster retrieval
over the Neo4j `herb-eval` graph (the v1 artefact build), run in the v3 harness
beside the lucene and vector arms under the shared generator contract and RAGAS
eval.

The graph under test is `Source -[:CONTAINS]-> File -[:HAS_CHUNK]-> Chunk
-[:HAS_TAG]-> Tag`, holding no content — structure, weights, and embeddings
only. Each `HAS_TAG` edge carries `w_chunk`, `w_facets`, `facets`, and
`run_id`. The semantic layer is the nemotron tag family written by
`reembed_herb_eval.py` (run once before this arm): each `:Tag` name embedded
bare as `t.emb` under the `tag_emb` cosine index. Query interpretation uses the
signed-in Claude CLI; query embeddings use NIM.

Retrieval is the user's query-relative area design. Areas are born and die with
each query:

  1. interpret — two Claude Haiku passes; the default serves the cached plan
     when one exists, so a repeat run makes no interpreter call, and
     `HERB_FRESH_INTERP=1` re-runs them. Pass 1 emits a self-contained
     statement of the information need plus the prompt parts (specific noun
     phrases / entities / actions). Pass 2 scores each part across five facets
     (topic, entities, activity, temporal, evidence).
  2. levels — each part is embedded and gathers its local tag pool from
     `tag_emb` over a doubling sequence of kNN levels. Multi-k support: every
     level contributes fuzzy k-NN weight (inverse squared distance, Keller et
     al. 1985) for the tags inside it, so a tag near the part at every level
     accumulates more support than one that only appears at the widest — no
     single k is trusted. The pool's tags then cluster by their embedding
     distances TO EACH OTHER (average-linkage): the part anchors at its
     highest-support tag, and the anchor's containing-cluster chain through
     the dendrogram — finest to coarsest — is the part's widening levels,
     each carrying its merge height as the level's distance.
  3. walk — every part's anchor level opens unconditionally (each part
     searches through its own area), and every part also opens a description
     lookup: the same fuzzy multi-k mechanism over `chunk_desc_emb`,
     chunk-level. Widening events across all parts open in ascending merge
     height (the globally tightest next level first). An opened level's tags
     pull their chunks, each chunk keeping its highest-support tag. Widen only
     while the distinct-chunk pool is still short of the caller's k, then cut
     the pooled chunks at k by value. Hard stop at k; no answer-sufficiency
     oracle. With `HERB_CURVE_WALK=1` the clustering decides the K: the
     description neighborhoods are clustered like tag pools — anchor chunk plus
     a dendrogram chain — and one progressive frontier opens the cheapest next
     level anywhere, tag or description. The gaps between the openings walked
     so far are the spread the next one is tested against: when its height gap
     sits more than two standard deviations above their mean, the walk stops.
     K = the distinct chunks the opened areas vouch for, the caller's k only
     the ceiling; stated scope corroborates value and competes for the K slots
     but never sets the count.

     Value scores on one scale, identical in both regimes. Each of the three
     paths — tag areas, description lookups, stated scope — gives a chunk a base
     (the tag support, the description support, or the scope support, summed
     across the parts or sources that vouch for it) and min-max normalizes that
     base over its own candidate pool. Priority modifiers lift the normalized
     base by an exposed strength `s` as base × (1 + s·(m − 1)): the tag path's
     facet agreement, `w_chunk` and `relevance_to_file`, the description path's
     hint-match factor, the scope path's match fraction. Strength 0 leaves the
     base untouched whatever `m` is; strength 1 makes the factor `m` itself, so
     there an `m` above 1 lifts, below 1 damps, and 0 removes that path's
     contribution for the chunk. The three lifted scores combine as
     a weighted sum (`W_TAG` / `W_DESC` / `W_SCOPE`) over the union, so evidence
     the whole plan touches outranks evidence a single broad tag grips. The
     aggregation and the normalization are selectable — `HERB_AGG` (sum / max),
     `HERB_NORM` (relative / absolute / none) and `HERB_NORM_SCOPE` (per-path /
     global) — the defaults being sum and per-path min-max.

  4. sufficiency — the interpreter holds the conversation: the walk's
     evidence is shown to it cumulatively at the doubling level sequence and
     at each level it decides whether it can answer. Sufficient → exactly the
     evidence seen is kept; never sufficient → the full retrieval stands. The
     caller's k is the forced stop either way.

  Structure enters by order of operations: what the query STATES resolves
  before what the interpreter reads into it. Stated scope (product / section
  / channel / employee_id / years — extracted only when explicitly named) is
  its own path whose pool is the matching chunk set — no clustering, nothing
  fuzzy about a stated fact. Its base is the fuzzy support over description
  distances to the need, extended across the whole matching set, and its match
  fraction is the priority modifier over that normalized base. For the
  interpreted parts, structure raises, never filters: a tag's support scales by
  (1 + the fraction of its edges landing on hint-matching chunks) before the
  anchor is chosen, and anything with no structural touch keeps its full
  semantic weight; a description chunk that matches a stated hint carries the
  hint modifier over its normalized base. Every coefficient — the three path
  weights and the per-modifier strengths — is read from the environment
  (RETRIEVAL_FLAGS) so a run documents and sweeps its own value model.

The graph stores references, never content: a retrieved chunk is a pointer —
`locator_json` on the chunk plus `rel_path` + `sha256` on its file — resolved
from raw under `v3/data/raw` at answer time, hash-verified. `context_ids` are
HERB artifact ids from the raw records. Retrieval excludes the oracle sections
by `c.section`; resolution reads the raw file whole.

Contract: `prepare_over_corpus(corpus) -> Prepared`; `answer_one_question(...)
-> ArmOutput`. The question is read for id + text ONLY.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import os
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform

import abort
import nim
from contract import (
    ArmOutput, BuildStats, ModelUsage, generator_usage_from_nim, unpack_generation,
)
from pipelines.vector import EMBED_MODEL, _embed

# --- graph + retrieval constants ---------------------------------------------

DATABASE = os.environ.get("NEO4J_DATABASE", "herb-eval")
DATASET_ID = os.environ.get("HERB_DATASET_ID", "Salesforce__HERB")
RUN_ID = os.environ.get("HERB_TAG_RUN_ID", "pilot_full_herb")

INTERPRET_MODEL = "claude-haiku-4-5"

ALL_FACETS = ("topic", "entities", "activity", "temporal", "evidence")
GROUND_INDEX = "tag_emb"
DESC_INDEX = "chunk_desc_emb"

# The doubling kNN level sequence: each level contributes fuzzy k-NN support
# for the tags inside it; the widest level is the part's whole pool.
K_LEVELS = (8, 16, 32, 64)

# The over-fetch multiplier on both vector indexes: a kNN query asks the index
# for this many times the intended width, and the LIMIT trims back to it.
KNN_OVERFETCH = 4

# The curve walk: with HERB_CURVE_WALK=1, one progressive frontier walks all
# semantic areas cheapest-first and stops where its own trajectory breaks —
# the clustering decides the per-query evidence count under the caller's k
# ceiling. It selects membership and K; the value scale is identical in both
# regimes.
CURVE_WALK = os.environ.get("HERB_CURVE_WALK") == "1"

# With HERB_DOOR_TRACE=1 every pooled chunk's per-path values and resolve
# pointers land in meta.door_trace — observability only, retrieval untouched.
# Heavy (whole pool per question); for diagnosis runs.
DOOR_TRACE = os.environ.get("HERB_DOOR_TRACE") == "1"

# Flat-regime widening gate: with HERB_WALK_GATE=1 the widening loop counts
# only chunks the tag areas reached, so description and stated-scope finds rank
# and compete at the cut without stopping the walk (the curve walk's frontier
# carries its own stop).
WALK_GATE = os.environ.get("HERB_WALK_GATE") == "1"

# Fresh interpretation: with HERB_FRESH_INTERP=1 the haiku leg re-runs the
# interpreter instead of reading a cached plan, then refreshes the cache. The
# default reuses the cached interpretation, which both saves the call and
# freezes the plan across a retrieval sweep so the comparison is not confounded
# by interpreter sampling.
FRESH_INTERP = os.environ.get("HERB_FRESH_INTERP") == "1"

# Sufficiency review: with HERB_NO_REVIEW=1 the haiku leg keeps the full
# retrieved set instead of letting the interpreter truncate it by content. The
# default runs the review; disabling it lets a retrieval sweep measure retrieval
# alone, with no per-question content cut confounding the depth.
NO_REVIEW = os.environ.get("HERB_NO_REVIEW") == "1"


def _env_float(name: str, default: float) -> float:
    """A run-tunable coefficient read from the environment, `default` when unset
    or blank. A non-numeric value fails loud rather than silently reverting."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    """A run-tunable integer read from the environment, `default` when unset
    or blank. A non-integer value fails loud rather than silently reverting."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


# Per-path combine weights: each of the three paths (tag areas / description
# lookups / stated scope) contributes its normalized, modifier-adjusted base to
# the cross-path sum scaled by its weight.
W_TAG = _env_float("HERB_W_TAG", 1.0)
W_DESC = _env_float("HERB_W_DESC", 1.0)
W_SCOPE = _env_float("HERB_W_SCOPE", 1.0)

# Priority-modifier strengths: a modifier m applies over the normalized base as
# base * (1 + strength * (m - 1)) — strength 0 leaves the base untouched,
# strength 1 is the modifier's full factor. The tag facet-term modifier defaults
# to strength 0, so the stored edge facet weights reach no score; the one sweep
# at full strength lands inside ±0.035 recall of no change, too wide to separate
# the channel from inert either way.
STR_FACET = _env_float("HERB_STR_FACET", 0.0)
STR_WCHUNK = _env_float("HERB_STR_WCHUNK", 1.0)
STR_RELEVANCE = _env_float("HERB_STR_RELEVANCE", 1.0)
STR_DESC_HINT = _env_float("HERB_STR_DESC_HINT", 1.0)
STR_SCOPE_MATCH = _env_float("HERB_STR_SCOPE_MATCH", 1.0)

# The description path's hint-match modifier: the factor a description chunk
# matching a stated scope hint carries into the lerp STR_DESC_HINT grades.
DESC_HINT_M = _env_float("HERB_DESC_HINT_M", 2.0)

# Cluster-guided tag weighting: five per-facet fuzzy membership matrices over
# the tag pool, built once by `build_tag_clusters.py` and cached under
# output/tag_cluster_cache/. Per part, the facet values blend the five
# membership rows of each pool tag, cells below HERB_GUIDE_TAU drop, and the
# surviving mass g in [0, 1] lifts tag support as support × (1 + STR_GUIDE·g)
# before the anchor is chosen. Strength 0 is off — no cache load, no code
# path. C / M / LAMBDA / SEED name the cache entry the arm reads, so a run
# documents the exact build it guided with.
STR_GUIDE = _env_float("HERB_STR_GUIDE", 0.0)
GUIDE_TAU = _env_float("HERB_GUIDE_TAU", 0.01)
GUIDE_C = _env_int("HERB_GUIDE_C", 128)
GUIDE_M = _env_float("HERB_GUIDE_M", 1.5)
GUIDE_LAMBDA = _env_float("HERB_GUIDE_LAMBDA", 0.05)
GUIDE_SEED = _env_int("HERB_GUIDE_SEED", 20260731)
if STR_GUIDE < 0.0:
    raise ValueError(f"HERB_STR_GUIDE must be >= 0.0, got {STR_GUIDE!r}")
if GUIDE_M <= 1.0:
    raise ValueError(
        f"HERB_GUIDE_M (the fuzzifier) must be > 1.0, got {GUIDE_M!r} — "
        f"membership exponents divide by m - 1, and m < 1 flips them toward "
        f"the farthest prototype")

if STR_GUIDE > 0:
    print(f"artefact_v1: cluster guide on (HERB_STR_GUIDE={STR_GUIDE}, "
          f"tau={GUIDE_TAU}, C={GUIDE_C}, m={GUIDE_M})", flush=True)

# Combine-space mode switches — all additive over the default pipeline (AGG ->
# normalize -> modifier lerp -> weighted sum), the defaults reproducing it.
#   HERB_AGG        sum (default) | max — how a path folds a chunk's support over
#                   the parts/sources that vouch for it: sum lifts a corroborated
#                   chunk, max keeps its single best contribution.
#   HERB_NORM       relative (default) | absolute | none — how each path's base
#                   scores reach a comparable scale before the weighted sum:
#                   relative min-max over a pool, absolute saturation against a
#                   fixed reference (pool-independent), or none (raw base).
#   HERB_NORM_SCOPE per_path (default) | global — for relative only: min-max over
#                   each path's own pool, or over the union of all paths' bases;
#                   inert when HERB_NORM is not relative.
AGG = os.environ.get("HERB_AGG", "sum")
NORM = os.environ.get("HERB_NORM", "relative")
NORM_SCOPE = os.environ.get("HERB_NORM_SCOPE", "per_path")
if AGG not in ("sum", "max"):
    raise ValueError(f"HERB_AGG must be 'sum' or 'max', got {AGG!r}")
if NORM not in ("relative", "absolute", "none"):
    raise ValueError(f"HERB_NORM must be 'relative', 'absolute' or 'none', got {NORM!r}")
if NORM_SCOPE not in ("per_path", "global"):
    raise ValueError(f"HERB_NORM_SCOPE must be 'per_path' or 'global', got {NORM_SCOPE!r}")

# The absolute-normalization reference. _ABS_UNIT is the support one level of a
# chunk at a reference cosine distance earns (1 / dist^2); a path's reference is
# that scaled by the number of levels a top-ranked member spans, so
# base / (base + ref) saturates to 0.5 at the reference distance for EVERY path
# regardless of how deep it stacks. Tag and description pools never extend, so
# their reference is fixed at len(K_LEVELS) levels; stated scope's is
# level-count-aware per query.
_ABS_REF_DIST = 0.5
_ABS_UNIT = 1.0 / _ABS_REF_DIST ** 2
_ABS_REF = len(K_LEVELS) * _ABS_UNIT

# Manifest provenance: the regime switches and the environment-exposed combine
# coefficients, recorded by the runner in run_manifest.json.
RETRIEVAL_FLAGS = {
    "HERB_CURVE_WALK": CURVE_WALK, "HERB_DOOR_TRACE": DOOR_TRACE,
    "HERB_WALK_GATE": WALK_GATE, "HERB_FRESH_INTERP": FRESH_INTERP,
    "HERB_NO_REVIEW": NO_REVIEW,
    "HERB_AGG": AGG, "HERB_NORM": NORM, "HERB_NORM_SCOPE": NORM_SCOPE,
    "HERB_W_TAG": W_TAG, "HERB_W_DESC": W_DESC, "HERB_W_SCOPE": W_SCOPE,
    "HERB_STR_FACET": STR_FACET, "HERB_STR_WCHUNK": STR_WCHUNK,
    "HERB_STR_RELEVANCE": STR_RELEVANCE, "HERB_STR_DESC_HINT": STR_DESC_HINT,
    "HERB_STR_SCOPE_MATCH": STR_SCOPE_MATCH, "HERB_DESC_HINT_M": DESC_HINT_M,
    "HERB_STR_GUIDE": STR_GUIDE, "HERB_GUIDE_TAU": GUIDE_TAU,
    "HERB_GUIDE_C": GUIDE_C, "HERB_GUIDE_M": GUIDE_M,
    "HERB_GUIDE_LAMBDA": GUIDE_LAMBDA, "HERB_GUIDE_SEED": GUIDE_SEED,
}

# Content-addressed on-disk caches under output/. The query-embed cache keys a
# question's part/description vectors by (embed model, input_type, text); the
# interpretation cache keys the haiku plan by (interpret model, question text,
# and a signature of the interpreter's prompts and code). Both persist across
# runs. A cached vector is served only for the same model and exact text; a
# cached plan only when the model, the question, and the interpreter's prompts
# and code are all unchanged — an edit to any of them yields a fresh key.
EMBED_CACHE_DIR = Path(__file__).resolve().parent.parent / "output" / "query_embed_cache"
INTERP_CACHE_DIR = Path(__file__).resolve().parent.parent / "output" / "interp_cache"

# The cluster-guide cache: one entry per HERB_GUIDE_* constant set, written by
# `build_tag_clusters.py`. The arm only reads it, and only when STR_GUIDE > 0.
GUIDE_CACHE_DIR = Path(__file__).resolve().parent.parent / "output" / "tag_cluster_cache"

GATE_SECTIONS = (
    "slack", "documents", "meeting_transcripts", "meeting_chats", "prs",
    "urls", "answerable_questions", "unanswerable_questions", "product_profile",
)

EXCLUDED_SECTIONS = ("answerable_questions", "unanswerable_questions", "product_profile")
_EXCLUDED_PARAM = list(EXCLUDED_SECTIONS)
# Sections the interpreter may name as scope hints: the enum minus the oracle
# sections — an excluded section can never be retrieved.
OFFERED_SECTIONS = tuple(s for s in GATE_SECTIONS if s not in EXCLUDED_SECTIONS)

FILLER = {"data", "information", "content", "record", "text", "chunk", "item", "find"}

RAW_ROOT = Path(__file__).resolve().parent.parent / "data" / "raw"

Generator = Callable[[str, list], object]


# --- Cypher ------------------------------------------------------------------

# The part's tag pool, best-first by index score with the tag name as the
# stable tiebreaker — level membership and the anchor read this order. Pooled
# tags carry at least one HAS_TAG edge from the active run; the index is
# over-fetched and the trim caps the pool at its width. The surviving width
# lands in the walk meta per part.
_GROUND_CYPHER = """
CALL db.index.vector.queryNodes($idx, $fetch, $vec) YIELD node, score
WHERE EXISTS { MATCH (node)<-[r:HAS_TAG]-(:Chunk) WHERE r.run_id = $runId }
RETURN node.name AS name, score AS sim, node.emb AS emb
ORDER BY sim DESC, name
LIMIT $k
"""

# An opened area's tags pull their chunks; each chunk keeps its highest-support
# tag and that edge's priority-modifier components. The base score is the tag
# support (qt.weight); facetTerm is the part's facet values against the edge's
# facet arrays, riding the same edge as w_chunk, while relevance_to_file is a
# chunk property, one value for every edge into it. The components return raw —
# the strength lerp and the per-path normalization apply in Python on the shared
# scale.
_AREA_CHUNKS_CYPHER = """
UNWIND $tags AS qt
MATCH (t:Tag {name: qt.name})<-[r:HAS_TAG]-(c:Chunk)<-[:HAS_CHUNK]-(f:File)
WHERE coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND r.run_id = $runId
  AND NOT (coalesce(c.section, "") IN $excludedSections)
WITH c, f, qt, r,
     reduce(dot = 0.0, fi IN range(0, size(coalesce(r.facets, [])) - 1) |
       dot + (CASE r.facets[fi]
                WHEN 'topic'    THEN qt.topic
                WHEN 'entities' THEN qt.entities
                WHEN 'activity' THEN qt.activity
                WHEN 'temporal' THEN qt.temporal
                WHEN 'evidence' THEN qt.evidence
                ELSE 0.0
              END) * coalesce(r.w_facets[fi], 0.0)) AS facetTerm
WITH c, f, qt.weight AS support, coalesce(facetTerm, 0.0) AS facetTerm,
     coalesce(r.w_chunk, 0.0) AS w_chunk,
     coalesce(c.relevance_to_file, 1.0) AS relevance
ORDER BY support DESC, w_chunk DESC
WITH c, f, collect({support: support, facetTerm: facetTerm,
                    w_chunk: w_chunk, relevance: relevance})[0] AS best
RETURN c.chunk_id AS chunkId, c.locator_json AS locator,
       f.rel_path AS relpath, f.sha256 AS sha256,
       best.support AS support, best.facetTerm AS facetTerm,
       best.w_chunk AS w_chunk, best.relevance AS relevance
"""

# The description surface: the same fuzzy mechanism on the chunk-description
# embeddings — the part kNNs `chunk_desc_emb` directly. Structural fields ride
# along so scope hints can raise a chunk's weight in Python; the curve walk's
# variant also carries the embeddings, which it clusters into an area. The
# index is over-fetched and the LIMIT trims it back to the neighborhood width.
_DESC_KNN_TEMPLATE = """
CALL db.index.vector.queryNodes($idx, $fetch, $vec) YIELD node AS c, score AS sim
MATCH (f:File)-[:HAS_CHUNK]->(c)
WHERE coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND NOT (coalesce(c.section, "") IN $excludedSections)
RETURN c.chunk_id AS chunkId, c.locator_json AS locator,
       f.rel_path AS relpath, f.sha256 AS sha256, sim,{emb}
       c.product AS product, c.section AS section, c.channel AS channel,
       c.employee_id AS employee_id, c.years AS years
ORDER BY sim DESC, chunkId
LIMIT $k
"""
_DESC_KNN_CYPHER = _DESC_KNN_TEMPLATE.format(emb="")
_DESC_KNN_EMB_CYPHER = _DESC_KNN_TEMPLATE.format(
    emb="\n       c.desc_emb AS desc_emb,")


def _hint_terms(gate: dict) -> tuple:
    """Cypher boolean terms for the interpreted scope hints, over chunk
    fields. ([], {}) when no hint is set."""
    terms, params = [], {}
    for f in ("product", "section", "channel", "employee_id"):
        if gate.get(f):
            terms.append(f"c.{f} = $g_{f}")
            params[f"g_{f}"] = gate[f]
    if gate.get("years"):
        terms.append("any(y IN $g_years WHERE y IN coalesce(c.years, []))")
        params["g_years"] = list(gate["years"])
    return terms, params


def _tag_affinity(session, names: list, gate: dict) -> dict:
    """Structural affinity per tag: the fraction of the tag's edges landing on
    hint-matching chunks, in [0, 1]. It reweights the embedding's pool, raising
    the tags the stated scope also touches. {} when no hint is set."""
    terms, params = _hint_terms(gate)
    if not terms:
        return {}
    cypher = f"""
UNWIND $names AS name
MATCH (t:Tag {{name: name}})<-[r:HAS_TAG]-(c:Chunk)<-[:HAS_CHUNK]-(f:File)
WHERE r.run_id = $runId
  AND coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND NOT (coalesce(c.section, "") IN $excludedSections)
RETURN name, count(c) AS total,
       sum(CASE WHEN {" OR ".join(terms)} THEN 1 ELSE 0 END) AS hits
"""
    res = session.run(cypher, names=names, runId=RUN_ID, datasetId=DATASET_ID,
                      excludedSections=_EXCLUDED_PARAM, **params)
    return {rec["name"]: (float(rec["hits"]) / float(rec["total"]))
            for rec in res if rec["total"]}


def _hint_match(row: dict, gate: dict) -> bool:
    """Whether one chunk row matches at least one scope hint."""
    for f in ("product", "section", "channel", "employee_id"):
        if gate.get(f) and row.get(f) == gate[f]:
            return True
    if gate.get("years") and set(gate["years"]) & set(row.get("years") or []):
        return True
    return False


# --- query-embed cache -------------------------------------------------------

def _embed_key(text: str, input_type: str) -> str:
    """Content address for one embedding: (embed model, input_type, text), each
    length-prefixed so no field's bytes can forge a boundary and alias a
    different text onto the same key. A new embedder id yields a new key."""
    h = hashlib.sha256()
    for field in (EMBED_MODEL, input_type, text):
        b = field.encode("utf-8")
        h.update(len(b).to_bytes(8, "big"))
        h.update(b)
    return h.hexdigest()


def _load_cached_vec(key: str):
    """The cached embedding for `key`, or None on a miss. A corrupt or
    half-written file reads as a miss — never a wrong hit."""
    path = EMBED_CACHE_DIR / f"{key}.npy"
    if not path.is_file():
        return None
    try:
        return np.load(path)
    except (ValueError, OSError):
        return None


def _store_cached_vec(key: str, vec: np.ndarray) -> None:
    """Write one embedding under its content address, published atomically so a
    concurrent reader never loads a partial vector."""
    EMBED_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=EMBED_CACHE_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            np.save(f, np.asarray(vec, dtype=np.float32))
        os.replace(tmp, EMBED_CACHE_DIR / f"{key}.npy")
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _embed_cached(texts: list, input_type: str) -> tuple:
    """Embed `texts` through the shared NIM embedder with a persistent per-text
    cache keyed by (model, input_type, text). Hits load from disk; the misses
    embed in one batch and each new vector is stored content-addressed. Usage
    counts the miss embed only — a fully-cached call reports zero NIM cost, the
    same shape pipelines.vector._embed returns."""
    keys = [_embed_key(t, input_type) for t in texts]
    rows: dict = {}
    misses, miss_at = [], []
    for i, (t, key) in enumerate(zip(texts, keys)):
        vec = _load_cached_vec(key)
        if vec is None:
            misses.append(t)
            miss_at.append(i)
        else:
            rows[i] = vec
    calls = tok_in = tok_out = 0
    secs = 0.0
    if misses:
        mat, calls, tok_in, tok_out, secs = _embed(misses, input_type)
        for j, i in enumerate(miss_at):
            vec = np.asarray(mat[j], dtype=np.float32)
            rows[i] = vec
            _store_cached_vec(keys[i], vec)
    return (np.asarray([rows[i] for i in range(len(texts))], dtype=np.float32),
            calls, tok_in, tok_out, secs)


# --- prepare -----------------------------------------------------------------

@dataclass
class Prepared:
    driver: object
    build_stats: Optional[BuildStats] = None


def _driver():
    from neo4j import GraphDatabase
    nim._load_dotenv()
    pw = os.environ.get("NEO4J_PASSWORD")
    if not pw:
        raise RuntimeError("NEO4J_PASSWORD is not set — add it to v3/.env (like NVIDIA_API_KEY).")
    uri = os.environ.get("NEO4J_URI", "neo4j://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    return GraphDatabase.driver(uri, auth=(user, pw),
                                notifications_min_severity="OFF")


def prepare_over_corpus(corpus) -> Prepared:
    t0 = time.perf_counter()
    drv = _driver()
    try:
        with drv.session(database=DATABASE) as s:
            s.run("RETURN 1").consume()
            present = s.run(
                "SHOW INDEXES YIELD name WHERE name IN [$t, $d] "
                "RETURN collect(name) AS names",
                t=GROUND_INDEX, d=DESC_INDEX).single()["names"]
            # the retrieved population, under the same empty guard the
            # retrieval queries carry
            no_desc = s.run(
                "MATCH (c:Chunk) WHERE coalesce(c.empty, false) = false "
                "AND c.desc_emb IS NULL RETURN count(c) AS n").single()["n"]
            multi = s.run(
                "MATCH (c:Chunk) WITH c, count { (:File)-[:HAS_CHUNK]->(c) } AS n "
                "WHERE n <> 1 RETURN count(*) AS bad").single()["bad"]
        if multi:
            raise RuntimeError(
                f"{multi} chunk(s) in {DATABASE!r} without exactly one File — "
                f"pointer resolution would be ambiguous")
        missing = sorted({GROUND_INDEX, DESC_INDEX} - set(present))
        if missing or no_desc:
            raise RuntimeError(
                f"semantic layer incomplete in {DATABASE!r} (missing indexes: {missing or 'none'}, "
                f"non-empty chunks without desc_emb: {no_desc}) — run `python reembed_herb_eval.py` once.")
    except Exception:
        drv.close()
        raise
    return Prepared(
        driver=drv,
        build_stats=BuildStats(
            build_time_s=time.perf_counter() - t0,
            model=ModelUsage(),
            models=[EMBED_MODEL],
        ),
    )


# --- interpret (two Claude Haiku CLI passes) ----------------------------------

def _qid_text(question) -> tuple:
    if hasattr(question, "question") and hasattr(question, "id"):
        return question.id, question.question
    if isinstance(question, dict):
        return question.get("id", ""), question.get("question", "")
    if isinstance(question, (tuple, list)) and len(question) == 2:
        return question[0], question[1]
    return "", str(question)


def _extract_json(text: str) -> dict:
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    body = fence.group(1).strip() if fence else text
    start = body.find("{")
    if start == -1:
        raise ValueError(f"no JSON object in model output: {text[:200]!r}")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(body)):
        ch = body[i]
        if esc:
            esc = False
            continue
        if ch == "\\" and in_str:
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(body[start:i + 1])
    raise ValueError(f"unterminated JSON object in model output: {text[:200]!r}")


_PASS1_SYSTEM = (
    "You interpret a user query for graph retrieval. Work in three steps. "
    'STEP 1: write "description" — a concise, self-contained 1-3 sentence statement of the '
    "underlying information need (what the user actually wants to find, including implied "
    "entities/scope), in plain declarative prose, not a restatement of the question. "
    'STEP 2: derive "tags" FROM that description — the query\'s distinct parts as specific '
    "noun phrases, named entities, systems, or actions. No generic filler words. "
    'STEP 3: extract "gate" — structured scope hints ONLY when the query explicitly names them, '
    'else null/[]. Fields: product (a "*Force"/"*Genie"-style product name if named), '
    f"section (one of: {', '.join(OFFERED_SECTIONS)} — map synonyms, e.g. \"pull requests\"->prs, \"chat\"->slack), "
    'channel (a Slack channel name if given), employee_id (an "eid_..." id if given), '
    "years (array of 4-digit years explicitly mentioned). Do NOT guess values not in the query. "
    'Return ONLY valid JSON: {"description":"...","tags":["tag1"],'
    '"gate":{"product":null,"section":null,"channel":null,"employee_id":null,"years":[]}}.'
)

_PASS2_SYSTEM = (
    "Score retrieval tags against five facets (each 0.0-1.0). "
    "topic: subject matter. entities: named people/orgs/products/systems. "
    "activity: events/processes/actions. temporal: time relevance. evidence: answer material type. "
    'Return ONLY valid JSON: {"scores":[{"t":"tag","facets":{"topic":0.0,"entities":0.0,"activity":0.0,"temporal":0.0,"evidence":0.0}}]}'
)

_REVIEW_SYSTEM = (
    "You are driving evidence retrieval for a question. You see the evidence "
    "collected so far, best-first. Decide whether it is sufficient to answer "
    "the question. Say sufficient ONLY when the answer is actually contained "
    "in the evidence shown — more evidence arrives if you say it is not. "
    'Return ONLY valid JSON: {"sufficient": true} or {"sufficient": false}.'
)


class InterpreterError(RuntimeError):
    """A failed interpreter turn. Carries the model usage spent across the
    turn's attempts, so a caller that survives the failure still accounts
    its cost."""

    def __init__(self, message: str, calls: int = 0, tokens_in: int = 0,
                 tokens_out: int = 0, time_s: float = 0.0):
        super().__init__(message)
        self.calls = calls
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.time_s = time_s


def _chat_json(model: str, system: str, user: str, max_tokens: int,
               validate: Optional[Callable[[dict], None]] = None) -> tuple:
    """One JSON turn on the interpreter model -> (parsed_json, tokens_in,
    tokens_out, time_s), usage summed over attempts. A malformed emission —
    unparseable JSON, or a payload `validate` rejects with ValueError — gets
    one retry; an empty or truncated response fails immediately, naming its
    finish_reason. Those failures raise InterpreterError carrying the usage
    spent."""
    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    calls = tok_in = tok_out = 0
    elapsed = 0.0

    def fail(message: str) -> InterpreterError:
        return InterpreterError(message, calls=calls, tokens_in=tok_in,
                                tokens_out=tok_out, time_s=elapsed)

    for attempt in (1, 2):
        t0 = time.perf_counter()
        resp = nim.post("/chat/completions", payload, timeout=480.0)
        elapsed += time.perf_counter() - t0
        calls += 1
        ti, to = generator_usage_from_nim(resp.get("usage"))
        tok_in += ti
        tok_out += to
        choices = resp.get("choices") or []
        finish = choices[0].get("finish_reason") if choices else "no choices"
        content = (choices[0].get("message") or {}).get("content") if choices else None
        if not content:
            raise fail(f"interpreter returned empty content (finish_reason={finish})")
        if finish == "length":
            raise fail(
                f"interpreter truncated at max_tokens={max_tokens} (finish_reason=length) — raise the budget")
        try:
            parsed = _extract_json(content)
            if validate is not None:
                validate(parsed)
            return parsed, tok_in, tok_out, elapsed
        except ValueError as e:
            if attempt == 2:
                raise fail(f"interpreter emitted a malformed payload twice: {e}") from e


def _clean_tag(raw: str) -> str:
    return re.sub(r"^_+|_+$", "", re.sub(r"[^a-z0-9]+", "_", raw.lower()))


def _readable(name: str) -> str:
    return name.replace("_", " ").strip()


def _parse_gate(raw) -> dict:
    """Normalise the model's loose gate into strict scope hints: string-or-null
    fields, a section restricted to the offered set, 4-digit years."""
    g = raw if isinstance(raw, dict) else {}

    def s(v):
        return v.strip() if isinstance(v, str) and v.strip() else None

    section = s(g.get("section"))
    years, seen = [], set()
    for y in (g.get("years") or []):
        try:
            yi = int(y)
        except (TypeError, ValueError):
            continue
        if 1000 <= yi <= 9999 and yi not in seen:
            seen.add(yi)
            years.append(yi)
    return {
        "product": s(g.get("product")),
        "section": section if section in OFFERED_SECTIONS else None,
        "channel": s(g.get("channel")),
        "employee_id": s(g.get("employee_id")),
        "years": years,
    }


def _validate_scores(parsed: dict) -> None:
    """Pass-2 payload shape: `scores` is a list of rows, each {t: str,
    facets: {facet: number}}. A violation raises ValueError, which
    `_chat_json` retries like any malformed emission."""
    scores = parsed.get("scores")
    if not isinstance(scores, list):
        raise ValueError(f"scores is not a list: {type(scores).__name__}")
    for row in scores:
        if not isinstance(row, dict) or not isinstance(row.get("t"), str):
            raise ValueError(f"score row malformed: {row!r}")
        facets = row.get("facets")
        if not isinstance(facets, dict):
            raise ValueError(f"facets missing for tag {row['t']!r}")
        for f, v in facets.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError(f"facet {f!r} of tag {row['t']!r} is not a number: {v!r}")


def _interpret(text: str, model: str) -> tuple:
    """interpret a question -> (plan, calls, tokens_in, tokens_out, time_s).
    plan = {description, parts:[{t, facets}], gate}. Pass 2 is skipped when
    pass 1 yields no usable parts; the description then stands in as the
    single part. Tags pass 2 leaves unscored keep the neutral default and are
    listed in plan["unscored"]."""
    p1, in1, out1, t1 = _chat_json(model, _PASS1_SYSTEM, f"User query: {text}", 512)
    description = p1.get("description") or text
    gate = _parse_gate(p1.get("gate"))
    raw_parts, seen = [], set()
    for raw in (p1.get("tags") or []):
        t = _clean_tag(str(raw))
        if len(t) > 1 and t not in FILLER and t not in seen:
            seen.add(t)
            raw_parts.append(t)

    if not raw_parts:
        neutral = {f: 0.2 for f in ALL_FACETS}
        return ({"description": description,
                 "parts": [{"t": description, "facets": neutral}],
                 "gate": gate},
                1, in1, out1, t1)

    p2, in2, out2, t2 = _chat_json(
        model, _PASS2_SYSTEM,
        f"Original query: {text}\n\nScore these tags:\n{json.dumps(raw_parts)}", 1024,
        validate=_validate_scores)
    # echoed tags match on the same cleaned form the parts carry, so case or
    # spacing drift in the echo cannot detach a score row
    score_map = {_clean_tag(row["t"]): (row.get("facets") or {})
                 for row in (p2.get("scores") or [])}
    default = {f: 0.2 for f in ALL_FACETS}
    unscored = [t for t in raw_parts if t not in score_map]
    parts = []
    for t in raw_parts:
        facets = {f: min(1.0, max(0.0, float(score_map.get(t, default).get(f, 0.2))))
                  for f in ALL_FACETS}
        parts.append({"t": t, "facets": facets})
    plan = {"description": description, "parts": parts, "gate": gate}
    if unscored:
        plan["unscored"] = unscored
    return plan, 2, in1 + in2, out1 + out2, t1 + t2


# --- interpretation cache ----------------------------------------------------

# The prompts AND the code that shape an interpretation. Folding a signature of
# both into the cache key means editing a prompt, the tag cleaner, the gate
# parser, the score validator, the JSON extractor, the facet set, the filler
# set, or the interpret flow itself invalidates every cached plan.
_INTERP_SIG = hashlib.sha256("\x00".join([
    _PASS1_SYSTEM, _PASS2_SYSTEM, repr(sorted(FILLER)), repr(ALL_FACETS),
    inspect.getsource(_interpret), inspect.getsource(_clean_tag),
    inspect.getsource(_parse_gate), inspect.getsource(_validate_scores),
    inspect.getsource(_extract_json),
]).encode("utf-8")).hexdigest()


def _interp_key(text: str, model: str) -> str:
    """Content address for one interpretation: (interpret model, interpreter
    signature, question text), length-prefixed against boundary aliasing. A
    change to the model, the prompts, or the interpreter code yields a new key."""
    h = hashlib.sha256()
    for field in (model, _INTERP_SIG, text):
        b = field.encode("utf-8")
        h.update(len(b).to_bytes(8, "big"))
        h.update(b)
    return h.hexdigest()


def _store_interp(key: str, plan: dict) -> None:
    """Write one interpreted plan under its content address, published
    atomically so a concurrent reader never loads a partial plan."""
    INTERP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=INTERP_CACHE_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False)
        os.replace(tmp, INTERP_CACHE_DIR / f"{key}.json")
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _interpret_cached(text: str, model: str) -> tuple:
    """interpret with a persistent plan cache keyed by (model, prompt
    signature, question text). A hit returns the stored plan with zero
    interpreter usage — no LLM call — so a retrieval sweep reuses one frozen
    interpretation per question instead of re-sampling it. HERB_FRESH_INTERP=1
    re-runs the interpreter and refreshes the cache; a corrupt or shapeless
    cache file reads as a miss, never a wrong plan. Same return shape as
    _interpret."""
    key = _interp_key(text, model)
    path = INTERP_CACHE_DIR / f"{key}.json"
    if not FRESH_INTERP and path.is_file():
        try:
            plan = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            plan = None
        if isinstance(plan, dict) and isinstance(plan.get("parts"), list):
            return plan, 0, 0, 0, 0.0
    plan, calls, tok_in, tok_out, secs = _interpret(text, model)
    _store_interp(key, plan)
    return plan, calls, tok_in, tok_out, secs


# --- query-relative areas (fuzzy clusters over the part's tag pool) -----------

def _unit(a: np.ndarray) -> np.ndarray:
    """`a` scaled to unit length along its last axis; a zero vector has no
    direction and stays zero."""
    norms = np.linalg.norm(a, axis=-1, keepdims=True)
    norms[norms == 0] = 1.0
    return a / norms


def _gap_break(gaps: list, gap: float) -> bool:
    """The walk's stopping test, read from the walk's own gaps: the next
    opening breaks the walk when its height gap jumps more than two standard
    deviations above their mean, over every gap walked so far. Three gaps are
    the minimum history the test fires on, and a jump must clear float noise —
    an excess of rounding-error size is never a break."""
    if len(gaps) < 3 or gap <= 1e-9:
        return False
    return gap > float(np.mean(gaps)) + 2.0 * float(np.std(gaps)) + 1e-9


def _multi_k_support(dists: np.ndarray, extend: bool = False,
                     normalize: bool = True) -> np.ndarray:
    """Fuzzy k-NN support aggregated over the doubling level sequence: every
    level contributes inverse-squared-distance weight for the members inside
    it, so support is a staircase over the level sequence with distance
    modulating inside each step. Normalized over the pool by default; with
    `normalize` off the raw inverse-square weights return — a pure function
    of distance, one scale shared by every area. With `extend`, the doubling
    continues until the sequence covers the whole ranked set — every member
    carries support, deeper levels carry less."""
    levels = list(K_LEVELS)
    if extend:
        while levels[-1] < len(dists):
            levels.append(levels[-1] * 2)
    support = np.zeros(len(dists))
    for k in levels:
        kk = min(k, len(dists))
        support[:kk] += 1.0 / np.maximum(dists[:kk], 1e-6) ** 2
    if not normalize:
        return support
    total = support.sum()
    return support / total if total > 0 else support


def _norm_pool(base: dict, lo: float, hi: float) -> dict:
    """Min-max a path's base scores against the given bounds: hi <= lo (a single
    scale point) maps every member to 1, an empty base to nothing."""
    if not base:
        return {}
    if hi <= lo:
        return {cid: 1.0 for cid in base}
    span = hi - lo
    return {cid: (v - lo) / span for cid, v in base.items()}


def _minmax(raw: dict) -> dict:
    """Min-max normalize a path's per-chunk base scores onto [0, 1] over that
    path's own candidate pool: the pool's strongest chunk lands at 1, its
    weakest at 0, decoupling the path's influence from the raw magnitude of its
    scoring function, and a single-member pool lands at 1."""
    if not raw:
        return {}
    return _norm_pool(raw, min(raw.values()), max(raw.values()))


def _absolute(base: float, ref: float) -> float:
    """A pool-independent bounded score: the raw support saturated against a
    per-path reference, base / (base + ref). The reference scales with the
    levels the path stacks, so a top match at the reference distance scores 0.5
    in every path; order within a path is preserved and a path that found only
    weak matches keeps low scores instead of stretching its best to 1."""
    return base / (base + ref)


def _n_levels(n: int) -> int:
    """The number of doubling levels a stated-scope ranked set of size n spans —
    the level multiplicity a top-ranked member accumulates. Tag and description
    pools never extend, so their multiplicity is always len(K_LEVELS)."""
    levels = list(K_LEVELS)
    while levels[-1] < n:
        levels.append(levels[-1] * 2)
    return len(levels)


def _agg(slots: list) -> dict:
    """Fold a path's per-part/source support dicts into one per-chunk base by
    the HERB_AGG mode: sum lifts a chunk each part corroborates, max keeps its
    single best contribution."""
    base: dict = {}
    for slot in slots:
        for cid, sup in slot.items():
            if cid not in base:
                base[cid] = sup
            elif AGG == "max":
                base[cid] = max(base[cid], sup)
            else:
                base[cid] = base[cid] + sup
    return base


def _normalize(tag_base: dict, desc_base: dict, scope_base: dict,
               scope_levels: int) -> tuple:
    """Put the three paths' bases on a comparable scale by the HERB_NORM mode:
    relative min-max (HERB_NORM_SCOPE per-path, or global over the union of all
    three), absolute saturation against a per-path level-count-aware reference,
    or none (raw). `scope_levels` is the stated-scope path's per-query level
    multiplicity, so equal distance scores equal across paths under absolute.
    Returns the three normalized base dicts."""
    if NORM == "none":
        return tag_base, desc_base, scope_base
    if NORM == "absolute":
        scope_ref = scope_levels * _ABS_UNIT
        return ({cid: _absolute(v, _ABS_REF) for cid, v in tag_base.items()},
                {cid: _absolute(v, _ABS_REF) for cid, v in desc_base.items()},
                {cid: _absolute(v, scope_ref) for cid, v in scope_base.items()})
    if NORM_SCOPE == "global":
        allvals = [*tag_base.values(), *desc_base.values(), *scope_base.values()]
        lo = min(allvals) if allvals else 0.0
        hi = max(allvals) if allvals else 0.0
        return (_norm_pool(tag_base, lo, hi), _norm_pool(desc_base, lo, hi),
                _norm_pool(scope_base, lo, hi))
    return _minmax(tag_base), _minmax(desc_base), _minmax(scope_base)


def _mod(m: float, strength: float) -> float:
    """A priority modifier over the normalized base: strength 0 returns 1 (the
    modifier is inert), strength 1 returns the raw factor `m`, values between
    interpolate. Clamped at 0 so a strength past 1 damps toward zero without
    flipping sign; the damped score ranks and is cut at k like any other."""
    return max(0.0, 1.0 + strength * (m - 1.0))


def _level_chain(embs: np.ndarray, anchor: int, dist_shaper=None) -> list:
    """The anchor leaf's containing-cluster chain through the dendrogram,
    finest to coarsest: [(height, added_leaf_indices)]. Level 0 is the anchor
    alone at height 0; each later level is the merge that grew the anchor's
    cluster, adding the sibling's leaves at that merge's height. The heights
    are cosine distances — one scale, comparable across parts. A caller-
    supplied `dist_shaper(embs, D) -> D` may reshape the mutual distances
    before clustering, so the areas themselves form query-relatively."""
    n = len(embs)
    if n == 1:
        return [(0.0, [0])]
    D = 1.0 - np.clip(embs @ embs.T, -1.0, 1.0)
    np.fill_diagonal(D, 0.0)
    if dist_shaper is not None:
        D = dist_shaper(embs, D)
        np.fill_diagonal(D, 0.0)
    Z = linkage(squareform(D, checks=False), method="average")

    members = {i: [i] for i in range(n)}
    for i, (a, b, _, _) in enumerate(Z):
        members[n + i] = members[int(a)] + members[int(b)]

    levels = [(0.0, [anchor])]
    node = anchor
    for i, (a, b, height, _) in enumerate(Z):
        a, b = int(a), int(b)
        if node in (a, b):
            sibling = b if node == a else a
            levels.append((float(height), list(members[sibling])))
            node = n + i
    return levels


# --- cluster guide (per-facet fuzzy memberships over the tag pool) ------------

_GUIDE: Optional[dict] = None


def _guide_key() -> str:
    """The cache entry name for one build of the membership matrices: the
    database, the tagging run, and every constant the build depends on."""
    return (f"{DATABASE}__{RUN_ID}__C{GUIDE_C}__m{GUIDE_M}"
            f"__lam{GUIDE_LAMBDA}__seed{GUIDE_SEED}")


def _guide_tables() -> dict:
    """The cached membership matrices, loaded once per process: `U` stacked
    (n_facets, n_tags, C) in ALL_FACETS order, plus the tag-name -> row index.
    The manifest is written last by the build, so its presence marks a complete
    entry; a missing one fails loud naming the build step."""
    global _GUIDE
    if _GUIDE is None:
        entry = GUIDE_CACHE_DIR / _guide_key()
        if not (entry / "manifest.json").is_file():
            raise RuntimeError(
                f"tag-cluster cache missing at {entry} — run `python build_tag_clusters.py` once.")
        with np.load(entry / "memberships.npz") as z:
            U = np.stack([z[f] for f in ALL_FACETS])
        names = json.loads((entry / "tags.json").read_text(encoding="utf-8"))
        _GUIDE = {"U": U, "row": {n: i for i, n in enumerate(names)}}
    return _GUIDE


def _guidance(names: list, facets: dict, stats: Optional[dict] = None) -> np.ndarray:
    """Cluster guidance g per pool tag, in [0, 1]. The part's facet values
    normalize to a unit-sum blend (an all-zero profile blends uniformly — a
    flat profile IS the uniform blend), the blend scales each facet's
    membership row, cells below GUIDE_TAU drop, and g is the surviving mass.
    A tag the cache index does not carry keeps g = 0. `stats` accumulates the
    matched/unmatched counts and the g mass for the retrieval meta."""
    tables = _guide_tables()
    U, row = tables["U"], tables["row"]
    phi = np.array([float(facets.get(f, 0.0)) for f in ALL_FACETS])
    total = phi.sum()
    phi = phi / total if total > 0 else np.full(len(ALL_FACETS), 1.0 / len(ALL_FACETS))
    g = np.zeros(len(names))
    hit = [(i, row[n]) for i, n in enumerate(names) if n in row]
    if hit:
        at, rows = zip(*hit)
        cells = phi[:, None, None] * U[:, list(rows), :]
        g[list(at)] = np.where(cells >= GUIDE_TAU, cells, 0.0).sum(axis=(0, 2))
    if stats is not None:
        stats["matched"] += len(hit)
        stats["unmatched"] += len(names) - len(hit)
        stats["g_sum"] += float(g.sum())
        stats["g_n"] += len(names)
    return g


def _part_levels(session, part: dict, vec: np.ndarray, gate: dict,
                 shaper=None, dist_shaper=None, guide_stats=None) -> list:
    """One part -> its widening levels: [{height, tags: [(name, support)]}]
    finest to coarsest. Support is raw fuzzy multi-k weight raised by structural
    affinity — support × (1 + affinity) — so a part's tag supports stay on the
    one distance-derived scale the combine step normalizes, and scope hints
    inform where the part anchors without ever zeroing an unrelated tag. With
    STR_GUIDE > 0 cluster guidance lifts it the same way — support ×
    (1 + STR_GUIDE·g) — from the part's facet blend of the cached membership
    matrices. A caller-supplied `shaper(names, embs, support) -> support` may
    reshape support from the pool's own geometry before the anchor is chosen.
    The part anchors at its highest-support tag; each level is the dendrogram
    merge that widens the anchor's cluster, carrying the merge height."""
    recs = list(session.run(
        _GROUND_CYPHER, idx=GROUND_INDEX, k=K_LEVELS[-1],
        fetch=KNN_OVERFETCH * K_LEVELS[-1], runId=RUN_ID,
        vec=[float(x) for x in vec]))
    rows = [(r["name"], r["sim"], r["emb"]) for r in recs
            if r["name"] and r["sim"] is not None and r["emb"] is not None]
    if not rows:
        return []
    names = [n for n, _, _ in rows]
    embs = _unit(np.asarray([e for _, _, e in rows], dtype=np.float64))
    dists = np.array([1.0 - float(s) for _, s, _ in rows])

    support = _multi_k_support(dists, normalize=False)
    affinity = _tag_affinity(session, names, gate)
    if affinity:
        support = support * np.array([1.0 + affinity.get(n, 0.0) for n in names])
    if STR_GUIDE > 0:
        support = support * (1.0 + STR_GUIDE * _guidance(names, part["facets"], guide_stats))
    if shaper is not None:
        support = shaper(names, embs, support)
    anchor = int(np.argmax(support))
    return [{"height": h,
             "tags": [(names[i], float(support[i])) for i in added]}
            for h, added in _level_chain(embs, anchor, dist_shaper)]


def _open_area(session, area: dict, facets: dict) -> list:
    """Open one area: its tags pull their chunks; each chunk keeps its
    highest-support tag, carrying that edge's facet agreement and w_chunk plus
    the chunk's own relevance_to_file as the tag path's priority modifiers over
    the tag-support base."""
    cols = {f: float(facets.get(f, 0.0)) for f in ALL_FACETS}
    res = session.run(
        _AREA_CHUNKS_CYPHER,
        tags=[{"name": n, "weight": s, **cols} for n, s in area["tags"]],
        datasetId=DATASET_ID,
        runId=RUN_ID,
        excludedSections=_EXCLUDED_PARAM,
    )
    return [dict(rec) for rec in res]


def _retrieve(session, plan: dict, k: int) -> tuple:
    """interpret-plan -> (pointer rows cut at k, query embed ModelUsage,
    retrieval meta). Every part anchors at its tightest cluster (level 0) and
    widens up its own dendrogram; widening events across all parts open in
    ascending merge height (the globally tightest next level first) and only
    while the distinct-chunk pool — with `HERB_WALK_GATE=1`, only the chunks
    the tag areas reached — is short of k. With `HERB_CURVE_WALK=1` one
    progressive frontier walks all semantic areas — tag areas and clustered
    description neighborhoods — cheapest opening first on the shared
    cosine-height scale, and stops when the next opening's gap jumps two
    standard deviations above the gaps walked so far (`_gap_break`); K = the
    distinct chunks the opened areas vouch for, capped by the caller's k.

    Membership is the union of what the three paths — tag areas, description
    lookups, stated scope — find; description and scope stay finders, never
    trimmed to the tag chunks. Value is scored on one scale in both regimes:
    each path's per-chunk base (tag support / description support / scope
    support, summed across the parts or sources that vouch for a chunk) is
    min-max normalized over that path's own pool, its priority modifiers (facet
    agreement, w_chunk and relevance_to_file for tags; a hint match for
    descriptions; the match fraction for scope) lift the normalized base by
    their exposed strengths, and the three lifted scores combine as a weighted
    sum (W_TAG / W_DESC / W_SCOPE). Stated scope corroborates value and competes
    for the K slots but never sets the count."""
    if k <= 0:
        raise ValueError("k must be positive")

    parts = plan["parts"]
    qmat, calls, tok_in, tok_out, secs = _embed_cached(
        [plan["description"]] + [_readable(p["t"]) for p in parts], "query")
    usage = ModelUsage(calls=calls, tokens_in=tok_in, tokens_out=tok_out, time_s=secs)
    need_vec = _unit(np.asarray([float(x) for x in qmat[0]], dtype=np.float64))

    gate = plan.get("gate") or {}
    shaper = plan.get("_support_shaper")        # callables, never serialized
    dist_shaper = plan.get("_distance_shaper")
    guide_stats = ({"matched": 0, "unmatched": 0, "g_sum": 0.0, "g_n": 0}
                   if STR_GUIDE > 0 else None)
    anchors = []   # every part's level 0 — always opened
    widening = []  # (height, part_index, level)
    part_vecs = []
    level_log = []
    for i, part in enumerate(parts):
        vec = _unit(np.asarray([float(x) for x in qmat[i + 1]], dtype=np.float64))
        part_vecs.append(vec)
        levels = _part_levels(session, part, vec, gate, shaper, dist_shaper,
                              guide_stats)
        level_log.append({
            "part": part["t"],
            # the tag-pool width
            "pool": sum(len(lv["tags"]) for lv in levels),
            "levels": [{"height": round(lv["height"], 4),
                        "size": len(lv["tags"]),
                        "tags": [n for n, _ in lv["tags"][:6]]}
                       for lv in levels],
        })
        # the chain's level 0 is the anchor; every later level widens, whatever
        # its merge height
        for li, lv in enumerate(levels):
            if li == 0:
                anchors.append((i, lv))
            else:
                widening.append((lv["height"], i, lv))
    if not anchors:
        raise RuntimeError("no tag pool for any prompt part — is tag_emb empty?")
    widening.sort(key=lambda x: x[0])

    pool: set = set()          # every chunk any path found — the union membership
    semantic: set = set()      # chunks the tag/description paths vouch for — the K
    tag_reached: set = set()   # chunks a tag area reached — the walk-gate count
    payload: dict = {}
    walk = []

    # Raw per-path bases, held off the shared scale until the combine step
    # normalizes each pool. Tag and description sum a chunk's best support
    # across the parts/sources that vouch for it; scope is a single source.
    tag_slots = [dict() for _ in parts]  # per part: chunkId -> best tag support
    tag_supp: dict = {}                  # chunkId -> its top tag support
    tag_mods: dict = {}                  # chunkId -> (facetTerm, w_chunk, relevance) at that support
    desc_sources: list = []              # each a dict chunkId -> best description support
    desc_hint: dict = {}                 # chunkId -> description priority modifier (DESC_HINT_M on a hint match)
    scope_base: dict = {}                # chunkId -> scope support
    scope_match: dict = {}               # chunkId -> stated-scope match fraction
    scope_n = 0                          # stated-scope matching-set size — its level multiplicity

    def _pointer(row):
        return {f: row[f] for f in ("chunkId", "locator", "relpath", "sha256")}

    def open_level(height, pi, level):
        rows = _open_area(session, level, parts[pi]["facets"])
        fresh = 0
        for row in rows:
            cid = row["chunkId"]
            sup = float(row["support"])
            if cid not in pool:
                fresh += 1
                pool.add(cid)
            semantic.add(cid)
            tag_reached.add(cid)
            # a first sighting always records a base, so a tag-reached chunk
            # carries a tag score into the combine
            if cid not in tag_slots[pi] or sup > tag_slots[pi][cid]:
                tag_slots[pi][cid] = sup
            # the chunk's top-support edge across all parts supplies its tag modifiers
            if cid not in tag_supp or sup > tag_supp[cid]:
                tag_supp[cid] = sup
                tag_mods[cid] = (float(row["facetTerm"]), float(row["w_chunk"]),
                                 float(row["relevance"]))
            payload.setdefault(cid, _pointer(row))
        walk.append({"part": parts[pi]["t"], "path": "tag", "height": round(height, 4),
                     "tags": len(level["tags"]), "chunks": len(rows), "new": fresh})

    def _record_desc(slot, rows, vals):
        """Record one description source's rows into its slot (best support per
        chunk) and set the shared hint modifier on any chunk a scope hint
        matches. Returns the count new to the union."""
        hinted = bool(_hint_terms(gate)[0])
        fresh = 0
        for row, val in zip(rows, vals):
            cid = row["chunkId"]
            if cid not in pool:
                fresh += 1
                pool.add(cid)
            semantic.add(cid)
            v = float(val)
            if v > slot.get(cid, 0.0):
                slot[cid] = v
            if hinted and _hint_match(row, gate):
                desc_hint[cid] = DESC_HINT_M
            payload.setdefault(cid, _pointer(row))
        return fresh

    def open_desc(vec, label):
        """A part's description lookup: fuzzy multi-k support over
        `chunk_desc_emb`, chunk-level, its own source in the description pool."""
        recs = list(session.run(
            _DESC_KNN_CYPHER, idx=DESC_INDEX, k=K_LEVELS[-1],
            fetch=KNN_OVERFETCH * K_LEVELS[-1],
            vec=[float(x) for x in vec],
            datasetId=DATASET_ID, excludedSections=_EXCLUDED_PARAM))
        rows = [dict(r) for r in recs if r["sim"] is not None]
        if not rows:
            return
        dists = np.array([1.0 - float(r["sim"]) for r in rows])
        vals = _multi_k_support(dists, normalize=False)
        slot: dict = {}
        desc_sources.append(slot)
        fresh = _record_desc(slot, rows, vals)
        walk.append({"part": label, "path": "desc", "chunks": len(rows), "new": fresh})

    def open_desc_area(vec, label):
        """A description area for the curve walk: the chunk-description
        neighborhood of one prompt vector, clustered exactly like a tag pool.
        Its base is the raw fuzzy support of each chunk's distance to the
        vector; the neighborhood anchors at its highest-support chunk and its
        dendrogram chain supplies widening events on the same cosine-height
        scale the tag areas walk. Opens the anchor level now and returns the
        widening events [(height, open_fn)] for the frontier."""
        recs = list(session.run(
            _DESC_KNN_EMB_CYPHER, idx=DESC_INDEX, k=K_LEVELS[-1],
            fetch=KNN_OVERFETCH * K_LEVELS[-1],
            vec=[float(x) for x in vec],
            datasetId=DATASET_ID, excludedSections=_EXCLUDED_PARAM))
        rows = [dict(r) for r in recs
                if r["sim"] is not None and r["desc_emb"] is not None]
        if not rows:
            return []
        dists = np.array([1.0 - float(r["sim"]) for r in rows])
        vals = _multi_k_support(dists, normalize=False)
        embs = _unit(np.asarray([r["desc_emb"] for r in rows], dtype=np.float64))
        chain = _level_chain(embs, int(np.argmax(vals)))
        slot: dict = {}
        desc_sources.append(slot)

        def open_members(height, added):
            fresh = _record_desc(slot, [rows[j] for j in added],
                                 [vals[j] for j in added])
            walk.append({"part": label, "path": "desc", "height": round(height, 4),
                         "chunks": len(added), "new": fresh})

        open_members(*chain[0])
        return [(h, (lambda h=h, added=added: open_members(h, added)))
                for h, added in chain[1:]]

    def open_stated_scope():
        """The stated-scope path: the query names its scope, so the pool is the
        matching chunk set — no clustering, no similarity gate to get in. Its
        base is fuzzy support over description distances to the need (extended
        across the whole matching set — a stated fact has no horizon); the match
        fraction is its priority modifier. Absent hints mean no scope path."""
        terms, params = _hint_terms(gate)
        if not terms:
            return
        matched_expr = " + ".join(f"(CASE WHEN {t} THEN 1 ELSE 0 END)" for t in terms)
        cypher = f"""
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
WHERE coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND NOT (coalesce(c.section, "") IN $excludedSections)
  AND ({" OR ".join(terms)})
WITH c, f, ({matched_expr}) AS matched,
     vector.similarity.cosine(c.desc_emb, $descVec) AS sim
RETURN c.chunk_id AS chunkId, c.locator_json AS locator,
       f.rel_path AS relpath, f.sha256 AS sha256, matched, sim
ORDER BY sim DESC, chunkId
"""
        recs = list(session.run(cypher, descVec=[float(x) for x in need_vec],
                                datasetId=DATASET_ID,
                                excludedSections=_EXCLUDED_PARAM, **params))
        rows = [dict(r) for r in recs if r["sim"] is not None]
        if not rows:
            return
        nonlocal scope_n
        scope_n = len(rows)
        dists = np.array([1.0 - float(r["sim"]) for r in rows])
        vals = _multi_k_support(dists, extend=True, normalize=False)
        fresh = 0
        for row, val in zip(rows, vals):
            cid = row["chunkId"]
            if cid not in pool:
                fresh += 1
                pool.add(cid)
            sup = float(val)
            if sup > scope_base.get(cid, 0.0):
                scope_base[cid] = sup
                scope_match[cid] = float(row["matched"]) / len(terms)
            payload.setdefault(cid, _pointer(row))
        walk.append({"part": "stated-scope", "path": "scope",
                     "chunks": len(rows), "new": fresh})

    for pi, lv in anchors:
        open_level(0.0, pi, lv)

    stopped = False
    opened = 0
    if CURVE_WALK:
        seq = iter(range(1 << 30))
        frontier = [(h, next(seq), (lambda h=h, pi=pi, lv=lv: open_level(h, pi, lv)))
                    for h, pi, lv in widening]
        for pi in range(len(parts)):
            frontier += [(h, next(seq), fn) for h, fn in
                         open_desc_area(part_vecs[pi], parts[pi]["t"])]
        if plan["description"] not in (
                {p["t"] for p in parts} | {_readable(p["t"]) for p in parts}):
            # the whole-need description is its own area: the question as one
            # thought, matched against the chunk descriptions
            frontier += [(h, next(seq), fn) for h, fn in
                         open_desc_area(need_vec, "description")]
        open_stated_scope()
        # One frontier, cheapest opening anywhere first; the stop is the gap
        # that sits two standard deviations above the mean of the walked gaps.
        frontier.sort(key=lambda e: e[:2])
        gaps, last_h = [], 0.0
        for height, _, open_fn in frontier:
            gap = height - last_h
            if _gap_break(gaps, gap):
                stopped = True
                break
            open_fn()
            gaps.append(gap)
            last_h = height
        opened = len(gaps)
    else:
        for pi in range(len(parts)):
            open_desc(part_vecs[pi], parts[pi]["t"])
        open_stated_scope()
        for height, pi, lv in widening:
            # the widening gate: the whole pool, or with HERB_WALK_GATE=1
            # only the chunks the tag areas themselves reached
            walked = len(tag_reached) if WALK_GATE else len(pool)
            if walked >= k:
                break
            open_level(height, pi, lv)
    if not pool:
        raise RuntimeError("opened areas produced no evidence chunks")
    if CURVE_WALK and not semantic:
        raise RuntimeError(
            "semantic areas vouch for no chunks — stated scope alone filled the pool")

    # Each path folds a chunk's best support over the parts/sources that vouch
    # for it (HERB_AGG: sum lifts a corroborated chunk, max keeps its single
    # best), the bases reach a comparable scale (HERB_NORM / HERB_NORM_SCOPE),
    # the strength-graded modifiers lift them, and the three combine as a
    # weighted sum over the union.
    tag_base = _agg(tag_slots)
    desc_base = _agg(desc_sources)
    tag_norm, desc_norm, scope_norm = _normalize(
        tag_base, desc_base, scope_base, _n_levels(scope_n))
    tag_score, desc_score, scope_score = {}, {}, {}
    for cid, nb in tag_norm.items():
        ft, wc, rel = tag_mods[cid]
        tag_score[cid] = nb * _mod(ft, STR_FACET) * _mod(wc, STR_WCHUNK) * _mod(rel, STR_RELEVANCE)
    for cid, nb in desc_norm.items():
        desc_score[cid] = nb * _mod(desc_hint.get(cid, 1.0), STR_DESC_HINT)
    for cid, nb in scope_norm.items():
        scope_score[cid] = nb * _mod(scope_match.get(cid, 1.0), STR_SCOPE_MATCH)

    totals: dict = {}
    for cid, s in tag_score.items():
        totals[cid] = totals.get(cid, 0.0) + W_TAG * s
    for cid, s in desc_score.items():
        totals[cid] = totals.get(cid, 0.0) + W_DESC * s
    for cid, s in scope_score.items():
        totals[cid] = totals.get(cid, 0.0) + W_SCOPE * s

    ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    kept_k = min(len(semantic), k) if CURVE_WALK else k
    ranked = ranked[:kept_k]
    selected = [{**payload[cid], "score": round(sc, 4)} for cid, sc in ranked]

    meta = {
        # a serializable copy of the plan: private keys carry callables and
        # stay out
        "plan": {key: val for key, val in plan.items() if not key.startswith("_")},
        "knn_levels": list(K_LEVELS),
        "parts": level_log,
        "walk": walk,
        "retrieved": len(selected),
    }
    if CURVE_WALK:
        meta["curve_walk"] = {"pool": len(totals), "semantic": len(semantic),
                              "kept": kept_k, "stopped": stopped,
                              "opened": opened}
    if STR_GUIDE > 0:
        meta["guide"] = {
            "str": STR_GUIDE, "tau": GUIDE_TAU, "C": GUIDE_C, "m": GUIDE_M,
            "matched": guide_stats["matched"],
            "unmatched": guide_stats["unmatched"],
            "mean_g": round(guide_stats["g_sum"] / guide_stats["g_n"], 4)
                      if guide_stats["g_n"] else 0.0}
    if DOOR_TRACE:
        meta["door_trace"] = [
            {**payload[cid],
             "tag": round(W_TAG * tag_score.get(cid, 0.0), 6),
             "desc": round(W_DESC * desc_score.get(cid, 0.0), 6),
             "scope": round(W_SCOPE * scope_score.get(cid, 0.0), 6),
             "total": round(totals[cid], 6)}
            for cid in sorted(totals, key=lambda c: (-totals[c], c))]
    return selected, usage, meta


# --- resolve -----------------------------------------------------------------

def _load_verified_doc(relpath: str, sha256: str, cache: dict):
    key = (relpath, sha256)
    doc = cache.get(key)
    if doc is not None:
        return doc
    path = (RAW_ROOT / relpath).resolve()
    if not path.is_relative_to(RAW_ROOT):
        raise RuntimeError(
            f"locator relpath {relpath!r} resolves outside the raw root — refusing to read it")
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != sha256:
        raise RuntimeError(
            f"HASH MISMATCH for {relpath}: graph built against {sha256[:12]}…, "
            f"on-disk is {actual[:12]}…. Refusing to serve drifted content.")
    doc = json.loads(data.decode("utf-8"))
    cache[key] = doc
    return doc


def _nth_entry(root, i: int):
    if isinstance(root, list):
        return root[i]
    k, v = list(root.items())[i]
    return {k: v}


def _resolve_chunk(row: dict, cache: dict) -> tuple:
    loc = json.loads(row["locator"])
    doc = _load_verified_doc(row["relpath"], row["sha256"], cache)

    if "metadata" in loc:
        if "indices" in loc:
            recs = [_nth_entry(doc, i) for i in loc["indices"]]
        else:
            rec = _nth_entry(doc, loc["index"])
            if loc.get("subsection"):
                rec = rec[loc["subsection"]]
            recs = [rec]
        return "\n".join(json.dumps(r, ensure_ascii=False) for r in recs), []

    arr = doc[loc["section"]]
    if "char_range" in loc:
        rec = arr[loc["index"]]
        start, end = loc["char_range"]
        text = rec[loc["field"]][start:end]
        aid = rec.get("id")
        return text, [str(aid)] if aid is not None else []

    recs = [arr[i] for i in (loc["indices"] if "indices" in loc else [loc["index"]])]
    ids, seen = [], set()
    for rec in recs:
        aid = rec.get("id")
        if aid is not None and aid not in seen:
            seen.add(aid)
            ids.append(str(aid))
    return "\n".join(json.dumps(r, ensure_ascii=False) for r in recs), ids


# --- answer ------------------------------------------------------------------

def _sufficient_cut(text: str, contexts: list) -> tuple:
    """The interpreter holds the conversation: evidence is shown cumulatively
    at the doubling level sequence (capped at what was retrieved) and at each
    level the interpreter decides whether it can answer. Sufficient → keep
    exactly the evidence seen; never sufficient → the full retrieval stands
    (the hard k cap is the forced stop). A review-call failure keeps the full
    retrieval and is logged, never silent; the usage the failed call spent
    still counts.
    Returns (kept, review_log, calls, tokens_in, tokens_out, time_s)."""
    kept = len(contexts)
    log = []
    calls = tok_in = tok_out = 0
    time_s = 0.0
    for lv in [l for l in K_LEVELS if l < len(contexts)]:
        digest = "\n\n".join(f"[{i + 1}] {contexts[i][:240]}" for i in range(lv))
        try:
            verdict, ti, to, el = _chat_json(
                INTERPRET_MODEL, _REVIEW_SYSTEM,
                f"Question: {text}\n\nEvidence so far (top {lv}):\n{digest}", 128)
        except abort.Aborted:  # q pressed mid-call — stop the run, no fallback
            raise
        except Exception as e:
            calls += getattr(e, "calls", 0)
            tok_in += getattr(e, "tokens_in", 0)
            tok_out += getattr(e, "tokens_out", 0)
            time_s += getattr(e, "time_s", 0.0)
            log.append({"at": lv, "decision": "fallback",
                        "error": f"{type(e).__name__}: {e}"})
            break
        calls += 1
        tok_in += ti
        tok_out += to
        time_s += el
        sufficient = bool(verdict.get("sufficient"))
        log.append({"at": lv, "sufficient": sufficient})
        if sufficient:
            kept = lv
            break
    return kept, log, calls, tok_in, tok_out, time_s


def answer_one_question(question, prepared: Prepared, generate: Optional[Generator],
                        k: int = 50) -> ArmOutput:
    _, text = _qid_text(question)

    t0 = time.perf_counter()
    plan, interp_calls, interp_in, interp_out, interp_time = _interpret_cached(text, INTERPRET_MODEL)
    with prepared.driver.session(database=DATABASE) as session:
        rows, ground_usage, meta = _retrieve(session, plan, k)
    meta["interpreter"] = {"model": INTERPRET_MODEL, "backend": "claude-cli"}
    retrieve_wall = time.perf_counter() - t0

    doc_cache: dict = {}
    contexts: list[str] = []
    context_ids: list[str] = []
    chunk_id_lists: list[list[str]] = []
    seen: set[str] = set()
    for row in rows:
        chunk_text, ids = _resolve_chunk(row, doc_cache)
        contexts.append(chunk_text)
        chunk_id_lists.append(ids)
        for aid in ids:
            if aid not in seen:
                seen.add(aid)
                context_ids.append(aid)
    # The interpreter decides when it has enough: evidence levels reviewed
    # cumulatively; sufficient → keep exactly what was seen, hard k the cap.
    # With HERB_NO_REVIEW=1 the review is off and the full retrieved set stands,
    # so a retrieval sweep measures retrieval with no per-question content cut.
    if NO_REVIEW:
        kept, review_log = len(contexts), []
        rev_calls = rev_in = rev_out = 0
        rev_time = 0.0
    else:
        kept, review_log, rev_calls, rev_in, rev_out, rev_time = _sufficient_cut(text, contexts)
    contexts = contexts[:kept]
    chunk_id_lists = chunk_id_lists[:kept]
    seen = set()
    context_ids = []
    for ids in chunk_id_lists:
        for aid in ids:
            if aid not in seen:
                seen.add(aid)
                context_ids.append(aid)
    meta["review"] = {"kept": kept, "rounds": review_log}
    # meta["retrieved"] counts what retrieval selected; "returned" what the
    # sufficiency cut let through
    meta["returned"] = len(contexts)
    # per-chunk artifact ids, aligned with contexts — depth studies truncate
    # chunks and rebuild the id list from what is kept
    meta["chunk_ids"] = chunk_id_lists

    search_time_s = max(0.0, retrieve_wall - interp_time - ground_usage.time_s)
    retrieval_usage = ModelUsage(
        calls=interp_calls + ground_usage.calls + rev_calls,
        tokens_in=interp_in + ground_usage.tokens_in + rev_in,
        tokens_out=interp_out + ground_usage.tokens_out + rev_out,
        time_s=interp_time + ground_usage.time_s + rev_time)

    if generate is None:
        answer, gen = "", ModelUsage()
    else:
        g0 = time.perf_counter()
        result = generate(text, contexts)
        answer, gen = unpack_generation(result, time.perf_counter() - g0)

    return ArmOutput(
        answer=answer,
        contexts=contexts,
        context_ids=context_ids,
        search_time_s=search_time_s,
        generator=gen,
        retrieval=retrieval_usage,
        meta=meta,
    )

"""artefact_v1_relevance_weight.py — the ARTEFACT-V1 arm resolved by the
multi-step relevance weight: one operation over the derived facet layer and the
whole tag vocabulary, with no selection anywhere in it.

The graph under test is the same `herb-eval` build the other artefact_v1 legs
query, read strictly read-only: tag embeddings, chunk description embeddings,
chunk pointers and hard fields. The facet layer is the derived one
`build_facet_layer.py` computes, read from its cache entry
(`output/derived_facet_cache/<entry>/facets.npz`) and never from the graph,
which keeps the model-emitted layer it holds.

One scale, stated once: every distance here is the full cosine distance
1 − cos over unit vectors. The tag-to-tag table the areas cluster under is
computed once at prepare and held as a float64 memmap under
`output/tag_distance_cache/<entry>/`, keyed by the vocabulary it was built from,
so a run that finds a complete entry builds nothing and every query slices its
region's rows and columns out of it. The Neo4j vector indexes, whose score is
the half-scale (1 + cos)/2, are not queried at all.

The mechanism, prompt in to answer out:

  1. affinity — the question embeds once (query side) and scores every one of
     the layer's tags: support(r) = ln(P/r) / d(r)², r the tag's rank by cosine
     over the whole vocabulary and P its size. That is the continuous limit of
     the doubling level ladder — across the ranks the ladder {8, 16, 32, 64}
     spans, it carries floor(log2(64/r)) + 1 levels at rank r — so no k, no
     pool and no ladder constant decides which tags carry weight. The
     logarithm's base is a global factor on the whole vector, so it cancels in
     every comparison the arm makes. The nearest tag carries most, the last
     exactly none.

  2. demand — how relevant each facet is for this prompt, read from the
     prompt's own position and nothing else: the affinity-weighted deviation of
     the query's tag neighbourhood from the corpus in each facet, in that
     facet's own tag-marginal spread, softmaxed onto the five and then shrunk
     toward uniform by that facet's measured reliability — the ICC the layer's
     build recorded, where it measured one, times a query-side split-half
     reliability measured once at prepare (the tag vocabulary split by the
     build's own sha256 parity, every chunk description probing both halves,
     Spearman-Brown on the half-correlation). A facet that cannot measure
     reliably cannot steer the retrieval, and no facet is weighted on an
     unmeasured reliability. HERB_DEMAND=flat is the control: the identical
     operator with the five facets weighted equally. HERB_DEMAND=centred
     weights by the read's deviation from the corpus-expected demand — the
     same read over a probe bank of the corpus's own chunk descriptions,
     averaged at prepare — so what carries weight is where the prompt departs
     from the corpus, and a facet it wants less than the corpus does
     subtracts.

  3. the one operation — per edge, the prompt's facet demand meets the tag's
     per-facet weight on that chunk in one inner product, and that times the
     tag's affinity is what the edge carries:

         value(c) = Σ      affinity(t) · ⟨demand, φ(t, c) − ½⟩
                   t ∈ T(c)

     ½ is the calibrated scale's neutral point — the mid-rank CDF sends every
     facet's median there — and a cell the layer marks unevidenced is zeroed
     outright. That zero walks two paths. In the chunk value an unevidenced
     cell contributes exactly nothing — no admission test, no exclusion, no
     gate. In the tag's facet character, silence dilutes: the per-tag marginal
     averages over all the tag's edges, so a tag is as facetal as its edges
     make it, and a tag mostly silent on a facet reads weakly there. The
     layer's magnitude `w_chunk` is sqrt(A·Q) of the same facet row — a
     deterministic function of the vector the inner product reads — so the
     combination folds the tag's chunk relevance weight implicitly.
     Combination happens at the edge, not as separate path scores combined at
     the end, and every chunk in the graph receives a value.

  4. areas — the query-activated tag region is the ranked prefix of tags
     carrying at least the uniform share 1/P of the whole vocabulary's support
     mass; past it every remaining tag carries less, so the support
     distribution sets its own edge. The region clusters once per facet under
     that facet's own weighting: two tags that differ in facet f sit that much
     further apart in facet f's clustering, each difference in the facet's own
     corpus spread, so the five areas are five shapes of one region. An area's
     own extent is its best fit — the interior maximum of the silhouette over
     the anchor's containing-cluster chain. The areas open in the order the
     prompt ranks them, each banking the hit of what it opened; the first area
     stops at its best fit, and from there the standard is the median of what
     is banked so far. An area whose hits are weak against it widens one level
     at a time until it clears the standard or the chain ends — the only two
     stops — and its hit is the hit of everything it opened. K is the distinct
     chunks the opened areas reached, capped by the caller's k.

  5. guides — stated scope and the description are guiding priority, "if they
     fit": each is rank-calibrated over the chunk population and zeroed below
     its own median, then combined with the value by noisy-OR,
     1 − (1 − base)(1 − fit). A guide that does not fit contributes exactly
     nothing; one that does can only promote, never demote; and the result
     stays inside [0, 1), monotone in every term.

Nothing here reads `relevance_to_file`, and no value propagates through the
file level.

The graph stores references, never content: a retrieved chunk is a pointer —
`locator_json` on the chunk plus `rel_path` + `sha256` on its file — resolved
from raw under `v3/data/raw` at answer time and hash-verified by artefact_v1's
own resolver. `context_ids` are HERB artifact ids from the raw records. The
oracle sections are outside the chunk population. The whole layer loads at
prepare, so answering a question opens no graph session at all.

Contract: `prepare_over_corpus(corpus) -> Prepared`; `answer_one_question(...)
-> ArmOutput`. The question is read for id + text ONLY.
"""
from __future__ import annotations

print("artefact_v1_relevance_weight: the multi-step relevance weight over the "
      "derived facet layer — loading numpy + scipy …", flush=True)

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform

from build_facet_layer import (
    COS_BLOCK, DERIVED_CACHE_DIR, ICC_CEIL, _derived_key, fetch_matrix,
    midrank_cdf, sha256_parity,
)
from contract import ArmOutput, BuildStats, ModelUsage, unpack_generation
from pipelines.artefact_v1 import (
    ALL_FACETS, DATABASE, DATASET_ID, EXCLUDED_SECTIONS, OFFERED_SECTIONS,
    RUN_ID, _driver, _embed_cached, _qid_text, _readable, _resolve_chunk, _unit,
)
from pipelines.vector import EMBED_MODEL
from progress import progress

# --- constants ---------------------------------------------------------------

INTERPRET_MODEL = "deterministic"

# The tag-to-tag cosine distance table: one cache entry per vocabulary, holding
# the float64 memmap the areas are clustered from and the manifest that marks it
# complete.
TAG_DISTANCE_CACHE_DIR = (Path(__file__).resolve().parent.parent / "output" /
                          "tag_distance_cache")

# The facet demand: `read` takes it from the query's own tag neighbourhood,
# `flat` weights the five facets equally — the control that isolates the demand
# from everything else in the operator — and `centred` takes the read less the
# corpus-expected demand, a deviation whose negative entries subtract.
DEMAND = os.environ.get("HERB_DEMAND", "read")
if DEMAND not in ("read", "flat", "centred"):
    raise ValueError(
        f"HERB_DEMAND must be 'read', 'flat' or 'centred', got {DEMAND!r}")

# The point the facet weights centre on before the inner product: the mid-rank
# CDF sends every facet's median to 1/2, so an edge cell at the median says
# nothing and centres to exactly zero.
PHI_NEUTRAL = 0.5

# Divide-by-zero guard on every quantity this arm divides by: the distance in
# the inverse-square support, the silhouette's own scale, and a facet's
# tag-marginal spread.
DIVIDE_FLOOR = 1e-6

# The facets whose demand carries a build-measured ICC factor, and the manifest
# key each is read from. Every facet's reliability multiplies this factor with
# the query-side split-half measurement; a facet absent from the map carries
# the query-side measurement alone.
LAYER_ICC = {"topic": "icc_topic_vote", "temporal": "icc_temporal"}

# Stated scope, read from the question's literal form.
_EID = re.compile(r"\beid_[0-9a-f]+\b")
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_SCOPE_FIELDS = ("product", "section", "channel", "employee_id", "years")

# Manifest provenance: the regime switches the runner copies into
# run_manifest.json.
RETRIEVAL_FLAGS = {"HERB_DEMAND": DEMAND}

Generator = Callable[[str, list], object]


# --- Cypher ------------------------------------------------------------------

# The chunk population: every chunk of the dataset with its pointer, the guard
# fields deciding whether it is retrievable at all, and the hard fields stated
# scope matches on.
_CHUNKS_CYPHER = """
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
WHERE ($datasetId IS NULL OR f.dataset_id = $datasetId)
RETURN c.chunk_id AS chunkId, c.locator_json AS locator, f.rel_path AS relpath,
       f.sha256 AS sha256, coalesce(c.empty, false) AS empty,
       coalesce(c.section, "") AS section, c.product AS product,
       c.channel AS channel, c.employee_id AS employee_id, c.years AS years
ORDER BY chunkId
"""

_TAG_EMB_CYPHER = """
UNWIND $keys AS key
MATCH (t:Tag {name: key})
RETURN t.name AS key, t.emb AS emb
"""

_CHUNK_EMB_CYPHER = """
UNWIND $keys AS key
MATCH (c:Chunk {chunk_id: key})
RETURN c.chunk_id AS key, c.desc_emb AS emb
"""

_PRODUCTS_CYPHER = """
MATCH (c:Chunk) WHERE c.product IS NOT NULL
RETURN DISTINCT c.product AS product ORDER BY product
"""

# Retrievability is a graph property, verified at prepare: a chunk carrying an
# excluded section would take a value and could bank an area's hit while never
# being returnable, so the graph must hold none.
_ORACLE_COUNT_CYPHER = """
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
WHERE ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND coalesce(c.section, "") IN $excludedSections
RETURN count(c) AS n
"""


# --- prepare -----------------------------------------------------------------

@dataclass
class Layer:
    """Everything one prompt is resolved against, loaded once per process."""
    tags: list                    # the layer's tag vocabulary, in index order
    tag_emb: np.ndarray           # (T, dim) unit rows
    tag_distance: np.ndarray      # (T, T) float64 memmap of 1 − cos over the tags
    chunk_ids: list               # the chunk population, in index order
    desc_emb: np.ndarray          # (C, dim) unit rows
    rows: np.ndarray              # (E,) tag index per edge
    cols: np.ndarray              # (E,) chunk index per edge
    phi_centred: np.ndarray       # (E, 5) weights less the neutral 1/2; unevidenced cells zero
    marginal: np.ndarray          # (T, 5) each tag's mean facet weight over its edges
    marginal_mean: np.ndarray     # (5,) corpus mean of those marginals
    marginal_sd: np.ndarray       # (5,) their corpus spread
    reliability: np.ndarray       # (5,) build ICC × query-side split-half, per facet
    expected_demand: Optional[np.ndarray]  # (5,) the probe bank's mean demand, under `centred`
    retrievable: np.ndarray       # (C,) bool — the oracle sections sit outside it
    pointers: list                # (C,) resolve rows: chunkId / locator / relpath / sha256
    fields: list                  # (C,) hard fields stated scope matches on
    products: list                # the graph's own product vocabulary


@dataclass
class Prepared:
    layer: Layer
    build_stats: Optional[BuildStats] = None


def _read_layer_cache() -> tuple:
    """The derived facet layer -> (per-edge weights, per-cell evidence mask,
    edge tag names, edge chunk ids, build manifest). A missing entry fails loud
    naming the build step."""
    entry = DERIVED_CACHE_DIR / _derived_key()
    if not (entry / "manifest.json").is_file():
        raise RuntimeError(
            f"derived facet layer missing at {entry} — "
            f"run `python build_facet_layer.py` once.")
    manifest = json.loads((entry / "manifest.json").read_text(encoding="utf-8"))
    with np.load(entry / "facets.npz", allow_pickle=False) as z:
        phi = z["phi"].astype(np.float64)
        evidenced = z["evidenced"].astype(bool)
        edge_tag = [str(t) for t in z["tag"]]
        edge_chunk = [str(c) for c in z["chunk_id"]]
    print(f"  layer {entry.name}: {len(phi)} edges, "
          f"{len(set(edge_tag))} tags", flush=True)
    return phi, evidenced, edge_tag, edge_chunk, manifest


def _tag_distance_key(tags: list, tag_emb: np.ndarray) -> str:
    """The cache entry name for one vocabulary: the database, the tagging run,
    the vocabulary size, and a digest of the tag names and the vectors they
    stand at. A changed tag set or a re-embedded layer digests differently and
    lands in a sibling entry."""
    digest = hashlib.sha256()
    digest.update("\n".join(tags).encode("utf-8"))
    digest.update(np.ascontiguousarray(tag_emb).tobytes())
    return f"{DATABASE}__{RUN_ID}__t{len(tags)}__{digest.hexdigest()[:16]}"


def _tag_distance_table(tags: list, tag_emb: np.ndarray) -> np.ndarray:
    """The whole vocabulary's tag-to-tag cosine distance, as a float64 memmap
    under `output/tag_distance_cache/<entry>/`. An entry whose manifest is
    written is complete and is reused as it stands; anything else is built from
    the unit vectors in one blocked pass and marked complete by writing the
    manifest last."""
    entry = TAG_DISTANCE_CACHE_DIR / _tag_distance_key(tags, tag_emb)
    path = entry / "distance.npy"
    if (entry / "manifest.json").is_file():
        table = np.load(path, mmap_mode="r")
        print(f"  tag geometry {entry.name}: {table.nbytes / 1e9:.3f} GB reused",
              flush=True)
        return table

    t0 = time.perf_counter()
    entry.mkdir(parents=True, exist_ok=True)
    u = tag_emb.astype(np.float64)
    out = np.lib.format.open_memmap(path, mode="w+", dtype=np.float64,
                                    shape=(len(u), len(u)))
    bar = progress(total=len(u), desc="tag geometry", unit="tag")
    for i in range(0, len(u), COS_BLOCK):
        out[i:i + COS_BLOCK] = 1.0 - np.clip(u[i:i + COS_BLOCK] @ u.T, -1.0, 1.0)
        bar.update(min(COS_BLOCK, len(u) - i))
    bar.close()
    out.flush()
    del out
    elapsed = time.perf_counter() - t0
    (entry / "manifest.json").write_text(json.dumps({
        "database": DATABASE, "run_id": RUN_ID, "n_tags": len(tags),
        "dim": int(tag_emb.shape[1]), "dtype": "float64",
        "bytes": path.stat().st_size, "build_time_s": elapsed,
    }, indent=1), encoding="utf-8")
    table = np.load(path, mmap_mode="r")
    print(f"  tag geometry {entry.name}: {table.nbytes / 1e9:.3f} GB built in "
          f"{elapsed:.1f}s", flush=True)
    return table


def _facet_reliability(manifest: dict, query_rho: np.ndarray) -> np.ndarray:
    """Each facet's reliability, in ALL_FACETS order: the ICC the layer's build
    measured, where it measured one, times the query-side split-half
    reliability. A facet without a build ICC carries the query-side measurement
    alone — no facet is weighted on an unmeasured reliability."""
    build = np.array([float(manifest[LAYER_ICC[f]]) if f in LAYER_ICC else 1.0
                      for f in ALL_FACETS])
    return build * query_rho


def _query_reliability(tags: list, tag_emb: np.ndarray, marginal: np.ndarray,
                       marginal_mean: np.ndarray, marginal_sd: np.ndarray,
                       desc_emb: np.ndarray) -> np.ndarray:
    """The query side of each facet's reliability, measured at prepare with no
    model calls: the tag vocabulary splits by sha256 parity, every chunk
    description vector probes both halves as a query, and a facet's value is
    the Spearman-Brown step-up of the correlation between its two half-reads
    across the probe bank — how well the demand read reproduces from half the
    vocabulary. Deterministic: the split is content-addressed and the probe
    bank is the corpus itself."""
    parity = sha256_parity(tags)
    reads = []
    for half in (0, 1):
        idx = np.flatnonzero(parity == half)
        if len(idx) < 2:
            raise RuntimeError(
                f"sha256-parity half {half} holds {len(idx)} tag(s) — too few "
                f"to rank a half-read")
        M = (marginal[idx] - marginal_mean) / marginal_sd
        half_emb = tag_emb[idx]
        out = np.empty((len(desc_emb), len(ALL_FACETS)))
        bar = progress(total=len(desc_emb), desc=f"half-read {half}", unit="probe")
        for i in range(0, len(desc_emb), COS_BLOCK):
            cos = (desc_emb[i:i + COS_BLOCK] @ half_emb.T).astype(np.float64)
            order = np.argsort(-cos, axis=1, kind="stable")
            rank = np.empty_like(cos)
            np.put_along_axis(
                rank, order,
                np.arange(1, len(idx) + 1, dtype=np.float64)[None, :], axis=1)
            support = (np.log(len(idx) / rank) /
                       np.maximum(1.0 - cos, DIVIDE_FLOOR) ** 2)
            weight = support / np.maximum(support.sum(axis=1, keepdims=True),
                                          DIVIDE_FLOOR)
            out[i:i + len(cos)] = weight @ M
            bar.update(len(cos))
        bar.close()
        reads.append(out)
    a, b = (r - r.mean(axis=0) for r in reads)
    denom = np.sqrt((a * a).sum(axis=0) * (b * b).sum(axis=0))
    r = np.divide((a * b).sum(axis=0), denom,
                  out=np.zeros(len(ALL_FACETS)), where=denom > 0)
    return np.clip(np.where(r > 0, 2.0 * r / (1.0 + r), 0.0), 0.0, ICC_CEIL)


def _marginals(phi_centred: np.ndarray, rows: np.ndarray, n_tags: int) -> tuple:
    """Each tag's mean facet weight over its own edges -> (marginals, their
    corpus mean, their corpus spread). The demand reads a query's neighbourhood
    against these, so they are tag-side statistics over the centred weights."""
    total = np.zeros((n_tags, len(ALL_FACETS)))
    count = np.zeros(n_tags)
    np.add.at(total, rows, phi_centred)
    np.add.at(count, rows, 1.0)
    marginal = total / np.maximum(count, 1.0)[:, None]
    present = count > 0
    return (marginal, marginal[present].mean(axis=0),
            np.maximum(marginal[present].std(axis=0), DIVIDE_FLOOR))


def _demand_read(marginal: np.ndarray, marginal_mean: np.ndarray,
                 marginal_sd: np.ndarray, reliability: np.ndarray,
                 support: np.ndarray) -> np.ndarray:
    """The five facet weights one tag neighbourhood reads: the affinity-weighted
    deviation of the neighbourhood from the corpus, per facet, in that facet's
    own tag-marginal spread, softmaxed onto the five and shrunk toward uniform
    at each facet's measured reliability. A stack of supports reads as a bank,
    one demand per row."""
    weight = support / support.sum(axis=-1, keepdims=True)
    scaled = (weight @ (marginal - marginal_mean)) / marginal_sd
    read = np.exp(scaled - scaled.max(axis=-1, keepdims=True))
    read = read / read.sum(axis=-1, keepdims=True)
    shrunk = reliability * read + (1.0 - reliability) / len(ALL_FACETS)
    return shrunk / shrunk.sum(axis=-1, keepdims=True)


def _expected_demand(tag_emb: np.ndarray, marginal: np.ndarray,
                     marginal_mean: np.ndarray, marginal_sd: np.ndarray,
                     reliability: np.ndarray, desc_emb: np.ndarray) -> np.ndarray:
    """What the corpus itself demands, measured at prepare with no model calls:
    every chunk description vector probes the whole tag vocabulary as a query,
    each probe reads the demand a prompt would read, and the five weights are
    the mean over the bank. Deterministic — the bank is the corpus and the read
    is the one a prompt gets."""
    total = np.zeros(len(ALL_FACETS))
    bar = progress(total=len(desc_emb), desc="expected demand", unit="probe")
    for i in range(0, len(desc_emb), COS_BLOCK):
        cos = (desc_emb[i:i + COS_BLOCK] @ tag_emb.T).astype(np.float64)
        order = np.argsort(-cos, axis=1, kind="stable")
        rank = np.empty_like(cos)
        np.put_along_axis(
            rank, order,
            np.arange(1, len(tag_emb) + 1, dtype=np.float64)[None, :], axis=1)
        support = (np.log(len(tag_emb) / rank) /
                   np.maximum(1.0 - cos, DIVIDE_FLOOR) ** 2)
        total += _demand_read(marginal, marginal_mean, marginal_sd, reliability,
                              support).sum(axis=0)
        bar.update(len(cos))
    bar.close()
    expected = total / len(desc_emb)
    print("  expected demand " +
          " ".join(f"{f}={v:.3f}" for f, v in zip(ALL_FACETS, expected)),
          flush=True)
    return expected


def _build_layer(chunk_rows: list, products: list, tags: list, tag_emb: np.ndarray,
                 desc_emb: np.ndarray, edge_tag: list, edge_chunk: list,
                 phi: np.ndarray, evidenced: np.ndarray, manifest: dict) -> Layer:
    """The graph rows, the cached layer and the tag geometry as the one
    structure a prompt is resolved against. The facet weights are centred on the
    calibrated scale's neutral point and every unevidenced cell is zeroed
    outright — exactly nothing in any chunk's value, silence diluting the tag's
    marginals; a chunk the layer was built on that the graph does not carry
    fails loud rather than resolving to the wrong pointer."""
    tag_at = {t: i for i, t in enumerate(tags)}
    chunk_at = {r["chunkId"]: i for i, r in enumerate(chunk_rows)}
    absent = sorted({c for c in edge_chunk if c not in chunk_at})
    if absent:
        raise RuntimeError(
            f"{len(absent)} chunk(s) the facet layer was built on are not in "
            f"{DATABASE!r} (e.g. {absent[:3]}) — rebuild the layer.")
    tag_distance = _tag_distance_table(tags, tag_emb)
    rows = np.array([tag_at[t] for t in edge_tag])
    cols = np.array([chunk_at[c] for c in edge_chunk])
    phi_centred = np.where(evidenced, phi - PHI_NEUTRAL, 0.0)
    marginal, marginal_mean, marginal_sd = _marginals(phi_centred, rows, len(tags))
    query_rho = _query_reliability(tags, tag_emb, marginal, marginal_mean,
                                   marginal_sd, desc_emb)
    reliability = _facet_reliability(manifest, query_rho)
    expected = (_expected_demand(tag_emb, marginal, marginal_mean, marginal_sd,
                                 reliability, desc_emb)
                if DEMAND == "centred" else None)
    return Layer(
        tags=tags, tag_emb=tag_emb, tag_distance=tag_distance,
        chunk_ids=[r["chunkId"] for r in chunk_rows],
        desc_emb=desc_emb, rows=rows, cols=cols, phi_centred=phi_centred,
        marginal=marginal, marginal_mean=marginal_mean, marginal_sd=marginal_sd,
        reliability=reliability, expected_demand=expected,
        retrievable=np.array([not r["empty"] and r["section"] not in EXCLUDED_SECTIONS
                              for r in chunk_rows]),
        pointers=[{k: r[k] for k in ("chunkId", "locator", "relpath", "sha256")}
                  for r in chunk_rows],
        fields=[{k: r[k] for k in _SCOPE_FIELDS} for r in chunk_rows],
        products=products)


def prepare_over_corpus(corpus) -> Prepared:
    """Load the derived facet layer, the tag and chunk-description embeddings,
    the tag-to-tag geometry, and the chunk pointers and hard fields. Read-only:
    the graph is never written, and the session closes before the first
    question."""
    t0 = time.perf_counter()
    phi, evidenced, edge_tag, edge_chunk, manifest = _read_layer_cache()
    drv = _driver()
    try:
        with drv.session(database=DATABASE) as s:
            multi = s.run(
                "MATCH (c:Chunk) WITH c, count { (:File)-[:HAS_CHUNK]->(c) } AS n "
                "WHERE n <> 1 RETURN count(*) AS bad").single()["bad"]
            if multi:
                raise RuntimeError(
                    f"{multi} chunk(s) in {DATABASE!r} without exactly one File — "
                    f"pointer resolution would be ambiguous")
            oracle = s.run(_ORACLE_COUNT_CYPHER, datasetId=DATASET_ID,
                           excludedSections=list(EXCLUDED_SECTIONS)).single()["n"]
            if oracle:
                raise RuntimeError(
                    f"{oracle} chunk(s) in {DATABASE!r} carry an excluded "
                    f"section — scoreable but never returnable")
            print(f"artefact_v1_relevance_weight: reading {DATABASE!r} "
                  f"(about a minute) …", flush=True)
            chunk_rows = [dict(r) for r in s.run(_CHUNKS_CYPHER, datasetId=DATASET_ID)]
            products = [r["product"] for r in s.run(_PRODUCTS_CYPHER)]
            tags = sorted(set(edge_tag))
            print(f"  {len(chunk_rows)} chunks, {len(products)} products", flush=True)
            tag_emb = fetch_matrix(s, _TAG_EMB_CYPHER, tags, "tag")
            desc_emb = fetch_matrix(s, _CHUNK_EMB_CYPHER,
                                    [r["chunkId"] for r in chunk_rows], "chunk")
    finally:
        drv.close()

    layer = _build_layer(chunk_rows, products, tags, tag_emb, desc_emb,
                         edge_tag, edge_chunk, phi, evidenced, manifest)
    elapsed = time.perf_counter() - t0
    print("  reliability " +
          " ".join(f"{f}={v:.3f}" for f, v in zip(ALL_FACETS, layer.reliability)) +
          f"  ({elapsed:.0f}s)", flush=True)
    return Prepared(
        layer=layer,
        build_stats=BuildStats(build_time_s=elapsed, model=ModelUsage(),
                               models=[EMBED_MODEL]),
    )


# --- affinity, demand, and the one operation ---------------------------------

def _affinity(layer: Layer, qvec: np.ndarray) -> tuple:
    """Every tag's affinity to the prompt -> (support, the ranking order).
    support(r) = ln(P/r)/d(r)² over the whole vocabulary: the doubling ladder's
    continuous limit, on the full cosine distance. Ranks tie-break on tag index,
    so one question always reads one ranking."""
    cos = (layer.tag_emb @ qvec).astype(np.float64)
    order = np.argsort(-cos, kind="stable")
    rank = np.empty(len(cos))
    rank[order] = np.arange(1, len(cos) + 1)
    dist = np.maximum(1.0 - cos, DIVIDE_FLOOR)
    return np.log(len(cos) / rank) / dist ** 2, order


def _demand(layer: Layer, support: np.ndarray) -> np.ndarray:
    """The five facet weights the prompt itself carries: what its own tag
    neighbourhood reads. HERB_DEMAND=flat returns the equal weighting instead;
    HERB_DEMAND=centred returns the read less the corpus-expected demand, which
    is no weighting on the simplex — a facet the prompt wants less than the
    corpus does carries a negative weight and subtracts."""
    if DEMAND == "flat":
        n = len(ALL_FACETS)
        return np.full(n, 1.0 / n)
    read = _demand_read(layer.marginal, layer.marginal_mean, layer.marginal_sd,
                        layer.reliability, support)
    return read - layer.expected_demand if DEMAND == "centred" else read


def _edge_weight(layer: Layer, demand: np.ndarray) -> np.ndarray:
    """What one edge carries once the prompt has met it: the demand against the
    tag's centred per-facet weight on that chunk, in one inner product."""
    return layer.phi_centred @ demand


def _chunk_value(layer: Layer, support: np.ndarray,
                 edge_weight: np.ndarray) -> np.ndarray:
    """The one operation folded per chunk: each edge carries its tag's affinity
    times its facet-resolved weight, and a chunk's value is the sum over the
    edges that touch it. Every chunk in the population gets one; nothing is
    admitted and nothing is excluded."""
    return np.bincount(layer.cols, weights=support[layer.rows] * edge_weight,
                       minlength=len(layer.chunk_ids))


# --- areas -------------------------------------------------------------------

def _area_levels(dist: np.ndarray, anchor: int) -> list:
    """The anchor's containing-cluster chain through the dendrogram of one
    facet's distances, finest to coarsest: [(height, added_indices)]. Level 0 is
    the anchor alone; each later level is the merge that grew its cluster,
    carrying that merge's height."""
    n = len(dist)
    if n == 1:
        return [(0.0, [0])]
    Z = linkage(squareform(dist, checks=False), method="average")
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


def _best_fit(dist: np.ndarray, levels: list) -> int:
    """The level the area fits best at: the interior maximum of the silhouette
    over the anchor's chain, every cut scored on the same facet-weighted
    distances the chain was built from. The cut whose members sit closest to
    each other against everything outside is the area's own extent."""
    n = len(dist)
    rowsum = dist.sum(axis=1)
    insum = np.zeros(n)
    inside: list = []
    best, at = -np.inf, 0
    for level, (_, added) in enumerate(levels):
        insum += dist[:, added].sum(axis=1)
        inside.extend(added)
        if len(inside) < 2 or len(inside) >= n:
            continue
        ins = np.array(inside)
        a = insum[ins] / (len(ins) - 1)
        b = (rowsum[ins] - insum[ins]) / (n - len(ins))
        score = float(np.mean((b - a) / np.maximum(np.maximum(a, b), DIVIDE_FLOOR)))
        if score > best:
            best, at = score, level
    return at


def _facet_distances(base: np.ndarray, marginal: np.ndarray,
                     spread: float) -> np.ndarray:
    """One facet's distances over the region: the cosine distance stretched by
    how far apart the two tags stand in that facet, each difference in the
    facet's own corpus spread — so every facet's stretch speaks on one scale
    and each clusters the same region into a different shape."""
    gap = np.abs(marginal[:, None] - marginal[None, :]) / spread
    dist = base * (1.0 + gap)
    np.fill_diagonal(dist, 0.0)
    return dist


def _touched(layer: Layer, tags: np.ndarray) -> np.ndarray:
    """The chunks a set of tags touches."""
    member = np.zeros(len(layer.tags), dtype=bool)
    member[tags] = True
    return np.unique(layer.cols[member[layer.rows]])


def _hit(layer: Layer, support: np.ndarray, edge_weight: np.ndarray,
         tags: np.ndarray) -> float:
    """The best value a set of opened tags puts on any chunk. Hits are measured
    in the one operation's own units, so every area is weak or strong on one
    scale."""
    opened = np.zeros(len(layer.tags))
    opened[tags] = support[tags]
    reach = _touched(layer, tags)
    if not len(reach):
        return 0.0
    return float(_chunk_value(layer, opened, edge_weight)[reach].max())


def _open_area(levels: list, cut: int, standard: Optional[float], hit_of) -> tuple:
    """One area's own opening -> (the positions it opened, its hit, the last
    level it reached). It opens at its best fit; with no standard yet, that is
    the whole area. Against a standard its hit is weak under, it widens one
    level at a time until it clears the standard or the chain ends — the only
    two stops — and its hit is the hit of everything it opened."""
    opened: list = []
    for level in range(cut + 1):
        opened.extend(levels[level][1])
    hit = hit_of(opened)
    widened = cut
    if standard is None:
        return opened, hit, widened
    for level in range(cut + 1, len(levels)):
        if hit >= standard:
            break
        opened.extend(levels[level][1])
        widened = level
        hit = hit_of(opened)
    return opened, hit, widened


def _region(support: np.ndarray, order: np.ndarray) -> np.ndarray:
    """The query-activated tag region: the ranked prefix carrying at least the
    uniform share of the whole vocabulary's support mass. Support falls with
    rank, so past the prefix every remaining tag carries less than 1/P of the
    mass — the support distribution's own stopping point."""
    ranked = support[order]
    share = ranked.sum() / len(ranked)
    n = int(np.searchsorted(-ranked, -share, side="right"))
    return order[:n]


def _walk(layer: Layer, support: np.ndarray, edge_weight: np.ndarray,
          demand: np.ndarray, order: np.ndarray) -> tuple:
    """Open the five areas in the order the prompt ranks them -> (the chunks
    they reached, one log entry per area). Each area banks the hit of what it
    opened; the first opens to its best fit alone, and the standard every
    later area is weighed against is the median of what is banked so far."""
    region = _region(support, order)
    base = np.array(layer.tag_distance[np.ix_(region, region)])
    np.fill_diagonal(base, 0.0)
    anchor = int(np.argmax(support[region]))

    reached: set = set()
    banked: list = []
    log: list = []
    standard: Optional[float] = None
    for fi in np.argsort(-demand, kind="stable"):
        dist = _facet_distances(base, layer.marginal[region, fi],
                                float(layer.marginal_sd[fi]))
        levels = _area_levels(dist, anchor)
        cut = _best_fit(dist, levels)
        opened, hit, widened = _open_area(
            levels, cut, standard,
            lambda o: _hit(layer, support, edge_weight, region[o]))
        touched = _touched(layer, region[opened])
        reached |= set(touched.tolist())
        banked.append(hit)
        standard = float(np.median(banked))
        log.append({"facet": ALL_FACETS[fi], "demand": float(demand[fi]),
                    "best_fit": cut, "levels": widened + 1, "tags": len(opened),
                    "chunks": len(touched), "hit": hit, "standard": standard})
    return reached, log


# --- guides ------------------------------------------------------------------

def _phrase_at(phrase: str, low: str) -> int:
    """Position of `phrase` as whole words in the lowercased question; -1 when
    absent."""
    m = re.search(rf"\b{re.escape(phrase)}\b", low)
    return m.start() if m else -1


def _stated_scope(layer: Layer, text: str) -> dict:
    """What the question literally states about where its answer sits. The
    stated product is the earliest whole-word mention of one the graph's own
    chunks carry, longest name on a tie; a section matches as its enum token or
    its readable phrase; employee ids and years match by pattern. A field the
    question does not name is not stated."""
    low = text.lower()
    words = set(re.findall(r"[a-z_]+", low))
    product, best = None, None
    for p in layer.products:
        at = _phrase_at(p.lower(), low)
        if at >= 0 and (best is None or (at, -len(p)) < best):
            best = (at, -len(p))
            product = p
    section = next((s for s in OFFERED_SECTIONS
                    if s in words or _phrase_at(_readable(s), low) >= 0), None)
    eid = _EID.search(low)
    stated = {"product": product, "section": section, "channel": None,
              "employee_id": eid.group(0) if eid else None,
              "years": [int(y) for y in dict.fromkeys(_YEAR.findall(text))]}
    return {f: v for f, v in stated.items() if v}


def _scope_reach(layer: Layer, stated: dict) -> np.ndarray:
    """How much of the stated scope each chunk sits inside: the fraction of the
    stated fields its own hard fields match. Nothing stated is zero
    everywhere."""
    reach = np.zeros(len(layer.chunk_ids))
    if not stated:
        return reach
    for i, chunk in enumerate(layer.fields):
        matched = 0
        for f, want in stated.items():
            if f == "years":
                matched += bool(set(want) & set(chunk["years"] or []))
            else:
                matched += chunk[f] == want
        reach[i] = matched / len(stated)
    return reach


def _fit(raw: np.ndarray, population: np.ndarray) -> np.ndarray:
    """A guide's fit over the chunk population: rank-calibrated, then zeroed
    below its own median — the calibrated median maps to 0 and the top to 1, so
    a guide that does not fit contributes exactly nothing and one that does
    carries how well it fits."""
    return np.maximum(0.0, 2.0 * midrank_cdf(raw, population) - 1.0)


def _promote(base: np.ndarray, *guides: np.ndarray) -> np.ndarray:
    """The guides over the value, by noisy-OR: 1 − Π(1 − term). Bounded inside
    [0, 1), monotone in every term, and a guide at zero leaves the value exactly
    as it was — guidance promotes, never demotes."""
    out = 1.0 - base
    for guide in guides:
        out = out * (1.0 - guide)
    return 1.0 - out


# --- retrieve ----------------------------------------------------------------

def _retrieve(layer: Layer, qvec: np.ndarray, text: str, k: int) -> tuple:
    """One prompt against the whole layer -> (selected pointer rows, meta)."""
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    support, order = _affinity(layer, qvec)
    demand = _demand(layer, support)
    edge_weight = _edge_weight(layer, demand)
    value = _chunk_value(layer, support, edge_weight)

    touched, walk = _walk(layer, support, edge_weight, demand, order)
    reached = sorted(i for i in touched if layer.retrievable[i])
    if not reached:
        raise RuntimeError("the opened areas reached no retrievable chunk")

    stated = _stated_scope(layer, text)
    scope_fit = _fit(_scope_reach(layer, stated), layer.retrievable)
    desc_fit = _fit(layer.desc_emb @ qvec, layer.retrievable)
    score = _promote(midrank_cdf(value, layer.retrievable), scope_fit, desc_fit)

    kept = min(len(reached), k)
    ranked = sorted(np.flatnonzero(layer.retrievable).tolist(),
                    key=lambda i: (-score[i], layer.chunk_ids[i]))[:kept]
    selected = [{**layer.pointers[i], "score": float(score[i])} for i in ranked]

    meta = {
        "demand": {f: float(v) for f, v in zip(ALL_FACETS, demand)},
        "reliability": {f: float(v) for f, v in zip(ALL_FACETS, layer.reliability)},
        "areas": walk,
        "stated_scope": stated,
        "guides": {"stated_scope": int((scope_fit > 0).sum()),
                   "description": int((desc_fit > 0).sum())},
        "population": int(layer.retrievable.sum()),
        "reached": len(reached),
        "K": kept,
        "retrieved": len(selected),
    }
    return selected, meta


# --- answer ------------------------------------------------------------------

def answer_one_question(question, prepared: Prepared, generate: Optional[Generator],
                        k: int = 50) -> ArmOutput:
    _, text = _qid_text(question)

    t0 = time.perf_counter()
    qmat, calls, tok_in, tok_out, secs = _embed_cached([text], "query")
    qvec = _unit(np.asarray(qmat[0], dtype=np.float32))
    rows, meta = _retrieve(prepared.layer, qvec, text, k)
    meta["interpreter"] = {"model": INTERPRET_MODEL, "backend": "none"}
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
    meta["chunk_ids"] = chunk_id_lists
    meta["returned"] = len(contexts)

    search_time_s = max(0.0, retrieve_wall - secs)
    retrieval_usage = ModelUsage(calls=calls, tokens_in=tok_in,
                                 tokens_out=tok_out, time_s=secs)

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

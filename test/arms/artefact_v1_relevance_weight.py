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

from graph.build_facet_layer import (
    COS_BLOCK, DERIVED_CACHE_DIR, ICC_CEIL, _derived_key, fetch_matrix,
    midrank_cdf, sha256_parity,
)
from harness.contract import ArmOutput, BuildStats, ModelUsage, unpack_generation
from arms.artefact_v1 import (
    ALL_FACETS, DATABASE, DATASET_ID, EXCLUDED_SECTIONS, OFFERED_SECTIONS,
    RUN_ID, _driver, _embed_cached, _qid_text, _readable, _resolve_chunk, _unit,
)
from harness.embed import EMBED_MODEL
from harness.progress import progress


INTERPRET_MODEL = "deterministic"

TAG_DISTANCE_CACHE_DIR = (Path(__file__).resolve().parent.parent.parent / "output" /
                          "tag_distance_cache")

DEMAND = os.environ.get("HERB_DEMAND", "read")
if DEMAND not in ("read", "flat", "centred"):
    raise ValueError(
        f"HERB_DEMAND must be 'read', 'flat' or 'centred', got {DEMAND!r}")

PHI_NEUTRAL = 0.5

DIVIDE_FLOOR = 1e-6

LAYER_ICC = {"topic": "icc_topic_vote", "temporal": "icc_temporal"}

_EID = re.compile(r"\beid_[0-9a-f]+\b")
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_SCOPE_FIELDS = ("product", "section", "channel", "employee_id", "years")

RETRIEVAL_FLAGS = {"HERB_DEMAND": DEMAND}

Generator = Callable[[str, list], object]


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

_ORACLE_COUNT_CYPHER = """
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
WHERE ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND coalesce(c.section, "") IN $excludedSections
RETURN count(c) AS n
"""


@dataclass
class Layer:
    tags: list
    tag_emb: np.ndarray
    tag_distance: np.ndarray
    chunk_ids: list
    desc_emb: np.ndarray
    rows: np.ndarray
    cols: np.ndarray
    phi_centred: np.ndarray
    marginal: np.ndarray
    marginal_mean: np.ndarray
    marginal_sd: np.ndarray
    reliability: np.ndarray
    expected_demand: Optional[np.ndarray]
    retrievable: np.ndarray
    pointers: list
    fields: list
    products: list


@dataclass
class Prepared:
    layer: Layer
    build_stats: Optional[BuildStats] = None


def _read_layer_cache() -> tuple:
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
    digest = hashlib.sha256()
    digest.update("\n".join(tags).encode("utf-8"))
    digest.update(np.ascontiguousarray(tag_emb).tobytes())
    return f"{DATABASE}__{RUN_ID}__t{len(tags)}__{digest.hexdigest()[:16]}"


def _tag_distance_table(tags: list, tag_emb: np.ndarray) -> np.ndarray:
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
    build = np.array([float(manifest[LAYER_ICC[f]]) if f in LAYER_ICC else 1.0
                      for f in ALL_FACETS])
    return build * query_rho


def _query_reliability(tags: list, tag_emb: np.ndarray, marginal: np.ndarray,
                       marginal_mean: np.ndarray, marginal_sd: np.ndarray,
                       desc_emb: np.ndarray) -> np.ndarray:
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
    weight = support / support.sum(axis=-1, keepdims=True)
    scaled = (weight @ (marginal - marginal_mean)) / marginal_sd
    read = np.exp(scaled - scaled.max(axis=-1, keepdims=True))
    read = read / read.sum(axis=-1, keepdims=True)
    shrunk = reliability * read + (1.0 - reliability) / len(ALL_FACETS)
    return shrunk / shrunk.sum(axis=-1, keepdims=True)


def _expected_demand(tag_emb: np.ndarray, marginal: np.ndarray,
                     marginal_mean: np.ndarray, marginal_sd: np.ndarray,
                     reliability: np.ndarray, desc_emb: np.ndarray) -> np.ndarray:
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


def _affinity(layer: Layer, qvec: np.ndarray) -> tuple:
    cos = (layer.tag_emb @ qvec).astype(np.float64)
    order = np.argsort(-cos, kind="stable")
    rank = np.empty(len(cos))
    rank[order] = np.arange(1, len(cos) + 1)
    dist = np.maximum(1.0 - cos, DIVIDE_FLOOR)
    return np.log(len(cos) / rank) / dist ** 2, order


def _demand(layer: Layer, support: np.ndarray) -> np.ndarray:
    if DEMAND == "flat":
        n = len(ALL_FACETS)
        return np.full(n, 1.0 / n)
    read = _demand_read(layer.marginal, layer.marginal_mean, layer.marginal_sd,
                        layer.reliability, support)
    return read - layer.expected_demand if DEMAND == "centred" else read


def _edge_weight(layer: Layer, demand: np.ndarray) -> np.ndarray:
    return layer.phi_centred @ demand


def _chunk_value(layer: Layer, support: np.ndarray,
                 edge_weight: np.ndarray) -> np.ndarray:
    return np.bincount(layer.cols, weights=support[layer.rows] * edge_weight,
                       minlength=len(layer.chunk_ids))


def _area_levels(dist: np.ndarray, anchor: int) -> list:
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
    gap = np.abs(marginal[:, None] - marginal[None, :]) / spread
    dist = base * (1.0 + gap)
    np.fill_diagonal(dist, 0.0)
    return dist


def _touched(layer: Layer, tags: np.ndarray) -> np.ndarray:
    member = np.zeros(len(layer.tags), dtype=bool)
    member[tags] = True
    return np.unique(layer.cols[member[layer.rows]])


def _hit(layer: Layer, support: np.ndarray, edge_weight: np.ndarray,
         tags: np.ndarray) -> float:
    opened = np.zeros(len(layer.tags))
    opened[tags] = support[tags]
    reach = _touched(layer, tags)
    if not len(reach):
        return 0.0
    return float(_chunk_value(layer, opened, edge_weight)[reach].max())


def _open_area(levels: list, cut: int, standard: Optional[float], hit_of) -> tuple:
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
    ranked = support[order]
    share = ranked.sum() / len(ranked)
    n = int(np.searchsorted(-ranked, -share, side="right"))
    return order[:n]


def _walk(layer: Layer, support: np.ndarray, edge_weight: np.ndarray,
          demand: np.ndarray, order: np.ndarray) -> tuple:
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


def _phrase_at(phrase: str, low: str) -> int:
    m = re.search(rf"\b{re.escape(phrase)}\b", low)
    return m.start() if m else -1


def _stated_scope(layer: Layer, text: str) -> dict:
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
    return np.maximum(0.0, 2.0 * midrank_cdf(raw, population) - 1.0)


def _promote(base: np.ndarray, *guides: np.ndarray) -> np.ndarray:
    out = 1.0 - base
    for guide in guides:
        out = out * (1.0 - guide)
    return 1.0 - out


def _retrieve(layer: Layer, qvec: np.ndarray, text: str, k: int) -> tuple:
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

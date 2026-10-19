"""His 2026-10-08 "what if we do all facets and only take the top cluster for each?", looked at
on the made-up question.

One rule for every list of numbers: least-squares clusters on the line, K where the curve of
the fit bends most, and only the cluster of the highest values is taken.
  - a querytag's closeness to every eligible graph tag (tags and querytags behind "query: ")
    -> its top cluster is the picked tags;
  - each of the five facets on the edges (topic made again from the query-mode tag vectors
    against the graph's chunk description vectors; the other four as stored) -> its top
    cluster, once over all the pool's edges and once over the picked tags' edges alone.
Prints the sizes, and for the picked tags' edges and chunks how many land in each facet's top
cluster, in at least one, and in all five.

    .venv/Scripts/python.exe output/research/2026-10-08-query-mode-tags/top_cluster_for_each.py

Reads the graph (read only). No write, no model call, no test question.
"""
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np

print("top_cluster_for_each: loading", flush=True)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_facet_joint import _unit  # noqa: E402
from graph.db import _driver, _readable  # noqa: E402

SOURCE = REPO / "output/research/2026-10-07-structure-last"
SIDE = REPO / "output/embed_local/20261008_rev113abe4acafa_float32/tags_query_readable.npz"
KEPT = HERE / "querytag_vectors_query_mode.npz"
J = json.loads((SOURCE / "structure_last_arrays.json").read_text(encoding="utf-8"))
FACETS = ("topic", "temporal", "why", "activity", "concreteness")
K_MOST = 40
BINS = 1500
SHOWN = 12


def top_cluster(values):
    """Least-squares clusters on the line, K at the bend of the fit curve. Returns K, the mask
    of the cluster of the highest values and that cluster's lowest value."""
    x = np.asarray(values, dtype=np.float64)
    order = np.argsort(x)
    s = x[order]
    if s.size < 3 or s[0] == s[-1]:
        return 1, np.ones(x.size, dtype=bool), float(s[0])
    edges = np.linspace(s[0], s[-1], BINS + 1)
    which = np.clip(np.searchsorted(edges, s, side="right") - 1, 0, BINS - 1)
    count = np.bincount(which, minlength=BINS).astype(np.float64)
    used = count > 0
    w = count[used]
    a = np.bincount(which, weights=s, minlength=BINS)[used]
    q = np.bincount(which, weights=s * s, minlength=BINS)[used]
    m = w.size
    c0 = np.concatenate(([0.], np.cumsum(w)))
    c1 = np.concatenate(([0.], np.cumsum(a)))
    c2 = np.concatenate(([0.], np.cumsum(q)))
    j, i = np.meshgrid(np.arange(m), np.arange(m), indexing="ij")
    inside = i >= j
    size = np.where(inside, c0[i + 1] - c0[j], 1.)
    cost = np.where(inside, np.maximum(c2[i + 1] - c2[j] - (c1[i + 1] - c1[j]) ** 2 / size, 0.),
                    np.inf)
    at = np.arange(m)
    prev = cost[0].copy()
    back, totals = [np.zeros(m, dtype=np.int64)], [float(prev[-1])]
    for k in range(2, min(K_MOST, m) + 1):
        lead = np.full(m, np.inf)
        lead[1:] = prev[:-1]
        table = lead[:, None] + cost
        start = np.argmin(table, axis=0)
        prev = table[start, at]
        back.append(start)
        totals.append(float(prev[-1]))
    y = np.asarray(totals)
    if y.size < 3 or y[0] == y[-1]:
        found = 1
    else:
        line = np.linspace(0., 1., y.size)
        found = int(np.argmax((1. - line) - (y - y[-1]) / (y[0] - y[-1]))) + 1
    first = int(back[found - 1][m - 1]) if found > 1 else 0     # the top cluster's first bin
    begin = int(c0[first])
    mask = np.zeros(x.size, dtype=bool)
    mask[order[begin:]] = True
    return found, mask, float(s[begin])


t0 = time.perf_counter()
driver = _driver()
try:
    with driver.session(database=V.DATABASE, default_access_mode="READ") as session:
        names = [r["id"] for r in session.run(
            "MATCH (t:Tag) WHERE t.emb IS NOT NULL AND EXISTS { MATCH (t)<-[r:HAS_TAG]-(c:Chunk) "
            "WHERE r.run_id = $run AND (c)-[:product]->() } RETURN t.name AS id ORDER BY id",
            run=V.RUN_ID)]
        products = [r["name"] for r in session.run(V.PRODUCT_CYPHER)]
        edges = [dict(r) for r in session.run(V.EDGE_CYPHER, run=V.RUN_ID)]
        chunks = [dict(r) for r in session.run(
            "MATCH (c:Chunk) WHERE c.desc_emb IS NOT NULL AND EXISTS { MATCH (c)-[r:HAS_TAG]->() "
            "WHERE r.run_id = $run } AND (c)-[:product]->() "
            "RETURN c.chunk_id AS chunkId, c.desc_emb AS vector ORDER BY chunkId", run=V.RUN_ID)]
finally:
    driver.close()
print(f"graph: {len(names)} pool tags, {len(chunks)} chunks, {len(edges)} edges "
      f"({time.perf_counter() - t0:.0f}s)", flush=True)

side = np.load(SIDE, allow_pickle=True)
side_at = {str(name): i for i, name in enumerate(side["ids"])}
tags = _unit(np.asarray(side["matrix"][[side_at[t] for t in names]], dtype=np.float32)).astype(np.float64)
folded = {p.casefold() for p in products}
eligible = np.array([t.casefold() not in folded for t in names], dtype=bool)
at = {name: i for i, name in enumerate(names)}
ci = {r["chunkId"]: i for i, r in enumerate(chunks)}
described = _unit(np.asarray([r["vector"] for r in chunks], dtype=np.float32)).astype(np.float64)
edge_tag = np.array([at[r["tag"]] for r in edges], dtype=np.int64)
edge_chunk = np.array([ci[r["chunkId"]] for r in edges], dtype=np.int64)
facets = np.array([r["values"] for r in edges], dtype=np.float64)
facets[:, 0] = np.einsum("ij,ij->i", tags[edge_tag], described[edge_chunk])   # topic made again
keep = eligible[edge_tag]
print(f"{int(eligible.sum())} eligible tags; {int(keep.sum())} of the edges belong to them")

print("\n== each facet over all the eligible edges ==")
whole = {}
for f, name in enumerate(FACETS):
    x = facets[keep, f]
    k, mask, low = top_cluster(x)
    whole[name] = low
    print(f"{name:13s} lowest {x.min():.3f}  middle {np.median(x):.3f}  highest {x.max():.3f}; "
          f"{k} clusters; the top one holds {int(mask.sum()):,} edges "
          f"({100.0 * mask.mean():.1f}%), from {low:.3f} up")

distinct = list(dict.fromkeys(J["query_tags"]))
if KEPT.is_file() and list(np.load(KEPT, allow_pickle=True)["tags"]) == distinct:
    vectors = np.load(KEPT, allow_pickle=True)["vectors"]
else:
    from harness import embed
    vectors = _unit(np.asarray(embed._embed([t.strip() for t in distinct], "query", bar=False)[0],
                               dtype=np.float32)).astype(np.float64)
    np.savez(KEPT, tags=np.array(distinct, dtype=object), vectors=vectors)
rows = vectors @ tags.T

print(f"\n== per querytag: the top cluster of its closeness, then each facet's top cluster ==")
print(f"the question: {J['question']}")
for tag, row in zip(distinct, rows):
    x = np.where(eligible, row, -np.inf)
    k, mask, low = top_cluster(row[eligible])
    picked = np.flatnonzero(eligible)[mask]
    by = picked[np.argsort(-row[picked])]
    mine = np.flatnonzero(np.isin(edge_tag, picked))
    reached = np.unique(edge_chunk[mine])
    print(f"\n\"{tag}\": {k} clusters; the top one holds {picked.size} tags, from {low:.3f} up: "
          + ", ".join(f"{_readable(names[t])} {row[t]:.3f}" for t in by[:SHOWN])
          + (" ..." if picked.size > SHOWN else ""))
    print(f"  their edges {mine.size}, the chunks they reach {reached.size}")
    if mine.size < 3:
        continue
    for label, source in (("each facet clustered over all edges", None),
                          ("each facet clustered over these edges alone", mine)):
        inside = np.zeros((mine.size, len(FACETS)), dtype=bool)
        parts = []
        for f, name in enumerate(FACETS):
            if source is None:
                inside[:, f] = facets[mine, f] >= whole[name]
                parts.append(f"{name} {int(inside[:, f].sum())}")
            else:
                kf, mf, lf = top_cluster(facets[mine, f])
                inside[:, f] = mf
                parts.append(f"{name} {int(mf.sum())} (K {kf}, from {lf:.3f})")
        some = inside.any(axis=1)
        every = inside.all(axis=1)
        print(f"  {label}: edges in the top cluster of " + ", ".join(parts))
        print(f"    of at least one facet: {int(some.sum())} edges, {np.unique(edge_chunk[mine[some]]).size} "
              f"chunks; of all five: {int(every.sum())} edges, "
              f"{np.unique(edge_chunk[mine[every]]).size} chunks; of the four without topic at least "
              f"one: {int(inside[:, 1:].any(axis=1).sum())} edges")
print("done", flush=True)

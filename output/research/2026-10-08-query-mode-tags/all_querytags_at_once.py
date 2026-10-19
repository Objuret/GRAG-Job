"""His 2026-10-08 "perhaps all query tags should be clustered at the same time? One facet at a
time", looked at on the made-up question, read only.

All the question's querytags at once: every graph tag's closeness to every querytag is one
list, clustered once (least-squares clusters on the line, K at the bend); the top cluster is
the picked (querytag, graph tag) pairs for the whole question. Beside it, per graph tag its
closest querytag only. Then the picked tags' edges, one facet at a time: each facet's values
clustered on their own, its top cluster, and the facets taken one after the other in the order
the querytags' readings give (the most important first, the next inside what the first kept).
Prints what each step keeps, by name where the list is short.

    .venv/Scripts/python.exe output/research/2026-10-08-query-mode-tags/all_querytags_at_once.py

Reads the graph (read only). No write, no model call, no test question.
"""
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np

print("all_querytags_at_once: loading", flush=True)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_facet_joint import _unit  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
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
    first = int(back[found - 1][m - 1]) if found > 1 else 0
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
            "RETURN c.chunk_id AS chunkId, c.desc_emb AS vector, c.kind AS kind ORDER BY chunkId",
            run=V.RUN_ID)]
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
facets[:, 0] = np.einsum("ij,ij->i", tags[edge_tag], described[edge_chunk])   # topic, as rewritten

# The querytags of the 2026-10-07 arrays (the same made-up question, the querytagger's answer
# that day), one row each; their facet readings from the same file.
A = np.load(SOURCE / "structure_last_arrays.npz")
texts = list(dict.fromkeys(J["query_tags"]))
readings = np.array([A["readings"][J["query_tags"].index(t)] for t in texts], dtype=np.float64)
kept = np.load(KEPT, allow_pickle=True)
if list(kept["tags"]) != texts:
    raise SystemExit("the kept querytag vectors are not this question's querytags")
rows = np.asarray(kept["vectors"], dtype=np.float64) @ tags.T   # (querytags, graph tags)
rows[:, ~eligible] = np.nan
print(f"the question: {J['question']}")
print(f"{len(texts)} different querytags, {int(eligible.sum())} eligible graph tags")

print("\n== per querytag, as before: the top cluster of its own list ==")
own = {}
for i, text in enumerate(texts):
    if text in own:
        continue
    k, mask, low = top_cluster(rows[i][eligible])
    own[text] = (int(mask.sum()), low)
    print(f"  {text!r}: {k} clusters, top one {int(mask.sum())} tags from {low:.3f} up")

print("\n== all querytags at once: every (querytag, graph tag) closeness in one list ==")
stack = rows[:, eligible]
flat = stack.ravel()
k, mask, low = top_cluster(flat)
picked_pairs = mask.reshape(stack.shape)
pairs = int(picked_pairs.sum())
picked_tags = np.flatnonzero(eligible)[picked_pairs.any(axis=0)]
print(f"{flat.size:,} values; {k} clusters; the top one holds {pairs} pairs from {low:.3f} up, "
      f"{picked_tags.size} different graph tags")
print("  pairs in the top cluster per querytag: " + ", ".join(
    f"{texts[i]!r} {int(picked_pairs[i].sum())}" for i in range(len(texts))))
by = picked_tags[np.argsort(-np.nanmax(rows[:, picked_tags], axis=0))]
print("  the graph tags, nearest first: " + ", ".join(
    f"{_readable(names[t])} {np.nanmax(rows[:, t]):.3f} ({texts[int(np.nanargmax(rows[:, t]))]})"
    for t in by[:40]) + (" ..." if by.size > 40 else ""))

print("\n== all querytags at once, each graph tag by its closest querytag only ==")
best = np.nanmax(stack, axis=0)
k2, mask2, low2 = top_cluster(best)
picked2 = np.flatnonzero(eligible)[mask2]
print(f"{best.size:,} values; {k2} clusters; the top one holds {picked2.size} graph tags from {low2:.3f} up")
whose = np.nanargmax(stack, axis=0)[mask2]
print("  by the querytag that is closest: " + ", ".join(
    f"{texts[i]!r} {int((whose == i).sum())}" for i in range(len(texts)) if (whose == i).any()))

print("\n== the per-querytag picks put together: every querytag's own top cluster, the edges once ==")
union = set()
per_tag = {}
for i, text in enumerate(texts):
    k_i, mask_i, _ = top_cluster(rows[i][eligible])
    tags_i = np.flatnonzero(eligible)[mask_i]
    edges_i = np.flatnonzero(np.isin(edge_tag, tags_i))
    per_tag[text] = edges_i
    union.update(edges_i.tolist())
pooled = np.array(sorted(union), dtype=np.int64)
print(f"the edges of all picked tags, each edge once: {pooled.size}, chunks {np.unique(edge_chunk[pooled]).size}; "
      f"per querytag: " + ", ".join(f"{t!r} {per_tag[t].size}" for t in texts))
gaps = dict(zip(FACETS[1:], (1.01, 1.38, 1.06, 1.30)))
print("each facet on its own over that one list, and where each querytag's own edges fall:")
for f, name in enumerate(FACETS):
    kf, mf, lf = top_cluster(facets[pooled, f])
    above = lf - np.median(facets[pooled, f])
    note = "" if name == "topic" else f"; starts {above:.2f} above the middle, the facet's retrain gap {gaps[name]}"
    inside = set(pooled[mf].tolist())
    shares = ", ".join(f"{t!r} {sum(1 for e in per_tag[t] if e in inside)}/{per_tag[t].size}" for t in texts)
    print(f"  {name:13s} {kf} clusters; top one {int(mf.sum())} edges, {np.unique(edge_chunk[pooled[mf]]).size} chunks, "
          f"from {lf:.3f} up{note}\n{'':16s}of each querytag's edges in it: {shares}")

print("\n== then one facet at a time, over the pooled pick's tags' edges ==")
mine = np.flatnonzero(np.isin(edge_tag, picked_tags))
print(f"the picked tags' edges: {mine.size}, chunks they reach: {np.unique(edge_chunk[mine]).size}")
# the question's facet order: the four ranking facets by the querytags' readings, summed
order = np.argsort(-readings[:, 1:].sum(axis=0), kind="stable")
print("the question's facet order from the readings (the four, summed over the querytags): "
      + ", ".join(FACETS[1:][j] for j in order))
gaps = dict(zip(FACETS[1:], (1.01, 1.38, 1.06, 1.30)))
print("each facet on its own over those edges:")
for f, name in enumerate(FACETS):
    kf, mf, lf = top_cluster(facets[mine, f])
    note = "" if name == "topic" else f"; the facet's retrain gap {gaps[name]}, the top cluster starts {lf - np.median(facets[mine, f]):.2f} above the middle"
    print(f"  {name:13s} {kf} clusters; top one {int(mf.sum())} edges, "
          f"{np.unique(edge_chunk[mine[mf]]).size} chunks, from {lf:.3f} up{note}")
print("one after the other, in the question's facet order, topic last:")
left = mine.copy()
for j in list(order) + [None]:
    f = 0 if j is None else j + 1
    name = FACETS[f]
    if left.size < 3:
        print(f"  {name}: fewer than three edges left, nothing to cluster")
        break
    kf, mf, lf = top_cluster(facets[left, f])
    left = left[mf]
    print(f"  {name:13s} {kf} clusters; keeps {left.size} edges, {np.unique(edge_chunk[left]).size} chunks, from {lf:.3f} up")
print("  what is left, by chunk and tag: " + "; ".join(
    f"{chunks[edge_chunk[e]]['kind']} {chunks[edge_chunk[e]]['chunkId'][:8]} via {_readable(names[edge_tag[e]])}"
    for e in left[:SHOWN]) + (" ..." if left.size > SHOWN else ""))
print("done", flush=True)

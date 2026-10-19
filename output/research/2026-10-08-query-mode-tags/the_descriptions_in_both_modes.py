"""The 4,869 chunk descriptions embedded behind "passage: " and behind "query: ", both by the
local embedder, and the made-up question's description and question in both modes: how the
numbers spread in each mode, whether a description's nearest descriptions are the same ones,
how topic on the edges moves (the query-mode tag vectors against each description mode), and
what the description side of the walk would see.

    .venv/Scripts/python.exe output/research/2026-10-08-query-mode-tags/the_descriptions_in_both_modes.py

Reads the side files, the graph (read only, for the edges) and the embedder for the two texts
of the made-up question. No write, no model call, no test question.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

print("the_descriptions_in_both_modes: loading", flush=True)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")

from scipy.stats import spearmanr  # noqa: E402

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_facet_joint import _unit  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from graph.db import _driver  # noqa: E402
from harness import embed  # noqa: E402

FILES = {"passage": REPO / "output/embed_local/20261007_rev113abe4acafa_float32/descriptions_passage.npz",
         "query": REPO / "output/embed_local/20261008_rev113abe4acafa_float32/descriptions_query.npz"}
TAGS = REPO / "output/embed_local/20261008_rev113abe4acafa_float32/tags_query_readable.npz"
SOURCE = REPO / "output/research/2026-10-07-structure-last/structure_last_arrays.json"
NEAREST = (1, 2, 4, 8, 16, 32)
EDGES = np.linspace(-1.0, 1.0, 20001)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def at_share(counts, share):
    cum = np.cumsum(counts)
    return float(EDGES[min(int(np.searchsorted(cum, share * cum[-1])) + 1, EDGES.size - 1)])


def read(mode):
    z = np.load(FILES[mode], allow_pickle=True)
    ids = [str(i) for i in z["ids"]]
    m = _unit(np.asarray(z["matrix"], dtype=np.float32)).astype(np.float64)
    print(f"{mode}: {FILES[mode].relative_to(REPO).as_posix()}  sha256 {sha(FILES[mode])[:16]}  {m.shape}")
    return ids, m


def sweep(m):
    n = m.shape[0]
    s = m @ m.T
    np.fill_diagonal(s, -3.)
    top = np.argsort(-s, axis=1)[:, :NEAREST[-1]]
    nearest = s[np.arange(n), top[:, 0]]
    np.fill_diagonal(s, 3.)
    counts = np.histogram(np.clip(s, -1., 1.), bins=EDGES)[0]
    return counts, top, nearest, float(np.linalg.norm(m.mean(axis=0)))


ids_p, passage = read("passage")
ids_q, query = read("query")
if ids_p != ids_q:
    raise SystemExit("the two files do not hold the same chunks in the same order")
n = len(ids_p)
out = {}
for mode, m in (("passage", passage), ("query", query)):
    counts, top, nearest, mean_len = sweep(m)
    out[mode] = top
    print(f"\n== descriptions behind \"{mode}: \" ==")
    print(f"length of the mean of all description vectors (0 all ways, 1 all the same): {mean_len:.3f}")
    print(f"two different descriptions, all {n * (n - 1) // 2:,} pairs: 1% {at_share(counts, 0.01):.3f}  "
          f"middle {at_share(counts, 0.5):.3f}  99% {at_share(counts, 0.99):.3f}")
    print(f"a description to its nearest other description: lowest {nearest.min():.3f}  "
          f"middle {np.median(nearest):.3f}  highest {nearest.max():.3f}")
print("\n== a description's nearest descriptions, behind \"passage: \" against behind \"query: \" ==")
for k in NEAREST:
    a, b = out["passage"][:, :k], out["query"][:, :k]
    shared = np.array([np.intersect1d(a[i], b[i]).size for i in range(n)])
    print(f"the {k:>2} nearest: {100.0 * shared.mean() / k:5.1f}% are the same descriptions; all {k} the same "
          f"for {int((shared == k).sum()):,}, none for {int((shared == 0).sum()):,}")

print("\n== topic on the edges: the query-mode tag vectors against each description mode ==")
t0 = time.perf_counter()
driver = _driver()
try:
    with driver.session(database=V.DATABASE, default_access_mode="READ") as session:
        edges = [dict(r) for r in session.run(V.EDGE_CYPHER, run=V.RUN_ID)]
finally:
    driver.close()
side = np.load(TAGS, allow_pickle=True)
tag_at = {str(name): i for i, name in enumerate(side["ids"])}
tags = _unit(np.asarray(side["matrix"], dtype=np.float32)).astype(np.float64)
ci = {c: i for i, c in enumerate(ids_p)}
edge_tag = np.array([tag_at[r["tag"]] for r in edges])
edge_chunk = np.array([ci[r["chunkId"]] for r in edges])
stored = np.array([r["values"][0] for r in edges], dtype=np.float64)
topic_p = np.einsum("ij,ij->i", tags[edge_tag], passage[edge_chunk])
topic_q = np.einsum("ij,ij->i", tags[edge_tag], query[edge_chunk])
print(f"{len(edges)} edges ({time.perf_counter() - t0:.0f}s); stored topic against tag(query) x description(passage), "
      f"largest difference {np.abs(stored - topic_p).max():.2e}")
for name, t in (("description behind \"passage: \" (as the graph stands)", topic_p),
                ("description behind \"query: \"", topic_q)):
    q = np.percentile(t, [0, 25, 50, 75, 100])
    print(f"  {name}: lowest {q[0]:.3f}  25% {q[1]:.3f}  middle {q[2]:.3f}  75% {q[3]:.3f}  highest {q[4]:.3f}")
print(f"  rank agreement over all edges (Spearman): {spearmanr(topic_p, topic_q)[0]:.3f}")
for name, key in (("tag", edge_tag), ("chunk", edge_chunk)):
    order = np.argsort(key, kind="stable")
    cuts = np.flatnonzero(np.diff(key[order])) + 1
    groups = [g for g in np.split(order, cuts) if g.size > 1]
    same_top = sum(int(np.argmax(topic_p[g]) == np.argmax(topic_q[g])) for g in groups)
    print(f"  per {name} with more than one edge ({len(groups)}): the highest-topic edge is the same one for "
          f"{100.0 * same_top / len(groups):.1f}%")

print("\n== the description side of the walk for the made-up question ==")
J = json.loads(SOURCE.read_text(encoding="utf-8"))
A = np.load(SOURCE.with_suffix(".npz"))
question = J["question"]
# the query description of the 2026-10-07 arrays is not kept as text in them; the walkthrough file has it
walk = json.loads((REPO / "output/walkthrough/20261005T040000Z/walkthrough.json").read_text(encoding="utf-8"))
description = walk["description"]
print(f"question: {question}\ndescription: {description[:160]}...")
texts = {"question behind \"query: \"": (question, "query"),
         "description behind \"passage: \"": (description, "passage"),
         "description behind \"query: \"": (description, "query")}
vec = {}
for label, (text, role) in texts.items():
    vec[label] = _unit(np.asarray(embed._embed([text], role, bar=False)[0], dtype=np.float32)).astype(np.float64)[0]
pairs = [("question behind \"query: \"", "passage", "as the arm stands"),
         ("question behind \"query: \"", "query", "descriptions behind \"query: \""),
         ("description behind \"passage: \"", "passage", "as the arm stands"),
         ("description behind \"query: \"", "query", "both behind \"query: \"")]
standings = {}
for label, mode, note in pairs:
    m = passage if mode == "passage" else query
    d = m @ vec[label]
    z, middle, spread = WK.standing(d)
    top = np.argsort(-d)[:5]
    standings[(label, mode)] = (d, z)
    print(f"  {label} x descriptions behind \"{mode}: \" ({note}): middle {middle:.3f}, spread {spread:.4f}, "
          f"nearest {d.max():.3f} standing {z.max():.1f} spreads above; nearest five chunks "
          f"{[ids_p[i][:8] for i in top]}")
a = standings[("description behind \"passage: \"", "passage")][0]
b = standings[("description behind \"query: \"", "query")][0]
for k in (10, 25, 50):
    shared = np.intersect1d(np.argsort(-a)[:k], np.argsort(-b)[:k]).size
    print(f"  the description's {k} nearest chunks shared between the two modes: {shared}")
print("done", flush=True)

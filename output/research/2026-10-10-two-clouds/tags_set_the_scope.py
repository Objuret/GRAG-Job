"""His 2026-10-10 '"the tags cannot set scope".. oh, cant they? are they not connected to
chunks?', on the made-up question, read only.

The tags reach the chunks over the edges, so a chunk has a nearness through its tags: the
closeness of its closest tag to a querytag. On that one number per chunk the same steps as
for the chunk descriptions: the list cut into k clusters, the first is the nearness cloud; the
same values per scope (a chunk's own scope carries the average of its chunks), cut the same
way, the first is the near scopes; the near scopes that hold chunks of the nearness cloud, read
as their branch.

  all querytags   per chunk the largest closeness over every querytag and every tag on the chunk
  one querytag    the same per querytag, each on its own
  beside them     the chunk descriptions' nearness to the question, for which chunks both clouds hold

    .venv/Scripts/python.exe output/research/2026-10-10-two-clouds/tags_set_the_scope.py

Reads the graph (read only), the side file of the tags' vectors the graph carries, and the
query side's vectors kept by two_clouds_made_up.py. No write, no model call, no test question.
"""
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np

print("tags_set_the_scope: loading", flush=True)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_facet_joint import _unit  # noqa: E402
from graph.db import _driver, _readable  # noqa: E402

WALK = REPO / "output/walkthrough/20261005T040000Z/walkthrough.json"
ARRAYS = REPO / "output/research/2026-10-07-structure-last"
TAGS = REPO / "output/embed_local/20261008_rev113abe4acafa_float32/tags_query_readable.npz"
KS = (3, 4, 5, 6, 7)
BINS = 1500
SHOWN = 5


def levels(values, k):
    """Least-squares clusters on the line, k of them (fewer when the values fill fewer bins).
    Returns each value's level, 1 the nearest."""
    x = np.asarray(values, dtype=np.float64)
    order = np.argsort(x)
    s = x[order]
    if s[0] == s[-1]:
        return np.ones(x.size, dtype=np.int64)
    edges = np.linspace(s[0], s[-1], BINS + 1)
    which = np.clip(np.searchsorted(edges, s, side="right") - 1, 0, BINS - 1)
    count = np.bincount(which, minlength=BINS).astype(np.float64)
    used = np.flatnonzero(count)
    w = count[used]
    a = np.bincount(which, weights=s, minlength=BINS)[used]
    q = np.bincount(which, weights=s * s, minlength=BINS)[used]
    m = used.size
    k = min(int(k), m)
    c0, c1, c2 = (np.concatenate(([0.], np.cumsum(v))) for v in (w, a, q))
    j, i = np.meshgrid(np.arange(m), np.arange(m), indexing="ij")
    inside = i >= j
    size = np.where(inside, c0[i + 1] - c0[j], 1.)
    cost = np.where(inside, np.maximum(c2[i + 1] - c2[j] - (c1[i + 1] - c1[j]) ** 2 / size, 0.),
                    np.inf)
    at = np.arange(m)
    prev = cost[0].copy()
    back = [np.zeros(m, dtype=np.int64)]
    for _ in range(2, k + 1):
        lead = np.full(m, np.inf)
        lead[1:] = prev[:-1]
        table = lead[:, None] + cost
        start = np.argmin(table, axis=0)
        prev = table[start, at]
        back.append(start)
    bin_level = np.zeros(m, dtype=np.int64)
    end = m - 1
    for level, g in enumerate(range(k - 1, -1, -1), 1):
        first = int(back[g][end]) if g else 0
        bin_level[first:end + 1] = level
        end = first - 1
    out = np.empty(x.size, dtype=np.int64)
    out[order] = bin_level[np.searchsorted(used, which)]
    return out


def named(counts, names, most=SHOWN):
    by = np.argsort(-counts, kind="stable")
    shown = [f"{names[b]} {int(counts[b])}" for b in by[:most] if counts[b] > 0]
    more = int((counts > 0).sum()) - len(shown)
    return ", ".join(shown) + (f" and {more} more" if more > 0 else "")


t0 = time.perf_counter()
driver = _driver()
try:
    with driver.session(database=V.DATABASE, default_access_mode="READ") as session:
        chunk_rows = [dict(r) for r in session.run(V.CHUNK_CYPHER, run=V.RUN_ID)]
        edge_rows = [(r["tag"], r["chunkId"], r["values"][0])
                     for r in session.run(V.EDGE_CYPHER, run=V.RUN_ID)]
finally:
    driver.close()
chunk_ids = [r["chunkId"] for r in chunk_rows]
described = _unit(np.asarray([r["vector"] for r in chunk_rows], dtype=np.float32)).astype(np.float64)
n = len(chunk_ids)
print(f"graph {V.DATABASE}: {n} pool chunks, {len(edge_rows)} edges ({time.perf_counter() - t0:.0f}s)",
      flush=True)

J = json.loads((ARRAYS / "structure_last_arrays.json").read_text(encoding="utf-8"))
A = np.load(ARRAYS / "structure_last_arrays.npz")
if [J["kind_names"][i] for i in A["kind"]] != [str(r["kind"] or "") for r in chunk_rows]:
    raise SystemExit("the graph read now is not the pool the saved tree was made from")
paths = {p: np.array(sorted(m), dtype=np.int64) for p, m in J["paths"].items()}
branches = sorted(p for p in paths if "/" not in p)
branch_of = np.full(n, -1, dtype=np.int64)
for b, name in enumerate(branches):
    branch_of[paths[name]] = b
inner = {p.rsplit("/", 1)[0] for p in paths if "/" in p}
own = [p for p in sorted(paths) if p not in inner]

walk = json.loads(WALK.read_text(encoding="utf-8"))
query_tags = list(dict.fromkeys(t["text"] for t in walk["query_tags"]))
kept = np.load(HERE / "query_vectors.npz", allow_pickle=True)
if list(kept["texts"]) != [walk["question"], walk["description"]] + query_tags:
    raise SystemExit("the kept query vectors are not this question's; run two_clouds_made_up.py")
vectors = kept["vectors"]
print(f"the question: {walk['question']}")

side = np.load(TAGS, allow_pickle=True)
side_at = {str(t): i for i, t in enumerate(side["ids"])}
folded = {b.casefold() for b in branches}
eligible = sorted({t for t, _, _ in edge_rows if t.casefold() not in folded})
at = {t: i for i, t in enumerate(eligible)}
ci = {c: i for i, c in enumerate(chunk_ids)}
tag_matrix = _unit(np.asarray(side["matrix"][[side_at[t] for t in eligible]], dtype=np.float32)).astype(np.float64)
edge_tag = np.array([at[t] for t, _, _ in edge_rows if t in at], dtype=np.int64)
edge_chunk = np.array([ci[c] for t, c, _ in edge_rows if t in at], dtype=np.int64)
closeness = tag_matrix @ vectors[2:].T                       # (graph tags, querytags)
print(f"{len(eligible)} eligible graph tags, {edge_tag.size} edges of theirs, {len(query_tags)} querytags; "
      f"chunks with no such edge: {int(n - np.unique(edge_chunk).size)}")

# Per chunk and querytag: the closeness of the chunk's closest tag to that querytag.
through = np.full((n, len(query_tags)), -1.0)
for q in range(len(query_tags)):
    np.maximum.at(through[:, q], edge_chunk, closeness[edge_tag, q])
lists = {"all querytags": through.max(axis=1)}
lists.update({f'"{text}"': through[:, q] for q, text in enumerate(query_tags)})
question = described @ vectors[0]


def walk_one(name, x):
    print(f"-- {name}: lowest {x.min():.3f}, middle {np.median(x):.3f}, nearest {x.max():.3f} --")
    own_mean = np.array([x[paths[p]].mean() for p in own])
    for k in KS:
        level = levels(x, k)
        one = level == 1
        counts = np.bincount(branch_of[one], minlength=len(branches))
        near = np.flatnonzero(levels(own_mean, k) == 1)
        near = near[np.argsort(-own_mean[near])]
        holding = [i for i in near if one[paths[own[i]]].any()]
        main = sorted({own[i].split("/")[0] for i in holding})
        both = int((one & (levels(question, k) == 1)).sum())
        print(f"  k={k}: the nearness cloud {int(one.sum())} chunks, down to {x[one].min():.3f}, in "
              f"{int((counts > 0).sum())} branches: {named(counts, branches)}")
        print(f"      near scopes {near.size} of {len(own)}: "
              + ", ".join(f"{own[i]} {own_mean[i]:.3f} ({len(paths[own[i]])})" for i in near[:SHOWN])
              + (" ..." if near.size > SHOWN else ""))
        print(f"      the near scopes that hold chunks of the cloud, as their branch: "
              f"{', '.join(main[:SHOWN])}{' ...' if len(main) > SHOWN else ''} ({len(main)}); "
              f"chunks also in the question's nearness cloud at this k: {both}")


print("\n== the chunks' nearness through their tags, all querytags at once ==")
walk_one("all querytags", lists["all querytags"])
print("\n== the same, one querytag at a time ==")
for name in list(lists)[1:]:
    walk_one(name, lists[name])

print("\n== the tags behind the nearest chunks, all querytags at once, k=6 ==")
x = lists["all querytags"]
one = np.flatnonzero(levels(x, 6) == 1)
best_q = through[one].argmax(axis=1)
print("  the querytag that gives the chunk its value: "
      + ", ".join(f'"{query_tags[q]}" {int((best_q == q).sum())}' for q in range(len(query_tags))))
print("done", flush=True)

"""His 2026-10-10 "Why not take the first or first 2 kNN clusters or something? Aka making 2
clouds, one based on embedding nearness, and the other, of the same, based on scope, and we take
cloudintersection as main scope(s)?", walked through on the made-up question, read only.

  cloud one   every pool chunk description's nearness to the query (the description, and the
              question) in one list, cut into k clusters; the first, or the first two.
  cloud two   the same nearness values seen per scope: every place of the tree carries the
              mean of its own chunks' nearness; those values cut into k clusters the same way.
  beside it   the other reading of cloud two: cloud one's chunks grouped by the branch they
              sit in, the group sizes cut into k clusters.
  overlap     the near scopes that hold near chunks, read as their branch.
  the tags    each querytag's nearness to the eligible graph tags cut into k clusters; the
              first, or the first two; and where the chunks of those tags sit.

k runs from 3 to 7 (his 2026-10-09 "explore what k=3 to 7 mean"). The cut is least-squares
clusters on the line, the number of clusters given.

    .venv/Scripts/python.exe output/research/2026-10-10-two-clouds/two_clouds_made_up.py

Reads the graph (read only) and the side file of the tags' vectors the graph carries. No write,
no model call, no test question: the question is the made-up one of
output/walkthrough/20261005T040000Z/walkthrough.json.
"""
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np

print("two_clouds_made_up: loading", flush=True)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_facet_joint import _unit  # noqa: E402
from graph.db import _driver, _readable  # noqa: E402
from harness import embed  # noqa: E402

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


def sizes(level, k):
    return [int((level == n).sum()) for n in range(1, int(level.max()) + 1)]


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
        edge_rows = [(r["tag"], r["chunkId"]) for r in session.run(V.EDGE_CYPHER, run=V.RUN_ID)]
finally:
    driver.close()
chunk_ids = [r["chunkId"] for r in chunk_rows]
described = _unit(np.asarray([r["vector"] for r in chunk_rows], dtype=np.float32)).astype(np.float64)
n = len(chunk_ids)
print(f"graph {V.DATABASE}: {n} pool chunks, {len(edge_rows)} edges ({time.perf_counter() - t0:.0f}s)",
      flush=True)

# The tree of the arm, as saved with the made-up question's arrays of 2026-10-07; checked
# against the graph read now by each chunk's kind of record.
J = json.loads((ARRAYS / "structure_last_arrays.json").read_text(encoding="utf-8"))
A = np.load(ARRAYS / "structure_last_arrays.npz")
kinds_then = [J["kind_names"][i] for i in A["kind"]]
if n != len(kinds_then) or kinds_then != [str(r["kind"] or "") for r in chunk_rows]:
    raise SystemExit("the graph read now is not the pool the saved tree was made from")
paths = {p: np.array(sorted(m), dtype=np.int64) for p, m in J["paths"].items()}
branches = sorted(p for p in paths if "/" not in p)
branch_of = np.full(n, -1, dtype=np.int64)
for b, name in enumerate(branches):
    branch_of[paths[name]] = b
inner = {p.rsplit("/", 1)[0] for p in paths if "/" in p}
places = sorted(paths)
print(f"the tree: {len(branches)} branches, {len(places)} places in all, "
      f"{sum(1 for p in places if p not in inner)} of them a chunk's own scope")

walk = json.loads(WALK.read_text(encoding="utf-8"))
query_tags = list(dict.fromkeys(t["text"] for t in walk["query_tags"]))
texts = [walk["question"], walk["description"]] + query_tags
kept = HERE / "query_vectors.npz"            # the query side's vectors, kept beside the script
if kept.is_file() and list(np.load(kept, allow_pickle=True)["texts"]) == texts:
    vectors = np.load(kept, allow_pickle=True)["vectors"]
else:
    vectors = _unit(np.asarray(embed._embed(texts, "query", bar=False)[0], dtype=np.float32)).astype(np.float64)
    np.savez(kept, texts=np.array(texts, dtype=object), vectors=vectors)
print(f"\nthe question: {walk['question']}")
print(f"the description: {walk['description']}")
nearness = {"description": described @ vectors[1], "question": described @ vectors[0]}

print("\n== cloud one: the chunk descriptions' nearness, cut into k clusters ==")
cut = {}
for name, x in nearness.items():
    print(f"{name}: lowest {x.min():.3f}, middle {np.median(x):.3f}, nearest {x.max():.3f}")
    for k in KS:
        cut[name, k] = levels(x, k)
        s = sizes(cut[name, k], k)
        print(f"  k={k}: chunks per cluster from the nearest {s}; the first ends at "
              f"{x[cut[name, k] == 1].min():.3f}, the second at {x[cut[name, k] <= 2].min():.3f}")

print("\n== where cloud one sits, and the two readings of cloud two ==")
place_mean = {name: np.array([x[paths[p]].mean() for p in places]) for name, x in nearness.items()}
branch_at = np.array([branches.index(p.split("/")[0]) for p in places])
for name, x in nearness.items():
    print(f"-- nearness to the {name} --")
    for k in KS:
        scope_level = levels(place_mean[name], k)
        branch_level = levels(place_mean[name][[places.index(b) for b in branches]], k)
        for take in (1, 2):
            one = cut[name, k] <= take
            counts = np.bincount(branch_of[one], minlength=len(branches))
            grouped = levels(counts[counts > 0].astype(np.float64), k)
            largest = [branches[b] for b, g in zip(np.flatnonzero(counts > 0), grouped) if g <= take]
            near_places = np.flatnonzero(scope_level <= take)
            near_branches = [branches[b] for b in np.flatnonzero(branch_level <= take)]
            overlap = [i for i in near_places if one[paths[places[i]]].any()]
            main = sorted({branches[branch_at[i]] for i in overlap})
            kept = int(sum(len(paths[b]) for b in main))
            print(f"  k={k}, first {take}: cloud one {int(one.sum())} chunks in "
                  f"{int((counts > 0).sum())} branches: {named(counts, branches)}")
            print(f"      cloud two, near chunks grouped by branch, the largest groups: "
                  f"{', '.join(largest[:SHOWN])}{' ...' if len(largest) > SHOWN else ''} ({len(largest)})")
            print(f"      cloud two, the same nearness per scope: {near_places.size} near places of "
                  f"{len(places)}: " + ", ".join(f"{places[i]} {place_mean[name][i]:.3f} ({len(paths[places[i]])})"
                                                  for i in near_places[np.argsort(-place_mean[name][near_places])][:SHOWN])
                  + (" ..." if near_places.size > SHOWN else ""))
            print(f"      the branches alone, per branch mean: near {', '.join(near_branches[:SHOWN])}"
                  f"{' ...' if len(near_branches) > SHOWN else ''} ({len(near_branches)})")
            print(f"      overlap, near scopes that hold near chunks, as their branch: "
                  f"{', '.join(main[:SHOWN])}{' ...' if len(main) > SHOWN else ''} "
                  f"({len(main)} branches, {kept} chunks)")

print("\n== cloud two from a chunk's own scope alone, and where in its branch cloud one sits ==")
own = [p for p in places if p not in inner]
for name, x in nearness.items():
    own_mean = np.array([x[paths[p]].mean() for p in own])
    print(f"-- nearness to the {name} --")
    for k in KS:
        level = levels(own_mean, k)
        near = np.flatnonzero(level == 1)
        near = near[np.argsort(-own_mean[near])]
        parents = sorted({own[i].rsplit("/", 1)[0] for i in near})
        tops = sorted({own[i].split("/")[0] for i in near})
        one = cut[name, k] == 1
        holding = [i for i in near if one[paths[own[i]]].any()]
        main = sorted({own[i].split("/")[0] for i in holding})
        print(f"  k={k}: {near.size} near own scopes of {len(own)}: "
              + ", ".join(f"{own[i]} {own_mean[i]:.3f} ({len(paths[own[i]])})" for i in near[:SHOWN])
              + (" ..." if near.size > SHOWN else ""))
        print(f"      their parents {len(parents)}: {', '.join(parents[:SHOWN])}{' ...' if len(parents) > SHOWN else ''}; "
              f"their branches {len(tops)}: {', '.join(tops[:SHOWN])}{' ...' if len(tops) > SHOWN else ''}")
        print(f"      those that hold a chunk of cloud one, as their branch: {', '.join(main[:SHOWN])}"
              f"{' ...' if len(main) > SHOWN else ''} ({len(main)})")
        if len(main) == 1:
            inside = one & (branch_of == branches.index(main[0]))
            by_kind = {p: int(inside[paths[p]].sum()) for p in places
                       if p.count("/") == 1 and p.startswith(main[0] + "/")}
            print(f"      cloud one inside {main[0]} ({int(inside.sum())} of its {len(paths[main[0]])} chunks): "
                  + ", ".join(f"{p.split('/', 1)[1]} {c} of {len(paths[p])}" for p, c in sorted(by_kind.items())))

print("\n== the tags: each querytag's nearness to the graph tags, cut into k clusters ==")
side = np.load(TAGS, allow_pickle=True)
side_at = {str(t): i for i, t in enumerate(side["ids"])}
pool_tags = sorted({t for t, _ in edge_rows})
folded = {b.casefold() for b in branches}
eligible = [t for t in pool_tags if t.casefold() not in folded]
tag_matrix = _unit(np.asarray(side["matrix"][[side_at[t] for t in eligible]], dtype=np.float32)).astype(np.float64)
at = {t: i for i, t in enumerate(eligible)}
ci = {c: i for i, c in enumerate(chunk_ids)}
edge_tag = np.array([at[t] for t, _ in edge_rows if t in at], dtype=np.int64)
edge_chunk = np.array([ci[c] for t, c in edge_rows if t in at], dtype=np.int64)
print(f"{len(eligible)} eligible graph tags, {edge_tag.size} edges of theirs")
tag_level = {}
for q, text in enumerate(query_tags):
    row = tag_matrix @ vectors[2 + q]
    line = []
    for k in KS:
        tag_level[text, k] = levels(row, k)
        s = sizes(tag_level[text, k], k)
        line.append(f"k={k}: {s[0]} / {s[0] + s[1]}")
    first = np.flatnonzero(tag_level[text, 5] == 1)
    first = first[np.argsort(-row[first])]
    print(f"\"{text}\" (nearest {row.max():.3f}): tags in the first / the first two clusters, "
          + "; ".join(line))
    print("    the first of five: " + ", ".join(f"{_readable(eligible[t])} {row[t]:.3f}" for t in first[:10])
          + (f" and {first.size - 10} more" if first.size > 10 else ""))
print("\nwhere the chunks of the querytags' first clusters sit:")
for k in KS:
    for take in (1, 2):
        picked = np.zeros(len(eligible), dtype=bool)
        for text in query_tags:
            picked |= tag_level[text, k] <= take
        reached = np.zeros(n, dtype=bool)
        reached[edge_chunk[picked[edge_tag]]] = True
        counts = np.bincount(branch_of[reached], minlength=len(branches))
        print(f"  k={k}, first {take}: {int(picked.sum())} tags, {int(reached.sum())} chunks in "
              f"{int((counts > 0).sum())} branches: {named(counts, branches)}")
print("done", flush=True)

"""His 2026-10-10 'so, rethink that', after '"the tags cannot set scope".. oh, cant they? are they
not connected to chunks?', on the made-up question, read only.

Both sides reach the chunks, so both can set the border. Printed with the roles swapped:

  as now        the chunk descriptions set the border, the tags do their thing inside it
  the opposite  the tags (through their chunks) set the border, the chunk descriptions do their
                thing inside it
  together      where the two sides' clouds and borders meet

A side's border: its nearness per chunk cut into k clusters, the first is its nearness cloud; the
same values per scope (a chunk's own scope carries the average of its chunks) cut the same way,
the first is the near scopes; the near scopes that hold chunks of the cloud, read as their branch
with everything under it.

  chunk descriptions   a chunk's nearness is its description's, to the question or to the query description
  tags                 a chunk's nearness is that of its closest tag to a querytag, over every tag on the chunk
  inside a border      the list is cut again, over what the border holds only

    .venv/Scripts/python.exe output/research/2026-10-10-two-clouds/both_sides_made_up.py

Reads the graph (read only), the side file of the tags' vectors the graph carries, and the query
side's vectors kept by two_clouds_made_up.py. No write, no model call, no test question.
"""
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np

print("both_sides_made_up: loading", flush=True)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_facet_joint import _unit  # noqa: E402
from graph.db import _driver  # noqa: E402

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
    return (", ".join(shown) + (f" and {more} more" if more > 0 else "")) or "none"


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

J = json.loads((ARRAYS / "structure_last_arrays.json").read_text(encoding="utf-8"))
A = np.load(ARRAYS / "structure_last_arrays.npz")
kinds = [str(r["kind"] or "") for r in chunk_rows]
if [J["kind_names"][i] for i in A["kind"]] != kinds:
    raise SystemExit("the graph read now is not the pool the saved tree was made from")
paths = {p: np.array(sorted(m), dtype=np.int64) for p, m in J["paths"].items()}
branches = sorted(p for p in paths if "/" not in p)
branch_of = np.full(n, -1, dtype=np.int64)
for b, name in enumerate(branches):
    branch_of[paths[name]] = b
inner = {p.rsplit("/", 1)[0] for p in paths if "/" in p}
own = [p for p in sorted(paths) if p not in inner]
kind_names = sorted(set(kinds))
kind_of = np.array([kind_names.index(x) for x in kinds], dtype=np.int64)

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
eligible = sorted({t for t, _ in edge_rows if t.casefold() not in folded})
at = {t: i for i, t in enumerate(eligible)}
ci = {c: i for i, c in enumerate(chunk_ids)}
tag_matrix = _unit(np.asarray(side["matrix"][[side_at[t] for t in eligible]], dtype=np.float32)).astype(np.float64)
edge_tag = np.array([at[t] for t, _ in edge_rows if t in at], dtype=np.int64)
edge_chunk = np.array([ci[c] for t, c in edge_rows if t in at], dtype=np.int64)
closeness = tag_matrix @ vectors[2:].T                       # (graph tags, querytags)
through = np.full((n, len(query_tags)), -1.0)
for q in range(len(query_tags)):
    np.maximum.at(through[:, q], edge_chunk, closeness[edge_tag, q])

SIDES = {"the question": described @ vectors[0],
         "the description": described @ vectors[1],
         "the tags": through.max(axis=1)}


def border(x, k):
    """A side's nearness cloud, the branches it names, and every chunk under those branches."""
    one = levels(x, k) == 1
    own_mean = np.array([x[paths[p]].mean() for p in own])
    near = np.flatnonzero(levels(own_mean, k) == 1)
    main = sorted({own[i].split("/")[0] for i in near if one[paths[own[i]]].any()})
    inside = np.zeros(n, dtype=bool)
    for name in main:
        inside[paths[name]] = True
    return one, main, inside


def main_scopes(x, k):
    """The own scopes of a side's scope cloud that hold chunks of its nearness cloud."""
    one = levels(x, k) == 1
    own_mean = np.array([x[paths[p]].mean() for p in own])
    near = np.flatnonzero(levels(own_mean, k) == 1)
    return {int(i) for i in near if one[paths[own[i]]].any()}


def near_scopes(x, k):
    """The own scopes of a side's scope cloud: the first cluster of the per-scope averages."""
    own_mean = np.array([x[paths[p]].mean() for p in own])
    return {int(i) for i in np.flatnonzero(levels(own_mean, k) == 1)}


def per_branch(mask):
    return named(np.bincount(branch_of[mask], minlength=len(branches)), branches)


def some(names):
    return (", ".join(names[:SHOWN]) + (" ..." if len(names) > SHOWN else "")) or "none"


for k in KS:
    got = {name: border(x, k) for name, x in SIDES.items()}
    print(f"\n== k={k} ==")
    print("  each side's nearness cloud")
    for name, (one, _, _) in got.items():
        label = "through the tags" if name == "the tags" else f"chunk descriptions to {name}"
        print(f"    {label}: {int(one.sum())} chunks in "
              f"{np.unique(branch_of[one]).size} branches: {per_branch(one)}")
    print("  the border each side sets")
    for name, (_, main, inside) in got.items():
        print(f"    by {name}: {some(main)} ({len(main)} branches, {int(inside.sum())} chunks)")
    print("  together")
    t_one, t_main, t_in = got["the tags"]
    for name in ("the question", "the description"):
        d_one, d_main, d_in = got[name]
        both = t_one & d_one
        either = t_one | d_one
        shared = sorted(set(t_main) & set(d_main))
        top = np.bincount(branch_of[both], minlength=len(branches)).max() if both.any() else 0
        print(f"    in the tags' cloud or in the cloud of {name}: {int(either.sum())} chunks: {per_branch(either)}")
        print(f"    in the tags' cloud and in the cloud of {name}: {int(both.sum())} chunks: {per_branch(both)}"
              f"; the largest branch holds {'over' if 2 * top > both.sum() else 'not over'} half")
        print(f"    branches both the tags and {name} name: {some(shared)} ({len(shared)})")
        scopes = sorted(main_scopes(SIDES["the tags"], k) & main_scopes(SIDES[name], k))
        under = sorted({own[i].split("/")[0] for i in scopes})
        print(f"    scopes in the scope cloud of the tags and of {name}: {len(scopes)}: "
              f"{some([own[i] for i in scopes])}; their branches: {some(under)} "
              f"({len(under)}, {sum(len(paths[b]) for b in under)} chunks)")

    # His "overlapping clouds for each step": at the scope step the chunks both nearness clouds
    # hold and the scopes both scope clouds hold; the scopes of the second that hold chunks of
    # the first, as their branch. Inside that border both sides are cut again over what it holds.
    print("  overlapping clouds for each step")
    for name in ("the question", "the description"):
        x_t, x_d = SIDES["the tags"], SIDES[name]
        both_chunks = (levels(x_t, k) == 1) & (levels(x_d, k) == 1)
        both_scopes = sorted(near_scopes(x_t, k) & near_scopes(x_d, k))
        main = [i for i in both_scopes if both_chunks[paths[own[i]]].any()]
        under = sorted({own[i].split("/")[0] for i in main})
        held = np.zeros(n, dtype=bool)
        for b in under:
            held[paths[b]] = True
        print(f"    with {name}, the scope step: {int(both_chunks.sum())} chunks in both nearness clouds, "
              f"{len(both_scopes)} scopes in both scope clouds, {len(main)} of those hold such chunks: "
              f"{some([own[i] for i in main])}; their branches: {some(under)} ({len(under)}, {int(held.sum())} chunks)")
        if held.any():
            where = np.flatnonzero(held)
            t_first = levels(x_t[where], k) == 1
            d_first = levels(x_d[where], k) == 1
            print(f"    with {name}, inside: the tags' cloud {int(t_first.sum())} chunks, the chunk descriptions' cloud "
                  f"{int(d_first.sum())}, in both {int((t_first & d_first).sum())}, in one {int((t_first ^ d_first).sum())}, "
                  f"in neither {int((~t_first & ~d_first).sum())}; in both, by kind: "
                  f"{named(np.bincount(kind_of[where[t_first & d_first]], minlength=len(kind_names)), kind_names, 6)}")

    print("  as now: the chunk descriptions set the border, the tags inside it")
    for name in ("the question", "the description"):
        _, d_main, d_in = got[name]
        held = d_in[edge_chunk]
        tags_in = np.unique(edge_tag[held])
        pairs = closeness[tags_in]                           # every querytag's closeness, one list
        picked = (levels(pairs.ravel(), k) == 1).reshape(pairs.shape).any(axis=1)
        is_picked = np.zeros(len(eligible), dtype=bool)
        is_picked[tags_in[picked]] = True
        reached = np.zeros(n, dtype=bool)
        reached[edge_chunk[held & is_picked[edge_tag]]] = True
        low = pairs[(levels(pairs.ravel(), k) == 1).reshape(pairs.shape)].min()
        print(f"    border by {name} ({int(d_in.sum())} chunks): {tags_in.size} tags inside, "
              f"{int(picked.sum())} in the first cluster (down to {low:.3f}), on {int(reached.sum())} chunks: "
              f"{per_branch(reached)}; by kind: {named(np.bincount(kind_of[reached], minlength=len(kind_names)), kind_names, 6)}")

    print("  the opposite: the tags set the border, the chunk descriptions inside it")
    where = np.flatnonzero(t_in)
    for name in ("the question", "the description"):
        x = SIDES[name][where]
        first = np.zeros(n, dtype=bool)
        first[where[levels(x, k) == 1]] = True
        print(f"    border by the tags ({where.size} chunks), nearness to {name}, the first cluster: "
              f"{int(first.sum())} chunks, down to {x[levels(x, k) == 1].min():.3f}: {per_branch(first)}; "
              f"by kind: {named(np.bincount(kind_of[first], minlength=len(kind_names)), kind_names, 6)}")
print("done", flush=True)

"""The clusterings tried on 2026-10-08 on one querytag's nearness values, run again on the same
querytags of the made-up question with the graph's tags and the querytags behind "query: ".

Per querytag, side by side: the values as the arm has them now (the saved arrays of 2026-10-07,
stored tag vectors, querytags behind "passage: ") and the query-mode values (the side file of
2026-10-08, querytags embedded now behind "query: "). The clusterings are the ones of
output/research/2026-10-08-his-ideas (`clustering_decides_the_hits`, `levels_from_the_distances`)
and the arm's `v4_walk.top_cluster`, unchanged:

  mixture  a Gaussian mixture on the line, the number of levels the one with the smallest BIC
  A        least-squares clusters on the line of all values, K at the bend of the fit curve
  B        the same on the values above the middle
  C        the jumps: a level ends at a step larger than the steps of the list below the middle
  D        the knee of the sorted curve above the middle, repeated inside what lies above it
  apart    single linkage on the values above the middle, cut at the largest jump of the merge
           distances (`v4_walk.top_cluster`)
  mirror   the tags further above the middle than any tag lies below it

    .venv/Scripts/python.exe output/research/2026-10-08-query-mode-tags/picking_on_the_open_scale.py

Reads the tag names from the graph (read only). No write, no model call, no test question.
"""
import json
import sys
import warnings
from pathlib import Path

import numpy as np

print("picking_on_the_open_scale: loading", flush=True)

REPO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

from sklearn.mixture import GaussianMixture  # noqa: E402

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_facet_joint import _unit  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from graph.db import _driver  # noqa: E402
from harness import embed  # noqa: E402

SOURCE = REPO / "output/research/2026-10-07-structure-last"
SIDE = REPO / "output/embed_local/20261008_rev113abe4acafa_float32/tags_query.npz"
A = np.load(SOURCE / "structure_last_arrays.npz")
J = json.loads((SOURCE / "structure_last_arrays.json").read_text(encoding="utf-8"))
NAMES = ("MATCH (t:Tag) WHERE t.emb IS NOT NULL AND EXISTS { MATCH (t)<-[r:HAS_TAG]-(c:Chunk) "
         "WHERE r.run_id = $run AND (c)-[:product]->() } RETURN t.name AS id ORDER BY id")
K_MOST = 40          # as on 2026-10-08: the fit curve is drawn this far
BINS = 1500
SHOWN = 14           # tags listed by name per level

driver = _driver()
try:
    with driver.session(database=V.DATABASE, default_access_mode="READ") as session:
        names = np.array([r["id"] for r in session.run(NAMES, run=V.RUN_ID)], dtype=object)
finally:
    driver.close()
eligible = A["eligible"].astype(bool)
if names.size != eligible.size:
    raise RuntimeError("the graph read now is not the one the saved arrays were made from")


def mixture(values):
    """`clustering_decides_the_hits.levels`: K by the smallest BIC, searched upward from one
    until it rises. Returns K and the mask of the values the fit puts in the nearest level."""
    x = np.asarray(values, dtype=np.float64).reshape(-1, 1)
    best = None
    for count in range(1, 30):
        start = np.quantile(x, (np.arange(count) + 0.5) / count).reshape(-1, 1)
        fit = GaussianMixture(count, means_init=start, random_state=0, max_iter=500).fit(x)
        score = fit.bic(x)
        if best is not None and score >= best[0]:
            break
        best = (score, count, fit)
    _, count, fit = best
    top = int(np.argmax(fit.means_.ravel()))
    return count, fit.predict(x) == top


def squares_by_count(x, most):
    edges = np.linspace(x[0], x[-1], BINS + 1)
    which = np.clip(np.searchsorted(edges, x, side="right") - 1, 0, BINS - 1)
    used = np.unique(which)
    w = np.array([(which == b).sum() for b in used], dtype=np.float64)
    a = np.array([x[which == b].sum() for b in used])
    q = np.array([(x[which == b] ** 2).sum() for b in used])
    m = used.size
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
    for count in range(2, min(most, m) + 1):
        lead = np.full(m, np.inf)
        lead[1:] = prev[:-1]
        table = lead[:, None] + cost
        start = np.argmin(table, axis=0)
        prev = table[start, at]
        back.append(start)
        totals.append(float(prev[-1]))
    return np.array(totals), back, c0


def cuts_for(back, count, c0):
    starts, end = [], len(back[0]) - 1
    for g in range(count - 1, -1, -1):
        start = int(back[g][end]) if g else 0
        starts.append(int(c0[start]))
        end = start - 1
    return starts[::-1]


def bend(curve):
    y = np.asarray(curve, dtype=np.float64)
    if y.size < 3 or y[0] == y[-1]:
        return 0
    x = np.linspace(0., 1., y.size)
    y = (y - y[-1]) / (y[0] - y[-1])
    return int(np.argmax((1. - x) - y))


def natural(values):
    x = np.sort(values)
    totals, back, c0 = squares_by_count(x, min(K_MOST, x.size - 1))
    count = bend(totals) + 1
    starts = cuts_for(back, count, c0)
    return count, np.diff(starts + [x.size])[::-1].tolist()


def jumps(values, middle):
    above = np.sort(values[values > middle])[::-1]
    below = np.sort(values[values < middle])
    steps_above = above[:-1] - above[1:]
    steps_below = below[1:] - below[:-1]
    span = min(steps_above.size, steps_below.size)
    larger = np.flatnonzero(steps_above[:span] > np.maximum.accumulate(
        np.r_[steps_below[:span][1:], 0.][::-1])[::-1])
    return np.diff(np.r_[0, larger + 1]).tolist()


def knee_levels(values, middle):
    above = np.sort(values[values > middle])[::-1]
    sizes, end = [], above.size
    while end > 3:
        k = bend(above[:end])
        if k < 1 or k >= end - 1:
            break
        sizes.append(end - k)
        end = k
    sizes.append(end)
    return sizes[::-1]


def report(label, values, tag_names, by_name):
    order = np.argsort(-values)
    middle = float(np.median(values))
    spread = float(WK.MAD_TO_SPREAD * np.median(np.abs(values - middle)))
    print(f"  -- {label}: middle {middle:.3f}, spread {spread:.4f}, nearest {values[order[0]]:.3f}, "
          f"lowest {values.min():.3f}")
    print("     the nearest 24: " + " ".join(f"{v:.3f}" for v in values[order[:24]]))
    count, top = mixture(values)
    low = float(values[top].min()) if top.any() else float("nan")
    print(f"     mixture: K {count}; the nearest level holds {int(top.sum())} tags, down to {low:.3f}")
    count_a, sizes_a = natural(values)
    print(f"     A all values: K {count_a}; level sizes from the nearest: {sizes_a[:6]}")
    count_b, sizes_b = natural(values[values > middle])
    print(f"     B above the middle: K {count_b}; level sizes from the nearest: {sizes_b[:6]}")
    sizes_c = jumps(values, middle)
    print(f"     C the jumps: {len(sizes_c)} levels; sizes from the nearest: {sizes_c[:8]}")
    sizes_d = knee_levels(values, middle)
    print(f"     D the knee, repeated: level sizes from the nearest: {sizes_d[:8]}")
    apart = WK.top_cluster(values, above_middle=True)
    print(f"     apart (single linkage, largest jump): {int(apart.sum())} tags"
          + (f", down to {values[apart].min():.3f}; the next tag is at "
             f"{values[~apart].max():.3f}" if apart.any() else ""))
    mirror = values - middle > middle - values.min()
    print(f"     mirror (further above the middle than any tag lies below it, above "
          f"{2 * middle - values.min():.3f}): {int(mirror.sum())} tags")
    if by_name:
        print("     by name, nearest first: " + ", ".join(
            f"{tag_names[t]} {values[t]:.3f}" for t in order[:40]))
        at = 0
        for level, size in enumerate(sizes_d[:3], 1):
            members = order[at:at + size]
            print(f"     D level {level} ({size}): " + ", ".join(
                f"{tag_names[t]} {values[t]:.3f}" for t in members[:SHOWN])
                + (" ..." if size > SHOWN else ""))
            at += size
    return {"mixture": int(top.sum()), "A": sizes_a[0], "B": sizes_b[0],
            "C": sizes_c[0] if sizes_c else 0, "D": sizes_d[0], "apart": int(apart.sum()),
            "mirror": int(mirror.sum())}


side = np.load(SIDE, allow_pickle=True)
side_at = {str(name): i for i, name in enumerate(side["ids"])}
graph_query = _unit(np.asarray(side["matrix"][[side_at[str(t)] for t in names]], dtype=np.float32))
distinct = list(dict.fromkeys(J["query_tags"]))
tag_query = _unit(np.asarray(embed._embed([t.strip() for t in distinct], "query", bar=False)[0],
                             dtype=np.float32))
query_rows = tag_query.astype(np.float64) @ graph_query.astype(np.float64).T

print(f"the question: {J['question']}")
print(f"{int(eligible.sum())} graph tags compared, {len(distinct)} different querytags")
table = []
for k, tag in enumerate(distinct):
    i = J["query_tags"].index(tag)
    print(f"\n\"{tag}\"")
    now = report("as the arm has it (passage)", A["cosines"][i].astype(np.float64)[eligible],
                 names[eligible], False)
    new = report("behind \"query: \"", query_rows[k][eligible], names[eligible], True)
    table.append((tag, now, new))

print("\n== tags in the nearest level, as the arm has it / behind \"query: \" ==")
keys = ("mixture", "A", "B", "C", "D", "apart", "mirror")
print("querytag | " + " | ".join(keys))
for tag, now, new in table:
    print(f"{tag} | " + " | ".join(f"{now[key]} / {new[key]}" for key in keys))
print("done", flush=True)

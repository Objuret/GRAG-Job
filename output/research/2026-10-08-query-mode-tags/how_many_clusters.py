"""His 2026-10-08 "just do a fucking exploration and see how many clusters it discovers".

Clusterings that find the number of clusters themselves, each run on (a) the nearness values of
one querytag of the made-up question against every eligible graph tag, tags and querytag behind
"query: ", and (b) all pairs of two different eligible graph tags together. None is given a K.

  mixture      a Gaussian mixture on the line; K the one with the smallest BIC, searched upward
               from one until the BIC rises
  ls-bend      least-squares clusters on the line (exact, by dynamic programme over fine bins);
               K where the curve of the fit bends most (drawn to K_MOST)
  ls-bic       the same clusters; K with the smallest BIC of the clusters read as normal groups
               (the rule of Ckmeans.1d.dp), searched to K_MOST
  head/tail    head/tail breaks (Jiang 2013): cut at the mean, keep cutting the part above it
               while that part is the smaller one
  density      the humps of the density of the values (normal kernel, Silverman's width); a
               cluster is what lies between two dips
  hdbscan      HDBSCAN on the line with scikit-learn's own settings; it also leaves values
               outside every cluster

    .venv/Scripts/python.exe output/research/2026-10-08-query-mode-tags/how_many_clusters.py

Reads the tag names from the graph (read only). No write, no model call, no test question.
"""
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np

print("how_many_clusters: loading", flush=True)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

from scipy.stats import gaussian_kde  # noqa: E402
from sklearn.mixture import GaussianMixture  # noqa: E402

try:
    from sklearn.cluster import HDBSCAN  # noqa: E402
except ImportError:
    HDBSCAN = None

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_facet_joint import _unit  # noqa: E402
from graph.db import _driver  # noqa: E402

SOURCE = REPO / "output/research/2026-10-07-structure-last"
SIDE = REPO / "output/embed_local/20261008_rev113abe4acafa_float32/tags_query.npz"
ROWS = HERE / "querytag_rows_query_mode.npz"
A = np.load(SOURCE / "structure_last_arrays.npz")
J = json.loads((SOURCE / "structure_last_arrays.json").read_text(encoding="utf-8"))
NAMES = ("MATCH (t:Tag) WHERE t.emb IS NOT NULL AND EXISTS { MATCH (t)<-[r:HAS_TAG]-(c:Chunk) "
         "WHERE r.run_id = $run AND (c)-[:product]->() } RETURN t.name AS id ORDER BY id")
K_MOST = 40          # how far the two least-squares rules look
BINS = 1500          # the bins of the dynamic programme
GRID = 4000          # the points the density is read at
PAIR_BINS = 2000     # all pairs are counted in steps of 0.001
SHOWN = 14           # tags listed by name per cluster
NULL_SEED, NULLS, NULL_LETTERS = 20261008, 3, 8   # querytags of random letters: nothing is near


def bins_of(x):
    """Sorted values gathered into BINS equal-width bins: per used bin its count, sum and sum
    of squares."""
    edges = np.linspace(x[0], x[-1], BINS + 1)
    which = np.clip(np.searchsorted(edges, x, side="right") - 1, 0, BINS - 1)
    count = np.bincount(which, minlength=BINS).astype(np.float64)
    total = np.bincount(which, weights=x, minlength=BINS)
    square = np.bincount(which, weights=x * x, minlength=BINS)
    used = count > 0
    return count[used], total[used], square[used]


def squares(w, a, q, most):
    """Least-squares clusters of binned values for every number of clusters up to `most`: the
    within-cluster squares, and per number the count of values before each cluster's start."""
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
    for count in range(2, min(most, m) + 1):
        lead = np.full(m, np.inf)
        lead[1:] = prev[:-1]
        table = lead[:, None] + cost
        start = np.argmin(table, axis=0)
        prev = table[start, at]
        back.append(start)
        totals.append(float(prev[-1]))

    def starts(count):
        out, end = [], m - 1
        for g in range(count - 1, -1, -1):
            start = int(back[g][end]) if g else 0
            out.append(start)
            end = start - 1
        return out[::-1]                       # the first bin of each cluster, lowest first
    return np.array(totals), starts, (c0, c1, c2)


def bend(curve):
    y = np.asarray(curve, dtype=np.float64)
    if y.size < 3 or y[0] == y[-1]:
        return 0
    x = np.linspace(0., 1., y.size)
    y = (y - y[-1]) / (y[0] - y[-1])
    return int(np.argmax((1. - x) - y))


def group_bic(starts, sums, floor):
    """BIC of least-squares clusters read as normal groups, each with its own middle, spread and
    share (3K - 1 numbers). A group's variance is never taken under `floor`."""
    c0, c1, c2 = sums
    n = c0[-1]
    edges = list(starts) + [c0.size - 1]
    log_likelihood = 0.
    for lo, hi in zip(edges[:-1], edges[1:]):
        size = c0[hi] - c0[lo]
        ss = max(c2[hi] - c2[lo] - (c1[hi] - c1[lo]) ** 2 / size, 0.)
        variance = max(ss / size, floor)
        log_likelihood += (size * np.log(size / n) - 0.5 * size * np.log(2 * np.pi * variance)
                           - ss / (2 * variance))
    return -2. * log_likelihood + (3 * len(starts) - 1) * np.log(n)


def least_squares(w, a, q, width):
    """Returns for the bend rule and the BIC rule: K and each cluster's count, lowest first."""
    totals, starts, sums = squares(w, a, q, K_MOST)
    c0 = sums[0]
    out = {}
    by_bend = bend(totals) + 1
    bics = [group_bic(starts(k), sums, width * width / 12.) for k in range(1, totals.size + 1)]
    by_bic = int(np.argmin(bics)) + 1
    for name, count in (("ls-bend", by_bend), ("ls-bic", by_bic)):
        first = starts(count)
        out[name] = (count, np.diff(np.r_[c0[first], c0[-1]]).astype(np.int64))
    return out, by_bic == totals.size


def describe(x, sizes_low_first):
    """Clusters given as counts over the sorted values, lowest first: K, the sizes from the
    nearest, and the lowest value of each cluster from the nearest."""
    order = np.sort(x)
    ends = np.cumsum(sizes_low_first)
    lows = order[np.r_[0, ends[:-1]]]
    return sizes_low_first[::-1].tolist(), lows[::-1].tolist()


def mixture(x):
    column = x.reshape(-1, 1)
    best = None
    for count in range(1, 30):
        start = np.quantile(column, (np.arange(count) + 0.5) / count).reshape(-1, 1)
        fit = GaussianMixture(count, means_init=start, random_state=0, max_iter=500).fit(column)
        score = fit.bic(column)
        if best is not None and score >= best[0]:
            break
        best = (score, count, fit)
    _, count, fit = best
    label = fit.predict(column)
    by = np.argsort(-fit.means_.ravel())
    return count, [int((label == g).sum()) for g in by], [
        float(x[label == g].min()) if (label == g).any() else float("nan") for g in by]


def head_tail(x):
    data, breaks = x, []
    while True:
        middle = float(data.mean())
        head = data[data > middle]
        if head.size < 2 or head.size * 2 >= data.size:
            break
        breaks.append(middle)
        data = head
    edges = np.r_[-np.inf, breaks, np.inf]
    sizes = [int(((x > lo) & (x <= hi)).sum()) for lo, hi in zip(edges[:-1], edges[1:])]
    return len(breaks) + 1, sizes[::-1], breaks[::-1]


def density(x):
    grid = np.linspace(x.min(), x.max(), GRID)
    d = gaussian_kde(x, bw_method="silverman")(grid)
    inner = np.arange(1, GRID - 1)
    humps = inner[(d[inner] > d[inner - 1]) & (d[inner] >= d[inner + 1])]
    dips = [int(lo + np.argmin(d[lo:hi + 1])) for lo, hi in zip(humps[:-1], humps[1:])]
    edges = np.r_[-np.inf, grid[dips], np.inf]
    sizes = [int(((x > lo) & (x <= hi)).sum()) for lo, hi in zip(edges[:-1], edges[1:])]
    largest = int(np.argmax(d[humps]))                 # the hump that holds most of the values
    edge = float(grid[dips[largest]]) if largest < len(dips) else None
    return (humps.size, sizes[::-1], grid[dips][::-1].tolist(), float(grid[humps[largest]]),
            edge, int((x > edge).sum()) if edge is not None else 0)


def hdbscan(x):
    if HDBSCAN is None:
        return None
    label = HDBSCAN().fit_predict(x.reshape(-1, 1))
    found = [g for g in range(int(label.max()) + 1)]
    found.sort(key=lambda g: -float(x[label == g].mean()))
    return (len(found), int((label < 0).sum()), [int((label == g).sum()) for g in found],
            [float(x[label == g].min()) for g in found])


def short(values, digits=3, most=8):
    values = list(values)
    text = ", ".join(f"{v:.{digits}f}" if isinstance(v, float) else f"{v:,}" for v in values[:most])
    return "[" + text + (", ..." if len(values) > most else "") + "]"


driver = _driver()
try:
    with driver.session(database=V.DATABASE, default_access_mode="READ") as session:
        names = np.array([r["id"] for r in session.run(NAMES, run=V.RUN_ID)], dtype=object)
finally:
    driver.close()
eligible = A["eligible"].astype(bool)
if names.size != eligible.size:
    raise RuntimeError("the graph read now is not the one the saved arrays were made from")
side = np.load(SIDE, allow_pickle=True)
side_at = {str(name): i for i, name in enumerate(side["ids"])}
graph = _unit(np.asarray(side["matrix"][[side_at[str(t)] for t in names]], dtype=np.float32))
distinct = list(dict.fromkeys(J["query_tags"]))
# A reference with no meaning: two "words" of seeded random letters, embedded like a querytag.
letters = np.random.default_rng(NULL_SEED).integers(0, 26, size=(NULLS, 2, NULL_LETTERS))
nulls = [" ".join("".join(chr(97 + int(v)) for v in word) for word in pair) for pair in letters]
distinct += nulls
if ROWS.is_file() and list(np.load(ROWS, allow_pickle=True)["tags"]) == distinct:
    rows = np.load(ROWS, allow_pickle=True)["rows"]
else:
    from harness import embed
    vectors = _unit(np.asarray(embed._embed([t.strip() for t in distinct], "query", bar=False)[0],
                               dtype=np.float32))
    rows = vectors.astype(np.float64) @ graph.astype(np.float64).T
    np.savez(ROWS, tags=np.array(distinct, dtype=object), rows=rows)
tag_names = names[eligible]
print(f"the question: {J['question']}")
print(f"{int(eligible.sum())} eligible graph tags, {len(distinct) - len(nulls)} different querytags "
      f"and {len(nulls)} of random letters, tags and "
      f"querytags behind \"query: \"; HDBSCAN {'on' if HDBSCAN else 'not in this scikit-learn'}",
      flush=True)

table = []
for k, tag in enumerate(distinct):
    t0 = time.perf_counter()
    x = rows[k][eligible].astype(np.float64)
    order = np.argsort(-x)
    print(f"\n\"{tag}\"{' (random letters)' if tag in nulls else ''}: middle {np.median(x):.3f}, "
          f"nearest {x[order[0]]:.3f}, lowest {x.min():.3f}")
    print("  the nearest 16: " + " ".join(f"{v:.3f}" for v in x[order[:16]]))
    found = {}
    count, sizes, lows = mixture(x)
    found["mixture"] = count
    print(f"  mixture:   {count} clusters; sizes from the nearest {short(sizes)}; each one's "
          f"lowest value {short(lows)}")
    sorted_x = np.sort(x)
    ls, capped = least_squares(*bins_of(sorted_x), (sorted_x[-1] - sorted_x[0]) / BINS)
    kept = {}
    for name in ("ls-bend", "ls-bic"):
        count, low_first = ls[name]
        sizes, lows = describe(x, low_first)
        found[name] = count
        kept[name] = sizes
        print(f"  {name}:   {count} clusters{' (the most looked for)' if name == 'ls-bic' and capped else ''}"
              f"; sizes from the nearest {short(sizes)}; each one's lowest value {short(lows)}")
    count, sizes, breaks = head_tail(x)
    found["head/tail"] = count
    kept["head/tail"] = sizes
    print(f"  head/tail: {count} clusters; sizes from the nearest {short(sizes)}; cut at "
          f"{short(breaks)}")
    count, sizes, dips, bulk, edge, above = density(x)
    found["density"] = count
    found["above the large hump"] = above
    print(f"  density:   {count} humps, the largest at {bulk:.3f}; sizes from the nearest "
          f"{short(sizes)}; dips at {short(dips)}")
    if edge is None:
        print("             no dip above the large hump: nothing lies above it")
    else:
        print(f"             the large hump ends at {edge:.3f}; {above:,} tags lie above it: "
              + ", ".join(f"{tag_names[t]} {x[t]:.3f}" for t in order[:min(above, 40)])
              + (" ..." if above > 40 else ""))
    result = hdbscan(x)
    if result is not None:
        count, outside, sizes, lows = result
        found["hdbscan"] = count
        print(f"  hdbscan:   {count} clusters, {outside:,} values in none; sizes from the nearest "
              f"{short(sizes)}; each one's lowest value {short(lows)}")
    for name in ("ls-bend", "ls-bic", "head/tail"):
        at = 0
        for level, size in enumerate(kept[name][:3], 1):
            members = order[at:at + size]
            print(f"    {name} cluster {level} ({size:,}): " + ", ".join(
                f"{tag_names[t]} {x[t]:.3f}" for t in members[:SHOWN])
                + (" ..." if size > SHOWN else ""))
            at += size
    table.append((tag + (" (random letters)" if tag in nulls else ""), found))
    print(f"  ({time.perf_counter() - t0:.0f}s)", flush=True)

print("\n== all pairs of two different eligible graph tags, behind \"query: \" ==", flush=True)
vectors = graph[eligible].astype(np.float32)
edges = np.linspace(-1., 1., PAIR_BINS + 1)
counts = np.zeros(PAIR_BINS, dtype=np.int64)
for start in range(0, vectors.shape[0], 1024):
    stop = min(start + 1024, vectors.shape[0])
    s = np.clip(vectors[start:stop] @ vectors.T, -1., 1.)
    s[np.arange(stop - start), np.arange(start, stop)] = 3.
    counts += np.histogram(s, bins=edges)[0]
counts = counts // 2
centres = (edges[:-1] + edges[1:]) / 2
used = counts > 0
w, c = counts[used].astype(np.float64), centres[used]
print(f"{int(w.sum()):,} pairs, lowest {c[0]:.3f}, highest {c[-1]:.3f}, counted in steps of "
      f"{edges[1] - edges[0]:.3f}")
ls, capped = least_squares(w, w * c, w * c * c, edges[1] - edges[0])
pair_found = {}
cumulative = np.concatenate(([0.], np.cumsum(w)))
for name in ("ls-bend", "ls-bic"):
    count, low_first = ls[name]
    ends = np.cumsum(low_first)
    lows = c[np.searchsorted(cumulative[1:], np.r_[0, ends[:-1]], side="right")]
    pair_found[name] = count
    print(f"  {name}:   {count} clusters{' (the most looked for)' if name == 'ls-bic' and capped else ''}"
          f"; sizes from the nearest {short(low_first[::-1].tolist())}; each one's lowest value "
          f"{short(lows[::-1].tolist())}")
left_w, left_c, breaks = w, c, []
while True:
    middle = float((left_w * left_c).sum() / left_w.sum())
    head = left_c > middle
    if left_w[head].sum() < 2 or left_w[head].sum() * 2 >= left_w.sum():
        break
    breaks.append(middle)
    left_w, left_c = left_w[head], left_c[head]
cuts = np.r_[-np.inf, breaks, np.inf]
sizes = [int(w[(c > lo) & (c <= hi)].sum()) for lo, hi in zip(cuts[:-1], cuts[1:])]
pair_found["head/tail"] = len(breaks) + 1
print(f"  head/tail: {len(breaks) + 1} clusters; sizes from the nearest {short(sizes[::-1])}; cut at "
      f"{short(breaks[::-1], most=12)}")

print("\n== how many clusters each one discovers ==")
keys = [key for key in ("mixture", "ls-bend", "ls-bic", "head/tail", "density", "hdbscan",
                        "above the large hump")
        if any(key in found for _, found in table)]
print("list | " + " | ".join(keys))
for tag, found in table:
    print(f"{tag} | " + " | ".join(str(found.get(key, "")) for key in keys))
print("all pairs | " + " | ".join(str(pair_found.get(key, "")) for key in keys))
print("done", flush=True)

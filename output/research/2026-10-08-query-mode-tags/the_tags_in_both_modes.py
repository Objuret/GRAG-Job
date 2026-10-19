"""The graph's 16,714 tags embedded behind "passage: " and behind "query: ", both by the local
embedder: how the numbers spread in each mode, where the arm's same-thing pairs sit against
all pairs, and whether a tag's nearest tags are the same ones in both modes.

    .venv/Scripts/python.exe output/research/2026-10-08-query-mode-tags/the_tags_in_both_modes.py

Reads two files and nothing else: no graph, no model, no question.
"""
import hashlib
import sys
import time
from pathlib import Path

import numpy as np

print("the_tags_in_both_modes: loading", flush=True)

REPO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]

from artefact import v4_walk as WK  # noqa: E402

FILES = {
    "passage": REPO / "output/embed_local/20261007_rev113abe4acafa_float32/tags_passage.npz",
    "query": REPO / "output/embed_local/20261008_rev113abe4acafa_float32/tags_query.npz",
}
BLOCK = 1024
NEAREST = (1, 2, 4, 8, 16, 32)          # doubling, so no one count is picked
EDGES = np.linspace(-1.0, 1.0, 20001)   # the cosine axis in steps of 0.0001
SHOWN, SEED, PICKS, SHOW = "rollback procedures", 20261008, 5, 5   # what is listed by name


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def at_share(counts, share):
    """The cosine under which `share` of the counted pairs lie, off the 0.0001 steps."""
    cum = np.cumsum(counts)
    return float(EDGES[min(int(np.searchsorted(cum, share * cum[-1])) + 1, EDGES.size - 1)])


def lowest(counts):
    """The lowest cosine any counted pair has, off the 0.0001 steps."""
    return float(EDGES[int(np.flatnonzero(counts)[0])])


def read(mode):
    path = FILES[mode]
    z = np.load(path, allow_pickle=True)
    ids = [str(i) for i in z["ids"]]
    m = np.asarray(z["matrix"], dtype=np.float32)
    lengths = np.linalg.norm(m, axis=1)
    print(f"{mode}: {path.relative_to(REPO).as_posix()}  sha256 {sha256_file(path)[:16]}  "
          f"{m.shape} {m.dtype}  row lengths {lengths.min():.6f} to {lengths.max():.6f}", flush=True)
    return ids, m


def sweep(mode, m, level):
    """Every tag against every other tag: the count of pairs per 0.0001 of cosine, each tag's
    nearest other tags, and how many other tags stand at or above `level`."""
    n = m.shape[0]
    counts = np.zeros(EDGES.size - 1, dtype=np.int64)
    top = np.empty((n, NEAREST[-1]), dtype=np.int32)
    top_cos = np.empty((n, NEAREST[-1]), dtype=np.float32)
    at_level = np.empty(n, dtype=np.int64)
    t0 = time.perf_counter()
    for start in range(0, n, BLOCK):
        stop = min(start + BLOCK, n)
        s = m[start:stop] @ m.T
        np.clip(s, -1.0, 1.0, out=s)
        own = (np.arange(stop - start), np.arange(start, stop))
        s[own] = 3.0                                   # the tag itself, outside the axis
        counts += np.histogram(s, bins=EDGES)[0]
        s[own] = -3.0
        at_level[start:stop] = (s >= level).sum(axis=1)
        part = np.argpartition(-s, NEAREST[-1], axis=1)[:, :NEAREST[-1]]
        cos = np.take_along_axis(s, part, axis=1)
        by = np.argsort(-cos, axis=1, kind="stable")
        top[start:stop] = np.take_along_axis(part, by, axis=1)
        top_cos[start:stop] = np.take_along_axis(cos, by, axis=1)
        if stop == n or (start // BLOCK) % 4 == 3:
            print(f"  {mode}: {stop}/{n} tags  {time.perf_counter() - t0:.0f}s", flush=True)
    return counts, top, top_cos, at_level


names, passage = read("passage")
names_q, query = read("query")
if names != names_q:
    raise SystemExit("the two files do not hold the same tags in the same order")
n = len(names)
everyone = np.ones(n, dtype=bool)
pairs = np.array(WK.same_thing_pairs(names), dtype=np.int64)
print(f"tags {n}; same-thing pairs by the arm's rule (same once lower-cased, or a final s "
      f"dropped), over every tag: {len(pairs)}", flush=True)

out = {}
for mode, m in (("passage", passage), ("query", query)):
    same = WK.same_thing_level(names, m, everyone)
    scores = np.einsum("ij,ij->i", m[pairs[:, 0]].astype(np.float64),
                       m[pairs[:, 1]].astype(np.float64))
    counts, top, top_cos, at_level = sweep(mode, m, same["level"])
    mean_length = float(np.linalg.norm(m.astype(np.float64).mean(axis=0)))
    total = int(counts.sum())
    above = int(counts[np.searchsorted(EDGES, same["level"], side="left"):].sum())
    out[mode] = {"top": top, "cos": top_cos}
    print(f"\n== behind \"{mode}: \" ==")
    print(f"length of the mean of all tag vectors (0 all ways, 1 all the same): {mean_length:.3f}")
    print(f"two different tags, all {total // 2:,} pairs: lowest {lowest(counts):.3f}  "
          f"1% {at_share(counts, 0.01):.3f}  middle {at_share(counts, 0.5):.3f}  "
          f"99% {at_share(counts, 0.99):.3f}  highest {float(top_cos[:, 0].max()):.3f}")
    print(f"a tag to its nearest other tag: lowest {float(top_cos[:, 0].min()):.3f}  "
          f"middle {float(np.median(top_cos[:, 0])):.3f}  highest {float(top_cos[:, 0].max()):.3f}")
    print(f"the same-thing pairs: lowest {scores.min():.3f}  the arm's level ({same['point']}% "
          f"of them under it) {same['level']:.4f}  middle {same['median']:.3f}  "
          f"highest {scores.max():.3f}")
    print(f"pairs at or above that level: {above // 2:,} of {total // 2:,} "
          f"({100.0 * above / total:.4f}%)")
    print(f"other tags a tag has at or above that level: none for "
          f"{int((at_level == 0).sum()):,} tags; middle {int(np.median(at_level))}; "
          f"highest {int(at_level.max())}")

print("\n== a tag's nearest tags, behind \"passage: \" against behind \"query: \" ==")
for k in NEAREST:
    a, b = out["passage"]["top"][:, :k], out["query"]["top"][:, :k]
    shared = np.array([np.intersect1d(a[i], b[i]).size for i in range(n)])
    print(f"the {k:>2} nearest: {100.0 * shared.mean() / k:5.1f}% are the same tags; "
          f"all {k} the same for {int((shared == k).sum()):,} tags, none for "
          f"{int((shared == 0).sum()):,}")
# The tag today's other measurements used, and seeded picks beside it.
picks = [names.index(SHOWN)] + [int(i) for i in np.random.default_rng(SEED).choice(n, PICKS, replace=False)]
print(f"\n== the {SHOW} nearest tags of \"{SHOWN}\" and of {PICKS} tags drawn with seed {SEED} ==")
for i in picks:
    print(f"{names[i]!r}")
    for mode in ("passage", "query"):
        near = ", ".join(f"{names[j]} {c:.3f}" for j, c in
                         zip(out[mode]["top"][i, :SHOW], out[mode]["cos"][i, :SHOW]))
        print(f"   {mode:>7}: {near}")
print("done", flush=True)

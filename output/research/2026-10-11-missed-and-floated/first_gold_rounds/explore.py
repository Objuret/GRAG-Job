"""Helpers for trying orders against the per-chunk table of the hundred (numbers only).

The rounds here were run from the folder the tables were written to, outside the repository,
because the tables hold which chunks are gold. The tables are written by
`first_gold_signals.py`, `first_gold_signals_more.py`, `first_gold_signals_bare.py` and
`what_a_chunk_holds.py` in the folder above (each takes that folder as its last argument); with
the tables beside these files the rounds run as they are. Each round's print is `roundN.log`."""
import pickle
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
BUDGET = 72000
sys.stdout.reconfigure(encoding="utf-8")


def load(name="gold100"):
    with open(HERE / f"first_gold_signals__{name}.pkl", "rb") as handle:
        return pickle.load(handle)


def standing(x):
    x = np.asarray(x, dtype=np.float64)
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


def zscore(x):
    x = np.asarray(x, dtype=np.float64)
    s = x.std()
    return (x - x.mean()) / s if s > 0 else np.zeros_like(x)


def places(x, d):
    """1 for the highest; ties by the chunk's id order."""
    order = np.lexsort((d["id_rank"], -np.asarray(x, dtype=np.float64)))
    place = np.empty(order.size, dtype=np.int64)
    place[order] = np.arange(1, order.size + 1)
    return place


def measure(score, d):
    """(first chunk is gold, place of the first gold chunk, context_recall_id at the budget)."""
    order = np.lexsort((d["id_rank"], -np.asarray(score, dtype=np.float64)))
    gold = d["gold"][order]
    first = int(np.argmax(gold)) + 1 if gold.any() else order.size + 1
    fits = np.cumsum(d["length"][order]) <= BUDGET
    kept = order[:int(fits.sum()) if fits.all() else int(np.argmin(fits))]
    cited = set(d["cited_ids"])
    have = set()
    for k in kept:
        have.update(d["records"][k])
    return bool(gold[0]), first, len(cited & have) / d["cites"]


def report(scores, data, sort=True, show=None):
    """scores: name -> function(d) -> score per chunk. Prints one line per name."""
    rows = []
    for name, make in scores.items():
        got = [measure(make(d), d) for d in data["questions"].values()]
        first = sum(g[0] for g in got)
        pos = np.array([g[1] for g in got])
        rows.append((first, name, pos, float(np.mean([g[2] for g in got]))))
    if sort:
        rows.sort(key=lambda r: (-r[0], r[1]))
    print("first chunk gold (of %d) | first gold within 3 | within 5 | place of the first gold chunk: the middle "
          "(quarters), mean | context_recall_id" % len(data["questions"]))
    for first, name, pos, recall in rows[:show]:
        print(f"  {first:3d} | {int((pos <= 3).sum()):3d} | {int((pos <= 5).sum()):3d} | {np.median(pos):.0f} "
              f"({np.percentile(pos, 25):.0f}-{np.percentile(pos, 75):.0f}), {pos.mean():.1f} | {recall:.3f}  {name}")
    return rows

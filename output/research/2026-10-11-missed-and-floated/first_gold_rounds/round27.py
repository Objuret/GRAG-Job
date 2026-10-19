"""Round 27: the sure set as runs. A gold chunk of the sure set stands right above or under another
gold chunk of it 62% of the time, a sure chunk that is not gold 19% (round 26). So the sure set
may fall into runs (sure chunks that follow each other in their parent), some gold and some
not. Inside the question's product, the hundred. The sure set is that of round 22.

A run: sure chunks of one parent whose places follow each other with no gap. Printed:
  the runs a question, their sizes; how pure they are (all gold, none gold, mixed)
  with the gold in hand: the share of the sure set's gold that sits in its richest run
  without it: the run picked by a rule that needs no gold (the longest; the one with the highest
  summed value; the one with the highest mean value; the one holding the highest chunk; the one
  with the most chunks on the combo's first step): the share of the picked run that is gold, how
  often it holds any gold... given as the share of its chunks that are gold beside the sure
  set's 29%
  the chunks right above and under the picked run's ends (outside the sure set): share gold
  orders: the picked run first, then the chunks above and under it, then the rest of the sure
  set, then the rest: first chunk gold (of 100) and context_recall_id (share of the cited
  records delivered inside 72,000 characters)."""
import sys

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

from explore import BUDGET, load, standing  # noqa: E402

data = load()
Q = data["questions"]


def majority(hits, areas):
    ids = np.unique(areas)
    held = np.array([int(hits[areas == a].sum()) for a in ids])
    if not held.sum():
        return np.ones(areas.size, dtype=bool)
    taken, total = [], 0
    for k in np.lexsort((ids, -held)):
        taken.append(ids[k])
        total += held[k]
        if total * 2 > held.sum():
            break
    return np.isin(areas, taken)


def run_order(order, d):
    order = np.asarray(order, dtype=np.int64)
    fits = np.cumsum(d["length"][order]) <= BUDGET
    kept = order[:int(fits.sum()) if fits.all() else int(np.argmin(fits))]
    cited, have = set(d["cited_ids"]), set()
    for k in kept:
        have.update(d["records"][k])
    return bool(d["gold"][order[0]]), len(cited & have) / d["cites"]


n_runs, sizes, purity = [], [], {"all gold": 0, "no gold": 0, "mixed": 0}
purity_chunks = {"all gold": 0, "no gold": 0, "mixed": 0}
richest_share = []
rules = {}
ends = {}
orders = {}
count = len(Q)
for d in Q.values():
    D, T = np.asarray(d["description"], dtype=np.float64), np.asarray(d["tags"], dtype=np.float64)
    m, gold = D.size, d["gold"]
    step = WK.levels(D, 5) + WK.levels(T, 5)
    z = standing(D) + standing(T)
    hits = step <= 3 if (step <= 3).any() else step == step.min()
    scope = majority(hits, d["parent"])
    sure = (scope & (step <= 4)) | (~scope & (step == 2))
    cell = np.where(scope & (step == 2), 0, np.where(scope & (step == 3), 1, np.where(scope & (step == 4), 2,
                    np.where(~scope & (step == 2), 3, 9))))
    at = {(int(p), int(s)): k for k, (p, s) in enumerate(zip(d["parent"], d["spot"]))}
    runs, current = [], []
    for k in sorted(np.flatnonzero(sure).tolist(), key=lambda k: (int(d["parent"][k]), int(d["spot"][k]))):
        if current and d["parent"][k] == d["parent"][current[-1]] and d["spot"][k] == d["spot"][current[-1]] + 1:
            current.append(k)
        else:
            if current:
                runs.append(current)
            current = [k]
    if current:
        runs.append(current)
    n_runs.append(len(runs))
    sure_gold_total = int(gold[sure].sum())
    for run in runs:
        sizes.append(len(run))
        g = int(gold[run].sum())
        key = "all gold" if g == len(run) else "no gold" if g == 0 else "mixed"
        purity[key] += 1
        purity_chunks[key] += len(run)
    if sure_gold_total:
        richest_share.append(max(int(gold[run].sum()) for run in runs) / sure_gold_total)
    picks = {
        "the longest run": lambda run: (len(run), z[run].sum()),
        "the run with the highest summed value": lambda run: (z[run].sum(), len(run)),
        "the run with the highest mean value": lambda run: (z[run].mean(), len(run)),
        "the run that holds the highest chunk": lambda run: (z[run].max(), len(run)),
        "the run with the most chunks in scope on the combo's first step": lambda run: (int((cell[run] == 0).sum()), z[run].sum()),
        "with the gold in hand: the run with the most gold chunks": lambda run: (int(gold[run].sum()), len(run)),
    }
    base = np.lexsort((d["id_rank"], -z, np.where(sure, cell, 9), ~sure))
    a, b = run_order(base, d)
    row = orders.setdefault("the sure set by cell, then the rest (no runs)", [0, []])
    row[0] += int(a)
    row[1].append(b)
    for name, rule in picks.items():
        pick = max(runs, key=rule)
        row = rules.setdefault(name, [0, 0, 0])
        row[0] += len(pick)
        row[1] += int(gold[pick].sum())
        row[2] += 1
        p = int(d["parent"][pick[0]])
        outer = [at[(p, s)] for s in (int(d["spot"][pick[0]]) - 1, int(d["spot"][pick[-1]]) + 1) if (p, s) in at]
        outer = [k for k in outer if not sure[k]]
        row = ends.setdefault(name, [0, 0])
        row[0] += len(outer)
        row[1] += int(gold[outer].sum()) if outer else 0
        in_run = sorted(pick, key=lambda k: -z[k])
        used = set(in_run) | set(outer)
        order = in_run + outer + [k for k in base.tolist() if k not in used]
        a, b = run_order(order, d)
        row = orders.setdefault(f"{name} first, then the chunk above and the chunk under it, then the rest of the sure set", [0, []])
        row[0] += int(a)
        row[1].append(b)

total_runs = sum(purity.values())
print(f"runs a question: {np.median(n_runs):.0f} ({np.percentile(n_runs, 25):.0f}-{np.percentile(n_runs, 75):.0f}); chunks in a "
      f"run: {np.median(sizes):.0f} ({np.percentile(sizes, 25):.0f}-{np.percentile(sizes, 75):.0f}), mean {np.mean(sizes):.1f}")
print("runs by what they hold: " + ", ".join(f"{k}: {v} runs ({v / total_runs:.0%}), {purity_chunks[k]} chunks" for k, v in purity.items()))
print(f"with the gold in hand: the richest run holds {np.mean(richest_share):.0%} of the sure set's gold chunks (mean)")
print("\n== the run a rule picks: chunks in it (mean) | share of them gold | the chunks right above and under its ends, "
      "outside the sure set: a question, share gold ==")
for name, (chunks, golds, n) in rules.items():
    e = ends[name]
    print(f"  {chunks / n:4.1f} | {golds / max(chunks, 1):4.0%} | {e[0] / n:3.1f}, {e[1] / max(e[0], 1):4.0%}  {name}")
print("\n== orders: first chunk gold (of 100) | context_recall_id ==")
for name, (first, recall) in orders.items():
    print(f"  {first:3d} | {float(np.mean(recall)):.3f}  {name}")

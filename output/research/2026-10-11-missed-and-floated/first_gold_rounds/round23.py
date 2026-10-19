"""Round 23: inside the sure set (round 22), is a chunk gold more often when a pointer ties it to
another chunk of the sure set (right above or under it, a shared link, a shared conversation)?
And does a search that starts only from such tied chunks reach more gold? Inside the question's
product, the hundred; a chunk of the product is gold 6% of the time.

  1  the sure set's chunks by cell and by whether a pointer ties them to another sure chunk:
     chunks a question, share gold
  2  the chunks of the rest reached by a pointer from a TIED sure chunk, from a sure chunk that
     is not tied, and from two sure chunks that are tied to each other: chunks a question, share
     gold
  3  orders, first chunk gold (of 100) and context_recall_id (share of the cited records
     delivered inside 72,000 characters): the cells as they are; the tied chunks first inside
     every cell; the tied chunks of the sure set first, then what their pointers reach, then the
     rest of the sure set, then the rest."""
import pickle
import sys
from pathlib import Path

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

from explore import BUDGET, load, standing  # noqa: E402

HERE = Path(__file__).resolve().parent
data = load()
Q = data["questions"]
with open(HERE / "first_gold_signals_ties__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
for qid, d in Q.items():
    d.update(extra[qid])
CELLS = ("in scope, step 1", "in scope, step 2", "in scope, step 3", "outside, step 1")


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


def run(order, d):
    order = np.asarray(order, dtype=np.int64)
    fits = np.cumsum(d["length"][order]) <= BUDGET
    kept = order[:int(fits.sum()) if fits.all() else int(np.argmin(fits))]
    cited, have = set(d["cited_ids"]), set()
    for k in kept:
        have.update(d["records"][k])
    return bool(d["gold"][order[0]]), len(cited & have) / d["cites"]


one, two, three = {}, {}, {}
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
    talks = [set(t) for t in d["talks"]]
    linked = [set() for _ in range(m)]
    for a, b in d["share_a_link"].tolist():
        linked[a].add(b)
        linked[b].add(a)

    def pointers(k):
        p, s = int(d["parent"][k]), int(d["spot"][k])
        out = {at[(p, s + j)] for j in (-1, 1) if (p, s + j) in at}
        out |= linked[k]
        out |= {j for j in range(m) if j != k and talks[k] & talks[j]}
        return out

    points = {k: pointers(k) for k in range(m)}
    tied = np.array([sure[k] and any(sure[j] for j in points[k]) for k in range(m)])
    for k in np.flatnonzero(sure).tolist():
        row = one.setdefault((CELLS[int(cell[k])], "tied to another sure chunk" if tied[k] else "not tied"), [0, 0])
        row[0] += 1
        row[1] += int(gold[k])
        row = one.setdefault(("the whole sure set", "tied to another sure chunk" if tied[k] else "not tied"), [0, 0])
        row[0] += 1
        row[1] += int(gold[k])
    reached = {}
    for s in np.flatnonzero(sure).tolist():
        for k in points[s]:
            if not sure[k]:
                reached.setdefault(k, []).append(s)
    for k, froms in reached.items():
        labels = ["from any sure chunk"]
        labels.append("from a tied sure chunk" if any(tied[s] for s in froms) else "only from sure chunks that are not tied")
        if any(tied[s] and tied[t] and t in points[s] for s in froms for t in froms if s != t):
            labels.append("from two sure chunks that are tied to each other")
        if any(cell[s] == 0 and tied[s] for s in froms):
            labels.append("from a tied sure chunk on the combo's first step, in scope")
        for label in labels:
            row = two.setdefault(label, [0, 0])
            row[0] += 1
            row[1] += int(gold[k])
    # orders
    base = np.lexsort((d["id_rank"], -z, np.where(sure, cell, 9), ~sure))
    tied_first = np.lexsort((d["id_rank"], -z, ~tied, np.where(sure, cell, 9), ~sure))
    reach_mask = np.zeros(m, dtype=bool)
    for k, froms in reached.items():
        if any(tied[s] for s in froms):
            reach_mask[k] = True
    tier = np.where(sure & tied, 0, np.where(reach_mask, 1, np.where(sure, 2, 3)))
    searched = np.lexsort((d["id_rank"], -z, np.where(sure, cell, 9), tier))
    tier2 = np.where(sure & tied, 0, np.where(sure, 1, np.where(reach_mask, 2, 3)))
    searched2 = np.lexsort((d["id_rank"], -z, np.where(sure, cell, 9), tier2))
    for name, order in (("the cells as they are (sure set by cell, then the rest by both values)", base),
                        ("inside every cell the tied chunks first", tied_first),
                        ("the tied sure chunks, then what their pointers reach, then the rest of the sure set, then the rest", searched),
                        ("the tied sure chunks, then the rest of the sure set, then what the pointers reach, then the rest", searched2)):
        a, b = run(order, d)
        row = three.setdefault(name, [0, []])
        row[0] += int(a)
        row[1].append(b)

print("== 1: the sure set by cell and by pointer: chunks a question | share gold ==")
for (cell_name, label), (chunks, golds) in sorted(one.items()):
    print(f"  {chunks / count:5.1f} | {golds / max(chunks, 1):4.0%}  {cell_name}; {label}")
print("\n== 2: chunks of the rest reached by a pointer (above or under, a shared link, a shared conversation): chunks a "
      "question | share gold ==")
for label, (chunks, golds) in two.items():
    print(f"  {chunks / count:5.1f} | {golds / max(chunks, 1):4.0%}  {label}")
print("\n== 3: orders: first chunk gold (of 100) | context_recall_id ==")
for name, (first, recall) in three.items():
    print(f"  {first:3d} | {float(np.mean(recall)):.3f}  {name}")

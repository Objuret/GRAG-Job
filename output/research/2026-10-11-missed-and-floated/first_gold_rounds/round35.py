"""Round 35, for his 2026-10-12 goal "solve this": the order that held through the arm's delivery
(the combo with the question without the product's name on the chunk side, the scope gauged
after it, in-scope chunks first inside a step: 48 of 100 and 0.547) and what can still be put
into it without a number of mine. Inside the question's product, the hundred.

Inside a step, what goes first (each a yes or no, no weight): in scope; right above or under a
chunk of the combo's first step (his pointer); both in that order; the other order. The scope
gauged from the combo's first step alone or from its first two. Chunks on the same step and the
same yes and no by their two values added.
Printed: the first chunk gold (of 100), context_recall_id (share of the cited records delivered
inside 72,000 characters), gold chunks in the first 15 (of 10)."""
import sys

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

from explore import BUDGET, load, standing  # noqa: E402

Q = load()["questions"]


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
    return bool(d["gold"][order[0]]), len(cited & have) / d["cites"], int(d["gold"][order[:15]].sum())


rows = {}
for d in Q.values():
    D, T = np.asarray(d["question_bare"], dtype=np.float64), np.asarray(d["tags"], dtype=np.float64)
    m = D.size
    lD, lT = WK.levels(D, 5), WK.levels(T, 5)
    step = (lD + lT).astype(np.float64)
    z = standing(D) + standing(T)
    at = {(int(p), int(s)): k for k, (p, s) in enumerate(zip(d["parent"], d["spot"]))}
    top = step == step.min()
    beside = np.zeros(m, dtype=bool)
    for k in np.flatnonzero(top).tolist():
        p, s = int(d["parent"][k]), int(d["spot"][k])
        for j in (-1, 1):
            if (p, s + j) in at:
                beside[at[(p, s + j)]] = True
    scopes = {"its first two steps": majority(step <= 3 if (step <= 3).any() else top, d["parent"]),
              "its first step": majority(top, d["parent"])}
    tries = {"no scope below the product": (step,)}
    for name, scope in scopes.items():
        tries[f"in scope first inside a step (scope from {name})"] = (~scope, step)
        tries[f"in scope, then beside a first-step chunk (scope from {name})"] = (~beside, ~scope, step)
        tries[f"beside a first-step chunk, then in scope (scope from {name})"] = (~scope, ~beside, step)
    tries["beside a first-step chunk first inside a step, no scope"] = (~beside, step)
    for name, keys in tries.items():
        order = np.lexsort((d["id_rank"], -z, *keys))
        a, b, c = run(order, d)
        row = rows.setdefault(name, [0, [], []])
        row[0] += int(a)
        row[1].append(b)
        row[2].append(c)
print("first chunk gold (of 100) | context_recall_id | gold chunks in the first 15 (of 10)")
for name, (first, recall, top15) in rows.items():
    print(f"  {first:3d} | {np.mean(recall):.3f} | {np.mean(top15):.2f}  {name}")

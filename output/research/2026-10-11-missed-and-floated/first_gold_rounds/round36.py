"""Round 36, for his 2026-10-12 goal "solve this": the order of round 35 (the combo with the question
without the product's name on the chunk side, the scope gauged after it, in-scope chunks first
inside a step) with the TAGS' side made in different ways: from the first call's query tags (a
chunk's closest tag to any of them; their mean), from the question itself without the name (a
chunk's closest tag to the question's own vector, no first call), and from both. Inside the
question's product, the hundred. Printed: the first chunk gold (of 100), context_recall_id
(share of the cited records delivered inside 72,000 characters)."""
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
    return bool(d["gold"][order[0]]), len(cited & have) / d["cites"]


rows = {}
for d in Q.values():
    D = np.asarray(d["question_bare"], dtype=np.float64)
    sides = {
        "the first call's query tags, a chunk's closest tag to any of them": np.asarray(d["tags"], dtype=np.float64),
        "the first call's query tags, the mean over them": d["fit"].mean(axis=0).astype(np.float64),
        "the question without the name against the chunk's tags (no first call)": np.asarray(d["question_bare_tags"], dtype=np.float64),
        "the question as asked against the chunk's tags (no first call)": np.asarray(d["question_tags"], dtype=np.float64),
        "the query tags and the question's own reading, standings added": standing(d["tags"]) + standing(d["question_bare_tags"]),
    }
    for name, T in sides.items():
        for scoped in (False, True):
            step = (WK.levels(D, 5) + WK.levels(T, 5)).astype(np.float64)
            z = standing(D) + standing(T)
            scope = majority(step <= 3 if (step <= 3).any() else step == step.min(), d["parent"])
            keys = (d["id_rank"], -z, ~scope, step) if scoped else (d["id_rank"], -z, step)
            a, b = run(np.lexsort(keys), d)
            row = rows.setdefault((name, scoped), [0, []])
            row[0] += int(a)
            row[1].append(b)
print("first chunk gold (of 100) | context_recall_id")
for (name, scoped), (first, recall) in rows.items():
    print(f"  {first:3d} | {np.mean(recall):.3f}  tags' side: {name}; {'in-scope chunks first inside a step' if scoped else 'no scope below the product'}")

"""Round 28: inside the sure set (round 22: about 14 chunks a question, 29% gold) nothing of the layer
tells the gold chunks from the others (rounds 23 to 27). The one reading that does not come from
the descriptions or the tags is the single posts inside a chunk (the vector baseline's record
vectors) against the question read without the product's name. Is it a decider inside the sure
set? Inside the question's product, the hundred.

Printed: the sure set ordered by different deciders, the rest after it by the same decider:
first chunk gold (of 100), context_recall_id (share of the cited records delivered inside 72,000
characters), and the share of gold among the sure set's first three and first five chunks
(beside the sure set's own 29%)."""
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
with open(HERE / "first_gold_signals_more__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
for qid, d in Q.items():
    d.update(extra[qid])
KEPT = Path(r"C:\Coding\exjobbet\GRAG-Job\output\embed_local\20261007_rev113abe4acafa_float32")
corpus = np.load(KEPT / "corpus_passage.npz", allow_pickle=True)
row_of = {str(r): k for k, r in enumerate(corpus["ids"])}
matrix = np.asarray(corpus["matrix"], dtype=np.float32)
matrix = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
for d in Q.values():
    rows = [np.array([row_of[r] for r in recs if r in row_of], dtype=np.int64) for recs in d["records"]]
    near = [matrix[r] @ d["bare_vector"].astype(np.float32) if r.size else np.array([-1.], dtype=np.float32) for r in rows]
    d["record_top2_bare"] = np.array([float(np.sort(x)[-2:].mean()) for x in near])
    d["record_best_bare"] = np.array([float(x.max()) for x in near])


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
    D, T = np.asarray(d["description"], dtype=np.float64), np.asarray(d["tags"], dtype=np.float64)
    gold = d["gold"]
    step = WK.levels(D, 5) + WK.levels(T, 5)
    hits = step <= 3 if (step <= 3).any() else step == step.min()
    scope = majority(hits, d["parent"])
    sure = (scope & (step <= 4)) | (~scope & (step == 2))
    cell = np.where(scope & (step == 2), 0, np.where(scope & (step == 3), 1, np.where(scope & (step == 4), 2,
                    np.where(~scope & (step == 2), 3, 9))))
    deciders = {
        "the cells, both values added inside a cell (the combo and scope as they are)": (np.where(sure, cell, 9), standing(D) + standing(T)),
        "the two values added, no cells": (None, standing(D) + standing(T)),
        "the two closest posts against the question without the name": (None, d["record_top2_bare"]),
        "the closest post against the question without the name": (None, d["record_best_bare"]),
        "the description against the question without the name": (None, d["question_bare"]),
        "posts + description, both against the question without the name": (None, standing(d["record_top2_bare"]) + standing(d["question_bare"])),
        "posts + description + the two values": (None, standing(d["record_top2_bare"]) + standing(d["question_bare"]) + standing(D) + standing(T)),
        "the cells, the two closest posts inside a cell": (np.where(sure, cell, 9), d["record_top2_bare"]),
        "the cells, posts + description inside a cell": (np.where(sure, cell, 9), standing(d["record_top2_bare"]) + standing(d["question_bare"])),
    }
    for name, (key, value) in deciders.items():
        value = np.asarray(value, dtype=np.float64)
        keys = (d["id_rank"], -value) if key is None else (d["id_rank"], -value, key)
        inner = np.lexsort(keys)
        order = np.concatenate([[k for k in inner if sure[k]], [k for k in inner if not sure[k]]]).astype(np.int64)
        a, b = run(order, d)
        row = rows.setdefault(name, [0, [], 0, 0, 0, 0])
        row[0] += int(a)
        row[1].append(b)
        top = [k for k in inner if sure[k]]
        row[2] += int(gold[top[:3]].sum())
        row[3] += len(top[:3])
        row[4] += int(gold[top[:5]].sum())
        row[5] += len(top[:5])
    # no sure set at all: the whole product by the posts and the description
    for name, value in (("no sure set: the whole product by posts + description against the question without the name",
                         standing(d["record_top2_bare"]) + standing(d["question_bare"])),):
        order = np.lexsort((d["id_rank"], -value))
        a, b = run(order, d)
        row = rows.setdefault(name, [0, [], 0, 0, 0, 0])
        row[0] += int(a)
        row[1].append(b)
        row[2] += int(gold[order[:3]].sum())
        row[3] += 3
        row[4] += int(gold[order[:5]].sum())
        row[5] += 5

print("first chunk gold (of 100) | context_recall_id | share gold among the first three | among the first five")
for name, (first, recall, g3, n3, g5, n5) in rows.items():
    print(f"  {first:3d} | {float(np.mean(recall)):.3f} | {g3 / max(n3, 1):4.0%} | {g5 / max(n5, 1):4.0%}  the sure set ordered by: {name}"
          if not name.startswith("no sure set") else
          f"  {first:3d} | {float(np.mean(recall)):.3f} | {g3 / max(n3, 1):4.0%} | {g5 / max(n5, 1):4.0%}  {name}")

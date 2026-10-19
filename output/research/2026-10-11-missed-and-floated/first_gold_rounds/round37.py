"""Round 37, under his 2026-10-12 goal "solve this", after the combo step was built (the hundred
through the arm: context_recall_id 0.550, first chunk gold 48): the gold both sides touch still
stands among look-alikes. A look-alike is the same kind of conversation about another thing, and
the thing has a name. Do the graph's own tags that stand in the question WORD FOR WORD tell the
gold from the look-alikes? Inside the question's product, the hundred.

  1  the tags of the product whose name stands in the question (the product's own name aside),
     by how many words the tag has: questions that have one, chunks that carry one, share gold
  2  the same counted only inside the group both sides touch (first two clusters of the chunk
     side, a picked tag on the chunk)
  3  the combo order (the question without the name on the chunk side, the tags, the scope) with
     one more yes or no inside a step: the chunk carries such a tag, of two words or more; of
     three or more; put before the scope and after it. First chunk gold (of 100) and
     context_recall_id (share of the cited records delivered inside 72,000 characters)."""
import pickle
import sys
from pathlib import Path

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

from explore import BUDGET, load, standing  # noqa: E402

HERE = Path(__file__).resolve().parent
Q = load()["questions"]
with open(HERE / "first_gold_signals_tags__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
for qid, d in Q.items():
    d.update(extra[qid])


def run(order, d):
    order = np.asarray(order, dtype=np.int64)
    fits = np.cumsum(d["length"][order]) <= BUDGET
    kept = order[:int(fits.sum()) if fits.all() else int(np.argmin(fits))]
    cited, have = set(d["cited_ids"]), set()
    for k in kept:
        have.update(d["records"][k])
    return bool(d["gold"][order[0]]), len(cited & have) / d["cites"]


BANDS = (("one word", 1, 1), ("two words", 2, 2), ("three words or more", 3, 99), ("two words or more", 2, 99))
one = {name: [0, 0, 0] for name, _, _ in BANDS}      # questions with one, chunks carrying, gold among them
two = {name: [0, 0] for name, _, _ in BANDS}
orders = {}
group_total = [0, 0]
for d in Q.values():
    gold, m = d["gold"], d["gold"].size
    longest = d["named_longest"]                       # per chunk: the longest named tag it carries, in words (0: none)
    D, T = np.asarray(d["question_bare"], dtype=np.float64), np.asarray(d["tags"], dtype=np.float64)
    lD, lT = WK.levels(D, 5), WK.levels(T, 5)
    step = (lD + lT).astype(np.float64)
    z = standing(D) + standing(T)
    hits = step <= 3 if (step <= 3).any() else step == step.min()
    ids = np.unique(d["parent"])
    held = np.array([int(hits[d["parent"] == a].sum()) for a in ids])
    by = np.lexsort((ids, -held))
    total, last = 0, None
    for at in by:
        total += int(held[at])
        last = int(held[at])
        if total * 2 > int(held.sum()):
            break
    scope = np.isin(d["parent"], ids[held >= last])
    fit = d["tag_fit"].astype(np.float64)
    kth = np.sort(fit, axis=1)[:, ::-1][:, min(5, fit.shape[1]) - 1]
    picked = (fit >= kth[:, None] - 1e-12).any(axis=0)
    by_tags = np.zeros(m, dtype=bool)
    by_tags[d["edge_chunk"][picked[d["edge_tag"]]]] = True
    both = by_tags & (WK.levels(np.asarray(d["description"], dtype=np.float64), 5) <= 2)
    group_total[0] += int(both.sum())
    group_total[1] += int(gold[both].sum())
    for name, low, high in BANDS:
        carries = (longest >= low) & (longest <= high) if high < 99 else longest >= low
        one[name][0] += int(carries.any())
        one[name][1] += int(carries.sum())
        one[name][2] += int(gold[carries].sum())
        two[name][0] += int((carries & both).sum())
        two[name][1] += int(gold[carries & both].sum())
    named2, named3 = longest >= 2, longest >= 3
    tries = {
        "the combo order as built (step, in scope, the two values)": (-z, ~scope, step),
        "inside a step: a named tag of two words or more, then in scope": (-z, ~scope, ~named2, step),
        "inside a step: in scope, then a named tag of two words or more": (-z, ~named2, ~scope, step),
        "inside a step: a named tag of three words or more, then in scope": (-z, ~scope, ~named3, step),
        "chunks with a named tag of two words or more before every step": (-z, ~scope, step, ~named2),
        "chunks with a named tag of three words or more before every step": (-z, ~scope, step, ~named3),
    }
    for name, keys in tries.items():
        a, b = run(np.lexsort((d["id_rank"], *keys)), d)
        row = orders.setdefault(name, [0, []])
        row[0] += int(a)
        row[1].append(b)
count = len(Q)
print("== 1: the product's tags whose name stands in the question word for word: questions that have one | chunks carrying "
      "one, a question | share of those chunks gold (a chunk of the product: 6%) ==")
for name, (questions, chunks, golds) in one.items():
    print(f"  {questions:3d} | {chunks / count:5.1f} | {golds / max(chunks, 1):4.0%}  tags of {name}")
print(f"\n== 2: inside the group both sides touch ({group_total[0] / count:.1f} chunks a question, "
      f"{group_total[1] / group_total[0]:.0%} gold): chunks carrying one, a question | share gold ==")
for name, (chunks, golds) in two.items():
    print(f"  {chunks / count:5.1f} | {golds / max(chunks, 1):4.0%}  tags of {name}")
print("\n== 3: first chunk gold (of 100) | context_recall_id ==")
for name, (first, recall) in orders.items():
    print(f"  {first:3d} | {np.mean(recall):.3f}  {name}")

"""Round 47, under his 2026-10-12 goal "solve this": on 34 of 100 questions a meeting stands first in
the combo order, and on 15 of those it holds no cited record (round 46), while meetings are 5%
of the cited records. Is a kind of chunk put first more often than it is gold, and does the
number of tags a chunk carries do it (his 2026-10-05 "i dont think its a good idea to let
'amount of tags' make a chunk more important": the tags' side takes a chunk's CLOSEST tag, so a
chunk with more tags has more tries)? The hundred, inside the question's product, numbers only.

  by kind of chunk: chunks a question | share gold | tags a chunk, the middle | description
  characters, the middle (where the table has them) | first of the description side, of the tags'
  side, of the combo order (questions) | of those, gold
  and by the number of tags a chunk carries (thirds): share gold | share of the tags' side's first cluster
"""
import pickle
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

from explore import load, standing  # noqa: E402

HERE = Path(__file__).resolve().parent
T = load()
Q, KINDS = T["questions"], T["kind_names"]
with open(HERE / "first_gold_signals_tags__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
count, gold, tags_n = Counter(), Counter(), defaultdict(list)
first = {side: Counter() for side in ("description", "tags", "combo")}
first_gold = {side: Counter() for side in first}
thirds = defaultdict(lambda: [0, 0, 0, 0])
for qid, d in Q.items():
    d.update(extra[qid])
    m = d["gold"].size
    kind = [KINDS[x] for x in d["kind"]]
    D, Tg = np.asarray(d["question_bare"], dtype=np.float64), np.asarray(d["tags"], dtype=np.float64)
    lD, lT = WK.levels(D, 5), WK.levels(Tg, 5)
    step = (lD + lT).astype(np.float64)
    z = standing(D) + standing(Tg)
    hits = step <= 3 if (step <= 3).any() else step == step.min()
    ids = np.unique(d["parent"])
    held = np.array([int(hits[d["parent"] == a].sum()) for a in ids])
    total, last = 0, None
    for at in np.lexsort((ids, -held)):
        total += int(held[at])
        last = int(held[at])
        if total * 2 > int(held.sum()):
            break
    scope = np.isin(d["parent"], ids[held >= last])
    tops = {"description": int(np.lexsort((d["id_rank"], -D))[0]), "tags": int(np.lexsort((d["id_rank"], -Tg))[0]),
            "combo": int(np.lexsort((d["id_rank"], -z, ~scope, step))[0])}
    for side, k in tops.items():
        first[side][kind[k]] += 1
        first_gold[side][kind[k]] += bool(d["gold"][k])
    n_tags = np.asarray(d["n_tags"])
    cuts = np.quantile(n_tags, [1 / 3, 2 / 3])
    for k in range(m):
        count[kind[k]] += 1
        gold[kind[k]] += bool(d["gold"][k])
        tags_n[kind[k]].append(int(n_tags[k]))
        third = "fewest tags" if n_tags[k] <= cuts[0] else "most tags" if n_tags[k] > cuts[1] else "in between"
        row = thirds[third]
        row[0] += 1
        row[1] += bool(d["gold"][k])
        row[2] += int(lT[k] == 1)
        row[3] += int(n_tags[k])
n = len(Q)
print("kind of chunk: chunks a question | share gold | tags a chunk (middle) | first of the description side, the tags' side, "
      "the combo order: questions (of them gold)")
for name in sorted(count, key=lambda k: -count[k]):
    row = " ; ".join(f"{first[s][name]:3d} ({first_gold[s][name]:2d})" for s in ("description", "tags", "combo"))
    print(f"  {count[name] / n:6.1f} | {gold[name] / count[name]:4.0%} | {np.median(tags_n[name]):4.0f} | {row}  {name}")
print("\nby the number of tags a chunk carries: chunks a question | tags, the mean | share gold | share in the first cluster of the tags' side")
for third in ("fewest tags", "in between", "most tags"):
    c, g, f, t = thirds[third]
    print(f"  {c / n:6.1f} | {t / c:5.1f} | {g / c:4.0%} | {f / c:4.0%}  {third}")

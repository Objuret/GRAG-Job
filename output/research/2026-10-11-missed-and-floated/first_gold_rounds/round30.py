"""Round 30, his 2026-10-12 "you say we actually get about 96% gold in max/total.. that MEANS, the
actual chunks ARE touched, just not as well as the other chosen ones ... we DO have connections
to them". (The 0.96 he was told on 2026-10-10 was the most the 72,000 can hold when the gold
chunks are put first with the gold in hand, on the ten; it was not a count of what the tags and
descriptions touch.) Here is what they touch, inside the question's product, the hundred: how
much of a question's gold chunks is reached as more and more of the product's chunks are taken,
by each route and by the tags' pick.

  1  the share of the gold chunks among the first 15, 30, 50, 80, 120 chunks of a route (the
     product has about 160; a blind draw of that many chunks holds the same share of the gold as
     of the product)
  2  the tags' pick: a chunk is touched when it carries one of the tags a query tag picks (its
     5, 10, 20, 50 nearest of the product's tags; and every tag at the graph's same-thing
     level): chunks touched a question, share of the gold chunks touched
  3  the gold chunks by how the two sides place them: the description's cluster (1 the nearest
     to 5) against whether a picked tag (five nearest) sits on the chunk"""
import pickle
import sys
from pathlib import Path

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

from explore import load, standing  # noqa: E402

HERE = Path(__file__).resolve().parent
SAME = 0.8541
data = load()
Q = data["questions"]
with open(HERE / "first_gold_signals_tags__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
for qid, d in Q.items():
    d.update(extra[qid])
DEPTHS = (15, 30, 50, 80, 120)
ROUTES = {
    "the tags (a chunk's closest tag to any query tag)": lambda d: d["tags"],
    "the chunk descriptions against the query description": lambda d: d["description"],
    "the chunk descriptions against the question": lambda d: d["question"],
    "the three added": lambda d: standing(d["tags"]) + standing(d["description"]) + standing(d["question"]),
}
curve = {name: {k: [] for k in DEPTHS} for name in ROUTES}
blind = {k: [] for k in DEPTHS}
for d in Q.values():
    gold = d["gold"]
    for k in DEPTHS:
        blind[k].append(min(k, gold.size) / gold.size)
    for name, make in ROUTES.items():
        order = np.lexsort((d["id_rank"], -np.asarray(make(d), dtype=np.float64)))
        for k in DEPTHS:
            curve[name][k].append(float(gold[order[:k]].sum() / gold.sum()))
print("== 1: share of a question's gold chunks among the first chunks of a route (the product has about 160) ==")
print("  first chunks:                " + "   ".join(f"{k:4d}" for k in DEPTHS))
print("  a blind draw of that many:   " + "   ".join(f"{np.mean(blind[k]):4.0%}" for k in DEPTHS))
for name in ROUTES:
    print("  " + "   ".join(f"{np.mean(curve[name][k]):4.0%}" for k in DEPTHS) + f"   {name}")

picks = {}
grid = np.zeros((5, 2))
total_gold = 0
for d in Q.values():
    gold = d["gold"]
    m = gold.size
    fit = d["tag_fit"].astype(np.float64)
    ec, et = d["edge_chunk"], d["edge_tag"]
    ranked = np.sort(fit, axis=1)[:, ::-1]
    for label, k in (("its 5 nearest of the product's tags", 5), ("its 10 nearest", 10), ("its 20 nearest", 20),
                     ("its 50 nearest", 50)):
        kth = ranked[:, min(k, fit.shape[1]) - 1]
        picked = (fit >= kth[:, None] - 1e-12).any(axis=0)
        touched = np.zeros(m, dtype=bool)
        touched[ec[picked[et]]] = True
        row = picks.setdefault(label, [[], []])
        row[0].append(int(touched.sum()))
        row[1].append(float(gold[touched].sum() / gold.sum()))
        if k == 5:
            level = WK.levels(np.asarray(d["description"], dtype=np.float64), 5)
            for a in range(5):
                grid[a, 0] += int((gold & (level == a + 1) & touched).sum())
                grid[a, 1] += int((gold & (level == a + 1) & ~touched).sum())
            total_gold += int(gold.sum())
    same = (fit.max(axis=0) >= SAME)
    touched = np.zeros(m, dtype=bool)
    touched[ec[same[et]]] = True
    row = picks.setdefault("every tag that is the same thing as a query tag", [[], []])
    row[0].append(int(touched.sum()))
    row[1].append(float(gold[touched].sum() / gold.sum()))
print("\n== 2: the tags' pick: chunks of the product touched a question | share of the product | share of the gold chunks touched ==")
for label, (chunks, share) in picks.items():
    print(f"  {np.mean(chunks):5.1f} | {np.mean(chunks) / 160:4.0%} | {np.mean(share):4.0%}  a query tag picks {label}"
          if not label.startswith("every") else
          f"  {np.mean(chunks):5.1f} | {np.mean(chunks) / 160:4.0%} | {np.mean(share):4.0%}  {label}")
print("\n== 3: the hundred's gold chunks by the description's cluster and by whether a picked tag (five nearest) sits on "
      "them: share of all gold chunks ==")
print("  description cluster:      1 (nearest)      2      3      4      5      all")
print("  a picked tag on it:    " + "   ".join(f"{grid[a, 0] / total_gold:5.0%}" for a in range(5)) + f"   {grid[:, 0].sum() / total_gold:5.0%}")
print("  no picked tag on it:   " + "   ".join(f"{grid[a, 1] / total_gold:5.0%}" for a in range(5)) + f"   {grid[:, 1].sum() / total_gold:5.0%}")

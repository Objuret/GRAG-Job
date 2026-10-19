"""Round 31, his 2026-10-12 "the actual chunks ARE touched ... we DO have connections to them": the
product's chunks by which side touches them. Tags: the chunk carries a tag a query tag picks
(its five nearest of the product's tags). Descriptions: the chunk is in the first two of five
clusters of nearness to the query description. Inside the question's product, the hundred.
Printed per group: chunks a question, the share of them that is gold, the share of all the
question's gold chunks that sits in the group, and where the group's gold chunks stand in the
order of the three routes added (the middle place)."""
import pickle
import sys
from pathlib import Path

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

from explore import load, standing  # noqa: E402

HERE = Path(__file__).resolve().parent
Q = load()["questions"]
with open(HERE / "first_gold_signals_tags__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
for qid, d in Q.items():
    d.update(extra[qid])
GROUPS = ("touched by both", "by the tags only", "by the descriptions only", "by neither")
rows = {g: [0, 0, []] for g in GROUPS}
total_gold = 0
places = {"in the first 15 (what fits)": 0, "places 16 to 30": 0, "places 31 to 50": 0, "places 51 to 80": 0, "further down": 0}
for d in Q.values():
    gold, m = d["gold"], d["gold"].size
    fit = d["tag_fit"].astype(np.float64)
    kth = np.sort(fit, axis=1)[:, ::-1][:, min(5, fit.shape[1]) - 1]
    picked = (fit >= kth[:, None] - 1e-12).any(axis=0)
    by_tags = np.zeros(m, dtype=bool)
    by_tags[d["edge_chunk"][picked[d["edge_tag"]]]] = True
    by_desc = WK.levels(np.asarray(d["description"], dtype=np.float64), 5) <= 2
    plain = standing(d["tags"]) + standing(d["description"]) + standing(d["question"])
    order = np.lexsort((d["id_rank"], -plain))
    place = np.empty(m, dtype=np.int64)
    place[order] = np.arange(1, m + 1)
    total_gold += int(gold.sum())
    for name, mask in ((GROUPS[0], by_tags & by_desc), (GROUPS[1], by_tags & ~by_desc), (GROUPS[2], ~by_tags & by_desc),
                       (GROUPS[3], ~by_tags & ~by_desc)):
        rows[name][0] += int(mask.sum())
        rows[name][1] += int(gold[mask].sum())
        rows[name][2] += place[mask & gold].tolist()
    for p in place[gold].tolist():
        key = ("in the first 15 (what fits)" if p <= 15 else "places 16 to 30" if p <= 30 else "places 31 to 50" if p <= 50
               else "places 51 to 80" if p <= 80 else "further down")
        places[key] += 1
count = len(Q)
print("== chunks a question | share of them gold | share of the question's gold chunks in the group | place of the group's gold "
      "chunks in the order of the three routes added, the middle (quarters) ==")
for name, (chunks, golds, where) in rows.items():
    print(f"  {chunks / count:5.1f} | {golds / chunks:4.0%} | {golds / total_gold:4.0%} | {np.median(where):.0f} "
          f"({np.percentile(where, 25):.0f}-{np.percentile(where, 75):.0f})  {name}")
print("\n== where a question's gold chunks stand in the order of the three routes added (of 10.0 a question) ==")
for key, value in places.items():
    print(f"  {value / count:4.1f} ({value / total_gold:.0%})  {key}")

"""Round 18, his 2026-10-12 "the combo should fucking work": the chunk descriptions and the tags each
cut into five clusters (`v4_walk.levels`, 1 the nearest), inside the question's product, the
hundred. Every chunk has a level from the descriptions and a level from the tags, so the two
clouds overlap step by step (his 2026-10-10 "overlapping clouds for each step").

Printed: the grid, description level by tags level: chunks a question in the cell and what share
of them is gold (a chunk of the product is gold 6% of the time). Then orders made of the two
levels with no sum of values: the description level first and the tags level inside it; the
other way round; the two levels added; the worse of the two; each with the first chunk gold (of
100) and context_recall_id (share of the cited records delivered inside 72,000 characters).
Once with the tags read as the chunk's closest tag to any query tag (the arm's), once as the mean
over the query tags."""
import sys

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

from explore import load, measure, standing  # noqa: E402

data = load()
Q = data["questions"]
LEVELS = 5
TAGS = {"the chunk's closest tag to any query tag": lambda d: d["tags"],
        "the mean over the query tags": lambda d: d["fit"].mean(axis=0)}

for tags_name, tags_of in TAGS.items():
    cells = np.zeros((LEVELS + 1, LEVELS + 1, 2))
    first, recall = {}, {}
    for d in Q.values():
        D, T = np.asarray(d["description"], dtype=np.float64), np.asarray(tags_of(d), dtype=np.float64)
        lD, lT = WK.levels(D, LEVELS), WK.levels(T, LEVELS)
        for a in range(1, LEVELS + 1):
            for b in range(1, LEVELS + 1):
                cell = (lD == a) & (lT == b)
                cells[a, b, 0] += int(cell.sum())
                cells[a, b, 1] += int(d["gold"][cell].sum())
        zD, zT = standing(D), standing(T)
        small = (zD + zT) / 1e3                      # only to order chunks that share both levels
        orders = {
            "descriptions + tags, standings added (no levels)": zD + zT,
            "the description level first, the tags level inside it": -(lD * 10. + lT) + small,
            "the tags level first, the description level inside it": -(lT * 10. + lD) + small,
            "the two levels added (the overlap step by step)": -(lD + lT).astype(float) + small,
            "the worse of the two levels, then the better": -(np.maximum(lD, lT) * 10. + np.minimum(lD, lT)) + small,
            "the better of the two levels, then the worse": -(np.minimum(lD, lT) * 10. + np.maximum(lD, lT)) + small,
        }
        for name, score in orders.items():
            got = measure(score, d)
            first[name] = first.get(name, 0) + int(got[0])
            recall.setdefault(name, []).append(got[2])
    print(f"\n==== the tags read as: {tags_name} ====")
    print("  chunks a question | share of them gold; rows: description level 1 (nearest) to 5, columns: tags level 1 to 5")
    for a in range(1, LEVELS + 1):
        row = []
        for b in range(1, LEVELS + 1):
            chunks, gold = cells[a, b]
            row.append(f"{chunks / len(Q):5.1f} | {gold / chunks:4.0%}" if chunks else "  0.0 |    -")
        print(f"  description level {a}:   " + "     ".join(row))
    whole_d = [(cells[a, :, 0].sum(), cells[a, :, 1].sum()) for a in range(1, LEVELS + 1)]
    whole_t = [(cells[:, b, 0].sum(), cells[:, b, 1].sum()) for b in range(1, LEVELS + 1)]
    print("  a description level alone: " + ", ".join(f"level {k + 1}: {c / len(Q):.1f} chunks, {g / c:.0%} gold" for k, (c, g) in enumerate(whole_d)))
    print("  a tags level alone:        " + ", ".join(f"level {k + 1}: {c / len(Q):.1f} chunks, {g / c:.0%} gold" for k, (c, g) in enumerate(whole_t)))
    print("  == the first chunk is gold (of 100) | context_recall_id ==")
    for name in first:
        print(f"    {first[name]:3d} | {float(np.mean(recall[name])):.3f}  {name}")

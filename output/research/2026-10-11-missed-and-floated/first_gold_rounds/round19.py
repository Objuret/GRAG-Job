"""Round 19, his 2026-10-12 "the combo should fucking work", one step on from round 18: the chunk
cloud made three ways (the chunk descriptions against the query description; against the
question without the product's name; the two added), each overlapped with the tags' cloud (the
chunk's closest tag to any query tag), five clusters each (`v4_walk.levels`), inside the
question's product, the hundred.

Printed per chunk cloud: the gold share where both are in their first cluster, where one is in
its first and the other in its second, where both are in their second, and everywhere else,
with the chunks a question in each; the first chunk gold (of 100) and context_recall_id for the
cloud in its own order, the cloud ordered by the tags, and the two levels added."""
import sys

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

from explore import load, measure, standing  # noqa: E402

data = load()
Q = data["questions"]
CLOUDS = {
    "the chunk descriptions against the query description": lambda d: np.asarray(d["description"], dtype=np.float64),
    "the chunk descriptions against the question without the product's name": lambda d: np.asarray(d["question_bare"], dtype=np.float64),
    "both of those added": lambda d: standing(d["description"]) + standing(d["question_bare"]),
}
for name, make in CLOUDS.items():
    cells = {"both in their first cluster": [0, 0], "one in its first, the other in its second": [0, 0],
             "both in their second": [0, 0], "everywhere else": [0, 0]}
    first, recall = {}, {}
    for d in Q.values():
        D, T = make(d), np.asarray(d["tags"], dtype=np.float64)
        lD, lT = WK.levels(D, 5), WK.levels(T, 5)
        where = {"both in their first cluster": (lD == 1) & (lT == 1),
                 "one in its first, the other in its second": ((lD == 1) & (lT == 2)) | ((lD == 2) & (lT == 1)),
                 "both in their second": (lD == 2) & (lT == 2)}
        where["everywhere else"] = ~(where["both in their first cluster"] | where["one in its first, the other in its second"]
                                     | where["both in their second"])
        for key, mask in where.items():
            cells[key][0] += int(mask.sum())
            cells[key][1] += int(d["gold"][mask].sum())
        zD, zT = standing(D), standing(T)
        orders = {
            "the chunk cloud's own order": zD,
            "the chunk cloud first, ordered by the tags; then the rest by its own order": np.where(lD == 1, 1e3 + zT, zD),
            "the two levels added, chunks on the same step by both values added": -(lD + lT).astype(float) + (zD + zT) / 1e3,
            "both values added, no levels": zD + zT,
        }
        for key, score in orders.items():
            got = measure(score, d)
            first[key] = first.get(key, 0) + int(got[0])
            recall.setdefault(key, []).append(got[2])
    print(f"\n==== the chunk cloud from: {name} ====")
    for key, (chunks, gold) in cells.items():
        print(f"  {key}: {chunks / len(Q):.1f} chunks a question, {gold / max(chunks, 1):.0%} of them gold")
    print("  == the first chunk is gold (of 100) | context_recall_id ==")
    for key in first:
        print(f"    {first[key]:3d} | {float(np.mean(recall[key])):.3f}  {key}")

"""Round 15, his 2026-10-12 "No I literally meant the one above or under it. Pointer-based": for the
top cluster (the first of five clusters of a nearness, `v4_walk.levels`), every chunk of it
brings the chunk right above it and the chunk right under it in its parent (the place the
graph keeps for a chunk in its channel or file). Inside the question's product, the hundred.

Printed: the cluster, the chunks above and under that are not already in it, and both together:
chunks, characters, what share of the question's gold chunks they hold beside what share of the
product's chunks they are, and how many of them are gold. Then context_recall_id (share of the
cited records delivered inside 72,000 characters) for the cluster as it is, the cluster followed
by the chunks above and under, and each cluster chunk followed at once by its own two."""
import sys

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

from explore import BUDGET, load, measure, standing  # noqa: E402

data = load()
Q = data["questions"]
CLUSTERS = 5
KINDS = {
    "the three routes added": lambda d: standing(d["tags"]) + standing(d["description"]) + standing(d["question"]),
    "the tags (the chunk's closest tag to a query tag)": lambda d: d["tags"],
    "the description against the query description": lambda d: d["description"],
}


def delivered_recall(order, d):
    order = np.asarray(order, dtype=np.int64)
    fits = np.cumsum(d["length"][order]) <= BUDGET
    kept = order[:int(fits.sum()) if fits.all() else int(np.argmin(fits))]
    cited, have = set(d["cited_ids"]), set()
    for k in kept:
        have.update(d["records"][k])
    return len(cited & have) / d["cites"], kept


for name, make in KINDS.items():
    facts = {key: [] for key in ("cluster chunks", "cluster chars", "cluster gold share", "cluster product share",
                                 "cluster gold chunks", "added chunks", "added chars", "added gold share",
                                 "added product share", "added gold chunks", "both chunks", "both chars")}
    recall = {key: [] for key in ("the three routes added, as they are", "the cluster first, then the rest",
                                  "the cluster, then the chunks above and under, then the rest",
                                  "each cluster chunk followed at once by the one above and the one under, then the rest")}
    first_gold = {key: 0 for key in recall}
    for d in Q.values():
        plain = KINDS["the three routes added"](d)
        value = make(d)
        cluster = WK.levels(np.asarray(value, dtype=np.float64), CLUSTERS) == 1
        at = {(int(p), int(s)): k for k, (p, s) in enumerate(zip(d["parent"], d["spot"]))}
        above_under = {}
        for k in np.flatnonzero(cluster).tolist():
            p, s = int(d["parent"][k]), int(d["spot"][k])
            above_under[k] = [at[(p, s + step)] for step in (-1, 1) if (p, s + step) in at]
        added = np.zeros(cluster.size, dtype=bool)
        for near in above_under.values():
            added[near] = True
        added &= ~cluster
        gold, m = d["gold"], d["gold"].size
        facts["cluster chunks"].append(int(cluster.sum()))
        facts["cluster chars"].append(int(d["length"][cluster].sum()))
        facts["cluster gold share"].append(float(gold[cluster].sum() / gold.sum()))
        facts["cluster product share"].append(float(cluster.sum() / m))
        facts["cluster gold chunks"].append(int(gold[cluster].sum()))
        facts["added chunks"].append(int(added.sum()))
        facts["added chars"].append(int(d["length"][added].sum()))
        facts["added gold share"].append(float(gold[added].sum() / gold.sum()))
        facts["added product share"].append(float(added.sum() / m))
        facts["added gold chunks"].append(int(gold[added].sum()))
        facts["both chunks"].append(int((cluster | added).sum()))
        facts["both chars"].append(int(d["length"][cluster | added].sum()))
        by_plain = np.lexsort((d["id_rank"], -plain)).tolist()
        in_cluster = [k for k in by_plain if cluster[k]]
        rest = [k for k in by_plain if not cluster[k]]
        orders = {
            "the three routes added, as they are": by_plain,
            "the cluster first, then the rest": in_cluster + rest,
            "the cluster, then the chunks above and under, then the rest":
                in_cluster + [k for k in rest if added[k]] + [k for k in rest if not added[k]],
        }
        seen, woven = set(), []
        for k in in_cluster:
            for j in [k] + above_under[k]:
                if j not in seen:
                    seen.add(j)
                    woven.append(j)
        orders["each cluster chunk followed at once by the one above and the one under, then the rest"] = (
            woven + [k for k in by_plain if k not in seen])
        for key, order in orders.items():
            got, kept = delivered_recall(order, d)
            recall[key].append(got)
            first_gold[key] += int(gold[order[0]])
    mid = {key: float(np.median(v)) for key, v in facts.items()}
    mean = {key: float(np.mean(v)) for key, v in facts.items()}
    total = {key: int(np.sum(v)) for key, v in facts.items()}
    print(f"\n==== the top cluster of: {name} ====")
    print(f"  the cluster: {mid['cluster chunks']:.0f} chunks, {mid['cluster chars']:,.0f} characters; "
          f"{mean['cluster gold share']:.0%} of the question's gold chunks, {mean['cluster product share']:.0%} of the "
          f"product's chunks; over the hundred {total['cluster gold chunks']} of its {total['cluster chunks']} chunks are gold "
          f"({total['cluster gold chunks'] / total['cluster chunks']:.0%})")
    print(f"  the chunks above and under it, not already in it: {mid['added chunks']:.0f} chunks, {mid['added chars']:,.0f} "
          f"characters; {mean['added gold share']:.0%} of the gold chunks, {mean['added product share']:.0%} of the product's "
          f"chunks; over the hundred {total['added gold chunks']} of the {total['added chunks']} are gold "
          f"({total['added gold chunks'] / max(total['added chunks'], 1):.0%})")
    print(f"  both together: {mid['both chunks']:.0f} chunks, {mid['both chars']:,.0f} characters")
    print("  context_recall_id (share of the cited records delivered inside 72,000 characters):")
    for key, values in recall.items():
        print(f"    {float(np.mean(values)):.3f}  {key}")

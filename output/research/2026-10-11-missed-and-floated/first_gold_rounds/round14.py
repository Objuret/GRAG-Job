"""Round 14, his 2026-10-12 question "for the top k cluster, what do we get if we take its siblings
also?". The top cluster is the first of five clusters of a nearness (least squares on the line,
`v4_walk.levels`), inside the question's product. Its siblings, as read here: the other chunks
under the same parent as a chunk of the cluster (the same channel, or the same file of
documents, transcripts or pull requests). Beside it the narrower reading: only the chunks right
next to a cluster chunk in its parent.

Printed per kind of top cluster: how many chunks and characters the cluster is, and the cluster
with its siblings; what share of the question's gold chunks each holds, beside the share of the
product's chunks it is (what a blind draw of that size would hold); and context_recall_id (share
of the cited records delivered inside 72,000 characters) when the cluster is delivered first,
then its siblings, then the rest, each part in the order of the three routes added."""
import sys
from pathlib import Path

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

from explore import BUDGET, load, measure, standing  # noqa: E402

data = load()
Q = data["questions"]
CLUSTERS = 5
KINDS = {
    "the three routes added": lambda d: standing(d["tags"]) + standing(d["description"]) + standing(d["question"]),
    "the description against the query description": lambda d: d["description"],
    "the tags (the chunk's closest tag to a query tag)": lambda d: d["tags"],
}


def parts_of(d, value):
    cluster = WK.levels(np.asarray(value, dtype=np.float64), CLUSTERS) == 1
    parents = set(d["parent"][cluster].tolist())
    siblings = np.isin(d["parent"], list(parents)) & ~cluster
    spots = {(int(p), int(s)) for p, s in zip(d["parent"][cluster], d["spot"][cluster])}
    beside = np.array([((int(p), int(s) - 1) in spots or (int(p), int(s) + 1) in spots)
                       for p, s in zip(d["parent"], d["spot"])]) & ~cluster
    return cluster, siblings, beside


for name, make in KINDS.items():
    rows = {key: [] for key in ("cluster chunks", "cluster characters", "cluster gold", "cluster share of product",
                                "with siblings chunks", "with siblings characters", "with siblings gold",
                                "with siblings share of product", "with neighbours chunks", "with neighbours gold",
                                "with neighbours share of product", "parents")}
    recall = {key: [] for key in ("the three routes added, as they are", "the cluster first, then the rest",
                                  "the cluster, then its siblings, then the rest",
                                  "the cluster, then the chunks next to it, then the rest")}
    for d in Q.values():
        plain = KINDS["the three routes added"](d)
        cluster, siblings, beside = parts_of(d, make(d))
        gold, m = d["gold"], d["gold"].size
        rows["cluster chunks"].append(int(cluster.sum()))
        rows["cluster characters"].append(int(d["length"][cluster].sum()))
        rows["cluster gold"].append(float(gold[cluster].sum() / gold.sum()))
        rows["cluster share of product"].append(float(cluster.sum() / m))
        both = cluster | siblings
        rows["with siblings chunks"].append(int(both.sum()))
        rows["with siblings characters"].append(int(d["length"][both].sum()))
        rows["with siblings gold"].append(float(gold[both].sum() / gold.sum()))
        rows["with siblings share of product"].append(float(both.sum() / m))
        near = cluster | beside
        rows["with neighbours chunks"].append(int(near.sum()))
        rows["with neighbours gold"].append(float(gold[near].sum() / gold.sum()))
        rows["with neighbours share of product"].append(float(near.sum() / m))
        rows["parents"].append(len(set(d["parent"][cluster].tolist())))
        z = standing(plain)
        recall["the three routes added, as they are"].append(measure(plain, d)[2])
        recall["the cluster first, then the rest"].append(measure(z + 1e3 * cluster, d)[2])
        recall["the cluster, then its siblings, then the rest"].append(measure(z + 2e3 * cluster + 1e3 * siblings, d)[2])
        recall["the cluster, then the chunks next to it, then the rest"].append(measure(z + 2e3 * cluster + 1e3 * beside, d)[2])
    mid = {key: float(np.median(values)) for key, values in rows.items()}
    mean = {key: float(np.mean(values)) for key, values in rows.items()}
    print(f"\n==== the top cluster of: {name} ====")
    print(f"  the cluster: {mid['cluster chunks']:.0f} chunks in {mid['parents']:.0f} parents, {mid['cluster characters']:,.0f} "
          f"characters; it holds {mean['cluster gold']:.0%} of the question's gold chunks and is "
          f"{mean['cluster share of product']:.0%} of the product's chunks")
    print(f"  with its siblings: {mid['with siblings chunks']:.0f} chunks, {mid['with siblings characters']:,.0f} characters; "
          f"{mean['with siblings gold']:.0%} of the gold chunks, {mean['with siblings share of product']:.0%} of the product's chunks")
    print(f"  with only the chunks next to it: {mid['with neighbours chunks']:.0f} chunks; {mean['with neighbours gold']:.0%} of "
          f"the gold chunks, {mean['with neighbours share of product']:.0%} of the product's chunks")
    print("  context_recall_id (share of the cited records delivered inside 72,000 characters):")
    for key, values in recall.items():
        print(f"    {float(np.mean(values)):.3f}  {key}")

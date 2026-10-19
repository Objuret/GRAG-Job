"""Round 25: everything that reaches the unseen gold works from a gold chunk and not from a chunk that
only looks sure (rounds 22 to 24). So: do the gold chunks of the sure set stand together and
apart from its other chunks, so that the sure set splits into the right ones and the wrong
ones? Inside the question's product, the hundred. The sure set is that of round 22 (about 14
chunks a question, 29% of them gold).

The sure set is split in two (and in three) by its chunks' description nearness to each other
(average linkage on the cosines). Printed:
  with the gold in hand   the share of gold in the richer part and in the other, their sizes
                          (what the split is worth at most)
  without it              the part picked by a rule that needs no gold: the part with the higher
                          mean of the two values added; the part that holds the highest chunk;
                          the larger part; the part whose chunks are more tied by pointers to
                          each other; the tighter part. The share of gold in the picked part.
The same split made on the tags the chunks carry (two chunks are near when they share tags)."""
import pickle
import sys
from pathlib import Path

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

from explore import load, standing  # noqa: E402

HERE = Path(__file__).resolve().parent
data = load()
Q = data["questions"]
for name in ("tags", "ties"):
    with open(HERE / f"first_gold_signals_{name}__gold100.pkl", "rb") as handle:
        extra = pickle.load(handle)
    for qid, d in Q.items():
        d.update(extra[qid])


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


def split(similarity, parts):
    distance = 1. - similarity
    np.fill_diagonal(distance, 0.)
    distance = np.maximum((distance + distance.T) / 2., 0.)
    return fcluster(linkage(squareform(distance, checks=False), method="average"), parts, criterion="maxclust")


results = {}


def note(key, picked_gold, picked_size, other_gold, other_size):
    row = results.setdefault(key, [0, 0, 0, 0, 0])
    row[0] += picked_gold
    row[1] += picked_size
    row[2] += other_gold
    row[3] += other_size
    row[4] += 1


for d in Q.values():
    D, T = np.asarray(d["description"], dtype=np.float64), np.asarray(d["tags"], dtype=np.float64)
    m, gold = D.size, d["gold"]
    step = WK.levels(D, 5) + WK.levels(T, 5)
    z = standing(D) + standing(T)
    hits = step <= 3 if (step <= 3).any() else step == step.min()
    scope = majority(hits, d["parent"])
    sure = np.flatnonzero((scope & (step <= 4)) | (~scope & (step == 2)))
    if sure.size < 4:
        continue
    among = d["among"].astype(np.float64)[np.ix_(sure, sure)]
    tags_of = [set() for _ in range(m)]
    for c, t in zip(d["edge_chunk"].tolist(), d["edge_tag"].tolist()):
        tags_of[c].add(t)
    shared = np.array([[len(tags_of[a] & tags_of[b]) / max(len(tags_of[a] | tags_of[b]), 1) for b in sure] for a in sure])
    at = {(int(p), int(s)): k for k, (p, s) in enumerate(zip(d["parent"], d["spot"]))}
    talks = [set(t) for t in d["talks"]]
    linked = [set() for _ in range(m)]
    for a, b in d["share_a_link"].tolist():
        linked[a].add(b)
        linked[b].add(a)
    pointer = np.zeros((sure.size, sure.size))
    for i, a in enumerate(sure.tolist()):
        for j, b in enumerate(sure.tolist()):
            if i != j and (b in linked[a] or (talks[a] & talks[b])
                           or (d["parent"][a] == d["parent"][b] and abs(int(d["spot"][a]) - int(d["spot"][b])) == 1)):
                pointer[i, j] = 1.
    g = gold[sure]
    for space, similarity in (("descriptions", among), ("shared tags", shared)):
        for parts in (2, 3):
            label = split(similarity.copy(), parts)
            groups = [np.flatnonzero(label == value) for value in np.unique(label)]
            if len(groups) < 2:
                continue
            rest_of = lambda pick: np.concatenate([grp for grp in groups if grp is not pick])
            richest = max(groups, key=lambda grp: (g[grp].mean(), grp.size))
            note((space, parts, "with the gold in hand: the richer part"), int(g[richest].sum()), richest.size,
                 int(g[rest_of(richest)].sum()), rest_of(richest).size)
            rules = {
                "the part with the higher mean of the two values added": lambda grp: z[sure][grp].mean(),
                "the part that holds the highest chunk": lambda grp: z[sure][grp].max(),
                "the larger part": lambda grp: grp.size,
                "the part whose chunks are more tied to each other by pointers": lambda grp: pointer[np.ix_(grp, grp)].sum() / max(grp.size, 1),
                "the tighter part (mean nearness inside it)": lambda grp: (similarity[np.ix_(grp, grp)].sum() - grp.size) / max(grp.size * (grp.size - 1), 1),
            }
            for name, rule in rules.items():
                pick = max(groups, key=lambda grp: (rule(grp), grp.size))
                note((space, parts, name), int(g[pick].sum()), pick.size, int(g[rest_of(pick)].sum()), rest_of(pick).size)

print("split of the sure set | picked part: chunks a question, share gold | the other part(s): chunks a question, share gold")
for (space, parts, name), (pg, ps, og, os_, count) in results.items():
    print(f"  by {space}, in {parts} | {ps / count:4.1f}, {pg / max(ps, 1):4.0%} | {os_ / count:4.1f}, {og / max(os_, 1):4.0%}  {name}")

"""Round 17, his 2026-10-12 "the combo should fucking work.. So, if we use the chunk-cloud, see if you
can find a way to combo or lift with the tags". The chunk cloud is the first of five clusters of
the chunk descriptions' nearness to the query description (`v4_walk.levels`), inside the
question's product, the hundred. Ways the tags are brought in:

  a  inside the cloud, the tags order it (the closest query tag; the mean over the query tags;
     the tags' standing added to the description's)
  b  two clouds and their overlap first: the chunk cloud and a tag cloud (the first cluster of
     the tags' route; or the chunks carrying a picked tag), the overlap, then the rest of each
  c  the cloud says which tags to trust: a picked tag counts only when one of its chunks is in
     the chunk cloud; the trusted tags then pull in their other chunks, also outside the cloud
  d  a tag judged by both at once: its closeness to the query tags and how near the descriptions
     of the chunks it sits on are to the query description; a chunk takes its best tag
  f  the tags as the tie for a lift: a chunk is lifted by the description nearness of the other
     chunks that carry its tags (picked tags only; every tag)

Printed per way: on how many questions the first chunk is gold, context_recall_id (share of the
cited records delivered inside 72,000 characters), and for the ways with tiers how many chunks a
tier is and what share of them is gold (a chunk of the product is gold 6% of the time)."""
import pickle
import sys
from pathlib import Path

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

from explore import load, measure, standing  # noqa: E402

HERE = Path(__file__).resolve().parent
SAME = 0.8541
K = 5
data = load()
Q = data["questions"]
with open(HERE / "first_gold_signals_tags__gold100.pkl", "rb") as handle:
    TAGS = pickle.load(handle)
for qid, d in Q.items():
    d.update(TAGS[qid])


def tag_side(d):
    """Per tag of the product: its closeness to the closest query tag, whether a query tag picks it (its five
    nearest of the product's tags), and the chunks it sits on."""
    fit = d["tag_fit"].astype(np.float64)
    close = fit.max(axis=0)
    kth = np.sort(fit, axis=1)[:, ::-1][:, min(K, fit.shape[1]) - 1]
    picked = (fit >= kth[:, None] - 1e-12).any(axis=0)
    chunks_of = [[] for _ in range(fit.shape[1])]
    for c, t in zip(d["edge_chunk"].tolist(), d["edge_tag"].tolist()):
        chunks_of[t].append(c)
    return close, picked, chunks_of


def build(d):
    m = d["gold"].size
    D, T = np.asarray(d["description"], dtype=np.float64), np.asarray(d["tags"], dtype=np.float64)
    zD, zT = standing(D), standing(T)
    cloud = WK.levels(D, 5) == 1
    close, picked, chunks_of = tag_side(d)
    ec, et = d["edge_chunk"], d["edge_tag"]
    out, tiers = {}, {}
    out["the chunk descriptions alone (the cloud in its own order)"] = zD
    out["the tags alone (closest query tag)"] = zT
    out["descriptions + tags, standings added, no cloud"] = zD + zT
    # a
    out["a: the cloud, ordered by the tags' closest query tag; then the rest by description"] = (
        np.where(cloud, 1e3 + zT, zD))
    out["a: the cloud, ordered by the mean over the query tags; then the rest by description"] = (
        np.where(cloud, 1e3 + standing(d["fit"].mean(axis=0)), zD))
    out["a: the cloud, ordered by description + tags; then the rest by description + tags"] = 1e3 * cloud + zD + zT
    # b
    for label, other in (("the first cluster of the tags' route", WK.levels(T, 5) == 1),
                         ("the chunks carrying a picked tag", np.isin(np.arange(m), ec[picked[et]]))):
        tier = 3 * (cloud & other) + 2 * (cloud & ~other) + 1 * (~cloud & other)
        name = f"b: overlap of the chunk cloud and {label}, then the rest of the chunk cloud, then the rest of the other"
        out[name] = 1e3 * tier + zD + zT
        tiers[name] = (tier, {3: "in both", 2: "chunk cloud only", 1: "tag side only", 0: "neither"})
    # c
    for label, base in (("picked tags", picked), ("tags that are the same thing as a query tag", close >= SAME)):
        trusted = np.array([bool(base[t]) and any(cloud[c] for c in chunks_of[t]) for t in range(close.size)])
        lifted = np.isin(np.arange(m), ec[trusted[et]])
        tier = 3 * (cloud & lifted) + 2 * (~cloud & lifted) + 1 * (cloud & ~lifted)
        name = f"c: {label} with a chunk in the cloud are trusted; cloud chunks with one, then chunks outside with one, then the rest of the cloud"
        out[name] = 1e3 * tier + zD + zT
        tiers[name] = (tier, {3: "in the cloud, with a trusted tag", 2: "outside, pulled in by a trusted tag",
                              1: "in the cloud, no trusted tag", 0: "neither"})
        tier2 = 3 * (cloud & lifted) + 2 * (cloud & ~lifted) + 1 * (~cloud & lifted)
        name2 = f"c: the same with the rest of the cloud before the chunks pulled in ({label})"
        out[name2] = 1e3 * tier2 + zD + zT
    # d
    z_close = standing(close)
    for label, how in (("the mean over its chunks", np.mean), ("its best chunk", np.max)):
        of_tag = np.array([how(zD[chunks]) if chunks else zD.min() for chunks in chunks_of])
        value = z_close + standing(of_tag)
        best = np.full(m, value.min())
        np.maximum.at(best, ec, value[et])
        out[f"d: a tag judged by its closeness and by the description nearness of the chunks it sits on ({label}); a chunk takes its best tag"] = best
        out[f"d: the same ({label}) with the chunk's own description added"] = standing(best) + zD
    # f
    for label, allowed in (("picked tags only", picked), ("every tag", np.ones(close.size, dtype=bool))):
        lift = np.zeros(m)
        for t in np.flatnonzero(allowed).tolist():
            chunks = chunks_of[t]
            if len(chunks) < 2:
                continue
            total = zD[chunks].sum()
            for c in chunks:
                lift[c] = max(lift[c], (total - zD[c]) / (len(chunks) - 1))
        out[f"f: description, lifted by the description nearness of the other chunks sharing its tags ({label})"] = zD + lift
        out[f"f: the same with the tags' standing added ({label})"] = zD + zT + lift
    return out, tiers, cloud


first, recall, tier_counts, cloud_stats = {}, {}, {}, [0, 0]
for d in Q.values():
    out, tiers, cloud = build(d)
    cloud_stats[0] += int(cloud.sum())
    cloud_stats[1] += int(d["gold"][cloud].sum())
    for name, score in out.items():
        got = measure(score, d)
        first[name] = first.get(name, 0) + int(got[0])
        recall.setdefault(name, []).append(got[2])
    for name, (tier, labels) in tiers.items():
        row = tier_counts.setdefault(name, {})
        for value, label in labels.items():
            cell = row.setdefault(label, [0, 0])
            cell[0] += int((tier == value).sum())
            cell[1] += int(d["gold"][tier == value].sum())
print(f"the chunk cloud over the hundred: {cloud_stats[0] / 100:.0f} chunks a question, {cloud_stats[1] / cloud_stats[0]:.0%} "
      "of them gold; a chunk of the product is gold 6% of the time")
print("== the first chunk is gold (of 100) | context_recall_id ==")
for name in first:
    print(f"  {first[name]:3d} | {float(np.mean(recall[name])):.3f}  {name}")
    if name in tier_counts:
        for label, (chunks, gold) in tier_counts[name].items():
            if label != "neither":
                print(f"          {label}: {chunks / 100:.1f} chunks a question, {gold / max(chunks, 1):.0%} of them gold")

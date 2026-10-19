"""Round 13: his combo, tags and descriptions working together. The tags say which chunks are in (a
group the tags call equal); inside the group the chunk's description against the question
without the product's name decides. Several readings of "equal":
  the tie      the chunks that carry the one closest tag
  same thing   the chunks whose closest tag is the same thing as a query tag (the graph's own
               level for that, 0.8541 in query mode); where no chunk is, the tie
  picked       the chunks that carry one of a query tag's five nearest tags of the product
  first cluster the first of five clusters of the tags' route
After the group, the rest by the same decider."""
import pickle
from pathlib import Path

import numpy as np

from explore import load, report, standing

HERE = Path(__file__).resolve().parent
SAME = 0.8541
data = load()
Q = data["questions"]
with open(HERE / "first_gold_signals_more__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
for qid, d in Q.items():
    d.update(extra[qid])


def levels_first(values, k=5):
    """The first of k clusters on the line (least squares, by dynamic programming over the sorted values)."""
    v = np.sort(np.asarray(values, dtype=np.float64))[::-1]
    m = v.size
    if m <= k:
        return np.asarray(values) >= v[0]
    prefix, prefix2 = np.concatenate([[0.], np.cumsum(v)]), np.concatenate([[0.], np.cumsum(v * v)])

    def cost(i, j):
        s, s2, c = prefix[j] - prefix[i], prefix2[j] - prefix2[i], j - i
        return s2 - s * s / c
    best = np.full((k + 1, m + 1), np.inf)
    cut = np.zeros((k + 1, m + 1), dtype=np.int64)
    best[0, 0] = 0.
    for parts in range(1, k + 1):
        for j in range(parts, m + 1):
            for i in range(parts - 1, j):
                value = best[parts - 1, i] + cost(i, j)
                if value < best[parts, j]:
                    best[parts, j], cut[parts, j] = value, i
    j, bounds = m, []
    for parts in range(k, 0, -1):
        i = cut[parts, j]
        bounds.append(i)
        j = i
    first_size = sorted(bounds)[1] if len(bounds) > 1 else m
    return np.asarray(values) >= v[first_size - 1]


def groups(d):
    tags = d["tags"]
    tie = tags >= tags.max() - 1e-12
    same = tags >= SAME
    if not same.any():
        same = tie
    k = 5
    kth = np.sort(d["fit"], axis=1)[:, ::-1][:, min(k, d["fit"].shape[1]) - 1]
    picked = (d["fit"] >= kth[:, None] - 1e-12).any(axis=0)
    return {"the tie": tie, "same thing": same, "picked (five nearest of the product's tags)": picked,
            "first cluster of the tags' route": levels_first(tags)}


DECIDERS = {
    "the question without the name against descriptions (own pairing)": lambda d: d["bare_to_passage"],
    "the question without the name against descriptions (query both sides)": lambda d: d["question_bare"],
    "the question with the name against descriptions (query both sides)": lambda d: d["question"],
    "the query description against descriptions": lambda d: d["description"],
}
sizes = {}
tries = {"the tags' route alone (closest tag)": lambda d: d["tags"],
         "the plain order": lambda d: standing(d["tags"]) + standing(d["description"]) + standing(d["question"])}
for decider_name, decider in DECIDERS.items():
    tries[f"no group: {decider_name}"] = decider
    for group_name in ("the tie", "same thing", "picked (five nearest of the product's tags)", "first cluster of the tags' route"):
        def make(d, group_name=group_name, decider=decider):
            group = groups(d)[group_name]
            sizes.setdefault(group_name, []).append((int(group.sum()), bool(d["gold"][group].any()), float(d["gold"][group].mean())))
            return standing(decider(d)) + 1e3 * group
        tries[f"{group_name}, then {decider_name}"] = make
rows = report(tries, data, sort=False)
print()
for name, values in sizes.items():
    a = np.array(values[:100], dtype=np.float64)
    print(f"  {name}: {np.median(a[:, 0]):.0f} chunks ({np.percentile(a[:, 0], 25):.0f}-{np.percentile(a[:, 0], 75):.0f}); "
          f"a gold chunk in it on {int(a[:, 1].sum())} of 100; {a[:, 2].mean():.0%} of it gold")

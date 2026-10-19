"""Round 22: the gold the combo and the scope do not see, and what reaches it (his 2026-10-12 work on
the cloud combo and scope; his 2026-10-11 "a 'nearest' chunk etc could be used for search-start
or search-range", "an agnostic search that, if it's correct chunk, stops there, but if not,
actually does a search"). Inside the question's product, the hundred.

The sure set: the chunks in the cells where descriptions, tags and scope agree most (in the
majority's parents and on one of the combo's first three steps, or outside them on its first
step); about what fits in 72,000 characters. Everything else is the rest.

  A  the gold chunks in the rest: how many a question, of what kind, in which cell
  B  how a gold chunk of the rest is tied to a gold chunk of the sure set: right above or under
     it in its parent, two or three places away, in the same conversation (one channel, one
     day), sharing a link, in the same parent, on the same day
  C  what a search from the sure set reaches, not knowing which of its chunks are gold: for each
     tie, the chunks of the rest it reaches and what share of them is gold; then the same under
     conditions that need no gold (the reached chunk shares a tag with the chunk it was reached
     from; its description stands in the first cluster of nearness to that chunk's description;
     it continues the same conversation)
A chunk of the product is gold 6% of the time."""
import pickle
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

from explore import load, standing  # noqa: E402

HERE = Path(__file__).resolve().parent
data = load()
Q = data["questions"]
KINDS = data["kind_names"]
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


A_kind, A_cell = Counter(), Counter()
A_counts = {"gold chunks": [], "in the sure set": [], "in the rest": [], "sure set chunks": [], "sure set characters": []}
B = Counter()
C = {}
count = len(Q)
for d in Q.values():
    D, T = np.asarray(d["description"], dtype=np.float64), np.asarray(d["tags"], dtype=np.float64)
    m = D.size
    gold = d["gold"]
    step = WK.levels(D, 5) + WK.levels(T, 5)
    hits = step <= 3 if (step <= 3).any() else step == step.min()
    scope = majority(hits, d["parent"])
    sure = (scope & (step <= 4)) | (~scope & (step == 2))
    cell = np.where(scope, np.where(step == 2, "in scope, step 1", np.where(step == 3, "in scope, step 2",
                    np.where(step == 4, "in scope, step 3", "in scope, lower"))),
                    np.where(step == 2, "outside, step 1", np.where(step == 3, "outside, step 2",
                    np.where(step == 4, "outside, step 3", "outside, lower"))))
    A_counts["gold chunks"].append(int(gold.sum()))
    A_counts["in the sure set"].append(int(gold[sure].sum()))
    A_counts["in the rest"].append(int(gold[~sure].sum()))
    A_counts["sure set chunks"].append(int(sure.sum()))
    A_counts["sure set characters"].append(int(d["length"][sure].sum()))
    for k in np.flatnonzero(gold & ~sure).tolist():
        A_kind[KINDS[int(d["kind"][k])]] += 1
        A_cell[str(cell[k])] += 1
    # the ties
    at = {(int(p), int(s)): k for k, (p, s) in enumerate(zip(d["parent"], d["spot"]))}
    talks = [set(t) for t in d["talks"]]
    days = [set(t) for t in d["days"]]
    linked = [set() for _ in range(m)]
    for a, b in d["share_a_link"].tolist():
        linked[a].add(b)
        linked[b].add(a)
    tags_of = [set() for _ in range(m)]
    for c, t in zip(d["edge_chunk"].tolist(), d["edge_tag"].tolist()):
        tags_of[c].add(t)
    among = d["among"].astype(np.float64)

    def near_in_file(k, far):
        p, s = int(d["parent"][k]), int(d["spot"][k])
        return [at[(p, s + step_)] for step_ in (-far, far) if (p, s + step_) in at]

    sure_gold = set(np.flatnonzero(sure & gold).tolist())
    for k in np.flatnonzero(gold & ~sure).tolist():
        B["gold chunks of the rest"] += 1
        found = False
        for far, label in ((1, "right above or under a gold chunk of the sure set"), (2, "two places from one"),
                           (3, "three places from one")):
            if set(near_in_file(k, far)) & sure_gold:
                B[label] += 1
                found = True
                break
        if any(talks[k] & talks[g] for g in sure_gold):
            B["in a conversation a gold chunk of the sure set is in"] += 1
        if linked[k] & sure_gold:
            B["shares a link with a gold chunk of the sure set"] += 1
        if any(d["parent"][k] == d["parent"][g] for g in sure_gold):
            B["in the parent of a gold chunk of the sure set"] += 1
        if any(days[k] & days[g] for g in sure_gold):
            B["has a record on a day a gold chunk of the sure set has one"] += 1
        tied = (set(near_in_file(k, 1)) & sure_gold) or (linked[k] & sure_gold) or any(talks[k] & talks[g] for g in sure_gold)
        B["above or under, or a shared link, or a shared conversation"] += int(bool(tied))
        if not sure_gold:
            B["the sure set holds no gold chunk for its question"] += 1
    # what a search from the sure set reaches
    sources = np.flatnonzero(sure).tolist()
    first_level = {s: WK.levels(among[s][np.arange(m) != s], 5) for s in sources}

    def desc_close(s, k):
        idx = k if k < s else k - 1
        return first_level[s][idx] == 1

    reach = {}
    for s in sources:
        for k in near_in_file(s, 1):
            reach.setdefault(("right above or under", k), []).append(s)
        for k in near_in_file(s, 2):
            reach.setdefault(("two places away", k), []).append(s)
        for k in linked[s]:
            reach.setdefault(("shares a link", k), []).append(s)
        for k in range(m):
            if k != s and talks[k] & talks[s]:
                reach.setdefault(("in the same conversation", k), []).append(s)
    for (tie, k), froms in reach.items():
        if sure[k]:
            continue
        conditions = {
            "no condition": True,
            "it shares a tag with the chunk it was reached from": any(tags_of[k] & tags_of[s] for s in froms),
            "its description is in the first cluster of nearness to that chunk's": any(desc_close(s, k) for s in froms),
            "both of those": any((tags_of[k] & tags_of[s]) and desc_close(s, k) for s in froms),
            "it is reached from two or more chunks of the sure set": len(set(froms)) >= 2,
            "it is itself on the combo's step 4 or 5 (the next ones down)": step[k] <= 6,
            "it is reached from a chunk on the combo's first step": any(step[s] == 2 for s in froms),
        }
        for label, holds in conditions.items():
            if holds:
                row = C.setdefault((tie, label), [0, 0])
                row[0] += 1
                row[1] += int(gold[k])

print("== A: a question's gold chunks (the middle; mean) ==")
for name, values in A_counts.items():
    print(f"  {name}: {np.median(values):,.0f}; {np.mean(values):,.1f}")
total = sum(A_kind.values())
print("  the gold chunks of the rest by kind: " + ", ".join(f"{k}: {v} ({v / total:.0%})" for k, v in A_kind.most_common()))
print("  by cell: " + ", ".join(f"{k}: {v} ({v / total:.0%})" for k, v in A_cell.most_common()))
print("\n== B: the gold chunks of the rest, how they are tied to a gold chunk of the sure set ==")
base = B["gold chunks of the rest"]
for name, value in B.items():
    if name != "gold chunks of the rest":
        print(f"  {value:4d} of {base} ({value / base:.0%})  {name}")
print("\n== C: what a search from the sure set reaches in the rest: chunks a question | share of them gold ==")
for (tie, label), (chunks, golds) in sorted(C.items()):
    print(f"  {chunks / count:5.1f} | {golds / max(chunks, 1):4.0%}  {tie}; {label}")

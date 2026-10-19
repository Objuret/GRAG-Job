"""Round 24: the graph's own tie across parents, chunk - tag - chunk. Two thirds of the gold the combo
and the scope do not see is not tied by file place, link or conversation to any gold chunk they
do see (round 22). Is it tied through a shared tag? Inside the question's product, the hundred;
a chunk of the product is gold 6% of the time. The sure set is that of round 22.

  1  the gold chunks of the rest: how many share a tag with a gold chunk of the sure set, by how
     many chunks of the product the tag sits on, and by whether the tag is the same thing as a
     query tag (the graph's level, 0.8541); beside them the chunks of the rest that are not gold
  2  a search from the sure set through its tags, not knowing which sure chunks are gold: the
     chunks of the rest that share a tag with a sure chunk, by the tag's spread and its
     closeness to the query tags, and by the cell of the sure chunk: chunks a question, share gold
  3  the same when two or more sure chunks carry the tag (the tag is one the sure set shares)"""
import pickle
import sys
from pathlib import Path

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

from explore import load  # noqa: E402

HERE = Path(__file__).resolve().parent
SAME = 0.8541
data = load()
Q = data["questions"]
for name in ("tags", "ties"):
    with open(HERE / f"first_gold_signals_{name}__gold100.pkl", "rb") as handle:
        extra = pickle.load(handle)
    for qid, d in Q.items():
        d.update(extra[qid])
SPREADS = ((2, 2, "on 2 chunks of the product"), (3, 4, "on 3 or 4"), (5, 9, "on 5 to 9"), (10, 10 ** 6, "on 10 or more"))


def spread_label(k):
    return next(label for low, high, label in SPREADS if low <= k <= high)


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


one = {"gold": {}, "not gold": {}}
totals = {"gold": 0, "not gold": 0}
two, three = {}, {}
count = len(Q)
for d in Q.values():
    D, T = np.asarray(d["description"], dtype=np.float64), np.asarray(d["tags"], dtype=np.float64)
    m, gold = D.size, d["gold"]
    step = WK.levels(D, 5) + WK.levels(T, 5)
    hits = step <= 3 if (step <= 3).any() else step == step.min()
    scope = majority(hits, d["parent"])
    sure = (scope & (step <= 4)) | (~scope & (step == 2))
    first_cell = scope & (step == 2)
    close = d["tag_fit"].astype(np.float64).max(axis=0)
    n_tags = close.size
    chunks_of = [[] for _ in range(n_tags)]
    for c, t in zip(d["edge_chunk"].tolist(), d["edge_tag"].tolist()):
        chunks_of[t].append(c)
    # per chunk of the rest: the tags it shares with sure chunks
    shared_gold = [[] for _ in range(m)]       # tags shared with a gold chunk of the sure set
    shared_sure = [[] for _ in range(m)]       # (tag, sure chunks carrying it)
    for t, chunks in enumerate(chunks_of):
        if len(chunks) < 2:
            continue
        sure_here = [c for c in chunks if sure[c]]
        if not sure_here:
            continue
        for c in chunks:
            if not sure[c]:
                shared_sure[c].append((t, sure_here))
                if any(gold[s] for s in sure_here):
                    shared_gold[c].append(t)
    for k in np.flatnonzero(~sure).tolist():
        which = "gold" if gold[k] else "not gold"
        totals[which] += 1
        labels = set()
        if shared_gold[k]:
            labels.add("shares a tag with a gold chunk of the sure set")
            for t in shared_gold[k]:
                labels.add("... a tag " + spread_label(len(chunks_of[t])))
                if close[t] >= SAME:
                    labels.add("... a tag that is the same thing as a query tag")
        for label in labels:
            one[which][label] = one[which].get(label, 0) + 1
        seen2, seen3 = set(), set()
        for t, sure_here in shared_sure[k]:
            spread = spread_label(len(chunks_of[t]))
            keys = [("any sure chunk", "any tag"), ("any sure chunk", "a tag " + spread)]
            if close[t] >= SAME:
                keys += [("any sure chunk", "a tag that is the same thing as a query tag"),
                         ("any sure chunk", "the same thing as a query tag, " + spread)]
            if any(first_cell[s] for s in sure_here):
                keys += [("a sure chunk in scope on the combo's first step", "any tag"),
                         ("a sure chunk in scope on the combo's first step", "a tag " + spread)]
                if close[t] >= SAME:
                    keys.append(("a sure chunk in scope on the combo's first step", "a tag that is the same thing as a query tag"))
            for key in keys:
                if key not in seen2:
                    seen2.add(key)
                    row = two.setdefault(key, [0, 0])
                    row[0] += 1
                    row[1] += int(gold[k])
            if len(sure_here) >= 2:
                keys3 = [("any tag two or more sure chunks carry",), ("such a tag " + spread,)]
                if close[t] >= SAME:
                    keys3.append(("such a tag that is the same thing as a query tag",))
                if len(sure_here) * 2 >= len(chunks_of[t]):
                    keys3.append(("such a tag with half or more of its chunks in the sure set",))
                for key in keys3:
                    if key not in seen3:
                        seen3.add(key)
                        row = three.setdefault(key, [0, 0])
                        row[0] += 1
                        row[1] += int(gold[k])

print("== 1: chunks of the rest that share a tag with a GOLD chunk of the sure set: of the gold ones | of the ones that "
      "are not gold ==")
labels = sorted(set(one["gold"]) | set(one["not gold"]))
for label in labels:
    a, b = one["gold"].get(label, 0), one["not gold"].get(label, 0)
    print(f"  {a / totals['gold']:4.0%} | {b / totals['not gold']:4.0%}  {label}")
print(f"  (the rest holds {totals['gold'] / count:.1f} gold chunks and {totals['not gold'] / count:.1f} others a question)")
print("\n== 2: a search from the sure set through its tags: chunks of the rest reached a question | share gold ==")
for (source, tag), (chunks, golds) in sorted(two.items()):
    print(f"  {chunks / count:5.1f} | {golds / max(chunks, 1):4.0%}  from {source}; {tag}")
print("\n== 3: through a tag two or more sure chunks carry: chunks of the rest reached a question | share gold ==")
for (label,), (chunks, golds) in sorted(three.items()):
    print(f"  {chunks / count:5.1f} | {golds / max(chunks, 1):4.0%}  {label}")

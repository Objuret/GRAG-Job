"""Round 5: what a chunk holds and what it is, with no fit.
  a  on the questions whose first chunk (plain order) is not gold: for each property, on how many
     the first gold chunk has more of it than the wrong first chunk.
  b  each property as an order of its own, no question at all: first chunk gold, of 100.
  c  the graph's tags whose name stands in the question word for word."""
import pickle
from pathlib import Path

import numpy as np

from explore import load, measure, report, standing

data = load()
Q = data["questions"]
with open(Path(__file__).resolve().parent / "what_a_chunk_holds.pkl", "rb") as handle:
    HOLDS = pickle.load(handle)
KIND = data["kind_names"]
PARENTS = data["parent_names"]


def plain_of(d):
    return standing(d["tags"]) + standing(d["description"]) + standing(d["question"])


def properties(d):
    out = {name: HOLDS["table"][d["chunks"], k] for k, name in enumerate(HOLDS["names"])}
    parent_size = np.bincount(d["parent"])[d["parent"]]
    out["tags on the chunk"] = d["n_tags"].astype(float)
    out["how far into its parent"] = d["spot"] / np.maximum(parent_size - 1, 1)
    out["chunks in its parent"] = parent_size.astype(float)
    first = d["first_time"]
    span = np.nanmax(d["last_time"]) - np.nanmin(first)
    out["how late in the product's time"] = (first - np.nanmin(first)) / span if span > 0 else np.zeros_like(first)
    out["graph tags on it whose name stands in the question"] = d["named_count"]
    return out


# a
wins, ties, seen = {}, {}, {}
count = 0
for d in Q.values():
    plain = plain_of(d)
    order = np.lexsort((d["id_rank"], -plain))
    if d["gold"][order[0]]:
        continue
    count += 1
    top, gold = int(order[0]), int(order[np.argmax(d["gold"][order])])
    for name, v in properties(d).items():
        a, b = v[gold], v[top]
        if np.isnan(a) or np.isnan(b):
            continue
        seen[name] = seen.get(name, 0) + 1
        wins[name] = wins.get(name, 0) + int(a > b)
        ties[name] = ties.get(name, 0) + int(a == b)
print(f"== a: {count} questions with a wrong first chunk. The first gold chunk has MORE of it than the wrong first "
      "chunk on | less on | equal on ==")
for name in sorted(wins, key=lambda k: -(wins[k] - (seen[k] - wins[k] - ties[k]))):
    print(f"  {wins[name]:3d} | {seen[name] - wins[name] - ties[name]:3d} | {ties[name]:3d}  {name}")

# b
print("\n== b: one property as the whole order, no question at all ==")
alone = {}
for k, name in enumerate(HOLDS["names"]):
    alone[f"most {name} first"] = lambda d, k=k: HOLDS["table"][d["chunks"], k]
    alone[f"least {name} first"] = lambda d, k=k: -HOLDS["table"][d["chunks"], k]
alone["earliest in the product's time first"] = lambda d: -np.nan_to_num(d["first_time"], nan=np.inf)
alone["latest first"] = lambda d: np.nan_to_num(d["first_time"], nan=-np.inf)
alone["most tags first"] = lambda d: d["n_tags"].astype(float)
for k, name in enumerate(KIND):
    alone[f"kind {name} first"] = lambda d, k=k: (d["kind"] == k).astype(float)
report(alone, data, show=14)

# gold by kind of parent
share, total = {}, {}
for d in Q.values():
    for k in range(d["gold"].size):
        name = PARENTS[int(d["parent"][k])]
        parts = name.split(".")
        label = parts[2] + ("." + parts[3].split("-")[0] if len(parts) > 3 and parts[2] == "slack" else "")
        total[label] = total.get(label, 0) + 1
        share[label] = share.get(label, 0) + int(d["gold"][k])
print("\n== where the gold sits: chunk-and-question pairs by kind of parent | gold among them | share ==")
for label in sorted(total, key=lambda k: -share[k]):
    print(f"  {total[label]:6d} | {share[label]:4d} | {share[label] / total[label]:.1%}  {label}")

# c
named = [d["named_tags"] for d in Q.values()]
words = [w for d in Q.values() for w in d["named_tag_words"]]
print(f"\n== c: graph tags of the product whose name stands in the question word for word (the product's name aside): "
      f"{np.median(named):.0f} a question ({np.percentile(named, 25):.0f}-{np.percentile(named, 75):.0f}), none on "
      f"{sum(1 for x in named if x == 0)} questions; of {len(words)} such tags {sum(1 for w in words if w == 1)} are one "
      f"word, {sum(1 for w in words if w == 2)} two, {sum(1 for w in words if w >= 3)} three or more ==")
pairs = gold_pairs = 0
for d in Q.values():
    has = d["named_count"] > 0
    pairs += int(has.sum())
    gold_pairs += int(d["gold"][has].sum())
print(f"  chunks that carry such a tag: {pairs} over the hundred, {gold_pairs} of them gold ({gold_pairs / max(pairs, 1):.0%}; "
      f"a chunk of the product is gold 6% of the time)")


def named_order(kind):
    def make(d):
        plain = plain_of(d)
        if kind == "count":
            lead = d["named_count"]
        elif kind == "longest":
            lead = d["named_longest"]
        elif kind == "rarest":
            lead = np.where(np.isfinite(d["named_rarest"]), -d["named_rarest"], -1e9)
        else:
            lead = (d["named_longest"] >= 2).astype(float)
        return lead * 1e3 + plain
    return make


report({
    "the plain order": plain_of,
    "chunks with the most named tags first, the plain order inside": named_order("count"),
    "chunks with the longest named tag first, the plain order inside": named_order("longest"),
    "chunks with the rarest named tag first, the plain order inside": named_order("rarest"),
    "chunks with a named tag of two or more words first, the plain order inside": named_order("two"),
    "the plain order with the count of named tags added as a standing":
        lambda d: plain_of(d) + standing(d["named_count"]) if d["named_count"].any() else plain_of(d),
}, data, sort=False)

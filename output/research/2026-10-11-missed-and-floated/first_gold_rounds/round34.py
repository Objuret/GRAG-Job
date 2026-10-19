"""Round 34: what fills the 72,000 is the group both sides touch: 24 chunks a question, 20% gold, so 19
chunks a question that both the tags and the descriptions touch and that are not gold. His
concept gives one more thing to order with, the facet values on the edge from a tag to a chunk
(topic, temporal, why, activity, concreteness). Do they float the gold INSIDE that group?
Inside the question's product, the hundred.

A chunk's facet value: over its edges to the tags a query tag picks (five nearest of the
product's tags), the mean of the value and the highest. Printed per facet and for the four
ranking facets added (each on its own scale): the share of gold in the upper third of the group
against its lower third when the group is ordered by that value; then the order "the group both
sides touch first, ordered by the value, then the rest by the three routes added": gold chunks
in the first 15 (of 10), the first chunk gold (of 100), context_recall_id (share of the cited
records delivered inside 72,000 characters). Beside them the group in the order of the three
routes added, and ordered by how many different query tags touch the chunk."""
import pickle
import sys
from pathlib import Path

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

from explore import BUDGET, load, standing  # noqa: E402

HERE = Path(__file__).resolve().parent
data = load()
Q = data["questions"]
FACETS = list(data["facets"])
with open(HERE / "first_gold_signals_tags__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
for qid, d in Q.items():
    d.update(extra[qid])


def run(order, d):
    order = np.asarray(order, dtype=np.int64)
    fits = np.cumsum(d["length"][order]) <= BUDGET
    kept = order[:int(fits.sum()) if fits.all() else int(np.argmin(fits))]
    cited, have = set(d["cited_ids"]), set()
    for k in kept:
        have.update(d["records"][k])
    return bool(d["gold"][order[0]]), len(cited & have) / d["cites"], int(d["gold"][order[:15]].sum())


thirds, metrics = {}, {}
sizes = []
for d in Q.values():
    gold, m = d["gold"], d["gold"].size
    tag_fit = d["tag_fit"].astype(np.float64)
    kth = np.sort(tag_fit, axis=1)[:, ::-1][:, min(5, tag_fit.shape[1]) - 1]
    picked_by = tag_fit >= kth[:, None] - 1e-12                   # query tags x tags
    picked = picked_by.any(axis=0)
    ec, et, values = d["edge_chunk"], d["edge_tag"], d["edge_values"].astype(np.float64)
    on = picked[et]
    by_tags = np.zeros(m, dtype=bool)
    by_tags[ec[on]] = True
    by_desc = WK.levels(np.asarray(d["description"], dtype=np.float64), 5) <= 2
    group = np.flatnonzero(by_tags & by_desc)
    sizes.append(group.size)
    parts = np.zeros(m)
    for i in range(tag_fit.shape[0]):
        touched = np.zeros(m, dtype=bool)
        touched[ec[picked_by[i][et]]] = True
        parts += touched
    mean_value, high_value = np.zeros((m, 5)), np.full((m, 5), -np.inf)
    counts = np.bincount(ec[on], minlength=m).astype(np.float64)
    for j in range(5):
        np.add.at(mean_value[:, j], ec[on], values[on, j])
        np.maximum.at(high_value[:, j], ec[on], values[on, j])
    mean_value /= np.maximum(counts, 1.)[:, None]
    plain = standing(d["tags"]) + standing(d["description"]) + standing(d["question"])
    base = np.lexsort((d["id_rank"], -plain)).tolist()
    deciders = {"the three routes added (as now)": plain,
                "how many different query tags touch the chunk": parts + plain / 1e3}
    for j, facet in enumerate(FACETS):
        deciders[f"{facet}, the mean over its picked edges"] = mean_value[:, j]
        deciders[f"{facet}, the highest of its picked edges"] = np.where(np.isfinite(high_value[:, j]), high_value[:, j], 0.)
    if group.size >= 3:
        four = sum(standing(mean_value[group, j]) for j in range(1, 5))
        full = np.zeros(m)
        full[group] = four
        deciders["the four ranking facets added, each on its own scale inside the group"] = full
        five = np.zeros(m)
        five[group] = four + standing(mean_value[group, 0])
        deciders["topic and the four added"] = five
    for name, value in deciders.items():
        inner = group[np.lexsort((d["id_rank"][group], -value[group]))]
        third = max(inner.size // 3, 1)
        row = thirds.setdefault(name, [0, 0, 0, 0])
        if inner.size >= 3:
            row[0] += int(gold[inner[:third]].sum())
            row[1] += third
            row[2] += int(gold[inner[-third:]].sum())
            row[3] += third
        seen = set(inner.tolist())
        order = inner.tolist() + [k for k in base if k not in seen]
        a, b, c = run(order, d)
        got = metrics.setdefault(name, [0, [], []])
        got[0] += int(a)
        got[1].append(b)
        got[2].append(c)

print(f"the group both sides touch: {np.mean(sizes):.1f} chunks a question")
print("share gold in the upper third | in the lower third || the group first in this order, then the rest: gold chunks in "
      "the first 15 (of 10) | first chunk gold (of 100) | context_recall_id")
for name, (ug, un, lg, ln) in thirds.items():
    first, recall, top15 = metrics[name]
    print(f"  {ug / max(un, 1):4.0%} | {lg / max(ln, 1):4.0%} || {np.mean(top15):.2f} | {first:3d} | {np.mean(recall):.3f}  {name}")

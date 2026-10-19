"""Round 33, after his 2026-10-12 "thats pretty bad placement": two faults were shown (round 32). A side
does not put the gold it touches at the front of what it touches, and adding the sides drags
down gold only one side touches. Here, ways to mend each, inside the question's product, the
hundred. No gold is used by any of them.

The tags' side, how a chunk's value is made from the query tags:
  closest       its closest tag to ANY query tag (as now)
  mean          the mean over the query tags of its closest tag to each
  own scale     each query tag put on its own scale over the product's chunks first, then added
  parts         how many different query tags pick a tag that sits on it (their five nearest of
                the product's tags), then the mean
  sure tags     the mean, each query tag weighted by how far its own first cluster stands above
                its second (a query tag that separates the chunks clearly counts for more)
The descriptions' side: against the query description; against the question without the
product's name; both added.
The join: added once each; each side weighted by how far ITS first cluster stands above its
second in this question; the better of a chunk's two places; the two sides in turn.

Printed: the gold chunks in the first 15 (of 10 a question), the first chunk gold (of 100),
context_recall_id (share of the cited records delivered inside 72,000 characters), and the
middle place of the gold touched by both sides, by the tags only, by the descriptions only."""
import pickle
import sys
from pathlib import Path

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

from explore import BUDGET, load, standing  # noqa: E402

HERE = Path(__file__).resolve().parent
Q = load()["questions"]
with open(HERE / "first_gold_signals_tags__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
for qid, d in Q.items():
    d.update(extra[qid])


def rows_standing(rows):
    rows = np.asarray(rows, dtype=np.float64)
    mid = np.median(rows, axis=1, keepdims=True)
    spread = 1.4826 * np.median(np.abs(rows - mid), axis=1, keepdims=True)
    return np.where(spread > 0, (rows - mid) / np.where(spread > 0, spread, 1.), 0.)


def separation(values):
    """How far the first of five clusters stands above the second, in units of the values' spread."""
    values = np.asarray(values, dtype=np.float64)
    level = WK.levels(values, 5)
    first, second = values[level == 1], values[level == 2]
    spread = 1.4826 * np.median(np.abs(values - np.median(values)))
    if not first.size or not second.size or spread <= 0:
        return 0.
    return float((first.mean() - second.mean()) / spread)


def sides(d):
    m = d["gold"].size
    fit = d["fit"].astype(np.float64)                         # query tags x chunks: the chunk's closest tag to that query tag
    tag_fit = d["tag_fit"].astype(np.float64)                 # query tags x the product's tags
    kth = np.sort(tag_fit, axis=1)[:, ::-1][:, min(5, tag_fit.shape[1]) - 1]
    picked = tag_fit >= kth[:, None] - 1e-12
    parts = np.zeros(m)
    for i in range(tag_fit.shape[0]):
        touched = np.zeros(m, dtype=bool)
        touched[d["edge_chunk"][picked[i][d["edge_tag"]]]] = True
        parts += touched
    weights = np.array([separation(row) for row in fit])
    weights = weights if weights.sum() > 0 else np.ones(fit.shape[0])
    tags = {
        "closest": fit.max(axis=0),
        "mean": fit.mean(axis=0),
        "own scale": rows_standing(fit).sum(axis=0),
        "parts": parts + fit.mean(axis=0),
        "sure tags": (weights[:, None] * fit).sum(axis=0) / weights.sum(),
    }
    descriptions = {
        "query description": np.asarray(d["description"], dtype=np.float64),
        "question without the name": np.asarray(d["question_bare"], dtype=np.float64),
        "both": standing(d["description"]) + standing(d["question_bare"]),
    }
    by_tags = parts > 0
    by_desc = WK.levels(np.asarray(d["description"], dtype=np.float64), 5) <= 2
    return tags, descriptions, by_tags, by_desc


def joined(t, s, how, d):
    zt, zs = standing(t), standing(s)
    if how == "added once each":
        return zt + zs
    if how == "each side weighted by its own separation":
        a, b = separation(t), separation(s)
        if a + b <= 0:
            return zt + zs
        return (a * zt + b * zs) / (a + b)
    place_t = np.empty(t.size)
    place_t[np.lexsort((d["id_rank"], -t))] = np.arange(t.size)
    place_s = np.empty(s.size)
    place_s[np.lexsort((d["id_rank"], -s))] = np.arange(s.size)
    if how == "the better of its two places":
        return -(np.minimum(place_t, place_s) + np.maximum(place_t, place_s) / 1e4)
    return -(np.minimum(2 * place_t, 2 * place_s + 1))            # the two sides in turn, the tags first


def run(score, d):
    order = np.lexsort((d["id_rank"], -np.asarray(score, dtype=np.float64)))
    fits = np.cumsum(d["length"][order]) <= BUDGET
    kept = order[:int(fits.sum()) if fits.all() else int(np.argmin(fits))]
    cited, have = set(d["cited_ids"]), set()
    for k in kept:
        have.update(d["records"][k])
    place = np.empty(order.size, dtype=np.int64)
    place[order] = np.arange(1, order.size + 1)
    return bool(d["gold"][order[0]]), len(cited & have) / d["cites"], int((place[d["gold"]] <= 15).sum()), place


rows = {}
for d in Q.values():
    tags, descriptions, by_tags, by_desc = sides(d)
    gold = d["gold"]
    groups = {"both": by_tags & by_desc & gold, "tags only": by_tags & ~by_desc & gold, "descriptions only": ~by_tags & by_desc & gold}
    tries = {f"the tags alone: {name}": value for name, value in tags.items()}
    tries.update({f"the descriptions alone: {name}": value for name, value in descriptions.items()})
    for t_name in ("closest", "mean", "parts", "sure tags"):
        for s_name in ("query description", "both"):
            for how in ("added once each", "each side weighted by its own separation", "the better of its two places", "the two sides in turn"):
                tries[f"tags ({t_name}) with descriptions ({s_name}), {how}"] = joined(tags[t_name], descriptions[s_name], how, d)
    for name, score in tries.items():
        first, recall, top15, place = run(score, d)
        row = rows.setdefault(name, [0, [], [], {g: [] for g in groups}])
        row[0] += int(first)
        row[1].append(recall)
        row[2].append(top15)
        for g, mask in groups.items():
            row[3][g] += place[mask].tolist()

print("gold chunks in the first 15 (of 10) | first chunk gold (of 100) | context_recall_id | the middle place of the gold touched "
      "by both, by the tags only, by the descriptions only")
for name, (first, recall, top15, where) in sorted(rows.items(), key=lambda kv: -np.mean(kv[1][2])):
    print(f"  {np.mean(top15):.2f} | {first:3d} | {np.mean(recall):.3f} | {np.median(where['both']):3.0f}, "
          f"{np.median(where['tags only']):3.0f}, {np.median(where['descriptions only']):3.0f}  {name}")

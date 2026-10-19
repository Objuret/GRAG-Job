"""Round 29, with the gold in hand, to size the one open thing: IF it were known which chunks of the
sure set are gold, what would his search from there reach inside 72,000 characters? Inside the
question's product, the hundred. The sure set is that of round 22. Not a retrieval: the first
step uses the gold.

  the sure set as it is (the cells)
  its gold chunks first, then the rest of it
  its gold chunks, then the chunks right above and under them, then the rest
  its gold chunks, then every chunk a pointer ties to them (above or under, a shared link, a
  shared conversation), then the rest
  the same, then also the chunks that share with them a tag sitting on 2 to 4 chunks
  its gold chunks, then the chunks nearest them by description (first cluster), then the rest
Printed: context_recall_id (share of the cited records delivered inside 72,000 characters) and
the gold chunks delivered a question."""
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


def run(order, d):
    order = np.asarray(order, dtype=np.int64)
    fits = np.cumsum(d["length"][order]) <= BUDGET
    kept = order[:int(fits.sum()) if fits.all() else int(np.argmin(fits))]
    cited, have = set(d["cited_ids"]), set()
    for k in kept:
        have.update(d["records"][k])
    return len(cited & have) / d["cites"], int(d["gold"][kept].sum()), int(kept.size)


rows = {}
for d in Q.values():
    D, T = np.asarray(d["description"], dtype=np.float64), np.asarray(d["tags"], dtype=np.float64)
    m, gold = D.size, d["gold"]
    step = WK.levels(D, 5) + WK.levels(T, 5)
    z = standing(D) + standing(T)
    hits = step <= 3 if (step <= 3).any() else step == step.min()
    scope = majority(hits, d["parent"])
    sure = (scope & (step <= 4)) | (~scope & (step == 2))
    cell = np.where(scope & (step == 2), 0, np.where(scope & (step == 3), 1, np.where(scope & (step == 4), 2,
                    np.where(~scope & (step == 2), 3, 9))))
    base = np.lexsort((d["id_rank"], -z, np.where(sure, cell, 9), ~sure)).tolist()
    at = {(int(p), int(s)): k for k, (p, s) in enumerate(zip(d["parent"], d["spot"]))}
    talks = [set(t) for t in d["talks"]]
    linked = [set() for _ in range(m)]
    for a, b in d["share_a_link"].tolist():
        linked[a].add(b)
        linked[b].add(a)
    tags_of = [set() for _ in range(m)]
    spread = {}
    for c, t in zip(d["edge_chunk"].tolist(), d["edge_tag"].tolist()):
        tags_of[c].add(t)
        spread[t] = spread.get(t, 0) + 1
    rare = [{t for t in tags if 2 <= spread[t] <= 4} for tags in tags_of]
    among = d["among"].astype(np.float64)
    known = [k for k in base if sure[k] and gold[k]]
    beside, pointed, tagged, near = set(), set(), set(), set()
    for g in known:
        p, s = int(d["parent"][g]), int(d["spot"][g])
        here = {at[(p, s + j)] for j in (-1, 1) if (p, s + j) in at}
        beside |= here
        pointed |= here | linked[g] | {k for k in range(m) if k != g and talks[k] & talks[g]}
        tagged |= {k for k in range(m) if k != g and rare[k] & rare[g]}
        others = np.array([k for k in range(m) if k != g])
        level = WK.levels(among[g][others], 5)
        near |= set(others[level == 1].tolist())

    def staged(*stages):
        seen, out = set(), []
        for stage in stages:
            for k in base:
                if k in stage and k not in seen:
                    seen.add(k)
                    out.append(k)
        return out + [k for k in base if k not in seen]

    orders = {
        "the sure set as it is (the cells), then the rest": base,
        "with the gold in hand: its gold chunks first, then the rest of it, then the rest": staged(set(known)),
        "its gold chunks, then the chunks right above and under them, then the rest": staged(set(known), beside),
        "its gold chunks, then every chunk a pointer ties to them, then the rest": staged(set(known), pointed),
        "its gold chunks, pointer-tied chunks, then chunks sharing a rare tag with them, then the rest": staged(set(known), pointed, tagged),
        "its gold chunks, then the chunks nearest them by description, then the rest": staged(set(known), near),
        "its gold chunks, pointer-tied chunks, then the chunks nearest them by description, then the rest": staged(set(known), pointed, near),
    }
    for name, order in orders.items():
        recall, golds, kept = run(order, d)
        row = rows.setdefault(name, [[], [], []])
        row[0].append(recall)
        row[1].append(golds)
        row[2].append(kept)

print("context_recall_id | gold chunks delivered a question (of 10.0) | chunks delivered a question")
for name, (recall, golds, kept) in rows.items():
    print(f"  {np.mean(recall):.3f} | {np.mean(golds):4.1f} | {np.mean(kept):4.1f}  {name}")

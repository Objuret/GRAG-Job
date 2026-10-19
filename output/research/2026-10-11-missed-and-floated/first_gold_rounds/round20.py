"""Round 20, his 2026-10-12 "take that last cloud combo style.. How does scope before or after affect
that?", done on HIS scope after the first answer took the product border for it ("You are really
beeing as fucking lazy as possible now"). His scope: the areas of the tree where the hits gather
(2026-10-07 "gauge where the truth seems to be, and can thus cut the others", "cluster by scope",
"keep minorities if same parents"; 2026-10-09 "what the majority has on their scope stats",
"If majority of something, BRANCH is chosen", "the definition maybe should be parent").

Inside the question's product, the hundred. A parent is a channel or a file; the kind (slack,
documents, meeting transcripts, pull requests, links, meeting chats) is the level above it.

The combo: the chunk descriptions' nearness and the tags' nearness each cut into five clusters
(`v4_walk.levels`); a chunk's step is its two levels added (2 = both in their first cluster).

The scope is gauged from a set of hits by three gauges, at the parent level and at the kind level:
  majority       the areas that hold the most hits, taken until they hold more than half of them
  first cluster  the areas clustered by the share of their chunks that are hits, the first cluster
  every          every area that holds a hit
SCOPE BEFORE  the hits are the chunk cloud (the descriptions' first cluster made in the whole
              product); the combo's clusters are then made from the scope's chunks only.
SCOPE AFTER   the combo is made in the whole product; the hits are its first step (both in their
              first cluster), or its first two steps; then the scope cuts, or goes first.

Printed per variant: areas and chunks the scope keeps; the share of the question's gold chunks it
keeps beside the share of the product's chunks it is; the share of the scope's chunks that are
gold; the first chunk gold (of 100) and context_recall_id (share of the cited records delivered
inside 72,000 characters) with the scope as a cut (nothing outside it is delivered) and with the
scope first (the rest after it)."""
import sys

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

from explore import BUDGET, load, standing  # noqa: E402

data = load()
Q = data["questions"]
PARENTS = data["parent_names"]
KIND_OF = {}


def kind_index(name):
    parts = name.split(".")
    label = parts[2] if len(parts) > 2 else name
    return KIND_OF.setdefault(label, len(KIND_OF))


def areas_of(d, level):
    if level == "parent":
        return d["parent"]
    return np.array([kind_index(PARENTS[int(p)]) for p in d["parent"]])


def gauge(hits, areas, how):
    """The areas the gauge picks, as a mask over the chunks."""
    ids = np.unique(areas)
    held = np.array([int(hits[areas == a].sum()) for a in ids])
    size = np.array([int((areas == a).sum()) for a in ids])
    if not held.sum():
        return np.ones(areas.size, dtype=bool), ids.size
    if how == "every":
        picked = ids[held > 0]
    elif how == "majority":
        order = np.lexsort((ids, -held))
        taken, total = [], 0
        for k in order:
            taken.append(ids[k])
            total += held[k]
            if total * 2 > held.sum():
                break
        picked = np.array(taken)
    else:
        share = held / size
        picked = ids[WK.levels(share, min(5, ids.size)) == 1] if ids.size > 1 else ids
    return np.isin(areas, picked), int(picked.size)


def combo(D, T, members):
    """Levels made from the member chunks only; returns the step (levels added) and the two standings."""
    step = np.full(D.size, 99.)
    z = np.zeros(D.size)
    if members.sum() >= 2:
        lD, lT = WK.levels(D[members], 5), WK.levels(T[members], 5)
        step[members] = lD + lT
        z[members] = standing(D[members]) + standing(T[members])
    elif members.sum() == 1:
        step[members] = 2
    return step, z


def run(order, d):
    order = np.asarray(order, dtype=np.int64)
    if not order.size:
        return False, 0.
    fits = np.cumsum(d["length"][order]) <= BUDGET
    kept = order[:int(fits.sum()) if fits.all() else int(np.argmin(fits))]
    cited, have = set(d["cited_ids"]), set()
    for k in kept:
        have.update(d["records"][k])
    return bool(d["gold"][order[0]]), len(cited & have) / d["cites"]


rows = {}


def note(name, d, scope, n_areas, cut_order, first_order):
    row = rows.setdefault(name, {"areas": [], "chunks": [], "gold kept": [], "product share": [], "scope gold": [0, 0],
                                 "cut first": 0, "cut recall": [], "lead first": 0, "lead recall": []})
    gold = d["gold"]
    row["areas"].append(n_areas)
    row["chunks"].append(int(scope.sum()))
    row["gold kept"].append(float(gold[scope].sum() / gold.sum()))
    row["product share"].append(float(scope.mean()))
    row["scope gold"][0] += int(scope.sum())
    row["scope gold"][1] += int(gold[scope].sum())
    a, b = run(cut_order, d)
    row["cut first"] += int(a)
    row["cut recall"].append(b)
    a, b = run(first_order, d)
    row["lead first"] += int(a)
    row["lead recall"].append(b)


for d in Q.values():
    D, T = np.asarray(d["description"], dtype=np.float64), np.asarray(d["tags"], dtype=np.float64)
    m = D.size
    everything = np.ones(m, dtype=bool)
    step_all, z_all = combo(D, T, everything)
    base = np.lexsort((d["id_rank"], -z_all, step_all))
    note("no scope below the product: the combo as it is", d, everything, len(np.unique(d["parent"])), base, base)
    cloud = WK.levels(D, 5) == 1
    for level in ("parent", "kind"):
        areas = areas_of(d, level)
        for how in ("majority", "first cluster", "every"):
            # scope before: gauged from the chunk cloud, the combo made inside the scope
            scope, n_areas = gauge(cloud, areas, how)
            step, z = combo(D, T, scope)
            inside = np.flatnonzero(scope)
            cut = inside[np.lexsort((d["id_rank"][inside], -z[inside], step[inside]))]
            rest = np.array([k for k in base if not scope[k]], dtype=np.int64)
            note(f"BEFORE | {level} | {how} | hits: the chunk cloud", d, scope, n_areas, cut, np.concatenate([cut, rest]))
            # scope after: the combo first, the scope gauged from its top step(s)
            for label, hits in (("its first step", step_all == 2), ("its first two steps", step_all <= 3)):
                if not hits.any():
                    hits = step_all == step_all.min()
                scope, n_areas = gauge(hits, areas, how)
                inside = np.array([k for k in base if scope[k]], dtype=np.int64)
                rest = np.array([k for k in base if not scope[k]], dtype=np.int64)
                note(f"AFTER  | {level} | {how} | hits: {label}", d, scope, n_areas, inside, np.concatenate([inside, rest]))

print("areas the scope keeps (the middle) | chunks it keeps (the middle) | share of the question's gold chunks it keeps | "
      "share of the product's chunks it is | share of the scope's chunks that are gold || as a cut: first chunk gold "
      "(of 100) | context_recall_id || scope first, the rest after: first chunk gold | context_recall_id")
for name, row in rows.items():
    chunks, gold = row["scope gold"]
    print(f"  {np.median(row['areas']):4.0f} | {np.median(row['chunks']):4.0f} | {np.mean(row['gold kept']):4.0%} | "
          f"{np.mean(row['product share']):4.0%} | {gold / chunks:4.0%} || {row['cut first']:3d} | "
          f"{np.mean(row['cut recall']):.3f} || {row['lead first']:3d} | {np.mean(row['lead recall']):.3f}  {name}")

"""Round 21, the rest of his scope before or after the cloud combo (2026-10-12), inside the question's
product, the hundred. The combo and the gauges are those of round 20; the scope here is the
majority's parents (the parents that hold the most hits, taken until they hold more than half).

  1  the combo's steps inside the scope and outside it: chunks a question and the share of them
     that is gold, for the scope gauged BEFORE (from the chunk cloud) and AFTER (from the combo's
     first step; from its first two steps)
  2  his "keep minorities if same parents": the hits outside the majority's parents are kept too
     when they sit under the same kind as one of them
  3  his "the clouds give extra weight to specific areas of the scope": the scope not as a cut
     but as weight, a chunk in the scope moved up one step, or two
  4  scope before AND after: the scope gauged from the chunk cloud, the combo made inside it, the
     scope gauged again from that combo's first step
  5  the same with the chunk side made from the question without the product's name

Printed for 2 to 5: chunks the scope keeps, the share of the question's gold chunks it keeps
beside the share of the product's chunks it is, the first chunk gold (of 100), context_recall_id
(share of the cited records delivered inside 72,000 characters)."""
import sys

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

from explore import BUDGET, load, standing  # noqa: E402

data = load()
Q = data["questions"]
PARENTS = data["parent_names"]
STEPS = ((2, "both in their first cluster"), (3, "one in its first, the other in its second"),
         (4, "both in their second, or first and third"), (99, "everywhere else"))


def kind_of(d):
    labels = {}
    return np.array([labels.setdefault(PARENTS[int(p)].split(".")[2], len(labels)) for p in d["parent"]])


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


def combo(D, T, members):
    step, z = np.full(D.size, 99.), np.zeros(D.size)
    if members.sum() >= 2:
        step[members] = WK.levels(D[members], 5) + WK.levels(T[members], 5)
        z[members] = standing(D[members]) + standing(T[members])
    elif members.sum() == 1:
        step[members] = 2
    return step, z


def run(order, d):
    order = np.asarray(order, dtype=np.int64)
    fits = np.cumsum(d["length"][order]) <= BUDGET
    kept = order[:int(fits.sum()) if fits.all() else int(np.argmin(fits))]
    cited, have = set(d["cited_ids"]), set()
    for k in kept:
        have.update(d["records"][k])
    return bool(d["gold"][order[0]]), len(cited & have) / d["cites"]


grid = {}
rows = {}


def note(name, d, scope, order):
    row = rows.setdefault(name, {"chunks": [], "gold kept": [], "share": [], "first": 0, "recall": []})
    row["chunks"].append(int(scope.sum()))
    row["gold kept"].append(float(d["gold"][scope].sum() / d["gold"].sum()))
    row["share"].append(float(scope.mean()))
    a, b = run(order, d)
    row["first"] += int(a)
    row["recall"].append(b)


def ordered(d, step, z, lead=None):
    key = step if lead is None else step - lead
    return np.lexsort((d["id_rank"], -z, key))


for d in Q.values():
    m = d["gold"].size
    everything = np.ones(m, dtype=bool)
    parents, kinds = d["parent"], kind_of(d)
    for side, D in (("the query description", np.asarray(d["description"], dtype=np.float64)),
                    ("the question without the name", np.asarray(d["question_bare"], dtype=np.float64))):
        T = np.asarray(d["tags"], dtype=np.float64)
        step, z = combo(D, T, everything)
        base = ordered(d, step, z)
        cloud = WK.levels(D, 5) == 1
        scopes = {"BEFORE, gauged from the chunk cloud": majority(cloud, parents),
                  "AFTER, gauged from the combo's first step": majority(step == 2 if (step == 2).any() else step == step.min(), parents),
                  "AFTER, gauged from the combo's first two steps": majority(step <= 3 if (step <= 3).any() else step == step.min(), parents)}
        if side == "the query description":
            note("no scope below the product, the combo as it is", d, everything, base)
            for scope_name, scope in scopes.items():
                for value, label in STEPS:
                    mask = (step == value) if value != 99 else (step > 4)
                    for where, part in (("inside the scope", mask & scope), ("outside it", mask & ~scope)):
                        cell = grid.setdefault((scope_name, label, where), [0, 0])
                        cell[0] += int(part.sum())
                        cell[1] += int(d["gold"][part].sum())
        tag = "" if side == "the query description" else " [chunk side: the question without the name]"
        if side != "the query description":
            note("no scope below the product, the combo as it is" + tag, d, everything, base)
        after = scopes["AFTER, gauged from the combo's first two steps"]
        hits = step <= 3 if (step <= 3).any() else step == step.min()
        # 2: minorities kept when under the same kind as a majority parent
        same_kind = np.isin(kinds, np.unique(kinds[after]))
        wider = after | (hits & same_kind)
        note("2: the majority's parents after the combo, as a cut" + tag, d, after, np.array([k for k in base if after[k]]))
        note("2: the same, with the hits outside them kept when under the same kind" + tag, d, wider,
             np.array([k for k in base if wider[k]]))
        # 3: the scope as weight
        for lift in (1., 2.):
            note(f"3: the scope as weight, a chunk in it moved up {lift:.0f} step(s)" + tag, d, after,
                 ordered(d, step, z, lead=lift * after))
        note("3: the scope first (every chunk of it before the rest)" + tag, d, after,
             np.concatenate([[k for k in base if after[k]], [k for k in base if not after[k]]]).astype(np.int64))
        # 4: scope before and after
        before = scopes["BEFORE, gauged from the chunk cloud"]
        step_in, z_in = combo(D, T, before)
        again = majority((step_in == 2) if (step_in == 2).any() else (step_in == step_in.min()), parents) & before
        inner = ordered(d, step_in, z_in)
        note("4: scope before, the combo inside it, scope again from its first step; the rest after" + tag, d, again,
             np.concatenate([[k for k in inner if again[k]], [k for k in inner if before[k] and not again[k]],
                             [k for k in base if not before[k]]]).astype(np.int64))

count = len(Q)
print("== 1: the combo's steps inside the scope and outside it (the majority's parents): chunks a question, share of them gold ==")
last = None
for (scope_name, label, where), (chunks, gold) in grid.items():
    if scope_name != last:
        print(f"  -- scope {scope_name} --")
        last = scope_name
    print(f"     {label}, {where}: {chunks / count:.1f} chunks, {gold / max(chunks, 1):.0%} gold")
print("\n== 2 to 5: chunks the scope keeps (the middle) | share of the gold chunks it keeps | share of the product's chunks "
      "it is | first chunk gold (of 100) | context_recall_id ==")
for name, row in rows.items():
    print(f"  {np.median(row['chunks']):4.0f} | {np.mean(row['gold kept']):4.0%} | {np.mean(row['share']):4.0%} | "
          f"{row['first']:3d} | {np.mean(row['recall']):.3f}  {name}")

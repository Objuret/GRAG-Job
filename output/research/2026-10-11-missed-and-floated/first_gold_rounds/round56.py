"""Round 56, under his 2026-10-12 goal "solve this" (the order): round 53 again with the own
conversations and own pull requests embedded from text in which every own name of the product
is read as "the product" (`own_units_without_names.py`), as the question is. Set VECTORS to the
file of vectors. The hundred, inside the question's product, numbers only.
"""
import json
import pickle
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

import ties as TI  # noqa: E402
from explore import BUDGET, load, standing  # noqa: E402

HERE = Path(__file__).resolve().parent
OWN = Path(r"C:\Coding\exjobbet\GRAG-Job\output\research\2026-10-11-missed-and-floated\own_units")
T = load()
Q, KINDS = T["questions"], T["kind_names"]
with open(HERE / "first_gold_signals_tags__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
PARTS = ("document_part", "meeting_transcript_part")
rows = [json.loads(line) for line in open(OWN / "own_units.jsonl", encoding="utf-8")]
import os
kept = np.load(OWN / os.environ.get("VECTORS", "own_units_query.npz"), allow_pickle=True)
assert [str(x) for x in kept["ids"]] == [row["id"] for row in rows]
matrix = np.asarray(kept["matrix"], dtype=np.float32)
unit_of_record = {}
for at, row in enumerate(rows):
    for r in row["records"]:
        unit_of_record[r] = at


def hand_over(units, cited, cites):
    used, got, first, n = 0, set(), None, 0
    for records, chars, part in units:
        new = [r for r in records if r not in got]
        if not new and not part:
            continue
        if used + chars > BUDGET:
            break
        used += chars
        got.update(records)
        n += 1
        if first is None:
            first = bool(cited & set(records))
    return bool(first), len(cited & got) / cites, n


def length_of(records, P):
    return sum(P["size"][r] for r in records) + max(len(records) - 1, 0)


results = defaultdict(list)
for qid, d in Q.items():
    d.update(extra[qid])
    P = TI.product(qid.split("::")[0])
    m = d["gold"].size
    D, Tg = np.asarray(d["question_bare"], dtype=np.float64), np.asarray(d["tags"], dtype=np.float64)
    lT = WK.levels(Tg, 5)
    step = (WK.levels(D, 5) + lT).astype(np.float64)
    z = standing(D) + standing(Tg)
    hits = step <= 3 if (step <= 3).any() else step == step.min()
    ids = np.unique(d["parent"])
    held = np.array([int(hits[d["parent"] == a].sum()) for a in ids])
    total, last = 0, None
    for at in np.lexsort((ids, -held)):
        total += int(held[at])
        last = int(held[at])
        if total * 2 > int(held.sum()):
            break
    scope = np.isin(d["parent"], ids[held >= last])
    order = np.lexsort((d["id_rank"], -z, ~scope, step))
    place = np.empty(m, dtype=np.int64)
    place[order] = np.arange(m)
    cited, cites = set(d["cited_ids"]), d["cites"]
    kind = [KINDS[x] for x in d["kind"]]
    own = [[r for r in d["records"][k] if not TI.apart(r, P)] for k in range(m)]
    chunk_len = d["length"].astype(np.int64)
    bare = np.asarray(d["bare_vector"], dtype=np.float32)
    # the units: (records, characters, part, best chunk, own nearness)
    units, by_unit = [], {}
    for k in sorted(range(m), key=lambda k: (int(d["parent"][k]), int(d["id_rank"][k]))):
        if kind[k] in ("slack_thread_batch", "pr_batch"):
            for r in own[k]:
                u = unit_of_record[r]
                if u not in by_unit:
                    by_unit[u] = len(units)
                    units.append([list(rows[u]["records"]), None, False, k, float(matrix[u] @ bare)])
                elif place[k] < place[units[by_unit[u]][3]]:
                    units[by_unit[u]][3] = k
        elif own[k]:
            size = int(chunk_len[k]) if kind[k] in PARTS or len(own[k]) == len(d["records"][k]) else length_of(own[k], P)
            units.append([own[k], size, kind[k] in PARTS, k, float(D[k])])
    for u in units:
        if u[1] is None:
            u[1] = length_of(u[0], P)
    best = np.array([u[3] for u in units])
    near = np.array([u[4] for u in units])
    spot = np.arange(len(units))
    send = lambda by: hand_over(((units[i][0], units[i][1], units[i][2]) for i in by.tolist()), cited, cites)  # noqa: E731
    results["U1  the combo order as built, whole own conversations as their chunks show"].append(send(np.lexsort((spot, place[best]))))
    results["U2  every unit by its own nearness alone"].append(send(np.lexsort((spot, -near))))
    both = standing(near) + standing(z[best])
    results["U3  own nearness and the combo's value of its best chunk, as standings, added"].append(send(np.lexsort((spot, -both))))
    step_u = (WK.levels(near, 5) + lT[best]).astype(np.float64)
    z_u = standing(near) + standing(Tg[best])
    results["U4  the combo with the unit's own nearness in place of the chunk description"].append(
        send(np.lexsort((spot, -z_u, ~scope[best], step_u))))
    results["U5  U1, the conversations of one chunk in the order of their own nearness"].append(
        send(np.lexsort((spot, -near, place[best]))))

print("units handed over, a question | first handed over holds a cited record (of 100) | context_recall_id")
base = np.array([r[1] for r in results["U1  the combo order as built, whole own conversations as their chunks show"]])
for name, got in results.items():
    a = np.array(got, dtype=np.float64)
    diff = a[:, 1] - base
    print(f"  {a[:, 2].mean():5.1f} | {int(a[:, 0].sum()):3d} | {a[:, 1].mean():.3f}  {name}"
          + ("" if name.startswith("U1") else f"   [against U1: {diff.mean():+.3f}, standard error {diff.std(ddof=1) / 10:.3f}, "
             f"higher on {int((diff > 1e-9).sum())}, lower on {int((diff < -1e-9).sum())}]"))

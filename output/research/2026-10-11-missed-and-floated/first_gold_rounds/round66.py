"""Round 66, under his 2026-10-12 goal "solve this" (the order): what a reader of the hits gives. The
facet instrument's backbone (the reranker gte-reranker-modernbert-base, on the desktop, no lane
call) read every (question without the product's name, unit) pair of the hundred
(`reader_pairs.py`): a unit is an own conversation whole, an own pull request, or any other
chunk as the arm hands it over. A side measurement: a reader in the artefact is "more ai",
which he ruled out; this says what that route is worth. The hundred, numbers only.

  U1  the combo order as built, whole own conversations as their chunks show
  R1  every unit by the reader's score alone
  R2  the reader's standing and the combo's standing of the unit's best chunk, added
  R3  the combo's step and scope of the best chunk first, the reader inside
  R4  the units the combo puts first, as many as fill 72,000 characters twice over, in the
      reader's order; the rest as the combo has them
first unit holds a cited record | a cited record among the first three | context_recall_id
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
RES = Path(r"C:\Coding\exjobbet\GRAG-Job\output\research\2026-10-11-missed-and-floated")
T = load()
Q, KINDS = T["questions"], T["kind_names"]
with open(HERE / "first_gold_signals_tags__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
with open(HERE / "what_a_chunk_holds.pkl", "rb") as handle:
    chunk_ids = pickle.load(handle)["chunk_ids"]
PARTS = ("document_part", "meeting_transcript_part")
rows = [json.loads(line) for line in open(RES / "own_units" / "own_units.jsonl", encoding="utf-8")]
unit_of_record = {}
for row in rows:
    for r in row["records"]:
        unit_of_record[r] = row["id"]
records_of_unit = {row["id"]: list(row["records"]) for row in rows}
got = np.load(sys.argv[1], allow_pickle=False)
score = dict(zip((str(e) for e in got["edge_id"]), got["native_logit"].astype(np.float64).reshape(len(got["edge_id"]), -1)[:, 0]))
print(f"{len(score)} pairs read; cut short by the reader's length: {int(got['truncated'].sum())}")


def hand_over(units, cited, cites):
    used, seen, first, three, n = 0, set(), None, False, 0
    for records, chars, part in units:
        new = [r for r in records if r not in seen]
        if not new and not part:
            continue
        if used + chars > BUDGET:
            break
        used += chars
        seen.update(records)
        n += 1
        hit = bool(cited & set(records))
        if first is None:
            first = hit
        if n <= 3:
            three = three or hit
    return bool(first), three, len(cited & seen) / cites


def length_of(records, P):
    return sum(P["size"][r] for r in records) + max(len(records) - 1, 0)


results = defaultdict(list)
missing = 0
for qid, d in Q.items():
    d.update(extra[qid])
    P = TI.product(qid.split("::")[0])
    m = d["gold"].size
    D, Tg = np.asarray(d["question_bare"], dtype=np.float64), np.asarray(d["tags"], dtype=np.float64)
    step = (WK.levels(D, 5) + WK.levels(Tg, 5)).astype(np.float64)
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
    units, by_unit = [], {}
    for k in sorted(range(m), key=lambda k: (int(d["parent"][k]), int(d["id_rank"][k]))):
        if kind[k] in ("slack_thread_batch", "pr_batch"):
            for r in own[k]:
                u = unit_of_record[r]
                if u not in by_unit:
                    by_unit[u] = len(units)
                    units.append([records_of_unit[u], None, False, k, u])
                elif place[k] < place[units[by_unit[u]][3]]:
                    units[by_unit[u]][3] = k
        elif own[k]:
            size = int(chunk_len[k]) if kind[k] in PARTS or len(own[k]) == len(d["records"][k]) else length_of(own[k], P)
            units.append([own[k], size, kind[k] in PARTS, k, f"chunk|{chunk_ids[int(d['chunks'][k])]}"])
    for u in units:
        if u[1] is None:
            u[1] = length_of(u[0], P)
    read = np.array([score.get(f"{qid}||{u[4]}", np.nan) for u in units])
    missing += int(np.isnan(read).sum())
    read = np.where(np.isnan(read), np.nanmin(read), read)
    best = np.array([u[3] for u in units])
    spot = np.arange(len(units))
    send = lambda by: hand_over(((units[i][0], units[i][1], units[i][2]) for i in by.tolist()), cited, cites)  # noqa: E731
    c_order = np.lexsort((spot, place[best]))
    results["U1  the combo order as built, whole own conversations"].append(send(c_order))
    results["R1  every unit by the reader's score alone"].append(send(np.lexsort((spot, -read))))
    both = standing(read) + standing(z[best])
    results["R2  the reader's standing and the combo's, added"].append(send(np.lexsort((spot, -both))))
    results["R3  the combo's step and scope first, the reader inside"].append(
        send(np.lexsort((spot, -read, ~scope[best], step[best]))))
    used, top = 0, []
    for i in c_order.tolist():
        if used + units[i][1] > 2 * BUDGET:
            break
        used += units[i][1]
        top.append(i)
    top = np.array(top, dtype=np.int64)
    rest = np.array([i for i in c_order.tolist() if i not in set(top.tolist())], dtype=np.int64)
    results["R4  the combo's first units (twice the budget) in the reader's order"].append(
        send(np.concatenate([top[np.argsort(-read[top], kind="stable")], rest])))

print(f"pairs with no score: {missing}")
print("first unit holds a cited record (of 100) | a cited record among the first three | context_recall_id")
base = np.array([r[2] for r in results["U1  the combo order as built, whole own conversations"]])
for name, rows_ in results.items():
    a = np.array(rows_, dtype=np.float64)
    diff = a[:, 2] - base
    print(f"  {int(a[:, 0].sum()):3d} | {int(a[:, 1].sum()):3d} | {a[:, 2].mean():.3f}  {name}"
          + ("" if name.startswith("U1") else f"   [{diff.mean():+.3f}, standard error {diff.std(ddof=1) / 10:.3f}, higher on "
             f"{int((diff > 1e-9).sum())}, lower on {int((diff < -1e-9).sum())}]"))

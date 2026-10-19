"""Round 67, under his 2026-10-12 goal "solve this" (the order): everything that moved the first unit,
put together, to see where the order tops out on the hundred with the means measured: the
company's scope (the graph: Customer-[company]->Company, round 63) and the local reader
(round 66). A side count; the reader is "more ai" and not in the arm. A unit is one own
conversation whole, an own pull request, or any other chunk. The hundred, numbers only.

  U1  the combo order as built
  K1  the company's scope first (the conversations naming a customer of a company the question
      names), then the combo order
  K2  the combo's first units (twice the budget) in the reader's order
  K3  the company's scope first, in the reader's order; then K2
first unit holds a cited record | among the first three | context_recall_id
"""
import json
import pickle
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO = Path("C:/Coding/exjobbet/GRAG-Job")
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

import ties as TI  # noqa: E402
from explore import BUDGET, load, standing  # noqa: E402

HERE = Path(__file__).resolve().parent
RES = REPO / "output/research/2026-10-11-missed-and-floated"
T = load()
Q, KINDS = T["questions"], T["kind_names"]
with open(HERE / "first_gold_signals_tags__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
with open(HERE / "what_a_chunk_holds.pkl", "rb") as handle:
    chunk_ids = pickle.load(handle)["chunk_ids"]
PARTS = ("document_part", "meeting_transcript_part")
CUST = re.compile(r"CUST-\d+")
rows = [json.loads(line) for line in open(RES / "own_units" / "own_units.jsonl", encoding="utf-8")]
unit_of_record = {r: row["id"] for row in rows for r in row["records"]}
records_of_unit = {row["id"]: list(row["records"]) for row in rows}
got = np.load(RES / "reader" / "reader__gold100.npz", allow_pickle=False)
score = dict(zip((str(e) for e in got["edge_id"]), got["native_logit"].astype(np.float64).reshape(len(got["edge_id"]), -1)[:, 0]))
asked = {q.id: q.question for q in HQ.load_questions()}
customers = json.loads((REPO / "data/raw/Salesforce__HERB/metadata/customers_data.json").read_text(encoding="utf-8"))


def plain(text):
    return " " + re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip() + " "


of_company = defaultdict(set)
for row in customers:
    of_company[plain(row["company"])].add(row["id"])


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
    read = np.array([score[f"{qid}||{u[4]}"] for u in units])
    best = np.array([u[3] for u in units])
    spot = np.arange(len(units))
    words = plain(asked[qid])
    wanted = set().union(*[of_company[name] for name in of_company if name in words])
    named = np.array([u[4].startswith("talk|") and bool(wanted & {c for r in u[0] for c in CUST.findall(
        P["raw"][r][1]["Message"]["User"]["text"])}) for u in units])
    send = lambda by: hand_over(((units[i][0], units[i][1], units[i][2]) for i in by.tolist()), cited, cites)  # noqa: E731
    c_order = np.lexsort((spot, place[best]))
    results["U1  the combo order as built"].append(send(c_order))
    results["K1  the company's scope first, then the combo order"].append(send(np.lexsort((spot, place[best], ~named))))

    def top_by_reader(pool):
        used, top = 0, []
        for i in pool:
            if used + units[i][1] > 2 * BUDGET:
                break
            used += units[i][1]
            top.append(i)
        top = np.array(top, dtype=np.int64)
        rest = np.array([i for i in pool if i not in set(top.tolist())], dtype=np.int64)
        return np.concatenate([top[np.argsort(-read[top], kind="stable")], rest]) if top.size else rest

    results["K2  the combo's first units in the reader's order"].append(send(top_by_reader(c_order.tolist())))
    first = np.array([i for i in c_order.tolist() if named[i]], dtype=np.int64)
    first = first[np.argsort(-read[first], kind="stable")] if first.size else first
    rest = top_by_reader([i for i in c_order.tolist() if not named[i]])
    results["K3  the company's scope first in the reader's order, then K2"].append(send(np.concatenate([first, rest])))

print("first unit holds a cited record (of 100) | a cited record among the first three | context_recall_id")
base = np.array([r[2] for r in results["U1  the combo order as built"]])
for name, rows_ in results.items():
    a = np.array(rows_, dtype=np.float64)
    diff = a[:, 2] - base
    print(f"  {int(a[:, 0].sum()):3d} | {int(a[:, 1].sum()):3d} | {a[:, 2].mean():.3f}  {name}"
          + ("" if name.startswith("U1") else f"   [{diff.mean():+.3f}, standard error {diff.std(ddof=1) / 10:.3f}, higher on "
             f"{int((diff > 1e-9).sum())}, lower on {int((diff < -1e-9).sum())}]"))

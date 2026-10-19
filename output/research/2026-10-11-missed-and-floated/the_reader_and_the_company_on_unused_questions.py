"""For his 2026-10-12 goal "solve this" (the order): the two things that moved the first unit on the
hundred (`first_gold_rounds/round67`), checked on the 300 unused questions, where a company is
named on 4% of the questions and not 18%: the company's scope (Customer-[company]->Company in
the graph; the messages name a customer by its id) and the local reader (the facet instrument's
backbone, `reader_pairs.py`, the desktop's GPU, no lane call). The order is the one made with no
model call (the combo and the scope, the question without the product's name). A unit is one
own conversation whole, an own pull request, or any other chunk as the arm hands it over. A
side count: the reader is "more ai" and is not in the arm. The gold ids are read inside;
numbers only.

  U1  the order with no model call
  K1  the company's scope first, then that order
  K2  the order's first units (twice the budget) in the reader's order
  K3  the company's scope first in the reader's order, then K2

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/the_reader_and_the_company_on_unused_questions.py <set> <npz>
"""
import json
import os
import random
import re
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test"), str(HERE / "first_gold_rounds")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"
os.environ["HERB_V4_SCOPE_STEP"] = "both"

import ties as TI  # noqa: E402
from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET, NPZ = sys.argv[1], Path(sys.argv[2])
BUDGET = 72000
CLUSTERS = 5
CUST = re.compile(r"CUST-\d+")
ids_of = {name: {json.loads(line)["id"] for line in (REPO / "data" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
                 if line.strip()} for name in ("gold100", "heldout100")}
every = HQ.load_questions()
if SET == "gold100":
    drawn = [q for q in every if q.id in ids_of["gold100"]]
else:
    fresh = sorted((q for q in every if q.id not in ids_of["gold100"] | ids_of["heldout100"] and q.citations), key=lambda q: q.id)
    drawn = random.Random(20261011).sample(fresh, 300)
got = np.load(NPZ, allow_pickle=False)
score = dict(zip((str(e) for e in got["edge_id"]), got["native_logit"].astype(np.float64).reshape(len(got["edge_id"]), -1)[:, 0]))
customers = json.loads((REPO / "data/raw/Salesforce__HERB/metadata/customers_data.json").read_text(encoding="utf-8"))


def plain(text):
    return " " + re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip() + " "


of_company = defaultdict(set)
for row in customers:
    of_company[plain(row["company"])].add(row["id"])
own_rows = [json.loads(line) for line in open(HERE / "own_units" / "own_units.jsonl", encoding="utf-8")]
unit_of_record = {r: row["id"] for row in own_rows for r in row["records"]}
records_of_unit = {row["id"]: list(row["records"]) for row in own_rows}
p = V.prepare_over_corpus("the reader and the company")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
et, ec = layer["edge_tag"], layer["edge_chunk"]
parents = [str(row["parent"]) for row in p.chunk_rows]
parent_ids = {name: k for k, name in enumerate(sorted(set(parents)))}
parent_of = np.array([parent_ids[name] for name in parents], dtype=np.int64)
product_of = [name.split(".")[1] for name in parents]
CV = np.asarray(p.chunk_vectors, dtype=np.float64)
TV = np.asarray(p.tag_vectors, dtype=np.float64)
AXES = V._QueryAxes(TV, np.eye(CV.shape[1]))
doc_cache = {}
records, length, is_part = [], np.zeros(n, dtype=np.int64), np.zeros(n, dtype=bool)
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, doc_cache)
    records.append([str(x) for x in ids])
    length[i] = len(text)
    is_part[i] = "char_range" in json.loads(row["locator"])
print(f"prepared; {len(drawn)} questions, {len(score)} pairs read", flush=True)


def standing(x):
    x = np.asarray(x, dtype=np.float64)
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


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


def closest_tag(vector):
    row = vector @ TV.T
    out = np.full(n, float(row.min()))
    np.maximum.at(out, ec, row[et])
    return out


def length_of(ids, P):
    return sum(P["size"][r] for r in ids) + max(len(ids) - 1, 0)


def hand_over(units, cites):
    used, seen, first, three, count = 0, set(), None, False, 0
    for ids, chars, part in units:
        new = [r for r in ids if r not in seen]
        if not new and not part:
            continue
        if used + chars > BUDGET:
            break
        used += chars
        seen.update(ids)
        count += 1
        hit = bool(cites & set(ids))
        if first is None:
            first = hit
        if count <= 3:
            three = three or hit
    return bool(first), three, len(cites & seen) / len(cites)


WAYS = ("U1  the order with no model call", "K1  the company's scope first, then that order",
        "K2  the order's first units in the reader's order", "K3  the company's scope first in the reader's order, then K2")
results = {way: [] for way in WAYS}
types, with_company, unread = [], [], 0
for q in drawn:
    border, scope = V.scope_by_name(q.question, p.tree, n)
    names = scope["names_in_the_question"]
    if len(names) != 1:
        continue
    inside = np.flatnonzero(border)
    cites = {str(c) for c in q.citations}
    P = TI.product(product_of[int(inside[0])])
    bare = V._without_names(q.question, names)
    vector = np.asarray(V._query_cosines(bare, [], AXES)[0]["query_description_cosines"], dtype=np.float64)
    D, T = (CV @ vector)[inside], closest_tag(vector)[inside]
    step = (WK.levels(D, CLUSTERS) + WK.levels(T, CLUSTERS)).astype(np.float64)
    z = standing(D) + standing(T)
    in_scope = majority(step <= 3 if (step <= 3).any() else step == step.min(), parent_of[inside])
    order = inside[np.lexsort((id_rank[inside], -z, ~in_scope, step))].tolist()
    place = {i: at for at, i in enumerate(order)}
    units, by_unit = [], {}
    for i in sorted(order, key=lambda i: (parents[i], int(id_rank[i]))):
        own = [r for r in records[i] if not TI.apart(r, P)]
        if own and own[0] in unit_of_record and not is_part[i]:
            for r in own:
                u = unit_of_record[r]
                if u not in by_unit:
                    by_unit[u] = len(units)
                    rs = records_of_unit[u]
                    units.append([rs, length_of(rs, P), False, i, u])
                elif place[i] < place[units[by_unit[u]][3]]:
                    units[by_unit[u]][3] = i
        elif own:
            size = int(length[i]) if is_part[i] or len(own) == len(records[i]) else length_of(own, P)
            units.append([own, size, bool(is_part[i]), i, f"chunk|{p.chunk_ids[i]}"])
    read = np.array([score.get(f"{q.id}||{u[4]}", np.nan) for u in units])
    unread += int(np.isnan(read).sum())
    read = np.where(np.isnan(read), np.nanmin(read), read)
    best = np.array([place[u[3]] for u in units])
    spot = np.arange(len(units))
    words = plain(bare)
    wanted = set().union(*[of_company[name] for name in of_company if name in words])
    named = np.array([u[4].startswith("talk|") and bool(wanted & {c for r in u[0] for c in CUST.findall(
        P["raw"][r][1]["Message"]["User"]["text"])}) for u in units])
    send = lambda by: hand_over(((units[k][0], units[k][1], units[k][2]) for k in by.tolist()), cites)  # noqa: E731
    c_order = np.lexsort((spot, best))

    def top_by_reader(pool):
        used, top = 0, []
        for k in pool:
            if used + units[k][1] > 2 * BUDGET:
                break
            used += units[k][1]
            top.append(k)
        top = np.array(top, dtype=np.int64)
        rest = np.array([k for k in pool if k not in set(top.tolist())], dtype=np.int64)
        return np.concatenate([top[np.argsort(-read[top], kind="stable")], rest]) if top.size else rest

    results[WAYS[0]].append(send(c_order))
    results[WAYS[1]].append(send(np.lexsort((spot, best, ~named))))
    results[WAYS[2]].append(send(top_by_reader(c_order.tolist())))
    first = np.array([k for k in c_order.tolist() if named[k]], dtype=np.int64)
    first = first[np.argsort(-read[first], kind="stable")] if first.size else first
    results[WAYS[3]].append(send(np.concatenate([first, top_by_reader([k for k in c_order.tolist() if not named[k]])])))
    types.append(str(q.type))
    with_company.append(bool(wanted))

count = len(types)
print(f"\n==== {SET}: {count} questions; a company named on {int(np.sum(with_company))}; pairs with no score {unread} ====")
print("== first unit holds a cited record | a cited record among the first three | context_recall_id ==")
base = np.array([r[2] for r in results[WAYS[0]]])
for way in WAYS:
    a = np.array(results[way], dtype=np.float64)
    diff = a[:, 2] - base
    tail = "" if way == WAYS[0] else (f"   [{diff.mean():+.3f}, standard error {diff.std(ddof=1) / np.sqrt(diff.size):.3f}, "
                                      f"higher on {int((diff > 1e-9).sum())}, lower on {int((diff < -1e-9).sum())}]")
    print(f"  {int(a[:, 0].sum()):3d} of {count} ({a[:, 0].mean():.0%}) | {int(a[:, 1].sum()):3d} ({a[:, 1].mean():.0%}) | "
          f"{a[:, 2].mean():.3f}  {way}{tail}")
types = np.array(types)
print("== by the benchmark's own type of question (15 questions or more): first unit holds a cited record, U1 ; K2 ; K3 ==")
for kind in sorted(set(types.tolist())):
    pick = types == kind
    if pick.sum() >= 15:
        print(f"  {kind:8s} {int(pick.sum()):3d} | " + " ; ".join(
            f"{np.array(results[way], dtype=np.float64)[pick, 0].mean():.0%}" for way in (WAYS[0], WAYS[2], WAYS[3])))
print("done", flush=True)

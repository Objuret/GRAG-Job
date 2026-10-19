"""For his 2026-10-12 goal "solve this" (the order): the question widened by what it finds first,
checked on the gold hundred and on the 300 unused questions (the seeded draw of
`the_order_on_unused_questions`; the held-out hundred left as it is). No model call of the lane.

Units: an own conversation whole and an own pull request, each with a vector of its own text
(`own_units_for_embedding.py`, the repo's own embedder behind "query: ", the desktop's GPU); any
other chunk (meeting, document, url, chat) with its description's vector. The records that are
not the product's own work are left out (`first_gold_rounds/ties.py`).

  C    the order made with no model call (the combo and the scope, the question without the
       product's name), whole own conversations as their chunks show
  U2   every unit by its own nearness to the question
  F2   the question's vector plus the middle of the conversations C puts first (as many as the
       first of five clusters of the conversations' own nearness holds), every unit by its
       nearness to that
  F4   C's first conversations (the same ones) first, in C's order, then every other unit by F2

first handed over holds a cited record | context_recall_id (share of the cited records
delivered inside 72,000 characters). The gold ids are read inside this script; numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/the_widened_question_on_unused_questions.py [vectors.npz]
"""
import json
import os
import random
import re
import sys
import warnings
from collections import Counter, defaultdict
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

SEED = 20261011
BUDGET = 72000
CLUSTERS = 5
TOKEN = re.compile(r"[a-z0-9]+")
OWN = HERE / "own_units"
VECTORS = sys.argv[1] if len(sys.argv) > 1 else "own_units_query.npz"

ids_of = {name: {json.loads(line)["id"] for line in (REPO / "data" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
                 if line.strip()} for name in ("gold100", "heldout100")}
every = HQ.load_questions()
fresh = sorted((q for q in every if q.id not in ids_of["gold100"] | ids_of["heldout100"] and q.citations), key=lambda q: q.id)
SETS = {"the gold hundred": [q for q in every if q.id in ids_of["gold100"]],
        "300 unused questions": random.Random(SEED).sample(fresh, 300)}
own_rows = [json.loads(line) for line in open(OWN / "own_units.jsonl", encoding="utf-8")]
own_matrix = np.asarray(np.load(OWN / VECTORS, allow_pickle=True)["matrix"], dtype=np.float64)
unit_of_record = {}
for at, row in enumerate(own_rows):
    for r in row["records"]:
        unit_of_record[r] = at
p = V.prepare_over_corpus("the widened question")
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
print(f"prepared; vectors: {VECTORS}", flush=True)


def vector_of(text):
    return np.asarray(V._query_cosines(text, [], AXES)[0]["query_description_cosines"], dtype=np.float64)


def without_the_names(question, names):
    out = question
    for name in names:
        parts = TOKEN.findall(name.lower())
        if parts:
            pattern = re.compile(r"(?<![A-Za-z0-9])" + r"[^A-Za-z0-9]*".join(re.escape(part) for part in parts)
                                 + r"(?![A-Za-z0-9])", re.IGNORECASE)
            out = pattern.sub("the product", out)
    return " ".join(out.split())


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


def unit(v):
    return v / max(float(np.linalg.norm(v)), 1e-12)


def hand_over(units, cites):
    used_chars, got, first = 0, set(), None
    for ids, chars, part in units:
        new = [r for r in ids if r not in got]
        if not new and not part:
            continue
        if used_chars + chars > BUDGET:
            break
        used_chars += chars
        got.update(ids)
        if first is None:
            first = bool(cites & set(ids))
    return bool(first), len(cites & got) / len(cites)


WAYS = ("C   the order with no model call, whole own conversations", "U2  every unit by its own nearness to the question",
        "F2  every unit by its nearness to the question plus the middle of the conversations C puts first",
        "F4  C's first conversations first, then every other unit by F2")
for label, drawn in SETS.items():
    results = {way: [] for way in WAYS}
    types = []
    for q in drawn:
        border, scope = V.scope_by_name(q.question, p.tree, n)
        names = scope["names_in_the_question"]
        if len(names) != 1:
            continue
        inside = np.flatnonzero(border)
        cites = {str(c) for c in q.citations}
        P = TI.product(product_of[int(inside[0])])
        vector = vector_of(without_the_names(q.question, names))
        D, T = (CV @ vector)[inside], closest_tag(vector)[inside]
        step = (WK.levels(D, CLUSTERS) + WK.levels(T, CLUSTERS)).astype(np.float64)
        z = standing(D) + standing(T)
        in_scope = majority(step <= 3 if (step <= 3).any() else step == step.min(), parent_of[inside])
        order = inside[np.lexsort((id_rank[inside], -z, ~in_scope, step))].tolist()
        place = {i: at for at, i in enumerate(order)}
        own = {i: [r for r in records[i] if not TI.apart(r, P)] for i in order}
        units, by_unit, vectors = [], {}, []
        for i in sorted(order, key=lambda i: (parents[i], int(id_rank[i]))):
            if own[i] and own[i][0] in unit_of_record and not is_part[i]:
                for r in own[i]:
                    u = unit_of_record[r]
                    if u not in by_unit:
                        by_unit[u] = len(units)
                        rs = list(own_rows[u]["records"])
                        units.append([rs, length_of(rs, P), False, i, own_rows[u]["id"].startswith("talk|")])
                        vectors.append(own_matrix[u])
                    elif place[i] < place[units[by_unit[u]][3]]:
                        units[by_unit[u]][3] = i
            elif own[i]:
                size = int(length[i]) if is_part[i] or len(own[i]) == len(records[i]) else length_of(own[i], P)
                units.append([own[i], size, bool(is_part[i]), i, False])
                vectors.append(CV[i])
        M = np.stack(vectors)
        talk = np.array([u[4] for u in units])
        best = np.array([place[u[3]] for u in units])
        spot = np.arange(len(units))
        near = M @ vector
        send = lambda by: hand_over(((units[k][0], units[k][1], units[k][2]) for k in by.tolist()), cites)  # noqa: E731
        c_order = np.lexsort((spot, best))
        results[WAYS[0]].append(send(c_order))
        results[WAYS[1]].append(send(np.lexsort((spot, -near))))
        many = int((WK.levels(near[talk], CLUSTERS) == 1).sum()) if talk.any() else 0
        front = c_order[talk[c_order]][:max(many, 1)]
        if front.size:
            wide = unit(vector + unit(M[front].mean(axis=0)))
            near_wide = M @ wide
        else:
            near_wide = near
        results[WAYS[2]].append(send(np.lexsort((spot, -near_wide))))
        first = np.zeros(len(units), dtype=bool)
        first[front] = True
        results[WAYS[3]].append(send(np.lexsort((spot, np.where(first, best, 0), -np.where(first, 0., near_wide), ~first))))
        types.append(str(q.type))
    count = len(types)
    print(f"\n==== {label}: {count} questions ====")
    print("== first handed over holds a cited record | context_recall_id ==")
    base = np.array([r[1] for r in results[WAYS[0]]])
    for way in WAYS:
        a = np.array(results[way], dtype=np.float64)
        diff = a[:, 1] - base
        tail = "" if way == WAYS[0] else (f"   [against C: {diff.mean():+.3f}, standard error {diff.std(ddof=1) / np.sqrt(diff.size):.3f}, "
                                          f"higher on {int((diff > 1e-9).sum())}, lower on {int((diff < -1e-9).sum())}]")
        print(f"  {int(a[:, 0].sum()):3d} of {count} | {a[:, 1].mean():.3f}  {way}{tail}")
    types = np.array(types)
    print("== by the benchmark's own type of question (15 questions or more): context_recall_id, C ; U2 ; F2 ; F4 ==")
    for kind in sorted(set(types.tolist())):
        pick = types == kind
        if pick.sum() >= 15:
            print(f"  {kind:8s} {int(pick.sum()):3d} | " + " ; ".join(
                f"{np.array(results[way], dtype=np.float64)[pick, 1].mean():.3f}" for way in WAYS))
print("done", flush=True)

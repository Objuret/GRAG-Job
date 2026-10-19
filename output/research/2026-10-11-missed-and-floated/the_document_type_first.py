"""For his 2026-10-12 goal "solve this" (the order): a document's type named in the question, used as
the company's name is (`the_names_a_question_holds`): the scope it picks goes first. The scope,
by the records' own ties: the documents of that type, the meetings about that type, and the
product's own conversations that link to a document of that type. The order is the one made
with no model call (the combo and the scope, the question without the product's name); handed
over as the step as it stands does (the product's own work, conversations whole). The gold
hundred and the 300 unused questions; the held-out hundred left as it is. No model call; the
gold ids are read inside; numbers only.

  C     as it stands
  N     the company's scope first (the conversations naming a customer of a company the
        question names)
  DT    the document type's scope first, its chunks in the combo's order among themselves
  NDT   the company's scope, then the document type's, then the rest
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

SEED = 20261011
BUDGET = 72000
CLUSTERS = 5
TOKEN = re.compile(r"[a-z0-9]+")
CUST = re.compile(r"CUST-\d+")

ids_of = {name: {json.loads(line)["id"] for line in (REPO / "data" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
                 if line.strip()} for name in ("gold100", "heldout100")}
every = HQ.load_questions()
fresh = sorted((q for q in every if q.id not in ids_of["gold100"] | ids_of["heldout100"] and q.citations), key=lambda q: q.id)
SETS = {"the gold hundred": [q for q in every if q.id in ids_of["gold100"]],
        "300 unused questions": random.Random(SEED).sample(fresh, 300)}
customers = json.loads((REPO / "data/raw/Salesforce__HERB/metadata/customers_data.json").read_text(encoding="utf-8"))


def plain(text):
    return " " + re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip() + " "


of_company = defaultdict(set)
for row in customers:
    of_company[plain(row["company"])].add(row["id"])
p = V.prepare_over_corpus("the document type first")
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
print("prepared", flush=True)


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


WAYS = ("C     as it stands", "N     the company's scope first", "DT    the document type's scope first",
        "NDT   the company's scope, then the document type's")
for label, drawn in SETS.items():
    results = {way: [] for way in WAYS}
    holds = {"a company": [], "a document type": []}
    for q in drawn:
        border, scope = V.scope_by_name(q.question, p.tree, n)
        names = scope["names_in_the_question"]
        if len(names) != 1:
            continue
        inside = np.flatnonzero(border)
        cites = {str(c) for c in q.citations}
        product = product_of[int(inside[0])]
        P = TI.product(product)
        bare = without_the_names(q.question, names)
        vector = vector_of(bare)
        D, T = (CV @ vector)[inside], closest_tag(vector)[inside]
        step = (WK.levels(D, CLUSTERS) + WK.levels(T, CLUSTERS)).astype(np.float64)
        z = standing(D) + standing(T)
        in_scope = majority(step <= 3 if (step <= 3).any() else step == step.min(), parent_of[inside])
        own = {i: [r for r in records[i] if not TI.apart(r, P)] for i in inside.tolist()}
        slack = {i: bool(records[i]) and records[i][0] in P["talk_of"] for i in inside.tolist()}
        talk_records = defaultdict(list)
        for i in sorted(inside.tolist(), key=lambda i: (parents[i], int(id_rank[i]))):
            if slack[i]:
                for r in own[i]:
                    talk_records[P["talk_of"][r]].append(r)
        words = plain(bare)
        wanted = set().union(*[of_company[name] for name in of_company if name in words])
        by_company = {t for t, rs in talk_records.items()
                      if wanted & {c for r in rs for c in CUST.findall(P["raw"][r][1]["Message"]["User"]["text"])}}
        kinds = {plain(r["type"]) for kind, r in P["raw"].values() if kind == "documents"}
        named = {k for k in kinds if k in words}
        docs = {rid for rid, (kind, r) in P["raw"].items() if kind == "documents" and plain(r["type"]) in named}
        meetings = {rid for rid, (kind, r) in P["raw"].items()
                    if kind == "meeting_transcripts" and plain(r["document_type"]) in named}
        by_type = {t for t in talk_records if P["links"][t][3] & docs}
        type_chunks = {i for i in inside.tolist() if not slack[i] and set(records[i]) & (docs | meetings)}
        holds["a company"].append(bool(wanted))
        holds["a document type"].append(bool(named))

        def send(first_talks, second_talks=frozenset(), second_chunks=frozenset()):
            rank = {i: (0 if slack[i] and any(P["talk_of"][r] in first_talks for r in own[i]) else
                        1 if i in second_chunks or (slack[i] and any(P["talk_of"][r] in second_talks for r in own[i])) else 2)
                    for i in inside.tolist()}
            boost = np.array([rank[i] for i in inside.tolist()])
            order = inside[np.lexsort((id_rank[inside], -z, ~in_scope, step, boost))].tolist()
            used, got, first, seen, sent = 0, set(), None, set(), set()
            for i in order:
                if not own[i]:
                    continue
                if not slack[i]:
                    ids = own[i]
                    size = int(length[i]) if is_part[i] or len(own[i]) == len(records[i]) else length_of(own[i], P)
                    if not is_part[i] and not [r for r in ids if r not in got]:
                        continue
                else:
                    here = [t for t in dict.fromkeys(P["talk_of"][r] for r in own[i]) if t not in seen]
                    here.sort(key=lambda t: (t not in first_talks, t not in second_talks))
                    ids = [r for t in here for r in talk_records[t] if r not in sent]
                    if not ids:
                        continue
                    size = length_of(ids, P)
                if used + size > BUDGET:
                    break
                used += size
                if slack[i]:
                    seen.update(here)
                    sent.update(ids)
                got.update(ids)
                if first is None:
                    first = bool(cites & set(ids))
            return bool(first), len(cites & got) / len(cites)

        results[WAYS[0]].append(send(frozenset()))
        results[WAYS[1]].append(send(by_company))
        results[WAYS[2]].append(send(frozenset(), by_type, type_chunks))
        results[WAYS[3]].append(send(by_company, by_type, type_chunks))
    count = len(results[WAYS[0]])
    company, doc_type = np.array(holds["a company"]), np.array(holds["a document type"])
    either = company | doc_type
    print(f"\n==== {label}: {count} questions; hold a company's name {int(company.sum())}, a document type {int(doc_type.sum())}, "
          f"either {int(either.sum())}, both {int((company & doc_type).sum())} ====")
    print("== first text holds a cited record | context_recall_id | over the questions that hold either name: the same two ==")
    base = np.array([r[1] for r in results[WAYS[0]]])
    for way in WAYS:
        a = np.array(results[way], dtype=np.float64)
        diff = a[:, 1] - base
        tail = "" if way == WAYS[0] else (f"   [{diff.mean():+.3f}, standard error {diff.std(ddof=1) / np.sqrt(diff.size):.3f}, "
                                          f"higher on {int((diff > 1e-9).sum())}, lower on {int((diff < -1e-9).sum())}]")
        print(f"  {int(a[:, 0].sum()):3d} of {count} | {a[:, 1].mean():.3f} | {int(a[either, 0].sum()):3d} of {int(either.sum())}, "
              f"{a[either, 1].mean():.3f}  {way}{tail}")
print("done", flush=True)

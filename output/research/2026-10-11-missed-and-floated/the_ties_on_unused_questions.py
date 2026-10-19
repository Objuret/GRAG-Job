"""For his 2026-10-12 goal "solve this": the ties of a product's records, checked on questions never
used (the same seeded draw of 300 as `the_order_on_unused_questions`; the gold hundred and the
held-out hundred left as they are). No model call.

What the ties are (`first_gold_rounds/ties.py`, read from the records alone, no question): a
product's file holds, beside the product's own work, another project's pull requests (their
authors post nowhere in the product), talks about those in the product's own channels, and the
planning channel of a team that does not continue (its people post nowhere else in the product).
The benchmark's own paper names these as built-in distraction (arXiv 2506.23139).

Counted here:
  1  the cited records of the 300 by their tie
  2  the order made with no model call (the combo and the scope, the question without the
     product's name), handed over three ways inside 72,000 characters:
       as built            every chunk whole
       own work only       each chunk without the records that are not the product's own work
       whole talks         that, and a talk is handed over whole where it first shows
     first handed over holds a cited record | context_recall_id (share of the cited records
     delivered inside 72,000 characters), all and by the benchmark's own type of question

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/the_ties_on_unused_questions.py [300]
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

MANY = int(sys.argv[1]) if len(sys.argv) > 1 else 300
SEED = 20261011
BUDGET = 72000
CLUSTERS = 5
TOKEN = re.compile(r"[a-z0-9]+")

used = set()
for name in ("gold100", "heldout100"):
    used |= {json.loads(line)["id"] for line in (REPO / "data" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
             if line.strip()}
every = HQ.load_questions()
fresh = sorted((q for q in every if q.id not in used and q.citations), key=lambda q: q.id)
drawn = random.Random(SEED).sample(fresh, min(MANY, len(fresh)))
p = V.prepare_over_corpus("the ties on unused questions")
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
print(f"prepared; {len(drawn)} questions drawn (seed {SEED})", flush=True)


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


def hand_over(units, cites):
    """units: (record ids, characters, a part of one record) in order; the harness's cut: the first that does not fit ends it."""
    used_chars, got, first, count = 0, set(), None, 0
    for ids, chars, part in units:
        new = [r for r in ids if r not in got]
        if not new and not part:
            continue
        if used_chars + chars > BUDGET:
            break
        used_chars += chars
        got.update(ids)
        count += 1
        if first is None:
            first = bool(cites & set(ids))
    return bool(first), len(cites & got) / len(cites), count


WAYS = ("as built", "own work only", "whole talks")
results = {way: [] for way in WAYS}
types, seen_tie, cited_tie = [], Counter(), Counter()
skipped = done = 0
for q in drawn:
    border, scope = V.scope_by_name(q.question, p.tree, n)
    names = scope["names_in_the_question"]
    if len(names) != 1:
        skipped += 1
        continue
    inside = np.flatnonzero(border)
    cites = {str(c) for c in q.citations}
    P = TI.product(product_of[int(inside[0])])
    for i in inside.tolist():
        for r in records[i]:
            t = TI.tie(r, P)
            seen_tie[t] += 1
            cited_tie[t] += r in cites
    vector = vector_of(without_the_names(q.question, names))
    D, T = (CV @ vector)[inside], closest_tag(vector)[inside]
    step = (WK.levels(D, CLUSTERS) + WK.levels(T, CLUSTERS)).astype(np.float64)
    z = standing(D) + standing(T)
    in_scope = majority(step <= 3 if (step <= 3).any() else step == step.min(), parent_of[inside])
    order = inside[np.lexsort((id_rank[inside], -z, ~in_scope, step))].tolist()
    own = {i: [r for r in records[i] if not TI.apart(r, P)] for i in order}
    slack = {i: bool(records[i]) and records[i][0] in P["talk_of"] for i in order}

    def trimmed(i):
        return int(length[i]) if is_part[i] or len(own[i]) == len(records[i]) else length_of(own[i], P)

    talk_records = defaultdict(list)
    for i in sorted(order, key=lambda i: (parents[i], int(id_rank[i]))):
        if slack[i]:
            for r in own[i]:
                talk_records[P["talk_of"][r]].append(r)

    def whole_talks():
        seen, sent = set(), set()
        for i in order:
            if not own[i]:
                continue
            if not slack[i]:
                yield own[i], trimmed(i), bool(is_part[i])
                continue
            ids = []
            for r in own[i]:
                t = P["talk_of"][r]
                if t not in seen:
                    seen.add(t)
                    ids.extend(talk_records[t])
            ids = [r for r in dict.fromkeys(ids) if r not in sent]
            if ids:
                yield ids, length_of(ids, P), False
                sent.update(ids)

    results["as built"].append(hand_over(((records[i], int(length[i]), bool(is_part[i])) for i in order), cites))
    results["own work only"].append(hand_over(((own[i], trimmed(i), bool(is_part[i])) for i in order if own[i]), cites))
    results["whole talks"].append(hand_over(whole_talks(), cites))
    types.append(str(q.type))
    done += 1
    if done % 50 == 0:
        print(f"  ... {done} questions", flush=True)

count = len(types)
print(f"\n{len(drawn)} drawn, {skipped} without exactly one product's name, read: {count}; their types: {dict(Counter(types))}")
print("\n== 1: the records of the question's product by their tie: records, a question | of them cited | share of the "
      "cited records ==")
total = sum(cited_tie.values())
for t, seen in sorted(seen_tie.items(), key=lambda kv: -kv[1]):
    print(f"  {seen / count:7.1f} | {cited_tie[t] / seen:6.2%} | {cited_tie[t] / total:5.1%}  {t}")
print("\n== 2: chunks or units handed over, a question | first handed over holds a cited record | context_recall_id ==")
base = np.array([r[1] for r in results["as built"]])
for way in WAYS:
    a = np.array(results[way], dtype=np.float64)
    diff = a[:, 1] - base
    tail = "" if way == "as built" else (f"   [against as built: {diff.mean():+.3f}, standard error "
                                          f"{diff.std(ddof=1) / np.sqrt(diff.size):.3f}, higher on {int((diff > 1e-9).sum())}, "
                                          f"lower on {int((diff < -1e-9).sum())}]")
    print(f"  {a[:, 2].mean():5.1f} | {a[:, 0].mean():4.0%} | {a[:, 1].mean():.3f}  {way}{tail}")
print("\n== by the benchmark's own type of question: questions | first handed over holds a cited record, context_recall_id: "
      "as built ; own work only ; whole talks ==")
types = np.array(types)
for kind in sorted(set(types.tolist())):
    pick = types == kind
    row = " ; ".join(f"{np.array(results[way], dtype=np.float64)[pick, 0].mean():4.0%}, "
                     f"{np.array(results[way], dtype=np.float64)[pick, 1].mean():.3f}" for way in WAYS)
    print(f"  {kind:8s} {int(pick.sum()):3d} | {row}")
print("done", flush=True)

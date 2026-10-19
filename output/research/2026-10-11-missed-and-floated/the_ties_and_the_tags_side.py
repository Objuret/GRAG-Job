"""For his 2026-10-12 goal "solve this": do the ties (`first_gold_rounds/ties.py`) help the ORDER, not
only the room? A chunk's tags were written over a batch that mixes an own talk with a talk about
another project's pull request. Here an edge from a chunk to a tag is left out of the tags' side
when the tag's own words stand only in records of the chunk that are not the product's own work
(word for word, in no own record of that chunk); and a chunk that is nothing but such records is
out before the clusters are cut. The order is the one made with no model call (the combo and
the scope, the question without the product's name), handed over as whole own talks. The gold
hundred and the 300 unused questions; the held-out hundred left as it is. Numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/the_ties_and_the_tags_side.py
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

ids_of = {name: {json.loads(line)["id"] for line in (REPO / "data" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
                 if line.strip()} for name in ("gold100", "heldout100")}
every = HQ.load_questions()
fresh = sorted((q for q in every if q.id not in ids_of["gold100"] | ids_of["heldout100"] and q.citations), key=lambda q: q.id)
SETS = {"the gold hundred": [q for q in every if q.id in ids_of["gold100"]],
        "300 unused questions": random.Random(SEED).sample(fresh, 300)}
p = V.prepare_over_corpus("the ties and the tags' side")
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
product_ties = {name: TI.product(name) for name in sorted(set(product_of))}
all_apart = np.zeros(n, dtype=bool)
edge_other = np.zeros(et.size, dtype=bool)      # the tag's words stand only in records that are not the product's own work
mixed = {}
for i in range(n):
    P = product_ties[product_of[i]]
    if is_part[i] or not records[i]:
        continue
    flags = [TI.apart(r, P) for r in records[i]]
    all_apart[i] = all(flags)
    if any(flags) and not all(flags):
        mixed[i] = ([" " + " ".join(TOKEN.findall(json.dumps(P["raw"][r][1], ensure_ascii=False).lower())) + " "
                     for r in records[i]], flags)
for e in range(et.size):
    i = int(ec[e])
    if i not in mixed:
        continue
    words = " ".join(TOKEN.findall(str(p.graph_tags[int(et[e])]).lower()))
    if not words:
        continue
    texts, flags = mixed[i]
    hit = [(" " + words + " ") in text for text in texts]
    edge_other[e] = any(h and f for h, f in zip(hit, flags)) and not any(h and not f for h, f in zip(hit, flags))
print(f"prepared; chunks that are nothing but records not the product's own work: {int(all_apart.sum())} of {n}; "
      f"mixed chunks: {len(mixed)}; edges whose tag stands only in such records of a mixed chunk: "
      f"{int(edge_other.sum())} of {et.size}", flush=True)


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


def closest_tag(vector, keep=None):
    row = vector @ TV.T
    out = np.full(n, float(row.min()))
    if keep is None:
        np.maximum.at(out, ec, row[et])
    else:
        np.maximum.at(out, ec[keep], row[et[keep]])
    return out


def length_of(ids, P):
    return sum(P["size"][r] for r in ids) + max(len(ids) - 1, 0)


def hand_over(units, cites):
    """units: (record ids, characters, a part of one record); the harness's cut: the first that does not fit ends it."""
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


WAYS = ("the order as built", "the tags' side without the edges of the other talks",
        "that, and the chunks that are nothing but such records out before the clusters")
for label, drawn in SETS.items():
    results = {way: [] for way in WAYS}
    for q in drawn:
        border, scope = V.scope_by_name(q.question, p.tree, n)
        names = scope["names_in_the_question"]
        if len(names) != 1:
            continue
        cites = {str(c) for c in q.citations}
        vector = vector_of(without_the_names(q.question, names))
        for way in WAYS:
            inside = np.flatnonzero(border & ~all_apart) if way == WAYS[2] else np.flatnonzero(border)
            P = product_ties[product_of[int(inside[0])]]
            D = (CV @ vector)[inside]
            T = closest_tag(vector, None if way == WAYS[0] else ~edge_other)[inside]
            step = (WK.levels(D, CLUSTERS) + WK.levels(T, CLUSTERS)).astype(np.float64)
            z = standing(D) + standing(T)
            in_scope = majority(step <= 3 if (step <= 3).any() else step == step.min(), parent_of[inside])
            order = inside[np.lexsort((id_rank[inside], -z, ~in_scope, step))].tolist()
            own = {i: [r for r in records[i] if not TI.apart(r, P)] for i in order}
            slack = {i: bool(records[i]) and records[i][0] in P["talk_of"] for i in order}
            talk_records = defaultdict(list)
            for i in sorted(order, key=lambda i: (parents[i], int(id_rank[i]))):
                if slack[i]:
                    for r in own[i]:
                        talk_records[P["talk_of"][r]].append(r)
            units, seen, sent = [], set(), set()
            for i in order:
                if not own[i]:
                    continue
                if not slack[i]:
                    size = int(length[i]) if is_part[i] or len(own[i]) == len(records[i]) else length_of(own[i], P)
                    units.append((own[i], size, bool(is_part[i])))
                    continue
                ids = []
                for r in own[i]:
                    t = P["talk_of"][r]
                    if t not in seen:
                        seen.add(t)
                        ids.extend(talk_records[t])
                ids = [r for r in dict.fromkeys(ids) if r not in sent]
                if ids:
                    units.append((ids, length_of(ids, P), False))
                    sent.update(ids)
            results[way].append(hand_over(units, cites))
    count = len(results[WAYS[0]])
    print(f"\n==== {label}: {count} questions, handed over as whole own talks ====")
    print("== first handed over holds a cited record | context_recall_id ==")
    base = np.array([r[1] for r in results[WAYS[0]]])
    for way in WAYS:
        a = np.array(results[way], dtype=np.float64)
        diff = a[:, 1] - base
        tail = "" if way == WAYS[0] else (f"   [against the first: {diff.mean():+.3f}, standard error "
                                          f"{diff.std(ddof=1) / np.sqrt(diff.size):.3f}, higher on {int((diff > 1e-9).sum())}, "
                                          f"lower on {int((diff < -1e-9).sum())}]")
        print(f"  {int(a[:, 0].sum()):3d} of {count} | {a[:, 1].mean():.3f}  {way}{tail}")
print("done", flush=True)

"""The check behind `which_links_are_strong.py`: links inside the same parent and links through rare
tags led to cited chunks more often. But a chunk under the same parent as a handed-over chunk may be
cited more often anyway, linked or not (the arm's scope already leans on the parents). So every
chunk of the border that is not handed over is counted, linked or not:
  where        under a parent that holds a handed-over chunk (of the same kind), or not
  link         its rarest tag shared with a handed-over chunk: 2 to 3 chunks, 4 to 8, 9 to 27,
               28 or more (the tag sizes as cut in `which_links_are_strong.py`), or no shared tag
Per cell: chunks a question and the share holding a cited record. The gold hundred (the arm's own
order and hand-over, facets off, cached first calls) and the first hundred of the seeded draw of
the unused questions (the order from the question alone; the arm's hand-over). No model call.
The gold ids are read inside; numbers only.
"""
import json
import os
import random
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"
os.environ["HERB_V4_FACETS"] = "off"
os.environ.pop("HERB_V4_SCOPE_STEP", None)

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

BUDGET = 72000
CLUSTERS = 5
ids_of = {name: {json.loads(line)["id"] for line in (REPO / "data" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
                 if line.strip()} for name in ("gold100", "heldout100")}
every = HQ.load_questions()
fresh = sorted((q for q in every if q.id not in ids_of["gold100"] | ids_of["heldout100"] and q.citations), key=lambda q: q.id)
SETS = (("the gold hundred", [q for q in every if q.id in ids_of["gold100"]]),
        ("100 unused questions", random.Random(20261011).sample(fresh, 300)[:100]))
p = V.prepare_over_corpus("the parent and the rare tag")
layer, n = p.layer, len(p.chunk_ids)
tag_e, chunk_e, id_rank = layer["edge_tag"], layer["edge_chunk"], layer["id_rank"]
chunks_of_tag, tags_of_chunk = defaultdict(set), defaultdict(set)
for t, c in zip(tag_e.tolist(), chunk_e.tolist()):
    chunks_of_tag[t].add(c)
    tags_of_chunk[c].add(t)
tag_ids = sorted(chunks_of_tag)
size_level = dict(zip(tag_ids, WK.levels(np.log([len(chunks_of_tag[t]) for t in tag_ids]), CLUSTERS).tolist()))
size_name = {}
for lv in sorted(set(size_level.values())):
    sizes = [len(chunks_of_tag[t]) for t in tag_ids if size_level[t] == lv]
    size_name[lv] = f"{min(sizes)} to {max(sizes)} chunks"
parents = [str(row["parent"]) for row in p.chunk_rows]
kinds = [str(row["kind"]) for row in p.chunk_rows]
home = [(a, b) for a, b in zip(parents, kinds)]
parent_ids = {name: k for k, name in enumerate(sorted(set(parents)))}
parent_of = np.array([parent_ids[name] for name in parents], dtype=np.int64)
CV = np.asarray(p.chunk_vectors, dtype=np.float64)
TV = np.asarray(p.tag_vectors, dtype=np.float64)
AXES = V._QueryAxes(TV, np.eye(CV.shape[1]))
doc_cache = {}
records = [{str(x) for x in _resolve_chunk(row, doc_cache)[1]} for row in p.chunk_rows]
print("prepared", flush=True)


def standing(x):
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


def closest_tag(vector):
    row = vector @ TV.T
    out = np.full(n, float(row.min()))
    np.maximum.at(out, chunk_e, row[tag_e])
    return out


captured = {}
the_hand = V._hand_over


def hand_rec(order, prepared, char_budget, k, cache):
    out = the_hand(order, prepared, char_budget, k, cache)
    captured["delivered"] = list(out[4])
    return out


for label, drawn in SETS:
    cells = defaultdict(lambda: [0, 0])
    used = 0
    for q in drawn:
        cites = {str(c) for c in q.citations}
        border, said = V.scope_by_name(q.question, p.tree, n)
        if label == "the gold hundred":
            V._hand_over = hand_rec
            V.answer_one_question((q.id, q.question), p, None, 50, BUDGET)
            V._hand_over = the_hand
            delivered = set(captured["delivered"])
        else:
            names = said["names_in_the_question"]
            if len(names) != 1:
                continue
            inside = np.flatnonzero(border)
            vector = np.asarray(V._query_cosines(V._without_names(q.question, names), [], AXES)[0]["query_description_cosines"],
                                dtype=np.float64)
            D, T = (CV @ vector)[inside], closest_tag(vector)[inside]
            step = WK.levels(D, CLUSTERS) + WK.levels(T, CLUSTERS)
            z = standing(D) + standing(T)
            taken = WK.majority_scopes(step <= max(3, int(step.min())), parent_of[inside])
            in_scope = np.isin(parent_of[inside], taken)
            order = inside[np.lexsort((id_rank[inside], -z, ~in_scope, step))].tolist()
            delivered = set(V._hand_over(order, p, BUDGET, 50, doc_cache)[4])
        used += 1
        homes = {home[a] for a in delivered}
        shared = defaultdict(lambda: 99)
        for a in delivered:
            for t in tags_of_chunk[a]:
                for c in chunks_of_tag[t]:
                    if c != a and c not in delivered and border[c]:
                        lv = size_level[t]
                        shared[c] = min(shared[c], -lv) if shared[c] != 99 else -lv   # the rarest: the largest level
        for c in np.flatnonzero(border).tolist():
            if c in delivered:
                continue
            g = int(bool(cites & records[c]))
            where = "under a parent of a handed-over chunk" if home[c] in homes else "under another parent"
            link = f"rarest shared tag {size_name[-shared[c]]}" if c in shared else "no shared tag"
            cells[(where, link)][0] += 1
            cells[(where, link)][1] += g
    print(f"\n{label}: {used} questions")
    for where in ("under a parent of a handed-over chunk", "under another parent"):
        for link in [f"rarest shared tag {size_name[lv]}" for lv in sorted(size_name, reverse=True) if size_name[lv] != "1 to 1 chunks"] + ["no shared tag"]:
            m, g = cells[(where, link)]
            if m:
                print(f"  {where:40s} {link:36s}: {m / used:6.1f}/q {g / m:5.1%} ({g})")
print("done", flush=True)

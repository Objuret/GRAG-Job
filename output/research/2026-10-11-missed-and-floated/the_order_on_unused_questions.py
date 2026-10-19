"""For his 2026-10-12 goal "solve this": the whole order, made with no model call at all, checked on
questions never used. On the hundred the order (the combo and the scope) gave the same whether
the tags' side came from the first call's query tags or from the question itself read against
the chunks' tags (0.547 and 0.543), so here everything is read from the question alone and the
300 unused questions can be run: the same seeded draw as `first_gold_fresh_check` (questions
with citations in neither the gold hundred nor the held-out hundred; both left as they are).

The order, inside the border the product's name sets (`scope_by_name`), delivered through the
arm's own cut (`_budget_contexts`, 72,000 characters):
  chunk side   the chunk descriptions against the question
  tags' side   a chunk's closest tag to the question's own vector
  the combo    each side cut into five clusters (`v4_walk.levels`), the two levels added, chunks
               on one step by their two values added
  the scope    gauged after the combo: the parents that hold the most chunks of its first two
               steps, taken until they hold more than half; in-scope chunks first inside a step
each with the question as asked and with the product's name taken out.

Stated before the run: with the name taken out the full order delivers more of the cited
records and puts a gold chunk first more often than the same order with the name in, and more
than the chunk descriptions alone.

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/the_order_on_unused_questions.py [300]
"""
import json
import os
import random
import re
import sys
import warnings
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"
os.environ["HERB_V4_SCOPE_STEP"] = "both"

from arms import artefact_v4 as V  # noqa: E402
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
p = V.prepare_over_corpus("the order on unused questions")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
et, ec = layer["edge_tag"], layer["edge_chunk"]
parents = [str(row["parent"]) for row in p.chunk_rows]
parent_ids = {name: k for k, name in enumerate(sorted(set(parents)))}
parent_of = np.array([parent_ids[name] for name in parents], dtype=np.int64)
CV = np.asarray(p.chunk_vectors, dtype=np.float64)
TV = np.asarray(p.tag_vectors, dtype=np.float64)
AXES = V._QueryAxes(TV, np.eye(CV.shape[1]))
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


NAMES = ("the chunk descriptions alone, the question as asked",
         "the chunk descriptions alone, the question without the name",
         "the combo, the question as asked, no scope below the product",
         "the combo, the question as asked, in-scope chunks first inside a step",
         "the combo, the question without the name, no scope below the product",
         "the combo, the question without the name, in-scope chunks first inside a step")
results = {name: ([], []) for name in NAMES}
kept_types, skipped = Counter(), 0
done = 0
for q in drawn:
    border, scope = V.scope_by_name(q.question, p.tree, n)
    names = scope["names_in_the_question"]
    if len(names) != 1:
        skipped += 1
        continue
    inside = np.flatnonzero(border)
    cites = {str(c) for c in q.citations}
    kept_types[str(q.type)] += 1
    orders = {}
    for label, text in (("the question as asked", q.question), ("the question without the name", without_the_names(q.question, names))):
        vector = vector_of(text)
        D, T = (CV @ vector)[inside], closest_tag(vector)[inside]
        orders[f"the chunk descriptions alone, {label}"] = inside[np.lexsort((id_rank[inside], -D))]
        step = (WK.levels(D, CLUSTERS) + WK.levels(T, CLUSTERS)).astype(np.float64)
        z = standing(D) + standing(T)
        in_scope = majority(step <= 3 if (step <= 3).any() else step == step.min(), parent_of[inside])
        orders[f"the combo, {label}, no scope below the product"] = inside[np.lexsort((id_rank[inside], -z, step))]
        orders[f"the combo, {label}, in-scope chunks first inside a step"] = inside[np.lexsort((id_rank[inside], -z, ~in_scope, step))]
    doc_cache = {}
    for name, order in orders.items():
        contexts, id_lists, context_ids, budget = V._budget_contexts([p.chunk_rows[i] for i in order.tolist()], BUDGET, doc_cache)
        got = {str(x) for x in context_ids}
        first = {str(x) for x in (id_lists[0] if id_lists else [])}
        results[name][0].append(bool(first & cites))
        results[name][1].append(len(cites & got) / len(cites))
    done += 1
    if done % 50 == 0:
        print(f"  ... {done} questions", flush=True)

count = len(results[NAMES[0]][0])
print(f"\n{len(drawn)} drawn, {skipped} without exactly one product's name, read: {count}; their types: {dict(kept_types)}")
print("== the first delivered chunk is gold | share | context_recall_id ==")
for name in NAMES:
    first, recall = results[name]
    print(f"  {int(sum(first))} | {np.mean(first):.0%} | {float(np.mean(recall)):.3f}  {name}")
print("\n== paired, context_recall_id: questions higher / lower, mean difference (standard error); first chunk gold: only "
      "with the first / only with the second ==")
for a, b in ((NAMES[5], NAMES[3]), (NAMES[5], NAMES[1]), (NAMES[5], NAMES[0]), (NAMES[5], NAMES[4]), (NAMES[4], NAMES[2])):
    diff = np.asarray(results[a][1]) - np.asarray(results[b][1])
    x, y = np.asarray(results[a][0]), np.asarray(results[b][0])
    print(f"  {int((diff > 0).sum())} / {int((diff < 0).sum())}, {float(diff.mean()):+.3f} ({float(diff.std(ddof=1) / np.sqrt(diff.size)):.3f}); "
          f"{int((x & ~y).sum())} / {int((~x & y).sum())}  [{a}]  against  [{b}]")
print("done", flush=True)

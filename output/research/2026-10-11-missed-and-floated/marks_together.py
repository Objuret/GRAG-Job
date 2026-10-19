"""After `what_marks_a_correct_hit`: the three marks that separate, read together, and what an
order made of them delivers inside 72,000 characters. On the hundred, inside the gold's branch,
cached query side, no model call.

Marks of a hit (a chunk that carries a picked tag, or sits in the first of 5 clusters of the
description nearness against the query description or against the question):
  routes     how many of the three routes hit it
  same       its closest tag is the same thing as a query tag (at or above the middle score of
             the graph's own same-thing pairs)
  facets     the values on the edge of its closest tag: topic and the four facets

Printed: gold share by routes and same together; for each facet, among the edges one query tag
picks, the half with the higher value against the half with the lower, and the same inside one
kind of chunk; and the gold chunks delivered inside the budget by orders built from the marks
(the orders are the agent's own, to see what the marks are worth).

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/marks_together.py [gold100]
"""
import json
import os
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"
os.environ["HERB_V4_SCOPE_STEP"] = "both"

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
BUDGET = 72000
CACHE = REPO / "output/private/artefact_v4_cache/querytag"
K = V._k_nearest()
COLUMNS = ("topic", "temporal", "why", "activity", "concreteness")

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("marks together")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
kind_of = layer["kind"]
et, ec, eligible, raw = layer["edge_tag"], layer["edge_chunk"], layer["eligible"], layer["raw"]
docs, records, length = {}, [], np.zeros(n, dtype=np.int64)
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    records.append(frozenset(str(x) for x in ids))
    length[i] = len(text)
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b
same = next((h["same_thing_pairs"] for h in (getattr(p, "provenance", None), V.RETRIEVAL_FLAGS)
             if isinstance(h, dict) and isinstance(h.get("same_thing_pairs"), dict)), None)
SAME_MEDIAN = float(same["median"]) if same else 0.9499
# the standing of every edge's value in its column over the eligible edges (0 the lowest, 1 the highest)
standing_of = np.column_stack([rankdata(raw[:, j], method="average") / raw.shape[0] for j in range(raw.shape[1])])


def cached_sides():
    out = []
    for f in CACHE.glob("*.json"):
        if f.name.endswith(".started.json"):
            continue
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        got = j.get("raw")
        if j.get("ok") and isinstance(got, dict) and got.get("description") and got.get("tags"):
            out.append((f.stat().st_mtime, (j.get("signature") or {}).get("user") or "", got))
    return sorted(out, key=lambda row: -row[0])


SIDES = cached_sides()


def side_of(q):
    def names(rows):
        return list(dict.fromkeys(str(r["t"]).strip() for r in rows or []
                                  if isinstance(r, dict) and str(r.get("t", "")).strip()))
    for _, user, got in SIDES:
        if q.question in user:
            return str(got["description"]), names(got.get("tags")), names(got.get("query_tags"))
    raise SystemExit(f"no cached first call for {q.id}")


def kept_of(order):
    fits = np.cumsum(length[order]) <= BUDGET
    return int(fits.sum()) if fits.all() else int(np.argmin(fits))


def standing(x):
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


joint = defaultdict(lambda: [0, 0])
halves = defaultdict(lambda: [0, 0, 0, 0])
delivered, recall, held = Counter(), defaultdict(list), defaultdict(list)
gold_total = 0
done = 0
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    description, tags, asked = side_of(q)
    answer, _, _ = V._tag_cosines(description, tags, p)
    rows, d_description = list(answer["tags"]), np.asarray(answer["description"], dtype=np.float64)
    if asked:
        rows += list(V._tag_cosines(description, asked, p)[0]["tags"])
    rows = np.array(rows, dtype=np.float64)
    d_question = np.asarray(V._query_cosines(q.question, [], p)[0]["query_description_cosines"], dtype=np.float64)
    gold = np.array([bool(records[i] & cites) for i in range(n)])
    main = Counter(branch_of[np.flatnonzero(gold)].tolist()).most_common(1)[0][0]
    inside = np.flatnonzero(branch_of == main)
    gold_total += int(gold[inside].sum())
    here = np.zeros(n, dtype=bool)
    here[inside] = True
    edges_here = np.flatnonzero(here[ec])
    place_of_tag = np.full(rows.shape, np.inf)
    place_of_tag[:, eligible] = np.array([rankdata(-row[eligible], method="min") for row in rows])
    top = rows[:, et].max(axis=0)
    t_near, t_edge = WK.best_edges(top, ec, n)
    t_near = np.where(t_edge >= 0, t_near, t_near[t_edge >= 0].min())
    best_place = np.full(n, np.inf)
    np.minimum.at(best_place, ec, place_of_tag[:, et].min(axis=0))
    by_tags = best_place[inside] <= K
    by_description = WK.levels(d_description[inside], K) == 1
    by_question = WK.levels(d_question[inside], K) == 1
    routes = by_tags.astype(int) + by_description.astype(int) + by_question.astype(int)
    is_same = t_near[inside] >= SAME_MEDIAN
    base = standing(t_near[inside]) + standing(d_description[inside]) + standing(d_question[inside])
    edge_at = t_edge[inside]
    facet = np.where(edge_at[:, None] >= 0, standing_of[np.maximum(edge_at, 0)], 0.)      # (chunks, 5)
    for k, c in enumerate(inside.tolist()):
        if routes[k]:
            cell = joint[int(routes[k]), bool(is_same[k])]
            cell[0] += int(gold[c])
            cell[1] += 1
    # each facet among the edges one query tag picks, and the same inside one kind of chunk
    for i in range(rows.shape[0]):
        mine = edges_here[place_of_tag[i, et[edges_here]] <= K]
        for scope, groups in (("any kind", [mine]),
                              ("inside one kind", [mine[kind_of[ec[mine]] == code]
                                                   for code in np.unique(kind_of[ec[mine]])])):
            for group in groups:
                if group.size < 4:
                    continue
                is_gold = gold[ec[group]]
                if not is_gold.any() or is_gold.all():
                    continue
                half = group.size // 2
                for j, name in enumerate(COLUMNS):
                    order = np.argsort(-raw[group, j], kind="stable")
                    cell = halves[scope, name]
                    cell[0] += int(is_gold[order[:half]].sum())
                    cell[1] += half
                    cell[2] += int(is_gold[order[group.size - half:]].sum())
                    cell[3] += half

    def score(name, keys):
        """Deliver by the keys, the first the most important, the higher the earlier."""
        order = inside[np.lexsort((id_rank[inside], *[-np.asarray(key, dtype=np.float64) for key in reversed(keys)]))]
        kept = order[:kept_of(order)]
        delivered[name] += int(gold[kept].sum())
        held[name].append(kept.size)
        got = set().union(*(records[i] for i in kept)) if kept.size else set()
        recall[name].append(len(cites & got) / len(cites))

    mean_facets = facet[:, 1:].mean(axis=1)
    score("the plain order: the three routes' standings added", [base])
    score("routes that hit it, then the plain order", [routes, base])
    score("same thing, then the plain order", [is_same, base])
    score("routes, then same thing, then the plain order", [routes, is_same, base])
    score("same thing, then routes, then the plain order", [is_same, routes, base])
    score("routes, then same thing, then the four facets' mean standing on its closest edge, then the plain order",
          [routes, is_same, mean_facets, base])
    score("routes, then the four facets' mean standing on its closest edge, then the plain order",
          [routes, mean_facets, base])
    for j, name in enumerate(COLUMNS):
        score(f"routes, then same thing, then {name} on its closest edge, then the plain order",
              [routes, is_same, facet[:, j], base])
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

m = len(wanted)
print(f"\n{SET}: {m} questions, inside the gold's branch; gold chunks {gold_total}")
print("\n== hits by the routes that hit them and whether the closest tag is the same thing: gold of chunks (share) ==")
for routes_n in (3, 2, 1):
    cells = []
    for flag, label in ((True, "same thing"), (False, "not the same thing")):
        g, t = joint[routes_n, flag]
        cells.append(f"{label}: {g} of {t} ({(g / t if t else 0):.3f})")
    print(f"  {routes_n} routes  " + " | ".join(cells))
print("\n== among the edges one query tag picks: the half with the higher value | the half with the lower, gold of "
      "chunks (share) ==")
for scope in ("any kind", "inside one kind"):
    for name in COLUMNS:
        g1, t1, g2, t2 = halves[scope, name]
        print(f"  {scope}, by {name}: {g1} of {t1} ({(g1 / t1 if t1 else 0):.3f}) | {g2} of {t2} "
              f"({(g2 / t2 if t2 else 0):.3f})")
print(f"\n== inside {BUDGET} characters: gold chunks delivered of {gold_total} | chunks delivered per question, the "
      "middle | context_recall_id ==")
for name in delivered:
    print(f"  {delivered[name]} | {np.median(held[name]):.0f} | {float(np.mean(recall[name])):.3f}  {name}")
print("done", flush=True)

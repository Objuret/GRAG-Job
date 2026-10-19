"""The agent's own routes, 2026-10-11 night (his "But you are just trying MY shit over and over.."):
four readings nobody tried, each set beside the plain order (the three routes' standings added:
the chunk's closest tag to a query tag, its description against the query description, its
description against the question). On the hundred, inside the question's product, cached query
side, no model call.

  the question as a tag   the question's own vector against the graph's tags, a chunk's value its
                          closest tag: in place of the query tags' route, and as a fourth route.
  the same step elsewhere the 30 products went through the same work, so a chunk has a look-alike
                          in every other product (the chunk there whose description is nearest
                          its own). A chunk's value is how near the question, the query
                          description and the query tags are to its look-alikes in the other 29
                          products (the mean): what the chunk is about as a kind of event, with
                          the product's own content taken out.
  tags by where they live the tags' route made only from tags that live in one product, or only
                          from tags that recur across products.
  the product's own taken out
                          description closeness after the middle of the product's description
                          vectors is taken off both sides.

Printed: context_recall_id (share of the cited records delivered inside 72,000 characters) and
the difference to the plain order.

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/routes_of_the_agents_own.py [gold100]
"""
import json
import os
import sys
import warnings
from collections import Counter, defaultdict
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
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
BUDGET = 72000
CACHE = REPO / "output/private/artefact_v4_cache/querytag"
LEVELS = ((1, 1, "tags living in one product"), (2, 99, "tags in two or more products"),
          (2, 7, "tags in 2-7 products"), (8, 99, "tags in 8 or more products"))

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("routes of the agent's own")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
et, ec, eligible = layer["edge_tag"], layer["edge_chunk"], layer["eligible"]
docs, record_sets, length = {}, [], np.zeros(n, dtype=np.int64)
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    record_sets.append(frozenset(str(x) for x in ids))
    length[i] = len(text)
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b
CV = np.asarray(p.chunk_vectors, dtype=np.float64)
TV = np.asarray(p.tag_vectors, dtype=np.float64)
AXES = V._QueryAxes(TV, np.eye(CV.shape[1]))
# every chunk's look-alike in every product: the chunk there whose description is nearest its own
near = (CV @ CV.T).astype(np.float32)
alike = np.zeros((n, len(branches)), dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    alike[:, b] = chunks[np.argmax(near[:, chunks], axis=1)]
alike_closeness = np.array([[near[c, alike[c, b]] for b in range(len(branches))] for c in range(n)])
del near
products_of_tag = defaultdict(set)
for e in range(et.size):
    products_of_tag[int(et[e])].add(int(branch_of[ec[e]]))
edge_products = np.array([len(products_of_tag[int(t)] - {-1}) for t in et], dtype=np.int64)
print(f"prepared: {n} chunks, {len(branches)} products; a chunk's look-alike in another product stands at closeness "
      f"{float(np.median(alike_closeness[branch_of[:, None] != np.arange(len(branches))[None, :]])):.3f} (the middle)",
      flush=True)


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


def standing(x):
    x = np.asarray(x, dtype=np.float64)
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


def closest_tag(rows, edges, floor):
    """Per chunk the closest of its tags (over the edges given) to any row."""
    out = np.full((rows.shape[0], n), floor)
    np.maximum.at(out.T, ec[edges], rows[:, et[edges]].T)
    return out.max(axis=0)


recall = defaultdict(list)
done = 0
every_edge = np.arange(et.size)
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    description, tags, asked = side_of(q)
    answer = V._tag_cosines(description, tags, p)[0]
    rows = list(answer["tags"])
    if asked:
        rows += list(V._tag_cosines(description, asked, p)[0]["tags"])
    rows = np.array(rows, dtype=np.float64)
    question_vector = np.asarray(V._query_cosines(q.question, [], AXES)[0]["query_description_cosines"], dtype=np.float64)
    description_vector = np.asarray(V._query_cosines(description, [], AXES)[0]["query_description_cosines"], dtype=np.float64)
    d_question, d_description = question_vector @ CV.T, description_vector @ CV.T
    gold = np.array([bool(record_sets[i] & cites) for i in range(n)])
    main = Counter(branch_of[np.flatnonzero(gold)].tolist()).most_common(1)[0][0]
    inside = np.flatnonzero(branch_of == main)
    floor = float(rows[:, eligible].min())
    tag_best = closest_tag(rows, every_edge, floor)
    question_rows = (question_vector @ TV.T)[None, :]
    question_tag = closest_tag(question_rows, every_edge, float(question_rows[0, eligible].min()))
    T, D, Q = standing(tag_best[inside]), standing(d_description[inside]), standing(d_question[inside])
    plain = T + D + Q
    others = [b for b in range(len(branches)) if b != main]
    look = alike[inside][:, others]
    step_q, step_d, step_t = d_question[look].mean(axis=1), d_description[look].mean(axis=1), tag_best[look].mean(axis=1)
    middle = CV[inside].mean(axis=0)
    off = CV[inside] - middle
    off /= np.linalg.norm(off, axis=1, keepdims=True)

    def taken_out(vector):
        left = vector - middle
        return off @ (left / np.linalg.norm(left))

    scores = {
        "the plain order": plain,
        "the question as a tag, in place of the query tags' route": standing(question_tag[inside]) + D + Q,
        "the question as a tag, as a fourth route": plain + standing(question_tag[inside]),
        "the same step elsewhere, alone (question, description and tags against the look-alikes)":
            standing(step_q) + standing(step_d) + standing(step_t),
        "the plain order and the question against the look-alikes": plain + standing(step_q),
        "the plain order and all three against the look-alikes":
            plain + standing(step_q) + standing(step_d) + standing(step_t),
        "the product's own taken out of the two description routes": T + standing(taken_out(description_vector))
        + standing(taken_out(question_vector)),
    }
    for low, high, name in LEVELS:
        edges = np.flatnonzero((edge_products >= low) & (edge_products <= high))
        scores[f"the tags' route from {name} only"] = standing(closest_tag(rows, edges, floor)[inside]) + D + Q
    for name, score in scores.items():
        order = inside[np.lexsort((id_rank[inside], -score))]
        fits = np.cumsum(length[order]) <= BUDGET
        kept = order[:int(fits.sum()) if fits.all() else int(np.argmin(fits))]
        got = set().union(*(record_sets[i] for i in kept)) if kept.size else set()
        recall[name].append(len(cites & got) / len(cites))
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

print(f"\n{SET}: {len(wanted)} questions, inside the question's product")
print("== context_recall_id (share of the cited records delivered inside 72,000 characters) | against the plain "
      "order: mean difference, its standard error, questions higher / lower ==")
first = np.asarray(recall["the plain order"])
for name, values in recall.items():
    diff = np.asarray(values) - first
    print(f"  {float(np.mean(values)):.3f} | {float(diff.mean()):+.3f}, {float(diff.std(ddof=1) / np.sqrt(diff.size)):.3f}, "
          f"{int((diff > 0).sum())} / {int((diff < 0).sum())}  {name}")
print("done", flush=True)

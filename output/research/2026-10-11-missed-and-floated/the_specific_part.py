"""A test of the agent's own reading, 2026-10-11 night (after his "it is INSANE if the top chunk is NOT
a gold"): nearness mostly reads which KIND of conversation a chunk is, the same in every product,
and cannot tell which feature's conversation it is. Every chunk has a look-alike in each of the
other 29 products (the chunk there whose description is nearest its own). A route's value for a
chunk is split in two:
  the kind part       the mean of the route's value over the chunk's look-alikes in the other
                      products (what a chunk of this kind gets, whatever it is about)
  the specific part   the chunk's own value less that (what this chunk gets beyond its kind)
On the hundred, inside the question's product, cached query side, no model call: the order by the
specific part of the three routes, alone and added to the plain order (the three routes'
standings added), beside the plain order and the kind part alone. Printed: context_recall_id and
on how many questions the first chunk is gold.

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/the_specific_part.py [gold100]
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
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
BUDGET = 72000
CACHE = REPO / "output/private/artefact_v4_cache/querytag"

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the specific part")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
et, ec = layer["edge_tag"], layer["edge_chunk"]
docs, record_sets, length = {}, [], np.zeros(n, dtype=np.int64)
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    record_sets.append(frozenset(str(x) for x in ids))
    length[i] = len(text)
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b
CV = np.array(p.chunk_vectors, dtype=np.float64)
CV = CV / np.linalg.norm(CV, axis=1, keepdims=True)
near = (CV @ CV.T).astype(np.float32)
alike = np.zeros((n, len(branches)), dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    alike[:, b] = chunks[np.argmax(near[:, chunks], axis=1)]
del near
print("prepared", flush=True)


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


recall, first_gold = defaultdict(list), defaultdict(list)
done = 0
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    description, tags, asked = side_of(q)
    answer = V._tag_cosines(description, tags, p)[0]
    rows, d_description = list(answer["tags"]), np.asarray(answer["description"], dtype=np.float64)
    if asked:
        rows += list(V._tag_cosines(description, asked, p)[0]["tags"])
    rows = np.array(rows, dtype=np.float64)
    d_question = np.asarray(V._query_cosines(q.question, [], p)[0]["query_description_cosines"], dtype=np.float64)
    gold = np.array([bool(record_sets[i] & cites) for i in range(n)])
    main = Counter(branch_of[np.flatnonzero(gold)].tolist()).most_common(1)[0][0]
    inside = np.flatnonzero(branch_of == main)
    t_near, t_edge = WK.best_edges(rows[:, et].max(axis=0), ec, n)
    t_near = np.where(t_edge >= 0, t_near, t_near[t_edge >= 0].min())
    others = [b for b in range(len(branches)) if b != main]
    look = alike[inside][:, others]
    routes = {"tags": t_near, "description": d_description, "question": d_question}
    own = {name: value[inside] for name, value in routes.items()}
    kind_part = {name: value[look].mean(axis=1) for name, value in routes.items()}
    specific = {name: own[name] - kind_part[name] for name in routes}
    plain = sum(standing(v) for v in own.values())
    scores = {
        "the plain order (the three routes' standings added)": plain,
        "the kind part alone": sum(standing(v) for v in kind_part.values()),
        "the specific part alone": sum(standing(v) for v in specific.values()),
        "the plain order with the specific part added": plain + sum(standing(v) for v in specific.values()),
        "the specific part of the two description routes only, with the tags' route as it is":
            standing(own["tags"]) + standing(specific["description"]) + standing(specific["question"]),
    }
    for name, score in scores.items():
        order = inside[np.lexsort((id_rank[inside], -score))]
        fits = np.cumsum(length[order]) <= BUDGET
        kept = order[:int(fits.sum()) if fits.all() else int(np.argmin(fits))]
        got = set().union(*(record_sets[i] for i in kept)) if kept.size else set()
        recall[name].append(len(cites & got) / len(cites))
        first_gold[name].append(bool(gold[order[0]]))
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

print(f"\n{SET}: {len(wanted)} questions, inside the question's product")
print("== context_recall_id (share of the cited records delivered inside 72,000 characters) | the first chunk is "
      "gold, questions ==")
for name, values in recall.items():
    print(f"  {float(np.mean(values)):.3f} | {sum(first_gold[name])} of {len(values)}  {name}")
print("done", flush=True)

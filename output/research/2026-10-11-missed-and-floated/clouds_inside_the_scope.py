"""His 2026-10-11 "doing the cluster clouds could be a combination thing. We could first use both the
clouds and then after, still limited by the chosen scope. Or perhaps you do the scope first and
then you scope the cloud, meaning the clouds give extra weight to specific areas of the scope
while perhaps still in the same branch."

On the hundred, cached query side, no model call. The chosen scope is the question's product (the
name border, right on 100 of 100). Relevance is the three routes' standings added. An area is a
parent (a channel or a file). The agent's readings, each the agent's own:

  both clouds, then the scope
      the tags' cloud and the description's cloud are the first cluster of each nearness over the
      WHOLE pool; then only the product's chunks are kept; the chunks both clouds hold come first,
      then the chunks one holds, then the rest; inside each the plain order
  the scope, then the clouds as weight on its areas
      inside the product a chunk gets, added to its own value as a standing, the value of the best
      chunk of its area; and the same with only the areas that hold a high chunk counting (high =
      the first cluster of the product's relevance), the other areas getting the lowest

Clusters three to seven are shown side by side. The gold ids are read inside this script; it
prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/clouds_inside_the_scope.py [gold100]
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
KS = (3, 4, 5, 6, 7)

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("clouds inside the scope")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
et, ec = layer["edge_tag"], layer["edge_chunk"]
docs, records, length, parent = {}, [], np.zeros(n, dtype=np.int64), []
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    records.append(frozenset(str(x) for x in ids))
    length[i] = len(text)
    parent.append(str(row["parent"]))
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b
parent_code = {name: k for k, name in enumerate(sorted(set(parent)))}
area = np.array([parent_code[name] for name in parent], dtype=np.int64)


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
    x = np.asarray(x, dtype=np.float64)
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


recall, delivered = defaultdict(list), Counter()
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
    t_near, t_edge = WK.best_edges(rows[:, et].max(axis=0), ec, n)
    t_near = np.where(t_edge >= 0, t_near, t_near[t_edge >= 0].min())
    base = standing(t_near[inside]) + standing(d_description[inside]) + standing(d_question[inside])
    areas = area[inside]
    best_of_area = np.full(areas.max() + 1, -np.inf)
    np.maximum.at(best_of_area, areas, base)
    area_best = best_of_area[areas]

    def score(name, keys):
        order = inside[np.lexsort((id_rank[inside], *[-np.asarray(key, dtype=np.float64) for key in reversed(keys)]))]
        kept = order[:kept_of(order)]
        delivered[name] += int(gold[kept].sum())
        got = set().union(*(records[i] for i in kept)) if kept.size else set()
        recall[name].append(len(cites & got) / len(cites))

    score("the plain order", [base])
    score("the scope, then every area's best chunk as weight on its chunks", [base + standing(area_best)])
    for k in KS:
        in_tags = (WK.levels(t_near, k) == 1)[inside]
        in_description = (WK.levels(d_description, k) == 1)[inside]
        held = in_tags.astype(int) + in_description.astype(int)
        score(f"both clouds over the pool, then the scope: held by both, by one, by none; {k} clusters", [held, base])
        high = WK.levels(base, k) == 1
        cloud_area = np.zeros(areas.max() + 1, dtype=bool)
        cloud_area[areas[high]] = True
        weight = np.where(cloud_area[areas], area_best, base.min())
        score(f"the scope, then the clouds as weight on their areas; {k} clusters", [base + standing(weight)])
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

first = "the plain order"
print(f"\n{SET}: {len(wanted)} questions, inside the question's product; gold chunks {gold_total}; budget {BUDGET}")
print("== gold chunks delivered | context_recall_id | against the plain order: mean difference, its standard error, "
      "questions higher / lower ==")
for name in recall:
    diff = np.asarray(recall[name]) - np.asarray(recall[first])
    print(f"  {delivered[name]} | {float(np.mean(recall[name])):.3f} | {float(diff.mean()):+.3f}, "
          f"{float(diff.std(ddof=1) / np.sqrt(diff.size)):.3f}, {int((diff > 0).sum())} / {int((diff < 0).sum())}  {name}")
print("done", flush=True)

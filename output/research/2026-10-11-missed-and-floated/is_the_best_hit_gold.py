"""His 2026-10-11 question "So the best hit of tags or chunk is not always a gold?". On the hundred,
inside the question's product, cached query side, no model call.

A route's best hit is the chunk it puts first:
  tags          the chunk whose closest tag stands nearest a query tag (several chunks can carry
                that tag and tie; the tie group is counted too)
  description   the chunk whose description stands nearest the query description
  question      the chunk whose description stands nearest the question
  the three     the three routes' standings added
Printed per route: on how many questions the best hit is a gold chunk, and what it delivers as
the search-start with the chunks whose descriptions are nearest it as the search-range (as many
as fit in 72,000 characters). Then the tags' best hit and the description's best hit together:
how often they are the same chunk, and how often gold then.

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/is_the_best_hit_gold.py [gold100]
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
p = V.prepare_over_corpus("is the best hit gold")
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


first_gold, start_reach, tied, tied_any, top_three = (defaultdict(list) for _ in range(5))
same, same_gold, differ_tags_gold, differ_description_gold, either_gold = [], [], [], [], []
base_rate, plain_recall = [], []
tie_pick, tie_sizes, tie_has_gold, tie_share = defaultdict(list), [], [], []
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
    m = inside.size
    is_gold = gold[inside]
    base_rate.append(float(is_gold.mean()))
    t_near, t_edge = WK.best_edges(rows[:, et].max(axis=0), ec, n)
    t_near = np.where(t_edge >= 0, t_near, t_near[t_edge >= 0].min())
    routes = {"tags": t_near[inside], "description": d_description[inside], "question": d_question[inside]}
    routes["the three routes added"] = sum(standing(v) for v in list(routes.values()))
    sizes = length[inside]
    among = CV[inside] @ CV[inside].T

    def delivered(order):
        fits = np.cumsum(sizes[order]) <= BUDGET
        return order[:int(fits.sum()) if fits.all() else int(np.argmin(fits))]

    def got(kept):
        have = set().union(*(record_sets[inside[k]] for k in kept)) if len(kept) else set()
        return len(cites & have) / len(cites)

    plain_recall.append(got(delivered(np.lexsort((id_rank[inside], -routes["the three routes added"])))))
    firsts = {}
    for name, value in routes.items():
        order = np.lexsort((id_rank[inside], -value))
        best = int(order[0])
        firsts[name] = best
        first_gold[name].append(float(is_gold[best]))
        top_three[name].append(float(is_gold[order[:3]].any()))
        group = np.flatnonzero(value >= value[best] - 1e-12)
        tied[name].append(group.size)
        tied_any[name].append(float(is_gold[group].any()))
        near = among[best].copy()
        near[best] = np.inf
        start_reach[name].append(got(delivered(np.lexsort((id_rank[inside], -near)))))
    # inside the tags' tie group (the chunks that carry the closest tag): which one, by what
    value = routes["tags"]
    group = np.flatnonzero(value >= value.max() - 1e-12)
    edge = t_edge[inside][group]
    inside_tie = {"the chunk's id (what a bare tie falls back on)": -id_rank[inside][group].astype(np.float64),
                  "the description's nearness to the query description": routes["description"][group],
                  "the description's nearness to the question": routes["question"][group],
                  "both of those (standings added)": (standing(routes["description"]) + standing(routes["question"]))[group]}
    for j, facet in enumerate(WK.FACETS):
        inside_tie[f"the {facet} value on the edge from that tag to the chunk"] = np.where(
            edge >= 0, layer["raw"][np.maximum(edge, 0), j], -np.inf)
    for name, score in inside_tie.items():
        tie_pick[name].append(float(is_gold[group[int(np.argmax(score))]]))
    tie_sizes.append(group.size)
    tie_has_gold.append(float(is_gold[group].any()))
    tie_share.append(float(is_gold[group].mean()))
    a, b = firsts["tags"], firsts["description"]
    same.append(float(a == b))
    either_gold.append(float(is_gold[a] or is_gold[b]))
    if a == b:
        same_gold.append(float(is_gold[a]))
    else:
        differ_tags_gold.append(float(is_gold[a]))
        differ_description_gold.append(float(is_gold[b]))
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

count = len(wanted)
print(f"\n{SET}: {count} questions, inside the question's product; a chunk of the product is gold "
      f"{float(np.mean(base_rate)):.0%} of the time; the three routes added deliver context_recall_id "
      f"{float(np.mean(plain_recall)):.3f}")
print("\n== a route's best hit: gold on how many questions | a gold chunk among its first three | chunks that tie at "
      "the top, the middle | a gold chunk in that tie group | context_recall_id with the best hit as the "
      "search-start and the chunks nearest it by description as the search-range ==")
for name in first_gold:
    print(f"  {name}: {int(sum(first_gold[name]))} of {count} | {int(sum(top_three[name]))} of {count} | "
          f"{np.median(tied[name]):.0f} | {int(sum(tied_any[name]))} of {count} | {float(np.mean(start_reach[name])):.3f}")
print("\n== the tags' best hit and the description's best hit ==")
print(f"  the same chunk on {int(sum(same))} of {count} questions; gold then on {int(sum(same_gold))} of {len(same_gold)}")
print(f"  two different chunks on {len(differ_tags_gold)}: the tags' one gold on {int(sum(differ_tags_gold))}, "
      f"the description's one gold on {int(sum(differ_description_gold))}")
print(f"  at least one of the two gold on {int(sum(either_gold))} of {count}")
print()
print(f"== inside the tags' tie group (the chunks that carry the closest tag; {np.median(tie_sizes):.0f} chunks at the "
      f"middle, {np.percentile(tie_sizes, 25):.0f}-{np.percentile(tie_sizes, 75):.0f}; a gold chunk among them on "
      f"{int(sum(tie_has_gold))} of {count}; {float(np.mean(tie_share)):.0%} of the group gold on average): the chunk "
      "picked is gold on how many questions, picked by ==")
for name, values in tie_pick.items():
    print(f"  {int(sum(values))} of {count}  {name}")
print("done", flush=True)

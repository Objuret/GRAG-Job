"""His 2026-10-11 "they ARE found, they are just not FLOATED.. meaning we actually DO find them with
the tags etc?". On the hundred, inside the gold's branch, cached query side, no model call.

Found by the tags, the way the arm picks: a query tag picks its 5 nearest graph tags (HERB_V4_K),
and a chunk is hit when it carries a picked tag. Read without a number too: for the chunk's
closest tag, its place among ALL the graph tags by nearness to a query tag, the best over the
query tags; a chunk is hit at any pick at least that wide.

Found by the descriptions: the chunk is in the first of the five clusters the branch's
description nearness is cut into (against the query description; against the question).

Floated: among the chunks the three routes' standings added deliver inside 72,000 characters.

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/hit_or_floated.py [gold100]
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
ROUTES = ("tags", "description", "question")
CACHE = REPO / "output/private/artefact_v4_cache/querytag"
K = V._k_nearest()
GROUPS = ("gold and floated", "gold and missed", "not gold and floated")

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("hit or floated")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
kind_names, kind_of = layer["kind_names"], layer["kind"]
et, ec, eligible = layer["edge_tag"], layer["edge_chunk"], layer["eligible"]
docs, records, length = {}, [], np.zeros(n, dtype=np.int64)
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    records.append(frozenset(str(x) for x in ids))
    length[i] = len(text)
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b


def cached_sides():
    out = []
    for f in CACHE.glob("*.json"):
        if f.name.endswith(".started.json"):
            continue
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        raw = j.get("raw")
        if j.get("ok") and isinstance(raw, dict) and raw.get("description") and raw.get("tags"):
            out.append((f.stat().st_mtime, (j.get("signature") or {}).get("user") or "", raw))
    return sorted(out, key=lambda row: -row[0])


SIDES = cached_sides()


def side_of(q):
    def names(rows):
        return list(dict.fromkeys(str(r["t"]).strip() for r in rows or []
                                  if isinstance(r, dict) and str(r.get("t", "")).strip()))
    for _, user, raw in SIDES:
        if q.question in user:
            return str(raw["description"]), names(raw.get("tags")), names(raw.get("query_tags"))
    raise SystemExit(f"no cached first call for {q.id}")


def kept_of(order):
    fits = np.cumsum(length[order]) <= BUDGET
    return int(fits.sum()) if fits.all() else int(np.argmin(fits))


def standing(x):
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
per_question = defaultdict(list)
done = 0
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    description, tags, asked = side_of(q)
    got, _, _ = V._tag_cosines(description, tags, p)
    rows, d_description = list(got["tags"]), np.asarray(got["description"], dtype=np.float64)
    if asked:
        rows += list(V._tag_cosines(description, asked, p)[0]["tags"])
    rows = np.array(rows, dtype=np.float64)
    d_question = np.asarray(V._query_cosines(q.question, [], p)[0]["query_description_cosines"], dtype=np.float64)
    # the place of every graph tag among the eligible graph tags, per query tag; a chunk's best over its tags and
    # over the query tags
    place_of_tag = np.full(rows.shape, np.inf)
    place_of_tag[:, eligible] = np.array([rankdata(-row[eligible], method="min") for row in rows])
    on_edge = place_of_tag[:, et].min(axis=0)
    best_place = np.full(n, np.inf)
    np.minimum.at(best_place, ec, on_edge)
    t_near, t_edge = WK.best_edges(rows[:, et].max(axis=0), ec, n)
    t_near = np.where(t_edge >= 0, t_near, t_near[t_edge >= 0].min())
    signal = {"tags": t_near, "description": d_description, "question": d_question}
    gold = np.array([bool(records[i] & cites) for i in range(n)])
    main = Counter(branch_of[np.flatnonzero(gold)].tolist()).most_common(1)[0][0]
    inside = np.flatnonzero(branch_of == main)
    x = {r: signal[r][inside] for r in ROUTES}
    first = {r: WK.levels(x[r], K) == 1 for r in ROUTES}
    base = sum(standing(x[r]) for r in ROUTES)
    order = inside[np.lexsort((id_rank[inside], -base))]
    floated = set(order[:kept_of(order)].tolist())
    hit = best_place[inside] <= K
    per_question["chunks of the branch"].append(inside.size)
    per_question["chunks of the branch that carry a picked tag"].append(int(hit.sum()))
    per_question["gold chunks"].append(int(gold[inside].sum()))
    per_question["gold chunks that carry a picked tag"].append(int((hit & gold[inside]).sum()))
    per_question["chunks in the first cluster of the description nearness"].append(int(first["description"].sum()))
    per_question["gold chunks in it"].append(int((first["description"] & gold[inside]).sum()))
    per_question["chunks over the whole pool that carry a picked tag"].append(int((best_place <= K).sum()))
    for k, c in enumerate(inside.tolist()):
        if gold[c]:
            group = GROUPS[0] if c in floated else GROUPS[1]
        elif c in floated:
            group = GROUPS[2]
        else:
            continue
        either = bool(hit[k] or first["description"][k] or first["question"][k])
        values = {"carries a picked tag": float(hit[k]), "place of its closest tag among all graph tags": best_place[c],
                  "in the first cluster of the tags' nearness": float(first["tags"][k]),
                  "in the first cluster of the description against the query description": float(first["description"][k]),
                  "in the first cluster of the description against the question": float(first["question"][k]),
                  "carries a picked tag or is in a first description cluster": float(either)}
        for where in (kind_names[kind_of[c]], "all kinds"):
            for name, value in values.items():
                data[where][group][name].append(float(value))
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)


def spread_of(values):
    q1, mid, q3 = np.percentile(np.asarray(values, dtype=np.float64), [25, 50, 75])
    return f"{mid:.0f} ({q1:.0f}-{q3:.0f})"


print(f"\n{SET}: {len(wanted)} questions, inside the gold's branch; a query tag picks its {K} nearest graph tags; "
      f"nearness cut into {K} clusters")
print("== per question, the middle (a quarter - three quarters) ==")
for name, values in per_question.items():
    print(f"  {name}: {spread_of(values)}")
order_of_kinds = ["all kinds"] + sorted((k for k in data if k != "all kinds"),
                                        key=lambda k: -sum(len(data[k][g]["carries a picked tag"]) for g in GROUPS[:2]))
for kind in order_of_kinds:
    counts = [len(data[kind][g]["carries a picked tag"]) for g in GROUPS]
    if not (counts[0] + counts[1]):
        continue
    print(f"\n== {kind}: {GROUPS[0]} {counts[0]} | {GROUPS[1]} {counts[1]} | {GROUPS[2]} {counts[2]} ==")
    for name in ("carries a picked tag", "in the first cluster of the tags' nearness",
                 "in the first cluster of the description against the query description",
                 "in the first cluster of the description against the question",
                 "carries a picked tag or is in a first description cluster"):
        cells = []
        for g in GROUPS:
            values = data[kind][g][name]
            cells.append(f"{int(sum(values))} of {len(values)}" if values else "-")
        print(f"  {name}: " + " | ".join(cells))
    cells = [spread_of(data[kind][g]["place of its closest tag among all graph tags"])
             if data[kind][g]["place of its closest tag among all graph tags"] else "-" for g in GROUPS]
    print("  place of its closest tag among all the graph tags, for its best query tag: " + " | ".join(cells))
print("done", flush=True)

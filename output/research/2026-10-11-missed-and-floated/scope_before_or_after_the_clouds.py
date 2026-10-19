"""His 2026-10-12 "take that last cloud combo style.. How does scope before or after affect that?". The
combo: the chunk descriptions' nearness to the query description and the tags' nearness (a
chunk's closest tag to any query tag) are each cut into five clusters (`v4_walk.levels`, 1 the
nearest), and the two clouds are overlapped step by step: both in their first cluster; one in
its first and the other in its second; both in their second; everywhere else.

Three ways, on the hundred, cached query side, no model call:
  scope before   the border first (the product whose name stands in the question), the clusters
                 made from the product's chunks only
  scope after    the clusters made from every chunk of the pool, then the border: chunks of other
                 products are cut out of each step
  no scope       the clusters made from every chunk of the pool, nothing cut

Printed per way and step: chunks a question, what share of them is gold, and for scope after how
many chunks a question the border cuts out of the step. Then the first chunk gold (of 100) and
context_recall_id (share of the cited records delivered inside 72,000 characters) for two
orders: the chunk cloud first, ordered by the tags; and the two levels added.

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/scope_before_or_after_the_clouds.py [gold100]
"""
import json
import os
import sys
import warnings
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
CLUSTERS = 5
CACHE = REPO / "output/private/artefact_v4_cache/querytag"
STEPS = ("both in their first cluster", "one in its first, the other in its second", "both in their second",
         "everywhere else")

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("scope before or after the clouds")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
et, ec = layer["edge_tag"], layer["edge_chunk"]
docs, record_sets, length = {}, [], np.zeros(n, dtype=np.int64)
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    record_sets.append(frozenset(str(x) for x in ids))
    length[i] = len(text)
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


def steps_of(level_d, level_t):
    first = (level_d == 1) & (level_t == 1)
    mixed = ((level_d == 1) & (level_t == 2)) | ((level_d == 2) & (level_t == 1))
    second = (level_d == 2) & (level_t == 2)
    return {STEPS[0]: first, STEPS[1]: mixed, STEPS[2]: second, STEPS[3]: ~(first | mixed | second)}


def delivered(order, cites):
    order = np.asarray(order, dtype=np.int64)
    fits = np.cumsum(length[order]) <= BUDGET
    kept = order[:int(fits.sum()) if fits.all() else int(np.argmin(fits))]
    have = set().union(*(record_sets[i] for i in kept)) if kept.size else set()
    return len(cites & have) / len(cites)


WAYS = ("scope before", "scope after", "no scope")
cells = {way: {step: [0, 0, 0] for step in STEPS} for way in WAYS}       # chunks, gold, cut out by the border
first = {way: {"the chunk cloud first, ordered by the tags": 0, "the two levels added": 0} for way in WAYS}
recall = {way: {"the chunk cloud first, ordered by the tags": [], "the two levels added": []} for way in WAYS}
sizes = {way: [] for way in WAYS}
spread_d = {way: np.zeros(CLUSTERS) for way in WAYS}      # the product's chunks in each description cluster
spread_t = {way: np.zeros(CLUSTERS) for way in WAYS}
gold_d = {way: np.zeros(CLUSTERS) for way in WAYS}
edges = {way: [] for way in WAYS}                         # the lowest description nearness still in the first cluster
done = 0
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    description, tags, asked = side_of(q)
    answer = V._tag_cosines(description, tags, p)[0]
    rows, D = list(answer["tags"]), np.asarray(answer["description"], dtype=np.float64)
    if asked:
        rows += list(V._tag_cosines(description, asked, p)[0]["tags"])
    rows = np.array(rows, dtype=np.float64)
    t_near, t_edge = WK.best_edges(rows[:, et].max(axis=0), ec, n)
    T = np.where(t_edge >= 0, t_near, t_near[t_edge >= 0].min())
    gold = np.array([bool(record_sets[i] & cites) for i in range(n)])
    border, scope = V.scope_by_name(q.question, p.tree, n)
    inside = np.flatnonzero(border)
    every = np.arange(n)
    for way in WAYS:
        made_from = inside if way == "scope before" else every
        level_d = np.zeros(n, dtype=np.int64)
        level_t = np.zeros(n, dtype=np.int64)
        level_d[made_from] = WK.levels(D[made_from], CLUSTERS)
        level_t[made_from] = WK.levels(T[made_from], CLUSTERS)
        z_d, z_t = np.zeros(n), np.zeros(n)
        z_d[made_from], z_t[made_from] = standing(D[made_from]), standing(T[made_from])
        kept = inside if way != "no scope" else every
        sizes[way].append(int((level_d[made_from] == 1).sum()))
        for level in range(1, CLUSTERS + 1):
            spread_d[way][level - 1] += int((level_d[inside] == level).sum())
            spread_t[way][level - 1] += int((level_t[inside] == level).sum())
            gold_d[way][level - 1] += int(gold[inside][level_d[inside] == level].sum())
        edges[way].append(float(D[made_from][level_d[made_from] == 1].min()))
        where = steps_of(level_d[made_from], level_t[made_from])
        in_border = border[made_from]
        for step, mask in where.items():
            held = mask & (in_border if way != "no scope" else True)
            cells[way][step][0] += int(held.sum())
            cells[way][step][1] += int(gold[made_from][held].sum())
            cells[way][step][2] += int((mask & ~in_border).sum()) if way == "scope after" else 0
        cloud_by_tags = np.where(level_d[kept] == 1, 1e3 + z_t[kept], z_d[kept])
        levels_added = -(level_d[kept] + level_t[kept]).astype(float) + (z_d[kept] + z_t[kept]) / 1e3
        for name, score in (("the chunk cloud first, ordered by the tags", cloud_by_tags),
                            ("the two levels added", levels_added)):
            order = kept[np.lexsort((id_rank[kept], -score))]
            first[way][name] += int(gold[order[0]])
            recall[way][name].append(delivered(order, cites))
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

count = len(wanted)
print(f"\n{SET}: {count} questions; a chunk of the question's product is gold 6% of the time, a chunk of the whole pool 0.2%")
for way in WAYS:
    print(f"\n==== {way} (the description's first cluster is {np.median(sizes[way]):.0f} chunks at the middle, "
          f"{np.percentile(sizes[way], 25):.0f}-{np.percentile(sizes[way], 75):.0f}) ====")
    for step in STEPS:
        chunks, golds, cut = cells[way][step]
        extra = f"; the border cuts {cut / count:.1f} chunks a question out of this step" if way == "scope after" else ""
        print(f"  {step}: {chunks / count:.1f} chunks a question, {golds / max(chunks, 1):.0%} of them gold{extra}")
    for name in first[way]:
        print(f"  first chunk gold {first[way][name]} of {count} | context_recall_id {float(np.mean(recall[way][name])):.3f}  {name}")
print()
print("== the PRODUCT's chunks in each of the five clusters (1 the nearest), chunks a question; then the share of them gold ==")
for way in ("scope before", "scope after"):
    print(f"  {way}, descriptions: " + ", ".join(f"{v / count:.1f}" for v in spread_d[way]) + "   gold: "
          + ", ".join(f"{g / max(v, 1):.0%}" for g, v in zip(gold_d[way], spread_d[way])))
    print(f"  {way}, tags:         " + ", ".join(f"{v / count:.1f}" for v in spread_t[way]))
    print(f"  {way}: the lowest description nearness still in the first cluster, the middle: {np.median(edges[way]):.3f}")
print("done", flush=True)

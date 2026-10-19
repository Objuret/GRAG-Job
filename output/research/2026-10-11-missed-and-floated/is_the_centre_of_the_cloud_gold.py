"""His 2026-10-11 question "If we cloud the chunks for example, is the most center of them gold?". On
the hundred, inside the question's product, cached query side, no model call.

A cloud is a set of chunks; its centre is the chunk whose description stands nearest the other
chunks of the cloud on average. Six clouds, so the answer does not hang on one reading:
  the delivered chunks              what the three routes added deliver inside 72,000 characters
  the first cluster of the three    the first of five clusters of the three routes' added values
  the first cluster by description  the first of five clusters of the description's nearness to
                                    the query description
  the chunks with a picked tag      the chunks that carry one of a query tag's five nearest tags
  the hits                          the last two together
  the hits in their fullest parent  the hits that sit in the parent holding most of them
Printed per cloud: its size, how much of it is gold (what a blind pick inside it gives), on how
many questions it holds a gold chunk at all, on how many its centre is gold, and on how many its
highest chunk by the three routes added is gold.

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/is_the_centre_of_the_cloud_gold.py [gold100]
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
CLUSTERS = 5
CACHE = REPO / "output/private/artefact_v4_cache/querytag"
K = V._k_nearest()

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("is the centre of the cloud gold")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
et, ec, eligible = layer["edge_tag"], layer["edge_chunk"], layer["eligible"]
docs, record_sets, length, parent = {}, [], np.zeros(n, dtype=np.int64), []
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    record_sets.append(frozenset(str(x) for x in ids))
    length[i] = len(text)
    parent.append(str(row["parent"]))
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


facts = defaultdict(lambda: defaultdict(list))
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
    t_near, t_edge = WK.best_edges(rows[:, et].max(axis=0), ec, n)
    t_near = np.where(t_edge >= 0, t_near, t_near[t_edge >= 0].min())
    plain = standing(t_near[inside]) + standing(d_description[inside]) + standing(d_question[inside])
    order = np.lexsort((id_rank[inside], -plain))
    fits = np.cumsum(length[inside][order]) <= BUDGET
    sent = order[:int(fits.sum()) if fits.all() else int(np.argmin(fits))]
    kth = np.sort(rows[:, eligible], axis=1)[:, ::-1][:, K - 1]
    picked_edge = ((rows[:, et] >= kth[:, None]) & eligible[et]).any(axis=0)
    with_tag = np.zeros(n, dtype=bool)
    with_tag[ec[picked_edge]] = True
    by_description = WK.levels(d_description[inside], CLUSTERS) == 1
    hits = with_tag[inside] | by_description
    in_parent = Counter(parent[c] for c in inside[hits].tolist())
    fullest = in_parent.most_common(1)[0][0] if in_parent else None
    clouds = {
        "the delivered chunks": sent,
        "the first cluster of the three routes added": np.flatnonzero(WK.levels(plain, CLUSTERS) == 1),
        "the first cluster by description": np.flatnonzero(by_description),
        "the chunks with a picked tag": np.flatnonzero(with_tag[inside]),
        "the hits (the two together)": np.flatnonzero(hits),
        "the hits in their fullest parent": np.array([k for k in np.flatnonzero(hits).tolist()
                                                      if parent[inside[k]] == fullest], dtype=np.int64),
    }
    among = CV[inside] @ CV[inside].T
    for name, cloud in clouds.items():
        row = facts[name]
        row["size"].append(cloud.size)
        if not cloud.size:
            for key in ("gold share", "holds gold", "centre gold", "highest gold"):
                row[key].append(0.)
            continue
        inner = among[np.ix_(cloud, cloud)].copy()
        np.fill_diagonal(inner, 0.)
        central = inner.sum(axis=1) / max(cloud.size - 1, 1)
        centre = int(cloud[np.lexsort((id_rank[inside][cloud], -plain[cloud], -central))[0]])
        highest = int(cloud[np.lexsort((id_rank[inside][cloud], -plain[cloud]))[0]])
        row["gold share"].append(float(is_gold[cloud].mean()))
        row["holds gold"].append(float(is_gold[cloud].any()))
        row["centre gold"].append(float(is_gold[centre]))
        row["highest gold"].append(float(is_gold[highest]))
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

count = len(wanted)
print(f"\n{SET}: {count} questions, inside the question's product")
print("== cloud | chunks in it, the middle | share of it that is gold (a blind pick inside it) | it holds a gold "
      "chunk, questions | its centre is gold, questions | its highest chunk by the three routes added is gold, "
      "questions ==")
for name, row in facts.items():
    size = row["size"]
    print(f"  {name} | {np.median(size):.0f} ({np.percentile(size, 25):.0f}-{np.percentile(size, 75):.0f}) | "
          f"{float(np.mean(row['gold share'])):.0%} | {int(sum(row['holds gold']))} of {count} | "
          f"{int(sum(row['centre gold']))} of {count} | {int(sum(row['highest gold']))} of {count}")
print("done", flush=True)

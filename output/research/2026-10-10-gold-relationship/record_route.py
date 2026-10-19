"""His 2026-10-11 goal, one more reading: the single records inside a chunk. A chunk is about ten
records and the routes read a summary of the ten (its description, its tags); the cited record
is one of them. Here a chunk's value is the closeness of its closest RECORD to the question, from
the record vectors the vector baseline already has (records behind "passage: ", the question
behind "query: ", the embedder's own pairing).

On the hundred, cached query side, no model call: the record reading alone and added to the three
routes, inside the gold's branch and inside the branch a gauge points at; and which gauge points
at the gold's branch. The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-10-gold-relationship/record_route.py [gold100]
"""
import json
import os
import sys
import warnings
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
BUDGET = 72000
ROUTES = ("tags", "description", "question")
CACHE = REPO / "output/private/artefact_v4_cache/querytag"
KEPT = REPO / "output/embed_local/20261007_rev113abe4acafa_float32"

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the record route")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
docs, records, length = {}, [], np.zeros(n, dtype=np.int64)
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    records.append([str(x) for x in ids])
    length[i] = len(text)
corpus = np.load(KEPT / "corpus_passage.npz", allow_pickle=True)
row_of = {str(r): k for k, r in enumerate(corpus["ids"])}
matrix = np.asarray(corpus["matrix"], dtype=np.float32)
asked_vectors = np.load(KEPT / "question_query_vecs.npz", allow_pickle=True)
question_at = {str(q): k for k, q in enumerate(asked_vectors["ids"])}
rows_of = [np.array([row_of[r] for r in recs if r in row_of], dtype=np.int64) for recs in records]
chunk_of_row = np.full(matrix.shape[0], -1, dtype=np.int64)
for i, rows in enumerate(rows_of):
    chunk_of_row[rows] = i
print(f"{SET}: {len(wanted)} questions; pool {n} chunks; chunks with a record vector {sum(r.size > 0 for r in rows_of)}; "
      f"record vectors inside pool chunks {int((chunk_of_row >= 0).sum())} of {matrix.shape[0]}")
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b
record_sets = [frozenset(r) for r in records]


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


def recall_of(order, cites):
    order = np.asarray(order, dtype=np.int64)
    kept = kept_of(order)
    got = set().union(*(record_sets[i] for i in order[:kept])) if kept else set()
    return len(cites & got) / len(cites)


def by_value(chunks, value):
    return chunks[np.lexsort((id_rank[chunks], -value))]


def standing(x):
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


scores = {"gold": {}, "gauged": {}}
places = {}
gauge = Counter()
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
    on_edge = rows[:, layer["edge_tag"]]
    t_near, t_edge = WK.best_edges(on_edge.max(axis=0), layer["edge_chunk"], n)
    t_near = np.where(t_edge >= 0, t_near, t_near[t_edge >= 0].min())
    # the record reading: every record's closeness to the question, a chunk takes its closest record's
    near = matrix @ np.asarray(asked_vectors["matrix"][question_at[qid]], dtype=np.float32)
    best = np.full(n, float(near.min()))
    mean_top = np.full(n, float(near.min()))
    for i, at in enumerate(rows_of):
        if at.size:
            best[i] = float(near[at].max())
            mean_top[i] = float(near[at].mean())
    signal = {"tags": t_near, "description": d_description, "question": d_question, "record": best, "records mean": mean_top}
    gold = np.array([bool(record_sets[i] & cites) for i in range(n)])
    main = Counter(branch_of[np.flatnonzero(gold)].tolist()).most_common(1)[0][0]

    # which gauge points at the gold's branch: the branch most of an order's own delivery sits in
    def points(value):
        order = np.lexsort((id_rank, -value))
        counts = np.bincount(branch_of[order[:kept_of(order)]], minlength=len(branches))
        return int(counts.argmax())
    pointed = {"question": points(d_question), "record": points(best),
               "question and record": points(standing(d_question) + standing(best)),
               "all four": points(sum(standing(signal[r]) for r in (*ROUTES, "record")))}
    for name, b in pointed.items():
        gauge[name] += int(b == main)
    # the records themselves, with no chunk in between: the branch most of the closest records sit in
    top_rows = np.argsort(-near)[:200]
    top_rows = top_rows[chunk_of_row[top_rows] >= 0]
    gauge["the closest records' branch"] += int(Counter(branch_of[chunk_of_row[top_rows]].tolist()).most_common(1)[0][0] == main)

    for where, branch in (("gold", main), ("gauged", pointed["all four"])):
        inside = np.flatnonzero(branch_of == branch)
        z = {r: standing(signal[r][inside]) for r in signal}
        cand = {
            "the three routes' standings added": sum(z[r] for r in ROUTES),
            "the record reading alone (a chunk's closest record to the question)": z["record"],
            "the mean of a chunk's records' closeness alone": z["records mean"],
            "three routes + the record reading (standings added)": sum(z[r] for r in ROUTES) + z["record"],
            "tags + description + the record reading (standings added)": z["tags"] + z["description"] + z["record"],
            "tags + the record reading (standings added)": z["tags"] + z["record"],
            "three routes + the record reading, the record reading counted twice": sum(z[r] for r in ROUTES) + 2 * z["record"],
        }
        for name, value in cand.items():
            scores[where].setdefault(name, []).append(recall_of(by_value(inside, value), cites))
            if where == "gold":
                places.setdefault(name, []).extend(rankdata(-value, method="average")[gold[inside]].tolist())
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

m = len(wanted)
print(f"\n{SET}: {m} questions")
print("== the branch a reading's own delivery points at is the gold's branch, questions of the hundred ==")
print("  " + ", ".join(f"{name} {count}" for name, count in gauge.items()))
print("\n== context_recall_id at the budget, mean: inside the gold's branch | inside the branch all four readings "
      "point at | the gold chunks' middle place ==")
for name in sorted(scores["gold"], key=lambda k: -float(np.mean(scores["gold"][k]))):
    print(f"  {float(np.mean(scores['gold'][name])):.3f} | {float(np.mean(scores['gauged'][name])):.3f} | "
          f"{np.median(places[name]):.0f}  {name}")
np.save(HERE / f"record_route__{SET}.npy", scores, allow_pickle=True)
print("done", flush=True)

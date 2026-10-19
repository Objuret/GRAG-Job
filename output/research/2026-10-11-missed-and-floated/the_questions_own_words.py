"""Where the information that tells one case from another sits: the question's own words read
literally against the chunks' own text, inside the gold's branch. A diagnosis, not a proposal for
the arm (it is what the lucene baseline reads, here held to one branch).

BM25 with Lucene's standard settings (k1 1.2, b 0.75), the weight of a word taken from how many
chunks of the branch hold it, so a word every chunk of the branch has counts for nothing.

On the hundred, cached query side, no model call. The gold ids and the question texts are read
inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/the_questions_own_words.py [gold100]
"""
import json
import math
import os
import re
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
K1, B = 1.2, 0.75
TOKEN = re.compile(r"[a-z0-9]+")
BANDS = ("places 1-5", "places 6-15", "places 16-36", "further down")

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the question's own words")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
et, ec, eligible = layer["edge_tag"], layer["edge_chunk"], layer["eligible"]
docs, records, length, words = {}, [], np.zeros(n, dtype=np.int64), []
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    records.append(frozenset(str(x) for x in ids))
    length[i] = len(text)
    words.append(Counter(TOKEN.findall(text.lower())))
size = np.array([sum(w.values()) for w in words], dtype=np.float64)
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b
held_by = {}


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


def band_of(place):
    return BANDS[0] if place <= 5 else BANDS[1] if place <= 15 else BANDS[2] if place <= 36 else BANDS[3]


table = defaultdict(lambda: [0, 0])
delivered, recall = Counter(), defaultdict(list)
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
    if main not in held_by:
        df = Counter()
        for c in inside.tolist():
            df.update(words[c].keys())
        held_by[main] = (df, float(size[inside].mean()))
    df, mean_size = held_by[main]
    m_here = inside.size
    asked_words = set(TOKEN.findall(q.question.lower()))
    bm25 = np.zeros(m_here)
    for word in asked_words:
        held = df.get(word, 0)
        if not held:
            continue
        idf = math.log(1. + (m_here - held + .5) / (held + .5))
        tf = np.array([words[c].get(word, 0) for c in inside.tolist()], dtype=np.float64)
        bm25 += idf * tf * (K1 + 1.) / (tf + K1 * (1. - B + B * size[inside] / mean_size))
    place_of_tag = np.full(rows.shape, np.inf)
    place_of_tag[:, eligible] = np.array([rankdata(-row[eligible], method="min") for row in rows])
    best_place = np.full(n, np.inf)
    np.minimum.at(best_place, ec, place_of_tag[:, et].min(axis=0))
    t_near, t_edge = WK.best_edges(rows[:, et].max(axis=0), ec, n)
    t_near = np.where(t_edge >= 0, t_near, t_near[t_edge >= 0].min())
    found = ((best_place[inside] <= K) | (WK.levels(d_description[inside], K) == 1)
             | (WK.levels(d_question[inside], K) == 1))
    base = standing(t_near[inside]) + standing(d_description[inside]) + standing(d_question[inside])
    lexical_place = rankdata(-bm25, method="min")
    for k, c in enumerate(inside.tolist()):
        for scope in ("hit" if found[k] else "not hit", "all"):
            cell = table[scope, band_of(lexical_place[k])]
            cell[0] += int(gold[c])
            cell[1] += 1

    def score(name, value):
        order = inside[np.lexsort((id_rank[inside], -value))]
        kept = order[:kept_of(order)]
        delivered[name] += int(gold[kept].sum())
        got = set().union(*(records[i] for i in kept)) if kept.size else set()
        recall[name].append(len(cites & got) / len(cites))

    score("the plain order: the three routes' standings added", base)
    score("the question's own words alone (BM25 inside the branch)", bm25)
    score("the plain order with the standing of the question's own words added", base + standing(bm25))
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

print(f"\n{SET}: {len(wanted)} questions, inside the gold's branch; gold chunks {gold_total}")
print("\n== a chunk's place in the branch by the question's own words: gold of chunks (share), among the hits | among "
      "the chunks not hit | all ==")
for band in BANDS:
    cells = []
    for scope in ("hit", "not hit", "all"):
        g, t = table[scope, band]
        cells.append(f"{g} of {t} ({(g / t if t else 0):.3f})")
    print(f"  {band}: " + " | ".join(cells))
print(f"\n== inside {BUDGET} characters: gold chunks delivered of {gold_total} | context_recall_id ==")
for name in delivered:
    print(f"  {delivered[name]} | {float(np.mean(recall[name])):.3f}  {name}")
print("done", flush=True)

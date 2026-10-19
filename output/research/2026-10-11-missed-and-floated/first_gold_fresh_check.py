"""A check on questions never used, for his 2026-10-11 goal "Explore this more to find the closest
first gold". On the gold hundred the question read WITHOUT the product's name, in the embedder's
own pairing (the question behind "query: ", the chunk descriptions behind "passage: "), put a
gold chunk first on 53 of 100 against 39 with the name. That was found after many readings were
tried on the same hundred, so it is checked here on other questions.

The questions: a seeded draw from the benchmark's questions that have citations and are in
neither the gold hundred nor the held-out hundred (both left as they are). Only readings that
need no first call are made, so there is no model call: the local embedder writes the question
with and without the name.

Stated before the run: inside the border the name sets (`scope_by_name`), the question without
the name puts a gold chunk first on more questions than the question with it, against the
descriptions (both pairings) and against the single records.

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/first_gold_fresh_check.py [300]
"""
import json
import math
import os
import random
import re
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

MANY = int(sys.argv[1]) if len(sys.argv) > 1 else 300
SEED = 20261011
BUDGET = 72000
KEPT = REPO / "output/embed_local/20261007_rev113abe4acafa_float32"
K1, B = 1.2, 0.75
TOKEN = re.compile(r"[a-z0-9]+")


def unit(m):
    m = np.asarray(m, dtype=np.float64)
    return m / np.maximum(np.linalg.norm(m, axis=-1, keepdims=True), 1e-12)


used = set()
for name in ("gold100", "heldout100"):
    used |= {json.loads(line)["id"] for line in (REPO / "data" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
             if line.strip()}
every = HQ.load_questions()
fresh = sorted((q for q in every if q.id not in used and q.citations), key=lambda q: q.id)
drawn = random.Random(SEED).sample(fresh, min(MANY, len(fresh)))
print(f"{len(every)} questions; {len(fresh)} with citations in neither hundred; {len(drawn)} drawn (seed {SEED})", flush=True)

p = V.prepare_over_corpus("first gold, a fresh check")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
docs, record_ids, length, words = {}, [], np.zeros(n, dtype=np.int64), []
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    record_ids.append([str(x) for x in ids])
    length[i] = len(text)
    words.append(Counter(TOKEN.findall(text.lower())))
record_sets = [frozenset(r) for r in record_ids]
size = np.array([sum(w.values()) for w in words], dtype=np.float64)
branches = V.tree_level(p.tree, "product")
CQ = unit(p.chunk_vectors)
desc_side = np.load(KEPT / "descriptions_passage.npz", allow_pickle=True)
desc_at = {str(c): k for k, c in enumerate(desc_side["ids"])}
CP = unit(desc_side["matrix"][[desc_at[str(c)] for c in p.chunk_ids]])
corpus = np.load(KEPT / "corpus_passage.npz", allow_pickle=True)
row_of = {str(r): k for k, r in enumerate(corpus["ids"])}
matrix = np.asarray(corpus["matrix"], dtype=np.float32)
matrix = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
rows_of = [np.array([row_of[r] for r in recs if r in row_of], dtype=np.int64) for recs in record_ids]
AXES = V._QueryAxes(unit(p.tag_vectors), np.eye(CQ.shape[1]))
print("prepared", flush=True)


def vector_of(text):
    return np.asarray(V._query_cosines(text, [], AXES)[0]["query_description_cosines"], dtype=np.float64)


def without_the_name(question, name):
    parts = TOKEN.findall(name.lower())
    pattern = re.compile(r"(?<![A-Za-z0-9])" + r"[^A-Za-z0-9]*".join(re.escape(part) for part in parts)
                         + r"(?![A-Za-z0-9])", re.IGNORECASE)
    return " ".join(pattern.sub("the product", question).split())


def standing(x):
    x = np.asarray(x, dtype=np.float64)
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


got = defaultdict(list)
types = []
no_name = several = no_gold_inside = 0
kept_types = Counter()
held_by = {}
done = 0
for q in drawn:
    first, scope = V.scope_by_name(q.question, p.tree, n)
    named = scope["names_in_the_question"]
    if not named:
        no_name += 1
        continue
    if len(named) > 1:
        several += 1
        continue
    inside = np.flatnonzero(first)
    cites = {str(c) for c in q.citations}
    gold = np.array([bool(record_sets[c] & cites) for c in inside.tolist()])
    if not gold.any():
        no_gold_inside += 1
        continue
    kept_types[str(q.type)] += 1
    types.append(str(q.type))
    m = inside.size
    vq, vb = vector_of(q.question), vector_of(without_the_name(q.question, named[0]))
    near_q, near_b = matrix @ vq.astype(np.float32), matrix @ vb.astype(np.float32)

    def records(near, top):
        return np.array([float(np.sort(near[rows_of[c]])[-top:].mean()) if rows_of[c].size else -1.
                         for c in inside.tolist()])
    if named[0] not in held_by:
        df = Counter()
        for c in inside.tolist():
            df.update(words[c].keys())
        held_by[named[0]] = (df, float(size[inside].mean()))
    df, mean_size = held_by[named[0]]
    own_words = np.zeros(m)
    for word in set(TOKEN.findall(q.question.lower())):
        held = df.get(word, 0)
        if held:
            tf = np.array([words[c].get(word, 0) for c in inside.tolist()], dtype=np.float64)
            own_words += (math.log(1. + (m - held + .5) / (held + .5)) * tf * (K1 + 1.)
                          / (tf + K1 * (1. - B + B * size[inside] / mean_size)))
    readings = {
        "with the name, descriptions, query both sides (today's question route)": CQ[inside] @ vq,
        "with the name, descriptions, own pairing (the old arm's question route)": CP[inside] @ vq,
        "without the name, descriptions, query both sides": CQ[inside] @ vb,
        "without the name, descriptions, own pairing": CP[inside] @ vb,
        "with the name, the closest record": records(near_q, 1),
        "without the name, the closest record": records(near_b, 1),
        "with the name, the two closest records": records(near_q, 2),
        "without the name, the two closest records": records(near_b, 2),
        "the question's words on the chunk text (BM25)": own_words,
    }
    readings["without the name: descriptions (own pairing) + the two closest records"] = (
        standing(readings["without the name, descriptions, own pairing"])
        + standing(readings["without the name, the two closest records"]))
    readings["with the name: descriptions (own pairing) + the two closest records"] = (
        standing(readings["with the name, descriptions, own pairing (the old arm's question route)"])
        + standing(readings["with the name, the two closest records"]))
    for name, score in readings.items():
        order = np.lexsort((id_rank[inside], -np.asarray(score, dtype=np.float64)))
        place = int(np.argmax(gold[order])) + 1
        fits = np.cumsum(length[inside][order]) <= BUDGET
        kept = order[:int(fits.sum()) if fits.all() else int(np.argmin(fits))]
        have = set().union(*(record_sets[inside[k]] for k in kept)) if kept.size else set()
        got[name].append((place, len(cites & have) / len(cites)))
    done += 1
    if done % 25 == 0:
        print(f"  ... {done} questions", flush=True)

count = len(next(iter(got.values()))) if got else 0
print(f"\n{len(drawn)} drawn; no product's name in the question {no_name}; more than one {several}; no gold chunk inside "
      f"the named product {no_gold_inside}; read: {count}; their types: {dict(kept_types)}")
print("== first chunk gold | share | first gold within 3 | within 5 | place of the first gold chunk, the middle | "
      "context_recall_id ==")
for name, rows in got.items():
    place = np.array([r[0] for r in rows])
    print(f"  {int((place == 1).sum()):3d} | {float((place == 1).mean()):.0%} | {int((place <= 3).sum()):3d} | "
          f"{int((place <= 5).sum()):3d} | {np.median(place):.0f} ({np.percentile(place, 25):.0f}-{np.percentile(place, 75):.0f}) | "
          f"{float(np.mean([r[1] for r in rows])):.3f}  {name}")
print("\n== paired: gold first with the first reading and not the second | the other way ==")
for a, b in (("without the name, descriptions, own pairing", "with the name, descriptions, own pairing (the old arm's question route)"),
             ("without the name, descriptions, own pairing", "with the name, descriptions, query both sides (today's question route)"),
             ("without the name, descriptions, query both sides", "with the name, descriptions, query both sides (today's question route)"),
             ("without the name, descriptions, own pairing", "without the name, descriptions, query both sides"),
             ("without the name, the two closest records", "with the name, the two closest records"),
             ("without the name, the closest record", "with the name, the closest record")):
    x = np.array([r[0] == 1 for r in got[a]])
    y = np.array([r[0] == 1 for r in got[b]])
    print(f"  {int((x & ~y).sum()):3d} | {int((~x & y).sum()):3d}  {a}  against  {b}")
print()
print("== by the benchmark's own type of question: questions | first chunk gold with the name, descriptions (query both "
      "sides) | without the name, the same | without the name, the two closest records | without the name, descriptions "
      "(own pairing) + the two closest records ==")
kinds = np.array(types)
picks = ("with the name, descriptions, query both sides (today's question route)",
         "without the name, descriptions, query both sides", "without the name, the two closest records",
         "without the name: descriptions (own pairing) + the two closest records")
for kind in sorted(set(types)):
    mask = kinds == kind
    cells = []
    for name in picks:
        first = np.array([r[0] == 1 for r in got[name]])[mask]
        cells.append(f"{int(first.sum())} ({first.mean():.0%})")
    print(f"  {kind}: {int(mask.sum())} | " + " | ".join(cells))
print("done", flush=True)

"""More readings for his 2026-10-11 goal "Explore this more to find the closest first gold", written
beside the first table (same questions, same chunks of the question's product). No model call
(the local embedder only).

  the embedder's own pairing   the model is made for a question behind "query: " against a text
                               behind "passage: ". The graph's descriptions and tags have stood
                               behind "query: " since 2026-10-08; their passage vectors of
                               2026-10-07 are on the side. Read here: the question (query)
                               against the descriptions (passage), the same with the product's
                               name taken out, the query description as a query and as a passage
                               against them, the question against the chunks' tags (passage), and
                               the query tags (passage) against the chunks' tags (passage), the
                               closest and the mean.
  the question's words against the layer itself
                               BM25 of the question's words against a chunk's description text,
                               against its tags' names, and against both (inside the product).

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/first_gold_signals_more.py gold100 <folder>
"""
import json
import math
import os
import pickle
import re
import sys
import warnings
from collections import Counter
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
from graph.db import _readable  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
OUT = Path(sys.argv[2])
CACHE = REPO / "output/private/artefact_v4_cache/querytag"
KEPT = REPO / "output/embed_local/20261007_rev113abe4acafa_float32"
K1, B = 1.2, 0.75
TOKEN = re.compile(r"[a-z0-9]+")


def unit(m):
    m = np.asarray(m, dtype=np.float64)
    return m / np.maximum(np.linalg.norm(m, axis=-1, keepdims=True), 1e-12)


with open(OUT / f"first_gold_signals__{SET}.pkl", "rb") as handle:
    first = pickle.load(handle)["questions"]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("first gold signals, more")
layer, n = p.layer, len(p.chunk_ids)
et, ec = layer["edge_tag"], layer["edge_chunk"]
tags_side = np.load(KEPT / "tags_passage.npz", allow_pickle=True)
tag_at = {str(t): k for k, t in enumerate(tags_side["ids"])}
TP = unit(tags_side["matrix"][[tag_at[str(t)] for t in p.graph_tags]])
desc_side = np.load(KEPT / "descriptions_passage.npz", allow_pickle=True)
desc_at = {str(c): k for k, c in enumerate(desc_side["ids"])}
CP = unit(desc_side["matrix"][[desc_at[str(c)] for c in p.chunk_ids]])
dim = CP.shape[1]
AXES = V._QueryAxes(TP, np.eye(dim))
texts = {}
for line in (KEPT / "descriptions.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        row = json.loads(line)
        texts[str(row["id"])] = str(row["text"])
description_words = [Counter(TOKEN.findall(texts.get(str(c), "").lower())) for c in p.chunk_ids]
tag_words = [Counter() for _ in range(n)]
for e in range(et.size):
    tag_words[int(ec[e])].update(TOKEN.findall(_readable(p.graph_tags[int(et[e])]).lower()))
both_words = [a + b for a, b in zip(description_words, tag_words)]
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


def bm25(asked, bags, inside):
    m = inside.size
    size = np.array([sum(bags[c].values()) for c in inside.tolist()], dtype=np.float64)
    mean_size = float(size.mean()) or 1.
    df = Counter()
    for c in inside.tolist():
        df.update(bags[c].keys())
    out = np.zeros(m)
    for word in asked:
        held = df.get(word, 0)
        if held:
            tf = np.array([bags[c].get(word, 0) for c in inside.tolist()], dtype=np.float64)
            out += math.log(1. + (m - held + .5) / (held + .5)) * tf * (K1 + 1.) / (tf + K1 * (1. - B + B * size / mean_size))
    return out


def closest_tag(rows):
    out = np.full((rows.shape[0], n), -1.)
    np.maximum.at(out.T, ec, rows[:, et].T)
    return out


more, done = {}, 0
for qid, d in first.items():
    q = by_id[qid]
    inside = d["chunks"]
    description, tags, asked = side_of(q)
    every = tags + [t for t in asked if t not in tags]
    as_passage = V._query_cosines(description, every, AXES, "passage")[0]
    tag_vectors = np.asarray(as_passage["query_chunk_cosines"], dtype=np.float64)
    description_passage = np.asarray(as_passage["query_description_cosines"], dtype=np.float64)
    question_vector = d["question_vector"].astype(np.float64)
    bare_vector = d["bare_vector"].astype(np.float64)
    description_query = d["description_vector"].astype(np.float64)
    fit = closest_tag(tag_vectors @ TP.T)[:, inside]
    singles = closest_tag(np.vstack([question_vector @ TP.T, bare_vector @ TP.T]))[:, inside]
    asked_words = set(TOKEN.findall(q.question.lower()))
    more[qid] = {
        "question_to_passage": (CP[inside] @ question_vector),
        "bare_to_passage": (CP[inside] @ bare_vector),
        "description_query_to_passage": (CP[inside] @ description_query),
        "description_passage_to_passage": (CP[inside] @ description_passage),
        "tags_passage_closest": fit.max(axis=0), "tags_passage_mean": fit.mean(axis=0),
        "tags_passage_to_description": (tag_vectors @ CP[inside].T).astype(np.float32),
        "question_to_tags_passage": singles[0], "bare_to_tags_passage": singles[1],
        "words_on_description": bm25(asked_words, description_words, inside),
        "words_on_tags": bm25(asked_words, tag_words, inside),
        "words_on_both": bm25(asked_words, both_words, inside),
        "among_passage": (CP[inside] @ CP[inside].T).astype(np.float32),
    }
    done += 1
    if done % 10 == 0:
        print(f"  ... {done} questions", flush=True)
with open(OUT / f"first_gold_signals_more__{SET}.pkl", "wb") as handle:
    pickle.dump(more, handle)
print(f"{SET}: {len(more)} questions written")
print("done", flush=True)

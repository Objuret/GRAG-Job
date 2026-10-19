"""His 2026-10-11 goal "Explore this more to find the closest first gold". One pass over the hundred that
writes, per question and per chunk of the question's product, every reading there is, so orders
can be tried against it without reading the graph again. No model call (the local embedder
writes the question with the product's name taken out; nothing else is embedded anew).

Per question, arrays over the product's chunks:
  gold, cited (cited records in the chunk), length, kind, parent, spot (its place in its parent)
  tags              its closest tag to any query tag
  fit               per query tag, its closest tag to that query tag
  description       its description against the query description
  question          its description against the question
  question_tags     its closest tag to the question's own vector
  description_tags  its closest tag to the query description's vector
  tags_description  per query tag, that query tag against its description
  question_bare     its description against the question with the product's name taken out
  question_bare_tags its closest tag to that
  record_best, record_mean  its records against the question (the vector baseline's record vectors)
  words             BM25 of the question's words against its text (inside the product)
  kind_tags, kind_description, kind_question   the three routes' mean over its look-alikes in the
                    other 29 products
  edge              the five values on the edge to its closest tag (topic, temporal, why, activity,
                    concreteness)
  among             description nearness between the product's chunks
The file holds which chunks are gold, so it is written outside the repository (the folder given
as the second argument).

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/first_gold_signals.py gold100 <folder>
"""
import json
import math
import os
import pickle
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
from arms.artefact_v2 import _load_verified_doc, _resolve_chunk  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
OUT = Path(sys.argv[2])
CACHE = REPO / "output/private/artefact_v4_cache/querytag"
KEPT = REPO / "output/embed_local/20261007_rev113abe4acafa_float32"
K1, B = 1.2, 0.75
TOKEN = re.compile(r"[a-z0-9]+")

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("first gold signals")
layer, n = p.layer, len(p.chunk_ids)
id_rank, kind = layer["id_rank"], layer["kind"]
et, ec, eligible = layer["edge_tag"], layer["edge_chunk"], layer["eligible"]
docs, record_ids, length, words, parent, ordinal = {}, [], np.zeros(n, dtype=np.int64), [], [], np.zeros(n, dtype=np.int64)
first_time, last_time, talks = np.full(n, np.nan), np.full(n, np.nan), np.zeros(n, dtype=np.int64)
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    record_ids.append([str(x) for x in ids])
    length[i] = len(text)
    words.append(Counter(TOKEN.findall(text.lower())))
    parent.append(str(row["parent"]))
    ordinal[i] = int(row["ordinal"])
    loc = json.loads(row["locator"])
    arr = _load_verified_doc(row["relpath"], row["sha256"], docs)[loc["section"]]
    times, days = [], set()
    for r in [arr[k] for k in (loc["indices"] if "indices" in loc else [loc["index"]])]:
        raw = ((r.get("Message") or {}).get("User") or {}).get("timestamp") if "Message" in r else (
            r.get("date") if "date" in r else r.get("created_at"))
        when = None
        if raw is not None:
            try:
                when = float(str(raw).strip())
            except ValueError:
                try:
                    from datetime import datetime
                    when = datetime.fromisoformat(str(raw).strip().replace("Z", "+00:00").replace(" ", "T")).timestamp()
                except ValueError:
                    when = None
        if when is not None:
            times.append(when)
            channel = (r.get("Channel") or {}).get("channelID") if "Channel" in r else None
            days.add((channel, int(when // 86400)))
    if times:
        first_time[i], last_time[i] = min(times), max(times)
    talks[i] = len(days)
plain_tag = [" " + " ".join(TOKEN.findall(str(t).lower())) + " " for t in p.graph_tags]
tag_words = np.array([len(t.split()) for t in plain_tag], dtype=np.int64)
record_sets = [frozenset(r) for r in record_ids]
size = np.array([sum(w.values()) for w in words], dtype=np.float64)
members = defaultdict(list)
for i in range(n):
    members[parent[i]].append(i)
spot = np.zeros(n, dtype=np.int64)
for chunks in members.values():
    for k, c in enumerate(sorted(chunks, key=lambda c: (ordinal[c], id_rank[c]))):
        spot[c] = k
parent_names = sorted(members)
parent_at = {name: k for k, name in enumerate(parent_names)}
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b
CV = np.array(p.chunk_vectors, dtype=np.float64)
CV = CV / np.linalg.norm(CV, axis=1, keepdims=True)
TV = np.array(p.tag_vectors, dtype=np.float64)
TV = TV / np.linalg.norm(TV, axis=1, keepdims=True)
AXES = V._QueryAxes(TV, np.eye(CV.shape[1]))
near = (CV @ CV.T).astype(np.float32)
alike = np.zeros((n, len(branches)), dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    alike[:, b] = chunks[np.argmax(near[:, chunks], axis=1)]
del near
corpus = np.load(KEPT / "corpus_passage.npz", allow_pickle=True)
row_of = {str(r): k for k, r in enumerate(corpus["ids"])}
matrix = np.asarray(corpus["matrix"], dtype=np.float32)
asked_vectors = np.load(KEPT / "question_query_vecs.npz", allow_pickle=True)
question_at = {str(q): k for k, q in enumerate(asked_vectors["ids"])}
rows_of = [np.array([row_of[r] for r in recs if r in row_of], dtype=np.int64) for recs in record_ids]
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


def vector_of(text):
    return np.asarray(V._query_cosines(text, [], AXES)[0]["query_description_cosines"], dtype=np.float64)


def closest_tag(rows):
    """Per row and chunk: the chunk's closest tag to that row."""
    out = np.full((rows.shape[0], n), -1.)
    np.maximum.at(out.T, ec, rows[:, et].T)
    return out


def without_the_name(question, name):
    """The question with the product's name (letters and digits compared, case left aside) replaced
    by 'the product'."""
    parts = TOKEN.findall(name.lower())
    if not parts:
        return question
    pattern = re.compile(r"(?<![A-Za-z0-9])" + r"[^A-Za-z0-9]*".join(re.escape(part) for part in parts)
                         + r"(?![A-Za-z0-9])", re.IGNORECASE)
    return " ".join(pattern.sub("the product", question).split())


held_by, out, done, named = {}, {}, 0, 0
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    description, tags, asked = side_of(q)
    answer = V._tag_cosines(description, tags, p)[0]
    rows, tag_rows = list(answer["tags"]), list(answer["tags_to_chunks"])
    to_description = list(answer["tags_to_description"])
    if asked:
        more = V._tag_cosines(description, asked, p)[0]
        rows += list(more["tags"])
        tag_rows += list(more["tags_to_chunks"])
        to_description += list(more["tags_to_description"])
    rows, tag_rows = np.array(rows, dtype=np.float64), np.array(tag_rows, dtype=np.float64)
    question_vector, description_vector = vector_of(q.question), vector_of(description)
    gold = np.array([bool(record_sets[i] & cites) for i in range(n)])
    main = Counter(branch_of[np.flatnonzero(gold)].tolist()).most_common(1)[0][0]
    inside = np.flatnonzero(branch_of == main)
    m = inside.size
    name = branches[main][0]
    bare = without_the_name(q.question, name)
    named += int(bare != q.question)
    bare_vector = vector_of(bare)
    fit = closest_tag(rows)
    t_edge = WK.best_edges(rows[:, et].max(axis=0), ec, n)[1]
    singles = closest_tag(np.vstack([question_vector @ TV.T, description_vector @ TV.T, bare_vector @ TV.T]))
    record_near = matrix @ np.asarray(asked_vectors["matrix"][question_at[qid]], dtype=np.float32)
    record_best = np.array([float(record_near[r].max()) if r.size else float(record_near.min()) for r in rows_of])
    record_mean = np.array([float(record_near[r].mean()) if r.size else float(record_near.min()) for r in rows_of])
    if main not in held_by:
        df = Counter()
        for c in inside.tolist():
            df.update(words[c].keys())
        held_by[main] = (df, float(size[inside].mean()))
    df, mean_size = held_by[main]
    own_words = np.zeros(m)
    for word in set(TOKEN.findall(q.question.lower())):
        held = df.get(word, 0)
        if held:
            tf = np.array([words[c].get(word, 0) for c in inside.tolist()], dtype=np.float64)
            own_words += (math.log(1. + (m - held + .5) / (held + .5)) * tf * (K1 + 1.)
                          / (tf + K1 * (1. - B + B * size[inside] / mean_size)))
    # the graph's own tags whose name stands in the question word for word (the product's own name aside)
    plain_question = " " + " ".join(TOKEN.findall(q.question.lower())) + " "
    plain_name = " " + " ".join(TOKEN.findall(name.lower())) + " "
    inside_set = np.zeros(n, dtype=bool)
    inside_set[inside] = True
    on_product = np.flatnonzero(inside_set[ec])
    product_tags = np.unique(et[on_product])
    spread_of = Counter(et[on_product].tolist())
    stands = {int(t) for t in product_tags.tolist()
              if eligible[t] and plain_tag[t].strip() and plain_tag[t] != plain_name and plain_tag[t] in plain_question}
    named_count, named_rarest, named_longest = np.zeros(n), np.full(n, np.inf), np.zeros(n)
    for e in on_product.tolist():
        t = int(et[e])
        if t in stands:
            c = int(ec[e])
            named_count[c] += 1
            named_rarest[c] = min(named_rarest[c], spread_of[t])
            named_longest[c] = max(named_longest[c], tag_words[t])
    others = [b for b in range(len(branches)) if b != main]
    look = alike[inside][:, others]
    tags_all = fit.max(axis=0)
    d_description, d_question = description_vector @ CV.T, question_vector @ CV.T
    edge = t_edge[inside]
    out[qid] = {
        "chunks": inside, "gold": gold[inside], "cited": np.array([len(record_sets[c] & cites) for c in inside.tolist()]),
        "cites": len(cites), "records": [record_ids[c] for c in inside.tolist()], "cited_ids": sorted(cites),
        "length": length[inside], "kind": kind[inside], "id_rank": id_rank[inside],
        "parent": np.array([parent_at[parent[c]] for c in inside.tolist()]), "spot": spot[inside],
        "first_list": len(tags), "tags_to_description": np.array(to_description, dtype=np.float64),
        "n_tags": layer["n_c"][inside], "first_time": first_time[inside], "last_time": last_time[inside],
        "talks": talks[inside], "named_count": named_count[inside], "named_rarest": named_rarest[inside],
        "named_longest": named_longest[inside], "named_tags": len(stands),
        "named_tag_words": sorted(int(tag_words[t]) for t in stands),
        "product_tags": int(product_tags.size),
        "tags": tags_all[inside], "fit": fit[:, inside].astype(np.float32),
        "description": d_description[inside], "question": d_question[inside],
        "question_tags": singles[0][inside], "description_tags": singles[1][inside],
        "tags_description": tag_rows[:, inside].astype(np.float32),
        "question_bare": (bare_vector @ CV.T)[inside], "question_bare_tags": singles[2][inside],
        "record_best": record_best[inside], "record_mean": record_mean[inside], "words": own_words,
        "kind_tags": tags_all[look].mean(axis=1), "kind_description": d_description[look].mean(axis=1),
        "kind_question": d_question[look].mean(axis=1),
        "edge": np.where(edge[:, None] >= 0, layer["raw"][np.maximum(edge, 0)], np.nan),
        "among": (CV[inside] @ CV[inside].T).astype(np.float32),
        "question_vector": question_vector.astype(np.float32), "description_vector": description_vector.astype(np.float32),
        "bare_vector": bare_vector.astype(np.float32), "chunk_vectors": CV[inside].astype(np.float32),
    }
    done += 1
    if done % 10 == 0:
        print(f"  ... {done} questions", flush=True)

OUT.mkdir(parents=True, exist_ok=True)
with open(OUT / f"first_gold_signals__{SET}.pkl", "wb") as handle:
    pickle.dump({"kind_names": list(layer["kind_names"]), "facets": list(WK.FACETS), "parent_names": parent_names,
                 "questions": out}, handle)
print(f"{SET}: {len(out)} questions written; the product's name stood in the question and was taken out on {named}")
print("done", flush=True)

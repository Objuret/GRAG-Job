"""The agent's own line, 2026-10-11 night, after `is_the_gold_one_cloud`: from the best single gold
chunk as the landing point, the product's chunks ordered by description nearness to it deliver
0.75 of the cited records (the plain order 0.50). So a cloud exists: a chunk and the chunks whose
descriptions are nearest its own. Can the right cloud be told without the gold?

On the hundred, inside the question's product, cached query side, no model call. A cloud is a
landing chunk and the chunks nearest it by description, as many as fit in 72,000 characters: it
is exactly what would be delivered. Every chunk of the product is tried as the landing.

  with the gold in hand   what the best landing reaches, taken among the gold chunks and among all
                          chunks; what a gold chunk and any chunk reach as a landing on average
  without it              the landing is the chunk whose cloud scores highest, the score read from
                          the plain order's values (the three routes' standings added) of the
                          cloud's members: their mean, their middle (the majority of the cloud),
                          their lowest quarter; or the landing is the plain order's first chunk.
                          And the best cloud and the plain order taken in turn.
Printed: context_recall_id, and where the best landing (gold in hand) stands among the chunks by
each score.

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/the_cloud_around_a_landing.py [gold100]
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
K1, B = 1.2, 0.75
TOKEN = re.compile(r"[a-z0-9]+")

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the cloud around a landing")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
et, ec = layer["edge_tag"], layer["edge_chunk"]
docs, record_sets, length, words = {}, [], np.zeros(n, dtype=np.int64), []
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    record_sets.append(frozenset(str(x) for x in ids))
    length[i] = len(text)
    words.append(Counter(TOKEN.findall(text.lower())))
size = np.array([sum(w.values()) for w in words], dtype=np.float64)
kind, kind_names = layer["kind"], layer["kind_names"]
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


recall, places = defaultdict(list), defaultdict(list)
best_kind, held_by, picked_gold = Counter(), {}, defaultdict(list)
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
    t_near, t_edge = WK.best_edges(rows[:, et].max(axis=0), ec, n)
    t_near = np.where(t_edge >= 0, t_near, t_near[t_edge >= 0].min())
    plain = standing(t_near[inside]) + standing(d_description[inside]) + standing(d_question[inside])
    sizes = length[inside]
    cited = [len(record_sets[c] & cites) for c in inside.tolist()]

    def delivered(order):
        fits = np.cumsum(sizes[order]) <= BUDGET
        return order[:int(fits.sum()) if fits.all() else int(np.argmin(fits))]

    def got(kept):
        have = set().union(*(record_sets[inside[k]] for k in kept)) if len(kept) else set()
        return len(cites & have) / len(cites)

    plain_order = np.lexsort((id_rank[inside], -plain))
    recall["the plain order"].append(got(delivered(plain_order)))
    # the question's own words against the chunk text (BM25 inside the product, Lucene's settings)
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
    with_words = plain + standing(own_words)
    words_order = np.lexsort((id_rank[inside], -with_words))
    recall["the plain order with the question's own words added (BM25 on the chunk text)"].append(
        got(delivered(words_order)))
    among = CV[inside] @ CV[inside].T
    clouds, reach = [], np.zeros(m)
    for c in range(m):
        value = among[c].copy()
        value[c] = np.inf
        clouds.append(delivered(np.lexsort((id_rank[inside], -value))))
        reach[c] = got(clouds[c])
    is_gold = gold[inside]
    recall["gold in hand: the best landing among the gold chunks"].append(float(reach[is_gold].max()))
    recall["gold in hand: the best landing among all chunks"].append(float(reach.max()))
    recall["gold in hand: a gold chunk as the landing, on average"].append(float(reach[is_gold].mean()))
    recall["gold in hand: any chunk as the landing, on average"].append(float(reach.mean()))
    sent = delivered(plain_order)
    recall["gold in hand: the best landing among the chunks the plain order delivers"].append(float(reach[sent].max()))
    recall["gold in hand: a gold chunk the plain order delivers as the landing, on average"].append(
        float(reach[sent][is_gold[sent]].mean()) if is_gold[sent].any() else 0.)
    # the landing picked among the chunks the plain order delivers, without the gold
    inner = among[np.ix_(sent, sent)].copy()
    np.fill_diagonal(inner, 0.)
    weight = plain[sent] - plain[sent].min()
    overlap = np.array([len(set(clouds[c].tolist()) & set(sent.tolist())) for c in sent.tolist()], dtype=np.float64)
    among_sent = {
        "the one nearest the other delivered chunks on average (the most central of them)": inner.mean(axis=1),
        "the same, each of the others counted by its own value in the plain order": inner @ weight,
        "the one whose cloud holds the most of the delivered chunks": overlap + 1e-6 * inner.mean(axis=1),
        "the one whose cloud has the highest mean of the plain order's values":
            np.array([plain[clouds[c]].mean() for c in sent.tolist()]),
        "the one whose cloud lies tightest around it (its members' mean nearness to it)":
            np.array([among[c, clouds[c][1:]].mean() if clouds[c].size > 1 else 0. for c in sent.tolist()]),
    }
    # the five values on the edge to the chunk's closest tag (topic and the four facets)
    edge = t_edge[inside][sent]
    for j, facet in enumerate(("topic", *WK.RANKING_FACETS)):
        among_sent[f"the one with the highest {facet} value on the edge to its closest tag"] = np.where(
            edge >= 0, layer["raw"][np.maximum(edge, 0), j], -np.inf)
    # no landing picked: every chunk's own value with the mean value of its cloud added (the chunks
    # around it in description nearness speak for it)
    cloud_mean = np.array([plain[cloud].mean() for cloud in clouds])
    recall["no landing: the plain order with the mean value of each chunk's own cloud added (standings)"].append(
        got(delivered(np.lexsort((id_rank[inside], -(standing(plain) + standing(cloud_mean)))))))
    for name, score in among_sent.items():
        pick = int(sent[np.lexsort((id_rank[inside][sent], -score))[0]])
        label = f"picked among the delivered chunks: {name}"
        recall[label].append(float(reach[pick]))
        picked_gold[label].append(float(is_gold[pick]))
        turn, seen = [], set()
        for a, b in zip(clouds[pick].tolist() + [None] * m, plain_order.tolist()):
            for k in (a, b):
                if k is not None and k not in seen:
                    seen.add(k)
                    turn.append(k)
        recall[label + ", its cloud and the plain order in turn"].append(got(delivered(np.array(turn, dtype=np.int64))))
    best = int(np.argmax(reach))
    best_kind[kind_names[int(kind[inside[best]])]] += 1
    scores = {
        "the landing is the plain order's first chunk": plain,
        "the landing whose cloud has the highest mean of the plain order's values":
            np.array([plain[cloud].mean() for cloud in clouds]),
        "the landing whose cloud has the highest middle of them (the majority of the cloud)":
            np.array([np.median(plain[cloud]) for cloud in clouds]),
        "the landing whose cloud has the highest lower quarter of them":
            np.array([np.percentile(plain[cloud], 25) for cloud in clouds]),
        "the landing whose cloud has the highest mean of the question's nearness":
            np.array([d_question[inside][cloud].mean() for cloud in clouds]),
        "the landing is the chunk the question's own words fit best (BM25)": own_words,
        "the landing is the first chunk of the plain order with the question's own words added": with_words,
        "the landing whose cloud has the highest mean of the plain order's values with the words added":
            np.array([with_words[cloud].mean() for cloud in clouds]),
    }
    for name, score in scores.items():
        order = np.lexsort((id_rank[inside], -score))
        landing = int(order[0])
        recall[name].append(float(reach[landing]))
        place = np.empty(m, dtype=np.int64)
        place[order] = np.arange(1, m + 1)
        places[name].append(int(place[best]))
        if name.startswith("the landing whose cloud has the highest middle"):
            cloud_order = clouds[landing].tolist()
            turn, seen = [], set()
            for a, b in zip(cloud_order + [None] * m, plain_order.tolist()):
                for k in (a, b):
                    if k is not None and k not in seen:
                        seen.add(k)
                        turn.append(k)
            recall["that cloud and the plain order in turn"].append(got(delivered(np.array(turn, dtype=np.int64))))
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

print(f"\n{SET}: {len(wanted)} questions, inside the question's product")
print("== context_recall_id (share of the cited records delivered inside 72,000 characters) | against the plain "
      "order: mean difference, its standard error, questions higher / lower | place of the best landing (gold in "
      "hand, among all chunks) by this score, the middle ==")
first = np.asarray(recall["the plain order"])
for name, values in recall.items():
    diff = np.asarray(values) - first
    where = (f" | {np.median(places[name]):.0f} ({np.percentile(places[name], 25):.0f}-{np.percentile(places[name], 75):.0f})"
             if name in places else "")
    print(f"  {float(np.mean(values)):.3f} | {float(diff.mean()):+.3f}, {float(diff.std(ddof=1) / np.sqrt(diff.size)):.3f}, "
          f"{int((diff > 0).sum())} / {int((diff < 0).sum())}{where}  {name}")
for name, values in picked_gold.items():
    print(f"  the picked landing is a gold chunk on {int(sum(values))} of {len(values)} questions  ({name})")
print("the best landing (gold in hand, among all chunks) by kind of chunk: "
      + ", ".join(f"{name}: {count}" for name, count in best_kind.most_common()))
print("done", flush=True)

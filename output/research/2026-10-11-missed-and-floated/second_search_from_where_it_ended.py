"""His 2026-10-11 "finally ending up somewhere should make you search the correct scopes no matter
what desc or tags say" and "an agnostic search that ... actually does a search and
semi-deterministically actually find": a second search that starts from where the first one ended.

On the hundred, inside the gold's branch, cached query side, no model call.

Where the first search ended = the chunks its order delivers inside 72,000 characters (the three
routes' standings added). From those, through ties the graph already holds:
  their tags       a chunk's value is the sum, over the tags it shares with those chunks, of how
                   many of them carry the tag times how rare the tag is in the branch (the log of
                   the branch's chunks over the chunks carrying it); its own vote is left out
  their descriptions  the closeness of a chunk's description to the middle of those chunks'
                   descriptions, its own left out
  their neighbours the best first-search value among the chunks next to it in its file
Beside them, as a diagnosis only: the question's own words against the chunk's text (BM25).

Each is added to the first order as a standing (the value less the middle over the spread). The
orders are the agent's construction of his sentence; printed is what each delivers.

The gold ids and the question texts are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/second_search_from_where_it_ended.py [gold100]
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

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("second search from where it ended")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
et, ec, eligible = layer["edge_tag"], layer["edge_chunk"], layer["eligible"]
D = np.asarray(p.chunk_vectors, dtype=np.float64)
docs, records, length, words = {}, [], np.zeros(n, dtype=np.int64), []
parent, ordinal = [], np.zeros(n, dtype=np.int64)
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    records.append(frozenset(str(x) for x in ids))
    length[i] = len(text)
    words.append(Counter(TOKEN.findall(text.lower())))
    parent.append(str(row["parent"]))
    ordinal[i] = int(row["ordinal"])
size = np.array([sum(w.values()) for w in words], dtype=np.float64)
members = defaultdict(list)
for i in range(n):
    members[parent[i]].append(i)
beside = [[] for _ in range(n)]
for chunks in members.values():
    ordered = sorted(chunks, key=lambda c: (ordinal[c], id_rank[c]))
    for a, b in zip(ordered, ordered[1:]):
        beside[a].append(b)
        beside[b].append(a)
tags_of = [[] for _ in range(n)]
for e in range(et.size):
    tags_of[ec[e]].append(int(et[e]))
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b
of_branch = {}


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
    at = {int(c): k for k, c in enumerate(inside.tolist())}
    if main not in of_branch:
        carried, df = Counter(), Counter()
        for c in inside.tolist():
            carried.update(tags_of[c])
            df.update(words[c].keys())
        of_branch[main] = (carried, df, float(size[inside].mean()))
    carried, df, mean_size = of_branch[main]
    m_here = inside.size
    t_near, t_edge = WK.best_edges(rows[:, et].max(axis=0), ec, n)
    t_near = np.where(t_edge >= 0, t_near, t_near[t_edge >= 0].min())
    base = standing(t_near[inside]) + standing(d_description[inside]) + standing(d_question[inside])
    first = inside[np.lexsort((id_rank[inside], -base))]
    ended = first[:kept_of(first)].tolist()                     # where the first search ended
    ended_set = set(ended)
    votes = Counter(t for c in ended for t in set(tags_of[c]))
    by_tags = np.zeros(m_here)
    for k, c in enumerate(inside.tolist()):
        own = 1 if c in ended_set else 0
        by_tags[k] = sum(math.log(m_here / carried[t]) * (votes[t] - own) for t in set(tags_of[c]) if votes[t] > own)
    total = D[ended].sum(axis=0)
    by_descriptions = np.zeros(m_here)
    for k, c in enumerate(inside.tolist()):
        middle = total - D[c] if c in ended_set else total
        norm = np.linalg.norm(middle)
        by_descriptions[k] = float(D[c] @ middle / norm) if norm > 0 else 0.
    by_neighbours = np.full(m_here, base.min())
    for k, c in enumerate(inside.tolist()):
        near = [at[j] for j in beside[c] if j in at]
        if near:
            by_neighbours[k] = base[near].max()
    asked_words = set(TOKEN.findall(q.question.lower()))
    own_words = np.zeros(m_here)
    for word in asked_words:
        held = df.get(word, 0)
        if held:
            idf = math.log(1. + (m_here - held + .5) / (held + .5))
            tf = np.array([words[c].get(word, 0) for c in inside.tolist()], dtype=np.float64)
            own_words += idf * tf * (K1 + 1.) / (tf + K1 * (1. - B + B * size[inside] / mean_size))

    def score(name, value):
        order = inside[np.lexsort((id_rank[inside], -value))]
        kept = order[:kept_of(order)]
        delivered[name] += int(gold[kept].sum())
        got = set().union(*(records[i] for i in kept)) if kept.size else set()
        recall[name].append(len(cites & got) / len(cites))

    zt, zd, zn, zw = standing(by_tags), standing(by_descriptions), standing(by_neighbours), standing(own_words)
    score("the first search: the three routes' standings added", base)
    score("+ their tags", base + zt)
    score("+ their descriptions", base + zd)
    score("+ their neighbours", base + zn)
    score("+ their tags and their descriptions", base + zt + zd)
    score("+ their tags, their descriptions and their neighbours (all three from the graph)", base + zt + zd + zn)
    score("their tags, descriptions and neighbours alone, without the first search's values", zt + zd + zn)
    score("+ the question's own words (diagnosis)", base + zw)
    score("+ all three from the graph and the question's own words (diagnosis)", base + zt + zd + zn + zw)
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

print(f"\n{SET}: {len(wanted)} questions, inside the gold's branch; gold chunks {gold_total}")
print(f"\n== inside {BUDGET} characters: gold chunks delivered of {gold_total} | context_recall_id ==")
for name in delivered:
    print(f"  {delivered[name]} | {float(np.mean(recall[name])):.3f}  {name}")
first_name = "the first search: the three routes' standings added"
print("\n== against the first search, question by question: mean difference in context_recall_id | its standard "
      "error | questions higher, lower, the same ==")
for name in delivered:
    if name == first_name:
        continue
    diff = np.asarray(recall[name]) - np.asarray(recall[first_name])
    print(f"  {float(diff.mean()):+.3f} | {float(diff.std(ddof=1) / np.sqrt(diff.size)):.3f} | "
          f"{int((diff > 0).sum())}, {int((diff < 0).sum())}, {int((diff == 0).sum())}  {name}")
print("done", flush=True)

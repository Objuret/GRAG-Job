"""His 2026-10-13 "how do we make them work then?" (the query facets), the part of his own that is
not in the arm: his 2026-10-09 "we DID build that neural net for judging the facets, why the fuck
is the model doing that work then?" The net that scored the graph's edges reads each query tag
(`test/artefact/query_facets.py`, the round-1 head, on the laptop), so a query tag has four
values on the edges' own scale. Does like against like then tell the cited chunk's edge from the
others among the edges a query tag picked?

A side count on the hundred: no arm change, no model call to the lane (HERB_V4_OFFLINE=on, the
cached first calls; the facet net runs here). The gold ids are read inside; numbers only.

  the text the query tag is read against   D the query description | Q the question and the
                                           description (the join is mine)
  ways of using the four values of a query tag on its picked edges (inside the border):
    top       the edge's value in the facet the net reads highest for the query tag
    order     his multi-key: the four facets in the query tag's order, each facet's edge values
              cut into five clusters over the query tag's picked edges as the equal range
    weights   the query tag's ranks of the four as weights (4, 3, 2, 1) on the edge's positions
    profile   (mine) how well the edge's four values agree in order with the query tag's four
  each as it is, and with the own level taken out on both sides (the edge's value less its
  chunk's mean; the query tag's reading less the mean over its question's query tags)
  the check: the same with the readings of a query tag of ANOTHER question (shuffled)

Printed: how often the cited chunk's edge stands above another edge of the same query tag
(0.50 says nothing), over the sets that hold both.
"""
import json
import os
import random
import sys
import warnings
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"
os.environ["HERB_V4_SCOPE_STEP"] = "name"
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from artefact import query_facets as QF  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

BUDGET = 72000
FOUR = WK.RANKING_FACETS
wanted = [json.loads(line)["id"] for line in (REPO / "data" / "gold100.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the query side by his net")
layer, n = p.layer, len(p.chunk_ids)
tag_e, chunk_e, raw, pos = layer["edge_tag"], layer["edge_chunk"], layer["raw"][:, 1:], layer["pos"][:, 1:]
n_c = np.maximum(layer["n_c"], 1)
chunk_mean = np.column_stack([np.bincount(chunk_e, weights=raw[:, f], minlength=n) / n_c for f in range(len(FOUR))])
less = raw - chunk_mean[chunk_e]
doc_cache = {}
records = [{str(x) for x in _resolve_chunk(row, doc_cache)[1]} for row in p.chunk_rows]
print("prepared", flush=True)

captured = {}
the_chain, the_interpret = WK.chain, V._interpret


def recording(layer_, query, cos_noise, k):
    out = the_chain(layer_, query, cos_noise, k)
    captured["query"], captured["out"] = query, out
    return out


def interpreting(text, prepared):
    got = the_interpret(text, prepared)
    captured["content"] = got[0]
    return got


WK.chain, V._interpret = recording, interpreting

per_question = []
for at, qid in enumerate(wanted):
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    V.answer_one_question((qid, q.question), p, None, 50, BUDGET)
    content, query, out = captured["content"], captured["query"], captured["out"]
    phrases = [t.text for t in (*content.tags, *content.query_tags)]
    if len(phrases) != np.asarray(query["named_facet"]).size:
        raise SystemExit("the query tags and the chain's rows do not line up")
    read = {"D": QF.head_scores(phrases, content.description)[:, 1:],
            "Q": QF.head_scores(phrases, content.question + "\n\n" + content.description)[:, 1:]}
    border, _ = V.scope_by_name(q.question, p.tree, n)
    gold = np.array([bool(cites & records[i]) for i in range(n)])
    sets = []
    for i in range(len(phrases)):
        edges = np.flatnonzero(out["picked_edge"][i] & border[chunk_e])
        if gold[chunk_e[edges]].any() and not gold[chunk_e[edges]].all():
            sets.append((i, edges, gold[chunk_e[edges]]))
    per_question.append({"read": read, "sets": sets})
    if (at + 1) % 25 == 0:
        print(f"   {at + 1} questions", flush=True)
WK.chain, V._interpret = the_chain, the_interpret


def above(score, is_gold):
    g, h = score[is_gold][:, None], score[~is_gold][None, :]
    return float((g > h).sum() + 0.5 * (g == h).sum()), g.size * h.size


def keyed(keys):
    """One number per edge from a row of keys compared left to right (smaller first), higher the better."""
    order = np.lexsort(tuple(keys[:, j] for j in range(keys.shape[1] - 1, -1, -1)))
    place = np.empty(len(order))
    same = np.r_[True, (np.diff(keys[order], axis=0) != 0).any(axis=1)]
    place[order] = np.cumsum(same)
    return -place


def ways(reading, edge_values, edge_positions):
    """Per way one score per edge, higher the better, from one query tag's four readings."""
    by = np.argsort(-reading, kind="stable")                      # the query tag's order of the four facets
    levels = np.column_stack([WK.levels(edge_values[:, f], 5) for f in by]) if edge_values.shape[0] > 1 else np.zeros((1, 4))
    ranks = rankdata(reading)                                     # 4 the highest
    edge_ranks = np.apply_along_axis(rankdata, 1, edge_values)
    agree = ((edge_ranks - 2.5) * (ranks - 2.5)[None, :]).sum(axis=1)
    return {"top": edge_values[:, by[0]], "order": keyed(levels), "weights": edge_positions @ ranks, "profile": agree}


rng = random.Random(20261014)
pool = [(k, i) for k, question in enumerate(per_question) for i in range(question["read"]["D"].shape[0])]
print("\nhow often the cited chunk's edge stands above another edge of the same query tag (0.50 says nothing); "
      f"{sum(len(question['sets']) for question in per_question)} sets hold both")
for text in ("D", "Q"):
    for own_level in (False, True):
        tally = {}
        for shuffled in (False, True):
            for k, question in enumerate(per_question):
                read = question["read"][text]
                centre = read.mean(axis=0) if own_level else 0.
                for i, edges, is_gold in question["sets"]:
                    if shuffled:
                        other_k, other_i = rng.choice([x for x in pool if x[0] != k])
                        other = per_question[other_k]["read"][text]
                        reading = other[other_i] - (other.mean(axis=0) if own_level else 0.)
                    else:
                        reading = read[i] - centre
                    values = (less if own_level else raw)[edges]
                    for way, score in ways(reading, values, pos[edges]).items():
                        w, m = above(np.asarray(score, dtype=np.float64), is_gold)
                        row = tally.setdefault((way, shuffled), [0., 0])
                        row[0] += w
                        row[1] += m
        said = " ; ".join(f"{way} {tally[(way, False)][0] / tally[(way, False)][1]:.3f} (another question's: "
                          f"{tally[(way, True)][0] / tally[(way, True)][1]:.3f})" for way in ("top", "order", "weights", "profile"))
        print(f"  read against {'the description' if text == 'D' else 'the question and the description'}, "
              f"{'the own level taken out on both sides' if own_level else 'as it is'}: {said}")
print("done", flush=True)

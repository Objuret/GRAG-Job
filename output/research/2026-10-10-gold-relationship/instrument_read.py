"""The facet instrument read directly between the query side and the chunks: what it says about
the gold. Reads the extractor's output for the pairs of `instrument_pairs.py`, puts the round-1
head on the pooled layer (as `test/artefact/query_facets.py` does), and orders the branch's chunks
by each reading alone and together with the three routes.

Readings per chunk:
  head topic         the head's own topic score for (query tag, chunk text): the largest and the
                     mean over the query tags
  head named facet   per query tag the head's score on the facet that tag names: largest, mean
  backbone           the backbone's own relevance score for (question, chunk text),
                     (description, chunk text), and the largest over the query tags

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-10-gold-relationship/instrument_read.py 10smoke <npz>
"""
import json
import os
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

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET, NPZ = sys.argv[1], Path(sys.argv[2])
BUDGET = 72000
FACETS = ("topic", "temporal", "why", "activity", "concreteness")
MODEL = REPO / "output/facet_pairs/rounds/round1/model"

import torch  # noqa: E402

z = np.load(MODEL / "standardisation.npz")
state = torch.load(MODEL / "head.pt", map_location="cpu")
weight, bias = state["net.weight"].numpy().astype(np.float64), state["net.bias"].numpy().astype(np.float64)
got = np.load(NPZ, allow_pickle=False)
pooled = got["mean_L-3"].astype(np.float32)
head = ((pooled - z["mu"].astype(np.float32)) / z["sd"].astype(np.float32)).astype(np.float64) @ weight.T + bias
native = got["native_logit"].astype(np.float64).reshape(len(head), -1)[:, 0]
at = {str(e): k for k, e in enumerate(got["edge_id"])}
side = json.loads((HERE / f"instrument_pairs__{SET}.side.json").read_text(encoding="utf-8"))
print(f"{SET}: {len(at)} pairs read; head {head.shape}; truncated {int(got['truncated'].sum())}")

by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("instrument read")
layer, n = p.layer, len(p.chunk_ids)
ci = {c: i for i, c in enumerate(p.chunk_ids)}
docs, records, length = {}, [], np.zeros(n, dtype=np.int64)
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    records.append(frozenset(str(x) for x in ids))
    length[i] = len(text)
id_rank = layer["id_rank"]


def recall_of(order, cites):
    fits = np.cumsum(length[order]) <= BUDGET
    kept = int(fits.sum()) if fits.all() else int(np.argmin(fits))
    held = set().union(*(records[i] for i in order[:kept])) if kept else set()
    return len(cites & held) / len(cites)


def by_value(chunks, value):
    return chunks[np.lexsort((id_rank[chunks], -value))]


def standing(x):
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


scores, places, gauged = {}, {}, 0
for qid, s in side.items():
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    inside = np.array([ci[c] for c in s["chunks"]], dtype=np.int64)
    gold = np.array([bool(records[i] & cites) for i in inside])
    gauged += int(gold.any())
    qi = s["index"]
    H = np.array([[head[at[f"{qi}|{pi}|{c}"]] for c in s["chunks"]] for pi in range(len(s["phrases"]))])
    N = np.array([[native[at[f"{qi}|{pi}|{c}"]] for c in s["chunks"]] for pi in range(len(s["phrases"]))])
    is_tag = np.array([ph["role"] in ("tag", "question tag") for ph in s["phrases"]])
    named = np.array([FACETS.index(ph["facet"]) if ph["facet"] else 0 for ph in s["phrases"]])
    tag_rows = np.flatnonzero(is_tag)
    of_named = np.array([H[pi, :, named[pi]] for pi in tag_rows])
    pq = [k for k, ph in enumerate(s["phrases"]) if ph["role"] == "question"][0]
    pd = [k for k, ph in enumerate(s["phrases"]) if ph["role"] == "description"][0]
    content, _, _ = V._interpret(q.question, p)
    tg, _, _ = V._tag_cosines(content.description, [t.text for t in content.tags], p)
    rows = list(tg["tags"])
    if content.query_tags:
        rows += list(V._tag_cosines(content.description, [t.text for t in content.query_tags], p)[0]["tags"])
    rows = np.array(rows, dtype=np.float64)
    d_question = np.asarray(V._query_cosines(q.question, [], p)[0]["query_description_cosines"], dtype=np.float64)
    on_edge = rows[:, layer["edge_tag"]]
    t_near, t_edge = WK.best_edges(on_edge.max(axis=0), layer["edge_chunk"], n)
    t_near = np.where(t_edge >= 0, t_near, t_near[t_edge >= 0].min())
    routes = standing(t_near[inside]) + standing(np.asarray(tg["description"], dtype=np.float64)[inside]) + standing(d_question[inside])
    cand = {
        "the three routes' standings added (for comparison)": routes,
        "head topic, largest over the query tags": H[tag_rows, :, 0].max(axis=0),
        "head topic, mean over the query tags": H[tag_rows, :, 0].mean(axis=0),
        "head named facet, largest over the query tags": of_named.max(axis=0),
        "head named facet, mean over the query tags": of_named.mean(axis=0),
        "head, all four facets and topic, mean over the query tags": H[tag_rows].mean(axis=(0, 2)),
        "backbone score for the question": N[pq],
        "backbone score for the description": N[pd],
        "backbone score, largest over the query tags": N[tag_rows].max(axis=0),
        "backbone score, mean over the query tags": N[tag_rows].mean(axis=0),
    }
    cand["routes + head topic mean (standings added)"] = routes + standing(cand["head topic, mean over the query tags"])
    cand["routes + backbone question (standings added)"] = routes + standing(cand["backbone score for the question"])
    cand["routes + backbone question + backbone description (standings added)"] = (
        routes + standing(cand["backbone score for the question"]) + standing(cand["backbone score for the description"]))
    cand["backbone question + backbone description (standings added)"] = (
        standing(cand["backbone score for the question"]) + standing(cand["backbone score for the description"]))
    for name, value in cand.items():
        scores.setdefault(name, []).append(recall_of(by_value(inside, value), cites))
        places.setdefault(name, []).extend(rankdata(-value, method="average")[gold].tolist())

print(f"questions whose gauged branch holds gold: {gauged} of {len(side)}")
print("\n== context_recall_id at the budget inside the branch, mean over the questions | the gold chunks' middle place ==")
for name, values in sorted(scores.items(), key=lambda kv: -float(np.mean(kv[1]))):
    print(f"  {float(np.mean(values)):.3f} | {np.median(places[name]):.0f} | {name}   per question: "
          + " ".join(f"{v:.2f}" for v in values))
print("done", flush=True)

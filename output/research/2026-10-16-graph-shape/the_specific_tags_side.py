"""His 2026-10-16 "Really.. Nothing..?" after the graph-shape counts. A tag that sits on hundreds of
chunks ("sprint review" on 527) hands the same closeness to every one of them on the arm's tags
side, where each chunk gets the closeness of its closest tag to a query tag. The counts of the
day showed that such tags tie nothing (a common shared tag adds nothing over none) while rare ones
do. So the graph's shape, the tag's number of chunks, is put on the path query tag -> graph tag
-> chunk. Fixed before the count (mine):
  the arm         the closest tag's closeness, as built
  no hub tags     the closest tag among the chunk's tags outside the largest size cluster (the
                  tags' sizes over the graph, log, cut into the arm's five clusters by `levels`;
                  the largest cluster is 28 to 519 chunks); a chunk with hub tags only keeps them
  idf             each edge's closeness times log(N / the tag's chunks) / log(N), N the pool's
                  chunks (the standard inverse document frequency; no number chosen); the chunk's
                  largest
The rest of the arm as it stands (descriptions, steps, scope, hand-over). The gold hundred (the
arm's own first calls, cached, facets off) and the first hundred of the seeded draw of the unused
questions (the tags side from the question alone). No model call. The gold ids are read inside;
numbers only.
"""
import json
import os
import random
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"
os.environ["HERB_V4_FACETS"] = "off"
os.environ.pop("HERB_V4_SCOPE_STEP", None)

from arms import artefact_v4 as V  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

BUDGET = 72000
CLUSTERS = 5
ids_of = {name: {json.loads(line)["id"] for line in (REPO / "data" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
                 if line.strip()} for name in ("gold100", "heldout100")}
every = HQ.load_questions()
fresh = sorted((q for q in every if q.id not in ids_of["gold100"] | ids_of["heldout100"] and q.citations), key=lambda q: q.id)
SETS = (("the gold hundred", [q for q in every if q.id in ids_of["gold100"]]),
        ("100 unused questions", random.Random(20261011).sample(fresh, 300)[:100]))
p = V.prepare_over_corpus("the specific tags side")
layer, n = p.layer, len(p.chunk_ids)
tag_e, chunk_e, id_rank, eligible = layer["edge_tag"], layer["edge_chunk"], layer["id_rank"], layer["eligible"]
size = np.bincount(tag_e, minlength=len(p.graph_tags)).astype(np.float64)
used_tags = np.flatnonzero(size > 0)
level = np.zeros(len(p.graph_tags), dtype=np.int64)
level[used_tags] = WK.levels(np.log(size[used_tags]), CLUSTERS)
hub = level == 1
print(f"hub tags (largest cluster): {int(hub.sum())}, {int(size[hub].min())} to {int(size[hub].max())} chunks; "
      f"edges through them {int(hub[tag_e].sum())} of {tag_e.size}")
idf = np.zeros(len(p.graph_tags))
idf[used_tags] = np.log(n / size[used_tags]) / np.log(n)
parents = [str(row["parent"]) for row in p.chunk_rows]
parent_ids = {name: k for k, name in enumerate(sorted(set(parents)))}
parent_of = np.array([parent_ids[name] for name in parents], dtype=np.int64)
CV = np.asarray(p.chunk_vectors, dtype=np.float64)
TV = np.asarray(p.tag_vectors, dtype=np.float64)
AXES = V._QueryAxes(TV, np.eye(CV.shape[1]))
doc_cache = {}
print("prepared", flush=True)


def per_chunk(edge_value, keep):
    out = np.full(n, -np.inf)
    np.maximum.at(out, chunk_e[keep], edge_value[keep])
    return out


def tags_side(edge_close, variant):
    """Per chunk from per-edge closeness (eligible edges only)."""
    ok = eligible[tag_e] if eligible.shape[0] == len(p.graph_tags) else np.ones(tag_e.size, dtype=bool)
    if variant == "the arm":
        out = per_chunk(edge_close, ok)
    elif variant == "no hub tags":
        out = per_chunk(edge_close, ok & ~hub[tag_e])
        fallback = per_chunk(edge_close, ok)
        out = np.where(np.isfinite(out), out, fallback)
    else:
        out = per_chunk(edge_close * idf[tag_e], ok)
    finite = np.isfinite(out)
    return np.where(finite, out, out[finite].min())


def score(id_lists, context_ids, cites):
    got = {str(x) for x in context_ids}
    whole = [u for u in ([str(x) for x in unit] for unit in id_lists if unit) if set(u) <= got]
    return (bool(whole and set(whole[0]) & cites), any(set(u) & cites for u in whole[:3]), len(cites & got) / len(cites))


def standing(x):
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


VARIANTS = ("the arm", "no hub tags", "idf")
captured = {}
the_combo = WK.cloud_combo


def recording(*a, **kw):
    captured["args"], captured["kw"] = a, kw
    return the_combo(*a, **kw)


for label, drawn in SETS:
    rows = {v: [] for v in VARIANTS}
    for q in drawn:
        cites = {str(c) for c in q.citations}
        if label == "the gold hundred":
            WK.cloud_combo = recording
            V.answer_one_question((q.id, q.question), p, None, 50, BUDGET)
            WK.cloud_combo = the_combo
            a = captured["args"]
            cosines = np.asarray(a[1], dtype=np.float64)
            edge_close = cosines[:, tag_e].max(axis=0)
            for v in VARIANTS:
                combo = the_combo(*a, tags_near=tags_side(edge_close, v))
                _, id_lists, context_ids, _, _, _ = V._hand_over(combo["order"], p, BUDGET, 50, doc_cache)
                rows[v].append(score(id_lists, context_ids, cites))
        else:
            border, said = V.scope_by_name(q.question, p.tree, n)
            names = said["names_in_the_question"]
            if len(names) != 1:
                continue
            inside = np.flatnonzero(border)
            vector = np.asarray(V._query_cosines(V._without_names(q.question, names), [], AXES)[0]["query_description_cosines"],
                                dtype=np.float64)
            D = (CV @ vector)[inside]
            edge_close = (vector @ TV.T)[tag_e]
            for v in VARIANTS:
                T = tags_side(edge_close, v)[inside]
                step = WK.levels(D, CLUSTERS) + WK.levels(T, CLUSTERS)
                z = standing(D) + standing(T)
                taken = WK.majority_scopes(step <= max(3, int(step.min())), parent_of[inside])
                in_scope = np.isin(parent_of[inside], taken)
                order = inside[np.lexsort((id_rank[inside], -z, ~in_scope, step))].tolist()
                _, id_lists, context_ids, _, _, _ = V._hand_over(order, p, BUDGET, 50, doc_cache)
                rows[v].append(score(id_lists, context_ids, cites))
    m = len(rows["the arm"])
    base = np.array(rows["the arm"], dtype=float)
    print(f"\n{label}: {m} questions")
    for v in VARIANTS:
        r = np.array(rows[v], dtype=float)
        d = r[:, 2] - base[:, 2]
        print(f"  {v:12s}: top text {r[:, 0].sum():3.0f} | among the first three {r[:, 1].sum():3.0f} | context_recall_id "
              f"{r[:, 2].mean():.3f} ({d.mean():+.3f}, se {d.std(ddof=1) / np.sqrt(m):.3f}, {int((d > 0).sum())} up {int((d < 0).sum())} down)")
print("done", flush=True)

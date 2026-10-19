"""The second batch after `the_specific_tags_side.py`, on the same path query tag -> graph tag ->
chunk, fixed before the count (mine):
  the arm               the closest tag's closeness, as built
  central tags only     the closeness counted only through the tags that are central to the chunk:
                        the topic facet ("how central is the tag to the topic of the chunk", his
                        09-08; "the main weight on a tag is the topic one", his 09-18), each chunk's
                        tags' topic values cut in two by `levels` and the upper cluster kept; a
                        chunk with no such eligible tag keeps all
  no hub tags, border   the hub tags counted inside the question's border (its product), not over
                        the graph: the tags' chunks in the border, log, cut into the arm's five
                        clusters; the largest cluster left out; a chunk with hub tags only keeps them
The rest of the arm as it stands. The gold hundred (cached first calls, facets off) and the first
hundred of the seeded draw of the unused questions (the tags side from the question alone). No
model call. The gold ids are read inside; numbers only.
"""
import json
import os
import random
import sys
import warnings
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
p = V.prepare_over_corpus("the central tags side")
layer, n = p.layer, len(p.chunk_ids)
tag_e, chunk_e, id_rank, eligible = layer["edge_tag"], layer["edge_chunk"], layer["id_rank"], layer["eligible"]
ok = eligible[tag_e]
topic = np.asarray(layer["raw"][:, 0], dtype=np.float64)
central = np.zeros(tag_e.size, dtype=bool)
order_by_chunk = np.argsort(chunk_e, kind="stable")
bounds = np.flatnonzero(np.diff(chunk_e[order_by_chunk])) + 1
for ks in np.split(order_by_chunk, bounds):
    central[ks] = WK.levels(topic[ks], 2) == 1 if ks.size > 1 else True
print(f"central edges {int(central.sum())} of {tag_e.size}")
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


def tags_side(edge_close, variant, member):
    if variant == "the arm":
        out = per_chunk(edge_close, ok)
    elif variant == "central tags only":
        out = per_chunk(edge_close, ok & central)
        out = np.where(np.isfinite(out), out, per_chunk(edge_close, ok))
    else:
        in_border = member[chunk_e]
        size = np.bincount(tag_e[in_border], minlength=len(p.graph_tags)).astype(np.float64)
        present = np.flatnonzero(size > 0)
        level = np.zeros(len(p.graph_tags), dtype=np.int64)
        level[present] = WK.levels(np.log(size[present]), CLUSTERS)
        hub = level == 1
        out = per_chunk(edge_close, ok & ~hub[tag_e])
        out = np.where(np.isfinite(out), out, per_chunk(edge_close, ok))
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


VARIANTS = ("the arm", "central tags only", "no hub tags, border")
captured = {}
the_combo = WK.cloud_combo


def recording(*a, **kw):
    captured["args"] = a
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
            member = np.zeros(n, dtype=bool)
            member[np.asarray(a[3], dtype=np.int64)] = True
            edge_close = np.asarray(a[1], dtype=np.float64)[:, tag_e].max(axis=0)
            for v in VARIANTS:
                combo = the_combo(*a, tags_near=tags_side(edge_close, v, member))
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
                T = tags_side(edge_close, v, border)[inside]
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
        print(f"  {v:20s}: top text {r[:, 0].sum():3.0f} | among the first three {r[:, 1].sum():3.0f} | context_recall_id "
              f"{r[:, 2].mean():.3f} ({d.mean():+.3f}, se {d.std(ddof=1) / np.sqrt(m):.3f}, {int((d > 0).sum())} up {int((d < 0).sum())} down)")
print("done", flush=True)

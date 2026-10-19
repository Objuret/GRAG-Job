"""His 2026-09-14 "the point is finding the areas, and let the chunks fill in the content": the graph
finds the area (the border by the product's name, the scope's parents) and the chunks' own text
fills it in. Asked after the day's counts showed that every relation of the graph's shape is made
of tags and descriptions, which hold only a fifth of the words that tell a cited chunk from its
neighbours (`where_the_words_sit`, 2026-10-11).

A third side beside the arm's tags side and description side (mine): the question with the
product's name taken out (as the description side asks), scored against each chunk's own text
inside the border by BM25 (k1 1.2 and b 0.75, Lucene's defaults, which the lucene arm uses; the
border's chunks are the collection; words: runs of letters and digits, lower case). Fixed before
the count:
  the arm         two sides, as built
  three sides     the words' scores cut into the arm's five clusters like the other two sides;
                  the step is the three levels added; the scope gauged from the first two steps;
                  inside a step the scope first, then the three standings added
  words inside    the two sides' steps as built; the words' standing added to the two standings,
                  so the words only order chunks inside a step and its scope
  words alone     the check (the partner's): the border's chunks by the words' score only, the
                  lucene arm's information inside the same border and the same hand-over. If it
                  does as well, the graph adds the border and nothing else
Handed over through the arm's `_hand_over`. The gold hundred (cached first calls, facets off) and
the first hundred of the seeded draw of the unused questions (the tags side from the question
alone). No model call. The gold ids are read inside; numbers only.
"""
import json
import math
import os
import random
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
os.environ["HERB_V4_FACETS"] = "off"
os.environ.pop("HERB_V4_SCOPE_STEP", None)

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

BUDGET = 72000
CLUSTERS = 5
K1, B = 1.2, 0.75
ids_of = {name: {json.loads(line)["id"] for line in (REPO / "data" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
                 if line.strip()} for name in ("gold100", "heldout100")}
every = HQ.load_questions()
fresh = sorted((q for q in every if q.id not in ids_of["gold100"] | ids_of["heldout100"] and q.citations), key=lambda q: q.id)
SETS = (("the gold hundred", [q for q in every if q.id in ids_of["gold100"]]),
        ("100 unused questions", random.Random(20261011).sample(fresh, 300)[:100]))
p = V.prepare_over_corpus("the area and its words")
layer, n = p.layer, len(p.chunk_ids)
tag_e, chunk_e, id_rank = layer["edge_tag"], layer["edge_chunk"], layer["id_rank"]
parents = [str(row["parent"]) for row in p.chunk_rows]
parent_ids = {name: k for k, name in enumerate(sorted(set(parents)))}
parent_of = np.array([parent_ids[name] for name in parents], dtype=np.int64)
CV = np.asarray(p.chunk_vectors, dtype=np.float64)
TV = np.asarray(p.tag_vectors, dtype=np.float64)
AXES = V._QueryAxes(TV, np.eye(CV.shape[1]))
doc_cache = {}
WORD = re.compile(r"[a-z0-9]+")
bags = [Counter(WORD.findall(_resolve_chunk(row, doc_cache)[0].lower())) for row in p.chunk_rows]
lengths = np.array([sum(b.values()) for b in bags], dtype=np.float64)
print("prepared", flush=True)


def bm25(query_words, inside):
    docs = [bags[i] for i in inside]
    dl = lengths[inside]
    avg = float(dl.mean()) if dl.size else 1.
    N = len(docs)
    score = np.zeros(N)
    for w in set(query_words):
        df = sum(1 for d in docs if w in d)
        if not df:
            continue
        idf = math.log(1 + (N - df + .5) / (df + .5))
        tf = np.array([d.get(w, 0) for d in docs], dtype=np.float64)
        score += idf * tf * (K1 + 1) / (tf + K1 * (1 - B + B * dl / avg))
    return score


def standing(x):
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


def closest_tag(vector):
    row = vector @ TV.T
    out = np.full(n, float(row.min()))
    np.maximum.at(out, chunk_e, row[tag_e])
    return out


def order_of(inside, sides, gauge_extra):
    """Steps = the sides' levels added; scope from the first two steps; then scope, standings, id."""
    step = sum(WK.levels(s, CLUSTERS) for s in sides)
    z = sum(standing(s) for s in sides)
    lowest = int(step.min())
    taken = WK.majority_scopes(step <= max(3 + gauge_extra, lowest), parent_of[inside])   # the arm's rule
    in_scope = np.isin(parent_of[inside], taken)
    return inside[np.lexsort((id_rank[inside], -z, ~in_scope, step))].tolist()


def score(id_lists, context_ids, cites):
    got = {str(x) for x in context_ids}
    whole = [u for u in ([str(x) for x in unit] for unit in id_lists if unit) if set(u) <= got]
    return (bool(whole and set(whole[0]) & cites), any(set(u) & cites for u in whole[:3]), len(cites & got) / len(cites))


VARIANTS = ("the arm", "three sides", "words inside", "words alone")
captured = {}
the_combo = WK.cloud_combo


def recording(*a, **kw):
    out = the_combo(*a, **kw)
    captured["out"], captured["args"] = out, a
    return out


for label, drawn in SETS:
    rows = {v: [] for v in VARIANTS}
    for q in drawn:
        cites = {str(c) for c in q.citations}
        border, said = V.scope_by_name(q.question, p.tree, n)
        names = said["names_in_the_question"]
        if label == "the gold hundred":
            WK.cloud_combo = recording
            V.answer_one_question((q.id, q.question), p, None, 50, BUDGET)
            WK.cloud_combo = the_combo
            combo, a = captured["out"], captured["args"]
            inside = np.asarray(a[3], dtype=np.int64)
            T, D = combo["tags_nearness"][inside], combo["description_nearness"][inside]
            arm_order = combo["order"]
        else:
            if len(names) != 1:
                continue
            inside = np.flatnonzero(border)
            vector = np.asarray(V._query_cosines(V._without_names(q.question, names), [], AXES)[0]["query_description_cosines"],
                                dtype=np.float64)
            D, T = (CV @ vector)[inside], closest_tag(vector)[inside]
            arm_order = order_of(inside, (T, D), 0)
        W = bm25(WORD.findall(V._without_names(q.question, names).lower()), inside)
        orders = {"the arm": arm_order, "three sides": order_of(inside, (T, D, W), 1)}
        step2 = WK.levels(T, CLUSTERS) + WK.levels(D, CLUSTERS)
        z3 = standing(T) + standing(D) + standing(W)
        taken = WK.majority_scopes(step2 <= max(3, int(step2.min())), parent_of[inside])
        in_scope = np.isin(parent_of[inside], taken)
        orders["words inside"] = inside[np.lexsort((id_rank[inside], -z3, ~in_scope, step2))].tolist()
        orders["words alone"] = inside[np.lexsort((id_rank[inside], -W))].tolist()
        for v in VARIANTS:
            _, id_lists, context_ids, _, _, _ = V._hand_over(orders[v], p, BUDGET, 50, doc_cache)
            rows[v].append(score(id_lists, context_ids, cites))
    m = len(rows["the arm"])
    base = np.array(rows["the arm"], dtype=float)
    print(f"\n{label}: {m} questions")
    for v in VARIANTS:
        r = np.array(rows[v], dtype=float)
        d = r[:, 2] - base[:, 2]
        print(f"  {v:13s}: top text {r[:, 0].sum():3.0f} | among the first three {r[:, 1].sum():3.0f} | context_recall_id "
              f"{r[:, 2].mean():.3f} ({d.mean():+.3f}, se {d.std(ddof=1) / np.sqrt(m):.3f}, {int((d > 0).sum())} up {int((d < 0).sum())} down)")
print("done", flush=True)

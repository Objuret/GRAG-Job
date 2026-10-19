"""Can the perk be used? `the_parent_and_the_rare_tag.py` showed: a chunk that shares a rare tag with
a handed-over chunk and sits under the same parent is cited about as often as what is handed
over, on both hundreds. Here the strongest hits (the first two steps, from which the arm gauges its
scope) are the start, and the chunks tied to them that way come right after them, before the
rest of the arm's order. Fixed before the count (mine):
  rare, same parent   a tag of 2 to 8 chunks shared with a strongest hit, under the same parent
  rare, any parent    a tag of 2 to 8 chunks shared with a strongest hit
  any tag, same parent  (the check: is the rarity needed?) any shared tag, under the same parent
Inside each group the arm's own order (step, scope, standings, id). Handed over through the arm's
`_hand_over` inside 72,000 characters. The gold hundred (the arm's order, facets off, cached first
calls) and the first hundred of the seeded draw of the unused questions (the order from the
question alone). No model call. The gold ids are read inside; numbers only.
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
p = V.prepare_over_corpus("the rare tag in the order")
layer, n = p.layer, len(p.chunk_ids)
tag_e, chunk_e, id_rank = layer["edge_tag"], layer["edge_chunk"], layer["id_rank"]
chunks_of_tag, tags_of_chunk = defaultdict(set), defaultdict(set)
for t, c in zip(tag_e.tolist(), chunk_e.tolist()):
    chunks_of_tag[t].add(c)
    tags_of_chunk[c].add(t)
tag_ids = sorted(chunks_of_tag)
size_level = dict(zip(tag_ids, WK.levels(np.log([len(chunks_of_tag[t]) for t in tag_ids]), CLUSTERS).tolist()))
rare = {t for t in tag_ids if 2 <= len(chunks_of_tag[t]) and size_level[t] >= 3}
print("rare tags (levels 3 and 4):", len(rare), "from", min(len(chunks_of_tag[t]) for t in rare), "to",
      max(len(chunks_of_tag[t]) for t in rare), "chunks")
parents = [str(row["parent"]) for row in p.chunk_rows]
kinds = [str(row["kind"]) for row in p.chunk_rows]
home = list(zip(parents, kinds))
parent_ids = {name: k for k, name in enumerate(sorted(set(parents)))}
parent_of = np.array([parent_ids[name] for name in parents], dtype=np.int64)
CV = np.asarray(p.chunk_vectors, dtype=np.float64)
TV = np.asarray(p.tag_vectors, dtype=np.float64)
AXES = V._QueryAxes(TV, np.eye(CV.shape[1]))
doc_cache = {}
print("prepared", flush=True)


def standing(x):
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


def closest_tag(vector):
    row = vector @ TV.T
    out = np.full(n, float(row.min()))
    np.maximum.at(out, chunk_e, row[tag_e])
    return out


def score(id_lists, context_ids, cites):
    got = {str(x) for x in context_ids}
    whole = [u for u in ([str(x) for x in unit] for unit in id_lists if unit) if set(u) <= got]
    return (bool(whole and set(whole[0]) & cites), any(set(u) & cites for u in whole[:3]), len(cites & got) / len(cites))


captured = {}
the_combo = WK.cloud_combo


def recording(*a, **kw):
    out = the_combo(*a, **kw)
    captured["combo"], captured["inside"] = out, np.asarray(a[3], dtype=np.int64)
    return out


VARIANTS = ("the arm", "rare, same parent", "rare, any parent", "any tag, same parent")
for label, drawn in SETS:
    rows = {v: [] for v in VARIANTS}
    tied_count = defaultdict(list)
    for q in drawn:
        cites = {str(c) for c in q.citations}
        if label == "the gold hundred":
            WK.cloud_combo = recording
            V.answer_one_question((q.id, q.question), p, None, 50, BUDGET)
            WK.cloud_combo = the_combo
            combo, inside = captured["combo"], captured["inside"]
            step, value, in_scope = combo["step"], combo["value"], combo["in_scope"]
        else:
            border, said = V.scope_by_name(q.question, p.tree, n)
            names = said["names_in_the_question"]
            if len(names) != 1:
                continue
            inside = np.flatnonzero(border)
            vector = np.asarray(V._query_cosines(V._without_names(q.question, names), [], AXES)[0]["query_description_cosines"],
                                dtype=np.float64)
            D, T = (CV @ vector)[inside], closest_tag(vector)[inside]
            step, value, in_scope = np.zeros(n, dtype=np.int64), np.zeros(n), np.zeros(n, dtype=bool)
            step[inside] = WK.levels(D, CLUSTERS) + WK.levels(T, CLUSTERS)
            value[inside] = standing(D) + standing(T)
            taken = WK.majority_scopes(step[inside] <= max(3, int(step[inside].min())), parent_of[inside])
            in_scope[inside] = np.isin(parent_of[inside], taken)
        member = np.zeros(n, dtype=bool)
        member[inside] = True
        top = max(3, int(step[inside].min()))
        hits = [int(i) for i in inside if step[i] <= top]
        tied = {v: np.zeros(n, dtype=bool) for v in VARIANTS[1:]}
        for h in hits:
            for t in tags_of_chunk[h]:
                for c in chunks_of_tag[t]:
                    if c == h or not member[c] or step[c] <= top:
                        continue
                    same = home[c] == home[h]
                    if t in rare and same:
                        tied["rare, same parent"][c] = True
                    if t in rare:
                        tied["rare, any parent"][c] = True
                    if same:
                        tied["any tag, same parent"][c] = True
        for v in VARIANTS:
            group = np.where(step[inside] <= top, 0, 2)
            if v != "the arm":
                group = np.where(tied[v][inside] & (group == 2), 1, group)
                tied_count[v].append(int(tied[v][inside].sum()))
            by = np.lexsort((id_rank[inside], -value[inside], ~in_scope[inside], step[inside], group))
            _, id_lists, context_ids, _, _, _ = V._hand_over(inside[by].tolist(), p, BUDGET, 50, doc_cache)
            rows[v].append(score(id_lists, context_ids, cites))
    m = len(rows["the arm"])
    base = np.array(rows["the arm"], dtype=float)
    print(f"\n{label}: {m} questions")
    for v in VARIANTS:
        r = np.array(rows[v], dtype=float)
        d = r[:, 2] - base[:, 2]
        tied_txt = f"{np.mean(tied_count[v]):5.1f} tied a question | " if v != "the arm" else " " * 22
        print(f"  {v:22s}: {tied_txt}top text {r[:, 0].sum():3.0f} | among the first three {r[:, 1].sum():3.0f} |"
              f" context_recall_id {r[:, 2].mean():.3f} ({d.mean():+.3f}, se {d.std(ddof=1) / np.sqrt(m):.3f},"
              f" {int((d > 0).sum())} up {int((d < 0).sum())} down)")
print("done", flush=True)

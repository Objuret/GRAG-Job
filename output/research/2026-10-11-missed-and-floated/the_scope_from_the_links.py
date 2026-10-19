"""His 2026-10-16 "it still sounds like this could be used for a better scope..", said after the
count that a chunk reached through more tag links from what is handed over is cited more often,
and that the facet ranking mostly sorts the kinds of record. Not to lift single chunks (his
2026-10-05 "amount of closely related chunks" does not make a chunk more important) but to gauge
the area, as the arm's scope does (his "majority", "parent", "picks a scope, not a chunk").

The scopes, fixed before the count (mine as readings of his words):
  the arm          the parents holding the majority of the first two steps' chunks (the arm's
                   own `majority_scopes`)
  links            the parents the majority of the tag links from those chunks lead into: a link
                   is one of those chunks, one of its tags, and another chunk of the border with
                   that tag; the parents taken from the most links down until they hold more than
                   half, and every parent holding as many as the last one taken
  same-role links  the same, counting only the links where the tag ranks best in the same facet
                   in both chunks (ranks among the tag's chunks in the border)
  the kind alone   the kinds of record holding the majority of those chunks, every chunk of them
                   in scope (the check: what the kind of record does by itself)
Each scope is used the way the arm uses its own: weight and not a cut, inside a step the chunks
in scope first. Handed over through the arm's own `_hand_over` inside 72,000 characters.

On the gold hundred the order is the arm's own (the persons step as it stood, facets off, cached
first calls). On the first hundred of the seeded draw of the unused questions there is no first
call, so the order is made from the question alone as `the_persons_lines_on_unused_questions.py`
makes it. No model call. Per scope: how often it takes the same parents as the arm's, the chunks
in it a question, the share of them that hold a cited record, and through the hand-over the top
text, a cited record among the first three, context_recall_id. The gold ids are read inside;
numbers only.
"""
import json
import os
import random
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
os.environ["HERB_V4_FACETS"] = "off"
os.environ.pop("HERB_V4_SCOPE_STEP", None)

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

BUDGET = 72000
CLUSTERS = 5
ids_of = {name: {json.loads(line)["id"] for line in (REPO / "data" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
                 if line.strip()} for name in ("gold100", "heldout100")}
every = HQ.load_questions()
fresh = sorted((q for q in every if q.id not in ids_of["gold100"] | ids_of["heldout100"] and q.citations), key=lambda q: q.id)
gold_hundred = [q for q in every if q.id in ids_of["gold100"]]
unused = random.Random(20261011).sample(fresh, 300)[:100]
p = V.prepare_over_corpus("the scope from the links")
layer, n = p.layer, len(p.chunk_ids)
tag_e, chunk_e, place, id_rank = layer["edge_tag"], layer["edge_chunk"], layer["pos"][:, 1:], layer["id_rank"]
edges_of_tag, tags_of_chunk = defaultdict(list), defaultdict(list)
for k, (t, c) in enumerate(zip(tag_e.tolist(), chunk_e.tolist())):
    edges_of_tag[t].append(k)
    tags_of_chunk[c].append(t)
kinds = np.array([str(row["kind"]) for row in p.chunk_rows])
parents = [str(row["parent"]) for row in p.chunk_rows]
parent_ids = {name: k for k, name in enumerate(sorted(set(parents)))}
parent_of = np.array([parent_ids[name] for name in parents], dtype=np.int64)
CV = np.asarray(p.chunk_vectors, dtype=np.float64)
TV = np.asarray(p.tag_vectors, dtype=np.float64)
AXES = V._QueryAxes(TV, np.eye(CV.shape[1]))
doc_cache = {}
records = [{str(x) for x in _resolve_chunk(row, doc_cache)[1]} for row in p.chunk_rows]
print("prepared", flush=True)


def majority_of(counts):
    """The same rule as `majority_scopes`, on counts."""
    if not counts:
        return []
    total, acc, last = sum(counts.values()), 0, None
    for s, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        acc, last = acc + c, c
        if acc * 2 > total:
            break
    return sorted(s for s, c in counts.items() if c >= last)


def link_counts(hits, member, scope_of, same_role_only):
    counts = Counter()
    for h in hits:
        for t in tags_of_chunk[h]:
            e = np.array([k for k in edges_of_tag[t] if member[chunk_e[k]]])
            if e.size < 2:
                continue
            ranks = np.column_stack([rankdata(-place[e, f], method="average") for f in range(place.shape[1])])
            best = np.argmin(ranks, axis=1)
            at = {int(chunk_e[k]): j for j, k in enumerate(e)}
            fh = best[at[h]]
            for c, j in at.items():
                if c != h and (not same_role_only or best[j] == fh):
                    counts[int(scope_of[c])] += 1
    return counts


def score(id_lists, context_ids, cites):
    got = {str(x) for x in context_ids}
    whole = [u for u in ([str(x) for x in unit] for unit in id_lists if unit) if set(u) <= got]
    return (bool(whole and set(whole[0]) & cites), any(set(u) & cites for u in whole[:3]), len(cites & got) / len(cites))


def standing(x):
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


def closest_tag(vector):
    row = vector @ TV.T
    out = np.full(n, float(row.min()))
    np.maximum.at(out, chunk_e, row[tag_e])
    return out


captured = {}
the_combo = WK.cloud_combo


def recording(*a, **kw):
    out = the_combo(*a, **kw)
    captured["combo"], captured["inside"], captured["scope_of"] = out, np.asarray(a[3], dtype=np.int64), np.asarray(a[4])
    return out


SCOPES = ("the arm", "links", "same-role links", "the kind alone")


def scopes_for(inside, step, scope_of):
    member = np.zeros(n, dtype=bool)
    member[inside] = True
    hits = inside[step[inside] <= max(3, int(step[inside].min()))].tolist()
    flags, taken = {}, {}
    taken["the arm"] = WK.majority_scopes(np.isin(inside, hits), scope_of[inside])
    taken["links"] = majority_of(link_counts(hits, member, scope_of, False))
    taken["same-role links"] = majority_of(link_counts(hits, member, scope_of, True))
    for name in ("the arm", "links", "same-role links"):
        flags[name] = np.zeros(n, dtype=bool)
        flags[name][inside] = np.isin(scope_of[inside], taken[name])
    kinds_taken = majority_of(Counter(kinds[hits].tolist()))
    taken["the kind alone"] = kinds_taken
    flags["the kind alone"] = np.zeros(n, dtype=bool)
    flags["the kind alone"][inside] = np.isin(kinds[inside], kinds_taken)
    return flags, taken


for label, drawn in (("the gold hundred", gold_hundred), ("100 unused questions", unused)):
    rows = {name: [] for name in SCOPES}
    same_as_arm = Counter()
    size, cited_in = defaultdict(list), defaultdict(lambda: [0, 0])
    own = []
    for q in drawn:
        cites = {str(c) for c in q.citations}
        if label == "the gold hundred":
            WK.cloud_combo = recording
            out = V.answer_one_question((q.id, q.question), p, None, 50, BUDGET)
            WK.cloud_combo = the_combo
            own.append(score(out.meta["chunk_ids"], out.context_ids, cites))
            combo, inside, scope_of = captured["combo"], captured["inside"], captured["scope_of"]
            step, value = combo["step"], combo["value"]
        else:
            border, said = V.scope_by_name(q.question, p.tree, n)
            names = said["names_in_the_question"]
            if len(names) != 1:
                continue
            inside = np.flatnonzero(border)
            vector = np.asarray(V._query_cosines(V._without_names(q.question, names), [], AXES)[0]["query_description_cosines"],
                                dtype=np.float64)
            D, T = (CV @ vector)[inside], closest_tag(vector)[inside]
            step, value = np.zeros(n, dtype=np.int64), np.zeros(n)
            step[inside] = WK.levels(D, CLUSTERS) + WK.levels(T, CLUSTERS)
            value[inside] = standing(D) + standing(T)
            scope_of = parent_of
        flags, taken = scopes_for(inside, step, scope_of)
        gold = np.array([bool(cites & records[i]) for i in inside.tolist()])
        for name in SCOPES:
            f = flags[name][inside]
            size[name].append(int(f.sum()))
            cited_in[name][0] += int(f.sum())
            cited_in[name][1] += int(gold[f].sum())
            same_as_arm[name] += bool((flags[name][inside] == flags["the arm"][inside]).all())
            by = np.lexsort((id_rank[inside], -value[inside], ~flags[name][inside], step[inside]))
            _, id_lists, context_ids, _, _, _ = V._hand_over(inside[by].tolist(), p, BUDGET, 50, doc_cache)
            rows[name].append(score(id_lists, context_ids, cites))
    m = len(rows["the arm"])
    print(f"\n{label}: {m} questions")
    if own:
        o = np.array(own, dtype=float).mean(axis=0)
        print(f"  the arm's own run: top text {o[0] * m:.0f} | among the first three {o[1] * m:.0f} | context_recall_id {o[2]:.3f}")
    base = np.array(rows["the arm"], dtype=float)
    for name in SCOPES:
        r = np.array(rows[name], dtype=float)
        d = r[:, 2] - base[:, 2]
        print(f"  {name:16s}: same chunks in scope as the arm on {same_as_arm[name]:3d} | {np.mean(size[name]):6.1f} chunks in scope a question,"
              f" {cited_in[name][1] / max(cited_in[name][0], 1):5.1%} of them cited | top text {r[:, 0].sum():3.0f} |"
              f" among the first three {r[:, 1].sum():3.0f} | context_recall_id {r[:, 2].mean():.3f}"
              f" ({d.mean():+.3f}, se {d.std(ddof=1) / np.sqrt(m) if m > 1 else 0:.3f}, {int((d > 0).sum())} up {int((d < 0).sum())} down)")
print("done", flush=True)

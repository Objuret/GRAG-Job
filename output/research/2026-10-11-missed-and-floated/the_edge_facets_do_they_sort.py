"""His 2026-10-13 "how do we make them work then?" (the query facets). Before any build: can the
edge's facet values sort the chunks under one tag at all, and does WHICH facet sorts them change
with the question? A side count: no arm change, no model call (HERB_V4_OFFLINE=on, the cached
first calls of the hundred, the chain of the `name` step for the picked tags). The gold ids are
read inside; numbers only.

Under one graph tag every edge has the same closeness to the query tag, so the five values on the
edges (topic, temporal, why, activity, concreteness) are all that can say which chunk under the
tag is the one.

  1  no gold. Per value: how much of its spread over all edges lies between record kinds,
     between chunks, between tags; and inside one tag's edges of one product (what a sort has to
     work with): the share of the whole spread that is left there, and how much of that is the
     record kind again.
  2  gold in hand. A group = one picked graph tag of one query tag, its edges inside the border,
     with a chunk that holds a cited record and one that does not. Per value: how often the
     cited chunk's edge stands above the other's (0.50 = says nothing), as it is, less the
     chunk's own mean over its edges, less its record kind's mean. The same for the facet the
     query tag names, for that facet's place among the edge's own four, and for the chunk
     description's closeness to the question and to the query description (what a value that
     does sort looks like).
  3  does the facet that sorts change with the question: per question the best of the four on
     half of its groups, read on the other half, beside the one facet that is best over all
     questions and beside the named facet.
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
os.environ["HERB_V4_SCOPE_STEP"] = "name"

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

BUDGET = 72000
FACETS = WK.FACETS
wanted = [json.loads(line)["id"] for line in (REPO / "data" / "gold100.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("do the edge facets sort")
layer, n = p.layer, len(p.chunk_ids)
tag_e, chunk_e, raw = layer["edge_tag"], layer["edge_chunk"], layer["raw"]
kind, product = layer["kind"], layer["product"]
doc_cache = {}
records = [{str(x) for x in _resolve_chunk(row, doc_cache)[1]} for row in p.chunk_rows]
print("prepared", flush=True)


def between(values, groups):
    """The share of the values' spread (sum of squares about the mean) that lies between the groups."""
    ids, at = np.unique(groups, return_inverse=True)
    mean = np.bincount(at, weights=values) / np.bincount(at)
    total = float(((values - values.mean()) ** 2).sum())
    return float((np.bincount(at) * (mean - values.mean()) ** 2).sum()) / total if total > 0 else 0.


print("\n== 1: no gold. The spread of each value over the", raw.shape[0], "edges ==")
pair = tag_e.astype(np.int64) * (int(product.max()) + 1) + product[chunk_e]
ids, at, size = np.unique(pair, return_inverse=True, return_counts=True)
print(f"a tag's edges inside one product: {ids.size} such groups, {int((size > 1).sum())} with more than one edge "
      f"(the middle one of those holds {int(np.median(size[size > 1]))} edges)")
print("value | between record kinds | between chunks | between tags | left inside one tag's edges of one product | of that, record kind again")
for f, name in enumerate(FACETS):
    x = raw[:, f]
    mean = np.bincount(at, weights=x) / size
    inside = x - mean[at]
    total = float(((x - x.mean()) ** 2).sum())
    left = float((inside ** 2).sum()) / total
    # inside a group, between the record kinds of its chunks
    key = at.astype(np.int64) * (int(kind.max()) + 1) + kind[chunk_e]
    kid, kat = np.unique(key, return_inverse=True)
    kmean = np.bincount(kat, weights=inside) / np.bincount(kat)
    by_kind = float((kmean[kat] ** 2).sum()) / max(float((inside ** 2).sum()), 1e-300)
    print(f"  {name:13s} | {between(x, kind[chunk_e]):5.0%} | {between(x, chunk_e):5.0%} | {between(x, tag_e):5.0%} | {left:5.0%} | {by_kind:5.0%}")

captured = {}
the_chain = WK.chain


def recording(layer_, query, cos_noise, k):
    out = the_chain(layer_, query, cos_noise, k)
    captured["query"], captured["out"] = query, out
    return out


WK.chain = recording
n_c = np.maximum(layer["n_c"], 1)
chunk_mean = np.column_stack([np.bincount(chunk_e, weights=raw[:, f], minlength=n) / n_c for f in range(len(FACETS))])
kind_count = np.bincount(kind[chunk_e])
kind_mean = np.column_stack([np.bincount(kind[chunk_e], weights=raw[:, f]) / kind_count for f in range(len(FACETS))])
LESS = {"as it is": raw, "less the chunk's own mean": raw - chunk_mean[chunk_e], "less its record kind's mean": raw - kind_mean[kind[chunk_e]]}


def above(gold, other):
    g, h = np.asarray(gold, dtype=np.float64)[:, None], np.asarray(other, dtype=np.float64)[None, :]
    return float((g > h).sum() + 0.5 * (g == h).sum()), g.size * h.size


pooled = defaultdict(lambda: [0., 0])
wide = defaultdict(lambda: [0., 0])     # the same over all the picked edges of one query tag (its five nearest tags together)
wide_groups, wide_sizes = 0, []
wide_question = []
by_tag_question = []
per_question = []                     # per question its groups: per facet (wins, pairs), and the named facet's
sizes, with_both, groups_all = [], 0, 0
top = defaultdict(lambda: [0, 0.])      # picking the highest edge of a group: right, and what blind would give
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    V.answer_one_question((qid, q.question), p, None, 50, BUDGET)
    query, out = captured["query"], captured["out"]
    border, _ = V.scope_by_name(q.question, p.tree, n)
    gold = np.array([bool(cites & records[i]) for i in range(n)])
    named = np.asarray(query["named_facet"], dtype=np.int64)
    d_q = np.asarray(query["d_question"], dtype=np.float64)
    d_d = np.asarray(query["d_description"], dtype=np.float64)
    here, here_wide = [], []
    rows = np.asarray(query["cosines"], dtype=np.float64)
    for i in range(named.size):
        edges = np.flatnonzero(out["picked_edge"][i] & border[chunk_e])
        g, h = edges[gold[chunk_e[edges]]], edges[~gold[chunk_e[edges]]]
        if g.size and h.size:
            wide_groups += 1
            wide_sizes.append(edges.size)
            f = 1 + int(named[i])
            row = {}
            for label, values in LESS.items():
                for j, name in enumerate(FACETS):
                    w, m = above(values[g, j], values[h, j])
                    wide[(label, name)][0] += w
                    wide[(label, name)][1] += m
                    row[(label, name)] = (w, m)
                    if label == "as it is":
                        row[name] = (w, m)
            for label, values in (("the closeness of the graph tag to the query tag", rows[i][tag_e]),
                                  ("the facet the query tag names", raw[:, f]),
                                  ("the facet the query tag names, less the chunk's own mean", LESS["less the chunk's own mean"][:, f]),
                                  ("that facet's place among the edge's own four", -out["rank_in_edge"][:, named[i]].astype(np.float64)),
                                  ("the chunk description's closeness to the question", d_q[chunk_e]),
                                  ("the chunk description's closeness to the query description", d_d[chunk_e])):
                w, m = above(values[g], values[h])
                wide[("", label)][0] += w
                wide[("", label)][1] += m
            row["named"] = above(raw[g, f], raw[h, f])
            here_wide.append(row)
        for t in np.unique(tag_e[edges]).tolist():
            e = edges[tag_e[edges] == t]
            groups_all += 1
            sizes.append(e.size)
            g, h = e[gold[chunk_e[e]]], e[~gold[chunk_e[e]]]
            if not g.size or not h.size:
                continue
            with_both += 1
            row = {}
            for label, values in LESS.items():
                for f, name in enumerate(FACETS):
                    w, m = above(values[g, f], values[h, f])
                    pooled[(label, name)][0] += w
                    pooled[(label, name)][1] += m
                    if label == "as it is":
                        row[name] = (w, m)
                        best = e[np.argmax(values[e, f])]
                        top[name][0] += bool(gold[chunk_e[best]])
            f = 1 + int(named[i])
            for label, values in (("the facet the query tag names", raw[:, f]),
                                  ("that facet's place among the edge's own four", -out["rank_in_edge"][:, named[i]].astype(np.float64)),
                                  ("the chunk description's closeness to the question", d_q[chunk_e]),
                                  ("the chunk description's closeness to the query description", d_d[chunk_e])):
                w, m = above(values[g], values[h])
                pooled[("", label)][0] += w
                pooled[("", label)][1] += m
                top[label][0] += bool(gold[chunk_e[e[np.argmax(values[e])]]])
            row["named"] = above(raw[g, f], raw[h, f])
            top["blind"][1] += g.size / e.size
            here.append(row)
    per_question.append(here)
    wide_question.append(here_wide)
    # every picked edge of the question once, with its graph tag: for the split by graph tags (part 6)
    every_edge = np.flatnonzero(out["picked_edge"].any(axis=0) & border[chunk_e])
    by_tag_question.append((every_edge, tag_e[every_edge], gold[chunk_e[every_edge]],
                            np.array([1 + int(named[out["picked_edge"][:, e].argmax()]) for e in every_edge], dtype=np.int64)))
WK.chain = the_chain

print(f"\n== 2: gold in hand. {groups_all} groups (a picked graph tag of a query tag inside the border), the middle one holds "
      f"{int(np.median(sizes))} edges; {with_both} hold a cited chunk and one that is not ==")
print("how often the cited chunk's edge stands above the other's (0.50 says nothing)")
for label in LESS:
    print(f"  {label:28s}: " + " ; ".join(f"{name} {pooled[(label, name)][0] / pooled[(label, name)][1]:.2f}" for name in FACETS))
for (label, name), (w, m) in pooled.items():
    if not label:
        print(f"  {name}: {w / m:.2f}")
print(f"the highest edge of a group is the cited chunk's (of {with_both} groups; blind would be right on {top['blind'][1]:.0f}): "
      + " ; ".join(f"{name} {top[name][0]}" for name in FACETS)
      + " ; " + " ; ".join(f"{name} {top[name][0]}" for name in top if name not in FACETS and name != "blind"))

print("\n== 3: does the facet that sorts change with the question (the four, topic left out) ==")
four = FACETS[1:]
rng = random.Random(20261014)
gain = {"the question's own best facet (picked on half of its groups, read on the other half)": [0., 0],
        "the one facet that is best over all the questions": [0., 0], "the facet the query tag names": [0., 0]}
everywhere = max(four, key=lambda name: pooled[("as it is", name)][0] / pooled[("as it is", name)][1])
used = 0
for groups in per_question:
    if len(groups) < 2:
        continue
    used += 1
    order = list(range(len(groups)))
    rng.shuffle(order)
    half = len(order) // 2
    for first, second in ((order[:half], order[half:]), (order[half:], order[:half])):
        score = {name: sum(groups[k][name][0] for k in first) / max(sum(groups[k][name][1] for k in first), 1) for name in four}
        mine = max(four, key=lambda name: score[name])
        for label, name in zip(gain, (mine, everywhere, "named")):
            gain[label][0] += sum(groups[k][name][0] for k in second)
            gain[label][1] += sum(groups[k][name][1] for k in second)
print(f"{used} questions with two groups or more; the facet best over all the questions is {everywhere}")
for label, (w, m) in gain.items():
    print(f"  {w / max(m, 1):.2f}  {label}")

print(f"\n== 4: the same over what a query tag sorts: all the picked edges of one query tag inside the border (its five nearest "
      f"graph tags together). {wide_groups} such sets hold a cited chunk and one that is not, the middle one {int(np.median(wide_sizes))} edges ==")
print("how often the cited chunk's edge stands above the other's (0.50 says nothing)")
for label in LESS:
    print(f"  {label:28s}: " + " ; ".join(f"{name} {wide[(label, name)][0] / wide[(label, name)][1]:.2f}" for name in FACETS))
for (label, name), (w, m) in wide.items():
    if not label:
        print(f"  {name}: {w / m:.2f}")
gain = {"the question's own best facet (picked on half of its sets, read on the other half)": [0., 0],
        "the one facet that is best over all the questions": [0., 0], "the facet the query tag names": [0., 0]}
everywhere = max(four, key=lambda name: wide[("as it is", name)][0] / wide[("as it is", name)][1])
used = 0
for groups in wide_question:
    if len(groups) < 2:
        continue
    used += 1
    order = list(range(len(groups)))
    rng.shuffle(order)
    half = len(order) // 2
    for first, second in ((order[:half], order[half:]), (order[half:], order[:half])):
        score = {name: sum(groups[k][name][0] for k in first) / max(sum(groups[k][name][1] for k in first), 1) for name in four}
        mine = max(four, key=lambda name: score[name])
        for label, name in zip(gain, (mine, everywhere, "named")):
            gain[label][0] += sum(groups[k][name][0] for k in second)
            gain[label][1] += sum(groups[k][name][1] for k in second)
print(f"{used} questions with two sets or more; the facet best over all the questions is {everywhere}")
for label, (w, m) in gain.items():
    print(f"  {w / max(m, 1):.2f}  {label}")

print("\n== 5: the same question with the chunk's own level, or its record kind's, taken out of the values: is there a facet that "
      "sorts for ONE question and keeps doing so on that question's other sets? (20 splits in halves, the mean) ==")
for less in LESS:
    own, fixed = [], {name: wide[(less, name)][0] / wide[(less, name)][1] for name in four}
    best_fixed = max(four, key=lambda name: fixed[name])
    for split in range(20):
        w_own = m_own = 0.
        for groups in wide_question:
            if len(groups) < 2:
                continue
            order = list(range(len(groups)))
            rng.shuffle(order)
            half = len(order) // 2
            for first, second in ((order[:half], order[half:]), (order[half:], order[:half])):
                score = {name: sum(groups[k][(less, name)][0] for k in first) / max(sum(groups[k][(less, name)][1] for k in first), 1)
                         for name in four}
                mine = max(four, key=lambda name: score[name])
                w_own += sum(groups[k][(less, mine)][0] for k in second)
                m_own += sum(groups[k][(less, mine)][1] for k in second)
        own.append(w_own / max(m_own, 1))
    print(f"  {less:28s}: the question's own best facet {np.mean(own):.3f} (between splits {np.std(own):.3f}) ; the one facet best "
          f"over all questions ({best_fixed}) {fixed[best_fixed]:.3f} ; the four: " + " ".join(f"{fixed[name]:.2f}" for name in four))

print("\n== 6: the same with no edge on both sides. Per question every picked edge once; its graph tags split in two halves; in a half "
      "every cited chunk's edge against every other edge. The facet best on one half read on the other (50 splits, the mean) ==")
SPLITS = 50
for less, values in LESS.items():
    own, fixed_w, fixed_m, named_w, named_m, used = [], np.zeros(len(four)), np.zeros(len(four)), 0., 0., 0
    for split in range(SPLITS):
        w_own = m_own = 0.
        for edges, tags, is_gold, named_at in by_tag_question:
            names = np.unique(tags).tolist()
            if len(names) < 2:
                continue
            rng.shuffle(names)
            halves = [np.isin(tags, names[:len(names) // 2]), np.isin(tags, names[len(names) // 2:])]
            sides = []
            for mask in halves:
                g, h = edges[mask & is_gold], edges[mask & ~is_gold]
                sides.append(None if not g.size or not h.size else
                             ([above(values[g, 1 + j], values[h, 1 + j]) for j in range(len(four))],
                              above(values[g, named_at[mask & is_gold]], values[h, named_at[mask & ~is_gold]])))
            if sides[0] is None or sides[1] is None:
                continue
            used += split == 0
            for a, b in ((0, 1), (1, 0)):
                mine = int(np.argmax([w / m for w, m in sides[a][0]]))
                w_own += sides[b][0][mine][0]
                m_own += sides[b][0][mine][1]
                for j in range(len(four)):
                    fixed_w[j] += sides[b][0][j][0]
                    fixed_m[j] += sides[b][0][j][1]
                named_w += sides[b][1][0]
                named_m += sides[b][1][1]
        own.append(w_own / max(m_own, 1))
    fixed = fixed_w / np.maximum(fixed_m, 1)
    print(f"  {less:28s}: {used} questions ; the question's own best facet {np.mean(own):.3f} (between splits {np.std(own):.3f}) ; "
          f"the four fixed: " + " ".join(f"{name} {fixed[j]:.3f}" for j, name in enumerate(four))
          + f" ; each edge by the facet its query tag names {named_w / max(named_m, 1):.3f}")
print("done", flush=True)

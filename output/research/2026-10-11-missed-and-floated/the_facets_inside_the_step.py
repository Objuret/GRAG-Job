"""His 2026-10-15 "the facets were never supposed to carry the whole weight themselves, they are
supposed to influence the already existing relationship for chunks and tags so to speak". The
existing relationship as the arm has it (the combo: the chunk descriptions' side and the tags'
side, each cut into clusters; a chunk's step is its two levels added; in scope first inside a
step) stays; its step is the range inside which chunks count as equal. Inside it the facets
decide: the facet ranking of the edge the chunk was reached through (its closest tag to a query
tag), in that query tag's order of the four facets; only then the two sides' standings added.

A side run through the arm's own delivery (`answer_one_question` with the step as it stands,
then `_hand_over` for the variants), the hundred, cached first calls, no lane call; the facet net
reads the query tags here. The arm's file is not changed.

  the arm as it stands
  facets inside the step, order: the facet the model named first | his net's order for the
  query tag | his net's order for a query tag of another question (the check)

Printed: top text holds a cited record (of 100) | a cited record among the first three texts |
context_recall_id (share of the cited records delivered inside 72,000 characters) | against the
arm: mean difference (standard error), questions higher / lower. The gold ids are read inside;
numbers only.
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
os.environ.pop("HERB_V4_SCOPE_STEP", None)
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from arms import artefact_v4 as V  # noqa: E402
from artefact import query_facets as QF  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

BUDGET = 72000
FOUR = list(WK.RANKING_FACETS)
wanted = [json.loads(line)["id"] for line in (REPO / "data" / "gold100.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the facets inside the step")
layer = p.layer
id_rank, pos = layer["id_rank"], layer["pos"][:, 1:]          # each edge's place in each facet's ranking, 0 to 1
print("prepared", flush=True)

captured = {}
the_combo, the_interpret = WK.cloud_combo, V._interpret


def recording(layer_, cosines, d_near, inside, scope_of, k):
    out = the_combo(layer_, cosines, d_near, inside, scope_of, k)
    captured["combo"], captured["inside"] = out, np.asarray(inside, dtype=np.int64)
    return out


def interpreting(text, prepared):
    got = the_interpret(text, prepared)
    captured["content"] = got[0]
    return got


WK.cloud_combo, V._interpret = recording, interpreting


def score(id_lists, context_ids, cites):
    got = {str(x) for x in context_ids}
    whole = [u for u in ([str(x) for x in unit] for unit in id_lists if unit) if set(u) <= got]
    return (bool(whole and set(whole[0]) & cites), any(set(u) & cites for u in whole[:3]), len(cites & got) / len(cites))


rows = []
for at, qid in enumerate(wanted):
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    out = V.answer_one_question((qid, q.question), p, None, 50, BUDGET)
    base = score(out.meta["chunk_ids"], out.context_ids, cites)
    combo, inside, content = captured["combo"], captured["inside"], captured["content"]
    tags = (*content.tags, *content.query_tags)
    net = QF.head_scores([t.text for t in tags], content.description)[:, 1:]
    named_orders = [[FOUR.index(t.facet)] + [j for j in range(4) if j != FOUR.index(t.facet)] for t in tags]
    net_orders = [list(np.argsort(-row, kind="stable")) for row in net]
    rows.append({"qid": qid, "cites": cites, "base": base, "combo": combo, "inside": inside,
                 "named": named_orders, "net": net_orders})
    if (at + 1) % 25 == 0:
        print(f"   {at + 1} questions", flush=True)
WK.cloud_combo, V._interpret = the_combo, the_interpret

rng = random.Random(20261015)
SOURCES = ("the facet the model named first", "his net's order", "his net's order of another question")
PLACES = ("inside the step", "only among chunks whose standings fall in one cluster (five over the border) inside the step")
results = {"the arm as it stands": [r["base"] for r in rows]}
for where in PLACES:
    for source in SOURCES:
        results[f"facets {where}: {source}"] = []
doc_cache = {}
for k, r in enumerate(rows):
    combo, inside = r["combo"], r["inside"]
    step, in_scope, value = combo["step"], combo["in_scope"], combo["value"]
    edge, qtag = combo["edge"], combo["query_tag"]
    other_rows = rng.choice([x for j, x in enumerate(rows) if j != k])["net"]
    value_level = WK.levels(value[inside], 5)                # the standings' own equal ranges, 1 the highest
    for source, orders in ((SOURCES[0], r["named"]), (SOURCES[1], r["net"]),
                           (SOURCES[2], [other_rows[i % len(other_rows)] for i in range(len(r["net"]))])):
        keys = np.ones((inside.size, 4))                     # a chunk with no eligible edge: last in every facet
        for at_c, c in enumerate(inside.tolist()):
            e = int(edge[c])
            if e >= 0:
                keys[at_c] = -pos[e, orders[int(qtag[c])]]
        for where in PLACES:
            if where == PLACES[0]:
                by = np.lexsort((id_rank[inside], -value[inside], keys[:, 3], keys[:, 2], keys[:, 1], keys[:, 0],
                                 ~in_scope[inside], step[inside]))
            else:
                by = np.lexsort((id_rank[inside], -value[inside], keys[:, 3], keys[:, 2], keys[:, 1], keys[:, 0],
                                 value_level, ~in_scope[inside], step[inside]))
            order = inside[by].tolist()
            _, id_lists, context_ids, _, _, _ = V._hand_over(order, p, BUDGET, 50, doc_cache)
            results[f"facets {where}: {source}"].append(score(id_lists, context_ids, r["cites"]))

print("\ntop text holds a cited record | a cited record among the first three texts | context_recall_id | against the arm: mean "
      "difference (standard error), questions higher / lower")
base = np.array([x[2] for x in results["the arm as it stands"]])
for label, got in results.items():
    a = np.array(got, dtype=np.float64)
    diff = a[:, 2] - base
    print(f"  {int(a[:, 0].sum()):3d} | {int(a[:, 1].sum()):3d} | {a[:, 2].mean():.4f} | {diff.mean():+.3f} "
          f"({diff.std(ddof=1) / np.sqrt(diff.size):.3f}), {int((diff > 1e-9).sum())} / {int((diff < -1e-9).sum())}  {label}")
print("done", flush=True)

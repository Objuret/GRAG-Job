"""His 2026-10-13 "how is it going with that concept, the rank/value/whatever from the queryfacets,
how are they used?" What the query facets do in the last version built on his words, the `name`
step of 2026-10-11 (the name border, `v4_walk.chain`'s order), on the hundred. A side run through
the arm's own `answer_one_question`: the arm's file is not changed, no model call
(HERB_V4_OFFLINE=on, the cached first calls).

In `chain` a query tag names one facet. Its picked edges (the edges of its five nearest graph
tags) are put in order by where that facet stands among the edge's own four facet values, then
topic, then closeness, and take their closeness from that order (`spread_by_facets`). Inside a
level of strength the chunks are ordered by the winning edge's facets.

  A  as it is
  B  the picked edges keep their own closeness: nothing re-placed
  C  re-placed by topic and closeness only: the named facet out
  D  every query tag made to name the same facet: temporal, why, activity, concreteness
  E  every query tag's named facet turned to the next one of the four

Printed per run: top chunk holds a cited record (of 100) | a cited record among the first three
chunks | context_recall_id (share of the cited records delivered inside 72,000 characters) |
against A: mean difference (standard error), questions higher / lower | the questions whose
delivered chunks are other chunks than in A. The gold ids are read inside; numbers only.
"""
import json
import os
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
os.environ["HERB_V4_SCOPE_STEP"] = "name"

from arms import artefact_v4 as V  # noqa: E402
from artefact import query_content as Q  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

BUDGET = 72000
wanted = [json.loads(line)["id"] for line in (REPO / "data" / "gold100.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the query facets in the name step")
print("prepared", flush=True)

the_spread = WK.spread_by_facets
the_index = Q.QueryTag.facet_index
FOUR = len(WK.RANKING_FACETS)


def keep_closeness(cosine, best, width, facet_class, order, topic):
    place, _ = the_spread(cosine, best, width, facet_class, order, topic)
    return place, np.asarray(cosine, dtype=np.float64)


def topic_only(cosine, best, width, facet_class, order, topic):
    return the_spread(cosine, best, width, np.zeros_like(np.asarray(facet_class)), order, topic)


RUNS = [("A  as it is", None, None),
        ("B  the picked edges keep their own closeness", keep_closeness, None),
        ("C  re-placed by topic and closeness only", topic_only, None)]
RUNS += [(f"D  every query tag names {name}", None, (lambda self, j=j: j)) for j, name in enumerate(WK.RANKING_FACETS)]
RUNS += [("E  every query tag's named facet turned to the next one", None,
          (lambda self: (WK.RANKING_FACETS.index(self.facet) + 1) % FOUR))]

results, delivered = {}, {}
for label, spread, index in RUNS:
    WK.spread_by_facets = spread or the_spread
    Q.QueryTag.facet_index = property(index) if index else the_index
    rows, sets = [], []
    for qid in wanted:
        q = by_id[qid]
        cites = {str(c) for c in q.citations}
        out = V.answer_one_question((qid, q.question), p, None, 50, BUDGET)
        got = {str(x) for x in out.context_ids}
        whole = [u for u in ([str(x) for x in unit] for unit in out.meta["chunk_ids"] if unit) if set(u) <= got]
        rows.append((bool(whole and set(whole[0]) & cites), any(set(u) & cites for u in whole[:3]), len(cites & got) / len(cites)))
        sets.append(frozenset(got))
    results[label], delivered[label] = np.array(rows, dtype=np.float64), sets
    print(f"   done: {label}", flush=True)
WK.spread_by_facets, Q.QueryTag.facet_index = the_spread, the_index

base, base_sets = results[RUNS[0][0]], delivered[RUNS[0][0]]
print("\ntop chunk holds a cited record | a cited record among the first three chunks | context_recall_id | against A: mean difference "
      "(standard error), questions higher / lower | questions whose delivered records differ from A")
for label, a in results.items():
    diff = a[:, 2] - base[:, 2]
    other = sum(1 for x, y in zip(delivered[label], base_sets) if x != y)
    print(f"  {int(a[:, 0].sum()):3d} | {int(a[:, 1].sum()):3d} | {a[:, 2].mean():.4f} | {diff.mean():+.3f} "
          f"({diff.std(ddof=1) / np.sqrt(diff.size):.3f}), {int((diff > 1e-9).sum())} / {int((diff < -1e-9).sum())} | {other:3d}  {label}")
print("done", flush=True)

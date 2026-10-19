"""The facets as the function a tag has on an edge (his thesis 6.4), used on the links between
chunks and not for the query: inside the arm's step (the range the existing relationship calls
equal), a chunk tied to one of the first hits by a tag that has the same role on both edges goes
first; then in scope, then the standings. A tag's role on an edge (mine): the facet the edge
stands highest in (its places in the four rankings compared). The first hits: the chunks the
scope is gauged from (the combo's first two steps). Checks: a tie by any shared tag; a tie only
by different-role tags.

A side run through the arm's own delivery (`_hand_over`), the persons step as it stands as the
base, the hundred, cached first calls, no lane call; the arm's file is not changed. Printed: top
text holds a cited record | among the first three | context_recall_id | against the arm. The gold
ids are read inside; numbers only.
"""
import json
import os
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
os.environ.pop("HERB_V4_SCOPE_STEP", None)

from arms import artefact_v4 as V  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

BUDGET = 72000
wanted = [json.loads(line)["id"] for line in (REPO / "data" / "gold100.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("role ties inside the step")
layer, n = p.layer, len(p.chunk_ids)
tag_e, chunk_e, id_rank = layer["edge_tag"], layer["edge_chunk"], layer["id_rank"]
role = np.argmax(layer["pos"][:, 1:], axis=1)
edges_of_chunk, edges_of_tag = defaultdict(list), defaultdict(list)
for k, (t, c) in enumerate(zip(tag_e.tolist(), chunk_e.tolist())):
    edges_of_chunk[c].append(k)
    edges_of_tag[t].append(k)
print("prepared", flush=True)

captured = {}
the_combo = WK.cloud_combo


def recording(layer_, cosines, d_near, inside, scope_of, k):
    out = the_combo(layer_, cosines, d_near, inside, scope_of, k)
    captured["combo"], captured["inside"] = out, np.asarray(inside, dtype=np.int64)
    return out


WK.cloud_combo = recording


def score(id_lists, context_ids, cites):
    got = {str(x) for x in context_ids}
    whole = [u for u in ([str(x) for x in unit] for unit in id_lists if unit) if set(u) <= got]
    return (bool(whole and set(whole[0]) & cites), any(set(u) & cites for u in whole[:3]), len(cites & got) / len(cites))


LABELS = ("tied to a first hit by a same-role tag, first inside the step", "tied to a first hit by any shared tag (check)",
          "tied to a first hit only by different-role tags (check)")
results = {"the arm as it stands": []}
for label in LABELS:
    results[label] = []
doc_cache = {}
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    out = V.answer_one_question((qid, q.question), p, None, 50, BUDGET)
    results["the arm as it stands"].append(score(out.meta["chunk_ids"], out.context_ids, cites))
    combo, inside = captured["combo"], captured["inside"]
    step, in_scope, value = combo["step"], combo["in_scope"], combo["value"]
    hits = set(inside[step[inside] <= max(3, int(step[inside].min()))].tolist())
    member = np.zeros(n, dtype=bool)
    member[inside] = True
    same, any_tie = np.zeros(n, dtype=bool), np.zeros(n, dtype=bool)
    for h in hits:
        for e1 in edges_of_chunk[h]:
            for e2 in edges_of_tag[int(tag_e[e1])]:
                c = int(chunk_e[e2])
                if c == h or not member[c]:
                    continue
                any_tie[c] = True
                if role[e1] == role[e2]:
                    same[c] = True
    only_other = any_tie & ~same
    for label, flag in zip(LABELS, (same, any_tie, only_other)):
        by = np.lexsort((id_rank[inside], -value[inside], ~flag[inside], ~in_scope[inside], step[inside]))
        _, id_lists, context_ids, _, _, _ = V._hand_over(inside[by].tolist(), p, BUDGET, 50, doc_cache)
        results[label].append(score(id_lists, context_ids, cites))
WK.cloud_combo = the_combo

print("\ntop text holds a cited record | a cited record among the first three texts | context_recall_id | against the arm: mean "
      "difference (standard error), questions higher / lower")
base = np.array([x[2] for x in results["the arm as it stands"]])
for label, got in results.items():
    a = np.array(got, dtype=np.float64)
    diff = a[:, 2] - base
    print(f"  {int(a[:, 0].sum()):3d} | {int(a[:, 1].sum()):3d} | {a[:, 2].mean():.4f} | {diff.mean():+.3f} "
          f"({diff.std(ddof=1) / np.sqrt(diff.size):.3f}), {int((diff > 1e-9).sum())} / {int((diff < -1e-9).sum())}  {label}")
print("done", flush=True)

"""His 2026-10-15 "well, build and explore the effect", then "you litterally just did the same shit as
you did before. .again..". The facet relations built into the arm (`v4_walk.facet_relations`)
varied where their effect could differ, each beside the same with the facet condition dropped
(any shared tag), so the facets' own part shows. A side run through the arm's own delivery, the
hundred, cached first calls, no lane call; the arm's file is not changed.

  start   the strongest hits (the first two steps) | the top chunk of the order only
  lift    inside the step after the scope (as built) | inside the step before the scope | one
          step up (a tied chunk's step less one)
  tags    every tag | only the tags whose chunk count in the border falls in the smaller of two
          clusters of the tags' sizes (rare tags; the two clusters are mine)
Printed per variant: share of cited records delivered (context_recall_id), top text holds a cited
record, against the arm without ties; and the chunks the variant moves into the 72,000 and out of
it, a question, and how often each holds a cited record. The gold ids are read inside; numbers
only.
"""
import json
import os
import sys
import warnings
from collections import defaultdict
from itertools import product as grid
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"
os.environ.pop("HERB_V4_SCOPE_STEP", None)

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

BUDGET = 72000
wanted = [json.loads(line)["id"] for line in (REPO / "data" / "gold100.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("exploring the facet relations")
layer, n = p.layer, len(p.chunk_ids)
tag_e, chunk_e, place, id_rank = layer["edge_tag"], layer["edge_chunk"], layer["pos"][:, 1:], layer["id_rank"]
doc_cache = {}
records = [{str(x) for x in _resolve_chunk(row, doc_cache)[1]} for row in p.chunk_rows]
print("prepared", flush=True)

captured = {}
the_combo = WK.cloud_combo


def combo_rec(layer_, cosines, d_near, inside, scope_of, k):
    out = the_combo(layer_, cosines, d_near, inside, scope_of, k)
    captured.update(combo=out, inside=np.asarray(inside, dtype=np.int64))
    return out


WK.cloud_combo = combo_rec


def ties(combo, inside, start, rare, facet):
    """Per chunk: tied to a start chunk through a tag (rare ones only, if asked) with the same role on both edges (or any)."""
    member = np.zeros(n, dtype=bool)
    member[inside] = True
    by_tag, by_chunk = defaultdict(list), defaultdict(list)
    for e in np.flatnonzero(member[chunk_e]).tolist():
        by_tag[int(tag_e[e])].append(e)
        by_chunk[int(chunk_e[e])].append(e)
    sizes = {t: len(es) for t, es in by_tag.items() if len(es) > 1}
    small = set(sizes)
    if rare and len(set(sizes.values())) > 1:
        names = sorted(sizes)
        lv = WK.levels(np.log(np.array([sizes[t] for t in names], dtype=np.float64)), 2)
        small = {t for t, level in zip(names, lv.tolist()) if level == lv.max()}
    roles = {}

    def role(t):
        if t not in roles:
            es = np.array(by_tag[t])
            ranks = np.column_stack([rankdata(-place[es, f]) for f in range(place.shape[1])])
            roles[t] = dict(zip(es.tolist(), np.argmin(ranks, axis=1).tolist()))
        return roles[t]

    tied = np.zeros(n, dtype=bool)
    for h in start:
        for e1 in by_chunk.get(h, []):
            t = int(tag_e[e1])
            if t not in small:
                continue
            r = role(t) if facet else None
            for e2 in by_tag[t]:
                c = int(chunk_e[e2])
                if c != h and (not facet or r[e2] == r[e1]):
                    tied[c] = True
    return tied


def score(id_lists, context_ids, cites):
    got = {str(x) for x in context_ids}
    whole = [u for u in ([str(x) for x in unit] for unit in id_lists if unit) if set(u) <= got]
    return bool(whole and set(whole[0]) & cites), len(cites & got) / len(cites)


rows_q = []
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    os.environ["HERB_V4_SCOPE_STEP"] = "combo"             # the order without ties: the combo's, handed over as the step does
    V.answer_one_question((qid, q.question), p, None, 50, BUDGET)
    os.environ.pop("HERB_V4_SCOPE_STEP", None)
    rows_q.append({"cites": cites, "combo": captured["combo"], "inside": captured["inside"]})
WK.cloud_combo = the_combo

cache = {}
STARTS, LIFTS, TAGS = ("the strongest hits", "the top chunk"), ("inside the step after scope", "inside the step before scope", "one step up"), ("every tag", "rare tags")
results = defaultdict(list)
moved = defaultdict(lambda: [0, 0, 0, 0])            # in, in cited, out, out cited
for r in rows_q:
    combo, inside, cites = r["combo"], r["inside"], r["cites"]
    gold = {c for c in inside.tolist() if cites & records[c]}
    step, in_scope, value = combo["step"], combo["in_scope"], combo["value"]
    _, ids0, ctx0, _, dl0, _ = V._hand_over(combo["order"], p, BUDGET, 50, cache)
    base = score(ids0, ctx0, cites)
    results["the arm without ties"].append(base)
    lowest = int(step[inside].min())
    strongest = [c for c in combo["order"] if step[c] <= max(3, lowest)]
    for start_name, lift, tags, facet in grid(STARTS, LIFTS, TAGS, (True, False)):
        start = strongest if start_name == STARTS[0] else combo["order"][:1]
        tied = ties(combo, inside, start, tags == TAGS[1], facet)
        s = step[inside].astype(np.int64) - (tied[inside] if lift == LIFTS[2] else 0)
        if lift == LIFTS[1]:
            keys = (id_rank[inside], -value[inside], ~in_scope[inside], ~tied[inside], s)
        else:
            keys = (id_rank[inside], -value[inside], ~tied[inside], ~in_scope[inside], s)
        order = inside[np.lexsort(keys)].tolist()
        _, ids, ctx, _, dl, _ = V._hand_over(order, p, BUDGET, 50, cache)
        label = f"{'facet' if facet else 'any tag'} | {start_name} | {lift} | {tags}"
        results[label].append(score(ids, ctx, cites))
        came, went = set(dl) - set(dl0), set(dl0) - set(dl)
        m = moved[label]
        m[0] += len(came)
        m[1] += len(came & gold)
        m[2] += len(went)
        m[3] += len(went & gold)

count = len(rows_q)
base = np.array([x[1] for x in results["the arm without ties"]])
print(f"\nthe arm without ties: top text {sum(x[0] for x in results['the arm without ties'])}, context_recall_id {base.mean():.4f}")
print("variant: top text | context_recall_id (difference, standard error, up / down) | moved into the 72,000 a question, cited | moved out, cited")
for label in sorted(k for k in results if k != "the arm without ties"):
    a = np.array(results[label], dtype=np.float64)
    diff = a[:, 1] - base
    m = moved[label]
    print(f"  {label:78s}: {int(a[:, 0].sum()):3d} | {a[:, 1].mean():.4f} ({diff.mean():+.3f}, {diff.std(ddof=1) / np.sqrt(count):.3f}, "
          f"{int((diff > 1e-9).sum())}/{int((diff < -1e-9).sum())}) | in {m[0] / count:.1f}, {m[1] / max(m[0], 1):.0%} | out {m[2] / count:.1f}, "
          f"{m[3] / max(m[2], 1):.0%}")
print("done", flush=True)

"""His 2026-10-15 "how the fuck can this not be relevant, and how do you mean it already holds it..
are those chunks always floated up you mean?" Where the chunks the same-role tag links reach
(from the arm's delivered chunks, not delivered themselves) stand in the arm's own order, and
whether the arm's order inside them picks the cited ones.

The arm as it stands (persons step), the hundred, cached first calls, no lane call. A tag's role
on an edge: the facet the edge stands highest in. Printed per question on average: the chunks
holding a cited record inside the border, how many are delivered, how many are missed, how many
of the missed the same-role links reach; the reached chunks by the arm's step (the description
side's and the tags' side's levels added, 2 the best), how many a question and how often cited;
the reached chunks taken in the arm's own order, the first one, three and five of them: how often
cited. The gold ids are read inside; numbers only.
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
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

BUDGET = 72000
wanted = [json.loads(line)["id"] for line in (REPO / "data" / "gold100.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("where the role links reach")
layer, n = p.layer, len(p.chunk_ids)
tag_e, chunk_e = layer["edge_tag"], layer["edge_chunk"]
role = np.argmax(layer["pos"][:, 1:], axis=1)
edges_of_chunk, edges_of_tag = defaultdict(list), defaultdict(list)
for k, (t, c) in enumerate(zip(tag_e.tolist(), chunk_e.tolist())):
    edges_of_chunk[c].append(k)
    edges_of_tag[t].append(k)
doc_cache = {}
records = [{str(x) for x in _resolve_chunk(row, doc_cache)[1]} for row in p.chunk_rows]
print("prepared", flush=True)

captured = {}
the_combo, the_hand = WK.cloud_combo, V._hand_over


def combo_rec(layer_, cosines, d_near, inside, scope_of, k):
    out = the_combo(layer_, cosines, d_near, inside, scope_of, k)
    captured["combo"], captured["inside"] = out, np.asarray(inside, dtype=np.int64)
    return out


def hand_rec(order, prepared, char_budget, k, cache):
    out = the_hand(order, prepared, char_budget, k, cache)
    captured["delivered"] = list(out[4])
    return out


WK.cloud_combo, V._hand_over = combo_rec, hand_rec
sums = defaultdict(float)
by_step = defaultdict(lambda: [0, 0])
first_k = defaultdict(lambda: [0, 0])
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    V.answer_one_question((qid, q.question), p, None, 50, BUDGET)
    combo, inside, delivered = captured["combo"], captured["inside"], set(captured["delivered"])
    member = np.zeros(n, dtype=bool)
    member[inside] = True
    gold = {i for i in inside.tolist() if cites & records[i]}
    reached = set()
    for s in delivered:
        for e1 in edges_of_chunk[s]:
            for e2 in edges_of_tag[int(tag_e[e1])]:
                c = int(chunk_e[e2])
                if member[c] and c not in delivered and role[e1] == role[e2]:
                    reached.add(c)
    missed = gold - delivered
    sums["cited chunks inside the border"] += len(gold)
    sums["of them delivered"] += len(gold & delivered)
    sums["of them missed"] += len(missed)
    sums["of the missed, reached by a same-role link"] += len(missed & reached)
    sums["chunks reached by a same-role link"] += len(reached)
    for c in reached:
        s = int(combo["step"][c])
        by_step[s][0] += 1
        by_step[s][1] += c in gold
    place = {c: at for at, c in enumerate(combo["order"])}
    ranked = sorted(reached, key=lambda c: place[c])
    for k in (1, 3, 5):
        first_k[k][0] += len(ranked[:k])
        first_k[k][1] += sum(1 for c in ranked[:k] if c in gold)
    the_delivered_cited = len(gold & delivered) / max(len(delivered), 1)
    sums["share of delivered chunks holding a cited record"] += the_delivered_cited
WK.cloud_combo, V._hand_over = the_combo, the_hand

count = len(wanted)
print("\nper question, on average:")
for key, value in sums.items():
    print(f"  {key}: {value / count:.2f}" if "share" in key else f"  {key}: {value / count:.1f}")
print("the reached chunks by the arm's step (2 is both sides' first cluster): how many a question | how often cited")
for s in sorted(by_step):
    print(f"  step {s:2d}: {by_step[s][0] / count:5.1f} | {by_step[s][1] / max(by_step[s][0], 1):.1%}")
print("the reached chunks in the arm's own order, the first ones: how often cited")
for k, (m, c) in first_k.items():
    print(f"  first {k}: {c / max(m, 1):.1%} ({m} chunks over the hundred)")
print("done", flush=True)

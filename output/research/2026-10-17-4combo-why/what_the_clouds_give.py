"""What the clouds give (his 2026-10-18 "dude, what are they GIVING us!? WHY do they exist!?"). The arm is run
over the hundred offline (no model call); for each question the same border, closeness and hand-over are kept and
three orders are handed over and scored by the citation ids (no question text printed):

  clouds        the clouds' order as the arm makes it before the 4-combo: the step (the two sides' cluster
                numbers added, k clusters each), then the scope's parents first, then the two standings added
  sum           the two standings added, nothing else (no clusters, no scope)
  sum, scope    the scope's parents first, then the two standings added (no clusters)

    .venv/Scripts/python.exe output/research/2026-10-17-4combo-why/what_the_clouds_give.py
"""
import json
import os
import sys
import threading
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"

from arms import artefact_v4 as V  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

p = V.prepare_over_corpus("what the clouds give")
wanted = [json.loads(line)["id"] for line in (REPO / "data/gold100.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
seen = {}
real_combo = WK.cloud_combo


def watched_combo(layer, cosines, d_near, inside, scope_of, k, tags_near=None):
    out = real_combo(layer, cosines, d_near, inside, scope_of, k, tags_near=tags_near)
    seen[threading.get_ident()] = (np.asarray(inside), out, layer)
    return out


WK.cloud_combo = watched_combo
WK.storyline_order = lambda combo_order, start, strength: list(combo_order)   # the clouds' order as it is
V._storyline_pairs = lambda chosen, chunks: []
results = {}


def one(qid):
    q = by_id[qid]
    V.answer_one_question((qid, q.question), p, None, 50, 72000)
    inside, combo, layer = seen.pop(threading.get_ident())
    value, in_scope, rank = combo["value"], combo["in_scope"], layer["id_rank"]
    orders = {
        "clouds": list(combo["order"]),
        "sum": inside[np.lexsort((rank[inside], -value[inside]))].tolist(),
        "sum, scope": inside[np.lexsort((rank[inside], -value[inside], ~in_scope[inside]))].tolist(),
    }
    cites = {str(c) for c in q.citations}
    got = {}
    for name, order in orders.items():
        context_ids = V._hand_over(order, p, 72000, 50, {})[2]
        got[name] = len(set(map(str, context_ids)) & cites) / len(cites) if cites else 0.
    results[qid] = got


with ThreadPoolExecutor(6) as pool:
    list(pool.map(one, wanted))
names = ("clouds", "sum", "sum, scope")
print("context_recall_id over the hundred, the same border, closeness and hand-over:")
for name in names:
    print(f"   {name}: {np.mean([r[name] for r in results.values()]):.4f}")
for a, b in (("clouds", "sum"), ("clouds", "sum, scope")):
    up = sum(r[a] > r[b] for r in results.values())
    down = sum(r[a] < r[b] for r in results.values())
    print(f"   {a} against {b}: higher on {up} questions, lower on {down}, the same on {len(results) - up - down}")

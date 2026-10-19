"""What each part of the arm does (his 2026-10-18 "what is built now then, finding those fucking clusters made
me doubt the entire fucking thing"). The arm is run over the hundred offline (no model call); per question the
same first call, closeness and graph are kept, and the delivery is made with one part taken out at a time, each
scored by context_recall_id from the citation ids (no question text printed):

  the arm                    as it stands
  without the 4-combo        the clouds' order as it is
  without the clouds         the two sides' standings added, nothing else
  tags side alone            each chunk's closest tag to a query tag, nothing else
  description side alone     each chunk's description against the question without the names, nothing else
  without the border         the two sides' standings added over every chunk of the pool (the question as asked)
  without the hand-over      the arm's order, every chunk handed over as it is
  without the facets         the clouds' order made from the plain closeness instead of the facet-weighted one

    .venv/Scripts/python.exe output/research/2026-10-18-is-something-off/what_each_part_does.py
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
from arms.artefact_v2 import _budget_contexts  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

p = V.prepare_over_corpus("what each part does")
wanted = [json.loads(line)["id"] for line in (REPO / "data/gold100.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
seen = {}
real_combo, real_order, real_cosines = WK.cloud_combo, WK.storyline_order, V._query_cosines


def box():
    return seen.setdefault(threading.get_ident(), {"near": []})


def watched_cosines(*args, **kwargs):
    out = real_cosines(*args, **kwargs)
    if len(args) == 3 and not kwargs:          # the question as asked, then without the names
        box()["near"].append(np.asarray(out[0]["query_description_cosines"], dtype=np.float64))
    return out


def watched_combo(layer, cosines, d_near, inside, scope_of, tags_near=None):
    out = real_combo(layer, cosines, d_near, inside, scope_of, tags_near=tags_near)
    box().update(inside=np.asarray(inside), combo=out, cosines=np.asarray(cosines), d_bare=d_near,
                 scope_of=scope_of, dealt=tags_near)
    return out


def watched_order(combo_order, start, strength, region):
    out = real_order(combo_order, start, strength, region)
    box()["order"] = out
    return out


V._query_cosines, WK.cloud_combo, WK.storyline_order = watched_cosines, watched_combo, watched_order


def z(x, over):
    here = x[over]
    mid = np.median(here)
    spread = 1.4826 * np.median(np.abs(here - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


layer = p.layer
every = np.arange(len(p.chunk_ids))
results = {}


def one(qid):
    q = by_id[qid]
    V.answer_one_question((qid, q.question), p, None, 50, 72000)
    s = seen.pop(threading.get_ident())
    inside, combo, rank = s["inside"], s["combo"], layer["id_rank"]
    t_near, d_bare = s["dealt"], s["d_bare"]
    d_question = s["near"][0]
    by = lambda x, over: over[np.lexsort((rank[over], -x[over]))].tolist()  # noqa: E731
    plain, _ = WK.tags_nearness(layer, s["cosines"])
    no_facets = real_combo(layer, s["cosines"], d_bare, inside, s["scope_of"], tags_near=plain)
    orders = {
        "the arm": s["order"],
        "without the 4-combo": list(combo["order"]),
        "without the clouds": by(z(t_near, inside) + z(d_bare, inside), inside),
        "tags side alone": by(t_near, inside),
        "description side alone": by(d_bare, inside),
        "without the border": by(z(t_near, every) + z(d_question, every), every),
        "without the facets": list(no_facets["order"]),
    }
    cites = {str(c) for c in q.citations}
    got = {}
    for name, order in orders.items():
        ids = V._hand_over(order, p, 72000, 50, {})[2]
        got[name] = (len(set(map(str, ids)) & cites) / len(cites), set(map(str, ids)))
    ids = _budget_contexts([p.chunk_rows[i] for i in s["order"]], 72000, {})[2]
    got["without the hand-over"] = (len(set(map(str, ids)) & cites) / len(cites), set(map(str, ids)))
    results[qid] = got


with ThreadPoolExecutor(6) as pool:
    list(pool.map(one, wanted))
names = ["the arm", "without the 4-combo", "without the clouds", "tags side alone", "description side alone",
         "without the border", "without the hand-over", "without the facets"]
print("context_recall_id over the hundred | questions delivered differently from the arm")
for name in names:
    score = np.mean([r[name][0] for r in results.values()])
    changed = sum(r[name][1] != r["the arm"][1] for r in results.values())
    print(f"   {name}: {score:.4f} | {changed}")

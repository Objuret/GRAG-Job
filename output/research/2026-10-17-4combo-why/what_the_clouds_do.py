"""What the clouds do that the plain sum of the two sides does not (his 2026-10-18 "apparently they DO something
then, what and why"). The arm is run over the hundred offline (no model call). Per question, the chunks handed
over by the clouds' order and not by the plain sum, and the other way round: how often they hold a cited record
(citation ids only), their cluster on each side, and their standing on each side (closeness less its middle over
its spread, over the border).

    .venv/Scripts/python.exe output/research/2026-10-17-4combo-why/what_the_clouds_do.py
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
from arms.artefact_v2 import _load_verified_doc  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

p = V.prepare_over_corpus("what the clouds do")
docs, records = {}, []
for row in p.chunk_rows:
    loc = json.loads(row["locator"])
    arr = _load_verified_doc(row["relpath"], row["sha256"], docs)[loc["section"]]
    records.append({str(arr[k]["id"]) for k in (loc["indices"] if "indices" in loc else [loc["index"]])
                    if arr[k].get("id") is not None})
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
WK.storyline_order = lambda combo_order, start, strength: list(combo_order)
V._storyline_pairs = lambda chosen, chunks: []
rows = {"clouds only": [], "sum only": [], "both": []}


def standing(x, inside):
    here = x[inside]
    mid = np.median(here)
    spread = 1.4826 * np.median(np.abs(here - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


def one(qid):
    q = by_id[qid]
    V.answer_one_question((qid, q.question), p, None, 50, 72000)
    inside, combo, layer = seen.pop(threading.get_ident())
    rank = layer["id_rank"]
    sum_order = inside[np.lexsort((rank[inside], -combo["value"][inside]))].tolist()
    a = set(V._hand_over(list(combo["order"]), p, 72000, 50, {})[4])
    b = set(V._hand_over(sum_order, p, 72000, 50, {})[4])
    cites = {str(c) for c in q.citations}
    zt, zd = standing(combo["tags_nearness"], inside), standing(combo["description_nearness"], inside)
    for c in a | b:
        name = "both" if c in a and c in b else "clouds only" if c in a else "sum only"
        rows[name].append({"cited": bool(records[c] & cites), "lt": int(combo["level"]["tags"][c]),
                           "ld": int(combo["level"]["description"][c]), "zt": float(zt[c]), "zd": float(zd[c]),
                           "scope": bool(combo["in_scope"][c])})


with ThreadPoolExecutor(6) as pool:
    list(pool.map(one, wanted))
for name, rs in rows.items():
    n = len(rs)
    if not n:
        continue
    cited = sum(r["cited"] for r in rs)
    lt, ld = np.array([r["lt"] for r in rs]), np.array([r["ld"] for r in rs])
    zt, zd = np.array([r["zt"] for r in rs]), np.array([r["zd"] for r in rs])
    print(f"{name}: {n} chunks, holding a cited record {cited} ({100 * cited / n:.1f}%)")
    print(f"   cluster on the tags side, middle {np.median(lt):.0f}; on the description side, middle {np.median(ld):.0f}; "
          f"in both first two clusters {int(((lt <= 2) & (ld <= 2)).sum())} ({100 * ((lt <= 2) & (ld <= 2)).mean():.0f}%)")
    print(f"   standing on the tags side, middle {np.median(zt):.2f}; on the description side, middle {np.median(zd):.2f}; "
          f"one side above 2 and the other below 1: {int((((zt > 2) & (zd < 1)) | ((zd > 2) & (zt < 1))).sum())}")
    print(f"   under the scope's parents: {sum(r['scope'] for r in rs)} ({100 * np.mean([r['scope'] for r in rs]):.0f}%)")

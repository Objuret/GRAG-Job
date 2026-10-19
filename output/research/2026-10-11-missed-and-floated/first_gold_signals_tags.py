"""For his 2026-10-12 "if we use the chunk-cloud, see if you can find a way to combo or lift with the
tags": the tag side of the table, per question, for the chunks of the question's product: which
of the product's tags sits on which chunk (the edges), each query tag's closeness to each of
those tags, and the five values on each edge. Written beside the first table, outside the
repository. No model call.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/first_gold_signals_tags.py gold100 <folder>
"""
import json
import os
import pickle
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
os.environ["HERB_V4_SCOPE_STEP"] = "both"

from arms import artefact_v4 as V  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
OUT = Path(sys.argv[2])
CACHE = REPO / "output/private/artefact_v4_cache/querytag"

with open(OUT / f"first_gold_signals__{SET}.pkl", "rb") as handle:
    first = pickle.load(handle)["questions"]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("first gold signals, the tag side")
layer, n = p.layer, len(p.chunk_ids)
et, ec, raw = layer["edge_tag"], layer["edge_chunk"], layer["raw"]
print("prepared", flush=True)


def cached_sides():
    out = []
    for f in CACHE.glob("*.json"):
        if f.name.endswith(".started.json"):
            continue
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        got = j.get("raw")
        if j.get("ok") and isinstance(got, dict) and got.get("description") and got.get("tags"):
            out.append((f.stat().st_mtime, (j.get("signature") or {}).get("user") or "", got))
    return sorted(out, key=lambda row: -row[0])


SIDES = cached_sides()


def side_of(q):
    def names(rows):
        return list(dict.fromkeys(str(r["t"]).strip() for r in rows or []
                                  if isinstance(r, dict) and str(r.get("t", "")).strip()))
    for _, user, got in SIDES:
        if q.question in user:
            return str(got["description"]), names(got.get("tags")), names(got.get("query_tags"))
    raise SystemExit(f"no cached first call for {q.id}")


tags_side, done = {}, 0
for qid, d in first.items():
    q = by_id[qid]
    inside = d["chunks"]
    local = np.full(n, -1, dtype=np.int64)
    local[inside] = np.arange(inside.size)
    description, tags, asked = side_of(q)
    rows = list(V._tag_cosines(description, tags, p)[0]["tags"])
    if asked:
        rows += list(V._tag_cosines(description, asked, p)[0]["tags"])
    rows = np.array(rows, dtype=np.float64)
    on = np.flatnonzero(local[ec] >= 0)
    product_tags, edge_tag_local = np.unique(et[on], return_inverse=True)
    tags_side[qid] = {
        "edge_chunk": local[ec[on]].astype(np.int32), "edge_tag": edge_tag_local.astype(np.int32),
        "edge_values": raw[on].astype(np.float32), "tag_fit": rows[:, product_tags].astype(np.float32),
        "tags_in_product": int(product_tags.size),
    }
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)
with open(OUT / f"first_gold_signals_tags__{SET}.pkl", "wb") as handle:
    pickle.dump(tags_side, handle)
print(f"{SET}: {len(tags_side)} questions written")
print("done", flush=True)

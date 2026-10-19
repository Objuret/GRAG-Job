"""Round 32, his 2026-10-12 "wait. thats pretty bad placement" (on the gold a side touches standing at
places 26 to 38): where the gold of each group stands under different orders, to see what puts
it there. The groups are those of round 31 (touched by both; by the tags only; by the
descriptions only; by neither), inside the question's product, the hundred.

Orders: the tags alone; the chunk descriptions against the query description alone; against the
question alone; the three added (the stand-in used so far: the descriptions count twice in it);
tags and description added (once each); and the arm's own order from its runs (today's arm with
the name border; the old arm of 2026-10-06). Printed: the middle place of the group's gold
chunks (quarters) in each order, and how many of a question's gold chunks each order puts in the
first 15."""
import json
import pickle
import sys
from pathlib import Path

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

from explore import load, standing  # noqa: E402

HERE = Path(__file__).resolve().parent
RUNS = Path(r"C:\Coding\exjobbet\GRAG-Job\output\k=chars")
Q = load()["questions"]
with open(HERE / "first_gold_signals_tags__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
for qid, d in Q.items():
    d.update(extra[qid])
with open(HERE / "what_a_chunk_holds.pkl", "rb") as handle:
    CHUNK_IDS = pickle.load(handle)["chunk_ids"]
index_of = {str(c): k for k, c in enumerate(CHUNK_IDS)}
arm_orders = {}
for label, name in (("the arm's own order, today (name border)", "artefact_v4__gold100__cb72000__20261011T164246Z_name"),
                    ("the arm's own order, the old arm of 10-06", "artefact_v4__gold100__cb72000__20261006T184959Z")):
    rows = {}
    for line in (RUNS / name / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["id"]] = [index_of[str(c)] for c in ((row.get("meta") or {}).get("ranking") or {}).get("ordered_chunk_ids", [])
                               if str(c) in index_of]
    arm_orders[label] = rows
GROUPS = ("touched by both", "by the tags only", "by the descriptions only", "by neither")
ORDERS = ["the tags alone", "the chunk descriptions against the query description alone",
          "the chunk descriptions against the question alone", "the three added (descriptions count twice)",
          "tags + description, once each"] + list(arm_orders)
where = {o: {g: [] for g in GROUPS} for o in ORDERS}
top15 = {o: [] for o in ORDERS}
for qid, d in Q.items():
    gold, m = d["gold"], d["gold"].size
    fit = d["tag_fit"].astype(np.float64)
    kth = np.sort(fit, axis=1)[:, ::-1][:, min(5, fit.shape[1]) - 1]
    picked = (fit >= kth[:, None] - 1e-12).any(axis=0)
    by_tags = np.zeros(m, dtype=bool)
    by_tags[d["edge_chunk"][picked[d["edge_tag"]]]] = True
    by_desc = WK.levels(np.asarray(d["description"], dtype=np.float64), 5) <= 2
    groups = {GROUPS[0]: by_tags & by_desc, GROUPS[1]: by_tags & ~by_desc, GROUPS[2]: ~by_tags & by_desc,
              GROUPS[3]: ~by_tags & ~by_desc}
    scores = {
        "the tags alone": d["tags"], "the chunk descriptions against the query description alone": d["description"],
        "the chunk descriptions against the question alone": d["question"],
        "the three added (descriptions count twice)": standing(d["tags"]) + standing(d["description"]) + standing(d["question"]),
        "tags + description, once each": standing(d["tags"]) + standing(d["description"]),
    }
    places = {}
    for name, score in scores.items():
        order = np.lexsort((d["id_rank"], -np.asarray(score, dtype=np.float64)))
        place = np.empty(m, dtype=np.int64)
        place[order] = np.arange(1, m + 1)
        places[name] = place
    local = {int(c): k for k, c in enumerate(d["chunks"].tolist())}
    for label, rows in arm_orders.items():
        inside = [local[c] for c in rows.get(qid, []) if c in local]
        place = np.full(m, m, dtype=np.int64)
        for k, c in enumerate(inside):
            place[c] = k + 1
        places[label] = place
    for name, place in places.items():
        top15[name].append(int((place[gold] <= 15).sum()))
        for g, mask in groups.items():
            where[name][g] += place[mask & gold].tolist()

print("the middle place of a group's gold chunks (quarters) in each order; the product has about 160 chunks, 15 fit")
print("  " + " | ".join(f"{g:>26s}" for g in GROUPS) + " | gold chunks in the first 15 (of 10)")
for name in ORDERS:
    cells = []
    for g in GROUPS:
        v = where[name][g]
        cells.append(f"{np.median(v):5.0f} ({np.percentile(v, 25):.0f}-{np.percentile(v, 75):.0f})".rjust(26))
    print("  " + " | ".join(cells) + f" | {np.mean(top15[name]):.1f}   {name}")

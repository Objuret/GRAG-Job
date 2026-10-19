"""Round 57, under his 2026-10-12 goal "solve this" (the order): every reading of the question against
the units lands at the same place (chunk descriptions and tags 0.653, whole-conversation vectors
0.644), and the cited conversations that are missed stand at place 37 of 119 by their own
nearness to the question (round 54). So the question itself is what runs short. Here the
question is widened by what it finds first: the middle of the first of five clusters of the
conversations' own nearness is added to the question's vector, and the units are read against
that (the published "pseudo-relevance feedback"; no number given beyond his five clusters).
VECTORS names the file of conversation vectors. The hundred, numbers only.

  U2   every unit by its own nearness to the question alone (round 53)
  F1   every unit by its nearness to the question plus the middle of the first cluster
  F2   the same, the first cluster taken from the units the combo order as built puts first
       (as many conversations as its first cluster holds)
  F3   U2's standing and F1's standing added
"""
import json
import os
import pickle
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

import ties as TI  # noqa: E402
from explore import BUDGET, load, standing  # noqa: E402

HERE = Path(__file__).resolve().parent
OWN = Path(r"C:\Coding\exjobbet\GRAG-Job\output\research\2026-10-11-missed-and-floated\own_units")
T = load()
Q, KINDS = T["questions"], T["kind_names"]
with open(HERE / "first_gold_signals_tags__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
PARTS = ("document_part", "meeting_transcript_part")
rows = [json.loads(line) for line in open(OWN / "own_units.jsonl", encoding="utf-8")]
matrix = np.asarray(np.load(OWN / os.environ.get("VECTORS", "own_units_query.npz"), allow_pickle=True)["matrix"], dtype=np.float32)
unit_of_record = {}
for at, row in enumerate(rows):
    for r in row["records"]:
        unit_of_record[r] = at


def hand_over(units, cited, cites):
    used, got, first = 0, set(), None
    for records, chars, part in units:
        new = [r for r in records if r not in got]
        if not new and not part:
            continue
        if used + chars > BUDGET:
            break
        used += chars
        got.update(records)
        if first is None:
            first = bool(cited & set(records))
    return bool(first), len(cited & got) / cites


def length_of(records, P):
    return sum(P["size"][r] for r in records) + max(len(records) - 1, 0)


def unit(v):
    return v / max(float(np.linalg.norm(v)), 1e-12)


results = defaultdict(list)
for qid, d in Q.items():
    d.update(extra[qid])
    P = TI.product(qid.split("::")[0])
    m = d["gold"].size
    D, Tg = np.asarray(d["question_bare"], dtype=np.float64), np.asarray(d["tags"], dtype=np.float64)
    step = (WK.levels(D, 5) + WK.levels(Tg, 5)).astype(np.float64)
    z = standing(D) + standing(Tg)
    hits = step <= 3 if (step <= 3).any() else step == step.min()
    ids = np.unique(d["parent"])
    held = np.array([int(hits[d["parent"] == a].sum()) for a in ids])
    total, last = 0, None
    for at in np.lexsort((ids, -held)):
        total += int(held[at])
        last = int(held[at])
        if total * 2 > int(held.sum()):
            break
    scope = np.isin(d["parent"], ids[held >= last])
    order = np.lexsort((d["id_rank"], -z, ~scope, step))
    place = np.empty(m, dtype=np.int64)
    place[order] = np.arange(m)
    cited, cites = set(d["cited_ids"]), d["cites"]
    kind = [KINDS[x] for x in d["kind"]]
    own = [[r for r in d["records"][k] if not TI.apart(r, P)] for k in range(m)]
    chunk_len = d["length"].astype(np.int64)
    bare = np.asarray(d["bare_vector"], dtype=np.float64)
    chunk_vectors = np.asarray(d["chunk_vectors"], dtype=np.float64)
    units, by_unit, vectors = [], {}, []
    for k in sorted(range(m), key=lambda k: (int(d["parent"][k]), int(d["id_rank"][k]))):
        if kind[k] in ("slack_thread_batch", "pr_batch"):
            for r in own[k]:
                u = unit_of_record[r]
                if u not in by_unit:
                    by_unit[u] = len(units)
                    units.append([list(rows[u]["records"]), None, False, k, True])
                    vectors.append(np.asarray(matrix[u], dtype=np.float64))
                elif place[k] < place[units[by_unit[u]][3]]:
                    units[by_unit[u]][3] = k
        elif own[k]:
            size = int(chunk_len[k]) if kind[k] in PARTS or len(own[k]) == len(d["records"][k]) else length_of(own[k], P)
            units.append([own[k], size, kind[k] in PARTS, k, False])
            vectors.append(chunk_vectors[k])
    for u in units:
        if u[1] is None:
            u[1] = length_of(u[0], P)
    V = np.stack(vectors)
    talk = np.array([u[4] for u in units])
    best = np.array([u[3] for u in units])
    near = V @ bare
    spot = np.arange(len(units))
    send = lambda by: hand_over(((units[i][0], units[i][1], units[i][2]) for i in by.tolist()), cited, cites)  # noqa: E731
    results["U2  every unit by its own nearness to the question alone"].append(send(np.lexsort((spot, -near))))
    level = np.full(len(units), 9)
    level[talk] = WK.levels(near[talk], 5)
    first_cluster = np.flatnonzero(level == 1)
    wide = unit(bare + unit(V[first_cluster].mean(axis=0)))
    near_wide = V @ wide
    results["F1  by nearness to the question plus the middle of its first cluster"].append(send(np.lexsort((spot, -near_wide))))
    front = np.lexsort((spot, place[best]))
    front = front[talk[front]][:max(first_cluster.size, 1)]
    wide2 = unit(bare + unit(V[front].mean(axis=0)))
    results["F2  the same, the first cluster taken from what the combo order puts first"].append(send(np.lexsort((spot, -(V @ wide2)))))
    results["F3  U2's standing and F1's standing added"].append(send(np.lexsort((spot, -(standing(near) + standing(near_wide))))))

print("first handed over holds a cited record (of 100) | context_recall_id")
base = np.array([r[1] for r in results["U2  every unit by its own nearness to the question alone"]])
for name, got in results.items():
    a = np.array(got, dtype=np.float64)
    diff = a[:, 1] - base
    print(f"  {int(a[:, 0].sum()):3d} | {a[:, 1].mean():.3f}  {name}"
          + ("" if name.startswith("U2") else f"   [{diff.mean():+.3f}, standard error {diff.std(ddof=1) / 10:.3f}, higher on "
             f"{int((diff > 1e-9).sum())}, lower on {int((diff < -1e-9).sum())}]"))

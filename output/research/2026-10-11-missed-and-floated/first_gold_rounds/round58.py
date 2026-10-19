"""Round 58, under his 2026-10-12 goal "solve this" (the order): the question widened by what it
finds first gave 0.705 with whole-conversation vectors (round 57). Does the same work with what
the graph already holds, the chunk descriptions' vectors, so that no new vectors are needed?
The hundred, the records that are not the product's own work left out, whole own conversations
handed over as their chunks show; numbers only.

  C    the combo order as built
  G1   the chunks by their description's nearness to the question plus the middle of the
       descriptions of the chunks C puts first (as many as the description side's first of five
       clusters holds)
  G2   the combo made again with that widened nearness as the description side (tags' side and
       scope as built)
  G3   C's first chunks (the same ones) first in C's order, then the rest by G1
  G4   G2, the middle taken from the chunks of the combo's first two steps
"""
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
T = load()
Q, KINDS = T["questions"], T["kind_names"]
with open(HERE / "first_gold_signals_tags__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
PARTS = ("document_part", "meeting_transcript_part")


def unit(v):
    return v / max(float(np.linalg.norm(v)), 1e-12)


def majority(hits, parent):
    ids = np.unique(parent)
    held = np.array([int(hits[parent == a].sum()) for a in ids])
    total, last = 0, None
    for at in np.lexsort((ids, -held)):
        total += int(held[at])
        last = int(held[at])
        if total * 2 > int(held.sum()):
            break
    return np.isin(parent, ids[held >= last])


def length_of(records, P):
    return sum(P["size"][r] for r in records) + max(len(records) - 1, 0)


results = defaultdict(list)
for qid, d in Q.items():
    d.update(extra[qid])
    P = TI.product(qid.split("::")[0])
    m = d["gold"].size
    cited, cites = set(d["cited_ids"]), d["cites"]
    kind = [KINDS[x] for x in d["kind"]]
    own = [[r for r in d["records"][k] if not TI.apart(r, P)] for k in range(m)]
    has_own = np.array([bool(o) for o in own])
    chunk_len = d["length"].astype(np.int64)
    CVq = np.asarray(d["chunk_vectors"], dtype=np.float64)
    bare = np.asarray(d["bare_vector"], dtype=np.float64)
    D, Tg = np.asarray(d["question_bare"], dtype=np.float64), np.asarray(d["tags"], dtype=np.float64)
    lD, lT = WK.levels(D, 5), WK.levels(Tg, 5)
    step = (lD + lT).astype(np.float64)
    z = standing(D) + standing(Tg)
    hits = step <= 3 if (step <= 3).any() else step == step.min()
    scope = majority(hits, d["parent"])
    order = np.lexsort((d["id_rank"], -z, ~scope, step))
    talk_records = defaultdict(list)
    for k in sorted(range(m), key=lambda k: (int(d["parent"][k]), int(d["id_rank"][k]))):
        if kind[k] == "slack_thread_batch":
            for r in own[k]:
                talk_records[P["talk_of"][r]].append(r)

    def send(by):
        used, got, first, seen, sent = 0, set(), None, set(), set()
        for k in by.tolist():
            if not own[k]:
                continue
            if kind[k] != "slack_thread_batch":
                records = own[k]
                size = int(chunk_len[k]) if kind[k] in PARTS or len(own[k]) == len(d["records"][k]) else length_of(own[k], P)
                if kind[k] not in PARTS and not [r for r in records if r not in got]:
                    continue
            else:
                here = [t for t in dict.fromkeys(P["talk_of"][r] for r in own[k]) if t not in seen]
                records = [r for t in here for r in talk_records[t] if r not in sent]
                if not records:
                    continue
                size = length_of(records, P)
            if used + size > BUDGET:
                break
            used += size
            if kind[k] == "slack_thread_batch":
                seen.update(here)
                sent.update(records)
            got.update(records)
            if first is None:
                first = bool(cited & set(records))
        return bool(first), len(cited & got) / cites

    results["C   the combo order as built"].append(send(order))
    many = max(int((lD == 1).sum()), 1)
    front = order[has_own[order]][:many]
    wide = unit(bare + unit(CVq[front].mean(axis=0)))
    D2 = CVq @ wide
    results["G1  the chunks by their description's nearness to the widened question"].append(send(np.lexsort((d["id_rank"], -D2))))
    step2 = (WK.levels(D2, 5) + lT).astype(np.float64)
    z2 = standing(D2) + standing(Tg)
    hits2 = step2 <= 3 if (step2 <= 3).any() else step2 == step2.min()
    scope2 = majority(hits2, d["parent"])
    results["G2  the combo made again with the widened nearness as the description side"].append(
        send(np.lexsort((d["id_rank"], -z2, ~scope2, step2))))
    first = np.zeros(m, dtype=bool)
    first[front] = True
    place = np.empty(m, dtype=np.int64)
    place[order] = np.arange(m)
    results["G3  C's first chunks first in C's order, then the rest by G1"].append(
        send(np.lexsort((d["id_rank"], np.where(first, place, 0), -np.where(first, 0., D2), ~first))))
    seeds = np.flatnonzero(hits & has_own)
    wide3 = unit(bare + unit(CVq[seeds].mean(axis=0))) if seeds.size else bare
    D3 = CVq @ wide3
    step3 = (WK.levels(D3, 5) + lT).astype(np.float64)
    z3 = standing(D3) + standing(Tg)
    hits3 = step3 <= 3 if (step3 <= 3).any() else step3 == step3.min()
    results["G4  G2, the middle taken from the chunks of the combo's first two steps"].append(
        send(np.lexsort((d["id_rank"], -z3, ~majority(hits3, d["parent"]), step3))))

print("first handed over holds a cited record (of 100) | context_recall_id")
base = np.array([r[1] for r in results["C   the combo order as built"]])
for name, got in results.items():
    a = np.array(got, dtype=np.float64)
    diff = a[:, 1] - base
    print(f"  {int(a[:, 0].sum()):3d} | {a[:, 1].mean():.3f}  {name}"
          + ("" if name.startswith("C  ") else f"   [{diff.mean():+.3f}, standard error {diff.std(ddof=1) / 10:.3f}, higher on "
             f"{int((diff > 1e-9).sum())}, lower on {int((diff < -1e-9).sum())}]"))

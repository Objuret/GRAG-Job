"""Round 62, under his 2026-10-12 goal "solve this" (the order): the tags' side takes a chunk's closest
query tag on one scale for all query tags, so the query tags that match many chunks word for
word fill its first cluster. A question that needs several different things would want each
query tag to bring its own chunks. Tried here: every query tag ranks the chunks by itself, and
the lists are taken in turn. The hundred, the first call's query tags as the run has them, the
records that are not the product's own work left out, whole own conversations; numbers only.

  C    the combo order as built
  R1   the tags' side by a chunk's best PLACE over the query tags (each query tag's own list),
       in place of its closest value; the combo otherwise as built
  R2   in turn: the description side's list, then each query tag's list, one chunk from each,
       round after round
  R3   C's first step (both sides in their first cluster) first, then R2
  R4   the query tags cut into clusters by how alike their lists are is not done here: each
       query tag is its own list (the finest cut); R4 is R2 over the query tags' lists only,
       after the chunks of the combo's first two steps
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


def length_of(records, P):
    return sum(P["size"][r] for r in records) + max(len(records) - 1, 0)


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


def in_turn(lists, m):
    out, seen = [], set()
    for rank in range(m):
        for one in lists:
            k = int(one[rank])
            if k not in seen:
                seen.add(k)
                out.append(k)
    return np.array(out, dtype=np.int64)


results = defaultdict(list)
for qid, d in Q.items():
    d.update(extra[qid])
    P = TI.product(qid.split("::")[0])
    m = d["gold"].size
    cited, cites = set(d["cited_ids"]), d["cites"]
    kind = [KINDS[x] for x in d["kind"]]
    own = [[r for r in d["records"][k] if not TI.apart(r, P)] for k in range(m)]
    chunk_len = d["length"].astype(np.int64)
    D, Tg = np.asarray(d["question_bare"], dtype=np.float64), np.asarray(d["tags"], dtype=np.float64)
    fit = np.asarray(d["fit"], dtype=np.float64)                 # query tags x chunks: the chunk's closest tag to that query tag
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
    lists = [np.lexsort((d["id_rank"], -row)) for row in fit]
    place = np.empty((len(lists), m), dtype=np.int64)
    for a, one in enumerate(lists):
        place[a, one] = np.arange(m)
    best_place = place.min(axis=0).astype(np.float64)
    T2 = -np.log1p(best_place)
    step2 = (lD + WK.levels(T2, 5)).astype(np.float64)
    z2 = standing(D) + standing(T2)
    hits2 = step2 <= 3 if (step2 <= 3).any() else step2 == step2.min()
    results["R1  the tags' side by a chunk's best place over the query tags"].append(
        send(np.lexsort((d["id_rank"], -z2, ~majority(hits2, d["parent"]), step2))))
    by_description = np.lexsort((d["id_rank"], -D))
    turn = in_turn([by_description] + lists, m)
    results["R2  in turn: the description side's list and each query tag's list"].append(send(turn))
    first_step = order[step[order] == step.min()]
    rest = np.array([k for k in turn.tolist() if k not in set(first_step.tolist())], dtype=np.int64)
    results["R3  the combo's first step first, then R2"].append(send(np.concatenate([first_step, rest])))
    two = order[hits[order]]
    tags_turn = in_turn(lists, m)
    rest = np.array([k for k in tags_turn.tolist() if k not in set(two.tolist())], dtype=np.int64)
    results["R4  the combo's first two steps first, then each query tag's list in turn"].append(send(np.concatenate([two, rest])))

print("first handed over holds a cited record (of 100) | context_recall_id")
base = np.array([r[1] for r in results["C   the combo order as built"]])
for name, got in results.items():
    a = np.array(got, dtype=np.float64)
    diff = a[:, 1] - base
    print(f"  {int(a[:, 0].sum()):3d} | {a[:, 1].mean():.3f}  {name}"
          + ("" if name.startswith("C  ") else f"   [{diff.mean():+.3f}, standard error {diff.std(ddof=1) / 10:.3f}, higher on "
             f"{int((diff > 1e-9).sum())}, lower on {int((diff < -1e-9).sum())}]"))

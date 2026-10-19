"""Round 42, under his 2026-10-12 goal "solve this": the order of the units once the records that are
not the product's own work are out and a talk is handed over whole (round 40: 0.650). The chunk's
description and tags are written over a batch that mixes talks, so they cannot say which talk of
the batch is meant. What can: the talk's own messages. The only vectors of single messages that
exist are the vector baseline's record vectors (`output/embed_local/...`), so this is a side
count for him to weigh, not the artefact's own information. The hundred, inside the question's
product, the question without the product's name, numbers only.

Units: an own talk whole; any other chunk without the records that are not the product's own.
A unit's value by its messages: the mean of its two closest records to the question.

  O1  the combo order as built, units as they first show (C of round 40)
  O2  the units by their messages alone
  O3  the unit's standing in the combo (the two values added, of its best chunk) and its
      standing by its messages, added
  O4  the combo's step and scope of its best chunk first, then O3 inside
  O5  O1, but the talks of one chunk in the order of their messages' value (the chunk order kept)
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
KEPT = Path(r"C:\Coding\exjobbet\GRAG-Job\output\embed_local\20261007_rev113abe4acafa_float32")
T = load()
Q, KINDS = T["questions"], T["kind_names"]
with open(HERE / "first_gold_signals_tags__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
for qid, d in Q.items():
    d.update(extra[qid])
PARTS = ("document_part", "meeting_transcript_part")
corpus = np.load(KEPT / "corpus_passage.npz", allow_pickle=True)
row_of = {str(r): k for k, r in enumerate(corpus["ids"])}
matrix = np.asarray(corpus["matrix"], dtype=np.float32)


def hand_over(units, cited, cites):
    used, got, n, first = 0, set(), 0, None
    for records, chars, part in units:
        new = [r for r in records if r not in got]
        if not new and not part:
            continue
        if used + chars > BUDGET:
            break
        used += chars
        got.update(records)
        n += 1
        if first is None:
            first = bool(cited & set(records))
    return n, bool(first), len(cited & got) / cites


def length_of(records, P):
    return sum(P["size"][r] for r in records) + max(len(records) - 1, 0)


def two_closest(values):
    values = np.sort(np.asarray(values, dtype=np.float64))[::-1]
    return float(values[:2].mean()) if values.size else float("-inf")


results = defaultdict(list)
for qid, d in Q.items():
    P = TI.product(qid.split("::")[0])
    m = d["gold"].size
    D, Tg = np.asarray(d["question_bare"], dtype=np.float64), np.asarray(d["tags"], dtype=np.float64)
    step = WK.levels(D, 5) + WK.levels(Tg, 5)
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
    bare = np.asarray(d["bare_vector"], dtype=np.float32)
    near = {}
    for k in range(m):
        for r in own[k]:
            if r in row_of and r not in near:
                near[r] = float(matrix[row_of[r]] @ bare)

    def trimmed(k):
        if kind[k] in PARTS or len(own[k]) == len(d["records"][k]):
            return int(chunk_len[k])
        return length_of(own[k], P)

    talk_records, talk_chunks = defaultdict(list), defaultdict(list)
    for k in sorted(range(m), key=lambda k: (int(d["parent"][k]), int(d["id_rank"][k]))):
        if kind[k] == "slack_thread_batch":
            for r in own[k]:
                t = P["talk_of"][r]
                talk_records[t].append(r)
                if k not in talk_chunks[t]:
                    talk_chunks[t].append(k)
    # the units: (records, characters, part, best chunk, value by its messages)
    units = []
    for t, rs in talk_records.items():
        best = min(talk_chunks[t], key=lambda k: int(place[k]))
        units.append((rs, length_of(rs, P), False, best, two_closest([near[r] for r in rs if r in near])))
    for k in range(m):
        if kind[k] != "slack_thread_batch" and own[k]:
            units.append((own[k], trimmed(k), kind[k] in PARTS, k, two_closest([near[r] for r in own[k] if r in near])))
    best = np.array([u[3] for u in units])
    by_messages = np.array([u[4] for u in units])
    by_messages[~np.isfinite(by_messages)] = np.nanmin(by_messages[np.isfinite(by_messages)])
    spot = np.arange(len(units))
    send = lambda by: hand_over(((units[i][0], units[i][1], units[i][2]) for i in by.tolist()), cited, cites)  # noqa: E731
    results["O1  the combo order as built, units as they first show"].append(send(np.lexsort((spot, place[best]))))
    results["O2  the units by their messages alone"].append(send(np.lexsort((spot, -by_messages))))
    both = standing(z[best]) + standing(by_messages)
    results["O3  the unit's standing in the combo and its standing by its messages, added"].append(send(np.lexsort((spot, -both))))
    results["O4  the combo's step and scope of its best chunk first, then O3 inside"].append(
        send(np.lexsort((spot, -both, ~scope[best], step[best]))))
    results["O5  O1, the talks of one chunk in the order of their messages' value"].append(
        send(np.lexsort((spot, -by_messages, place[best]))))

print("units handed over, a question | first handed over holds a cited record (of 100) | context_recall_id")
base = np.array([r[2] for r in results["O1  the combo order as built, units as they first show"]])
for name, got in results.items():
    a = np.array(got, dtype=np.float64)
    diff = a[:, 2] - base
    print(f"  {a[:, 0].mean():5.1f} | {int(a[:, 1].sum()):3d} | {a[:, 2].mean():.3f}  {name}"
          + ("" if name.startswith("O1") else f"   [against O1: {diff.mean():+.3f}, standard error {diff.std(ddof=1) / 10:.3f}, "
             f"higher on {int((diff > 1e-9).sum())}, lower on {int((diff < -1e-9).sum())}]"))

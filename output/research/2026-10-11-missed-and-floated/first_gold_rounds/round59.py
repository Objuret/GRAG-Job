"""Round 59, under his 2026-10-12 goal "solve this" (the order): where the first unit is wrong, by the
stage of the work most of the question's cited records come from, and by how many conversations
the question cites. The hundred, the combo order as built with the records that are not the
product's own work left out and whole own conversations; numbers only.
"""
import pickle
import sys
from collections import Counter, defaultdict
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


by_stage = defaultdict(lambda: [0, 0, []])
by_count = defaultdict(lambda: [0, 0, []])
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
    cited, cites = set(d["cited_ids"]), d["cites"]
    kind = [KINDS[x] for x in d["kind"]]
    own = [[r for r in d["records"][k] if not TI.apart(r, P)] for k in range(m)]
    chunk_len = d["length"].astype(np.int64)
    talk_records = defaultdict(list)
    for k in sorted(range(m), key=lambda k: (int(d["parent"][k]), int(d["id_rank"][k]))):
        if kind[k] == "slack_thread_batch":
            for r in own[k]:
                talk_records[P["talk_of"][r]].append(r)
    used, got, first, seen, sent = 0, set(), None, set(), set()
    for k in order.tolist():
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
    recall = len(cited & got) / cites
    per = Counter(P["channel_of"][r].split("-")[0] for r in cited if r in P["channel_of"])
    stage = per.most_common(1)[0][0] if per else "no Slack message cited"
    n_talks = sum(1 for t, rs in talk_records.items() if cited & set(rs))
    for table, key in ((by_stage, stage), (by_count, "1 or 2" if n_talks <= 2 else "3 or 4" if n_talks <= 4 else "5 to 8" if n_talks <= 8 else "9 or more")):
        row = table[key]
        row[0] += 1
        row[1] += bool(first)
        row[2].append(recall)
print("by the stage most of the cited messages come from: questions | first unit holds a cited record | context_recall_id")
for key, (n, f, r) in sorted(by_stage.items(), key=lambda kv: -kv[1][0]):
    print(f"  {n:3d} | {f:3d} | {np.mean(r):.3f}  {key}")
print("by how many conversations the question cites: questions | first unit holds a cited record | context_recall_id")
for key in ("1 or 2", "3 or 4", "5 to 8", "9 or more"):
    if key in by_count:
        n, f, r = by_count[key]
        print(f"  {n:3d} | {f:3d} | {np.mean(r):.3f}  {key}")

"""Round 26: what the sure set's chunks that are NOT gold are. The sure set (round 22) is about 14
chunks a question, 29% gold, and it does not split into its gold chunks and the others
(round 25). Inside the question's product, the hundred.

  1  a sure chunk that is not gold, against the question's gold chunks of the sure set: is it
     right above or under one, in a conversation one is in, sharing a link with one, sharing a
     tag that sits on 2 to 4 chunks of the product with one; how near its description stands to
     the nearest of them. Beside it the same for a gold chunk of the sure set against the OTHER
     gold chunks of the sure set, and for a chunk of the rest that is not gold.
  2  is it a chunk some OTHER question of the benchmark cites (all 1,514 questions, this one
     left out)? For the gold chunks, the sure chunks that are not gold, and the chunks of the
     rest that are not gold.

The gold ids are read inside this script; it prints numbers only."""
import json
import pickle
import sys
from pathlib import Path

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

from explore import load  # noqa: E402

HERE = Path(__file__).resolve().parent
data = load()
Q = data["questions"]
for name in ("tags", "ties"):
    with open(HERE / f"first_gold_signals_{name}__gold100.pkl", "rb") as handle:
        extra = pickle.load(handle)
    for qid, d in Q.items():
        d.update(extra[qid])
every = HQ.load_questions()
cited_by = {}
for q in every:
    for c in q.citations or []:
        cited_by.setdefault(str(c), set()).add(q.id)


def majority(hits, areas):
    ids = np.unique(areas)
    held = np.array([int(hits[areas == a].sum()) for a in ids])
    if not held.sum():
        return np.ones(areas.size, dtype=bool)
    taken, total = [], 0
    for k in np.lexsort((ids, -held)):
        taken.append(ids[k])
        total += held[k]
        if total * 2 > held.sum():
            break
    return np.isin(areas, taken)


GROUPS = ("a sure chunk that is not gold", "a gold chunk of the sure set", "a chunk of the rest that is not gold")
ties = {g: {} for g in GROUPS}
near = {g: [] for g in GROUPS}
others = {"a gold chunk of the question": [0, 0, []], "a sure chunk that is not gold": [0, 0, []],
          "a chunk of the rest that is not gold": [0, 0, []]}
for qid, d in Q.items():
    D, T = np.asarray(d["description"], dtype=np.float64), np.asarray(d["tags"], dtype=np.float64)
    m, gold = D.size, d["gold"]
    step = WK.levels(D, 5) + WK.levels(T, 5)
    hits = step <= 3 if (step <= 3).any() else step == step.min()
    scope = majority(hits, d["parent"])
    sure = (scope & (step <= 4)) | (~scope & (step == 2))
    sure_gold = np.flatnonzero(sure & gold).tolist()
    at = {(int(p), int(s)): k for k, (p, s) in enumerate(zip(d["parent"], d["spot"]))}
    talks = [set(t) for t in d["talks"]]
    linked = [set() for _ in range(m)]
    for a, b in d["share_a_link"].tolist():
        linked[a].add(b)
        linked[b].add(a)
    tags_of = [set() for _ in range(m)]
    spread = {}
    for c, t in zip(d["edge_chunk"].tolist(), d["edge_tag"].tolist()):
        tags_of[c].add(t)
        spread[t] = spread.get(t, 0) + 1
    rare = [{t for t in tags if 2 <= spread[t] <= 4} for tags in tags_of]
    among = d["among"].astype(np.float64)
    for k in range(m):
        group = (GROUPS[1] if (sure[k] and gold[k]) else GROUPS[0] if sure[k] else GROUPS[2] if not gold[k] else None)
        if group is None:
            continue
        against = [g for g in sure_gold if g != k]
        if not against:
            continue
        p, s = int(d["parent"][k]), int(d["spot"][k])
        facts = {
            "right above or under a gold chunk of the sure set": any(at.get((p, s + j)) in against for j in (-1, 1)),
            "in a conversation one of them is in": any(talks[k] & talks[g] for g in against),
            "shares a link with one of them": bool(linked[k] & set(against)),
            "shares with one of them a tag that sits on 2 to 4 chunks": any(rare[k] & rare[g] for g in against),
            "in the parent of one of them": any(d["parent"][k] == d["parent"][g] for g in against),
        }
        facts["any of the first four"] = any(list(facts.values())[:4])
        row = ties[group]
        row["n"] = row.get("n", 0) + 1
        for label, holds in facts.items():
            row[label] = row.get(label, 0) + int(holds)
        near[group].append(float(max(among[k][g] for g in against)))
    for k in range(m):
        label = ("a gold chunk of the question" if gold[k] else "a sure chunk that is not gold" if sure[k]
                 else "a chunk of the rest that is not gold")
        asked_by = set()
        for r in d["records"][k]:
            asked_by |= cited_by.get(r, set())
        asked_by.discard(qid)
        row = others[label]
        row[0] += 1
        row[1] += int(bool(asked_by))
        row[2].append(len(asked_by))

print("== 1: tied to the question's gold chunks of the sure set (the chunk itself left out) ==")
labels = [k for k in ties[GROUPS[0]] if k != "n"]
print("  " + " | ".join(f"{g} ({ties[g]['n']})" for g in GROUPS))
for label in labels:
    print("  " + " | ".join(f"{ties[g][label] / ties[g]['n']:4.0%}" for g in GROUPS) + f"  {label}")
print("  " + " | ".join(f"{np.median(near[g]):.3f}" for g in GROUPS) + "  description nearness to the nearest of them, the middle")
print("\n== 2: cited by some other question of the benchmark: chunks | share | other questions citing it, the middle ==")
for label, (n, cited, counts) in others.items():
    print(f"  {n:6d} | {cited / n:4.0%} | {np.median(counts):.0f}  {label}")

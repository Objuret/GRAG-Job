"""Round 70, his 2026-10-13 "its the fucking COMBO of those thingat the same time" (after "if you add
nearness by time and posts the same author is part of, limited by scope" and "near in tame from
the SAME conversation"): time and author IN the combo, at the same time as the description side
and the tags' side, not as a reach after the hits and not one at a time. The hundred, the
handing over of the step in the arm kept (the product's own work, conversations whole);
numbers only.

The combo as built: the description side and the tags' side are each cut into five clusters
over the border, a chunk's step is its two levels added, the scope's chunks first inside a step.
The hits: the chunks on its first two steps (what the scope is gauged from).

Sides added here, each cut into five clusters like the others (mine, to be said to him):
  time     a chunk's distance in time to the nearest hit in its own conversation (its parent: a
           channel); a chunk whose parent holds no hit stands with the farthest
  author   the best hit (by the combo's value) that shares a writer with the chunk; none: farthest
  joined   both at once as ONE side: among the hits in the chunk's own conversation that share a
           writer with it, the nearest in time; none: farthest
"limited by scope": the added sides are read only for the chunks under the scope's parents.

  C   the combo as built
  X1  four sides: description, tags, time, author; the levels added
  X2  three sides: description, tags, joined; the levels added
  X3  the combo's two sides, the joined side's level first inside a step
  the same three with the added sides limited to the scope's parents (L)
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


def writers(record_ids, P):
    out = set()
    for r in record_ids:
        kind, rec = P["raw"][r]
        if kind == "slack":
            out.add(rec["Message"]["User"]["userId"])
        elif kind == "prs":
            out.add(rec["user"]["login"])
        elif kind == "documents":
            out.add(rec["author"])
    return out - P["everywhere"]


def side(values, missing):
    """A side's nearness per chunk, higher the nearer; a chunk with none stands with the farthest. Levels and standing."""
    x = np.asarray(values, dtype=np.float64)
    have = ~missing
    if not have.any():
        return np.full(x.size, 5, dtype=np.int64), np.zeros(x.size)
    x = np.where(have, x, x[have].min() - 1.)
    return WK.levels(x, 5), standing(x)


results = defaultdict(list)
moved = defaultdict(list)
for qid, d in Q.items():
    d.update(extra[qid])
    P = TI.product(qid.split("::")[0])
    m = d["gold"].size
    cited, cites = set(d["cited_ids"]), d["cites"]
    kind = [KINDS[x] for x in d["kind"]]
    own = [[r for r in d["records"][k] if not TI.apart(r, P)] for k in range(m)]
    chunk_len = d["length"].astype(np.int64)
    D, Tg = np.asarray(d["question_bare"], dtype=np.float64), np.asarray(d["tags"], dtype=np.float64)
    lD, lT = WK.levels(D, 5), WK.levels(Tg, 5)
    step = (lD + lT).astype(np.float64)
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
    when = (np.asarray(d["first_time"], dtype=np.float64) + np.asarray(d["last_time"], dtype=np.float64)) / 2.
    who = [writers(own[k], P) for k in range(m)]
    hit_at = np.flatnonzero(hits)
    time_near, author_best, joined = np.full(m, np.nan), np.full(m, np.nan), np.full(m, np.nan)
    for k in range(m):
        same = [h for h in hit_at.tolist() if d["parent"][h] == d["parent"][k] and np.isfinite(when[h]) and np.isfinite(when[k])]
        if same:
            time_near[k] = -np.log1p(min(abs(when[h] - when[k]) for h in same))
        shared = [h for h in hit_at.tolist() if who[k] & who[h]]
        if shared:
            author_best[k] = max(z[h] for h in shared)
        both = [h for h in same if who[k] & who[h]]
        if both:
            joined[k] = -np.log1p(min(abs(when[h] - when[k]) for h in both))
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

    base_order = np.lexsort((d["id_rank"], -z, ~scope, step))
    results["C   the combo as built"].append(send(base_order))
    for limited in (False, True):
        tag = "  (L: added sides only under the scope's parents)" if limited else ""
        out = ~scope if limited else np.zeros(m, dtype=bool)
        lTime, sTime = side(time_near, np.isnan(time_near) | out)
        lAuth, sAuth = side(author_best, np.isnan(author_best) | out)
        lJoin, sJoin = side(joined, np.isnan(joined) | out)
        o1 = np.lexsort((d["id_rank"], -(z + sTime + sAuth), ~scope, (lD + lT + lTime + lAuth).astype(np.float64)))
        o2 = np.lexsort((d["id_rank"], -(z + sJoin), ~scope, (lD + lT + lJoin).astype(np.float64)))
        o3 = np.lexsort((d["id_rank"], -z, ~scope, lJoin, step))
        for label, o in (("X1  four sides: description, tags, time, author", o1), ("X2  three sides: description, tags, joined", o2),
                         ("X3  the two sides, the joined side's level first inside a step", o3)):
            results[label + tag].append(send(o))
            moved[label + tag].append(int((o[:15] != base_order[:15]).sum()))

print("first text holds a cited record (of 100) | context_recall_id | of the first 15 places, how many hold another chunk than in the combo")
base = np.array([r[1] for r in results["C   the combo as built"]])
for label, rows in results.items():
    a = np.array(rows, dtype=np.float64)
    diff = a[:, 1] - base
    print(f"  {int(a[:, 0].sum()):3d} | {a[:, 1].mean():.3f} | " + (f"{np.mean(moved[label]):4.1f}" if label in moved else "   -") + f"  {label}"
          + ("" if label.startswith("C  ") else f"   [{diff.mean():+.3f}, standard error {diff.std(ddof=1) / 10:.3f}, higher on "
             f"{int((diff > 1e-9).sum())}, lower on {int((diff < -1e-9).sum())}]"))

"""Round 71, his 2026-10-13 combo ("nearness by time and posts the same author is part of, limited
by scope", "near in time from the SAME conversation", "the COMBO of those things at the same
time"), worked through and not cut down. The hundred, the step in the arm as the base; numbers
only.

The pointer, with no number in it (mine, to be said to him): every thing a person takes part in
is put in the order of time, per person: a conversation (its writers, its first message's
time), an own pull request (its author and reviewers, when it was opened), a document (its
author, its date), a meeting (its participants, its date). Standing on one thing, each person
who is part of it points at the thing they were part of just before and just after: that is
"near in time" and "the same author is part of" at the same time, from the thing stood on.
"Limited by scope": a person's line is made of the things under the scope's parents only; the
product is shown beside it. A meeting is pointed at but not searched from (it has up to 48
participants).

  1  the pointer from the things the arm hands over: how many it reaches a start | share cited,
     when the start is cited and when it is not
  2  the test of a hit, with no gold in it: a handed-over thing is tied when the pointer joins
     it to another handed-over thing. How many are tied, and how often a tied one is cited
     against one that is not
  3  the search: from the tied ones only, what the pointer reaches at one step and at two:
     how many, share cited (a thing of the product with no hit near it: the base)
  4  the order rebuilt: the tied ones first; then what they reach; against the arm's order
     and against the pointer followed from every hit
"""
import pickle
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

import ties as TI  # noqa: E402
from explore import BUDGET, load, standing  # noqa: E402

HERE = Path(__file__).resolve().parent
T = load()
Q, KINDS, PARENTS = T["questions"], T["kind_names"], T["parent_names"]
with open(HERE / "first_gold_signals_tags__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
PARTS = ("document_part", "meeting_transcript_part")
WIDTHS = ("the scope's parents", "the product")


def seconds(stamp):
    return (datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).replace(tzinfo=None) - datetime(1970, 1, 1)).total_seconds()


def length_of(records, P):
    return sum(P["size"][r] for r in records) + max(len(records) - 1, 0)


reach_from = {w: {True: [0, 0, 0], False: [0, 0, 0]} for w in WIDTHS}
tied_count = {w: [0, 0, 0, 0] for w in WIDTHS}            # tied, tied and cited, untied, untied and cited
steps = {w: {1: [0, 0], 2: [0, 0]} for w in WIDTHS}
base = [0, 0]
results = defaultdict(list)
per_question_tied = defaultdict(list)
for qid, d in Q.items():
    d.update(extra[qid])
    P = TI.product(qid.split("::")[0])
    m = d["gold"].size
    cited, cites = set(d["cited_ids"]), d["cites"]
    kind = [KINDS[x] for x in d["kind"]]
    own = [[r for r in d["records"][k] if not TI.apart(r, P)] for k in range(m)]
    chunk_len = d["length"].astype(np.int64)
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

    # the things: (records, characters, a part of a record, persons, time, under the scope's parents, searched from)
    things, of_talk, of_record = [], {}, {}
    for k in sorted(range(m), key=lambda k: (int(d["parent"][k]), int(d["id_rank"][k]))):
        if kind[k] == "slack_thread_batch":
            for r in own[k]:
                t = P["talk_of"][r]
                if t not in of_talk:
                    of_talk[t] = len(things)
                    things.append({"records": [], "chunks": [], "part": False, "who": set(), "when": None, "from": True})
                thing = things[of_talk[t]]
                thing["records"].append(r)
                if k not in thing["chunks"]:
                    thing["chunks"].append(k)
                user = P["raw"][r][1]["Message"]["User"]
                thing["who"].add(user["userId"])
                stamp = seconds(user["timestamp"])
                thing["when"] = stamp if thing["when"] is None else min(thing["when"], stamp)
        else:
            for r in own[k]:
                if r not in of_record:
                    rec_kind, rec = P["raw"][r]
                    of_record[r] = len(things)
                    who, when, searched = set(), None, True
                    if rec_kind == "prs":
                        who = {rec["user"]["login"]} | {v["user"]["login"] for v in rec["reviews"]}
                        when = seconds(rec["created_at"])
                    elif rec_kind == "documents":
                        who, when = {rec["author"]}, seconds(rec["date"])
                    elif rec_kind == "meeting_transcripts":
                        who, when, searched = set(rec["participants"]), seconds(rec["date"]), False
                    things.append({"records": [r], "chunks": [], "part": False, "who": who, "when": when, "from": searched})
                thing = things[of_record[r]]
                if k not in thing["chunks"]:
                    thing["chunks"].append(k)
                    thing["part"] = thing["part"] or kind[k] in PARTS
    n = len(things)
    for thing in things:
        thing["who"] -= P["everywhere"]
        if len(thing["records"]) > 1 or thing["records"][0] in P["talk_of"]:
            thing["chars"] = length_of(thing["records"], P)
        elif thing["records"][0] in P["pr_own"]:
            thing["chars"] = P["size"][thing["records"][0]]
        else:
            thing["chars"] = int(sum(chunk_len[c] for c in thing["chunks"]))
        thing["place"] = min(int(place[c]) for c in thing["chunks"])
        thing["scope"] = any(scope[c] for c in thing["chunks"])
        thing["cited"] = bool(cited & set(thing["records"]))

    def pointer(width):
        """Per thing the things it points at: for each of its persons, the thing just before and just after on that
        person's own line of time (the line made of the things inside the width)."""
        lines = defaultdict(list)
        for i, thing in enumerate(things):
            if thing["when"] is None or (width == WIDTHS[0] and not thing["scope"]):
                continue
            for person in thing["who"]:
                lines[person].append(i)
        out = [set() for _ in range(n)]
        for person, line in lines.items():
            line.sort(key=lambda i: (things[i]["when"], i))
            for at, i in enumerate(line):
                if not things[i]["from"]:
                    continue
                if at:
                    out[i].add(line[at - 1])
                if at + 1 < len(line):
                    out[i].add(line[at + 1])
        return out

    def hand_over(sequence):
        used, seen, first, three, count, handed = 0, set(), None, False, 0, []
        for i in sequence:
            thing = things[i]
            new = [r for r in thing["records"] if r not in seen]
            if not new and not thing["part"]:
                continue
            if used + thing["chars"] > BUDGET:
                break
            used += thing["chars"]
            seen.update(thing["records"])
            count += 1
            hit = thing["cited"]
            first = hit if first is None else first
            three = three or (count <= 3 and hit)
            handed.append(i)
        return (bool(first), three, len(cited & seen) / cites), handed

    arm = sorted(range(n), key=lambda i: (things[i]["place"], i))
    got, handed = hand_over(arm)
    results["the arm's order"].append(got)
    handed_set = set(handed)
    base[0] += sum(1 for i in range(n) if i not in handed_set)
    base[1] += sum(1 for i in range(n) if i not in handed_set and things[i]["cited"])
    for width in WIDTHS:
        points = pointer(width)
        for a in handed:
            r = points[a] - handed_set
            row = reach_from[width][things[a]["cited"]]
            row[0] += 1
            row[1] += len(r)
            row[2] += sum(things[b]["cited"] for b in r)
        tied = {a for a in handed if any((b in points[a] or a in points[b]) for b in handed if b != a)}
        row = tied_count[width]
        row[0] += len(tied)
        row[1] += sum(things[a]["cited"] for a in tied)
        row[2] += len(handed) - len(tied)
        row[3] += sum(things[a]["cited"] for a in handed if a not in tied)
        per_question_tied[width].append(len(tied) / max(len(handed), 1))
        one = set().union(*[points[a] for a in tied]) - handed_set if tied else set()
        two = (set().union(*[points[b] for b in one]) - handed_set - one) if one else set()
        steps[width][1][0] += len(one)
        steps[width][1][1] += sum(things[b]["cited"] for b in one)
        steps[width][2][0] += len(two)
        steps[width][2][1] += sum(things[b]["cited"] for b in two)
        first = [a for a in arm if a in tied]
        rest = [a for a in arm if a not in tied]
        results[f"the tied ones first, then the arm's order ({width})"].append(hand_over(first + rest)[0])
        reached = sorted(one, key=lambda i: (things[i]["place"], i))
        results[f"the tied ones, then what they point at, then the rest ({width})"].append(
            hand_over(first + reached + [a for a in rest if a not in one])[0])
        blind, seen_ = [], set()
        for a in arm:
            for b in [a] + sorted(points[a], key=lambda i: (things[i]["place"], i)):
                if b not in seen_:
                    seen_.add(b)
                    blind.append(b)
        results[f"the pointer followed from every hit as it is handed over ({width})"].append(hand_over(blind)[0])

n_q = len(Q)
print(f"a thing of the product that the arm does not hand over is cited {base[1] / base[0]:.1%} of the time (the base)")
print("\n== 1: the pointer from a handed-over thing: reached, a start | share cited: from a cited start ; from one that is not ==")
for width in WIDTHS:
    a, b = reach_from[width][True], reach_from[width][False]
    print(f"   {a[1] / max(a[0], 1):4.1f}, {a[2] / max(a[1], 1):4.0%} ; {b[1] / max(b[0], 1):4.1f}, {b[2] / max(b[1], 1):4.0%}   within {width}")
print("\n== 2: the test of a hit (no gold in it): handed-over things tied to another handed-over thing, a question | of them cited ; "
      "not tied, a question | of them cited ==")
for width in WIDTHS:
    t = tied_count[width]
    print(f"   {t[0] / n_q:5.1f} | {t[1] / max(t[0], 1):4.0%} ; {t[2] / n_q:5.1f} | {t[3] / max(t[2], 1):4.0%}   within {width}")
print("\n== 3: from the tied ones only: reached at one step, a question | of them cited ; at two steps | of them cited ==")
for width in WIDTHS:
    s = steps[width]
    print(f"   {s[1][0] / n_q:5.1f} | {s[1][1] / max(s[1][0], 1):4.0%} ; {s[2][0] / n_q:5.1f} | {s[2][1] / max(s[2][0], 1):4.0%}   within {width}")
print("\n== 4: first thing holds a cited record (of 100) | a cited record among the first three | context_recall_id ==")
base_r = np.array([r[2] for r in results["the arm's order"]])
for label, rows in results.items():
    a = np.array(rows, dtype=np.float64)
    diff = a[:, 2] - base_r
    print(f"  {int(a[:, 0].sum()):3d} | {int(a[:, 1].sum()):3d} | {a[:, 2].mean():.3f}  {label}"
          + ("" if label == "the arm's order" else f"   [{diff.mean():+.3f}, standard error {diff.std(ddof=1) / 10:.3f}, higher on "
             f"{int((diff > 1e-9).sum())}, lower on {int((diff < -1e-9).sum())}]"))

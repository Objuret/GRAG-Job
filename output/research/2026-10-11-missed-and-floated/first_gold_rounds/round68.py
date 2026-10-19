"""Round 68, his 2026-10-13 "if you add nearness by time and posts the same author is part of,
limited by scope, how does it look then?": on top of the step in the arm (the product's own
work, conversations whole), from the conversations the arm hands over, reach other conversations
by time and by author, inside a scope. The hundred, numbers only.

Mine in this count, to be said to him: a conversation's time is its first message's; "near in
time" from a start is read two ways, the same day, and the first of five clusters of the other
conversations' distance in time to the start (the logarithm of the distance, `v4_walk.levels`);
"the same author is part of" is a person who writes in both (the account that opens channels is
no person); the scope is shown at three widths: the product, the parents the combo's scope
takes, the start's own channel.

  1  from a handed-over conversation: the conversations a pointer reaches (not yet handed
     over): how many a start | share with a cited message, when the start has a cited message
     and when it has none
  2  the cited conversations that are not handed over: share reached from a handed-over cited
     conversation | from any handed-over conversation
  3  handing over: as the arm does; and with the reached conversations right behind each
     conversation as it is handed over (for the pointers named there)
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
TIME = ("the same day", "the first of five clusters of nearness in time")
SCOPES = ("the product", "the scope's parents", "the start's own channel")
POINTERS = [(time, author, scope) for scope in SCOPES for time in (None,) + TIME for author in (False, True)
            if time or author]


def seconds(stamp):
    return (datetime.fromisoformat(stamp) - datetime(1970, 1, 1)).total_seconds()


def name(pointer):
    time, author, scope = pointer
    parts = ([f"near in time ({time})"] if time else []) + (["a person writes in both"] if author else [])
    return " and ".join(parts) + f", within {scope}"


def length_of(records, P):
    return sum(P["size"][r] for r in records) + max(len(records) - 1, 0)


reach = {p: {True: [0, 0, 0], False: [0, 0, 0]} for p in POINTERS}      # starts, reached, reached and cited
missed = {p: [0, 0] for p in POINTERS}
missed_total = 0
results = defaultdict(list)
SHOWN = [("the same day", True, "the scope's parents"), ("the same day", True, "the product"),
         ("the first of five clusters of nearness in time", True, "the scope's parents"),
         ("the same day", True, "the start's own channel"), (None, True, "the start's own channel")]
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
    scope_channels = {PARENTS[int(d["parent"][k])].split(".slack.", 1)[1] for k in range(m)
                      if scope[k] and kind[k] == "slack_thread_batch"}
    talk_records = defaultdict(list)
    for k in sorted(range(m), key=lambda k: (int(d["parent"][k]), int(d["id_rank"][k]))):
        if kind[k] == "slack_thread_batch":
            for r in own[k]:
                talk_records[P["talk_of"][r]].append(r)
    talks = list(talk_records)
    at_of = {t: i for i, t in enumerate(talks)}
    user = lambda r: P["raw"][r][1]["Message"]["User"]  # noqa: E731
    when = np.array([min(seconds(user(r)["timestamp"]) for r in talk_records[t]) for t in talks])
    day = [min(user(r)["timestamp"] for r in talk_records[t])[:10] for t in talks]
    people = [{user(r)["userId"] for r in talk_records[t]} - P["everywhere"] for t in talks]
    channel = [t[0] for t in talks]
    in_scope = np.array([c in scope_channels for c in channel])
    is_cited = np.array([bool(cited & set(talk_records[t])) for t in talks])
    n = len(talks)
    share = np.array([[bool(people[a] & people[b]) for b in range(n)] for a in range(n)])
    same_day = np.array([[day[a] == day[b] for b in range(n)] for a in range(n)])
    same_channel = np.array([[channel[a] == channel[b] for b in range(n)] for a in range(n)])

    def near_cluster(a, allowed):
        out = np.zeros(n, dtype=bool)
        pool = np.flatnonzero(allowed)
        if pool.size:
            out[pool[WK.levels(-np.log1p(np.abs(when[pool] - when[a])), 5) == 1]] = True
        return out

    def reached(a, pointer):
        time, author, width = pointer
        allowed = np.ones(n, dtype=bool) if width == SCOPES[0] else in_scope.copy() if width == SCOPES[1] else same_channel[a].copy()
        allowed[a] = False
        if author:
            allowed &= share[a]
        if time == TIME[0]:
            allowed &= same_day[a]
        elif time == TIME[1]:
            allowed = near_cluster(a, allowed)
        return allowed

    def units(pointer=None):
        seen, sent, out = set(), set(), []
        for k in order.tolist():
            if not own[k]:
                continue
            if kind[k] != "slack_thread_batch":
                size = int(chunk_len[k]) if kind[k] in PARTS or len(own[k]) == len(d["records"][k]) else length_of(own[k], P)
                out.append((None, own[k], size, kind[k] in PARTS))
                continue
            for t in dict.fromkeys(P["talk_of"][r] for r in own[k]):
                group = [t] + ([talks[b] for b in np.flatnonzero(reached(at_of[t], pointer)).tolist()] if pointer else [])
                for g in group:
                    if g not in seen:
                        seen.add(g)
                        out.append((g, talk_records[g], length_of(talk_records[g], P), False))
        return out

    def hand_over(units_):
        used, got, first, three, count, handed = 0, set(), None, False, 0, []
        for t, records, chars, part in units_:
            new = [r for r in records if r not in got]
            if not new and not part:
                continue
            if used + chars > BUDGET:
                break
            used += chars
            got.update(records)
            count += 1
            hit = bool(cited & set(records))
            first = hit if first is None else first
            three = three or (count <= 3 and hit)
            if t is not None:
                handed.append(t)
        return (bool(first), three, len(cited & got) / cites), handed

    base, handed = hand_over(units())
    results["as the arm does (a conversation its own unit)"].append(base)
    handed_i = np.array([at_of[t] for t in handed], dtype=np.int64)
    left = np.ones(n, dtype=bool)
    left[handed_i] = False
    lost = left & is_cited
    missed_total += int(lost.sum())
    for pointer in POINTERS:
        got_from_cited = np.zeros(n, dtype=bool)
        got_from_any = np.zeros(n, dtype=bool)
        for a in handed_i.tolist():
            r = reached(a, pointer) & left
            row = reach[pointer][bool(is_cited[a])]
            row[0] += 1
            row[1] += int(r.sum())
            row[2] += int((r & is_cited).sum())
            got_from_any |= r
            if is_cited[a]:
                got_from_cited |= r
        missed[pointer][0] += int((got_from_cited & lost).sum())
        missed[pointer][1] += int((got_from_any & lost).sum())
    for pointer in SHOWN:
        results["behind each handed-over conversation: " + name(pointer)].append(hand_over(units(pointer))[0])

n_q = len(Q)
print("== 1: a pointer from a handed-over conversation to conversations not handed over: reached, a start | share cited: from a "
      "start WITH a cited message ; from a start with NONE  ==  2: of the cited conversations not handed over "
      f"({missed_total / n_q:.1f} a question): reached from a cited start | from any start ==")
for pointer in POINTERS:
    a, b = reach[pointer][True], reach[pointer][False]
    print(f"  {a[1] / max(a[0], 1):5.1f}, {a[2] / max(a[1], 1):4.0%} ; {b[1] / max(b[0], 1):5.1f}, {b[2] / max(b[1], 1):4.0%}  ||  "
          f"{missed[pointer][0] / missed_total:4.0%} | {missed[pointer][1] / missed_total:4.0%}   {name(pointer)}")
print("\n== 3: first unit holds a cited record (of 100) | a cited record among the first three | context_recall_id ==")
base = np.array([r[2] for r in results["as the arm does (a conversation its own unit)"]])
for label, rows in results.items():
    a = np.array(rows, dtype=np.float64)
    diff = a[:, 2] - base
    print(f"  {int(a[:, 0].sum()):3d} | {int(a[:, 1].sum()):3d} | {a[:, 2].mean():.3f}  {label}"
          + ("" if label.startswith("as the arm") else f"   [{diff.mean():+.3f}, standard error {diff.std(ddof=1) / 10:.3f}, higher on "
             f"{int((diff > 1e-9).sum())}, lower on {int((diff < -1e-9).sum())}]"))

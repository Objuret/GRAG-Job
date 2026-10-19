"""Round 69, his 2026-10-13 "if you add nearness by time and posts the same author is part of,
limited by scope, how does it look then?", two more readings beside round 68's reach from every
hit. The hundred, the step in the arm as the base (the product's own work, conversations whole),
a single conversation as the unit; numbers only.

  A  as weight on the order (his 2026-10-11 "using it as a ranking-weight"): the hits are the
     conversations of the combo's first two steps' chunks; a conversation inside the scope's
     parents that is near in time to a hit, or that a hit's author takes part in, or both, comes
     first inside its step (as the scope's chunks do); nothing is reached or moved across steps
  B  the reach of round 68 (near in time and an author in both, inside the scope's parents),
     started from one conversation only: the arm's first; and the one the local reranker puts
     first among the arm's first units (a side count: the reranker is not in the arm)
     - how often that start holds a cited message, how many it reaches, share cited
     - handing over: the start, what it reaches, then the rest of the order
  "near in time": the first of k clusters of the distance in time to the start or hit; k = 5 as
  in the arm, and 3 and 7 beside it for B
"""
import json
import pickle
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

import ties as TI  # noqa: E402
from explore import BUDGET, load, standing  # noqa: E402

HERE = Path(__file__).resolve().parent
RES = Path(r"C:\Coding\exjobbet\GRAG-Job\output\research\2026-10-11-missed-and-floated")
T = load()
Q, KINDS, PARENTS = T["questions"], T["kind_names"], T["parent_names"]
with open(HERE / "first_gold_signals_tags__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
PARTS = ("document_part", "meeting_transcript_part")
rows = [json.loads(line) for line in open(RES / "own_units" / "own_units.jsonl", encoding="utf-8")]
unit_id = {tuple(row["records"]): row["id"] for row in rows if row["id"].startswith("talk|")}
got = np.load(RES / "reader" / "reader__gold100.npz", allow_pickle=False)
score = dict(zip((str(e) for e in got["edge_id"]), got["native_logit"].astype(np.float64).reshape(len(got["edge_id"]), -1)[:, 0]))


def seconds(stamp):
    return (datetime.fromisoformat(stamp) - datetime(1970, 1, 1)).total_seconds()


def length_of(records, P):
    return sum(P["size"][r] for r in records) + max(len(records) - 1, 0)


results = defaultdict(list)
starts = defaultdict(lambda: [0, 0, 0, 0])            # questions, start cited, reached, reached cited
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
    scope_channels = {PARENTS[int(d["parent"][k])].split(".slack.", 1)[1] for k in range(m)
                      if scope[k] and kind[k] == "slack_thread_batch"}
    talk_records, talk_chunks = defaultdict(list), defaultdict(list)
    for k in sorted(range(m), key=lambda k: (int(d["parent"][k]), int(d["id_rank"][k]))):
        if kind[k] == "slack_thread_batch":
            for r in own[k]:
                t = P["talk_of"][r]
                talk_records[t].append(r)
                if k not in talk_chunks[t]:
                    talk_chunks[t].append(k)
    talks = list(talk_records)
    at_of = {t: i for i, t in enumerate(talks)}
    n = len(talks)
    user = lambda r: P["raw"][r][1]["Message"]["User"]  # noqa: E731
    when = np.array([min(seconds(user(r)["timestamp"]) for r in talk_records[t]) for t in talks])
    people = [{user(r)["userId"] for r in talk_records[t]} - P["everywhere"] for t in talks]
    in_scope = np.array([t[0] in scope_channels for t in talks])
    is_cited = np.array([bool(cited & set(talk_records[t])) for t in talks])
    best = np.array([min(talk_chunks[t], key=lambda k: int(place[k])) for t in talks])
    share = np.array([[bool(people[a] & people[b]) for b in range(n)] for a in range(n)])

    def near(a, allowed, k=5):
        out = np.zeros(n, dtype=bool)
        pool = np.flatnonzero(allowed)
        if pool.size:
            out[pool[WK.levels(-np.log1p(np.abs(when[pool] - when[a])), k) == 1]] = True
        return out

    def reach(a, k=5):
        allowed = in_scope & share[a]
        allowed[a] = False
        return near(a, allowed, k)

    others = [(int(place[c]), own[c], (int(chunk_len[c]) if kind[c] in PARTS or len(own[c]) == len(d["records"][c])
                                         else length_of(own[c], P)), kind[c] in PARTS, None)
              for c in range(m) if kind[c] != "slack_thread_batch" and own[c]]

    def hand_over(talk_key):
        """talk_key: per conversation its sort key; the other chunks keep (their chunk's place,)."""
        units = [((p_,) if not isinstance(p_, tuple) else p_, recs, chars, part, t) for p_, recs, chars, part, t in others]
        units = [((u[0][0], 0, 0), u[1], u[2], u[3], u[4]) for u in units]
        for i, t in enumerate(talks):
            units.append((talk_key(i), talk_records[t], length_of(talk_records[t], P), False, i))
        units.sort(key=lambda u: u[0])
        used, seen, first, three, count = 0, set(), None, False, 0
        for _, records, chars, part, _t in units:
            new = [r for r in records if r not in seen]
            if not new and not part:
                continue
            if used + chars > BUDGET:
                break
            used += chars
            seen.update(records)
            count += 1
            hit = bool(cited & set(records))
            first = hit if first is None else first
            three = three or (count <= 3 and hit)
        return bool(first), three, len(cited & seen) / cites

    plain = lambda i: (int(place[best[i]]), 0, i)  # noqa: E731
    results["as the arm does (a conversation its own unit)"].append(hand_over(plain))

    # A: weight inside a step. The order of the chunks is (step, in scope, value); a conversation takes its best chunk's.
    hit_talks = np.array([any(hits[c] for c in talk_chunks[t]) for t in talks])
    marks = {"near in time to a hit": np.zeros(n, dtype=bool), "a hit's author takes part": np.zeros(n, dtype=bool)}
    for a in np.flatnonzero(hit_talks).tolist():
        allowed = in_scope.copy()
        allowed[a] = False
        marks["near in time to a hit"] |= near(a, allowed)
        marks["a hit's author takes part"] |= allowed & share[a]
    marks["both"] = marks["near in time to a hit"] & marks["a hit's author takes part"]
    for label, mark in marks.items():
        def key(i, mark=mark):
            c = best[i]
            return (float(step[c]), not (in_scope[i] and (mark[i] or hit_talks[i])), not scope[c], -float(z[c]), i)
        units_key = lambda i, key=key: key(i)  # noqa: E731
        # the other chunks sort by (step, in scope, value) too: rebuild the comparison on one scale
        def all_key(i, key=key):
            return key(i)
        others_scaled = [((float(step[c]), True, not scope[c], -float(z[c]), -1), own[c],
                          (int(chunk_len[c]) if kind[c] in PARTS or len(own[c]) == len(d["records"][c]) else length_of(own[c], P)),
                          kind[c] in PARTS) for c in range(m) if kind[c] != "slack_thread_batch" and own[c]]
        units = others_scaled + [(key(i), talk_records[t], length_of(talk_records[t], P), False) for i, t in enumerate(talks)]
        units.sort(key=lambda u: u[0])
        used, seen, first, three, count = 0, set(), None, False, 0
        for _, records, chars, part in units:
            new = [r for r in records if r not in seen]
            if not new and not part:
                continue
            if used + chars > BUDGET:
                break
            used += chars
            seen.update(records)
            count += 1
            hit = bool(cited & set(records))
            first = hit if first is None else first
            three = three or (count <= 3 and hit)
        results[f"A  first inside its step, within the scope: {label}"].append((bool(first), three, len(cited & seen) / cites))

    # B: the reach from one start
    c_order = sorted(range(n), key=plain)
    read = np.array([score.get(f"{qid}||{unit_id.get(tuple(talk_records[t]), '')}", -np.inf) for t in talks])
    used, top = 0, []
    for i in c_order:
        if used + length_of(talk_records[talks[i]], P) > 2 * BUDGET:
            break
        used += length_of(talk_records[talks[i]], P)
        top.append(i)
    for label, start in (("the arm's first conversation", c_order[0]),
                         ("the conversation the reranker puts first", max(top, key=lambda i: read[i]))):
        for k in (3, 5, 7):
            r = reach(start, k)
            row = starts[(label, k)]
            row[0] += 1
            row[1] += bool(is_cited[start])
            row[2] += int(r.sum())
            row[3] += int((r & is_cited).sum())
        r = reach(start, 5)
        results[f"B  {label}, what it reaches by time and author in the scope, then the rest"].append(
            hand_over(lambda i, s=start, r=r: (-2, 0, 0) if i == s else (-1, 0, i) if r[i] else plain(i)))
        results[f"B  {label} first, then the rest (no reach)"].append(
            hand_over(lambda i, s=start: (-2, 0, 0) if i == s else plain(i)))

print("== B: the start | questions where it holds a cited message | conversations it reaches | of them cited ==")
for (label, k), (qs, right, reached, hit) in starts.items():
    print(f"   {right:3d} of {qs} | {reached / qs:4.1f} | {hit / max(reached, 1):4.0%}   {label}, near in time = the first of {k} clusters")
print("\n== first unit holds a cited record (of 100) | a cited record among the first three | context_recall_id ==")
base = np.array([r[2] for r in results["as the arm does (a conversation its own unit)"]])
for label, rows_ in results.items():
    a = np.array(rows_, dtype=np.float64)
    diff = a[:, 2] - base
    print(f"  {int(a[:, 0].sum()):3d} | {int(a[:, 1].sum()):3d} | {a[:, 2].mean():.3f}  {label}"
          + ("" if label.startswith("as the arm") else f"   [{diff.mean():+.3f}, standard error {diff.std(ddof=1) / 10:.3f}, higher on "
             f"{int((diff > 1e-9).sum())}, lower on {int((diff < -1e-9).sum())}]"))

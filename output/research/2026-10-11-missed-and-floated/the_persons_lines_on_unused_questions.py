"""His 2026-10-13 combo ("nearness by time and posts the same author is part of, limited by scope",
"near in time from the SAME conversation", "the COMBO of those things at the same time"), on the
gold hundred and on 100 questions no run has used (the first hundred of the seeded draw out of
the 615 outside both hundreds; his 2026-10-13 "how about not 300.. thats alot.."; the count on
all 300 of the draw is kept in the_persons_lines_on_300_unused_questions.log). No model call;
the gold ids are read inside; numbers only.

The pointer (mine as a reading of his words): every thing a person takes part in is put in the
order of time, per person (a conversation: its writers, its first message's time; an own pull
request: its author and reviewers, when it was opened; a document: its author, its date; a
meeting: its participants, its date). Standing on a thing, each person who is part of it points
at the thing they were part of just before and just after. A meeting is pointed at and not
searched from.

  how wide    the same channel   a person's line holds the things of one parent only, a parent
                                 of the scope (his "from the SAME conversation")
              the scope          a person's line holds the things under all the scope's parents
              the product        a person's line holds everything of the product
  how near    next               the thing just before and just after, however far away in time
              near of two        only when that gap is in the cluster of the shorter gaps: the
                                 logarithms of all the gaps of those lines cut in two by least
                                 squares (the cut that makes conversations of a channel's messages)
              near of five       the same with five clusters, the nearest one

  the order   the one made with no model call (the combo and the scope, the question without
              the product's name; the tags' side read with the question itself, since the unused
              questions have no query tags), the product's own work, a thing its own unit
  a hit       a thing handed over inside 72,000 characters by that order
  tied        a hit the pointer joins to another hit (no gold in this)

Printed per set, per how wide and how near:
  tied a question, of them cited | not tied a question, of them cited | questions where the tied
  ones are cited more often / less often than the ones not tied | from the tied ones at one
  step: reached a question, of them cited | the tied ones first: first thing holds a cited
  record, a cited record among the first three | the tied ones, what they point at, then the
  rest: context_recall_id and its difference to the order
For "next" two more lines:
  the hits that are not tied, apart: those under the scope's parents and those outside them
  (outside the scope a thing is on no line in the two narrower widths, so it is never tied there)
  the first hit of the order: on how many questions it is tied and how often it then holds a
  cited record; on how many it is not tied and how often it then holds one; and on those, how
  often the first tied hit behind it holds one
  the clouds: the tied hits that hang together through the pointer; the largest ones are those
  holding the majority of the tied hits; how often their hits are cited against the other tied
  hits, and the first thing when the largest clouds go first
"""
import json
import os
import random
import sys
import warnings
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test"), str(HERE / "first_gold_rounds")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"
os.environ["HERB_V4_SCOPE_STEP"] = "both"

import ties as TI  # noqa: E402
from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

BUDGET = 72000
CLUSTERS = 5
WIDTHS = ("the same channel", "the scope", "the product")
NEAR = (("next", 0), ("near of two", 2), ("near of five", 5))
ids_of = {name: {json.loads(line)["id"] for line in (REPO / "data" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
                 if line.strip()} for name in ("gold100", "heldout100")}
every = HQ.load_questions()
fresh = sorted((q for q in every if q.id not in ids_of["gold100"] | ids_of["heldout100"] and q.citations), key=lambda q: q.id)
SETS = {"the gold hundred": [q for q in every if q.id in ids_of["gold100"]],
        "100 unused questions": random.Random(20261011).sample(fresh, 300)[:100]}
p = V.prepare_over_corpus("the persons' lines")
layer, n_chunks = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
et, ec = layer["edge_tag"], layer["edge_chunk"]
parents = [str(row["parent"]) for row in p.chunk_rows]
parent_ids = {name: k for k, name in enumerate(sorted(set(parents)))}
parent_of = np.array([parent_ids[name] for name in parents], dtype=np.int64)
product_of = [name.split(".")[1] for name in parents]
kinds = [str(row["kind"]) for row in p.chunk_rows]
CV = np.asarray(p.chunk_vectors, dtype=np.float64)
TV = np.asarray(p.tag_vectors, dtype=np.float64)
AXES = V._QueryAxes(TV, np.eye(CV.shape[1]))
doc_cache = {}
records, length, is_part = [], np.zeros(n_chunks, dtype=np.int64), np.zeros(n_chunks, dtype=bool)
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, doc_cache)
    records.append([str(x) for x in ids])
    length[i] = len(text)
    is_part[i] = "char_range" in json.loads(row["locator"])
print("prepared", flush=True)


def seconds(stamp):
    return (datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).replace(tzinfo=None) - datetime(1970, 1, 1)).total_seconds()


def standing(x):
    x = np.asarray(x, dtype=np.float64)
    mid = np.median(x)
    spread = WK.MAD_TO_SPREAD * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


def closest_tag(vector):
    row = vector @ TV.T
    out = np.full(n_chunks, float(row.min()))
    np.maximum.at(out, ec, row[et])
    return out


def length_of(ids, P):
    return sum(P["size"][r] for r in ids) + max(len(ids) - 1, 0)


def the_things(q, P, inside, place, scoped):
    """The product's own work inside the border as things, each with its records, its persons and its time."""
    cites = {str(c) for c in q.citations}
    things, of_talk, of_record = [], {}, {}
    for i in sorted(inside.tolist(), key=lambda i: (parents[i], int(id_rank[i]))):
        for r in (r for r in records[i] if not TI.apart(r, P)):
            if kinds[i] == "slack_thread_batch":
                t = P["talk_of"][r]
                if t not in of_talk:
                    of_talk[t] = len(things)
                    things.append({"records": [], "chunks": [], "part": False, "who": set(), "when": None, "from": True,
                                   "home": ("channel", t[0])})
                thing = things[of_talk[t]]
                thing["records"].append(r)
                user = P["raw"][r][1]["Message"]["User"]
                thing["who"].add(user["userId"])
                stamp = seconds(user["timestamp"])
                thing["when"] = stamp if thing["when"] is None else min(thing["when"], stamp)
            else:
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
                    things.append({"records": [r], "chunks": [], "part": False, "who": who, "when": when, "from": searched,
                                   "home": ("parent", parents[i])})
                thing = things[of_record[r]]
                thing["part"] = thing["part"] or bool(is_part[i])
            if i not in thing["chunks"]:
                thing["chunks"].append(i)
    for thing in things:
        thing["who"] -= P["everywhere"]
        first = thing["records"][0]
        thing["chars"] = (length_of(thing["records"], P) if first in P["talk_of"] else P["size"][first] if first in P["pr_own"]
                          else int(sum(length[c] for c in thing["chunks"])))
        thing["place"] = min(place[c] for c in thing["chunks"])
        thing["scope"] = any(scoped[c] for c in thing["chunks"])
        thing["cited"] = bool(cites & set(thing["records"]))
    return things, cites


def pointer(things, width, clusters):
    """Per thing the things it points at; and how many pairs of neighbours the lines hold, how many of them count as near."""
    lines = defaultdict(list)
    for i, thing in enumerate(things):
        if thing["when"] is None or (width != WIDTHS[2] and not thing["scope"]):
            continue
        for person in thing["who"]:
            lines[(person, thing["home"]) if width == WIDTHS[0] else person].append(i)
    gap = {}
    for line in lines.values():
        line.sort(key=lambda i: (things[i]["when"], i))
        for a, b in zip(line, line[1:]):
            gap[(a, b)] = things[b]["when"] - things[a]["when"]
    out = [set() for _ in things]
    if not gap:
        return out, 0, 0
    pairs = list(gap)
    near = np.ones(len(pairs), dtype=bool)
    if clusters:
        level = WK.levels(np.log1p(np.array([gap[pair] for pair in pairs])), clusters)
        if level.max() > 1:
            near = level == level.max()
    for (a, b), ok in zip(pairs, near):
        if ok:
            if things[a]["from"]:
                out[a].add(b)
            if things[b]["from"]:
                out[b].add(a)
    return out, len(pairs), int(near.sum())


for label, drawn in SETS.items():
    base, skipped = [], 0
    rows = {(w, n): {"tied": [0, 0], "untied": [0, 0], "more": 0, "less": 0, "both": 0, "one": [0, 0], "pairs": [0, 0],
                     "first": [], "with": [], "loose_in": [0, 0], "loose_out": [0, 0], "top_tied": [0, 0],
                     "top_loose": [0, 0], "behind": [0, 0], "cloud": [0, 0], "tied_other": [0, 0], "cloud_first": []}
            for w in WIDTHS for n, _ in NEAR}
    left_out = [0, 0]
    for at_q, q in enumerate(drawn):
        border, scope_said = V.scope_by_name(q.question, p.tree, n_chunks)
        names = scope_said["names_in_the_question"]
        if len(names) != 1:
            skipped += 1
            continue
        inside = np.flatnonzero(border)
        P = TI.product(product_of[int(inside[0])])
        vector = np.asarray(V._query_cosines(V._without_names(q.question, names), [], AXES)[0]["query_description_cosines"],
                            dtype=np.float64)
        D, T = (CV @ vector)[inside], closest_tag(vector)[inside]
        step = WK.levels(D, CLUSTERS) + WK.levels(T, CLUSTERS)
        z = standing(D) + standing(T)
        taken = WK.majority_scopes(step <= max(3, int(step.min())), parent_of[inside])
        in_scope = np.isin(parent_of[inside], taken)
        ordered = inside[np.lexsort((id_rank[inside], -z, ~in_scope, step))].tolist()
        place = {i: at for at, i in enumerate(ordered)}
        scoped = {i: bool(s) for i, s in zip(inside.tolist(), in_scope.tolist())}
        things, cites = the_things(q, P, inside, place, scoped)
        n = len(things)

        def hand_over(sequence):
            used, seen, first, three, k, handed = 0, set(), None, False, 0, []
            for i in sequence:
                thing = things[i]
                if not thing["part"] and not [r for r in thing["records"] if r not in seen]:
                    continue
                if used + thing["chars"] > BUDGET:
                    break
                used += thing["chars"]
                seen.update(thing["records"])
                k += 1
                first = thing["cited"] if first is None else first
                three = three or (k <= 3 and thing["cited"])
                handed.append(i)
            return (bool(first), three, len(cites & seen) / len(cites)), handed

        arm = sorted(range(n), key=lambda i: (things[i]["place"], i))
        got, handed = hand_over(arm)
        base.append(got)
        held = set(handed)
        left_out[0] += n - len(held)
        left_out[1] += sum(things[i]["cited"] for i in range(n) if i not in held)
        for width in WIDTHS:
            for near_name, clusters in NEAR:
                row = rows[(width, near_name)]
                points, pairs, near_pairs = pointer(things, width, clusters)
                row["pairs"][0] += pairs
                row["pairs"][1] += near_pairs
                tied = {a for a in handed if any((b in points[a] or a in points[b]) for b in handed if b != a)}
                loose = [a for a in handed if a not in tied]
                row["tied"][0] += len(tied)
                row["tied"][1] += sum(things[a]["cited"] for a in tied)
                row["untied"][0] += len(loose)
                row["untied"][1] += sum(things[a]["cited"] for a in loose)
                for a in loose:
                    side = row["loose_in"] if things[a]["scope"] else row["loose_out"]
                    side[0] += 1
                    side[1] += things[a]["cited"]
                if handed:
                    top = handed[0]
                    side = row["top_tied"] if top in tied else row["top_loose"]
                    side[0] += 1
                    side[1] += things[top]["cited"]
                    if top not in tied and tied:
                        row["behind"][0] += 1
                        row["behind"][1] += things[next(a for a in handed if a in tied)]["cited"]
                # The clouds: the tied hits that hang together through the pointer; the largest ones, those holding the
                # majority of the tied hits (`majority_scopes`, his 2026-10-09 "If majority of something, BRANCH is chosen").
                cloud_of = {}
                for a in handed:
                    if a in tied and a not in cloud_of:
                        cloud_of[a], stack = a, [a]
                        while stack:
                            x = stack.pop()
                            for y in handed:
                                if y not in cloud_of and (y in points[x] or x in points[y]):
                                    cloud_of[y] = a
                                    stack.append(y)
                main = set()
                if cloud_of:
                    members = sorted(cloud_of)
                    number = {c: k for k, c in enumerate(sorted(set(cloud_of.values())))}
                    largest = set(WK.majority_scopes(np.ones(len(members), dtype=bool),
                                                     np.array([number[cloud_of[a]] for a in members], dtype=np.int64)))
                    main = {a for a in members if number[cloud_of[a]] in largest}
                row["cloud"][0] += len(main)
                row["cloud"][1] += sum(things[a]["cited"] for a in main)
                row["tied_other"][0] += len(tied) - len(main)
                row["tied_other"][1] += sum(things[a]["cited"] for a in tied if a not in main)
                row["cloud_first"].append(hand_over([a for a in arm if a in main] + [a for a in arm if a not in main])[0])
                if tied and loose:
                    row["both"] += 1
                    a_share = sum(things[a]["cited"] for a in tied) / len(tied)
                    b_share = sum(things[a]["cited"] for a in loose) / len(loose)
                    row["more"] += a_share > b_share
                    row["less"] += a_share < b_share
                one = (set().union(*[points[a] for a in tied]) - held) if tied else set()
                row["one"][0] += len(one)
                row["one"][1] += sum(things[b]["cited"] for b in one)
                first = [a for a in arm if a in tied]
                rest = [a for a in arm if a not in tied]
                row["first"].append(hand_over(first + rest)[0])
                row["with"].append(hand_over(first + sorted(one, key=lambda i: (things[i]["place"], i))
                                             + [a for a in rest if a not in one])[0])
        if (at_q + 1) % 50 == 0:
            print(f"   {label}: {at_q + 1} questions", flush=True)
    count = len(base)
    b = np.array(base, dtype=np.float64)
    print(f"\n==== {label}: {count} questions ({skipped} with not one name of the tree left out) ====")
    print(f"the order: first thing holds a cited record {int(b[:, 0].sum())} of {count} ({b[:, 0].mean():.0%}) | a cited record among the "
          f"first three {int(b[:, 1].sum())} ({b[:, 1].mean():.0%}) | context_recall_id {b[:, 2].mean():.3f}")
    print(f"a thing of the product that is not handed over is cited {left_out[1] / max(left_out[0], 1):.1%} of the time")
    print("how wide | how near | pairs of neighbours a question, of them near | tied a question, cited | not tied a question, cited | "
          "questions: tied cited more often / less often (of those with both) | one step from the tied: reached a question, cited | "
          "tied first: first thing, among three | tied, pointed at, rest: context_recall_id (difference, standard error)")
    for width in WIDTHS:
        for near_name, _ in NEAR:
            row = rows[(width, near_name)]
            f = np.array(row["first"], dtype=np.float64)
            w = np.array(row["with"], dtype=np.float64)
            diff = w[:, 2] - b[:, 2]
            print(f"  {width:16s} | {near_name:12s} | {row['pairs'][0] / count:6.1f}, {row['pairs'][1] / max(row['pairs'][0], 1):4.0%} | "
                  f"{row['tied'][0] / count:5.1f}, {row['tied'][1] / max(row['tied'][0], 1):4.0%} | "
                  f"{row['untied'][0] / count:5.1f}, {row['untied'][1] / max(row['untied'][0], 1):4.0%} | "
                  f"{row['more']:3d} / {row['less']:3d} (of {row['both']:3d}) | "
                  f"{row['one'][0] / count:5.1f}, {row['one'][1] / max(row['one'][0], 1):4.0%} | "
                  f"{int(f[:, 0].sum()):3d} ({f[:, 0].mean():.0%}), {int(f[:, 1].sum()):3d} ({f[:, 1].mean():.0%}) | "
                  f"{w[:, 2].mean():.3f} ({diff.mean():+.3f}, {diff.std(ddof=1) / np.sqrt(diff.size):.3f})")
            if near_name == "next":
                li, lo, tt, tl, bh = (row[key] for key in ("loose_in", "loose_out", "top_tied", "top_loose", "behind"))
                print(f"       not tied, under the scope's parents: {li[0] / count:.1f} a question, {li[1] / max(li[0], 1):.0%} cited ; "
                      f"outside them: {lo[0] / count:.1f} a question, {lo[1] / max(lo[0], 1):.0%} cited")
                print(f"       the first hit is tied on {tt[0]} questions and holds a cited record on {tt[1]} of them ({tt[1] / max(tt[0], 1):.0%}) ; "
                      f"not tied on {tl[0]}, holds one on {tl[1]} ({tl[1] / max(tl[0], 1):.0%}) ; on {bh[0]} of those a tied hit stands "
                      f"behind it, and the first such holds one on {bh[1]} ({bh[1] / max(bh[0], 1):.0%})")
                cl, ot = row["cloud"], row["tied_other"]
                c = np.array(row["cloud_first"], dtype=np.float64)
                print(f"       the largest clouds of tied hits (those holding the majority of the tied hits): {cl[0] / count:.1f} a question, "
                      f"{cl[1] / max(cl[0], 1):.0%} cited ; the other tied hits: {ot[0] / count:.1f} a question, {ot[1] / max(ot[0], 1):.0%} cited ; "
                      f"the largest clouds first: first thing {int(c[:, 0].sum())} ({c[:, 0].mean():.0%}), among three {int(c[:, 1].sum())} "
                      f"({c[:, 1].mean():.0%})")
print("done", flush=True)

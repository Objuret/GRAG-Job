"""His 2026-10-13 question: "if a chunk gets a good hit, are the related in time and person chunks
better based on timenearness AFTER the first chunk, or "nearness around" or "before" ?" On the
gold hundred and on the first 100 of the seeded draw of unused questions. No model call; the
gold ids are read inside; numbers only.

Every thing a person takes part in is put in the order of time, per person (as in
the_persons_lines_on_unused_questions.py; a thing: one conversation, one own pull request, one
document, one meeting). Standing on a hit, each of its persons has things before it and things
after it on that person's own line. Counted per place on the line, -1 the thing just before, +1
the thing just after, out to three places each way (a thing counts at its nearest place on a
side): how many such things a start has, how often they hold a cited record, and the same for
those not already handed over. The lines hold the things under all the scope's parents.

  1  the start: the first hit of the order | the hits both sides put in their first cluster |
     every hit | a thing that is not a hit (the comparison: is it the hit, or where the cited
     things lie in time anyway); each for every start, and apart for the starts that hold a
     cited record and those that do not (that split has the gold in it)
  2  where in the product's time the things lie, 0 the first thing and 1 the last: the cited
     things, the hits, all things (the middle one of each)
  3  from every hit, by the kind of the start and by the kind of the thing reached: before
     against after
  4  the same question for chunks, by pointer: the chunk right above and the chunk right under
     a well-hit chunk in its own parent (in the order of time), all of them and those where a
     person of the hit chunk also takes part
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
STARTS = ("the first hit", "the hits in both first clusters", "every hit", "a thing that is not a hit")
WHICH = ("every start", "the start holds a cited record", "the start holds none")
PLACES = (-3, -2, -1, 1, 2, 3)
KIND_OF = {"slack": "a conversation", "prs": "a pull request", "documents": "a document", "meeting_transcripts": "a meeting"}
ids_of = {name: {json.loads(line)["id"] for line in (REPO / "data" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
                 if line.strip()} for name in ("gold100", "heldout100")}
every = HQ.load_questions()
fresh = sorted((q for q in every if q.id not in ids_of["gold100"] | ids_of["heldout100"] and q.citations), key=lambda q: q.id)
SETS = {"the gold hundred": [q for q in every if q.id in ids_of["gold100"]],
        "100 unused questions": random.Random(20261011).sample(fresh, 300)[:100]}
p = V.prepare_over_corpus("the direction from a hit")
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


def who_and_when(rec_kind, rec):
    """The persons of one record and its time in seconds; no time for a kind that has none."""
    if rec_kind == "slack":
        user = rec["Message"]["User"]
        return {user["userId"]}, seconds(user["timestamp"])
    if rec_kind == "prs":
        return {rec["user"]["login"]} | {v["user"]["login"] for v in rec["reviews"]}, seconds(rec["created_at"])
    if rec_kind == "documents":
        return {rec["author"]}, seconds(rec["date"])
    if rec_kind == "meeting_transcripts":
        return set(rec["participants"]), seconds(rec["date"])
    return set(), None


def the_things(q, P, inside, place, scoped, step_at):
    cites = {str(c) for c in q.citations}
    things, of_talk, of_record = [], {}, {}
    for i in sorted(inside.tolist(), key=lambda i: (parents[i], int(id_rank[i]))):
        for r in (r for r in records[i] if not TI.apart(r, P)):
            rec_kind, rec = P["raw"][r]
            who, when = who_and_when(rec_kind, rec)
            if kinds[i] == "slack_thread_batch":
                t = P["talk_of"][r]
                if t not in of_talk:
                    of_talk[t] = len(things)
                    things.append({"records": [], "chunks": [], "part": False, "who": set(), "when": None, "from": True,
                                   "kind": KIND_OF["slack"]})
                thing = things[of_talk[t]]
                thing["records"].append(r)
                thing["who"] |= who
                thing["when"] = when if thing["when"] is None else min(thing["when"], when)
            else:
                if r not in of_record:
                    of_record[r] = len(things)
                    things.append({"records": [r], "chunks": [], "part": False, "who": who, "when": when,
                                   "from": rec_kind != "meeting_transcripts", "kind": KIND_OF.get(rec_kind, "another kind")})
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
        thing["step"] = min(step_at[c] for c in thing["chunks"])
        thing["cited"] = bool(cites & set(thing["records"]))
    return things, cites


def chunk_sides(inside, P, kept={}):
    """Per chunk of the border its own records, its persons and its first time; and the chunk right above and right
    under it in its own parent, in the order of time."""
    key = (int(inside[0]), int(inside[-1]), int(inside.size))
    if key not in kept:
        info = {}
        for i in inside.tolist():
            own = [r for r in records[i] if not TI.apart(r, P)]
            who, when = set(), None
            for r in own:
                w, t = who_and_when(*P["raw"][r])
                who |= w
                if t is not None:
                    when = t if when is None else min(when, t)
            if own and when is not None:
                info[i] = {"own": set(own), "who": who - P["everywhere"], "when": when}
        by_parent = defaultdict(list)
        for i in info:
            by_parent[parents[i]].append(i)
        above, under = {}, {}
        for line in by_parent.values():
            line.sort(key=lambda i: (info[i]["when"], int(id_rank[i])))
            for a, b in zip(line, line[1:]):
                under[a], above[b] = b, a
        kept[key] = (info, above, under)
    return kept[key]


for label, drawn in SETS.items():
    cell = {(s, c): {"starts": 0, **{d: [0, 0, 0, 0] for d in PLACES}} for s in STARTS for c in WHICH}
    lies = {"the cited things": [], "the hits": [], "all things": []}
    by_start = defaultdict(lambda: {-1: [0, 0], 1: [0, 0]})
    by_reached = defaultdict(lambda: {-1: [0, 0], 1: [0, 0]})
    chunk_level = {s: {side: [0, 0, 0, 0] for side in ("above", "under")}
                   for s in ("the first chunk of the order", "the chunks in both first clusters")}
    for q in drawn:
        border, scope_said = V.scope_by_name(q.question, p.tree, n_chunks)
        names = scope_said["names_in_the_question"]
        if len(names) != 1:
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
        step_at = dict(zip(inside.tolist(), step.tolist()))
        things, cites = the_things(q, P, inside, place, scoped, step_at)
        used, seen, handed = 0, set(), []
        for i in sorted(range(len(things)), key=lambda i: (things[i]["place"], i)):
            thing = things[i]
            if not thing["part"] and not [r for r in thing["records"] if r not in seen]:
                continue
            if used + thing["chars"] > BUDGET:
                break
            used += thing["chars"]
            seen.update(thing["records"])
            handed.append(i)
        held = set(handed)
        timed = sorted((i for i in range(len(things)) if things[i]["when"] is not None), key=lambda i: (things[i]["when"], i))
        for at, i in enumerate(timed):
            share = at / max(len(timed) - 1, 1)
            lies["all things"].append(share)
            if things[i]["cited"]:
                lies["the cited things"].append(share)
            if i in held:
                lies["the hits"].append(share)
        lines = defaultdict(list)
        for i, thing in enumerate(things):
            if thing["when"] is not None and thing["scope"]:
                for person in thing["who"]:
                    lines[person].append(i)
        where = defaultdict(list)
        for key, line in lines.items():
            line.sort(key=lambda i: (things[i]["when"], i))
            for at, i in enumerate(line):
                where[i].append((key, at))
        starts = {STARTS[0]: handed[:1], STARTS[1]: [a for a in handed if things[a]["step"] == 2], STARTS[2]: handed,
                  STARTS[3]: [i for i in where if i not in held]}
        for name, chosen in starts.items():
            for s in chosen:
                if not things[s]["from"] or s not in where:
                    continue
                found = {}
                for sign in (-1, 1):
                    taken_here = {s}
                    for d in (1, 2, 3):
                        got = set()
                        for key, at in where[s]:
                            j = at + sign * d
                            if 0 <= j < len(lines[key]):
                                got.add(lines[key][j])
                        found[sign * d] = got - taken_here
                        taken_here |= got
                for which in (WHICH[0], WHICH[1] if things[s]["cited"] else WHICH[2]):
                    row = cell[(name, which)]
                    row["starts"] += 1
                    for d in PLACES:
                        row[d][0] += len(found[d])
                        row[d][1] += sum(things[b]["cited"] for b in found[d])
                        new = [b for b in found[d] if b not in held]
                        row[d][2] += len(new)
                        row[d][3] += sum(things[b]["cited"] for b in new)
                if name == STARTS[2]:
                    for sign in (-1, 1):
                        for d in (1, 2, 3):
                            for b in found[sign * d]:
                                for tally in (by_start[things[s]["kind"]], by_reached[things[b]["kind"]]):
                                    tally[sign][0] += 1
                                    tally[sign][1] += things[b]["cited"]
        info, above, under = chunk_sides(inside, P)
        first_chunk = next((i for i in ordered if i in info), None)
        for name, chosen in (("the first chunk of the order", [] if first_chunk is None else [first_chunk]),
                             ("the chunks in both first clusters", [i for i in ordered if step_at[i] == 2 and i in info])):
            for c in chosen:
                for side, other in (("above", above.get(c)), ("under", under.get(c))):
                    if other is None:
                        continue
                    row = chunk_level[name][side]
                    hit = bool(cites & info[other]["own"])
                    row[0] += 1
                    row[1] += hit
                    if info[c]["who"] & info[other]["who"]:
                        row[2] += 1
                        row[3] += hit
    print(f"\n==== {label} ====")
    print("1: per place on the person's line (-1 just before the start, +1 just after): things a start | of them holding a cited record "
          "| of those not already handed over, holding one")
    for name in STARTS:
        for which in WHICH:
            row = cell[(name, which)]
            n = max(row["starts"], 1)
            said = " ; ".join(f"{d:+d}: {row[d][0] / n:.1f} | {row[d][1] / max(row[d][0], 1):3.0%} | {row[d][3] / max(row[d][2], 1):3.0%}"
                              for d in PLACES)
            before = [sum(row[d][k] for d in (-3, -2, -1)) for k in range(4)]
            after = [sum(row[d][k] for d in (1, 2, 3)) for k in range(4)]
            print(f"   {name} / {which} ({row['starts']} starts)\n      {said}\n      the three before together: "
                  f"{before[1] / max(before[0], 1):.0%} cited ({before[1]} of {before[0]}), not handed over {before[3] / max(before[2], 1):.0%} "
                  f"({before[3]} of {before[2]}) ; the three after together: {after[1] / max(after[0], 1):.0%} cited ({after[1]} of "
                  f"{after[0]}), not handed over {after[3] / max(after[2], 1):.0%} ({after[3]} of {after[2]})")
    print("2: where in the product's time the things lie (0 the first thing, 1 the last), the middle one: "
          + " ; ".join(f"{name} {np.median(x):.2f} ({len(x)})" for name, x in lies.items()))
    print("3: from every hit, the three places before against the three after, share holding a cited record")
    for title, tally in (("by the kind of the start", by_start), ("by the kind of the thing reached", by_reached)):
        print(f"   {title}: " + " ; ".join(
            f"{kind}: before {t[-1][1] / max(t[-1][0], 1):.0%} ({t[-1][0]}), after {t[1][1] / max(t[1][0], 1):.0%} ({t[1][0]})"
            for kind, t in sorted(tally.items())))
    print("4: chunks by pointer in their own parent: the chunk right above | the chunk right under: how many, share holding a cited "
          "record ; where a person of the hit chunk also takes part: how many, share")
    for name, sides in chunk_level.items():
        print(f"   {name}: " + " | ".join(
            f"{side} {row[0]}, {row[1] / max(row[0], 1):.0%} ; same person {row[2]}, {row[3] / max(row[2], 1):.0%}"
            for side, row in sides.items()))
print("done", flush=True)

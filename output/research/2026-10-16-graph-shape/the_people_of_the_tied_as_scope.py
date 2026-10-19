"""Following his 2026-10-16 "this is worth digging into way more" (the handed-over texts that the
same people's timeline ties together are right more often). The use to count (the partner's
reading, mine to put to him): the people of those tied texts gauge an area, the way the arm's
scope gauges one from the parents of its first hits. Fixed before the count:

  the tied texts     the handed-over chunks whose things a person's line in time joins to another
                     handed-over chunk's things (as in `the_people_line_first.py`)
  their people       everyone taking part in their things, less the people who take part in very
                     many things of the product (each person's count of things, log, cut in two by
                     `levels`; the upper cluster left out, so one heavy poster does not join it all)
  the people's area  the chunks of the border with a thing one of those people takes part in

Each used as the arm uses its own scope, weight and not a cut (inside a step the chunks in scope
first), in place of the arm's parents, together with them (both), or beside them (either). Per
scope: chunks in it a question, the share of them holding a cited record, and through the arm's
`_hand_over` the first text, a cited record among the first three, context_recall_id. The gold
hundred (the arm's own run, cached first calls, facets off) and the first hundred of the seeded
draw of the unused questions (the order from the question alone). No model call. The raw records
are read through `ties.product`, which never reads a product's question keys. The gold ids are
read inside; numbers only.
"""
import json
import os
import random
import sys
import warnings
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test"),
                str(REPO / "output" / "research" / "2026-10-11-missed-and-floated" / "first_gold_rounds")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"
os.environ["HERB_V4_FACETS"] = "off"
os.environ.pop("HERB_V4_SCOPE_STEP", None)

import ties as TI  # noqa: E402
from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

BUDGET = 72000
CLUSTERS = 5
ids_of = {name: {json.loads(line)["id"] for line in (REPO / "data" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
                 if line.strip()} for name in ("gold100", "heldout100")}
every = HQ.load_questions()
fresh = sorted((q for q in every if q.id not in ids_of["gold100"] | ids_of["heldout100"] and q.citations), key=lambda q: q.id)
SETS = (("the gold hundred", [q for q in every if q.id in ids_of["gold100"]]),
        ("100 unused questions", random.Random(20261011).sample(fresh, 300)[:100]))
p = V.prepare_over_corpus("the people of the tied as scope")
layer, n = p.layer, len(p.chunk_ids)
id_rank, tag_e, chunk_e = layer["edge_tag"], layer["edge_chunk"], layer["id_rank"]
parents = [str(row["parent"]) for row in p.chunk_rows]
product_of = [name.split(".")[1] for name in parents]
parent_ids = {name: k for k, name in enumerate(sorted(set(parents)))}
parent_of = np.array([parent_ids[name] for name in parents], dtype=np.int64)
CV = np.asarray(p.chunk_vectors, dtype=np.float64)
TV = np.asarray(p.tag_vectors, dtype=np.float64)
AXES = V._QueryAxes(TV, np.eye(CV.shape[1]))
doc_cache = {}
records = [[str(x) for x in _resolve_chunk(row, doc_cache)[1]] for row in p.chunk_rows]
print("prepared", flush=True)


def seconds(stamp):
    return (datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).replace(tzinfo=None) - datetime(1970, 1, 1)).total_seconds()


def things_of(P, inside):
    things, of_talk, thing_of = [], {}, {}
    for i in inside.tolist():
        for r in (r for r in records[i] if not TI.apart(r, P)):
            if r in thing_of:
                continue
            if r in P["talk_of"]:
                t = P["talk_of"][r]
                if t not in of_talk:
                    of_talk[t] = len(things)
                    things.append({"who": set(), "when": None, "from": True})
                thing = things[of_talk[t]]
                user = P["raw"][r][1]["Message"]["User"]
                thing["who"].add(user["userId"])
                stamp = seconds(user["timestamp"])
                thing["when"] = stamp if thing["when"] is None else min(thing["when"], stamp)
                thing_of[r] = of_talk[t]
            else:
                rec_kind, rec = P["raw"][r]
                who, when, searched = set(), None, True
                if rec_kind == "prs":
                    who = {rec["user"]["login"]} | {v["user"]["login"] for v in rec["reviews"]}
                    when = seconds(rec["created_at"])
                elif rec_kind == "documents":
                    who, when = {rec["author"]}, seconds(rec["date"])
                elif rec_kind == "meeting_transcripts":
                    who, when, searched = set(rec["participants"]), seconds(rec["date"]), False
                thing_of[r] = len(things)
                things.append({"who": who, "when": when, "from": searched})
    for thing in things:
        thing["who"] -= P["everywhere"]
    return things, thing_of


def points(things):
    lines = defaultdict(list)
    for k, thing in enumerate(things):
        if thing["when"] is not None:
            for person in thing["who"]:
                lines[person].append(k)
    out = [set() for _ in things]
    for line in lines.values():
        line.sort(key=lambda k: (things[k]["when"], k))
        for a, b in zip(line, line[1:]):
            if things[a]["from"]:
                out[a].add(b)
            if things[b]["from"]:
                out[b].add(a)
    return out


def standing(x):
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


def closest_tag(vector):
    row = vector @ TV.T
    out = np.full(n, float(row.min()))
    np.maximum.at(out, chunk_e, row[tag_e])
    return out


def score(id_lists, context_ids, cites):
    got = {str(x) for x in context_ids}
    whole = [u for u in ([str(x) for x in unit] for unit in id_lists if unit) if set(u) <= got]
    return (bool(whole and set(whole[0]) & cites), any(set(u) & cites for u in whole[:3]), len(cites & got) / len(cites))


captured = {}
the_hand, the_combo = V._hand_over, WK.cloud_combo


def hand_rec(order, prepared, char_budget, k, cache):
    out = the_hand(order, prepared, char_budget, k, cache)
    captured["order"] = list(order)
    return out


def combo_rec(*a, **kw):
    out = the_combo(*a, **kw)
    captured["combo"] = out
    return out


SCOPES = ("the arm", "the people's area", "both", "either")
for label, drawn in SETS:
    rows = {v: [] for v in SCOPES}
    size, cited_in = defaultdict(list), defaultdict(lambda: [0, 0])
    used = skipped = 0
    for q in drawn:
        cites = {str(c) for c in q.citations}
        border, said = V.scope_by_name(q.question, p.tree, n)
        names = said["names_in_the_question"]
        if len(names) != 1:
            skipped += 1
            continue
        inside = np.flatnonzero(border)
        if label == "the gold hundred":
            V._hand_over, WK.cloud_combo = hand_rec, combo_rec
            V.answer_one_question((q.id, q.question), p, None, 50, BUDGET)
            V._hand_over, WK.cloud_combo = the_hand, the_combo
            order, combo = captured["order"], captured["combo"]
            step, value, arm_scope = combo["step"], combo["value"], combo["in_scope"]
        else:
            vector = np.asarray(V._query_cosines(V._without_names(q.question, names), [], AXES)[0]["query_description_cosines"],
                                dtype=np.float64)
            D, T = (CV @ vector)[inside], closest_tag(vector)[inside]
            step, value, arm_scope = np.zeros(n, dtype=np.int64), np.zeros(n), np.zeros(n, dtype=bool)
            step[inside] = WK.levels(D, CLUSTERS) + WK.levels(T, CLUSTERS)
            value[inside] = standing(D) + standing(T)
            taken = WK.majority_scopes(step[inside] <= max(3, int(step[inside].min())), parent_of[inside])
            arm_scope[inside] = np.isin(parent_of[inside], taken)
            order = inside[np.lexsort((id_rank[inside], -value[inside], ~arm_scope[inside], step[inside]))].tolist()
        used += 1
        out = V._hand_over(order, p, BUDGET, 50, doc_cache)
        delivered = [int(c) for c in out[4]]
        P = TI.product(product_of[int(inside[0])])
        things, thing_of = things_of(P, inside)
        pointed = points(things)
        degree = Counter(person for thing in things for person in thing["who"])
        people_all = sorted(degree)
        heavy = set()
        if len(people_all) > 2:
            lv = WK.levels(np.log([degree[x] for x in people_all]), 2)
            heavy = {x for x, l in zip(people_all, lv.tolist()) if l == 1}
        chunk_things = {c: {thing_of[r] for r in records[c] if r in thing_of} for c in inside.tolist()}
        handed = set().union(*(chunk_things[c] for c in delivered)) if delivered else set()
        tied = [c for c in delivered
                if any((pointed[a] & (handed - chunk_things[c])) or any(a in pointed[b] for b in handed - chunk_things[c])
                       for a in chunk_things[c])]
        crowd = set().union(*(things[a]["who"] for c in tied for a in chunk_things[c])) - heavy if tied else set()
        people_area = np.zeros(n, dtype=bool)
        for c in inside.tolist():
            people_area[c] = any(things[a]["who"] & crowd for a in chunk_things[c])
        flags = {"the arm": arm_scope, "the people's area": people_area, "both": arm_scope & people_area,
                 "either": arm_scope | people_area}
        gold = np.array([bool(cites & set(records[c])) for c in inside.tolist()])
        for v in SCOPES:
            f = flags[v][inside]
            size[v].append(int(f.sum()))
            cited_in[v][0] += int(f.sum())
            cited_in[v][1] += int(gold[f].sum())
            by = np.lexsort((id_rank[inside], -value[inside], ~f, step[inside]))
            o = V._hand_over(inside[by].tolist(), p, BUDGET, 50, doc_cache)
            rows[v].append(score(o[1], o[2], cites))
    m = used
    base = np.array(rows["the arm"], dtype=float)
    print(f"\n{label}: {m} questions ({skipped} left out)")
    for v in SCOPES:
        r = np.array(rows[v], dtype=float)
        d = r[:, 2] - base[:, 2]
        print(f"  {v:18s}: {np.mean(size[v]):6.1f} chunks in scope a question, {cited_in[v][1] / max(cited_in[v][0], 1):5.1%} of them cited |"
              f" top text {r[:, 0].sum():3.0f} | among the first three {r[:, 1].sum():3.0f} | context_recall_id {r[:, 2].mean():.3f}"
              f" ({d.mean():+.3f}, se {d.std(ddof=1) / np.sqrt(m):.3f}, {int((d > 0).sum())} up {int((d < 0).sum())} down)")
print("done", flush=True)

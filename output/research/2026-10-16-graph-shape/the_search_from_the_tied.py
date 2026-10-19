"""His 2026-10-16 "why are you starting on a "wrong hit" ?", after the people's lines in time were
shown to tie together the handed-over texts that are right more often (`the_people_line_first.py`).
So the search starts only from those: the handed-over chunks whose things a person's line in time
joins to another handed-over chunk's things (no gold in that). From them the same lines are
followed (each thing points at the person's thing just before and just after) to things that are
not handed over. Fixed before the count (mine):
  the arm              the arm's order through its own hand-over
  from the tied        the tied handed-over chunks, then the chunks holding what they point at,
                       then the handed-over chunks that are not tied, then the rest of the order
  from every hit       the same, the search started from every handed-over chunk (the check)
Per set: the first text, a cited record among the first three, context_recall_id, and how many
chunks the search reaches a question and how often they hold a cited record. The gold hundred
(the arm's own run, cached first calls, facets off) and the first hundred of the seeded draw of
the unused questions (the order from the question alone). No model call. The raw records are read
through `ties.product`, which never reads a product's question keys. The gold ids are read inside;
numbers only.
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
p = V.prepare_over_corpus("the people line first")
layer, n = p.layer, len(p.chunk_ids)
id_rank, tag_e, chunk_e = layer["id_rank"], layer["edge_tag"], layer["edge_chunk"]
parents = [str(row["parent"]) for row in p.chunk_rows]
product_of = [name.split(".")[1] for name in parents]
parent_ids = {name: k for k, name in enumerate(sorted(set(parents)))}
parent_of = np.array([parent_ids[name] for name in parents], dtype=np.int64)
CV = np.asarray(p.chunk_vectors, dtype=np.float64)
TV = np.asarray(p.tag_vectors, dtype=np.float64)
AXES = V._QueryAxes(TV, np.eye(CV.shape[1]))
doc_cache = {}
records = []
for row in p.chunk_rows:
    records.append([str(x) for x in _resolve_chunk(row, doc_cache)[1]])
print("prepared", flush=True)


def seconds(stamp):
    return (datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).replace(tzinfo=None) - datetime(1970, 1, 1)).total_seconds()


def things_of(P, inside):
    """The product's own records inside the border as things, each with its persons and its time
    (as `the_things` of 10-13 makes them). Returns the things and per record its thing."""
    things, of_talk, of_record, thing_of = [], {}, {}, {}
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
                of_record[r] = len(things)
                things.append({"who": who, "when": when, "from": searched})
                thing_of[r] = of_record[r]
    for thing in things:
        thing["who"] -= P["everywhere"]
    return things, thing_of


def points(things):
    """Product-wide lines: per person the things in the order of time; each thing points at the
    person's thing just before and just after (only things that search point)."""
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


def first_and_three(units, cites):
    return (bool(units and set(units[0]) & cites), any(set(u) & cites for u in units[:3]))


captured = {}
the_hand = V._hand_over


def hand_rec(order, prepared, char_budget, k, cache):
    out = the_hand(order, prepared, char_budget, k, cache)
    captured["out"], captured["order"] = out, list(order)
    return out


def score(id_lists, context_ids, cites):
    got = {str(x) for x in context_ids}
    whole = [u for u in ([str(x) for x in unit] for unit in id_lists if unit) if set(u) <= got]
    return (bool(whole and set(whole[0]) & cites), any(set(u) & cites for u in whole[:3]), len(cites & got) / len(cites))


VARIANTS = ("the arm", "from the tied", "from every hit")
for label, drawn in SETS:
    rows = {v: [] for v in VARIANTS}
    reach = {v: [0, 0] for v in VARIANTS[1:]}
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
            V._hand_over = hand_rec
            V.answer_one_question((q.id, q.question), p, None, 50, BUDGET)
            V._hand_over = the_hand
            order = captured["order"]
        else:
            vector = np.asarray(V._query_cosines(V._without_names(q.question, names), [], AXES)[0]["query_description_cosines"],
                                dtype=np.float64)
            D, T = (CV @ vector)[inside], closest_tag(vector)[inside]
            step = WK.levels(D, CLUSTERS) + WK.levels(T, CLUSTERS)
            z = standing(D) + standing(T)
            taken = WK.majority_scopes(step <= max(3, int(step.min())), parent_of[inside])
            in_scope = np.isin(parent_of[inside], taken)
            order = inside[np.lexsort((id_rank[inside], -z, ~in_scope, step))].tolist()
        used += 1
        out = V._hand_over(order, p, BUDGET, 50, doc_cache)
        rows["the arm"].append(score(out[1], out[2], cites))
        delivered = [int(c) for c in out[4]]
        P = TI.product(product_of[int(inside[0])])
        things, thing_of = things_of(P, inside)
        pointed = points(things)
        chunk_things = {c: {thing_of[r] for r in records[c] if r in thing_of} for c in inside.tolist()}
        holders = defaultdict(set)
        for c, ts in chunk_things.items():
            for t in ts:
                holders[t].add(c)
        handed = set().union(*(chunk_things[c] for c in delivered)) if delivered else set()
        tied = {c for c in delivered
                if any((pointed[a] & (handed - chunk_things[c])) or any(a in pointed[b] for b in handed - chunk_things[c])
                       for a in chunk_things[c])}
        for v, start in (("from the tied", [c for c in delivered if c in tied]), ("from every hit", delivered)):
            got_things = set().union(*(pointed[a] for c in start for a in chunk_things[c])) - handed if start else set()
            reached = {c for t in got_things for c in holders[t]} - set(delivered)
            reach[v][0] += len(reached)
            reach[v][1] += sum(1 for c in reached if cites & set(records[c]))
            first = [c for c in order if c in tied] if v == "from the tied" else [c for c in order if c in set(delivered)]
            loose = [c for c in order if c in set(delivered) and c not in tied] if v == "from the tied" else []
            new = first + [c for c in order if c in reached] + loose
            seen = set(new)
            new += [c for c in order if c not in seen]
            o = V._hand_over(new, p, BUDGET, 50, doc_cache)
            rows[v].append(score(o[1], o[2], cites))
    m = len(rows["the arm"])
    base = np.array(rows["the arm"], dtype=float)
    print()
    print(f"{label}: {m} questions ({skipped} left out)")
    for v in VARIANTS:
        r = np.array(rows[v], dtype=float)
        d = r[:, 2] - base[:, 2]
        extra = (f" | reached {reach[v][0] / m:4.1f} a question, {reach[v][1] / max(reach[v][0], 1):5.1%} cited"
                 if v in reach else "")
        print(f"  {v:15s}: top text {r[:, 0].sum():3.0f} | among the first three {r[:, 1].sum():3.0f} | context_recall_id "
              f"{r[:, 2].mean():.3f} ({d.mean():+.3f}, se {d.std(ddof=1) / np.sqrt(m):.3f}, {int((d > 0).sum())} up "
              f"{int((d < 0).sum())} down){extra}")
print("done", flush=True)

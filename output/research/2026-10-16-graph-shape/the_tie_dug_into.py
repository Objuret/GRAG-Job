"""His 2026-10-16 "this is worth digging into way more", on: the handed-over texts that the same
people's timeline ties to another handed-over text hold a cited record 33% against 19% (unused
43% against 26%) (`the_people_line_first.py`). The lines as there: per person (posters, a pull
request's author and reviewers, a document's author, a meeting's participants; the one who posts
everywhere left out) the things they take part in, in the order of time; a thing points at the
person's thing just before and just after (a meeting is pointed at, not from). Fixed before the
count (mine):

A. Why, inside what is handed over: a handed-over chunk is tied when one of its things and a
   thing of another handed-over chunk point at each other. Tied against untied, the share that
   holds a cited record, split by
     the kind of record of the chunk
     the chunk's step in the arm's order
     how many other handed-over chunks it is tied to (1, 2, 3 or more)
     the people in its things (1 to 2, 3 to 4, 5 or more), since more people give more chances
     the tie: through the same parent only, across parents
B. Before the cut: the chunks of the border that are not handed over, per step, tied (one of
   their things points at or is pointed at by a handed-over thing) against untied.
C. A re-cut from it: the tied handed-over chunks, then the tied chunks below the cut in the arm's
   order, then the untied handed-over chunks, then the rest; and the same with only the tied
   chunks of the steps the cut falls in. Through the arm's `_hand_over`.

The gold hundred (the arm's own run, cached first calls, facets off) and the first hundred of the
seeded draw of the unused questions (the order from the question alone). No model call. The raw
records are read through `ties.product`, which never reads a product's question keys. The gold
ids are read inside; numbers only.
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
p = V.prepare_over_corpus("the tie dug into")
layer, n = p.layer, len(p.chunk_ids)
id_rank, tag_e, chunk_e = layer["id_rank"], layer["edge_tag"], layer["edge_chunk"]
parents = [str(row["parent"]) for row in p.chunk_rows]
kinds = [str(row["kind"]) for row in p.chunk_rows]
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
                    things.append({"who": set(), "when": None, "from": True, "home": parents[i]})
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
                things.append({"who": who, "when": when, "from": searched, "home": parents[i]})
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
    captured["step"] = np.asarray(out["step"]).copy()
    return out


def band_people(k):
    return "1 to 2 people" if k <= 2 else ("3 to 4 people" if k <= 4 else "5 people or more")


VARIANTS = ("the arm", "re-cut", "re-cut, the cut's steps only")
for label, drawn in SETS:
    A, B = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    rows = {v: [] for v in VARIANTS}
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
            order, step = captured["order"], captured["step"]
        else:
            vector = np.asarray(V._query_cosines(V._without_names(q.question, names), [], AXES)[0]["query_description_cosines"],
                                dtype=np.float64)
            D, T = (CV @ vector)[inside], closest_tag(vector)[inside]
            step = np.zeros(n, dtype=np.int64)
            step[inside] = WK.levels(D, CLUSTERS) + WK.levels(T, CLUSTERS)
            z = standing(D) + standing(T)
            taken = WK.majority_scopes(step[inside] <= max(3, int(step[inside].min())), parent_of[inside])
            in_scope = np.isin(parent_of[inside], taken)
            order = inside[np.lexsort((id_rank[inside], -z, ~in_scope, step[inside]))].tolist()
        used += 1
        out = V._hand_over(order, p, BUDGET, 50, doc_cache)
        rows["the arm"].append(score(out[1], out[2], cites))
        delivered = [int(c) for c in out[4]]
        dset = set(delivered)
        P = TI.product(product_of[int(inside[0])])
        things, thing_of = things_of(P, inside)
        pointed = points(things)
        chunk_things = {c: {thing_of[r] for r in records[c] if r in thing_of} for c in inside.tolist()}
        owner = defaultdict(set)
        for c in delivered:
            for t in chunk_things[c]:
                owner[t].add(c)
        handed = set(owner)

        def partners(c):
            """The handed-over chunks (other than c) whose things are joined to c's things."""
            got = set()
            for a in chunk_things[c]:
                for b in pointed[a]:
                    if b in handed:
                        got |= owner[b]
                for b in handed:
                    if a in pointed[b]:
                        got |= owner[b]
            return got - {c}

        tied_d = {}
        for c in delivered:
            ps = partners(c)
            tied_d[c] = ps
            g = int(bool(cites & set(records[c])))
            t = bool(ps)
            people = len(set().union(*(things[a]["who"] for a in chunk_things[c]))) if chunk_things[c] else 0
            same_parent_only = t and all(parents[o] == parents[c] for o in ps)
            for key in (("kind", kinds[c]), ("step", f"step {int(step[c])}"),
                        ("people", band_people(people)),
                        ("ties", "not tied" if not t else ("tied to 1" if len(ps) == 1 else "tied to 2" if len(ps) == 2 else "tied to 3 or more")),
                        ("where", "not tied" if not t else ("tied inside its parent only" if same_parent_only else "tied across parents"))):
                cell = A[(key[0], key[1], t)] if key[0] in ("kind", "step", "people") else A[(key[0], key[1], None)]
                cell[0] += 1
                cell[1] += g
        tied_c = set()
        for c in order:
            if c in dset:
                continue
            t = bool(partners(c))
            g = int(bool(cites & set(records[c])))
            B[(int(step[c]), t)][0] += 1
            B[(int(step[c]), t)][1] += g
            if t:
                tied_c.add(c)
        cut_steps = {int(step[c]) for c in delivered}
        for v in VARIANTS[1:]:
            pick = tied_c if v == "re-cut" else {c for c in tied_c if int(step[c]) in cut_steps}
            first = [c for c in order if c in dset and tied_d[c]]
            new = first + [c for c in order if c in pick] + [c for c in order if c in dset and not tied_d[c]]
            seen = set(new)
            new += [c for c in order if c not in seen]
            o = V._hand_over(new, p, BUDGET, 50, doc_cache)
            rows[v].append(score(o[1], o[2], cites))
    m = used
    print(f"\n{label}: {m} questions ({skipped} left out)")
    print("  A. inside what is handed over (chunks a question, share holding a cited record):")
    for group in ("kind", "step", "people"):
        for value in sorted({k[1] for k in A if k[0] == group}):
            t, u = A[(group, value, True)], A[(group, value, False)]
            print(f"    {value:22s}: tied {t[0] / m:4.1f}/q {t[1] / max(t[0], 1):5.1%} | not tied {u[0] / m:4.1f}/q {u[1] / max(u[0], 1):5.1%}")
    for group in ("ties", "where"):
        cells = sorted((k for k in A if k[0] == group), key=lambda k: k[1])
        print("    " + " | ".join(f"{k[1]} {A[k][0] / m:4.1f}/q {A[k][1] / max(A[k][0], 1):5.1%}" for k in cells))
    print("  B. below the cut, per step (chunks a question, share holding a cited record):")
    for s in sorted({k[0] for k in B}):
        t, u = B[(s, True)], B[(s, False)]
        print(f"    step {s:2d}: tied {t[0] / m:5.1f}/q {t[1] / max(t[0], 1):5.1%} | not tied {u[0] / m:5.1f}/q {u[1] / max(u[0], 1):5.1%}")
    base = np.array(rows["the arm"], dtype=float)
    print("  C.")
    for v in VARIANTS:
        r = np.array(rows[v], dtype=float)
        d = r[:, 2] - base[:, 2]
        print(f"    {v:30s}: top text {r[:, 0].sum():3.0f} | among the first three {r[:, 1].sum():3.0f} | context_recall_id "
              f"{r[:, 2].mean():.3f} ({d.mean():+.3f}, se {d.std(ddof=1) / np.sqrt(m):.3f}, {int((d > 0).sum())} up {int((d < 0).sum())} down)")
print("done", flush=True)

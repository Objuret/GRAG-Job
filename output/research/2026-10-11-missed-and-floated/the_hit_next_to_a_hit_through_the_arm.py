"""One yes-or-no put into the arm's order, run through the arm's own delivery beside the arm as it
stands (his 2026-10-13 "Soo.." to: "inside a step, a hit standing next to another hit comes
first"). A side run: the arm's file is not changed. No model call (HERB_V4_OFFLINE=on; the
hundred uses the cached first calls through `answer_one_question`, the unused questions have no
query tags and read the tags' side with the question itself).

  a hit          a chunk the scope is gauged from: the chunks on the combo's first two steps
                 (`v4_walk.cloud_combo`), no number added here
  next to        by pointer: the chunk right above or right under it in its parent (`ordinal`)
                 is a hit too
                 by the same people in time: one of its things (a conversation, an own pull
                 request, a document, a meeting) stands just before or just after a thing of
                 another hit on the line of a person who takes part in both, the lines holding
                 the things under the scope's parents
  where it goes  inside a step: the step, then in scope, then the yes-or-no, then the value
                 first of all: the yes-or-no, then the step, in scope, the value
  handed over    `artefact_v4._hand_over` (the product's own work, conversations whole), the
                 harness's cut at 72,000 characters

Printed per set: top text holds a cited record | a cited record among the first three texts |
context_recall_id (share of the cited records delivered inside 72,000 characters), and against
the arm as it stands: mean difference (standard error), questions higher / lower. The gold ids
are read inside; numbers only.
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
os.environ.pop("HERB_V4_SCOPE_STEP", None)

import ties as TI  # noqa: E402
from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

BUDGET = 72000
NEIGHBOURS = ("by pointer", "by the same people in time")
PLACINGS = ("inside a step", "first of all")
ids_of = {name: [json.loads(line)["id"] for line in (REPO / "data" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
                 if line.strip()] for name in ("gold100", "heldout100")}
every = HQ.load_questions()
by_id = {q.id: q for q in every}
taken_ids = set(ids_of["gold100"]) | set(ids_of["heldout100"])
fresh = sorted((q for q in every if q.id not in taken_ids and q.citations), key=lambda q: q.id)
SETS = {"the gold hundred (the arm's real order, cached first calls)": [by_id[i] for i in ids_of["gold100"]],
        "100 unused questions (no query tags: the tags' side read with the question)": random.Random(20261011).sample(fresh, 300)[:100]}
p = V.prepare_over_corpus("a hit next to a hit through the arm")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
parents = [str(row["parent"]) for row in p.chunk_rows]
parent_ids = {name: k for k, name in enumerate(sorted(set(parents)))}
parent_of = np.array([parent_ids[name] for name in parents], dtype=np.int64)
kinds = [str(row["kind"]) for row in p.chunk_rows]
CV = np.asarray(p.chunk_vectors, dtype=np.float64)
TV = np.asarray(p.tag_vectors, dtype=np.float64)
AXES = V._QueryAxes(TV, np.eye(CV.shape[1]))
doc_cache = {}
records = [[str(x) for x in _resolve_chunk(row, doc_cache)[1]] for row in p.chunk_rows]
by_parent = defaultdict(list)
for i, row in enumerate(p.chunk_rows):
    by_parent[parents[i]].append((row["ordinal"], i))
beside = defaultdict(list)
for line in by_parent.values():
    line.sort()
    for (_, a), (_, b) in zip(line, line[1:]):
        beside[a].append(b)
        beside[b].append(a)
print("prepared", flush=True)

captured = {}
the_arms_combo = WK.cloud_combo


def recording(layer_, cosines, d_near, inside, scope_of, k):
    out = the_arms_combo(layer_, cosines, d_near, inside, scope_of, k)
    captured["combo"], captured["inside"] = out, np.asarray(inside, dtype=np.int64)
    return out


WK.cloud_combo = recording


def seconds(stamp):
    return (datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).replace(tzinfo=None) - datetime(1970, 1, 1)).total_seconds()


def who_and_when(rec_kind, rec):
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


def product_things(inside, P, kept={}):
    """The product's own work inside the border as things: the chunks each lies in, its persons, its time."""
    key = (int(inside[0]), int(inside[-1]), int(inside.size))
    if key not in kept:
        things, of_talk, of_record = [], {}, {}
        for i in sorted(inside.tolist(), key=lambda i: (parents[i], int(id_rank[i]))):
            for r in (r for r in records[i] if not TI.apart(r, P)):
                rec_kind, rec = P["raw"][r]
                who, when = who_and_when(rec_kind, rec)
                if kinds[i] == "slack_thread_batch":
                    t = P["talk_of"][r]
                    if t not in of_talk:
                        of_talk[t] = len(things)
                        things.append({"chunks": [], "who": set(), "when": None, "from": True})
                    thing = things[of_talk[t]]
                    thing["who"] |= who
                    thing["when"] = when if thing["when"] is None else min(thing["when"], when)
                else:
                    if r not in of_record:
                        of_record[r] = len(things)
                        things.append({"chunks": [], "who": who, "when": when, "from": rec_kind != "meeting_transcripts"})
                    thing = things[of_record[r]]
                if i not in thing["chunks"]:
                    thing["chunks"].append(i)
        for thing in things:
            thing["who"] -= P["everywhere"]
        kept[key] = things
    return kept[key]


def next_to(neighbour, hit, in_scope, inside):
    """Per chunk: it is a hit and stands next to another hit."""
    yes = np.zeros(n, dtype=bool)
    if neighbour == NEIGHBOURS[0]:
        for i in np.flatnonzero(hit).tolist():
            yes[i] = any(hit[j] for j in beside[i])
        return yes
    things = product_things(inside, TI.product(parents[int(inside[0])].split(".")[1]))
    is_hit = [any(hit[c] for c in thing["chunks"]) for thing in things]
    lines = defaultdict(list)
    for i, thing in enumerate(things):
        if thing["when"] is not None and any(in_scope[c] for c in thing["chunks"]):
            for person in thing["who"]:
                lines[person].append(i)
    tied = set()
    for line in lines.values():
        line.sort(key=lambda i: (things[i]["when"], i))
        for a, b in zip(line, line[1:]):
            if is_hit[a] and is_hit[b] and (things[a]["from"] or things[b]["from"]):
                tied.update((a, b))
    for i in tied:
        for c in things[i]["chunks"]:
            yes[c] = bool(hit[c])
    return yes


def score(id_lists, context_ids, cites):
    got = {str(x) for x in context_ids}
    whole = [u for u in ([str(x) for x in unit] for unit in id_lists if unit) if set(u) <= got]
    return (bool(whole and set(whole[0]) & cites), any(set(u) & cites for u in whole[:3]), len(cites & got) / len(cites))


for label, drawn in SETS.items():
    real = label.startswith("the gold hundred")
    results = {"the arm as it stands": []}
    reach = {neighbour: [0, 0] for neighbour in NEIGHBOURS}
    for neighbour in NEIGHBOURS:
        for placing in PLACINGS:
            results[f"a hit next to another hit {neighbour}, {placing}"] = []
    for at, q in enumerate(drawn):
        cites = {str(c) for c in q.citations}
        if real:
            out = V.answer_one_question((q.id, q.question), p, None, 50, BUDGET)
            results["the arm as it stands"].append(score(out.meta["chunk_ids"], out.context_ids, cites))
            combo, inside = captured["combo"], captured["inside"]
        else:
            border, said = V.scope_by_name(q.question, p.tree, n)
            inside = np.flatnonzero(border) if border.any() else np.arange(n)
            vector = np.asarray(V._query_cosines(V._without_names(q.question, said["names_in_the_question"]), [], AXES)[0][
                "query_description_cosines"], dtype=np.float64)
            combo = the_arms_combo(layer, np.array([vector @ TV.T]), CV @ vector, inside, parent_of, V._k_nearest())
            _, id_lists, context_ids, _, _, _ = V._hand_over(combo["order"], p, BUDGET, 50, doc_cache)
            results["the arm as it stands"].append(score(id_lists, context_ids, cites))
        step, in_scope, value = combo["step"], combo["in_scope"], combo["value"]
        hit = np.zeros(n, dtype=bool)
        hit[inside[step[inside] <= max(3, int(step[inside].min()))]] = True
        for neighbour in NEIGHBOURS:
            yes = next_to(neighbour, hit, in_scope, inside)
            reach[neighbour][0] += int(hit.sum())
            reach[neighbour][1] += int(yes.sum())
            for placing in PLACINGS:
                keys = ((id_rank[inside], -value[inside], ~yes[inside], ~in_scope[inside], step[inside]) if placing == PLACINGS[0]
                        else (id_rank[inside], -value[inside], ~in_scope[inside], step[inside], ~yes[inside]))
                order = inside[np.lexsort(keys)].tolist()
                _, id_lists, context_ids, _, _, _ = V._hand_over(order, p, BUDGET, 50, doc_cache)
                results[f"a hit next to another hit {neighbour}, {placing}"].append(score(id_lists, context_ids, cites))
        if (at + 1) % 25 == 0:
            print(f"   {at + 1} questions", flush=True)
    count = len(drawn)
    print(f"\n==== {label}: {count} questions ====")
    for neighbour in NEIGHBOURS:
        print(f"hits a question {reach[neighbour][0] / count:.1f}, of them next to another hit {neighbour}: {reach[neighbour][1] / count:.1f}")
    print("top text holds a cited record | a cited record among the first three texts | context_recall_id | against the arm as it "
          "stands: mean difference (standard error), questions higher / lower")
    base = np.array([row[2] for row in results["the arm as it stands"]])
    for name, rows in results.items():
        a = np.array(rows, dtype=np.float64)
        diff = a[:, 2] - base
        print(f"  {int(a[:, 0].sum()):3d} | {int(a[:, 1].sum()):3d} | {a[:, 2].mean():.4f} | {diff.mean():+.3f} "
              f"({diff.std(ddof=1) / np.sqrt(diff.size):.3f}), {int((diff > 1e-9).sum())} / {int((diff < -1e-9).sum())}  {name}")
print("done", flush=True)

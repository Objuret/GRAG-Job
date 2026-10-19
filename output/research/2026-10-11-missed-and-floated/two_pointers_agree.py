"""Two structural pointers from what the arm delivers, and where they agree. After his 2026-10-15
"how the fuck can this not be relevant": the same-role tag links from the delivered chunks reach
4.0 of the 5.7 missed cited chunks a question, but among 69 chunks, and the arm's order does not
pick them out.

  tag pointer      from a delivered chunk through a tag that has the same role on both edges (the
                   facet the edge stands highest in) to another chunk of the border
  people pointer   from a delivered thing (a conversation, an own pull request, a document, a
                   meeting) each of its persons points at the thing they took part in just before
                   and just after, on that person's own line of time over the product's own work
                   (as `the_persons_lines_on_unused_questions.py`); the chunks of that thing
  both             a chunk both pointers reach

Per question on average: how many chunks each reaches (not delivered), how often they hold a
cited record, how many of the missed cited chunks they reach; inside "both", the arm's own order:
the first one, three, five. The arm as it stands, the hundred, cached first calls, no lane call.
The gold ids are read inside; numbers only.
"""
import json
import os
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
wanted = [json.loads(line)["id"] for line in (REPO / "data" / "gold100.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("two pointers agree")
layer, n = p.layer, len(p.chunk_ids)
tag_e, chunk_e, id_rank = layer["edge_tag"], layer["edge_chunk"], layer["id_rank"]
role = np.argmax(layer["pos"][:, 1:], axis=1)
parents = [str(row["parent"]) for row in p.chunk_rows]
kinds = [str(row["kind"]) for row in p.chunk_rows]
edges_of_chunk, edges_of_tag = defaultdict(list), defaultdict(list)
for k, (t, c) in enumerate(zip(tag_e.tolist(), chunk_e.tolist())):
    edges_of_chunk[c].append(k)
    edges_of_tag[t].append(k)
doc_cache = {}
records = [[str(x) for x in _resolve_chunk(row, doc_cache)[1]] for row in p.chunk_rows]
print("prepared", flush=True)


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


def people_pointer(inside, P, kept={}):
    """Per chunk of the border the chunks the people pointer reaches from it (the product's own work, lines over the product)."""
    key = (int(inside[0]), int(inside[-1]), int(inside.size))
    if key in kept:
        return kept[key]
    things, of_talk, of_record = [], {}, {}
    for i in sorted(inside.tolist(), key=lambda i: (parents[i], int(id_rank[i]))):
        for r in (r for r in records[i] if not TI.apart(r, P)):
            rec_kind, rec = P["raw"][r]
            who, when = who_and_when(rec_kind, rec)
            if kinds[i] == "slack_thread_batch":
                t = P["talk_of"][r]
                if t not in of_talk:
                    of_talk[t] = len(things)
                    things.append({"chunks": set(), "who": set(), "when": None, "from": True})
                thing = things[of_talk[t]]
                thing["who"] |= who
                thing["when"] = when if thing["when"] is None else min(thing["when"], when)
            else:
                if r not in of_record:
                    of_record[r] = len(things)
                    things.append({"chunks": set(), "who": who, "when": when, "from": rec_kind != "meeting_transcripts"})
                thing = things[of_record[r]]
            thing["chunks"].add(i)
    for thing in things:
        thing["who"] -= P["everywhere"]
    lines = defaultdict(list)
    for k, thing in enumerate(things):
        if thing["when"] is not None:
            for person in thing["who"]:
                lines[person].append(k)
    points = defaultdict(set)
    for line in lines.values():
        line.sort(key=lambda k: (things[k]["when"], k))
        for at, k in enumerate(line):
            if things[k]["from"]:
                for j in (at - 1, at + 1):
                    if 0 <= j < len(line):
                        points[k].add(line[j])
    of_chunk = defaultdict(set)
    for k, thing in enumerate(things):
        for c in thing["chunks"]:
            of_chunk[c].add(k)
    reach = defaultdict(set)
    for c, ks in of_chunk.items():
        for k in ks:
            for j in points[k]:
                reach[c] |= things[j]["chunks"]
    kept[key] = reach
    return reach


captured = {}
the_combo, the_hand = WK.cloud_combo, V._hand_over


def combo_rec(layer_, cosines, d_near, inside, scope_of, k):
    out = the_combo(layer_, cosines, d_near, inside, scope_of, k)
    captured["combo"], captured["inside"] = out, np.asarray(inside, dtype=np.int64)
    return out


def hand_rec(order, prepared, char_budget, k, cache):
    out = the_hand(order, prepared, char_budget, k, cache)
    captured["delivered"] = list(out[4])
    return out


WK.cloud_combo, V._hand_over = combo_rec, hand_rec
sums = defaultdict(float)
first_k = defaultdict(lambda: [0, 0])
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    V.answer_one_question((qid, q.question), p, None, 50, BUDGET)
    combo, inside, delivered = captured["combo"], captured["inside"], set(captured["delivered"])
    member = np.zeros(n, dtype=bool)
    member[inside] = True
    gold = {i for i in inside.tolist() if cites & set(records[i])}
    missed = gold - delivered
    by_tag = set()
    for s in delivered:
        for e1 in edges_of_chunk[s]:
            for e2 in edges_of_tag[int(tag_e[e1])]:
                c = int(chunk_e[e2])
                if member[c] and c not in delivered and role[e1] == role[e2]:
                    by_tag.add(c)
    reach = people_pointer(inside, TI.product(parents[int(inside[0])].split(".")[1]))
    by_people = set()
    for s in delivered:
        by_people |= {c for c in reach.get(s, set()) if member[c] and c not in delivered}
    both = by_tag & by_people
    sums["missed cited chunks"] += len(missed)
    for label, found in (("the tag pointer", by_tag), ("the people pointer", by_people), ("both", both)):
        sums[(label, "reached")] += len(found)
        sums[(label, "cited")] += len(found & gold)
        sums[(label, "missed reached")] += len(found & missed)
    place = {c: at for at, c in enumerate(combo["order"])}
    ranked = sorted(both, key=lambda c: place[c])
    for k in (1, 3, 5):
        first_k[k][0] += len(ranked[:k])
        first_k[k][1] += sum(1 for c in ranked[:k] if c in gold)
WK.cloud_combo, V._hand_over = the_combo, the_hand

count = len(wanted)
print(f"\nmissed cited chunks a question: {sums['missed cited chunks'] / count:.1f}")
print("pointer | chunks reached a question (not delivered) | of them holding a cited record | of the missed cited chunks, reached")
for label in ("the tag pointer", "the people pointer", "both"):
    r, c, m = sums[(label, "reached")], sums[(label, "cited")], sums[(label, "missed reached")]
    print(f"  {label:18s} | {r / count:5.1f} | {c / max(r, 1):.1%} | {m / count:.1f}")
print("inside 'both', the arm's own order, the first ones: how often cited")
for k, (m, c) in first_k.items():
    print(f"  first {k}: {c / max(m, 1):.1%} ({m} chunks over the hundred)")
print("done", flush=True)

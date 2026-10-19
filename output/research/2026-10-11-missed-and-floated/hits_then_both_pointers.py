"""The hits, then what two structural pointers say belongs with them, then the rest: an order
through the arm's own delivery (after his 2026-10-15 "how the fuck can this not be relevant"). The
hits: the chunks the arm's scope is gauged from (the combo's first two steps). From the hits, the
tag pointer (a tag with the same role on both edges: the facet each edge stands highest in) and
the people pointer (each person's thing just before and after on their own line of time, the
product's own work). Variants: the hits, then the chunks both pointers reach, then the rest; the
people pointer alone; the tag pointer alone; people and any shared tag, the role left out (does
the facet role do the work). Each part in the arm's own order. A side run, the arm's file not
changed, the hundred, cached first calls, no lane call. The gold ids are read inside; numbers
only.
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
the_combo = WK.cloud_combo


def combo_rec(layer_, cosines, d_near, inside, scope_of, k):
    out = the_combo(layer_, cosines, d_near, inside, scope_of, k)
    captured["combo"], captured["inside"] = out, np.asarray(inside, dtype=np.int64)
    return out


WK.cloud_combo = combo_rec


def score(id_lists, context_ids, cites):
    got = {str(x) for x in context_ids}
    whole = [u for u in ([str(x) for x in unit] for unit in id_lists if unit) if set(u) <= got]
    return (bool(whole and set(whole[0]) & cites), any(set(u) & cites for u in whole[:3]), len(cites & got) / len(cites))


LABELS = ("the hits, then what both pointers reach, then the rest", "the hits, then the people pointer, then the rest",
          "the hits, then the same-role tag pointer, then the rest",
          "the hits, then people and any shared tag (role left out), then the rest",
          "stop or search: the first chunk tied to another hit by either pointer keeps the arm's order, else the hits, then both, then the rest")
searched = [0, 0]
results = {"the arm as it stands": []}
for label in LABELS:
    results[label] = []
cache = {}
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    out = V.answer_one_question((qid, q.question), p, None, 50, BUDGET)
    results["the arm as it stands"].append(score(out.meta["chunk_ids"], out.context_ids, cites))
    combo, inside = captured["combo"], captured["inside"]
    member = np.zeros(n, dtype=bool)
    member[inside] = True
    step = combo["step"]
    hits = set(inside[step[inside] <= max(3, int(step[inside].min()))].tolist())
    same_tag, any_tag = set(), set()
    for s in hits:
        for e1 in edges_of_chunk[s]:
            for e2 in edges_of_tag[int(tag_e[e1])]:
                c = int(chunk_e[e2])
                if member[c] and c not in hits:
                    any_tag.add(c)
                    if role[e1] == role[e2]:
                        same_tag.add(c)
    reach = people_pointer(inside, TI.product(parents[int(inside[0])].split(".")[1]))
    by_people = set()
    for s in hits:
        by_people |= {c for c in reach.get(s, set()) if member[c] and c not in hits}
    order = combo["order"]
    for label, middle in zip(LABELS, (same_tag & by_people, by_people, same_tag, any_tag & by_people)):
        first = [c for c in order if c in hits]
        then = [c for c in order if c in middle]
        rest = [c for c in order if c not in hits and c not in middle]
        _, id_lists, context_ids, _, _, _ = V._hand_over(first + then + rest, p, BUDGET, 50, cache)
        results[label].append(score(id_lists, context_ids, cites))
    # stop or search: is the arm's first chunk tied to another hit by a same-role tag or by the people pointer
    top = order[0]
    tied = any(c in hits and c != top for c in reach.get(top, set()))
    if not tied:
        for e1 in edges_of_chunk[top]:
            if any(int(chunk_e[e2]) in hits and int(chunk_e[e2]) != top and role[e1] == role[e2]
                   for e2 in edges_of_tag[int(tag_e[e1])]):
                tied = True
                break
    if tied:
        results[LABELS[4]].append(results["the arm as it stands"][-1])
        searched[0] += 1
    else:
        searched[1] += 1
        middle = same_tag & by_people
        first = [c for c in order if c in hits]
        then = [c for c in order if c in middle]
        rest = [c for c in order if c not in hits and c not in middle]
        _, id_lists, context_ids, _, _, _ = V._hand_over(first + then + rest, p, BUDGET, 50, cache)
        results[LABELS[4]].append(score(id_lists, context_ids, cites))
WK.cloud_combo = the_combo

print()
print("top text holds a cited record | a cited record among the first three texts | context_recall_id | against the arm: mean "
      "difference (standard error), questions higher / lower")
print(f"stop or search: the first chunk tied to another hit on {searched[0]} questions (kept), alone on {searched[1]} (searched)")
base = np.array([x[2] for x in results["the arm as it stands"]])
for label, got in results.items():
    a = np.array(got, dtype=np.float64)
    diff = a[:, 2] - base
    print(f"  {int(a[:, 0].sum()):3d} | {int(a[:, 1].sum()):3d} | {a[:, 2].mean():.4f} | {diff.mean():+.3f} "
          f"({diff.std(ddof=1) / np.sqrt(diff.size):.3f}), {int((diff > 1e-9).sum())} / {int((diff < -1e-9).sum())}  {label}")
print("done", flush=True)

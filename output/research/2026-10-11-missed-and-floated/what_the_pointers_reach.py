"""His 2026-10-11 "a 'nearest' chunk etc could be used for search-start or search-range for that
specific person or whatever pointer" and "perhaps my nearness idea with graphsearch is a play".

On the hundred, inside the gold's branch, cached query side, no model call. Where the retrieval
ends up = the found chunks: a chunk that carries a tag a query tag picked (its 5 nearest graph
tags) or sits in the first of the 5 clusters of the description nearness (against the query
description or against the question). From those, one step along a pointer the records hold:

  person          the chunk names a person a found chunk names
  person, parent  the same, and the two chunks are in the same parent (a channel or a file)
  link            a found chunk shares the link the chunk owns, or the other way round
  next to         the chunk is next to a found chunk in its file
  parent          the chunk is in the same parent as a found chunk

For each: how much of the gold that is NOT found it reaches, and how many chunks that are not gold
come along. The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/what_the_pointers_reach.py [gold100]
"""
import json
import os
import re
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"
os.environ["HERB_V4_SCOPE_STEP"] = "both"

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _load_verified_doc  # noqa: E402
from arms.artefact_v3 import file_adjacency  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402
from scipy.stats import rankdata  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
CACHE = REPO / "output/private/artefact_v4_cache/querytag"
K = V._k_nearest()
URL = re.compile(r"https?://[^\s\"'<>\)\]]+")
OWN = ("document_link", "link")
STEPS = ("person", "person, parent", "link", "next to", "parent", "link or next to",
         "link or next to or (person, parent)")


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def clean(link):
    return link.rstrip(".,;:!?").rstrip("/").lower()


def people_of(record):
    found = set()
    user = ((record.get("Message") or {}).get("User") or {}).get("userId")
    if user:
        found.add(str(user))
    if record.get("author"):
        found.add(str(record["author"]))
    for who in record.get("participants") or []:
        found.add(str(who))
    login = (record.get("user") or {}).get("login") if isinstance(record.get("user"), dict) else None
    if login:
        found.add(str(login))
    for review in record.get("reviews") or []:
        login = (review.get("user") or {}).get("login")
        if login:
            found.add(str(login))
    return found


wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("what the pointers reach")
layer, n = p.layer, len(p.chunk_ids)
et, ec, eligible = layer["edge_tag"], layer["edge_chunk"], layer["eligible"]
docs, records, people, parent = {}, [], [], []
owns, mentions = [set() for _ in range(n)], [set() for _ in range(n)]
for i, row in enumerate(p.chunk_rows):
    loc = json.loads(row["locator"])
    arr = _load_verified_doc(row["relpath"], row["sha256"], docs)[loc["section"]]
    recs = [arr[k] for k in (loc["indices"] if "indices" in loc else [loc["index"]])]
    records.append(frozenset(str(r["id"]) for r in recs if r.get("id") is not None))
    people.append(set().union(*(people_of(r) for r in recs)) if recs else set())
    parent.append(str(row["parent"]))
    for r in recs:
        for key in OWN:
            if isinstance(r.get(key), str) and r[key].startswith("http"):
                owns[i].add(clean(r[key]))
        body = (r[loc["field"]][loc["char_range"][0]:loc["char_range"][1]] if "char_range" in loc
                else " ".join(strings({k: v for k, v in r.items() if k not in OWN})))
        mentions[i].update(clean(u) for u in URL.findall(body))
    mentions[i] -= owns[i]
owner = defaultdict(set)
for i in range(n):
    for link in owns[i]:
        owner[link].add(i)
linked = [set() for _ in range(n)]
for i in range(n):
    for link in mentions[i]:
        for j in owner.get(link, ()):
            if j != i:
                linked[i].add(j)
                linked[j].add(i)
adjacency = file_adjacency([dict(r) for r in p.chunk_rows])
ptr, members = np.asarray(adjacency["ptr"]), np.asarray(adjacency["members"])
next_to = [set(members[ptr[i]:ptr[i + 1]].tolist()) for i in range(n)]
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b


def cached_sides():
    out = []
    for f in CACHE.glob("*.json"):
        if f.name.endswith(".started.json"):
            continue
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        raw = j.get("raw")
        if j.get("ok") and isinstance(raw, dict) and raw.get("description") and raw.get("tags"):
            out.append((f.stat().st_mtime, (j.get("signature") or {}).get("user") or "", raw))
    return sorted(out, key=lambda row: -row[0])


SIDES = cached_sides()


def side_of(q):
    def names(rows):
        return list(dict.fromkeys(str(r["t"]).strip() for r in rows or []
                                  if isinstance(r, dict) and str(r.get("t", "")).strip()))
    for _, user, raw in SIDES:
        if q.question in user:
            return str(raw["description"]), names(raw.get("tags")), names(raw.get("query_tags"))
    raise SystemExit(f"no cached first call for {q.id}")


totals = Counter()
per_question = defaultdict(list)
done = 0
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    description, tags, asked = side_of(q)
    got, _, _ = V._tag_cosines(description, tags, p)
    rows, d_description = list(got["tags"]), np.asarray(got["description"], dtype=np.float64)
    if asked:
        rows += list(V._tag_cosines(description, asked, p)[0]["tags"])
    rows = np.array(rows, dtype=np.float64)
    d_question = np.asarray(V._query_cosines(q.question, [], p)[0]["query_description_cosines"], dtype=np.float64)
    place_of_tag = np.full(rows.shape, np.inf)
    place_of_tag[:, eligible] = np.array([rankdata(-row[eligible], method="min") for row in rows])
    best_place = np.full(n, np.inf)
    np.minimum.at(best_place, ec, place_of_tag[:, et].min(axis=0))
    gold = np.array([bool(records[i] & cites) for i in range(n)])
    main = Counter(branch_of[np.flatnonzero(gold)].tolist()).most_common(1)[0][0]
    inside = np.flatnonzero(branch_of == main)
    found_mask = ((best_place[inside] <= K) | (WK.levels(d_description[inside], K) == 1)
                  | (WK.levels(d_question[inside], K) == 1))
    found = set(inside[found_mask].tolist())
    found_people = set().union(*(people[f] for f in found)) if found else set()
    found_parents = {parent[f] for f in found}
    by_parent = defaultdict(set)
    for f in found:
        by_parent[parent[f]] |= people[f]
    rest = [c for c in inside.tolist() if c not in found]
    missing_gold = [c for c in rest if gold[c]]
    totals["gold"] += int(gold[inside].sum())
    totals["found"] += len(found)
    totals["found gold"] += sum(int(gold[f]) for f in found)
    totals["not found gold"] += len(missing_gold)
    totals["not found, not gold"] += len(rest) - len(missing_gold)
    reached = {step: set() for step in STEPS}
    for c in rest:
        flags = {
            "person": bool(people[c] & found_people),
            "person, parent": bool(people[c] & by_parent.get(parent[c], set())),
            "link": bool(linked[c] & found),
            "next to": bool(next_to[c] & found),
            "parent": parent[c] in found_parents,
        }
        flags["link or next to"] = flags["link"] or flags["next to"]
        flags["link or next to or (person, parent)"] = flags["link or next to"] or flags["person, parent"]
        for step, yes in flags.items():
            if yes:
                reached[step].add(c)
    for step in STEPS:
        got_gold = sum(int(gold[c]) for c in reached[step])
        totals[step, "gold"] += got_gold
        totals[step, "other"] += len(reached[step]) - got_gold
        per_question[step].append(len(reached[step]))
    per_question["found"].append(len(found))
    per_question["rest"].append(len(rest))
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

m = len(wanted)
print(f"\n{SET}: {m} questions, inside the gold's branch")
print(f"gold chunks {totals['gold']}; found chunks {totals['found']} ({totals['found gold']} of them gold); gold that is "
      f"not found {totals['not found gold']}; chunks that are neither found nor gold {totals['not found, not gold']}")
print(f"per question, the middle: found chunks {np.median(per_question['found']):.0f}, chunks of the branch not found "
      f"{np.median(per_question['rest']):.0f}")
base = totals["not found gold"] / (totals["not found gold"] + totals["not found, not gold"])
print(f"share of gold among the chunks that are not found: {base:.3f}")
print("\n== one step from the found chunks: reaches of the gold that is not found | chunks reached per question, the "
      "middle | gold among the reached ==")
for step in STEPS:
    g, o = totals[step, "gold"], totals[step, "other"]
    print(f"  {step}: {g} of {totals['not found gold']} | {np.median(per_question[step]):.0f} | "
          f"{(g / (g + o) if g + o else 0):.3f}")
print("done", flush=True)

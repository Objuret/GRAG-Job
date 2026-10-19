"""His 2026-10-11 "a 'nearest' chunk etc could be used for search-start" and "wait.. 1 step puts
almost all back!?". On the hundred, inside the gold's branch, cached query side, no model call.

The starts, by the three routes' standings added (tags, description against the query
description, description against the question): the nearest chunk; the nearest 5; the chunks that
fit in 72,000 characters; and the found chunks (a picked tag, or the first of 5 clusters of the
description nearness). From a start set, a step takes every chunk that shares a link with a chunk
of the set (either way) or stands next to one in its file; a second step does the same from
everything held so far.

Printed: how many chunks a question then holds, and how many of the 996 gold chunks are among
them. The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/one_step_from_which_starts.py [gold100]
"""
import json
import os
import re
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"
os.environ["HERB_V4_SCOPE_STEP"] = "both"

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _load_verified_doc, _resolve_chunk  # noqa: E402
from arms.artefact_v3 import file_adjacency  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
BUDGET = 72000
ROUTES = ("tags", "description", "question")
CACHE = REPO / "output/private/artefact_v4_cache/querytag"
K = V._k_nearest()
URL = re.compile(r"https?://[^\s\"'<>\)\]]+")
OWN = ("document_link", "link")
STARTS = ("the nearest chunk", "the nearest 5", "the chunks that fit in 72,000", "the found chunks")
RELATIONS = ("link or next to", "next to only", "link only")


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


wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("one step from which starts")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
et, ec, eligible = layer["edge_tag"], layer["edge_chunk"], layer["eligible"]
docs, records, length = {}, [], np.zeros(n, dtype=np.int64)
owns, mentions = [set() for _ in range(n)], [set() for _ in range(n)]
for i, row in enumerate(p.chunk_rows):
    text, _ = _resolve_chunk(row, docs)
    length[i] = len(text)
    loc = json.loads(row["locator"])
    arr = _load_verified_doc(row["relpath"], row["sha256"], docs)[loc["section"]]
    recs = [arr[k] for k in (loc["indices"] if "indices" in loc else [loc["index"]])]
    records.append(frozenset(str(r["id"]) for r in recs if r.get("id") is not None))
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
tied = {"link or next to": [linked[i] | next_to[i] for i in range(n)], "next to only": next_to, "link only": linked}
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


def kept_of(order):
    fits = np.cumsum(length[order]) <= BUDGET
    return int(fits.sum()) if fits.all() else int(np.argmin(fits))


def standing(x):
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


gold_total = 0
held = defaultdict(list)          # (start, relation, steps) -> chunks held per question
got = Counter()                   # (start, relation, steps) -> gold chunks held, summed
chars = defaultdict(list)
done = 0
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    description, tags, asked = side_of(q)
    answer, _, _ = V._tag_cosines(description, tags, p)
    rows, d_description = list(answer["tags"]), np.asarray(answer["description"], dtype=np.float64)
    if asked:
        rows += list(V._tag_cosines(description, asked, p)[0]["tags"])
    rows = np.array(rows, dtype=np.float64)
    d_question = np.asarray(V._query_cosines(q.question, [], p)[0]["query_description_cosines"], dtype=np.float64)
    place_of_tag = np.full(rows.shape, np.inf)
    place_of_tag[:, eligible] = np.array([rankdata(-row[eligible], method="min") for row in rows])
    best_place = np.full(n, np.inf)
    np.minimum.at(best_place, ec, place_of_tag[:, et].min(axis=0))
    t_near, t_edge = WK.best_edges(rows[:, et].max(axis=0), ec, n)
    t_near = np.where(t_edge >= 0, t_near, t_near[t_edge >= 0].min())
    gold = np.array([bool(records[i] & cites) for i in range(n)])
    main = Counter(branch_of[np.flatnonzero(gold)].tolist()).most_common(1)[0][0]
    inside = np.flatnonzero(branch_of == main)
    within = set(inside.tolist())
    gold_total += int(gold[inside].sum())
    base = standing(t_near[inside]) + standing(d_description[inside]) + standing(d_question[inside])
    order = inside[np.lexsort((id_rank[inside], -base))]
    found_mask = ((best_place[inside] <= K) | (WK.levels(d_description[inside], K) == 1)
                  | (WK.levels(d_question[inside], K) == 1))
    starts = {
        "the nearest chunk": set(order[:1].tolist()),
        "the nearest 5": set(order[:5].tolist()),
        "the chunks that fit in 72,000": set(order[:kept_of(order)].tolist()),
        "the found chunks": set(inside[found_mask].tolist()),
    }
    for name, start in starts.items():
        for relation in RELATIONS:
            have = set(start)
            for steps in (0, 1, 2):
                if steps:
                    have = have | {j for c in have for j in tied[relation][c] if j in within}
                held[name, relation, steps].append(len(have))
                got[name, relation, steps] += sum(int(gold[c]) for c in have)
                chars[name, relation, steps].append(int(length[list(have)].sum()) if have else 0)
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

m = len(wanted)
print(f"\n{SET}: {m} questions, inside the gold's branch (about {int(np.median([len(b[1]) for b in branches]))} chunks); "
      f"gold chunks {gold_total}; the budget is {BUDGET} characters")
print("each cell: chunks held per question, the middle | their characters, the middle | gold chunks among them, of "
      f"{gold_total}")
for relation in RELATIONS:
    print(f"\n== a step = {relation} ==")
    for name in STARTS:
        cells = []
        for steps in (0, 1, 2):
            key = (name, relation, steps)
            cells.append(f"{np.median(held[key]):.0f} | {np.median(chars[key]):,.0f} | {got[key]}")
        print(f"  {name}: the start {cells[0]}  ->  one step {cells[1]}  ->  two steps {cells[2]}")
print("done", flush=True)

"""His 2026-10-11 "Dude, it is INSANE if the top chunk is NOT a gold!". From the arm's own runs on
the hundred (the chunks as the run delivered them, `meta.chunk_ids` of `arm_outputs.jsonl`): when
the first delivered chunk is not gold, what is it?

  where the first gold chunk stands in the delivery
  the kind of the first chunk, gold and not gold
  how a first chunk that is not gold relates to the question's gold chunks:
      next to a gold chunk in its parent (one place away)
      holds messages of a conversation that has cited messages (one channel, one day)
      shares a link with a gold chunk
      a gold chunk is among its five nearest chunks by description
      it sits in a parent that holds gold
      none of these
  and, for the first chunk of the three routes added (today's vectors): its place by each route
  beside the place of the best gold chunk by each route.

No model call. The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/what_is_on_top_when_not_gold.py
"""
import json
import os
import re
import sys
import warnings
from collections import Counter, defaultdict
from datetime import datetime, timezone
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
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

RUNS = REPO / "output" / "k=chars"
RUN_NAMES = {"today's arm, name border": "artefact_v4__gold100__cb72000__20261011T164246Z_name",
             "the old arm, 10-06": "artefact_v4__gold100__cb72000__20261006T184959Z"}
CACHE = REPO / "output/private/artefact_v4_cache/querytag"
URL = re.compile(r"https?://[^\s\"'<>\)\]]+")
OWN = ("document_link", "link")
NEAREST = 5
RELATIONS = ("next to a gold chunk in its parent", "holds messages of a conversation that has cited messages",
             "shares a link with a gold chunk", "a gold chunk among its five nearest by description",
             "sits in a parent that holds gold", "none of these")


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


def stamp(value):
    if value is None:
        return None
    text = str(value).strip()
    try:
        return float(text)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00").replace(" ", "T")).timestamp()
    except ValueError:
        return None


by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("what is on top when not gold")
layer, n = p.layer, len(p.chunk_ids)
id_rank, kind, kind_names = layer["id_rank"], layer["kind"], layer["kind_names"]
et, ec = layer["edge_tag"], layer["edge_chunk"]
docs, record_sets, parent, ordinal = {}, [], [], np.zeros(n, dtype=np.int64)
owns, mentions, talks_of = [set() for _ in range(n)], [set() for _ in range(n)], [set() for _ in range(n)]
talk_of_record = {}
for i, row in enumerate(p.chunk_rows):
    loc = json.loads(row["locator"])
    arr = _load_verified_doc(row["relpath"], row["sha256"], docs)[loc["section"]]
    recs = [arr[k] for k in (loc["indices"] if "indices" in loc else [loc["index"]])]
    record_sets.append(frozenset(str(r["id"]) for r in recs if r.get("id") is not None))
    parent.append(str(row["parent"]))
    ordinal[i] = int(row["ordinal"])
    for r in recs:
        for key in OWN:
            if isinstance(r.get(key), str) and r[key].startswith("http"):
                owns[i].add(clean(r[key]))
        body = (r[loc["field"]][loc["char_range"][0]:loc["char_range"][1]] if "char_range" in loc
                else " ".join(strings({k: v for k, v in r.items() if k not in OWN})))
        mentions[i].update(clean(u) for u in URL.findall(body))
        when = stamp(((r.get("Message") or {}).get("User") or {}).get("timestamp")) if "Message" in r else None
        channel = (r.get("Channel") or {}).get("channelID") if "Channel" in r else None
        if when is not None and channel is not None and r.get("id") is not None:
            talk = (row["relpath"], channel, datetime.fromtimestamp(when, timezone.utc).date().isoformat())
            talks_of[i].add(talk)
            talk_of_record[str(r["id"])] = talk
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
members = defaultdict(list)
for i in range(n):
    members[parent[i]].append(i)
spot = np.zeros(n, dtype=np.int64)
for chunks in members.values():
    for k, c in enumerate(sorted(chunks, key=lambda c: (ordinal[c], id_rank[c]))):
        spot[c] = k
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b
chunks_of_record = defaultdict(list)
for i in range(n):
    for r in record_sets[i]:
        chunks_of_record[r].append(i)
CV = np.array(p.chunk_vectors, dtype=np.float64)
CV = CV / np.linalg.norm(CV, axis=1, keepdims=True)
print("prepared", flush=True)


def relation(top, gold_chunks, cites):
    """Every way the chunk is tied to the question's gold chunks, and the first of them in RELATIONS order."""
    found = []
    if any(parent[g] == parent[top] and abs(int(spot[g]) - int(spot[top])) == 1 for g in gold_chunks):
        found.append(RELATIONS[0])
    cited_talks = {talk_of_record[r] for r in cites if r in talk_of_record}
    if talks_of[top] & cited_talks:
        found.append(RELATIONS[1])
    if linked[top] & gold_chunks:
        found.append(RELATIONS[2])
    inside = np.flatnonzero(branch_of == branch_of[top])
    near = CV[inside] @ CV[top]
    near[inside == top] = -np.inf
    if set(inside[np.argsort(-near)[:NEAREST]].tolist()) & gold_chunks:
        found.append(RELATIONS[3])
    if any(parent[g] == parent[top] for g in gold_chunks):
        found.append(RELATIONS[4])
    return found or [RELATIONS[5]]


def the_pool_chunk(records):
    """The pool chunk a delivered chunk is: the one holding its records (a document's parts share one id)."""
    hits = Counter(c for r in records for c in chunks_of_record.get(str(r), ()))
    if not hits:
        return None
    most = max(hits.values())
    return min((c for c, k in hits.items() if k == most), key=lambda c: (ordinal[c], id_rank[c]))


for label, name in RUN_NAMES.items():
    rows = [json.loads(line) for line in (RUNS / name / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]
    first_gold_at, kinds, relations, firsts = Counter(), defaultdict(Counter), Counter(), Counter()
    not_gold = 0
    for row in rows:
        q = by_id[row["id"]]
        cites = {str(c) for c in q.citations}
        delivered = [the_pool_chunk(c) for c in ((row.get("meta") or {}).get("chunk_ids") or [])]
        delivered = [c for c in delivered if c is not None]
        gold_chunks = {i for i in range(n) if record_sets[i] & cites}
        is_gold = [c in gold_chunks or bool(record_sets[c] & cites) for c in delivered]
        where = next((k + 1 for k, g in enumerate(is_gold) if g), None)
        first_gold_at["first" if where == 1 else "second or third" if where in (2, 3) else "fourth to sixth"
                      if where in (4, 5, 6) else "further down" if where else "no gold chunk delivered"] += 1
        top = delivered[0]
        kinds["gold" if is_gold[0] else "not gold"][kind_names[int(kind[top])]] += 1
        if not is_gold[0]:
            not_gold += 1
            found = relation(top, gold_chunks, cites)
            firsts[found[0]] += 1
            relations.update(found)
    print(f"\n==== {label} ({name}), {len(rows)} questions ====")
    print("  where the first gold chunk stands in the delivery: " + ", ".join(
        f"{k}: {first_gold_at[k]}" for k in ("first", "second or third", "fourth to sixth", "further down",
                                             "no gold chunk delivered")))
    for which in ("gold", "not gold"):
        print(f"  the first chunk when it is {which}, by kind: " + ", ".join(
            f"{k}: {v}" for k, v in kinds[which].most_common()))
    print(f"  the {not_gold} first chunks that are not gold, how they are tied to the question's gold "
          "(a chunk can be tied in several ways | counted once, by the first that holds):")
    for name_ in RELATIONS:
        print(f"    {relations[name_]:3d} | {firsts[name_]:3d}  {name_}")

# the three routes added, today's vectors: which route puts the first chunk there
SIDES = []
for f in CACHE.glob("*.json"):
    if f.name.endswith(".started.json"):
        continue
    try:
        j = json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        continue
    got = j.get("raw")
    if j.get("ok") and isinstance(got, dict) and got.get("description") and got.get("tags"):
        SIDES.append((f.stat().st_mtime, (j.get("signature") or {}).get("user") or "", got))
SIDES.sort(key=lambda row: -row[0])


def side_of(q):
    def names(rows):
        return list(dict.fromkeys(str(r["t"]).strip() for r in rows or []
                                  if isinstance(r, dict) and str(r.get("t", "")).strip()))
    for _, user, got in SIDES:
        if q.question in user:
            return str(got["description"]), names(got.get("tags")), names(got.get("query_tags"))
    raise SystemExit(f"no cached first call for {q.id}")


def standing(x):
    x = np.asarray(x, dtype=np.float64)
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


wanted = [json.loads(line)["id"] for line in (REPO / "data" / "gold100.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
top_place, gold_place, carried = defaultdict(list), defaultdict(list), Counter()
count = 0
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    description, tags, asked = side_of(q)
    answer = V._tag_cosines(description, tags, p)[0]
    rows, d_description = list(answer["tags"]), np.asarray(answer["description"], dtype=np.float64)
    if asked:
        rows += list(V._tag_cosines(description, asked, p)[0]["tags"])
    rows = np.array(rows, dtype=np.float64)
    d_question = np.asarray(V._query_cosines(q.question, [], p)[0]["query_description_cosines"], dtype=np.float64)
    gold = np.array([bool(record_sets[i] & cites) for i in range(n)])
    main = Counter(branch_of[np.flatnonzero(gold)].tolist()).most_common(1)[0][0]
    inside = np.flatnonzero(branch_of == main)
    t_near, t_edge = WK.best_edges(rows[:, et].max(axis=0), ec, n)
    t_near = np.where(t_edge >= 0, t_near, t_near[t_edge >= 0].min())
    routes = {"tags": t_near[inside], "description": d_description[inside], "question": d_question[inside]}
    total = sum(standing(v) for v in routes.values())
    top = int(np.lexsort((id_rank[inside], -total))[0])
    if gold[inside][top]:
        continue
    count += 1
    best_route = None
    for name_, value in routes.items():
        place = np.empty(inside.size, dtype=np.int64)
        place[np.lexsort((id_rank[inside], -value))] = np.arange(1, inside.size + 1)
        top_place[name_].append(int(place[top]))
        gold_place[name_].append(int(place[gold[inside]].min()))
    carried[min(routes, key=lambda r: top_place[r][-1])] += 1
print(f"\n==== the three routes added, today's vectors: the {count} questions whose first chunk is not gold ====")
print("  route | the first chunk's place by this route alone, the middle | the best gold chunk's place by it, the middle")
for name_ in top_place:
    a, b = top_place[name_], gold_place[name_]
    print(f"  {name_} | {np.median(a):.0f} ({np.percentile(a, 25):.0f}-{np.percentile(a, 75):.0f}) | "
          f"{np.median(b):.0f} ({np.percentile(b, 25):.0f}-{np.percentile(b, 75):.0f})")
print("  the route that places that first chunk highest: " + ", ".join(f"{k}: {v}" for k, v in carried.most_common()))
print("done", flush=True)

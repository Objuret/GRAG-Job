"""His 2026-10-11 "but is it 1 step from 'all' or a specific range of 'shitty hits'.. like, how
close are they". On the hundred, inside the gold's branch, cached query side, no model call.

Hits = the found chunks (a picked tag, or the first of 5 clusters of the description nearness
against the query description or the question). For every gold chunk that is NOT found:
  - how far it stands in its file from the nearest hit (places apart inside the same parent, a
    channel or a file; 1 = next to it), and how many chunks that are not gold stand as close;
  - whether the hit it stands next to is itself gold or not, and where that hit stands in the
    order of the three routes' standings added (the nearest chunk, places 2-5, 6-15, further);
  - the same for a link shared with a hit.

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/how_close_to_which_hits.py [gold100]
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
from arms.artefact_v2 import _load_verified_doc  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
CACHE = REPO / "output/private/artefact_v4_cache/querytag"
K = V._k_nearest()
URL = re.compile(r"https?://[^\s\"'<>\)\]]+")
OWN = ("document_link", "link")
BANDS = ("1", "2", "3", "4-5", "6-10", "further", "no hit in its file")
PLACES = ("the nearest chunk", "places 2-5", "places 6-15", "further down")


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


def band_of(d):
    if d is None:
        return "no hit in its file"
    return "1" if d == 1 else "2" if d == 2 else "3" if d == 3 else "4-5" if d <= 5 else "6-10" if d <= 10 else "further"


def place_band(place):
    return PLACES[0] if place == 1 else PLACES[1] if place <= 5 else PLACES[2] if place <= 15 else PLACES[3]


wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("how close to which hits")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
et, ec, eligible = layer["edge_tag"], layer["edge_chunk"], layer["eligible"]
docs, records = {}, []
owns, mentions = [set() for _ in range(n)], [set() for _ in range(n)]
parent, ordinal = [], np.zeros(n, dtype=np.int64)
for i, row in enumerate(p.chunk_rows):
    loc = json.loads(row["locator"])
    arr = _load_verified_doc(row["relpath"], row["sha256"], docs)[loc["section"]]
    recs = [arr[k] for k in (loc["indices"] if "indices" in loc else [loc["index"]])]
    records.append(frozenset(str(r["id"]) for r in recs if r.get("id") is not None))
    parent.append(str(row["parent"]))
    ordinal[i] = int(row["ordinal"])
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
# a chunk's place inside its parent: its rank by ordinal among the parent's chunks
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


def standing(x):
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


near_gold, near_other = Counter(), Counter()
beside, beside_place = Counter(), Counter()
by_link, by_link_place = Counter(), Counter()
hits_gold = hits_other = missing = 0
others = Counter()
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
    base = standing(t_near[inside]) + standing(d_description[inside]) + standing(d_question[inside])
    order = inside[np.lexsort((id_rank[inside], -base))]
    place = {int(c): k + 1 for k, c in enumerate(order.tolist())}
    found_mask = ((best_place[inside] <= K) | (WK.levels(d_description[inside], K) == 1)
                  | (WK.levels(d_question[inside], K) == 1))
    found = set(inside[found_mask].tolist())
    hits_gold += sum(int(gold[f]) for f in found)
    hits_other += sum(int(not gold[f]) for f in found)
    hits_in = defaultdict(list)
    for f in found:
        hits_in[parent[f]].append(f)
    for c in inside.tolist():
        if c in found:
            continue
        here = hits_in.get(parent[c])
        d = min(abs(int(spot[c]) - int(spot[f])) for f in here) if here else None
        if gold[c]:
            missing += 1
            near_gold[band_of(d)] += 1
            if d == 1:
                next_hits = [f for f in here if abs(int(spot[c]) - int(spot[f])) == 1]
                beside["next to a hit that is gold" if any(gold[f] for f in next_hits)
                       else "next to hits that are not gold only"] += 1
                beside_place[place_band(min(place[f] for f in next_hits))] += 1
            tied = linked[c] & found
            if tied:
                by_link["shares a link with a hit that is gold" if any(gold[f] for f in tied)
                        else "shares a link with hits that are not gold only"] += 1
                by_link_place[place_band(min(place[f] for f in tied))] += 1
        else:
            near_other[band_of(d)] += 1
            if d == 1:
                next_hits = [f for f in here if abs(int(spot[c]) - int(spot[f])) == 1]
                others["next to a hit that is gold" if any(gold[f] for f in next_hits)
                       else "next to hits that are not gold only"] += 1
            tied = linked[c] & found
            if tied:
                others["shares a link with a hit that is gold" if any(gold[f] for f in tied)
                       else "shares a link with hits that are not gold only"] += 1
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

m = len(wanted)
print(f"\n{SET}: {m} questions, inside the gold's branch; hits {hits_gold + hits_other} ({hits_gold} gold, "
      f"{hits_other} not gold); gold chunks that are not hit {missing}")
print("\n== places apart, in its file, from the nearest hit: gold chunks not hit | other chunks not hit, per question "
      "| gold among the chunks at that distance ==")
for band in BANDS:
    g, o = near_gold[band], near_other[band]
    print(f"  {band}: {g} | {o / m:.1f} | {(g / (g + o) if g + o else 0):.3f}")
print(f"\n== the {near_gold['1']} gold chunks that stand next to a hit ==")
for name, count in beside.most_common():
    print(f"  {name}: {count}")
print("  the best-placed hit they stand next to is: " + ", ".join(f"{name} {beside_place[name]}" for name in PLACES))
print(f"\n== the {sum(by_link.values())} gold chunks not hit that share a link with a hit ==")
for name, count in by_link.most_common():
    print(f"  {name}: {count}")
print("  the best-placed hit they share it with is: " + ", ".join(f"{name} {by_link_place[name]}" for name in PLACES))
print("\n== a chunk that is not hit, one step from a hit: how often it is gold, by what the hit is ==")
for name, golds in (("next to a hit that is gold", beside), ("next to hits that are not gold only", beside),
                    ("shares a link with a hit that is gold", by_link),
                    ("shares a link with hits that are not gold only", by_link)):
    g, o = golds[name], others[name]
    print(f"  {name}: {g} gold of {g + o} chunks ({(g / (g + o) if g + o else 0):.3f})")
print("done", flush=True)

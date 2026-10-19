"""After his 2026-10-11 "is it 1 step from all or a specific range of shitty hits": do the hits
that are gold hang together while the hits that are not gold stand alone. On the hundred, inside
the gold's branch, cached query side, no model call.

Hits = the found chunks (a picked tag, or the first of 5 clusters of the description nearness
against the query description or the question). Two hits are tied when they stand next to each
other in their file (neighbouring places in the same parent) or share a link. A group is the
hits that hang together through such ties.

Printed: how often a hit is gold by how many hits are one step from it, and by the size of its
group; the largest group of a question; and, as a check inside the budget (the orders are the
agent's own, to see whether the grouping carries anything): the gold chunks delivered in 72,000
characters by the plain order, by the hits taken group by group from the largest, and by the
same with each group followed by the chunks one step from it.

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/hits_that_hang_together.py [gold100]
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
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
BUDGET = 72000
CACHE = REPO / "output/private/artefact_v4_cache/querytag"
K = V._k_nearest()
URL = re.compile(r"https?://[^\s\"'<>\)\]]+")
OWN = ("document_link", "link")
TIES = ("next to or a shared link", "next to only")
DEGREES = ("no hit one step from it", "1 hit", "2 hits", "3 or more")
SIZES = ("alone", "2", "3-4", "5-9", "10 or more")


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


def degree_band(d):
    return DEGREES[min(d, 3)]


def size_band(s):
    return SIZES[0] if s == 1 else SIZES[1] if s == 2 else SIZES[2] if s <= 4 else SIZES[3] if s <= 9 else SIZES[4]


wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("hits that hang together")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
et, ec, eligible = layer["edge_tag"], layer["edge_chunk"], layer["eligible"]
docs, records, length = {}, [], np.zeros(n, dtype=np.int64)
owns, mentions = [set() for _ in range(n)], [set() for _ in range(n)]
parent, ordinal = [], np.zeros(n, dtype=np.int64)
for i, row in enumerate(p.chunk_rows):
    text, _ = _resolve_chunk(row, docs)
    length[i] = len(text)
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
members = defaultdict(list)
for i in range(n):
    members[parent[i]].append(i)
beside = [set() for _ in range(n)]
for chunks in members.values():
    ordered = sorted(chunks, key=lambda c: (ordinal[c], id_rank[c]))
    for a, b in zip(ordered, ordered[1:]):
        beside[a].add(b)
        beside[b].add(a)
tied = {"next to or a shared link": [beside[i] | linked[i] for i in range(n)], "next to only": beside}
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


by_degree = {t: {d: [0, 0] for d in DEGREES} for t in TIES}
by_size = {t: {s: [0, 0] for s in SIZES} for t in TIES}
largest = {t: defaultdict(list) for t in TIES}
delivered, recall = defaultdict(int), defaultdict(list)
gold_total = 0
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
    plain = inside[np.lexsort((id_rank[inside], -base))].tolist()
    place = {c: k for k, c in enumerate(plain)}
    found_mask = ((best_place[inside] <= K) | (WK.levels(d_description[inside], K) == 1)
                  | (WK.levels(d_question[inside], K) == 1))
    found = set(inside[found_mask].tolist())

    def score(name, order):
        order = np.asarray(order, dtype=np.int64)
        kept = order[:kept_of(order)]
        delivered[name] += int(gold[kept].sum())
        got = set().union(*(records[i] for i in kept)) if kept.size else set()
        recall[name].append(len(cites & got) / len(cites))

    score("the plain order (the three routes' standings added)", plain)
    for tie in TIES:
        relation = tied[tie]
        group_of, groups = {}, []
        for f in sorted(found, key=lambda c: place[c]):
            if f in group_of:
                continue
            group, edge = [], [f]
            group_of[f] = len(groups)
            while edge:
                c = edge.pop()
                group.append(c)
                for j in relation[c]:
                    if j in found and j not in group_of:
                        group_of[j] = len(groups)
                        edge.append(j)
            groups.append(sorted(group, key=lambda c: place[c]))
        for f in found:
            degree = len(relation[f] & found)
            size = len(groups[group_of[f]])
            for table, band in ((by_degree[tie], degree_band(degree)), (by_size[tie], size_band(size))):
                table[band][0] += int(gold[f])
                table[band][1] += 1
        ranked = sorted(groups, key=lambda g: (-len(g), place[g[0]]))
        top = ranked[0]
        largest[tie]["hits in it"].append(len(top))
        largest[tie]["of them gold"].append(sum(int(gold[c]) for c in top))
        largest[tie]["share of the question's gold chunks in it"].append(
            sum(int(gold[c]) for c in top) / max(int(gold[inside].sum()), 1))
        rest = [c for c in plain if c not in found]
        score(f"hits group by group from the largest ({tie}), then the rest", [c for g in ranked for c in g] + rest)
        taken, order = set(), []
        for g in ranked:
            around = sorted({j for c in g for j in relation[c] if j in within and j not in found}, key=lambda c: place[c])
            for c in g + around:
                if c not in taken:
                    taken.add(c)
                    order.append(c)
        order += [c for c in plain if c not in taken]
        score(f"each group followed by the chunks one step from it ({tie}), then the rest", order)
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

m = len(wanted)
print(f"\n{SET}: {m} questions, inside the gold's branch; gold chunks {gold_total}")
for tie in TIES:
    print(f"\n== two hits are tied when: {tie} ==")
    print("  how often a hit is gold, by the hits one step from it: "
          + "; ".join(f"{d}: {g} of {t} ({(g / t if t else 0):.2f})" for d, (g, t) in by_degree[tie].items()))
    print("  by the size of the group it hangs in: "
          + "; ".join(f"{s}: {g} of {t} ({(g / t if t else 0):.2f})" for s, (g, t) in by_size[tie].items()))
    print("  the largest group of a question, the middle (a quarter - three quarters): "
          + "; ".join(f"{name} {np.median(v):.2f} ({np.percentile(v, 25):.2f}-{np.percentile(v, 75):.2f})"
                      for name, v in largest[tie].items()))
print(f"\n== inside {BUDGET} characters: gold chunks delivered of {gold_total} | context_recall_id ==")
for name in delivered:
    print(f"  {delivered[name]} | {float(np.mean(recall[name])):.3f}  {name}")
print("done", flush=True)

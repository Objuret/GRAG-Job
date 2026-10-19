"""His 2026-10-11 "can our structure or scope help fix this somehow?", on the ten, inside the
gold's branch: what the three routes deliver (the tags; the chunk descriptions against the query
description; the chunk descriptions against the question), how the gold among it overlaps, what
the chunks NEXT TO a delivered chunk hold, and what a few orders give at the budget.

A route's set is what it alone would deliver inside the budget; nothing else is cut anywhere.
The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-10-gold-relationship/routes_and_structure.py [10smoke]
"""
import json
import os
import sys
import warnings
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from arms.artefact_v3 import file_adjacency  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "10smoke"
BUDGET = 72000
ROUTES = ("tags", "description", "question")

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("routes and structure")
layer, n = p.layer, len(p.chunk_ids)
docs, records, length = {}, [], np.zeros(n, dtype=np.int64)
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    records.append(frozenset(str(x) for x in ids))
    length[i] = len(text)
adjacency = file_adjacency([dict(r) for r in p.chunk_rows])
ptr, members = np.asarray(adjacency["ptr"]), np.asarray(adjacency["members"])
neighbours = [members[ptr[i]:ptr[i + 1]].tolist() for i in range(n)]
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b
id_rank = layer["id_rank"]


def kept_of(order):
    fits = np.cumsum(length[order]) <= BUDGET
    return int(fits.sum()) if fits.all() else int(np.argmin(fits))


def recall_of(order, cites):
    order = np.asarray(order, dtype=np.int64)
    kept = kept_of(order)
    got = set().union(*(records[i] for i in order[:kept])) if kept else set()
    return len(cites & got) / len(cites)


def in_turn(*orders):
    """One chunk from each order in turn, a chunk taken once."""
    out, seen = [], set()
    for row in zip(*orders):
        for i in row:
            i = int(i)
            if i not in seen:
                seen.add(i)
                out.append(i)
    return out


def with_neighbours(base):
    """The order `base`, and after each chunk taken the chunks next to it in its parent that are
    not taken yet."""
    out, seen = [], set()
    for i in base:
        for j in [int(i)] + [x for x in neighbours[int(i)]]:
            if j not in seen:
                seen.add(j)
                out.append(j)
    return out


def frontier_turn(orders, place):
    """The routes in turn and, as one more side, the structure: the chunk next to a chunk already
    taken that the routes place best (its best place over the routes); a chunk taken once."""
    out, seen, at = [], set(), [0] * len(orders)
    edge = set()
    total = len(orders[0])
    while len(out) < total:
        moved = False
        for r, order in enumerate(orders):
            while at[r] < total and int(order[at[r]]) in seen:
                at[r] += 1
            if at[r] < total:
                i = int(order[at[r]])
                seen.add(i)
                out.append(i)
                edge.update(j for j in neighbours[i] if j not in seen)
                moved = True
        edge -= seen
        if edge:
            i = min(edge, key=lambda j: (place[j], id_rank[j]))
            seen.add(i)
            out.append(i)
            edge.discard(i)
            edge.update(j for j in neighbours[i] if j not in seen)
            moved = True
        if not moved:
            break
    return out


CACHE = REPO / "output/private/artefact_v4_cache/querytag"


def cached_sides():
    """Every good cached first-call answer, the newest first: (time, the request's input, the answer)."""
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
    """The query side of a question from the cache: the description and the two tag lists of its
    newest good first-call answer, whatever the request's wording was. No model call."""
    def names(rows):
        return list(dict.fromkeys(str(r["t"]).strip() for r in rows or []
                                  if isinstance(r, dict) and str(r.get("t", "")).strip()))
    for _, user, raw in SIDES:
        if q.question in user:
            return str(raw["description"]), names(raw.get("tags")), names(raw.get("query_tags"))
    raise SystemExit(f"no cached first call for {q.id}")


done = 0
venn = Counter()
classes = Counter()
orders_recall = {}
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    description, tags, asked = side_of(q)
    got, _, _ = V._tag_cosines(description, tags, p)
    rows, d_description = list(got["tags"]), np.asarray(got["description"], dtype=np.float64)
    if asked:
        rows += list(V._tag_cosines(description, asked, p)[0]["tags"])
    rows = np.array(rows, dtype=np.float64)
    d_question = np.asarray(V._query_cosines(q.question, [], p)[0]["query_description_cosines"],
                            dtype=np.float64)
    done += 1
    if done % 10 == 0:
        print(f"  ... {done} questions", flush=True)
    on_edge = rows[:, layer["edge_tag"]]
    t_near, t_edge = WK.best_edges(on_edge.max(axis=0), layer["edge_chunk"], n)
    t_near = np.where(t_edge >= 0, t_near, t_near[t_edge >= 0].min())
    signal = {"tags": t_near, "description": d_description, "question": d_question}
    gold = np.array([bool(records[i] & cites) for i in range(n)])
    main = Counter(branch_of[np.flatnonzero(gold)].tolist()).most_common(1)[0][0]
    inside = np.flatnonzero(branch_of == main)
    order = {r: inside[np.lexsort((id_rank[inside], -signal[r][inside]))] for r in ROUTES}
    place = {r: dict(zip(order[r].tolist(), range(inside.size))) for r in ROUTES}
    best_place = {i: min(place[r][i] for r in ROUTES) for i in inside.tolist()}
    sets = {r: set(order[r][:kept_of(order[r])].tolist()) for r in ROUTES}
    for i in inside.tolist():
        held = tuple(r for r in ROUTES if i in sets[r])
        if gold[i]:
            venn[held] += 1
        venn[("all gold",)] += int(gold[i]) if not held else 0
        # the class of a chunk: how many routes deliver it; for the others whether it is next to one
        count = len(held)
        if count:
            name = f"delivered by {count} of the three routes"
        else:
            near = max((sum(j in sets[r] for r in ROUTES) for j in neighbours[i]), default=0)
            name = (f"not delivered, next to a chunk {near} routes deliver" if near
                    else "not delivered, next to none")
        classes[name, "chunks"] += 1
        classes[name, "gold"] += int(gold[i])
    cand = {
        "tags alone": order["tags"],
        "description alone": order["description"],
        "question alone": order["question"],
        "tags and description in turn (the 50/50)": in_turn(order["tags"], order["description"]),
        "tags, description and question in turn": in_turn(order["tags"], order["description"], order["question"]),
        "tags and description in turn, each chunk followed by the chunks next to it":
            with_neighbours(in_turn(order["tags"], order["description"])),
        "three in turn, each chunk followed by the chunks next to it":
            with_neighbours(in_turn(order["tags"], order["description"], order["question"])),
        "tags, description, then the best-placed chunk next to one already taken, in turn":
            frontier_turn([order["tags"], order["description"]], best_place),
        "tags, description, question, then the best-placed chunk next to one already taken, in turn":
            frontier_turn([order["tags"], order["description"], order["question"]], best_place),
    }
    # agreement first: the chunks more routes deliver, then (with structure) the chunks next to a
    # chunk at least two routes deliver, then the one-route chunks in turn, then everything else
    def agreed(routes, structure):
        held = {i: sum(i in sets[r] for r in routes) for i in inside.tolist()}
        spot = {i: sum(place[r][i] for r in routes) for i in inside.tolist()}
        out = sorted((i for i in held if held[i] >= 2), key=lambda i: (-held[i], spot[i], id_rank[i]))
        seen = set(out)
        if structure:
            near = {}
            for i in out:
                for j in neighbours[i]:
                    if j not in seen and branch_of[j] == main:
                        near[j] = min(near.get(j, len(out)), out.index(i))
            nxt = sorted(near, key=lambda j: (near[j], spot[j], id_rank[j]))
            out += nxt
            seen.update(nxt)
        rest = [i for i in in_turn(*(order[r] for r in routes)) if i not in seen]
        return out + rest

    cand.update({
        "tags and description: the chunks both deliver, then the rest in turn": agreed(("tags", "description"), False),
        "tags and description: the chunks both deliver, the chunks next to those, then the rest in turn":
            agreed(("tags", "description"), True),
        "three routes: delivered by three, by two, then the rest in turn": agreed(ROUTES, False),
        "three routes: delivered by three, by two, the chunks next to those, then the rest in turn":
            agreed(ROUTES, True),
    })
    for name, o in cand.items():
        orders_recall.setdefault(name, []).append(recall_of(o, cites))

print(f"{SET}: {len(wanted)} questions, inside the gold's branch, each route alone cut at {BUDGET} characters")
print("\n== the gold chunks by which routes deliver them ==")
for held, count in sorted(venn.items(), key=lambda kv: (-len(kv[0]), kv[0])):
    label = " and ".join(held) if held != ("all gold",) else "none of the three"
    print(f"  {label}: {count}")
print("\n== how often a chunk is gold, by what the routes say about it and about the chunks next to it ==")
for name in sorted({k[0] for k in classes}):
    c, g = classes[name, "chunks"], classes[name, "gold"]
    print(f"  {name}: {g} gold of {c} chunks ({g / c:.2f})")
print("\n== context_recall_id at the budget, mean over the questions ==")
for name, values in orders_recall.items():
    print(f"  {float(np.mean(values)):.3f}  {name}   per question: " + " ".join(f"{v:.2f}" for v in values))
print("done", flush=True)

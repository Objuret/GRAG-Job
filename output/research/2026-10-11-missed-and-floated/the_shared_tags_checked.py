"""The agent's own line, 2026-10-11 night, doubted: tags that two or more gold chunks share bring
chunks holding 69% of the gold (67% of them gold) against 44% and 37% for chunks drawn at random.
Four checks of that, on the hundred, inside the question's product, cached query side, no model
call.

  runs      the gold chunks come as runs of neighbours in a parent, and neighbours share tags. The
            control is drawn again as runs of the same lengths in parents of the same kind of
            chunk (20 draws a question, seed 20261011).
  the pick  the arm picks each query tag's five nearest among ALL the graph's tags and the border
            cuts afterwards. Here the five nearest are also taken among the product's own tags:
            how many chunks then carry a picked tag, how many of them gold, and how many of the
            gold's shared tags are picked.
  hops      from the picked tags to the chunks that carry them to the tags on those chunks: how
            many of the gold's shared tags stand one hop away, against tags of the product that
            sit on as many of its chunks.
  recurs    in how many products a tag occurs: the product's tags against the gold's shared tags.

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/the_shared_tags_checked.py [gold100]
"""
import json
import os
import random
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
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
CACHE = REPO / "output/private/artefact_v4_cache/querytag"
K = V._k_nearest()
MOST = 11
DRAWS = 20
LEVELS = ((1, 1, "one product"), (2, 3, "2-3"), (4, 7, "4-7"), (8, 15, "8-15"), (16, 99, "16 or more"))

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the shared tags, checked")
layer, n = p.layer, len(p.chunk_ids)
id_rank, kind = layer["id_rank"], layer["kind"]
et, ec, eligible = layer["edge_tag"], layer["edge_chunk"], layer["eligible"]
docs, records, parent, ordinal = {}, [], [], np.zeros(n, dtype=np.int64)
for i, row in enumerate(p.chunk_rows):
    _, ids = _resolve_chunk(row, docs)
    records.append(frozenset(str(x) for x in ids))
    parent.append(str(row["parent"]))
    ordinal[i] = int(row["ordinal"])
members = defaultdict(list)
for i in range(n):
    members[parent[i]].append(i)
for name in members:
    members[name].sort(key=lambda c: (ordinal[c], id_rank[c]))
spot = np.zeros(n, dtype=np.int64)
for chunks in members.values():
    for k, c in enumerate(chunks):
        spot[c] = k
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b
chunks_of_tag = defaultdict(set)
for e in range(et.size):
    chunks_of_tag[int(et[e])].add(int(ec[e]))
products_of_tag = {t: len({int(branch_of[c]) for c in chunks} - {-1}) for t, chunks in chunks_of_tag.items()}


def level_of(count):
    return next(name for low, high, name in LEVELS if low <= count <= high)


def cached_sides():
    out = []
    for f in CACHE.glob("*.json"):
        if f.name.endswith(".started.json"):
            continue
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        got = j.get("raw")
        if j.get("ok") and isinstance(got, dict) and got.get("description") and got.get("tags"):
            out.append((f.stat().st_mtime, (j.get("signature") or {}).get("user") or "", got))
    return sorted(out, key=lambda row: -row[0])


SIDES = cached_sides()


def side_of(q):
    def names(rows):
        return list(dict.fromkeys(str(r["t"]).strip() for r in rows or []
                                  if isinstance(r, dict) and str(r.get("t", "")).strip()))
    for _, user, got in SIDES:
        if q.question in user:
            return str(got["description"]), names(got.get("tags")), names(got.get("query_tags"))
    raise SystemExit(f"no cached first call for {q.id}")


def best_tags(of_product, wanted_set):
    """The tags that sit on two or more chunks of the set, picked one at a time for the balance
    between the set's chunks covered and the chunks brought that are not of the set."""
    here = {t: chunks for t, chunks in of_product.items() if len(chunks & wanted_set) >= 2}
    taken, best, picked = set(), 0., []
    while len(picked) < MOST:
        top, top_value = None, best
        for t, chunks in here.items():
            union = taken | chunks
            value = 2 * len(union & wanted_set) / (len(union) + len(wanted_set))
            if value > top_value + 1e-12:
                top, top_value = t, value
        if top is None:
            break
        taken |= here.pop(top)
        best = top_value
        picked.append(top)
    hit = len(taken & wanted_set)
    return picked, hit / max(len(wanted_set), 1), hit / max(len(taken), 1), len(taken), best


def runs_of(chunks):
    """The set as runs of neighbours: chunks of one parent at places that follow each other."""
    out, run = [], []
    for c in sorted(chunks, key=lambda c: (parent[c], spot[c])):
        if run and parent[c] == parent[run[-1]] and spot[c] == spot[run[-1]] + 1:
            run.append(c)
        else:
            if run:
                out.append(run)
            run = [c]
    if run:
        out.append(run)
    return out


def drawn_like(runs, parents_inside, draw):
    """As many runs of the same lengths, each in a parent of the same kind of chunk, no chunk twice."""
    taken = set()
    for run in sorted(runs, key=len, reverse=True):
        wanted_kind, size = int(kind[run[0]]), len(run)
        places = [(name, start) for name, chunks in parents_inside.items()
                  if int(kind[chunks[0]]) == wanted_kind
                  for start in range(len(chunks) - size + 1)]
        free = [(name, start) for name, start in places
                if not taken & set(parents_inside[name][start:start + size])]
        if not (free or places):
            taken |= set(run)
            continue
        name, start = draw.choice(free or places)
        taken |= set(parents_inside[name][start:start + size])
    return taken


draw = random.Random(20261011)
shared = defaultdict(list)
pick, hops, recurs = defaultdict(list), defaultdict(Counter), defaultdict(Counter)
done = 0
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    gold = {i for i in range(n) if records[i] & cites}
    main = Counter(branch_of[sorted(gold)].tolist()).most_common(1)[0][0]
    inside = set(np.flatnonzero(branch_of == main).tolist())
    gold &= inside
    of_product = {t: chunks & inside for t, chunks in chunks_of_tag.items() if eligible[t]}
    of_product = {t: chunks for t, chunks in of_product.items() if chunks}
    parents_inside = {name: [c for c in chunks if c in inside] for name, chunks in members.items()}
    parents_inside = {name: chunks for name, chunks in parents_inside.items() if chunks}

    # runs: the gold against sets drawn as runs of the same shape
    gold_runs = runs_of(gold)
    best, covered, pure, brought, balance = best_tags(of_product, gold)
    shared["the gold: runs"].append(len(gold_runs))
    shared["the gold: tags picked"].append(len(best))
    shared["the gold: share of its chunks covered"].append(covered)
    shared["the gold: share of the chunks brought that are gold"].append(pure)
    shared["the gold: balance of the two"].append(balance)
    rows_drawn = []
    for _ in range(DRAWS):
        other = drawn_like(gold_runs, parents_inside, draw)
        got = best_tags(of_product, other)
        rows_drawn.append((len(got[0]), got[1], got[2], got[4]))
    a = np.asarray(rows_drawn, dtype=np.float64).mean(axis=0)
    shared["runs drawn alike: tags picked"].append(a[0])
    shared["runs drawn alike: share of its chunks covered"].append(a[1])
    shared["runs drawn alike: share of the chunks brought that are of the set"].append(a[2])
    shared["runs drawn alike: balance of the two"].append(a[3])
    shared["questions where the gold's balance is above every draw's"].append(
        float(balance > max(r[3] for r in rows_drawn)))
    shared["questions where the gold's balance is above the draws' mean"].append(float(balance > a[3]))

    # the pick: among all the graph's tags (the arm) and among the product's own
    description, tags, asked = side_of(q)
    rows = list(V._tag_cosines(description, tags, p)[0]["tags"])
    if asked:
        rows += list(V._tag_cosines(description, asked, p)[0]["tags"])
    rows = np.array(rows, dtype=np.float64)
    own = np.array(sorted(of_product), dtype=np.int64)
    kth_all = np.sort(rows[:, eligible], axis=1)[:, ::-1][:, K - 1]
    kth_own = np.sort(rows[:, own], axis=1)[:, ::-1][:, min(K, own.size) - 1]
    picked = {"among all the graph's tags (the arm)": set(own[(rows[:, own] >= kth_all[:, None]).any(axis=0)].tolist()),
              "among the product's own tags": set(own[(rows[:, own] >= kth_own[:, None]).any(axis=0)].tolist())}
    by_size = defaultdict(list)
    for t, chunks in of_product.items():
        by_size[len(chunks)].append(t)
    for name, tag_set in picked.items():
        carried = set().union(*(of_product[t] for t in tag_set)) if tag_set else set()
        pick[name, "tags picked that sit in the product"].append(len(tag_set))
        pick[name, "chunks of the product that carry one"].append(len(carried))
        pick[name, "gold chunks among them"].append(len(carried & gold))
        pick[name, "share of the gold chunks among them"].append(len(carried & gold) / max(len(gold), 1))
        pick[name, "share of those chunks that are gold"].append(len(carried & gold) / max(len(carried), 1))
        pick[name, "the gold's shared tags that are picked (of them)"].append(
            len(set(best) & tag_set) / len(best) if best else np.nan)

        # hops from the picked tags: 0 picked, 1 on a chunk that carries a picked tag, 2 on a chunk
        # that shares a tag with such a chunk
        one = {t for t in of_product if of_product[t] & carried}
        two_chunks = set().union(*(of_product[t] for t in one)) if one else set()
        two = {t for t in of_product if of_product[t] & two_chunks}

        def hop(t):
            return "0" if t in tag_set else "1" if t in one else "2" if t in two else "further"
        for t in best:
            hops[name, "the gold's shared tags"][hop(t)] += 1
            for other in draw.sample(by_size[len(of_product[t])], min(20, len(by_size[len(of_product[t])]))):
                hops[name, "tags of the product on as many chunks"][hop(other)] += 1

    # recurs: in how many products a tag occurs
    for t in of_product:
        recurs["the product's tags"][level_of(products_of_tag[t])] += 1
        if len(of_product[t]) >= 2:
            recurs["the product's tags on two or more of its chunks"][level_of(products_of_tag[t])] += 1
    for t in best:
        recurs["the gold's shared tags"][level_of(products_of_tag[t])] += 1
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

print(f"\n{SET}: {len(wanted)} questions, inside the question's product; a query tag picks its {K} nearest")
print("\n== runs: tags on two or more chunks of a set, picked with the set in hand (at most 11) ==")
for name, values in shared.items():
    if name.startswith("questions"):
        print(f"  {name}: {int(sum(values))} of {len(values)}")
        continue
    q1, mid, q3 = np.percentile(values, [25, 50, 75])
    print(f"  {name}: {mid:.2f} ({q1:.2f}-{q3:.2f}); mean {float(np.mean(values)):.2f}")
print("\n== the pick: each query tag's five nearest (middles; mean) ==")
for (name, what), values in pick.items():
    values = [v for v in values if not np.isnan(v)]
    q1, mid, q3 = np.percentile(values, [25, 50, 75])
    print(f"  {name} | {what}: {mid:.2f} ({q1:.2f}-{q3:.2f}); mean {float(np.mean(values)):.2f}")
print("\n== hops from the picked tags (share of the tags at each distance) ==")
for (name, what), counts in hops.items():
    total = sum(counts.values())
    print(f"  {name} | {what} ({total}): " + ", ".join(f"{k}: {counts[k] / total:.2f}" for k in ("0", "1", "2", "further")))
print("\n== recurs: in how many products a tag occurs (share of the tags at each level) ==")
for what, counts in recurs.items():
    total = sum(counts.values())
    print(f"  {what} ({total}): " + ", ".join(f"{name}: {counts[name] / total:.2f}" for _, _, name in LEVELS))
print("done", flush=True)

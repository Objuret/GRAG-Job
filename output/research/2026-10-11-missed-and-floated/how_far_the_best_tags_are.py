"""After `the_best_tags_there_are` (about 5 of the product's own tags bring chunks that hold the
gold, 83% of them gold): how far those tags are from what the question's query tags reach today,
and how long the product's tag list is.

On the hundred, inside the question's product, cached query side, no model call. The best tags
are picked with the gold in hand as before. For each of them: its place among ALL the graph's
tags by nearness to a query tag, the best over the query tags (place 5 or better is what the arm
picks today), and its place among the product's own tags.

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/how_far_the_best_tags_are.py [gold100]
"""
import json
import os
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
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
CACHE = REPO / "output/private/artefact_v4_cache/querytag"
MOST = 11

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("how far the best tags are")
layer, n = p.layer, len(p.chunk_ids)
et, ec, eligible = layer["edge_tag"], layer["edge_chunk"], layer["eligible"]
docs, records = {}, []
for row in p.chunk_rows:
    _, ids = _resolve_chunk(row, docs)
    records.append(frozenset(str(x) for x in ids))
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b
chunks_of_tag = defaultdict(set)
for e in range(et.size):
    chunks_of_tag[int(et[e])].add(int(ec[e]))


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


pool_place, product_place, list_tags, list_chars = [], [], [], []
bands = Counter()
done = 0
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    gold = {i for i in range(n) if records[i] & cites}
    main = Counter(branch_of[sorted(gold)].tolist()).most_common(1)[0][0]
    inside = set(np.flatnonzero(branch_of == main).tolist())
    gold &= inside
    of_product = {t: chunks & inside for t, chunks in chunks_of_tag.items()}
    of_product = {t: chunks for t, chunks in of_product.items() if chunks}
    list_tags.append(len(of_product))
    list_chars.append(sum(len(str(p.graph_tags[t])) + 2 for t in of_product))
    here = {t: chunks for t, chunks in of_product.items() if chunks & gold}
    taken, best, picked = set(), 0., []
    while len(picked) < MOST:
        top, top_value = None, best
        for t, chunks in here.items():
            union = taken | chunks
            value = 2 * len(union & gold) / (len(union) + len(gold))
            if value > top_value + 1e-12:
                top, top_value = t, value
        if top is None:
            break
        taken |= here.pop(top)
        best = top_value
        picked.append(top)
    description, tags, asked = side_of(q)
    answer, _, _ = V._tag_cosines(description, tags, p)
    rows = list(answer["tags"])
    if asked:
        rows += list(V._tag_cosines(description, asked, p)[0]["tags"])
    rows = np.array(rows, dtype=np.float64)
    place = np.full(rows.shape, np.inf)
    place[:, eligible] = np.array([rankdata(-row[eligible], method="min") for row in rows])
    members = np.array(sorted(of_product), dtype=np.int64)
    inside_place = np.array([rankdata(-row[members], method="min") for row in rows])
    at = {int(t): k for k, t in enumerate(members)}
    for t in picked:
        best_pool = float(place[:, t].min())
        pool_place.append(best_pool)
        product_place.append(float(inside_place[:, at[t]].min()))
        bands["within the 5 nearest (picked today)" if best_pool <= 5 else "places 6-20" if best_pool <= 20
              else "places 21-100" if best_pool <= 100 else "further"] += 1
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

print(f"\n{SET}: {len(wanted)} questions; the best tags picked with the gold in hand: {len(pool_place)}")
for name, values in (("place of such a tag among all the graph's tags, by nearness to its nearest query tag", pool_place),
                     ("its place among the product's own tags", product_place),
                     ("tags in the product's own list", list_tags),
                     ("characters of that list", list_chars)):
    q1, mid, q3 = np.percentile(values, [25, 50, 75])
    print(f"  {name}: {mid:,.0f} ({q1:,.0f}-{q3:,.0f})")
print("  those tags by place among all the graph's tags: " + ", ".join(f"{k}: {v}" for k, v in bands.most_common()))
print("done", flush=True)

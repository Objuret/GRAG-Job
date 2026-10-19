"""The agent's own question, 2026-10-11 night: every route stops near 0.5 inside the product. Is that
because the gold does not hang together in what the graph holds, or because the query side does
not land where the gold is? With the gold in hand (this is not a retrieval): order the product's
chunks by nearness to the MIDDLE of the gold chunks, each gold chunk measured against the middle
of the OTHER gold chunks so it cannot find itself.

On the hundred, inside the question's product, cached query side, no model call. Two spaces:
  descriptions   a chunk is its description vector
  tags           a chunk is the middle of its tags' vectors
Printed per space: context_recall_id of that order at 72,000 characters (what one right landing
point could reach), the place of a gold chunk in it, how near the query description and the
question stand to that middle against how near the gold chunks stand to it, and from a gold
chunk the share of its five nearest chunks that are gold (from a chunk that is not gold: the
same share). A middle of several clouds stands between them, so the other end is printed too:
every gold chunk a landing point, a chunk valued by its nearness to the nearest OTHER gold chunk.

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/is_the_gold_one_cloud.py [gold100]
"""
import json
import os
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
BUDGET = 72000
CACHE = REPO / "output/private/artefact_v4_cache/querytag"
NEAREST = 5

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("is the gold one cloud")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
et, ec = layer["edge_tag"], layer["edge_chunk"]
docs, record_sets, length = {}, [], np.zeros(n, dtype=np.int64)
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    record_sets.append(frozenset(str(x) for x in ids))
    length[i] = len(text)
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b


def unit(rows):
    rows = np.asarray(rows, dtype=np.float64)
    size = np.linalg.norm(rows, axis=-1, keepdims=True)
    return rows / np.where(size > 0, size, 1.)


CV = unit(p.chunk_vectors)
TV = unit(p.tag_vectors)
summed = np.zeros_like(CV)
np.add.at(summed, ec, TV[et])
SPACES = {"descriptions": CV, "tags (the middle of a chunk's tags)": unit(summed)}
AXES = V._QueryAxes(TV, np.eye(CV.shape[1]))
print("prepared", flush=True)


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


def delivered(order, cites):
    fits = np.cumsum(length[order]) <= BUDGET
    kept = order[:int(fits.sum()) if fits.all() else int(np.argmin(fits))]
    got = set().union(*(record_sets[i] for i in kept)) if kept.size else set()
    return len(cites & got) / len(cites)


facts = defaultdict(list)
done = 0
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    description, tags, asked = side_of(q)
    vectors = {"the query description": np.asarray(
        V._query_cosines(description, [], AXES)[0]["query_description_cosines"], dtype=np.float64),
        "the question": np.asarray(
        V._query_cosines(q.question, [], AXES)[0]["query_description_cosines"], dtype=np.float64)}
    gold = np.array([bool(record_sets[i] & cites) for i in range(n)])
    main = Counter(branch_of[np.flatnonzero(gold)].tolist()).most_common(1)[0][0]
    inside = np.flatnonzero(branch_of == main)
    is_gold = gold[inside]
    if is_gold.sum() < 2:
        continue
    for space, matrix in SPACES.items():
        rows = matrix[inside]
        total = rows[is_gold].sum(axis=0)
        middle = unit(total)
        score = rows @ middle
        # a gold chunk against the middle of the other gold chunks
        for k in np.flatnonzero(is_gold):
            score[k] = float(rows[k] @ unit(total - rows[k]))
        order = np.lexsort((id_rank[inside], -score))
        facts[space, "context_recall_id, the product ordered by nearness to the middle of the gold"].append(
            delivered(inside[order], cites))
        place = np.empty(order.size, dtype=np.int64)
        place[order] = np.arange(1, order.size + 1)
        facts[space, "place of a gold chunk in that order (the middle of the question's gold chunks)"].append(
            float(np.median(place[is_gold])))
        facts[space, "gold chunks of the question"].append(int(is_gold.sum()))
        facts[space, "chunks of the product"].append(int(inside.size))
        facts[space, "closeness of a gold chunk to the middle of the other gold chunks"].append(
            float(np.median(score[is_gold])))
        facts[space, "closeness of a chunk that is not gold to the middle of the gold"].append(
            float(np.median(score[~is_gold])))
        if space == "descriptions":
            for name, vector in vectors.items():
                facts[space, f"closeness of {name} to the middle of the gold"].append(float(vector @ middle))
                near = rows @ vector
                facts[space, f"context_recall_id, the product ordered by nearness to {name}"].append(
                    delivered(inside[np.lexsort((id_rank[inside], -near))], cites))
                facts[space, f"share of the product's chunks nearer the middle of the gold than {name} is"].append(
                    float(((rows @ middle) > float(vector @ middle)).mean()))
        among = rows @ rows.T
        np.fill_diagonal(among, -np.inf)
        # every gold chunk a landing point: a chunk's nearness to its nearest OTHER gold chunk
        to_gold = among[:, np.flatnonzero(is_gold)].max(axis=1)
        facts[space, "context_recall_id, the product ordered by nearness to the nearest other gold chunk "
                     "(every gold chunk a landing point)"].append(
            delivered(inside[np.lexsort((id_rank[inside], -to_gold))], cites))
        # the best one, two and three gold chunks as landing points (picked with the gold in hand,
        # one at a time), every other chunk by its nearness to the nearest of them
        golds, chosen = np.flatnonzero(is_gold).tolist(), []

        def reach(landings):
            value = among[:, landings].max(axis=1)
            value[landings] = np.inf
            return delivered(inside[np.lexsort((id_rank[inside], -value))], cites)
        for step in range(3):
            tried = [(reach(chosen + [g]), -g) for g in golds if g not in chosen]
            if not tried:
                break
            top, g = max(tried)
            chosen.append(-g)
            facts[space, f"context_recall_id from the best {step + 1} gold chunk(s) as landing points, the rest by "
                         "nearness to the nearest of them"].append(top)
        if space == "descriptions":
            for name, vector in vectors.items():
                order_q = np.lexsort((id_rank[inside], -(rows @ vector)))
                place_q = np.empty(order_q.size, dtype=np.int64)
                place_q[order_q] = np.arange(1, order_q.size + 1)
                facts[space, f"place of the best single landing point by nearness to {name}"].append(
                    float(place_q[chosen[0]]))
                facts[space, f"place of the best-placed of those landing points by nearness to {name}"].append(
                    float(place_q[chosen].min()))
        nearest = np.argsort(-among, axis=1)[:, :NEAREST]
        share = is_gold[nearest].mean(axis=1)
        facts[space, f"from a gold chunk, share of its {NEAREST} nearest chunks that are gold"].append(
            float(share[is_gold].mean()))
        facts[space, f"from a chunk that is not gold, the same share"].append(float(share[~is_gold].mean()))
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

print(f"\n{SET}: {done} questions with two or more gold chunks, inside the question's product")
last = None
for (space, name), values in facts.items():
    if space != last:
        print(f"\n== {space} ==")
        last = space
    q1, mid, q3 = np.percentile(values, [25, 50, 75])
    print(f"  {name}: mean {float(np.mean(values)):.3f}; the middle {mid:.3f} ({q1:.3f}-{q3:.3f})")
print("done", flush=True)

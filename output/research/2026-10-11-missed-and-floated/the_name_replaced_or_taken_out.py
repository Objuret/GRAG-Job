"""A detail of the order before it is built (2026-10-12): the product's name in the question replaced
by the words "the product", or simply taken out. Otherwise as the script it is made from:

The order recommended to him on 2026-10-12, run on the hundred through the arm's own border and the
arm's own delivery (`_budget_contexts`, the 72,000 characters), beside the arm as it stands. A
side run: the arm's file is not changed. No model call (HERB_V4_OFFLINE=on, the cached first
calls).

The order, inside the border the product's name sets (`scope_by_name`):
  the combo   the chunk side's nearness and the tags' nearness (a chunk's closest tag to any
              query tag, `v4_walk.tags_nearness`) are each cut into five clusters
              (`v4_walk.levels`); a chunk's step is its two levels added, the overlap of the two
              first clusters first; chunks on one step by their two values added.
  the chunk side   the chunk descriptions against the query description; or against the question
              without the product's name; or both added.
  the scope   gauged AFTER the combo from its first two steps: the parents (a channel, a file)
              that hold the most of those chunks, taken until they hold more than half. Used as
              weight: inside a step the chunks in scope go first; or a chunk in scope moves up
              one step. The "more than half" and the "one step" are the agent's.

Printed per order: the first delivered chunk is gold (of 100), context_recall_id (share of the
cited records delivered inside 72,000 characters), and against the arm as it stands: questions
higher and lower, mean difference with its standard error.

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/the_combo_and_scope_through_the_arm.py [gold100]
"""
import json
import os
import re
import sys
import warnings
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"
os.environ.pop("HERB_V4_SCOPE_STEP", None)

from arms import artefact_v4 as V  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
BUDGET = 72000
CLUSTERS = 5
CACHE = REPO / "output/private/artefact_v4_cache/querytag"
TOKEN = re.compile(r"[a-z0-9]+")

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the combo and scope through the arm")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
parents = [str(row["parent"]) for row in p.chunk_rows]
parent_ids = {name: k for k, name in enumerate(sorted(set(parents)))}
parent_of = np.array([parent_ids[name] for name in parents], dtype=np.int64)
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


def standing(x):
    x = np.asarray(x, dtype=np.float64)
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


def without_the_names(question, names, word="the product"):
    out = question
    for name in names:
        parts = TOKEN.findall(name.lower())
        if parts:
            pattern = re.compile(r"(?<![A-Za-z0-9])" + r"[^A-Za-z0-9]*".join(re.escape(part) for part in parts)
                                 + r"(?![A-Za-z0-9])", re.IGNORECASE)
            out = pattern.sub(word, out)
    return " ".join(out.split())


def majority(hits, areas):
    ids = np.unique(areas)
    held = np.array([int(hits[areas == a].sum()) for a in ids])
    if not held.sum():
        return np.ones(areas.size, dtype=bool)
    taken, total = [], 0
    for k in np.lexsort((ids, -held)):
        taken.append(ids[k])
        total += held[k]
        if total * 2 > held.sum():
            break
    return np.isin(areas, taken)


def combo(chunk_side, tags_side, inside, scope_use):
    D, T = np.asarray(chunk_side, dtype=np.float64)[inside], np.asarray(tags_side, dtype=np.float64)[inside]
    step = (WK.levels(D, CLUSTERS) + WK.levels(T, CLUSTERS)).astype(np.float64)
    z = standing(D) + standing(T)
    hits = step <= 3 if (step <= 3).any() else step == step.min()
    scope = majority(hits, parent_of[inside])
    if scope_use == "none":
        keys = (id_rank[inside], -z, step)
    elif scope_use == "first inside a step":
        keys = (id_rank[inside], -z, ~scope, step)
    else:
        keys = (id_rank[inside], -z, step - scope)
    return inside[np.lexsort(keys)]


ORDERS = (
    ("the name replaced by 'the product', no scope below the product", "bare", "none"),
    ("the name replaced by 'the product', in-scope chunks first inside a step", "bare", "first inside a step"),
    ("the name taken out, no scope below the product", "gone", "none"),
    ("the name taken out, in-scope chunks first inside a step", "gone", "first inside a step"),
)
results = {"the arm as it stands": ([], [])}
for name, _, _ in ORDERS:
    results[name] = ([], [])
done = 0
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    out = V.answer_one_question((qid, q.question), p, None, 50, BUDGET)
    delivered = {str(x) for x in out.context_ids}
    chunks = [[str(x) for x in c] for c in (out.meta.get("chunk_ids") or []) if c]
    whole = [c for c in chunks if set(c) <= delivered]
    results["the arm as it stands"][0].append(bool(whole and set(whole[0]) & cites))
    results["the arm as it stands"][1].append(len(cites & delivered) / len(cites))
    description, tags, asked = side_of(q)
    answer = V._tag_cosines(description, tags, p)[0]
    rows, d_description = list(answer["tags"]), np.asarray(answer["description"], dtype=np.float64)
    if asked:
        rows += list(V._tag_cosines(description, asked, p)[0]["tags"])
    t_near, _ = WK.tags_nearness(layer, np.array(rows, dtype=np.float64))
    border, scope = V.scope_by_name(q.question, p.tree, n)
    inside = np.flatnonzero(border) if border.any() else np.arange(n)
    bare = without_the_names(q.question, scope["names_in_the_question"])
    d_bare = np.asarray(V._query_cosines(bare, [], p)[0]["query_description_cosines"], dtype=np.float64)
    gone = without_the_names(q.question, scope["names_in_the_question"], word="")
    d_gone = np.asarray(V._query_cosines(gone, [], p)[0]["query_description_cosines"], dtype=np.float64)
    sides = {"bare": d_bare, "gone": d_gone}
    doc_cache = {}
    for name, side, scope_use in ORDERS:
        order = combo(sides[side], t_near, inside, scope_use)
        contexts, id_lists, context_ids, budget = V._budget_contexts([p.chunk_rows[i] for i in order.tolist()], BUDGET, doc_cache)
        got = {str(x) for x in context_ids}
        first = {str(x) for x in (id_lists[0] if id_lists else [])}
        results[name][0].append(bool(first & cites))
        results[name][1].append(len(cites & got) / len(cites))
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

print(f"\n{SET}: {len(wanted)} questions")
print("== the first delivered chunk is gold | context_recall_id | against the arm as it stands: questions higher / lower, "
      "mean difference (standard error) ==")
base = np.asarray(results["the arm as it stands"][1])
for name, (first, recall) in results.items():
    diff = np.asarray(recall) - base
    print(f"  {int(sum(first))} of {len(first)} | {float(np.mean(recall)):.3f} | {int((diff > 0).sum())} / {int((diff < 0).sum())}, "
          f"{float(diff.mean()):+.3f} ({float(diff.std(ddof=1) / np.sqrt(diff.size)):.3f})  {name}")
print("done", flush=True)

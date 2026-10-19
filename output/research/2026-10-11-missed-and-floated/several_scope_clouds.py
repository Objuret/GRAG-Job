"""His 2026-10-11 "perhaps we can make the scope clouds better. Perhaps we take several clouds. For
example if there's a relevance cloud at the top for a specific scope, the combination is scope,
and high value is supposed to be a sort of cloud, right? Perhaps we just take several such scope
clouds? Or bad?"

On the hundred, inside the question's product, cached query side, no model call. The relevance is
the three routes' standings added. The agent's reading of his cloud, every part of it the agent's
choice: the scope is the parent (a channel or a file); the high values are the first of five
clusters the product's relevance values fall into; a scope cloud is a parent together with its
high chunks. The clouds are taken one after another from the top, as many as fit; what is left of
the 72,000 characters is filled by the plain order.

Two ways of saying which cloud is higher: by its best chunk, or by the sum of its high chunks'
values. Three ways of saying what a cloud delivers: its high chunks; the stretch of its parent
from its first to its last high chunk, with what lies between; its whole parent.

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/several_scope_clouds.py [gold100]
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
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
BUDGET = 72000
CACHE = REPO / "output/private/artefact_v4_cache/querytag"
K = V._k_nearest()

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("several scope clouds")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
et, ec = layer["edge_tag"], layer["edge_chunk"]
docs, records, length, parent, ordinal = {}, [], np.zeros(n, dtype=np.int64), [], np.zeros(n, dtype=np.int64)
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    records.append(frozenset(str(x) for x in ids))
    length[i] = len(text)
    parent.append(str(row["parent"]))
    ordinal[i] = int(row["ordinal"])
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


def kept_of(order):
    fits = np.cumsum(length[order]) <= BUDGET
    return int(fits.sum()) if fits.all() else int(np.argmin(fits))


def standing(x):
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


facts = defaultdict(list)
by_k = defaultdict(list)
delivered, recall, clouds_in = Counter(), defaultdict(list), defaultdict(list)
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
    gold = np.array([bool(records[i] & cites) for i in range(n)])
    main = Counter(branch_of[np.flatnonzero(gold)].tolist()).most_common(1)[0][0]
    inside = np.flatnonzero(branch_of == main)
    gold_total += int(gold[inside].sum())
    t_near, t_edge = WK.best_edges(rows[:, et].max(axis=0), ec, n)
    t_near = np.where(t_edge >= 0, t_near, t_near[t_edge >= 0].min())
    base = standing(t_near[inside]) + standing(d_description[inside]) + standing(d_question[inside])
    value = dict(zip(inside.tolist(), base.tolist()))
    plain = inside[np.lexsort((id_rank[inside], -base))].tolist()
    high = set(inside[WK.levels(base, K) == 1].tolist())
    in_parent = defaultdict(list)
    for c in inside.tolist():
        in_parent[parent[c]].append(c)
    for members in in_parent.values():
        members.sort(key=lambda c: (ordinal[c], id_rank[c]))
    clouds = {name: [c for c in members if c in high] for name, members in in_parent.items()}
    clouds = {name: members for name, members in clouds.items() if members}
    gold_here = int(gold[inside].sum())
    facts["parents of the product"].append(len(in_parent))
    facts["chunks with a high value"].append(len(high))
    facts["of them gold"].append(sum(int(gold[c]) for c in high))
    facts["scope clouds (parents with a high chunk)"].append(len(clouds))
    facts["share of the gold chunks that have a high value"].append(sum(int(gold[c]) for c in high) / max(gold_here, 1))
    facts["share of the gold chunks in a parent with a cloud"].append(
        sum(int(gold[c]) for name in clouds for c in in_parent[name]) / max(gold_here, 1))
    facts["chunks in the parents with a cloud"].append(sum(len(in_parent[name]) for name in clouds))

    def score(name, order, taken_clouds=None):
        order = np.asarray(order, dtype=np.int64)
        kept = order[:kept_of(order)]
        delivered[name] += int(gold[kept].sum())
        got = set().union(*(records[i] for i in kept)) if kept.size else set()
        recall[name].append(len(cites & got) / len(cites))
        if taken_clouds is not None:
            held = set(kept.tolist())
            clouds_in[name].append(sum(1 for members in taken_clouds if held & set(members)))

    score("the plain order", plain)
    ranked_by = {
        "the cloud with the best chunk first": sorted(clouds, key=lambda s: (-max(value[c] for c in clouds[s]), s)),
        "the cloud holding the most high value first": sorted(
            clouds, key=lambda s: (-sum(value[c] for c in clouds[s]), s)),
    }
    for how, ranked in ranked_by.items():
        units = {
            "its high chunks": [sorted(clouds[s], key=lambda c: -value[c]) for s in ranked],
            "the stretch from its first to its last high chunk": [
                in_parent[s][in_parent[s].index(clouds[s][0]): in_parent[s].index(clouds[s][-1]) + 1] for s in ranked],
            "its whole parent": [in_parent[s] for s in ranked],
        }
        for what, groups in units.items():
            seen, order = set(), []
            for group in groups:
                for c in group:
                    if c not in seen:
                        seen.add(c)
                        order.append(c)
            order += [c for c in plain if c not in seen]
            score(f"{how}; a cloud delivers {what}", order, groups)
        # one cloud only, then the plain order
        first = units["the stretch from its first to its last high chunk"][0]
        score(f"{how}; ONE cloud only (its stretch), then the plain order",
              first + [c for c in plain if c not in set(first)], [first])
    # the same two readings with the relevance cut into three to seven clusters, the first being "high"
    for k in (3, 4, 5, 6, 7):
        high_k = set(inside[WK.levels(base, k) == 1].tolist())
        clouds_k = {name: [c for c in members if c in high_k] for name, members in in_parent.items()}
        clouds_k = {name: members for name, members in clouds_k.items() if members}
        by_k[k, "chunks with a high value"].append(len(high_k))
        by_k[k, "clouds"].append(len(clouds_k))
        by_k[k, "gold in a parent with a cloud"].append(
            sum(int(gold[c]) for name in clouds_k for c in in_parent[name]) / max(gold_here, 1))
        by_k[k, "chunks in those parents"].append(sum(len(in_parent[name]) for name in clouds_k))
        ranked = sorted(clouds_k, key=lambda s: (-max(value[c] for c in clouds_k[s]), s))
        for what, groups in (("its high chunks", [sorted(clouds_k[s], key=lambda c: -value[c]) for s in ranked]),
                             ("its whole parent", [in_parent[s] for s in ranked])):
            seen, order = set(), []
            for group in groups:
                for c in group:
                    if c not in seen:
                        seen.add(c)
                        order.append(c)
            order = np.asarray(order + [c for c in plain if c not in seen], dtype=np.int64)
            kept = order[:kept_of(order)]
            got = set().union(*(records[i] for i in kept)) if kept.size else set()
            by_k[k, what].append(len(cites & got) / len(cites))
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

print(f"\n{SET}: {len(wanted)} questions, inside the question's product; gold chunks {gold_total}")
print("== per question, the middle (a quarter - three quarters) ==")
for name, values in facts.items():
    q1, mid, q3 = np.percentile(values, [25, 50, 75])
    digits = 2 if "share" in name else 0
    print(f"  {name}: {mid:.{digits}f} ({q1:.{digits}f}-{q3:.{digits}f})")
first_name = "the plain order"
print(f"\n== inside {BUDGET} characters: gold chunks delivered of {gold_total} | context_recall_id | against the plain "
      "order: mean difference, its standard error, questions higher / lower | clouds with a chunk delivered, the "
      "middle ==")
for name in recall:
    diff = np.asarray(recall[name]) - np.asarray(recall[first_name])
    extra = f" | {np.median(clouds_in[name]):.0f}" if clouds_in[name] else ""
    print(f"  {delivered[name]} | {float(np.mean(recall[name])):.3f} | {float(diff.mean()):+.3f}, "
          f"{float(diff.std(ddof=1) / np.sqrt(diff.size)):.3f}, {int((diff > 0).sum())} / {int((diff < 0).sum())}"
          f"{extra}  {name}")
plain_recall = np.asarray(recall[first_name])
print("\n== the relevance cut into three to seven clusters, the first being high; clouds from the best chunk: chunks "
      "with a high value | clouds | share of the gold in a parent with a cloud | chunks in those parents (middles) || "
      "a cloud delivers its high chunks: context_recall_id, against the plain order, its standard error || its whole "
      "parent: the same ==")
for k in (3, 4, 5, 6, 7):
    cells = []
    for what in ("its high chunks", "its whole parent"):
        values = np.asarray(by_k[k, what])
        diff = values - plain_recall
        cells.append(f"{values.mean():.3f}, {diff.mean():+.3f}, {diff.std(ddof=1) / np.sqrt(diff.size):.3f}")
    print(f"  {k} clusters: {np.median(by_k[k, 'chunks with a high value']):.0f} | {np.median(by_k[k, 'clouds']):.0f} | "
          f"{np.median(by_k[k, 'gold in a parent with a cloud']):.2f} | {np.median(by_k[k, 'chunks in those parents']):.0f} || "
          + " || ".join(cells))
print("done", flush=True)

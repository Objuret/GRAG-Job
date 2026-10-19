"""His 2026-10-11 "those chunks, compare those to those that always gets floated, to see what the
diff is, is the descriptions of them bad, is the tags bad etc".

On the hundred, inside the gold's branch, cached query side, no model call. The order is the three
routes' standings added (tags, description against the query description, description against the
question), cut at 72,000 characters. Per question a chunk of the branch is one of: gold and
floated, gold and missed, not gold and floated, the rest. The groups are set side by side inside
each kind of chunk, because the kinds are floated at very different rates.

Read off a chunk, question-free:
  - its records, its characters, its description's characters, its tags;
  - how many chunks of its branch carry each of its tags;
  - per record of it: the record's own text set against every chunk description of the branch,
    and against every chunk's tags (records, descriptions and tags all behind "passage: ", the
    vectors on the side from 2026-10-07): at which place does the record's own chunk come.
Read per question:
  - its place in the branch by each route alone;
  - how near its records themselves are to the question (the vector baseline's reading: record
    behind "passage: ", question behind "query: "), as the share of the branch's records that
    are nearer.

The gold ids are read inside this script; it prints numbers only: no question, no description and
no record text.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/missed_and_floated.py [gold100]
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
os.environ["HERB_V4_SCOPE_STEP"] = "both"      # the description texts are read here, not by the arm

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from arms.artefact_v3 import file_adjacency  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
BUDGET = 72000
ROUTES = ("tags", "description", "question")
CACHE = REPO / "output/private/artefact_v4_cache/querytag"
KEPT = REPO / "output/embed_local/20261007_rev113abe4acafa_float32"
GROUPS = ("gold and floated", "gold and missed", "not gold and floated")


def unit_rows(m):
    m = np.asarray(m, dtype=np.float32)
    return m / np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-12)


wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("missed and floated")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
kind_names, kind_of = layer["kind_names"], layer["kind"]
et, ec = layer["edge_tag"], layer["edge_chunk"]

docs, records, length = {}, [], np.zeros(n, dtype=np.int64)
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    records.append([str(x) for x in ids])
    length[i] = len(text)
record_sets = [frozenset(r) for r in records]
texts = {}
for line in (KEPT / "descriptions.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        row = json.loads(line)
        texts[str(row["id"])] = len(row["text"])
d_chars = np.array([texts.get(str(c), -1) for c in p.chunk_ids], dtype=np.int64)

corpus = np.load(KEPT / "corpus_passage.npz", allow_pickle=True)
row_of = {str(r): k for k, r in enumerate(corpus["ids"])}
M = np.asarray(corpus["matrix"], dtype=np.float32)
asked_vectors = np.load(KEPT / "question_query_vecs.npz", allow_pickle=True)
question_at = {str(q): k for k, q in enumerate(asked_vectors["ids"])}
passage = np.load(KEPT / "descriptions_passage.npz", allow_pickle=True)
at = {str(c): k for k, c in enumerate(passage["ids"])}
DP = unit_rows(passage["matrix"][[at[str(c)] for c in p.chunk_ids]])
tag_passage = np.load(KEPT / "tags_passage.npz", allow_pickle=True)
tag_at = {str(t): k for k, t in enumerate(tag_passage["ids"])}
TP = unit_rows(tag_passage["matrix"])
tag_row = np.array([tag_at.get(str(t), -1) for t in p.graph_tags], dtype=np.int64)
rows_of = [np.array([row_of[r] for r in recs if r in row_of], dtype=np.int64) for recs in records]
print(f"{SET}: {len(wanted)} questions; pool {n} chunks; descriptions with a text {int((d_chars >= 0).sum())}; "
      f"chunks with a record vector {sum(r.size > 0 for r in rows_of)}; eligible edges {et.size}, of them on a tag "
      f"with a passage vector {int((tag_row[et] >= 0).sum())}", flush=True)

branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b
adjacency = file_adjacency([dict(r) for r in p.chunk_rows])
ptr, members = np.asarray(adjacency["ptr"]), np.asarray(adjacency["members"])
next_to = [set(members[ptr[i]:ptr[i + 1]].tolist()) for i in range(n)]

# question-free: per (chunk, record) the place of the chunk when the record's own text is set
# against the branch's descriptions, and against the branch's chunks through their tags; per chunk
# how many chunks of the branch carry its tags
place_desc, place_tags = {}, {}
tag_carried, tag_own = np.full(n, np.nan), np.full(n, np.nan)
branch_rows = {}
for b, (_, chunks) in enumerate(branches):
    inside = np.asarray(chunks, dtype=np.int64)
    local = {int(c): k for k, c in enumerate(inside)}
    rr = np.unique(np.concatenate([rows_of[c] for c in inside] or [np.zeros(0, dtype=np.int64)]))
    branch_rows[b] = rr
    sel = np.flatnonzero(np.isin(ec, inside))
    tags_here, inv = np.unique(et[sel], return_inverse=True)
    carried = np.bincount(inv)                       # chunks of the branch carrying each tag
    chunk_local = np.array([local[int(c)] for c in ec[sel]], dtype=np.int64)
    for k, c in enumerate(inside):
        mine = carried[inv[chunk_local == k]]
        if mine.size:
            tag_carried[c], tag_own[c] = float(np.median(mine)), float((mine == 1).mean())
    if not rr.size:
        continue
    col_of = {int(r): j for j, r in enumerate(rr)}
    R = M[rr]
    S = DP[inside] @ R.T                             # chunks x records
    has = tag_row[tags_here] >= 0
    TS = np.full((tags_here.size, rr.size), -np.inf, dtype=np.float32)
    TS[has] = TP[tag_row[tags_here[has]]] @ R.T      # tags x records
    ST = np.full((inside.size, rr.size), -np.inf, dtype=np.float32)
    for k in range(inside.size):
        mine = inv[chunk_local == k]
        if mine.size:
            ST[k] = TS[mine].max(axis=0)
    for k, c in enumerate(inside):
        for r in rows_of[c]:
            j = col_of[int(r)]
            place_desc[int(c), int(r)] = int(1 + (S[:, j] > S[k, j]).sum())
            if np.isfinite(ST[k, j]):
                place_tags[int(c), int(r)] = int(1 + (ST[:, j] > ST[k, j]).sum())
    if (b + 1) % 10 == 0:
        print(f"  ... {b + 1} branches read", flush=True)


def middle_of(pairs):
    return float(np.median(pairs)) if len(pairs) else np.nan


chunk_self_desc = np.array([middle_of([place_desc[i, int(r)] for r in rows_of[i] if (i, int(r)) in place_desc])
                            for i in range(n)])
chunk_self_tags = np.array([middle_of([place_tags[i, int(r)] for r in rows_of[i] if (i, int(r)) in place_tags])
                            for i in range(n)])


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
    """The value less the middle, over the spread (1.4826 times the middle distance from the middle)."""
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))     # kind -> group -> measure -> values
floated_in, gold_in = defaultdict(list), defaultdict(list)
recalls = []
done = 0
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    description, tags, asked = side_of(q)
    got, _, _ = V._tag_cosines(description, tags, p)
    rows, d_description = list(got["tags"]), np.asarray(got["description"], dtype=np.float64)
    if asked:
        rows += list(V._tag_cosines(description, asked, p)[0]["tags"])
    rows = np.array(rows, dtype=np.float64)
    d_question = np.asarray(V._query_cosines(q.question, [], p)[0]["query_description_cosines"], dtype=np.float64)
    on_edge = rows[:, et]
    t_near, t_edge = WK.best_edges(on_edge.max(axis=0), ec, n)
    t_near = np.where(t_edge >= 0, t_near, t_near[t_edge >= 0].min())
    signal = {"tags": t_near, "description": d_description, "question": d_question}
    gold = np.array([bool(record_sets[i] & cites) for i in range(n)])
    main = Counter(branch_of[np.flatnonzero(gold)].tolist()).most_common(1)[0][0]
    inside = np.flatnonzero(branch_of == main)
    x = {r: signal[r][inside] for r in ROUTES}
    place = {r: rankdata(-x[r], method="average") for r in ROUTES}
    base = sum(standing(x[r]) for r in ROUTES)
    place_sum = rankdata(-base, method="average")
    order = inside[np.lexsort((id_rank[inside], -base))]
    kept = kept_of(order)
    floated = set(order[:kept].tolist())
    floated_gold = {c for c in floated if gold[c]}
    got_records = set().union(*(record_sets[i] for i in floated)) if floated else set()
    recalls.append(len(cites & got_records) / len(cites))
    floated_in[main].append(floated)
    gold_in[main].append(set(np.flatnonzero(gold).tolist()))
    # the records' own nearness to the question: the share of the branch's records that are nearer
    rr = branch_rows[main]
    near = M[rr] @ np.asarray(asked_vectors["matrix"][question_at[qid]], dtype=np.float32)
    nearer = dict(zip(rr.tolist(), ((rankdata(-near, method="min") - 1) / rr.size).tolist()))
    cited_rows = {row_of[c] for c in cites if c in row_of}
    for k, c in enumerate(inside.tolist()):
        if gold[c]:
            group = GROUPS[0] if c in floated else GROUPS[1]
        elif c in floated:
            group = GROUPS[2]
        else:
            continue
        mine = [int(r) for r in rows_of[c]]
        values = {
            "place_sum": place_sum[k], "place_tags": place["tags"][k],
            "place_description": place["description"][k], "place_question": place["question"][k],
            "records": len(records[c]), "chars": length[c], "desc_chars": d_chars[c], "tags": layer["n_c"][c],
            "tag_carried": tag_carried[c], "tag_own": tag_own[c],
            "self_desc": chunk_self_desc[c], "self_tags": chunk_self_tags[c],
            "near_any": min((nearer[r] for r in mine), default=np.nan),
            "next_floated": float(bool((next_to[c] & floated) - {c})),
        }
        if gold[c]:
            cited = [r for r in mine if r in cited_rows]
            others = [r for r in mine if r not in cited_rows]
            values.update({
                "cited_share": len(record_sets[c] & cites) / max(len(records[c]), 1),
                "cited_self_desc": middle_of([place_desc[c, r] for r in cited if (c, r) in place_desc]),
                "cited_self_tags": middle_of([place_tags[c, r] for r in cited if (c, r) in place_tags]),
                "other_self_desc": middle_of([place_desc[c, r] for r in others if (c, r) in place_desc]),
                "near_cited": min((nearer[r] for r in cited), default=np.nan),
                "next_floated_gold": float(bool((next_to[c] & floated_gold) - {c})),
            })
            if c not in floated:
                values["below_cut"] = place_sum[k] - kept
        for where in (kind_names[kind_of[c]], "all kinds"):
            for name, value in values.items():
                if not (isinstance(value, float) and np.isnan(value)):
                    data[where][group][name].append(float(value))
            data[where][group]["n"].append(1.0)
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)


def spread_of(values, digits):
    if not values:
        return "-"
    q1, mid, q3 = np.percentile(np.asarray(values, dtype=np.float64), [25, 50, 75])
    return f"{mid:.{digits}f} ({q1:.{digits}f}-{q3:.{digits}f})"


def share_of(values, digits):
    return f"{float(np.mean(values)):.2f}" if values else "-"


ROWS = (
    ("place in the branch by the three routes' sum", "place_sum", 0, spread_of),
    ("places below the cut in that sum", "below_cut", 0, spread_of),
    ("place by the tags alone", "place_tags", 0, spread_of),
    ("place by the description against the query description", "place_description", 0, spread_of),
    ("place by the description against the question", "place_question", 0, spread_of),
    ("records in the chunk", "records", 0, spread_of),
    ("share of its records that are cited", "cited_share", 2, spread_of),
    ("characters of the chunk", "chars", 0, spread_of),
    ("characters of its description", "desc_chars", 0, spread_of),
    ("tags on the chunk", "tags", 0, spread_of),
    ("chunks of the branch that carry one of its tags, middle over its tags", "tag_carried", 1, spread_of),
    ("share of its tags no other chunk of the branch carries", "tag_own", 2, spread_of),
    ("a record of it against the branch's descriptions: place of its own chunk, middle over its records",
     "self_desc", 0, spread_of),
    ("a CITED record of it against the branch's descriptions: place of its own chunk", "cited_self_desc", 0, spread_of),
    ("its records that are not cited, the same", "other_self_desc", 0, spread_of),
    ("a record of it against the branch's tags: place of its own chunk, middle over its records",
     "self_tags", 0, spread_of),
    ("a CITED record of it against the branch's tags: place of its own chunk", "cited_self_tags", 0, spread_of),
    ("its nearest record to the question: share of the branch's records that are nearer", "near_any", 3, spread_of),
    ("its nearest CITED record to the question: share of the branch's records that are nearer", "near_cited", 3,
     spread_of),
    ("next to a floated chunk in its file (share of the chunks)", "next_floated", 2, share_of),
    ("next to a floated gold chunk in its file (share of the chunks)", "next_floated_gold", 2, share_of),
)
m = len(wanted)
print(f"\n{SET}: {m} questions, inside the gold's branch; the three routes' standings added, cut at {BUDGET} characters; "
      f"context_recall_id {float(np.mean(recalls)):.3f}")
print("each cell: the middle (a quarter - three quarters) over the chunk and question pairs of the group")
order_of_kinds = ["all kinds"] + sorted((k for k in data if k != "all kinds"),
                                        key=lambda k: -len(data[k][GROUPS[0]]["n"]) - len(data[k][GROUPS[1]]["n"]))
for kind in order_of_kinds:
    counts = [len(data[kind][g]["n"]) for g in GROUPS]
    if not (counts[0] + counts[1]):
        continue
    print(f"\n== {kind}: {GROUPS[0]} {counts[0]} | {GROUPS[1]} {counts[1]} | {GROUPS[2]} {counts[2]} ==")
    for label, key, digits, show in ROWS:
        cells = [show(data[kind][g][key], digits) for g in GROUPS]
        if any(c != "-" for c in cells):
            print(f"  {label}: " + " | ".join(cells))

print("\n== every chunk of the pool by kind, no question and no gold: chunks | records in the chunk | characters | "
      "characters of its description | tags | a record of it against the branch's descriptions: place of its own "
      "chunk | the same against the branch's tags ==")
for kind_index, kind in enumerate(kind_names):
    which = np.flatnonzero(kind_of == kind_index)
    if not which.size:
        continue
    print(f"  {kind}: {which.size} | {spread_of([len(records[c]) for c in which], 0)} | "
          f"{spread_of(length[which].tolist(), 0)} | {spread_of(d_chars[which].tolist(), 0)} | "
          f"{spread_of(layer['n_c'][which].tolist(), 0)} | "
          f"{spread_of(chunk_self_desc[which][~np.isnan(chunk_self_desc[which])].tolist(), 0)} | "
          f"{spread_of(chunk_self_tags[which][~np.isnan(chunk_self_tags[which])].tolist(), 0)}")

print("\n== floated for how many of its branch's questions (branches with two or more questions among the hundred) ==")
slots, every, by_share, every_kinds, never_gold, always_gold = 0, 0, Counter(), Counter(), 0, 0
branches_counted = 0
for b, sets in floated_in.items():
    if len(sets) < 2:
        continue
    branches_counted += 1
    seen = Counter(c for s in sets for c in s)
    for c, times in seen.items():
        slots += times
        by_share[f"{times} of {len(sets)}"] += 1
        if times == len(sets):
            every += 1
            every_kinds[kind_names[kind_of[c]]] += 1
            is_gold = [c in g for g in gold_in[b]]
            never_gold += int(not any(is_gold))
            always_gold += int(all(is_gold))
print(f"  branches with two or more questions: {branches_counted}; floated places in them: {slots}")
print("  distinct floated chunks by 'floated for k of the branch's n questions': "
      + ", ".join(f"{name}: {count}" for name, count in sorted(by_share.items())))
print(f"  floated for every question of their branch: {every} chunks ("
      + ", ".join(f"{name} {count}" for name, count in every_kinds.most_common()) + f"); gold for none of those "
      f"questions {never_gold}, gold for every one {always_gold}")
print("done", flush=True)

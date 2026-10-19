"""How much of a chunk its description and its tags speak for, over the whole pool, no question and
no gold read.

  - PR batches: the pull request numbers of the chunk's records (from each record's link) against
    the numbers its description names.
  - Every kind with more than one record in a chunk: each record's own text set against the
    branch's chunk descriptions, and against the branch's chunks through their tags (all behind
    "passage: ", the 2026-10-07 side vectors): the place of the record's own chunk, for the
    chunk's best-led record and for its worst-led record.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/what_a_description_covers.py
"""
import json
import os
import re
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
os.environ["HERB_V4_SCOPE_STEP"] = "both"

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _load_verified_doc  # noqa: E402

KEPT = REPO / "output/embed_local/20261007_rev113abe4acafa_float32"
PULL = re.compile(r"/pull/(\d+)")
NUMBER = re.compile(r"\d+")


def unit_rows(m):
    m = np.asarray(m, dtype=np.float32)
    return m / np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-12)


def spread_of(values):
    if not len(values):
        return "-"
    q1, mid, q3 = np.percentile(np.asarray(values, dtype=np.float64), [25, 50, 75])
    return f"{mid:.0f} ({q1:.0f}-{q3:.0f})"


p = V.prepare_over_corpus("what a description covers")
layer, n = p.layer, len(p.chunk_ids)
kind_names, kind_of = layer["kind_names"], layer["kind"]
et, ec = layer["edge_tag"], layer["edge_chunk"]
texts = {}
for line in (KEPT / "descriptions.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        row = json.loads(line)
        texts[str(row["id"])] = row["text"]

docs, record_ids, record_rows = {}, [], []
for row in p.chunk_rows:
    loc = json.loads(row["locator"])
    arr = _load_verified_doc(row["relpath"], row["sha256"], docs)[loc["section"]]
    recs = [arr[k] for k in (loc["indices"] if "indices" in loc else [loc["index"]])]
    record_rows.append(recs)
    record_ids.append(list(dict.fromkeys(str(r["id"]) for r in recs if r.get("id") is not None)))

# PR batches: the pull requests in the chunk against the ones its description names
pr = kind_names.index("pr_batch")
named_of, shape = [], Counter()
for i in np.flatnonzero(kind_of == pr):
    numbers = []
    for r in record_rows[i]:
        found = PULL.search(str(r.get("link") or ""))
        if found:
            numbers.append(found.group(1))
    said = set(NUMBER.findall(texts.get(str(p.chunk_ids[i]), "")))
    named = sum(1 for x in numbers if x in said)
    shape[len(numbers), named] += 1
    if numbers:
        named_of.append(named / len(numbers))
print(f"\n== PR batches: {int((kind_of == pr).sum())} chunks; pull requests in the chunk and how many of them its "
      f"description names by number ==")
for (held, named), count in sorted(shape.items()):
    print(f"  {held} pull requests in the chunk, {named} named in the description: {count} chunks")
print(f"  share of a chunk's pull requests its description names, mean over the chunks: {float(np.mean(named_of)):.2f}")

# every kind: a record's own text against the branch's descriptions and tags, best-led and worst-led record
corpus = np.load(KEPT / "corpus_passage.npz", allow_pickle=True)
row_of = {str(r): k for k, r in enumerate(corpus["ids"])}
M = np.asarray(corpus["matrix"], dtype=np.float32)
passage = np.load(KEPT / "descriptions_passage.npz", allow_pickle=True)
at = {str(c): k for k, c in enumerate(passage["ids"])}
DP = unit_rows(passage["matrix"][[at[str(c)] for c in p.chunk_ids]])
tag_passage = np.load(KEPT / "tags_passage.npz", allow_pickle=True)
tag_at = {str(t): k for k, t in enumerate(tag_passage["ids"])}
TP = unit_rows(tag_passage["matrix"])
tag_row = np.array([tag_at.get(str(t), -1) for t in p.graph_tags], dtype=np.int64)
rows_of = [np.array([row_of[r] for r in recs if r in row_of], dtype=np.int64) for recs in record_ids]
best_d, worst_d, best_t, worst_t = (np.full(n, np.nan) for _ in range(4))
for b, (_, chunks) in enumerate(V.tree_level(p.tree, "product")):
    inside = np.asarray(chunks, dtype=np.int64)
    local = {int(c): k for k, c in enumerate(inside)}
    rr = np.unique(np.concatenate([rows_of[c] for c in inside]))
    col_of = {int(r): j for j, r in enumerate(rr)}
    R = M[rr]
    S = DP[inside] @ R.T
    sel = np.flatnonzero(np.isin(ec, inside) & (tag_row[et] >= 0))
    tags_here, inv = np.unique(et[sel], return_inverse=True)
    TS = TP[tag_row[tags_here]] @ R.T
    chunk_local = np.array([local[int(c)] for c in ec[sel]], dtype=np.int64)
    ST = np.full((inside.size, rr.size), -np.inf, dtype=np.float32)
    for k in range(inside.size):
        mine = inv[chunk_local == k]
        if mine.size:
            ST[k] = TS[mine].max(axis=0)
    for k, c in enumerate(inside):
        cols = [col_of[int(r)] for r in rows_of[c]]
        if not cols:
            continue
        by_d = [int(1 + (S[:, j] > S[k, j]).sum()) for j in cols]
        best_d[c], worst_d[c] = min(by_d), max(by_d)
        if np.isfinite(ST[k]).all():
            by_t = [int(1 + (ST[:, j] > ST[k, j]).sum()) for j in cols]
            best_t[c], worst_t[c] = min(by_t), max(by_t)
print("\n== chunks with more than one record, by kind: chunks | records in the chunk | a record's own text against "
      "the branch's descriptions, place of its own chunk: its best-led record | its worst-led record | the same "
      "through the branch's tags: best-led | worst-led ==")
for index, kind in enumerate(kind_names):
    which = np.array([c for c in np.flatnonzero(kind_of == index) if len(record_ids[c]) > 1], dtype=np.int64)
    if not which.size:
        continue
    print(f"  {kind}: {which.size} | {spread_of([len(record_ids[c]) for c in which])} | "
          f"{spread_of(best_d[which][~np.isnan(best_d[which])])} | {spread_of(worst_d[which][~np.isnan(worst_d[which])])} | "
          f"{spread_of(best_t[which][~np.isnan(best_t[which])])} | {spread_of(worst_t[which][~np.isnan(worst_t[which])])}")
print("done", flush=True)

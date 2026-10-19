"""Does a chunk's description (and do its tags) speak for all of its records or for the records at
one end of it. Over the whole pool, chunks with more than one record, no question read: each
record's own text set against the branch's chunk descriptions, and against the branch's chunks
through their tags (all behind "passage: ", the 2026-10-07 side vectors); the place of the
record's own chunk, by where the record stands in the chunk (first, in between, last).

One count uses the gold ids of the hundred and prints a number only: in the gold PR batches, how
often the cited pull request is the chunk's last record.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/position_in_the_chunk.py
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
os.environ["HERB_V4_SCOPE_STEP"] = "both"

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _load_verified_doc  # noqa: E402
from harness import questions as HQ  # noqa: E402

KEPT = REPO / "output/embed_local/20261007_rev113abe4acafa_float32"


def unit_rows(m):
    m = np.asarray(m, dtype=np.float32)
    return m / np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-12)


def spread_of(values):
    if not len(values):
        return "-"
    q1, mid, q3 = np.percentile(np.asarray(values, dtype=np.float64), [25, 50, 75])
    return f"{mid:.0f} ({q1:.0f}-{q3:.0f})"


p = V.prepare_over_corpus("position in the chunk")
layer, n = p.layer, len(p.chunk_ids)
kind_names, kind_of = layer["kind_names"], layer["kind"]
et, ec = layer["edge_tag"], layer["edge_chunk"]
docs, record_ids = {}, []
for row in p.chunk_rows:
    loc = json.loads(row["locator"])
    arr = _load_verified_doc(row["relpath"], row["sha256"], docs)[loc["section"]]
    recs = [arr[k] for k in (loc["indices"] if "indices" in loc else [loc["index"]])]
    record_ids.append(list(dict.fromkeys(str(r["id"]) for r in recs if r.get("id") is not None)))

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

by_d = {k: {"first": [], "between": [], "last": []} for k in kind_names}
by_t = {k: {"first": [], "between": [], "last": []} for k in kind_names}
best_is = {k: Counter() for k in kind_names}
for b, (_, chunks) in enumerate(V.tree_level(p.tree, "product")):
    inside = np.asarray(chunks, dtype=np.int64)
    local = {int(c): k for k, c in enumerate(inside)}
    held = [[row_of[r] for r in record_ids[c] if r in row_of] for c in inside]
    rr = np.unique(np.array([r for rows in held for r in rows], dtype=np.int64))
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
        rows = held[k]
        if len(rows) < 2:
            continue
        kind = kind_names[kind_of[c]]
        cols = [col_of[int(r)] for r in rows]
        d = [int(1 + (S[:, j] > S[k, j]).sum()) for j in cols]
        t = [int(1 + (ST[:, j] > ST[k, j]).sum()) for j in cols] if np.isfinite(ST[k]).all() else None
        for places, into in ((d, by_d), (t, by_t)):
            if places is None:
                continue
            into[kind]["first"].append(places[0])
            into[kind]["last"].append(places[-1])
            into[kind]["between"].extend(places[1:-1])
        low = min(d)
        at_low = [i for i, x in enumerate(d) if x == low]
        best_is[kind]["several records share the best place" if len(at_low) > 1 else
                      "the first record" if at_low[0] == 0 else
                      "the last record" if at_low[0] == len(d) - 1 else "a record in between"] += 1

print("\n== chunks with more than one record; a record's own text against the branch's descriptions: the place of "
      "its own chunk, for the chunk's first record | its records in between | its last record ==")
for kind in kind_names:
    if by_d[kind]["first"]:
        print(f"  {kind} ({len(by_d[kind]['first'])} chunks): {spread_of(by_d[kind]['first'])} | "
              f"{spread_of(by_d[kind]['between'])} | {spread_of(by_d[kind]['last'])}")
print("\n== the same through the branch's tags ==")
for kind in kind_names:
    if by_t[kind]["first"]:
        print(f"  {kind} ({len(by_t[kind]['first'])} chunks): {spread_of(by_t[kind]['first'])} | "
              f"{spread_of(by_t[kind]['between'])} | {spread_of(by_t[kind]['last'])}")
print("\n== which record of the chunk its description leads back from best ==")
for kind in kind_names:
    if best_is[kind]:
        print(f"  {kind}: " + ", ".join(f"{name} {count}" for name, count in best_is[kind].most_common()))

# the one count with gold in it: in the gold PR batches of the hundred, is the cited pull request the last record
wanted = [json.loads(line)["id"] for line in (REPO / "data/gold100.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
pr, slack = kind_names.index("pr_batch"), kind_names.index("slack_thread_batch")
cited_last, cited_other = 0, 0
slack_where = Counter()
for qid in wanted:
    cites = {str(c) for c in by_id[qid].citations}
    for c in range(n):
        ids = record_ids[c]
        if len(ids) < 2 or kind_of[c] not in (pr, slack):
            continue
        for k, rid in enumerate(ids):
            if rid in cites:
                if kind_of[c] == pr:
                    if k == len(ids) - 1:
                        cited_last += 1
                    else:
                        cited_other += 1
                else:
                    slack_where["the last record" if k == len(ids) - 1 else "the first record" if k == 0
                                else "a record in between"] += 1
print(f"\n== the hundred, gold PR batches with more than one pull request: the cited pull request is the chunk's last "
      f"record {cited_last} times, another record {cited_other} times ==")
print("== the hundred, gold Slack batches: a cited record is " + ", ".join(f"{k} {v}" for k, v in slack_where.most_common())
      + " ==")
print("done", flush=True)

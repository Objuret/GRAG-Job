"""Compare run folders of the arm against a base folder: context_recall_id per question (paired), the
first text holds a cited record, a cited record among the first three texts, search time. The gold
ids are read inside; numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/compare_runs.py <base folder> <folder> [<folder> ...]
"""
import json
import os
import sys

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path[:0] = [os.path.join(REPO, "prod"), os.path.join(REPO, "test")]
sys.stdout.reconfigure(encoding="utf-8")
from harness import questions as HQ  # noqa: E402

by_id = {q.id: q for q in HQ.load_questions()}


def read(d):
    scores = {}
    for line in open(os.path.join(d, "eval_results.jsonl"), encoding="utf-8"):
        j = json.loads(line)
        if isinstance(j.get("value"), (int, float)):
            scores.setdefault(j["metric"], {})[j["question_id"]] = float(j["value"])
    first = three = 0
    times = []
    for line in open(os.path.join(d, "arm_outputs.jsonl"), encoding="utf-8"):
        row = json.loads(line)
        qid = row.get("question_id") or row.get("qid") or row.get("id")
        cites = {str(c) for c in by_id[qid].citations}
        meta = row.get("meta") or {}
        got = {str(x) for x in row.get("context_ids") or []}
        whole = [u for u in ([str(x) for x in unit] for unit in meta.get("chunk_ids") or [] if unit) if set(u) <= got]
        first += bool(whole and set(whole[0]) & cites)
        three += any(set(u) & cites for u in whole[:3])
        if isinstance(row.get("search_time_s"), (int, float)):
            times.append(row["search_time_s"])
    return scores, first, three, float(np.median(times)) if times else float("nan")


base = read(sys.argv[1])
for d in sys.argv[1:]:
    scores, first, three, t = read(d)
    said = []
    for metric in sorted(scores):
        q = sorted(set(scores[metric]) & set(base[0].get(metric, {})))
        if not q:
            continue
        a = np.array([scores[metric][k] for k in q])
        b = np.array([base[0][metric][k] for k in q])
        diff = a - b
        said.append(f"{metric} {a.mean():.3f} ({diff.mean():+.3f}, se {diff.std(ddof=1) / np.sqrt(len(q)) if len(q) > 1 else 0:.3f}, "
                    f"{int((diff > 1e-9).sum())} up {int((diff < -1e-9).sum())} down, n {len(q)})")
    print(f"{os.path.basename(d)}: first text {first} | among three {three} | search time {t:.2f}s\n    " + "\n    ".join(said))

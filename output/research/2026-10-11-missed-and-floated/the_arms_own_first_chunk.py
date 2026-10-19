"""His 2026-10-11 "Even after all sorting and scope and the whole fucking shit..?", on the first chunk
being gold on 48 of 100 in the agent's stand-in order (the three routes' standings added). Here
the arm's OWN runs on the hundred are read from their folders: for each run, the chunks it
delivered in its own order (`meta.chunk_ids` of `arm_outputs.jsonl`: per delivered chunk the ids
of its records), and whether the first one, and any of the first three, is a gold chunk (holds a
cited record). No model call, no retrieval, no graph read.

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/the_arms_own_first_chunk.py
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")

from harness import questions as HQ  # noqa: E402

RUNS = REPO / "output" / "k=chars"
by_id = {q.id: q for q in HQ.load_questions()}

print("== the arm's runs on the hundred: context_recall_id (share of the cited records delivered inside 72,000 "
      "characters, from the run's own scoring) | questions | the first delivered chunk is gold | a gold chunk among "
      "the first three | none of the delivered chunks is gold | chunks delivered, the middle | gold chunks among "
      "them, the middle ==")
for folder in sorted(RUNS.glob("artefact_v4__gold100__*")):
    outputs = folder / "arm_outputs.jsonl"
    if not outputs.exists():
        continue
    rows = [json.loads(line) for line in outputs.read_text(encoding="utf-8").splitlines() if line.strip()]
    scores = {}
    results = folder / "eval_results.jsonl"
    if results.exists():
        for line in results.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("metric") == "context_recall_id" and r.get("value") is not None:
                    scores[r["question_id"]] = float(r["value"])
    first, three, none, sent, sent_gold = [], [], [], [], []
    for row in rows:
        q = by_id.get(row["id"])
        chunks = [[str(x) for x in c] for c in ((row.get("meta") or {}).get("chunk_ids") or []) if isinstance(c, list)]
        if q is None or not chunks:
            continue
        cites = {str(c) for c in q.citations}
        delivered = set(str(x) for x in row.get("context_ids") or [])
        whole = [c for c in chunks if c and set(c) <= delivered]      # a chunk cut at the budget is not counted
        if not whole:
            continue
        is_gold = [bool(set(c) & cites) for c in whole]
        first.append(float(is_gold[0]))
        three.append(float(any(is_gold[:3])))
        none.append(float(not any(is_gold)))
        sent.append(len(whole))
        sent_gold.append(sum(is_gold))
    recall = f"{float(np.mean(list(scores.values()))):.3f}" if scores else "  -  "
    if not first:
        print(f"  {recall} | no row with chunk lists  {folder.name}")
        continue
    print(f"  {recall} | {len(first)} | {int(sum(first))} | {int(sum(three))} | {int(sum(none))} | {np.median(sent):.0f} | "
          f"{np.median(sent_gold):.0f}  {folder.name}")
print("done", flush=True)

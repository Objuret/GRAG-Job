"""How often a chunk holds a cited record by its step in the clouds (his 2026-10-17 "since we do the clouds and
narrowing before, perhaps we actually do a fuzzy cut at that stage?"). The clouds' order runs step by step, so a
chunk's step is read off its place and the record's count of chunks on each step. From the run folder of the
clouds' order and the citation ids; no question text, no model call.

    .venv/Scripts/python.exe output/research/2026-10-17-4combo-why/cited_by_step.py <run of the clouds' order>
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
from arms.artefact_v2 import _load_verified_doc  # noqa: E402
from graph.db import _driver  # noqa: E402
from harness import questions as HQ  # noqa: E402

dr = _driver()
with dr.session(database="herb-eval-volmax") as s:
    rows = s.run("MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk) WHERE (c)-[:product]->() RETURN c.chunk_id AS id, "
                 "c.locator_json AS loc, f.rel_path AS relpath, f.sha256 AS sha256").data()
dr.close()
docs, records = {}, {}
for r in rows:
    loc = json.loads(r["loc"])
    arr = _load_verified_doc(r["relpath"], r["sha256"], docs)[loc["section"]]
    records[r["id"]] = {str(arr[k]["id"]) for k in (loc["indices"] if "indices" in loc else [loc["index"]])
                        if arr[k].get("id") is not None}
cites = {q.id: {str(c) for c in q.citations} for q in HQ.load_questions()}
by_step, reach, gold_reach = defaultdict(lambda: [0, 0]), defaultdict(list), defaultdict(list)
delivered = []
for line in (Path(sys.argv[1]) / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    r = json.loads(line)
    order = r["meta"]["ranking"]["ordered_chunk_ids"]
    counts = {int(s): n for s, n in r["meta"]["scope"]["combo"]["chunks_on_each_step"].items()}
    steps = [s for s in sorted(counts) for _ in range(counts[s])]
    assert len(steps) == len(order)
    delivered.append(len(r["meta"]["ranking"]["delivered_chunk_ids"]))
    gold = [bool(records[c] & cites[r["id"]]) for c in order]
    for s, g in zip(steps, gold):
        by_step[s][0] += 1
        by_step[s][1] += g
    total_gold = max(1, sum(gold))
    for top in sorted(counts):
        upto = sum(n for s, n in counts.items() if s <= top)
        reach[top].append(upto)
        gold_reach[top].append(sum(gold[:upto]) / total_gold)
print(f"chunks inside the 72,000 a question, middle: {int(np.median(delivered))}")
print("step: chunks, holding a cited record | chunks on this step and before it, a question (middle) | share of a "
      "question's chunks with a cited record that lie on this step or before (middle)")
for s in sorted(by_step):
    n, hit = by_step[s]
    print(f"   {s}: {n}, {hit} ({100 * hit / n:.1f}%) | {np.median(reach[s]):.0f} | {np.median(gold_reach[s]):.2f}")

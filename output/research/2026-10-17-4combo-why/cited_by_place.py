"""How often a chunk holds a cited record by its place in the clouds' order, and by its step (his 2026-10-17
"perhaps "far below the cut" isnt really a good place to pull shit from tho..?"). From the run folder of the
clouds' order and the citation ids; no question text, no model call.

    .venv/Scripts/python.exe output/research/2026-10-17-4combo-why/cited_by_place.py <run of the clouds' order>
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

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
bands = ((1, 15), (16, 30), (31, 60), (61, 120), (121, 10 ** 6))
by_band, delivered = defaultdict(lambda: [0, 0]), []
for line in (Path(sys.argv[1]) / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    r = json.loads(line)
    order = r["meta"]["ranking"]["ordered_chunk_ids"]
    delivered.append(len(r["meta"]["ranking"]["delivered_chunk_ids"]))
    for k, c in enumerate(order, 1):
        band = next(b for b in bands if b[0] <= k <= b[1])
        by_band[band][0] += 1
        by_band[band][1] += bool(records[c] & cites[r["id"]])
print(f"chunks delivered inside the 72,000 a question, middle: {sorted(delivered)[len(delivered) // 2]}")
print("place in the clouds' order: chunks, holding a cited record")
for b in bands:
    n, hit = by_band[b]
    print(f"   {b[0]}-{b[1] if b[1] < 10 ** 6 else 'end'}: {n}, {hit} ({100 * hit / n:.1f}%)")

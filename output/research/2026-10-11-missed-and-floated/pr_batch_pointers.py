"""The PR batches' pointers: what a PR batch's locator holds, how many pull requests and characters
a batch has, and whether every pull request record of the dataset is under some batch's pointer.
From the graph and the dataset files; no question and no gold read.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/pr_batch_pointers.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _load_verified_doc, _resolve_chunk  # noqa: E402
from graph.db import _driver  # noqa: E402

CYPHER = """
MATCH (c:Chunk {kind: 'pr_batch'}) WHERE c.desc_emb IS NOT NULL AND (c)-[:product]->()
MATCH (f:File)-[:HAS_CHUNK]->(c)
RETURN c.chunk_id AS chunk, c.locator_json AS locator, f.rel_path AS relpath, f.sha256 AS sha256,
       c.parent_ref AS parent, c.ordinal AS ordinal ORDER BY chunk
"""
driver = _driver()
with driver.session(database=V.DATABASE) as session:
    rows = session.execute_read(lambda tx: [dict(r) for r in tx.run(CYPHER)])
    labels = session.execute_read(lambda tx: [r["l"] for r in tx.run(
        "MATCH (n) UNWIND labels(n) AS l RETURN DISTINCT l ORDER BY l")])
driver.close()
docs, held, chars, covered, in_files = {}, Counter(), [], {}, {}
keys = Counter()
for row in rows:
    loc = json.loads(row["locator"])
    keys[tuple(sorted(loc))] += 1
    arr = _load_verified_doc(row["relpath"], row["sha256"], docs)[loc["section"]]
    indices = loc["indices"] if "indices" in loc else [loc["index"]]
    held[len(indices)] += 1
    text, _ = _resolve_chunk(row, docs)
    chars.append(len(text))
    covered.setdefault((row["relpath"], loc["section"]), set()).update(indices)
    in_files[row["relpath"], loc["section"]] = len(arr)
chars.sort()
print(f"PR batches: {len(rows)}; node labels in the graph: {', '.join(labels)}")
print("what a PR batch's locator holds (its keys): " + "; ".join(f"{', '.join(k)} ({v} chunks)" for k, v in keys.items()))
sample = json.loads(rows[0]["locator"])
print(f"one PR batch's locator as stored: {json.dumps(sample)}  (parent {rows[0]['parent']}, ordinal {rows[0]['ordinal']})")
print("pull requests in a batch: " + ", ".join(f"{k}: {held[k]} batches" for k in sorted(held)))
print(f"characters of a batch: smallest {chars[0]}, a quarter under {chars[len(chars) // 4]}, middle "
      f"{chars[len(chars) // 2]}, three quarters under {chars[3 * len(chars) // 4]}, largest {chars[-1]}")
total = sum(in_files.values())
under = sum(len(v) for v in covered.values())
print(f"pull request records in the dataset files those batches point into: {total}; under some batch's pointer: {under}")
print("done")

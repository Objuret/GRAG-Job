"""PR batches whose description names exactly one of their pull requests by number: which record of
the chunk is it (first, last, another), and how many tags the chunk has. From the graph and the
description texts; no question and no gold read.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/which_pull_request.py
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _load_verified_doc  # noqa: E402
from graph.db import _driver  # noqa: E402

PULL = re.compile(r"/pull/(\d+)")
NUMBER = re.compile(r"\d+")
CYPHER = """
MATCH (c:Chunk {kind: 'pr_batch'}) WHERE c.desc_emb IS NOT NULL AND (c)-[:product]->()
MATCH (f:File)-[:HAS_CHUNK]->(c)
OPTIONAL MATCH (c)-[r:HAS_TAG]->(t:Tag) WHERE r.run_id = $run AND t.emb IS NOT NULL
RETURN c.chunk_id AS chunk, c.locator_json AS locator, f.rel_path AS relpath, f.sha256 AS sha256,
       count(t) AS tags
"""
texts = {}
for line in (REPO / "output/embed_local/20261007_rev113abe4acafa_float32/descriptions.jsonl").read_text(
        encoding="utf-8").splitlines():
    if line.strip():
        row = json.loads(line)
        texts[str(row["id"])] = row["text"]
driver = _driver()
with driver.session(database=V.DATABASE) as session:
    rows = session.execute_read(lambda tx: [dict(r) for r in tx.run(CYPHER, run=V.RUN_ID)])
driver.close()
docs, where, tags_by_named = {}, Counter(), {}
for row in rows:
    loc = json.loads(row["locator"])
    arr = _load_verified_doc(row["relpath"], row["sha256"], docs)[loc["section"]]
    recs = [arr[k] for k in (loc["indices"] if "indices" in loc else [loc["index"]])]
    numbers = [m.group(1) if (m := PULL.search(str(r.get("link") or ""))) else None for r in recs]
    said = set(NUMBER.findall(texts.get(str(row["chunk"]), "")))
    named = [k for k, x in enumerate(numbers) if x is not None and x in said]
    key = "all" if len(named) == len(recs) else "one" if len(named) == 1 else "none" if not named else "some"
    if len(recs) > 1:
        tags_by_named.setdefault(key, []).append(int(row["tags"]))
        if len(named) == 1:
            where["the first record" if named[0] == 0 else "the last record" if named[0] == len(recs) - 1
                  else "a record in between"] += 1
print(f"PR batches read: {len(rows)}")
print("the one pull request the description names is: " + ", ".join(f"{k} {v}" for k, v in where.most_common()))
for key in ("one", "none", "some", "all"):
    values = sorted(tags_by_named.get(key, []))
    if values:
        print(f"  description names {key} of the chunk's pull requests: {len(values)} chunks; tags on the chunk, "
              f"middle {values[len(values) // 2]}")
print("done")

"""What the tags on a kind of chunk are, read from the graph: per kind the tags carried by the
most chunks of that kind, and two chunks of the kind drawn with a fixed seed from the whole pool
(their tags and their description). No question and no gold is read.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/tags_by_kind.py
"""
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")

from arms import artefact_v4 as V  # noqa: E402
from graph.db import _driver  # noqa: E402

KINDS = ("pr_batch", "slack_thread_batch", "meeting_transcript")
CYPHER = """
MATCH (c:Chunk)-[r:HAS_TAG]->(t:Tag)
WHERE r.run_id = $run AND c.desc_emb IS NOT NULL AND t.emb IS NOT NULL AND (c)-[:product]->()
RETURN c.chunk_id AS chunk, c.kind AS kind, t.name AS tag
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
tags_of, kind_of = defaultdict(list), {}
for row in rows:
    tags_of[row["chunk"]].append(row["tag"])
    kind_of[row["chunk"]] = row["kind"]
for kind in KINDS:
    chunks = sorted(c for c, k in kind_of.items() if k == kind)
    carried = Counter(t for c in chunks for t in set(tags_of[c]))
    once = sum(1 for count in carried.values() if count == 1)
    print(f"\n== {kind}: {len(chunks)} chunks, {len(carried)} different tags on them, {once} of those on one chunk "
          f"of the kind only ==")
    print("  the tags on the most chunks of the kind: "
          + "; ".join(f"{tag} ({count})" for tag, count in carried.most_common(15)))
    for chunk in random.Random(20261011).sample(chunks, 2):
        print(f"  a chunk drawn at random: tags: {'; '.join(sorted(tags_of[chunk]))}")
        print(f"    its description: {texts.get(chunk, '-')}")
print("done")

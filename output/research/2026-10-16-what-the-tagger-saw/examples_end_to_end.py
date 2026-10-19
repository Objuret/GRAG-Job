"""Three real chunks per batch kind, end to end: each post (pointer and the start of its text), what the May
tagger answered for the chunk, and which post each of the graph's tags on the chunk stands in. The chunks are
the first three by chunk id with four posts or more; no question and no gold read. Argument: the unzipped
snapshot folder (git show bcc3156:backend/data/tagging_runs/pilot_full_herb_snapshot_20260514T052226Z.zip).

    .venv/Scripts/python.exe output/research/2026-10-16-what-the-tagger-saw/examples_end_to_end.py <folder>
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
from arms.artefact_v2 import _load_verified_doc  # noqa: E402
from graph.db import _driver, _readable  # noqa: E402

folder = Path(sys.argv[1])
KINDS = ("pr_batch", "slack_thread_batch")
dr = _driver()
with dr.session(database="herb-eval-volmax") as s:
    rows = s.run(
        "MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk) WHERE c.kind IN $k AND (c)-[:product]->() "
        "OPTIONAL MATCH (c)-[:HAS_TAG]->(t:Tag) "
        "RETURN c.chunk_id AS id, c.kind AS kind, c.locator_json AS loc, f.rel_path AS relpath, f.sha256 AS sha256, "
        "collect(DISTINCT t.name) AS tags ORDER BY id", k=list(KINDS)).data()
dr.close()
picked = {k: [] for k in KINDS}
for r in rows:
    loc = json.loads(r["loc"])
    if len(loc.get("indices", [])) >= 4 and len(picked[r["kind"]]) < 3:
        picked[r["kind"]].append(r)
want = {r["id"] for k in KINDS for r in picked[k]}
answers = {}
for line in (folder / "io.jsonl").open(encoding="utf-8"):
    r = json.loads(line)
    if r["stage"] == "extract" and r["target_id"] in want and r.get("response_tool_input"):
        answers[r["target_id"]] = r["response_tool_input"]
docs = {}
for kind in KINDS:
    for r in picked[kind]:
        loc = json.loads(r["loc"])
        arr = _load_verified_doc(r["relpath"], r["sha256"], docs)[loc["section"]]
        recs = [arr[i] for i in loc["indices"]]
        texts = [json.dumps(x, ensure_ascii=False) for x in recs]
        print(f"\n===== {kind} {r['id']}: {len(recs)} posts")
        for k, (x, tx) in enumerate(zip(recs, texts)):
            print(f"  post {k + 1} [{x.get('id')}]: {tx[:220]}")
        a = answers.get(r["id"], {})
        print(f"  MAY TAGGER, description: {a.get('description')}")
        print(f"  MAY TAGGER, tags: {a.get('tags')}")
        print("  GRAPH TAGS, and the posts each stands in (whole words, any case):")
        for t in sorted(r["tags"]):
            pat = re.compile(r"(?<![0-9a-z])" + re.escape(_readable(t).lower()) + r"(?![0-9a-z])")
            inside = [str(k + 1) for k, tx in enumerate(texts) if pat.search(tx.lower())]
            print(f"    {_readable(t)}: posts {', '.join(inside) if inside else 'none (not verbatim)'}")

"""The exact chunks a redo of the tagger would go over, written out as id lists, with their posts and the May run's
tokens for them. Batch chunks from coverage_by_post.npz (run coverage_by_post.py first); the document chunks the May
code cut at a table from the snapshot (argument: the unzipped snapshot folder,
git show bcc3156:backend/data/tagging_runs/pilot_full_herb_snapshot_20260514T052226Z.zip). No question read.

    .venv/Scripts/python.exe output/research/2026-10-16-what-the-tagger-saw/the_chunks_to_redo.py <folder>
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
from arms.artefact_v2 import _load_verified_doc  # noqa: E402
from graph.db import _driver  # noqa: E402

folder = Path(sys.argv[1])
z = np.load(HERE / "coverage_by_post.npz", allow_pickle=True)
kinds, chunk_ids = [str(k) for k in z["kinds"]], [str(c) for c in z["chunk_ids"]]
posts = Counter(kinds[int(c)] for c in z["chunk"])
batch = ("pr_batch", "slack_thread_batch", "url_batch", "meeting_chat_batch")
lists = defaultdict(list)
for c, cid in enumerate(chunk_ids):
    if kinds[c] in batch:
        lists[kinds[c]].append(cid)
usage = defaultdict(lambda: [0, 0, 0])
want = {cid: k for k, ids in lists.items() for cid in ids}
for line in (folder / "io.jsonl").open(encoding="utf-8"):
    r = json.loads(line)
    if r["stage"] == "extract" and r["target_id"] in want:
        u = r.get("usage") or {}
        t = usage[want[r["target_id"]]]
        t[0] += 1
        t[1] += u.get("prompt_tokens", 0)
        t[2] += u.get("completion_tokens", 0)
print("== batch chunks of the pool, one id list a kind ==")
for k in batch:
    (HERE / f"redo_{k}.txt").write_text("\n".join(sorted(lists[k])) + "\n", encoding="utf-8")
    c, i, o = usage[k]
    print(f"   {k}: {len(lists[k])} chunks, {posts[k]} posts -> redo_{k}.txt; the May describe-and-tag calls on them: "
          f"{c} calls, {i} tokens in, {o} tokens out")

dr = _driver()
with dr.session(database="herb-eval-volmax") as s:
    rows = {r["id"]: r for r in s.run(
        "MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk) WHERE c.kind IN ['document','document_part'] AND (c)-[:product]->() "
        "RETURN c.chunk_id AS id, c.locator_json AS loc, f.rel_path AS relpath, f.sha256 AS sha256").data()}
dr.close()
docs, cut = {}, []
for line in (folder / "io.jsonl").open(encoding="utf-8"):
    r = json.loads(line)
    if r["stage"] != "extract" or r["target_id"] not in rows:
        continue
    row = rows[r["target_id"]]
    loc = json.loads(row["loc"])
    rec = _load_verified_doc(row["relpath"], row["sha256"], docs)[loc["section"]][loc["index"]]
    text = rec[loc.get("field") or "content"]
    if "char_range" in loc:
        a, b = loc["char_range"]
        text = text[a:b]
    sent = r["request"]["user"].split("\n---\n")[1]
    if sent.endswith("\n---"):
        sent = sent[:-4]
    if "---" in text and len(sent.strip()) < len(text.strip()):
        cut.append((r["target_id"], len(sent.strip()), len(text.strip())))
(HERE / "redo_documents_cut_at_a_table.txt").write_text("\n".join(sorted(c for c, _, _ in cut)) + "\n", encoding="utf-8")
print(f"\n== document chunks the May code cut at a table line: {len(cut)} -> redo_documents_cut_at_a_table.txt ==")
for cid, a, b in sorted(cut):
    print(f"   {cid}: {a} of {b} characters sent")

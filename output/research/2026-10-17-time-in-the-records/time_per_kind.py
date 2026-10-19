"""Can every pool chunk's posts be given a time read from the records (his 2026-10-17 "so, is reading
datetime an issue for this?")? Per kind of chunk: which field holds the time, how many posts carry one
that parses, the years they fall in, and how many chunks have no post with a time. No question read, no
model call, nothing written.

    .venv/Scripts/python.exe output/research/2026-10-17-time-in-the-records/time_per_kind.py
"""
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")

from arms.artefact_v2 import _load_verified_doc  # noqa: E402
from graph.db import _driver  # noqa: E402

STAMP = re.compile(r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?")


def parsed(value):
    if not isinstance(value, str):
        return None
    found = STAMP.search(value)
    if not found:
        return None
    try:
        return datetime.fromisoformat(found.group(0).replace(" ", "T"))
    except ValueError:
        return None


def time_of(kind, record):
    """(field, time) for one record, the field the record's own kind keeps its time in."""
    if kind == "slack_thread_batch":
        return "Message.User.timestamp", parsed(((record.get("Message") or {}).get("User") or {}).get("timestamp"))
    if kind == "pr_batch":
        return "created_at", parsed(record.get("created_at"))
    if kind in ("document", "document_part", "meeting_transcript", "meeting_transcript_part"):
        return "date", parsed(record.get("date"))
    if kind == "meeting_chat_batch":
        return "text (its first line)", parsed((record.get("text") or "").split("\n", 1)[0])
    return "none of its fields", None


dr = _driver()
with dr.session(database="herb-eval-volmax") as s:
    rows = s.run("MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk) WHERE (c)-[:product]->() "
                 "RETURN c.chunk_id AS id, c.kind AS kind, c.locator_json AS loc, "
                 "f.rel_path AS relpath, f.sha256 AS sha256").data()
dr.close()
docs = {}
posts, timed, chunks, chunks_timed = Counter(), Counter(), Counter(), Counter()
field, years, keys = {}, defaultdict(Counter), {}
for r in rows:
    loc = json.loads(r["loc"])
    arr = _load_verified_doc(r["relpath"], r["sha256"], docs)[loc["section"]]
    recs = [arr[i] for i in (loc["indices"] if "indices" in loc else [loc["index"]])]
    kind = r["kind"]
    chunks[kind] += 1
    keys.setdefault(kind, sorted(recs[0].keys()) if isinstance(recs[0], dict) else [])
    any_time = False
    for rec in recs:
        name, when = time_of(kind, rec)
        field[kind] = name
        posts[kind] += 1
        if when is not None:
            timed[kind] += 1
            years[kind][when.year] += 1
            any_time = True
    chunks_timed[kind] += any_time
for kind in sorted(posts):
    print(f"{kind}: time from {field[kind]}; posts {posts[kind]}, with a time {timed[kind]}; chunks {chunks[kind]}, "
          f"with no post that has a time {chunks[kind] - chunks_timed[kind]}; years "
          + (", ".join(f"{y}: {n}" for y, n in sorted(years[kind].items())) or "-"))
    if not timed[kind]:
        print(f"   its records' fields: {keys[kind]}")

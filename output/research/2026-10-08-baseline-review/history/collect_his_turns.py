"""Collect every typed turn of his from all sources into one file, oldest first.

Sources: docs/canon/raw/user_turns_all.jsonl, docs/canon/raw/user_turns.jsonl, and every session
transcript under ~/.claude/projects/C--Coding-exjobbet-GRAG-Job (read with tools/last_turns.read_turns,
which uses canon_extract's human-turn filter). Duplicates (same second, same text) collapse.

Writes his_turns_all_sources.jsonl next to this script. Prints counts only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(r"C:\Coding\exjobbet\GRAG-Job")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "tools"))
import last_turns as lt  # noqa: E402

PROJECT = Path.home() / ".claude" / "projects" / "C--Coding-exjobbet-GRAG-Job"

rows: dict[tuple[str, str], dict] = {}


def add(ts: str, text: str, source: str, session: str) -> None:
    key = ((ts or "")[:19], text.strip())
    if key in rows:
        rows[key]["sources"].append(source)
        return
    rows[key] = {"ts": ts, "text": text.strip(), "session": session, "sources": [source]}


for name in ("user_turns_all.jsonl", "user_turns.jsonl"):
    path = REPO / "docs" / "canon" / "raw" / name
    n = 0
    for line in path.open(encoding="utf-8"):
        r = json.loads(line)
        add(r["iso_timestamp"], r["text"], name, r.get("session_id", ""))
        n += 1
    print(f"{name}: {n} turns")

n_files = 0
n_turns = 0
for path in sorted(PROJECT.glob("*.jsonl")):
    try:
        turns = lt.read_turns(path)
    except Exception as exc:  # a transcript that does not parse is reported, not hidden
        print(f"FAILED {path.name}: {exc!r}")
        continue
    n_files += 1
    for t in turns:
        if t["who"] == "he" and t["text"].strip():
            add(t["ts"] or "", t["text"], "transcript", path.stem)
            n_turns += 1
print(f"transcripts: {n_files} files, {n_turns} typed turns")

out = sorted(rows.values(), key=lambda r: r["ts"] or "")
with (HERE / "his_turns_all_sources.jsonl").open("w", encoding="utf-8") as fh:
    for r in out:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"unique turns: {len(out)}; first {out[0]['ts']}; last {out[-1]['ts']}")
only_transcript = [r for r in out if r["sources"] == ["transcript"] or set(r["sources"]) == {"transcript"}]
print(f"turns only in transcripts (not in canon): {len(only_transcript)}")
if only_transcript:
    print(f"  first {only_transcript[0]['ts']}, last {only_transcript[-1]['ts']}")

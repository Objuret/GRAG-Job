"""The lane's own transcript counts of every model call of a run (the answer call and the arm's own
calls, such as its first call), for tools/correct_zero_usage.py:
{session_id: {input_tokens, cache_creation_input_tokens, cache_read_input_tokens, output_tokens}},
the usage of every assistant message of the session summed, one message (by its id) counted once.

    python tools/cli_transcript_counts.py <run folder> <out json> [<other json> ...]

It runs on the machine that made the calls: the lane's transcripts are under its own config folder
(~/.claude-herb-lane/projects). A run whose answers two machines made is counted on each; the
counts of the other machine, given as <other json>, are joined in, each session counted on one
machine only. Nothing is sent to a model; nothing of the run is written.
"""
import json
import sys
from pathlib import Path

KEYS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")


def main():
    run, out, others = Path(sys.argv[1]), Path(sys.argv[2]), [Path(p) for p in sys.argv[3:]]
    root = Path.home() / ".claude-herb-lane" / "projects"
    by_name = {}
    for f in root.rglob("*.jsonl"):
        by_name.setdefault(f.stem, []).append(f)
    counts, missing, several = {}, [], []
    sessions = []
    for line in (run / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        sessions += [(row["id"], c["envelope"]["session_id"]) for c in row["calls"]
                     if c.get("kind") == "chat" and c.get("ok") and (c.get("envelope") or {}).get("session_id")]
    for qid, sid in sessions:
        files = by_name.get(sid, [])
        if not files:
            missing.append(qid)
            continue
        if len(files) > 1:
            several.append(qid)
        msgs = {}
        for t in files:
            for x in t.read_text(encoding="utf-8").splitlines():
                if not x.strip():
                    continue
                ev = json.loads(x)
                m = ev.get("message") or {}
                if ev.get("type") == "assistant" and m.get("usage"):
                    msgs[m.get("id") or ev.get("uuid")] = m["usage"]
        counts[sid] = {k: sum(int(u.get(k) or 0) for u in msgs.values()) for k in KEYS}
    here = len(counts)
    for other in others:
        theirs = json.loads(other.read_text(encoding="utf-8"))
        both = set(theirs) & set(counts)
        if both:
            raise SystemExit(f"{other}: {len(both)} sessions counted on both machines; nothing written")
        counts.update(theirs)
    out.write_text(json.dumps(counts, indent=1), encoding="utf-8")
    print(f"model calls {len(sessions)}; sessions counted here {here}; no transcript here {len(missing)}; "
          f"more than one transcript file {len(several)}; sessions in the file {len(counts)}")


if __name__ == "__main__":
    main()

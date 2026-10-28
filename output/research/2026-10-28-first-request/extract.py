"""The numbers of each model request in the Claude Code lane's own transcripts, for the session ids
in sessions.json beside this file: the time of the prompt record; for each model request (one
assistant message id) the times of its first and last record, its usage and the kinds of its blocks;
for each tool result its time and whether it is an error. No text is read out: the transcripts hold
test questions. Standard library only; no model call.

    python extract.py <out name>      (default first_request_<machine>.json)
"""
import hashlib
import json
import platform
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
LANE = Path.home() / ".claude-herb-lane" / "projects"
USAGE = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")


def when(stamp):
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def find(sid):
    hits = sorted(LANE.glob(f"*/{sid}.jsonl"))
    return hits[0] if hits else None


def numbers(path):
    prompt, order, requests, results = None, [], {}, []
    for line in path.open(encoding="utf-8"):
        if not line.strip():
            continue
        rec = json.loads(line)
        msg = rec.get("message") or {}
        if rec.get("type") == "assistant" and msg.get("id"):
            mid = msg["id"]
            if mid not in requests:
                order.append(mid)
                requests[mid] = {"first_record": rec["timestamp"], "last_record": rec["timestamp"],
                                 "blocks": [], **{k: 0 for k in USAGE}}
            r = requests[mid]
            if when(rec["timestamp"]) > when(r["last_record"]):
                r["last_record"] = rec["timestamp"]
            usage = msg.get("usage") or {}
            for k in USAGE:
                r[k] = max(r[k], int(usage.get(k) or 0))
            r["blocks"] += [b["type"] for b in msg.get("content") or [] if isinstance(b, dict) and b.get("type")]
        elif rec.get("type") == "user":
            content = msg.get("content")
            tool = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_result"] \
                if isinstance(content, list) else []
            if tool:
                results.append({"time": rec["timestamp"], "is_error": any(bool(b.get("is_error")) for b in tool)})
            elif prompt is None:
                prompt = rec["timestamp"]
    return {"prompt": prompt, "requests": [{"id": m, **requests[m]} for m in order], "tool_results": results}


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else f"first_request_{platform.node()}.json"
    sids = json.loads((HERE / "sessions.json").read_text(encoding="utf-8"))["session_ids"]
    found, missing = {}, []
    for sid in sids:
        path = find(sid)
        if path is None:
            missing.append(sid)
        else:
            found[sid] = numbers(path)
    data = json.dumps({"machine": platform.node(), "lane": str(LANE),
                       "script_sha256": hashlib.sha256((HERE / "extract.py").read_bytes()).hexdigest(),
                       "sessions": found, "missing": missing}, indent=1, sort_keys=True).encode("utf-8")
    (HERE / name).write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    (HERE / (name + ".sha256")).write_text(digest + "\n", encoding="utf-8")
    print(f"{len(found)} sessions read, {len(missing)} not on this machine; {name} sha256 {digest}")


if __name__ == "__main__":
    main()

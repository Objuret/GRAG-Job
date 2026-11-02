"""The lane sessions that began inside a judging start's window of half b and that no record of
half b names: times, model, assistant message count and summed usage, never content.

    python judge_calls_without_record.py <out json>

Reads the lane's transcripts (~/.claude-herb-lane/projects/**/*.jsonl, file name = session id) and
half b's eval_calls.jsonl and arm_outputs.jsonl (every session_id key). No model call.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

RUN = Path(r"A:\exjobbet\GRAG-Job\output\split\answerable715\artefact_v4__answerable715.b__cb72000__20261025T211532Z_desktop")
ROOT = Path.home() / ".claude-herb-lane" / "projects"
START = "2026-10-26T10:52:52.400971+00:00"
LO, HI = "2026-10-26T10:52:52", "2026-10-26T22:44:30"
KEYS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")


def session_ids(o, out):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "session_id" and isinstance(v, str):
                out.add(v)
            else:
                session_ids(v, out)
    elif isinstance(o, list):
        for v in o:
            session_ids(v, out)


def events(path):
    # a line with NUL bytes (a transcript the machine's stop cut) is not an event
    for x in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not x.strip() or "\x00" in x:
            continue
        try:
            yield json.loads(x)
        except json.JSONDecodeError:
            continue


def main():
    out_path = Path(sys.argv[1])
    named = set()
    for name in ("eval_calls.jsonl", "arm_outputs.jsonl"):
        with open(RUN / name, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    session_ids(json.loads(line), named)

    in_window, unnamed = 0, []
    for t in ROOT.rglob("*.jsonl"):
        times = [ev["timestamp"] for ev in events(t) if ev.get("timestamp")]
        if not times or not (LO <= times[0][:19] <= HI):
            continue
        in_window += 1
        if t.stem in named:
            continue
        msgs, models = {}, []
        for ev in events(t):
            m = ev.get("message") or {}
            if ev.get("type") == "assistant":
                if m.get("model") and m["model"] not in models:
                    models.append(m["model"])
                if m.get("usage"):
                    msgs[m.get("id") or ev.get("uuid")] = m["usage"]
        row = {"session_id": t.stem, "first_event": times[0], "last_event": max(times),
               "model": models[0] if len(models) == 1 else models, "assistant_messages": len(msgs)}
        row.update({k: sum(int(u.get(k) or 0) for u in msgs.values()) for k in KEYS})
        unnamed.append(row)
    unnamed.sort(key=lambda r: r["first_event"])

    result = {
        "how_found": (f"The lane's transcripts in {ROOT} (file name = session id) whose first event lies "
                      f"in [{LO}Z, {HI}Z] were compared with the session ids named by half b's "
                      f"eval_calls.jsonl and arm_outputs.jsonl (every session_id key); only times, model "
                      f"and usage were read, no content, and no model call was made."),
        "found_at": datetime.now(timezone.utc).isoformat(),
        "host": os.environ.get("COMPUTERNAME"),
        "starts": {START: {"window": [f"{LO}Z", f"{HI}Z"], "transcripts_in_window": in_window,
                           "session_ids_named_by_records": len(named),
                           "named_by_no_record": unnamed}},
    }
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result["starts"][START], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

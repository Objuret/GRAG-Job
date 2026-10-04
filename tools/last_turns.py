"""Print the last conversation of a Claude Code project, verbatim: his typed turns and the answer
each one got, tool calls and tool results left out, plus an index of the other recent sessions.

    python tools/last_turns.py                       # the project of the current directory
    python tools/last_turns.py --pairs 20            # a longer tail
    python tools/last_turns.py --session <id>        # one named session
    python tools/last_turns.py --hook                # SessionStart hook: Claude Code's JSON on stdin

"Last" means the session in which HE typed last: the candidates are the SCAN most recently
modified transcripts, read, and ordered by the timestamp of his last typed turn (a file's mtime
moves without him: reminders, agent lines). The index lists the other candidates with the time
and first words of his last turn there, so a reader can see when several conversations are live
and pick one with --session.

As a SessionStart hook (``.claude/settings.local.json``, matcher ``startup|compact``) the output
lands in the new session's context before the first turn. On ``startup`` it prints the newest
OTHER session of the same project (the starting session is excluded by its own transcript path
and id). On ``compact`` it prints the tail of the session itself, the part the compaction
summary just dropped. On ``resume`` and ``clear`` it prints nothing. Claude Code caps a hook's
stdout at 10,000 characters and keeps the FRONT past that, so the hook budget stays under it.

Human-turn filtering is ``canon_extract``'s, same rules, same wrapper stripping, so what prints
here is what ``docs/canon/raw`` holds, plus the assistant's replies. Times are UTC, as in the
transcripts. PAIRS, SCAN and the character budgets are print budgets, not measurements.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import canon_extract as ce  # noqa: E402

PROJECTS_ROOT = Path.home() / ".claude" / "projects"
DEFAULT_PAIRS = 8
DEFAULT_SCAN = 8
DEFAULT_MAX_CHARS = 24_000
HOOK_MAX_CHARS = 9_000          # Claude Code caps SessionStart stdout at 10,000 characters
HOOK_SOURCES = ("startup", "compact")
INDEX_PREVIEW = 110


def project_dir_for_cwd(cwd: str) -> Path | None:
    """Claude Code names a project folder after its cwd with ':' '\\' '/' turned into '-'."""
    encoded = re.sub(r"[:\\/]", "-", cwd.rstrip("\\/")).lower()
    if not PROJECTS_ROOT.is_dir():
        return None
    for candidate in PROJECTS_ROOT.iterdir():
        if candidate.is_dir() and candidate.name.lower() == encoded:
            return candidate
    return None


def assistant_text(obj: dict) -> str:
    content = (obj.get("message") or {}).get("content")
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts = [b.get("text", "") for b in content
             if isinstance(b, dict) and b.get("type") == "text"]
    return "\n".join(p for p in parts if p).strip()


def read_turns(path: Path) -> list[dict]:
    """[{who: 'he' | 'answer' | 'compact', ts, text}] in file order, consecutive answers merged."""
    turns: list[dict] = []
    pending: dict[str, dict] = {}

    def add(who: str, ts: str | None, text: str) -> None:
        if who == "answer" and turns and turns[-1]["who"] == "answer":
            turns[-1]["text"] = (turns[-1]["text"] + "\n\n" + text).strip()
            turns[-1]["ts"] = ts or turns[-1]["ts"]
            return
        turns.append({"who": who, "ts": ts, "text": text})

    for obj in ce.iter_lines(path):
        if obj.get("isSidechain"):
            continue
        kind = obj.get("type")
        if kind == "assistant":
            ce.note_prompt_box_questions(obj, pending)
            text = assistant_text(obj)
            if text:
                add("answer", obj.get("timestamp"), text)
            continue
        queued = ce.queued_command_text(obj)
        if queued is None and kind != "user":
            continue
        if obj.get("isCompactSummary"):
            add("compact", obj.get("timestamp"), "")
            continue
        if queued is not None:
            rule, text = ce.classify_text(queued, False)
        else:
            rule, text = ce.classify(obj, False)
            if rule == "tool_result":
                answer = ce.prompt_box_answer(obj, pending)
                if answer is not None:
                    rule, text = None, answer
        if rule:
            continue
        add("he", obj.get("timestamp"), text)
    return turns


def last_his(turns: list[dict]) -> dict | None:
    for t in reversed(turns):
        if t["who"] == "he":
            return t
    return None


def candidates(project: Path, exclude: set[str], scan: int) -> list[dict]:
    """The SCAN most recently modified sessions, read, ordered by his last typed turn, newest first."""
    files = [p for p in project.glob("*.jsonl") if p.stem not in exclude]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    found: list[dict] = []
    for path in files[:max(1, scan)]:
        turns = read_turns(path)
        last = last_his(turns)
        if last is None:
            continue
        found.append({"path": path, "turns": turns, "last_ts": last["ts"] or "", "last_text": last["text"]})
    found.sort(key=lambda c: c["last_ts"], reverse=True)
    return found


def stamp(ts: str | None) -> str:
    return (ts or "")[:16].replace("T", " ") + ("Z" if ts else "")


def block(turn: dict) -> str:
    if turn["who"] == "he":
        return f"## He · {stamp(turn['ts'])}\n\n{turn['text'].rstrip()}\n"
    if turn["who"] == "answer":
        return f"## Answer\n\n{turn['text'].rstrip()}\n"
    return "*(the context was compacted here)*\n"


def index_lines(others: list[dict]) -> str:
    if not others:
        return ""
    lines = ["Other recent sessions of this project, by his last typed turn (print one with --session <id>):"]
    for c in others:
        preview = re.sub(r"\s+", " ", c["last_text"]).strip()
        if len(preview) > INDEX_PREVIEW:
            preview = preview[:INDEX_PREVIEW].rstrip() + "…"
        lines.append(f"- {c['path'].stem} · {stamp(c['last_ts'])} · {preview}")
    return "\n".join(lines) + "\n\n"


def render(project: Path, chosen: dict, others: list[dict], pairs: int, max_chars: int) -> str:
    turns, path = chosen["turns"], chosen["path"]
    his = [i for i, t in enumerate(turns) if t["who"] == "he"]
    total = len(his)
    start = his[-pairs] if total > pairs else 0
    tail = turns[start:]
    blocks = [block(t) for t in tail]
    index = index_lines(others)
    cut_pairs = 0

    def size() -> int:
        return len(index) + sum(len(b) + 1 for b in blocks)

    while size() > max_chars and sum(1 for t in tail if t["who"] == "he") > 1:
        first = next(i for i, t in enumerate(tail) if t["who"] == "he")
        nxt = next((i for i, t in enumerate(tail) if t["who"] == "he" and i > first), None)
        if nxt is None:
            break
        tail, blocks = tail[nxt:], blocks[nxt:]
        cut_pairs += 1
    if size() > max_chars:
        longest = max(range(len(blocks)), key=lambda i: len(blocks[i]))
        keep = max(1_500, max_chars - (size() - len(blocks[longest])))
        body = blocks[longest]
        if len(body) > keep:
            blocks[longest] = f"[... {len(body) - keep:,} characters cut from the front ...]\n" + body[-keep:]

    shown = sum(1 for t in tail if t["who"] == "he")
    first_ts = stamp(next((t["ts"] for t in tail if t["ts"]), None))
    last_ts = stamp(next((t["ts"] for t in reversed(tail) if t["ts"]), None))
    head = (
        f"# Last conversation — {project.name}\n"
        f"session {path.stem} · {first_ts} → {last_ts} (UTC) · his turns {total - shown + 1}–{total} of {total}"
        f"{f' · print budget cut {cut_pairs} more' if cut_pairs else ''}\n"
        "printed by tools/last_turns.py — verbatim; tool calls and tool results left out\n\n"
    )
    return head + index + "\n".join(blocks)


def run_hook() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(data, dict):
        return 0
    source = data.get("source")
    if source not in HOOK_SOURCES:
        return 0
    transcript = Path(data["transcript_path"]) if data.get("transcript_path") else None
    project = transcript.parent if transcript else project_dir_for_cwd(data.get("cwd") or os.getcwd())
    if project is None or not project.is_dir():
        return 0
    if source == "compact":
        if transcript is None or not transcript.is_file():
            return 0
        turns = read_turns(transcript)
        last = last_his(turns)
        if last is None:
            return 0
        chosen = {"path": transcript, "turns": turns, "last_ts": last["ts"] or "", "last_text": last["text"]}
        others: list[dict] = []
    else:
        exclude = {transcript.stem} if transcript else set()
        if data.get("session_id"):
            exclude.add(str(data["session_id"]))
        found = candidates(project, exclude, DEFAULT_SCAN)
        if not found:
            return 0
        chosen, others = found[0], found[1:]
    print(render(project, chosen, others, DEFAULT_PAIRS, HOOK_MAX_CHARS))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--project", type=Path, default=None,
                        help="a folder under ~/.claude/projects (default: the one for the current directory)")
    parser.add_argument("--session", default=None, help="print this session id instead of the newest")
    parser.add_argument("--exclude", action="append", default=[], help="session ids to skip (repeatable)")
    parser.add_argument("--pairs", type=int, default=DEFAULT_PAIRS, help="his last N turns with their answers")
    parser.add_argument("--scan", type=int, default=DEFAULT_SCAN,
                        help="how many recently modified transcripts to read when choosing the newest")
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    parser.add_argument("--hook", action="store_true", help="SessionStart hook mode: JSON on stdin")
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if args.hook:
        try:
            return run_hook()
        except Exception:
            return 0  # a hook must never break a session start

    project = args.project or project_dir_for_cwd(os.getcwd())
    if project is None or not project.is_dir():
        print(f"no transcript folder for {os.getcwd()} under {PROJECTS_ROOT}", file=sys.stderr)
        return 1
    if args.session:
        path = project / f"{args.session}.jsonl"
        if not path.is_file():
            print(f"no session {args.session} in {project}", file=sys.stderr)
            return 1
        turns = read_turns(path)
        last = last_his(turns)
        if last is None:
            print(f"session {args.session} has no typed turn", file=sys.stderr)
            return 1
        chosen = {"path": path, "turns": turns, "last_ts": last["ts"] or "", "last_text": last["text"]}
        others = [c for c in candidates(project, set(args.exclude) | {args.session}, args.scan)]
    else:
        found = candidates(project, set(args.exclude), args.scan)
        if not found:
            print(f"no session with a typed turn in {project}", file=sys.stderr)
            return 1
        chosen, others = found[0], found[1:]
    print(render(project, chosen, others, max(1, args.pairs), max(2_000, args.max_chars)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

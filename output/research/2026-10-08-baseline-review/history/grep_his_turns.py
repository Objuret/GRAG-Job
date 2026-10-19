"""Grep his typed turns (his_turns_all_sources.jsonl) for a regex; print matches with date.

    python grep_his_turns.py --count                      # hits per keyword of the task's list
    python grep_his_turns.py "regex" [--ctx 300] [--since 2026-06-01] [--before ...] [--max-len N]

With --ctx N only N characters on each side of every match are printed (turns longer than that);
without it the whole turn prints. Pasted blocks (very long turns) are cut to --max-len.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEYWORDS = ["metric", "token", "time", "latency", "cost", "build", "runtime", "stamp", "pointer",
            "trace", "trac", "manifest", "record", "keep", "kept", "save", "log", "telemetry",
            "provenance", "reproduc", "hardware", "memory", "cache", "datapoint", "measure",
            "duration", "seconds", "wall", "gpu", "vram", "cpu", "ram", "usage", "data"]


def load() -> list[dict]:
    return [json.loads(l) for l in (HERE / "his_turns_all_sources.jsonl").open(encoding="utf-8")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pattern", nargs="?")
    ap.add_argument("--count", action="store_true")
    ap.add_argument("--ctx", type=int, default=0)
    ap.add_argument("--since", default="")
    ap.add_argument("--before", default="9999")
    ap.add_argument("--max-len", type=int, default=6000)
    ap.add_argument("--skip-long", type=int, default=0, help="skip turns longer than this many chars (pastes)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rows = load()
    if args.count:
        for k in KEYWORDS:
            rx = re.compile(k, re.I)
            hits = [r for r in rows if rx.search(r["text"])]
            print(f"{k:12s} {len(hits):5d} turns")
        print(f"total turns {len(rows)}, total chars {sum(len(r['text']) for r in rows)}")
        return 0
    rx = re.compile(args.pattern, re.I)
    n = 0
    for r in rows:
        ts = r["ts"] or ""
        if not (args.since <= ts[:10] <= args.before):
            continue
        text = r["text"]
        if args.skip_long and len(text) > args.skip_long:
            continue
        ms = list(rx.finditer(text))
        if not ms:
            continue
        n += 1
        print(f"=== {ts[:16]}Z · session {r['session'][:8]} · {len(text)} chars")
        if args.ctx and len(text) > 2 * args.ctx:
            spans = []
            for m in ms:
                a, b = max(0, m.start() - args.ctx), min(len(text), m.end() + args.ctx)
                if spans and a <= spans[-1][1]:
                    spans[-1][1] = b
                else:
                    spans.append([a, b])
            for a, b in spans:
                print(("…" if a else "") + text[a:b].replace("\n", " ⏎ ") + ("…" if b < len(text) else ""))
        else:
            print(text[:args.max_len] + ("… [cut]" if len(text) > args.max_len else ""))
        print()
    print(f"--- {n} turns matched {args.pattern!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

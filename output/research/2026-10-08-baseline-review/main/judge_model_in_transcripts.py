"""Which model id answered the lane's Haiku calls, by day, read from the CLI's own transcripts.
STRUCTURE ONLY: of each line only `type`, `timestamp` and `message.model` are read; no text."""
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
LANE = Path.home() / ".claude" / "projects" / "C--Users-jocke-AppData-Local-Temp-herb-claude-lane"
by_day = defaultdict(Counter)
n_files = 0
pat = re.compile(r'"model"\s*:\s*"([^"]+)"')
tpat = re.compile(r'"timestamp"\s*:\s*"(\d{4}-\d{2}-\d{2})')
with os.scandir(LANE) as it:
    for e in it:
        if not e.name.endswith(".jsonl"):
            continue
        n_files += 1
        with open(e.path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"type":"assistant"' not in line:
                    continue
                m, t = pat.search(line), tpat.search(line)
                if m:
                    by_day[t.group(1) if t else "?"][m.group(1)] += 1
print(f"transcript files read: {n_files}")
for day in sorted(by_day):
    print(f"  {day}: " + ", ".join(f"{k} x{v}" for k, v in sorted(by_day[day].items())))

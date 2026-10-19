"""Keep the laptop from idle sleep while a run folder is locked by its run.

    .venv/Scripts/python.exe output/research/2026-10-09-baseline-unit-text/keep_awake.py <run folder> [<run folder> ...]

Windows is told the system is required for as long as this process lives; no power setting is
changed. It ends by itself when none of the folders holds a .run.lock any more, after it has seen
one. A closed lid still puts the laptop to sleep.
"""
import ctypes
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ES_CONTINUOUS, ES_SYSTEM_REQUIRED, ES_DISPLAY_REQUIRED = 0x80000000, 0x00000001, 0x00000002
folders = [Path(a) for a in sys.argv[1:]]
ok = ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)
print(f"{datetime.now(timezone.utc).isoformat()[:19]}Z keeping awake: {bool(ok)}", flush=True)
seen, quiet = False, 0
while True:
    locked = [f.name for f in folders if (f / ".run.lock").exists()]
    seen = seen or bool(locked)
    quiet = 0 if locked else quiet + 1
    if (seen and quiet >= 12) or (not seen and quiet >= 720):     # a minute after the last lock; or an hour with none
        break
    time.sleep(5)
ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
print(f"{datetime.now(timezone.utc).isoformat()[:19]}Z released", flush=True)

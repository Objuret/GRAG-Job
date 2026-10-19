"""When each row of a run was written, and which calls needed more than one try. Stamps and counts only."""
import io, json, sys
from datetime import datetime
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
d = Path(sys.argv[1])
rows = [json.loads(x) for x in (d / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
t = [datetime.fromisoformat(r["answered_at"]) for r in rows]
print(f"rows {len(rows)} | first written {t[0].isoformat()[:19]}Z | last written {t[-1].isoformat()[:19]}Z")
gaps = [(i, (t[i] - t[i - 1]).total_seconds()) for i in range(1, len(t))]
big = [(i, g) for i, g in gaps if g > 120]
print(f"seconds between one row and the next: median {sorted(g for _, g in gaps)[len(gaps) // 2]:.1f} | gaps over 120 s: {[(i, round(g)) for i, g in big]}")
for i, r in enumerate(rows):
    for c in r.get("calls") or []:
        if c.get("kind") == "chat" and (len(c.get("attempts") or []) > 1 or (r.get("timing") or {}).get("wall_s", 0) > 120):
            print(f"row {i}: written {r['answered_at'][:19]}Z | question wall {r['timing']['wall_s']:.0f} s | started {r['timing']['started_at'][:19]}Z | "
                  f"tries {[(a['n'], a['outcome'], round(a['seconds'], 1), a['started_at'][11:19]) for a in c['attempts']]} | generator time_s {r['generator']['time_s']:.0f} request_s {r['generator'].get('request_s', 0):.0f} retry_s {r['generator'].get('retry_s', 0):.0f}")
man = json.loads((d / "run_manifest.json").read_text(encoding="utf-8"))
for leg in man.get("legs") or []:
    print(f"start {leg['leg']}: {leg['started_at'][:19]}Z -> {leg['finished_at'][:19]}Z | wall {leg['wall_s']:.0f} s | answered {leg['n_answered']} of {leg['n_todo']} | aborted {leg.get('aborted')}")

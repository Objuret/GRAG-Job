"""The two rows of lucene's final run whose answer call spanned the laptop's sleep: every time field
they hold, and what the CLI's own transcripts of their tries show. Keys, numbers and stamps only."""
import io, json, sys
from datetime import datetime, timezone
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
d = Path(sys.argv[1])
rows = [json.loads(x) for x in (d / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
LANE = Path.home() / ".claude-herb-lane" / "projects" / "C--Users-jocke-AppData-Local-Temp-herb-claude-lane"
files = sorted(LANE.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)


def near(stamp):
    t = datetime.fromisoformat(stamp).timestamp()
    out = []
    for f in files:
        first = None
        with f.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                ts = e.get("timestamp")
                if ts:
                    first = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
                    break
        if first is not None and abs(first - t) < 20:
            out.append(f)
    return out


for i, r in enumerate(rows):
    c = next((c for c in r.get("calls") or [] if c.get("kind") == "chat"), None)
    if not c or len(c["attempts"]) < 2:
        continue
    print(f"row {i} id {r['id']}")
    print(f"   generator {r['generator']}")
    print(f"   timing {r['timing']}")
    print(f"   search_time_s {r['search_time_s']} | retrieval {r['retrieval']} | answered_at {r['answered_at']}")
    print(f"   call: started_at {c['started_at']} finished_at {c['finished_at']} timeout_s {c['timeout_s']} max_tries {c['max_tries']} | usage {c['usage']}")
    for a in c["attempts"]:
        print(f"      try {a['n']}: started_at {a['started_at']} seconds {a['seconds']} outcome {a['outcome']} returncode {a['returncode']} backoff_s {a.get('backoff_s')} | "
              f"stdout {len(a['stdout'] or '') if a.get('stdout') is not None else None} chars, stderr {len(a['stderr'] or '') if a.get('stderr') is not None else None} chars | keys {sorted(a)}")
        for f in near(a["started_at"]):
            kinds, blocks, usage = {}, {}, []
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                kinds[e.get("type")] = kinds.get(e.get("type"), 0) + 1
                if e.get("type") == "assistant":
                    m = e.get("message") or {}
                    for b in m.get("content") or []:
                        blocks[b.get("type")] = blocks.get(b.get("type"), 0) + 1
                    u = m.get("usage") or {}
                    usage.append((u.get("input_tokens"), u.get("cache_creation_input_tokens"), u.get("output_tokens"), e.get("timestamp", "")[11:19]))
            print(f"         the CLI's transcript {f.name[:8]}: entries {kinds} | assistant blocks {blocks} | assistant usage (in, cache_creation, out, at) {usage}")
man = json.loads((d / "run_manifest.json").read_text(encoding="utf-8"))
print("manifest legs:", [{k: leg.get(k) for k in ("leg", "started_at", "finished_at", "wall_s", "process_cpu_s", "prepare_s", "n_answered")} for leg in man["legs"]])
print("manifest keys with a time in them:", {k: man.get(k) for k in ("timestamp",)}, "| build_stats", man.get("build_stats"))
ev = json.loads((d / "eval_manifest.json").read_text(encoding="utf-8"))
print("eval manifest:", {k: ev.get(k) for k in ("timestamp", "judge_elapsed_s")}, "| legs", [(l["settings"].get("started_at"), l["settings"].get("finished_at"), round(l["settings"].get("wall_s") or 0, 1)) for l in ev.get("judge_legs") or []])

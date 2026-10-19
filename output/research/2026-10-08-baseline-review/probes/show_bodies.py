"""Print what a logged request body holds: every top-level field, and each system and message block
with its length. Text is shown only where it is the CLI's or the harness's own (system blocks, added
blocks); the user prompt itself (the made-up question and corpus units) is shown by length and ends."""
import io, json, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
d = Path(sys.argv[1])
show = int(sys.argv[2]) if len(sys.argv) > 2 else 700
for f in sorted(d.glob("*.request.json"), key=lambda p: p.stat().st_mtime):
    b = json.loads(f.read_text(encoding="utf-8"))
    print(f"\n=== request {f.name[:8]}  ({f.stat().st_size} bytes)  model {b.get('model')}")
    for k, v in b.items():
        if k in ("system", "messages", "tools"):
            continue
        print(f"  {k}: {json.dumps(v, ensure_ascii=False)[:400]}")
    sysv = b.get("system")
    if isinstance(sysv, str):
        print(f"  system: str[{len(sysv)}] {sysv[:show]!r}")
    else:
        for i, blk in enumerate(sysv or []):
            t = blk.get("text", "")
            print(f"  system[{i}]: type {blk.get('type')} cache_control {blk.get('cache_control')} text[{len(t)}] {t[:show]!r}")
    for i, tool in enumerate(b.get("tools") or []):
        print(f"  tools[{i}]: name {tool.get('name')!r} description[{len(tool.get('description') or '')}] {(tool.get('description') or '')[:300]!r} input_schema {json.dumps(tool.get('input_schema'))[:300]}")
    for i, m in enumerate(b.get("messages") or []):
        c = m.get("content")
        if isinstance(c, str):
            print(f"  messages[{i}] {m.get('role')}: str[{len(c)}] CR {c.count(chr(13))} LF {c.count(chr(10))} starts {c[:60]!r} ends {c[-60:]!r}")
        else:
            for j, blk in enumerate(c or []):
                t = blk.get("text") if blk.get("type") == "text" else json.dumps(blk, ensure_ascii=False)
                t = t or ""
                print(f"  messages[{i}] {m.get('role')} block[{j}] type {blk.get('type')} cache_control {blk.get('cache_control')} text[{len(t)}] CR {t.count(chr(13))} LF {t.count(chr(10))} starts {t[:300]!r} ends {t[-80:]!r}")
for f in sorted(d.glob("*.response.json"), key=lambda p: p.stat().st_mtime):
    b = json.loads(f.read_text(encoding="utf-8"))
    blocks = [(x.get("type"), len(x.get("text") or x.get("thinking") or json.dumps(x.get("input") or ""))) for x in (b.get("content") or [])]
    print(f"\n=== response {f.name[:16]} model {b.get('model')} stop_reason {b.get('stop_reason')} blocks {blocks} usage {json.dumps(b.get('usage'))[:500]}")

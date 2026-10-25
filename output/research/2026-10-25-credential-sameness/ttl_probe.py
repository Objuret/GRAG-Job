"""One judge-shaped call with the CLAUDE_API key and ENABLE_PROMPT_CACHING_1H=1, request logging on;
prints the logged request's betas and cache_control blocks (no ids, no key)."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, r"A:\exjobbet\GRAG-Job\prod")
from harness import chat  # noqa: E402

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
chat._login()
call = chat.call_settings({"model": "claude-haiku-4-5-20251001", "temperature": 0.01, "thinking": False,
                           "messages": [{"role": "user", "content": "Reply with the word ok."}]})
env = chat._try_env(call, "api_key")
env.update({"CLAUDE_CODE_ENABLE_TELEMETRY": "1", "OTEL_LOGS_EXPORTER": "console",
            "OTEL_METRICS_EXPORTER": "none", "OTEL_TRACES_EXPORTER": "none",
            "OTEL_LOG_RAW_API_BODIES": f"file:{out}", "ENABLE_PROMPT_CACHING_1H": "1"})
r = subprocess.run(call["cmd"], input=call["prompt"].encode("utf-8"), capture_output=True, timeout=180,
                   cwd=chat._claude_cwd(), env=env)
print("returncode", r.returncode)
for f in sorted(out.glob("*.request.json")):
    b = json.loads(f.read_text(encoding="utf-8"))
    print("betas:", sorted(b.get("betas", [])))
    print("system cache_control:", [s.get("cache_control") for s in b.get("system", [])])
    print("message cache_control:", [c.get("cache_control") for m in b.get("messages", [])
                                     for c in (m.get("content") if isinstance(m.get("content"), list) else [])
                                     if isinstance(c, dict) and c.get("cache_control")])

"""The lane's fallback path: the subscription try gets a faked usage-limit reply (HTTP 429), the
same try then goes for real with the CLAUDE_API key. Prints the call record's credential fields.
Also checks that without HERB_CLAUDE_API_FALLBACK=on the key is never used."""
import json
import os
import subprocess
import sys

sys.path.insert(0, r"A:\exjobbet\GRAG-Job\prod")
from harness import chat  # noqa: E402

real_run = subprocess.run
LIMIT = json.dumps({"type": "result", "subtype": "success", "is_error": True, "api_error_status": 429,
                    "result": "You've hit your session limit"}).encode()


def faked(cmd, **kw):
    if "ANTHROPIC_API_KEY" not in (kw.get("env") or {}):
        return subprocess.CompletedProcess(cmd, 1, stdout=LIMIT, stderr=b"")
    return real_run(cmd, **kw)


chat.subprocess.run = faked
payload = {"model": "claude-haiku-4-5-20251001", "temperature": 0.01, "thinking": False,
           "messages": [{"role": "user", "content": "Reply with the word ok."}]}

os.environ.pop("HERB_CLAUDE_API_FALLBACK", None)
try:
    chat.post("/chat/completions", payload, timeout=120, max_tries=1)
    print("switch off: answered (unexpected)")
except RuntimeError as e:
    print("switch off: refused as before ->", str(e)[:90])

os.environ["HERB_CLAUDE_API_FALLBACK"] = "on"
r = chat.post("/chat/completions", payload, timeout=120, max_tries=1)
rec = r["call"]
print("switch on: answer", repr(r["choices"][0]["message"]["content"])[:30], "| call credential", rec["credential"])
for a in rec["attempts"]:
    print("   try", a["n"], a["credential"], a["outcome"], f"{a['seconds']:.2f}s")
print("   usage", rec["usage"], "| env_set has a key:", any("KEY" in k for k in rec["env_set"]))

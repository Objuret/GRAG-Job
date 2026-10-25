"""Send the same lane call once with the subscription token and once with the CLAUDE_API key, with the
CLI's own request logging on, and compare the logged requests field by field. Prints only which
fields differ and how (lengths, hashes); never an id, an e-mail or a key. Made-up question and
context, nothing from HERB.

    python credential_probe.py <out dir>
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, r"A:\exjobbet\GRAG-Job\prod")
from harness import chat  # noqa: E402
from harness.contract import generator_messages  # noqa: E402
from harness.orchestrator import GENERATOR_MODEL, _ANSWER_SCHEMA, _GENERATOR_SETTINGS  # noqa: E402

OUT = Path(sys.argv[1])
QUESTION = "Which colour did the lighthouse keeper paint the north door in the spring of 1902?"
CONTEXTS = ["Logbook, April 1902: the keeper repainted the north door a pale green after the storms.",
            "Letter, May 1902: the south shed roof was mended; the doors were left as they were."]
CALLS = {
    "answer": {"model": GENERATOR_MODEL, **_GENERATOR_SETTINGS,
               "messages": generator_messages(QUESTION, CONTEXTS),
               "response_format": {"type": "json_schema",
                                   "json_schema": {"name": "answer", "schema": _ANSWER_SCHEMA}}},
    "judge": {"model": "claude-haiku-4-5-20251001", "temperature": 0.01, "thinking": False,
              "messages": [{"role": "user", "content": "Given the context and the answer, list the "
                            "claims in the answer as JSON {\"claims\": [...]}.\nContext: "
                            + CONTEXTS[0] + "\nAnswer: The north door was painted pale green."}]},
}
LOGGING = {"CLAUDE_CODE_ENABLE_TELEMETRY": "1", "OTEL_LOGS_EXPORTER": "console",
           "OTEL_METRICS_EXPORTER": "none", "OTEL_TRACES_EXPORTER": "none"}

chat._login()
key = os.environ.get("CLAUDE_API")
if not key:
    sys.exit("no CLAUDE_API in the environment or .env")


def flat(x, path=""):
    if isinstance(x, dict):
        for k, v in x.items():
            yield from flat(v, f"{path}.{k}" if path else k)
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from flat(v, f"{path}[{i}]")
    else:
        yield path, x


def show(v):
    s = json.dumps(v, ensure_ascii=False)
    return f"{len(s)} chars, sha256 {hashlib.sha256(s.encode()).hexdigest()[:12]}"


for name, payload in CALLS.items():
    call = chat.call_settings(payload)
    bodies, replies = {}, {}
    for cred in ("subscription", "api_key"):
        d = OUT / name / cred
        d.mkdir(parents=True, exist_ok=True)
        env = chat._try_env(call, cred)
        env.update(LOGGING, OTEL_LOG_RAW_API_BODIES=f"file:{d}")
        r = subprocess.run(call["cmd"], input=call["prompt"].encode("utf-8"), capture_output=True,
                           timeout=300, cwd=chat._claude_cwd(), env=env)
        try:
            reply = json.loads(r.stdout.decode("utf-8", "replace"))
        except ValueError:
            reply = {"unparsed": True}
        u = reply.get("usage") or {}
        mu = reply.get("modelUsage") or {}
        sid = reply.get("session_id")
        tfiles = list((Path.home() / ".claude-herb-lane" / "projects").glob(f"*/{sid}.jsonl")) if sid else []
        tusage = {}
        if tfiles:
            per = {}
            for line in tfiles[0].read_text(encoding="utf-8").splitlines():
                o = json.loads(line)
                if o.get("type") == "assistant":
                    per[o["message"]["id"]] = o["message"].get("usage") or {}
            tusage = {k: sum(int(x.get(k) or 0) for x in per.values())
                      for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
                                "output_tokens")}
        replies[cred] = {
            "returncode": r.returncode, "is_error": reply.get("is_error"),
            "api_error_status": reply.get("api_error_status"),
            "reply_fields": sorted(reply.keys()),
            "usage_tokens": {k: u.get(k) for k in ("input_tokens", "cache_creation_input_tokens",
                                                   "cache_read_input_tokens", "output_tokens")},
            "cache_writes": u.get("cache_creation"),
            "model_usage": {m: {k: v for k, v in x.items() if k != "costUSD"} for m, x in mu.items()},
            "has_duration_ms": "duration_ms" in reply, "has_duration_api_ms": "duration_api_ms" in reply,
            "has_cost": "total_cost_usd" in reply,
            "transcript_found": len(tfiles) == 1, "transcript_usage": tusage}
        files = sorted(d.glob("*.request.json"))
        bodies[cred] = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    print(f"== {name} call")
    for cred in replies:
        print(f"  {cred}: logged requests {len(bodies[cred])}")
        for k, v in replies[cred].items():
            print(f"      {k}: {v}")
    a, b = set(replies["subscription"]["reply_fields"]), set(replies["api_key"]["reply_fields"])
    print(f"  reply fields only with the subscription: {sorted(a - b)} | only with the key: {sorted(b - a)}")
    for i, (a, b) in enumerate(zip(bodies["subscription"], bodies["api_key"])):
        fa, fb = dict(flat(a)), dict(flat(b))
        diff = sorted(p for p in set(fa) | set(fb) if fa.get(p, "<absent>") != fb.get(p, "<absent>"))
        print(f"  request {i}: {len(fa)} fields with the subscription, {len(fb)} with the key; "
              f"{len(diff)} differ")
        for p in diff:
            print(f"    {p}: subscription {show(fa.get(p, '<absent>'))} | key {show(fb.get(p, '<absent>'))}")

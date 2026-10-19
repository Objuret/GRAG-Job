"""PROBES, third round: what the lane sends NOW (prod/harness/chat.py after the fixes), seen in the
request the CLI logs. The argv and the environment of each call are the lane's own
(chat.call_settings, chat._call_env); the only things added are the CLI's request-logging variables
and, per probe, what its name says. Made-up question only.

    .venv/Scripts/python.exe output/research/2026-10-08-baseline-review/probes/probe3.py <name> [<name> ...]
    .venv/Scripts/python.exe output/research/2026-10-08-baseline-review/probes/probe3.py --show

names:
  harness_answer / harness_judge     the call as the harness makes it, started from this (agent) shell
  terminal_answer / terminal_judge   the same with every CLAUDE* variable of the shell taken away,
                                     as a start from his own terminal has it
  ownconfig_judge / ownconfig_answer the same with the CLI given its own empty config folder and the
                                     login token of .env (the token is never printed)
"""
import io
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "prod"))

from harness import chat  # noqa: E402
from harness import orchestrator  # noqa: E402
from harness.contract import generator_messages  # noqa: E402
from eval import ragas as scorer  # noqa: E402

PROOF = REPO / "output" / "research" / "2026-10-08-keep-everything-proof"
ROW = json.loads((PROOF / "lucene__answer" / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines()[0])
QUESTION = ROW["question"]                       # the made-up question
SHORT_CONTEXTS = ROW["contexts"][:3]             # three corpus units the made-up question retrieved
JUDGE_PROMPT = "Reply with the single word:\nready"

# the two payloads exactly as the harness builds them (orchestrator.build_shared_generator,
# eval.ragas._claude_verdict)
ANSWER = {"model": orchestrator.GENERATOR_MODEL, **orchestrator._GENERATOR_SETTINGS,
          "messages": generator_messages(QUESTION, SHORT_CONTEXTS),
          "response_format": {"type": "json_schema",
                              "json_schema": {"name": "answer", "schema": orchestrator._ANSWER_SCHEMA}}}
JUDGE = {"model": scorer.JUDGE_MODEL, "messages": [{"role": "user", "content": JUDGE_PROMPT}],
         "temperature": scorer._JudgeLLM().get_temperature(1), "thinking": False}
LOGGING = {"CLAUDE_CODE_ENABLE_TELEMETRY": "1", "OTEL_LOGS_EXPORTER": "console",
           "OTEL_METRICS_EXPORTER": "none", "OTEL_TRACES_EXPORTER": "none"}


def now():
    return datetime.now(timezone.utc).isoformat()


def _dotenv_token():
    for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip().replace("export ", "")
        if line.startswith("CLAUDE_CODE_OAUTH_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("no CLAUDE_CODE_OAUTH_TOKEN line in .env")


def call(name, payload, shell="agent"):
    out_dir = HERE / name
    bodies = out_dir / "bodies"
    bodies.mkdir(parents=True, exist_ok=True)
    for old in bodies.glob("*.json"):
        old.unlink()
    chat._login()                  # the lane's own: the token of .env, its own config folder
    settings = chat.call_settings(payload)
    base = dict(os.environ)
    added = []
    if shell in ("terminal", "ownconfig"):
        base = {k: v for k, v in base.items() if not k.upper().startswith("CLAUDE")}
    if shell == "ownconfig":
        cfg = out_dir / "config"
        cfg.mkdir(exist_ok=True)
        base.update(CLAUDE_CONFIG_DIR=str(cfg), CLAUDE_CODE_OAUTH_TOKEN=_dotenv_token())
        added = ["CLAUDE_CONFIG_DIR=<an empty folder of the probe>", "CLAUDE_CODE_OAUTH_TOKEN=<.env>"]
    with patch.dict(os.environ, base, clear=True):
        env = chat._call_env(settings)
    env.update(LOGGING, OTEL_LOG_RAW_API_BODIES="file:" + bodies.as_posix())
    started, t0 = now(), time.perf_counter()
    r = subprocess.run(settings["cmd"], input=settings["prompt"].encode("utf-8"), capture_output=True,
                       timeout=300, cwd=chat._claude_cwd(), env=env)
    seconds = time.perf_counter() - t0
    stdout = r.stdout.decode("utf-8", "replace")
    (out_dir / "stdout.txt").write_text(stdout, encoding="utf-8")
    (out_dir / "stderr.txt").write_text(r.stderr.decode("utf-8", "replace"), encoding="utf-8")
    envelope = {}
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if line.startswith("{") and '"type"' in line and '"result"' in line:
            try:
                envelope = json.loads(line)
                break
            except ValueError:
                continue
    rec = {"probe": name, "started_at": started, "finished_at": now(), "seconds": round(seconds, 3),
           "returncode": r.returncode, "model": payload["model"], "flags": settings["flags"],
           "shell": shell, "added_env": added + ["<request logging>"],
           "lane_env_set": settings["env_set"], "lane_env_unset": settings["env_unset"],
           "applied": settings["applied"], "not_applied": settings["not_applied"],
           "prompt_chars": len(settings["prompt"]), "session_id": envelope.get("session_id"),
           "num_turns": envelope.get("num_turns"), "stop_reason": envelope.get("stop_reason"),
           "usage": {k: (envelope.get("usage") or {}).get(k) for k in
                     ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")},
           "models": sorted((envelope.get("modelUsage") or {}).keys()),
           "duration_ms": envelope.get("duration_ms"), "duration_api_ms": envelope.get("duration_api_ms"),
           "result": (envelope.get("result") or "")[:200],
           "result_chars": len(envelope.get("result") or "")}
    (out_dir / "sent.json").write_text(json.dumps(
        {"prompt": settings["prompt"], "system": settings["system"]}, ensure_ascii=False), encoding="utf-8")
    with (HERE / "calls_made.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in rec.items() if k not in ("flags",)}, ensure_ascii=False, indent=1))
    return rec


PROBES = {
    "harness_answer": (ANSWER, "agent"), "harness_judge": (JUDGE, "agent"),
    "terminal_answer": (ANSWER, "terminal"), "terminal_judge": (JUDGE, "terminal"),
    "ownconfig_judge": (JUDGE, "ownconfig"), "ownconfig_answer": (ANSWER, "ownconfig"),
}


def _requests(name):
    d = HERE / name / "bodies"
    if not d.is_dir():
        return None
    return [json.loads(f.read_text(encoding="utf-8"))
            for f in sorted(d.glob("*.request.json"), key=lambda p: p.stat().st_mtime)]


def _model_facing(body):
    """The request without the fields that name the account, the session or the client."""
    return {k: v for k, v in body.items() if k not in ("metadata",)}


def show():
    seen = {}
    for name in PROBES:
        reqs = _requests(name)
        if reqs is None:
            continue
        sent = json.loads((HERE / name / "sent.json").read_text(encoding="utf-8"))
        print(f"\n{name}: requests logged {len(reqs)}")
        for b in reqs:
            sysb = b.get("system") or []
            sysb = sysb if isinstance(sysb, list) else [{"text": sysb}]
            msg = b["messages"][0]["content"]
            blocks = msg if isinstance(msg, list) else [{"type": "text", "text": msg}]
            texts = [x.get("text", "") for x in blocks]
            reminder = next((t for t in texts if "<system-reminder>" in t), "")
            print(f"   model {b['model']} | thinking {json.dumps(b.get('thinking'))} | output_config "
                  f"{json.dumps(b.get('output_config'))} | temperature {b.get('temperature', '(not sent)')} | "
                  f"top_p {b.get('top_p', '(not sent)')} | max_tokens {b.get('max_tokens')} | "
                  f"tools {[t['name'] for t in b.get('tools') or []]} | tool_choice {json.dumps(b.get('tool_choice'))}")
            print(f"   messages {len(b['messages'])} | system blocks: "
                  f"{[(len(x.get('text', '')), x.get('text', '')[:62]) for x in sysb]}")
            print(f"   the harness's system text is a system block, byte for byte: "
                  f"{sent['system'] in [x.get('text', '') for x in sysb] if sent['system'] else 'none was given'}")
            print(f"   user blocks (chars): {[len(t) for t in texts]} | the last one is the kept prompt, byte for byte: "
                  f"{texts[-1] == sent['prompt']} | CR in it: {chr(13) in texts[-1]}")
            lines = [ln for ln in reminder.splitlines() if ln.startswith("# ")]
            print(f"   block in front of the prompt: {len(reminder)} chars, sections {lines}")
            other = sorted(k for k in b if k not in ("model", "messages", "system", "thinking", "output_config",
                                                      "temperature", "top_p", "max_tokens", "tools", "tool_choice",
                                                      "metadata", "stream"))
            print(f"   other request fields: {other} | stream {b.get('stream')}")
        seen[name] = [_model_facing(b) for b in reqs]
    for a, b in (("harness_answer", "terminal_answer"), ("harness_judge", "terminal_judge"),
                 ("harness_judge", "ownconfig_judge"), ("harness_answer", "ownconfig_answer")):
        if a in seen and b in seen:
            same = seen[a] == seen[b]
            print(f"\n{a} against {b}: request the same apart from `metadata`: {same}")
            if not same and len(seen[a]) == len(seen[b]) == 1:
                x, y = seen[a][0], seen[b][0]
                for k in sorted(set(x) | set(y)):
                    if x.get(k) != y.get(k):
                        xs, ys = json.dumps(x.get(k), ensure_ascii=False), json.dumps(y.get(k), ensure_ascii=False)
                        # the differing field, cut around the first differing character; the e-mail
                        # address is masked
                        i = next((i for i, (p, q) in enumerate(zip(xs, ys)) if p != q), min(len(xs), len(ys)))
                        def cut(s):
                            s = s[max(0, i - 80):i + 160]
                            import re
                            return re.sub(r"[\w.+-]+@[\w.-]+", "<e-mail>", s)
                        print(f"   field `{k}` differs (lengths {len(xs)} / {len(ys)}) at char {i}:")
                        print(f"      {a}: ...{cut(xs)}")
                        print(f"      {b}: ...{cut(ys)}")


if __name__ == "__main__":
    if sys.argv[1:] == ["--show"]:
        show()
    else:
        print(f"CLI: {chat.cli_version()} | judge {scorer.JUDGE_MODEL} | generator {orchestrator.GENERATOR_MODEL}")
        for n in sys.argv[1:]:
            payload, shell = PROBES[n]
            print(f"\n===== probe {n}")
            call(n, payload, shell)

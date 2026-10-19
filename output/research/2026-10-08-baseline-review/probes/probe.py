"""PROBES of the headless lane, on the made-up question only. Not a proof of the harness: these call the
CLI directly with the lane's own argv, working directory and stdin handling (prod/harness/chat.py:163-181,
210-215), plus what each probe adds (request logging variables, one extra flag, one extra variable).
Nothing under prod/ is changed. Each call is logged with its stamp and the CLI's session id in
calls_made.jsonl, so its transcript in the lane's folder is not mistaken for a call of a run.

    .venv/Scripts/python.exe output/research/2026-10-08-baseline-review/probes/probe.py <name> [<name> ...]

names: answer_logged, judge_logged, answer_no_user_settings, answer_no_title
"""
import io
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "prod"))

from harness import chat  # noqa: E402
from harness import orchestrator  # noqa: E402
from harness.contract import GENERATOR_SYSTEM, generator_user_content  # noqa: E402

PROOF = REPO / "output" / "research" / "2026-10-08-keep-everything-proof"
ROW = json.loads((PROOF / "lucene__answer" / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines()[0])
QUESTION = ROW["question"]                       # the made-up question
SHORT_CONTEXTS = ROW["contexts"][:3]             # three corpus units the made-up question retrieved
ANSWER_PROMPT = generator_user_content(QUESTION, SHORT_CONTEXTS)
JUDGE_PROMPT = "Reply with the single word: ready"


def lane_argv(model, system=None, schema=None, extra=()):
    cmd = [chat._CLAUDE_EXE, "-p", "--model", model, "--output-format", "json", "--tools", "", "--safe-mode"]
    cmd += list(extra)
    if system:
        cmd += ["--system-prompt", system]
    if schema:
        cmd += ["--json-schema", json.dumps(schema)]
    return cmd


def now():
    return datetime.now(timezone.utc).isoformat()


def call(name, model, prompt, system=None, schema=None, extra=(), env_add=None, logged=False,
         binary=False):
    out_dir = HERE / name
    out_dir.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "MEMPALACE_HOOKS_AUTO_SAVE": "false", **(env_add or {})}
    if logged:
        bodies = out_dir / "bodies"
        bodies.mkdir(exist_ok=True)
        env.update({"CLAUDE_CODE_ENABLE_TELEMETRY": "1", "OTEL_LOGS_EXPORTER": "console",
                    "OTEL_METRICS_EXPORTER": "none", "OTEL_TRACES_EXPORTER": "none",
                    "OTEL_LOG_RAW_API_BODIES": "file:" + bodies.as_posix()})
    cmd = lane_argv(model, system, schema, extra)
    started, t0 = now(), time.perf_counter()
    if binary:
        # the prompt handed over as UTF-8 bytes: no line-end translation on the way to the CLI
        rb = subprocess.run(cmd, input=prompt.encode("utf-8"), capture_output=True, timeout=300,
                            cwd=chat._claude_cwd(), env=env)
        r = subprocess.CompletedProcess(cmd, rb.returncode, rb.stdout.decode("utf-8", "replace"),
                                        rb.stderr.decode("utf-8", "replace"))
    else:
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=300,
                           encoding="utf-8", cwd=chat._claude_cwd(), env=env)
    seconds = time.perf_counter() - t0
    (out_dir / "stdout.txt").write_text(r.stdout or "", encoding="utf-8")
    (out_dir / "stderr.txt").write_text(r.stderr or "", encoding="utf-8")
    envelope = None
    for line in reversed((r.stdout or "").splitlines()):
        line = line.strip()
        if line.startswith("{") and '"type"' in line and '"result"' in line:
            try:
                envelope = json.loads(line)
                break
            except ValueError:
                continue
    if envelope is None:
        try:
            envelope = json.loads(r.stdout)
        except ValueError:
            envelope = {}
    rec = {"probe": name, "started_at": started, "finished_at": now(), "seconds": round(seconds, 3),
           "returncode": r.returncode, "model": model, "flags": cmd[1:9] + list(extra),
           "extra_env": sorted((env_add or {}).keys()) + (["<request logging>"] if logged else []),
           "prompt_chars": len(prompt), "session_id": envelope.get("session_id"),
           "num_turns": envelope.get("num_turns"), "stop_reason": envelope.get("stop_reason"),
           "usage": {k: (envelope.get("usage") or {}).get(k) for k in
                     ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")},
           "modelUsage": {m: {k: v.get(k) for k in ("inputTokens", "outputTokens", "cacheCreationInputTokens",
                                                     "cacheReadInputTokens")}
                          for m, v in (envelope.get("modelUsage") or {}).items()},
           "duration_ms": envelope.get("duration_ms"), "duration_api_ms": envelope.get("duration_api_ms"),
           "result_chars": len(envelope.get("result") or "")}
    with (HERE / "calls_made.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(json.dumps(rec, ensure_ascii=False, indent=1))
    return rec


PROBES = {
    # the generator's call as the lane makes it, short documents, with the CLI's request logging on
    "answer_logged": lambda: call("answer_logged", orchestrator.GENERATOR_MODEL, ANSWER_PROMPT,
                                  system=GENERATOR_SYSTEM, schema=orchestrator._ANSWER_SCHEMA, logged=True),
    # a judge-shaped call: no system prompt, no schema, the judge model
    "judge_logged": lambda: call("judge_logged", "claude-haiku-4-5", JUDGE_PROMPT, logged=True),
    # the generator's call with the user's settings file left out of what the CLI loads
    "answer_no_user_settings": lambda: call("answer_no_user_settings", orchestrator.GENERATOR_MODEL,
                                            ANSWER_PROMPT, system=GENERATOR_SYSTEM,
                                            schema=orchestrator._ANSWER_SCHEMA,
                                            extra=("--setting-sources", "project,local"), logged=True),
    # the generator's call with the documented switch that skips the session-title request
    "answer_no_title": lambda: call("answer_no_title", orchestrator.GENERATOR_MODEL, ANSWER_PROMPT,
                                    system=GENERATOR_SYSTEM, schema=orchestrator._ANSWER_SCHEMA,
                                    env_add={"CLAUDE_CODE_DISABLE_TERMINAL_TITLE": "1"}),
}

if __name__ == "__main__":
    print(f"CLI: {chat.cli_version()} | exe {chat._CLAUDE_EXE} | cwd {chat._claude_cwd()}")
    print(f"answer prompt: {len(ANSWER_PROMPT)} chars (the made-up question and three corpus units)")
    for n in sys.argv[1:]:
        print(f"\n===== probe {n}")
        PROBES[n]()

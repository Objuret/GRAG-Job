"""The chat lane: every model call the repo makes goes through `post`, and the only backend is
the headless Claude CLI, subscription-billed. The hosted NIM lane was purged on 2026-09-07 at
his word ("NIM is dead, you can purge nim"); a model string that is not a claude-* slug is an
error here, never a silent fallthrough.

Also home to the per-thread transport timing every arm folds into its ModelUsage, and the
`.env` loader the graph driver and the arms use for NEO4J_PASSWORD.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from harness import abort

MAX_TRIES = 6

_completed = [0]
_completed_lock = threading.Lock()


def completed_calls() -> int:
    return _completed[0]


_call_timing = threading.local()


def reset_timing() -> None:
    _call_timing.attempts = 0
    _call_timing.request_s = 0.0
    _call_timing.wait_s = 0.0
    _call_timing.retry_s = 0.0


def take_timing() -> dict:
    out = {
        "attempts": getattr(_call_timing, "attempts", 0),
        "request_s": getattr(_call_timing, "request_s", 0.0),
        "wait_s": getattr(_call_timing, "wait_s", 0.0),
        "retry_s": getattr(_call_timing, "retry_s", 0.0),
    }
    reset_timing()
    return out


def _record_timing(attempts: int, request_s: float, wait_s: float, retry_s: float) -> None:
    _call_timing.attempts = getattr(_call_timing, "attempts", 0) + attempts
    _call_timing.request_s = getattr(_call_timing, "request_s", 0.0) + request_s
    _call_timing.wait_s = getattr(_call_timing, "wait_s", 0.0) + wait_s
    _call_timing.retry_s = getattr(_call_timing, "retry_s", 0.0) + retry_s


_dotenv_loaded = False


def _load_dotenv() -> None:
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    env = Path(__file__).parent.parent.parent / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.replace("export ", "").strip(),
                                  value.strip().strip('"').strip("'"))
    _dotenv_loaded = True


# ------------------------------------------------------------------ the claude CLI lane

def _resolve_claude_exe() -> str:
    """The claude binary to spawn. An npm install puts a `claude.cmd` shim on PATH; a .cmd runs
    through cmd.exe, which cuts an argument at its first newline — a multi-line `--system-prompt`
    arrives as its first line only (measured on Djuret 2026-09-18: the model saw one line of a
    30-line prompt and answered in markdown). The shim's own target is the native binary beside
    it; that is called directly, so argv reaches the CLI intact on both machines."""
    found = shutil.which("claude")
    if found and found.lower().endswith((".cmd", ".bat")):
        native = (Path(found).parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin"
                  / "claude.exe")
        if native.is_file():
            return str(native)
    return found or str(Path.home() / ".local" / "bin" / "claude.exe")


_CLAUDE_EXE = _resolve_claude_exe()
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")
_CLAUDE_CWD = Path(tempfile.gettempdir()) / "herb-claude-lane"
_EFFORT_LEVELS = frozenset({"low", "medium", "high", "xhigh", "max"})


def _claude_cwd() -> str:
    _CLAUDE_CWD.mkdir(parents=True, exist_ok=True)
    return str(_CLAUDE_CWD)


def join_stream(stdout: str) -> tuple:
    """(joined assistant text, the result event) from `--output-format stream-json`.

    The `json` envelope carries only `result`, which is the LAST assistant message. When an
    answer runs past one message the CLI continues in a further message and `result` holds only
    the tail, so a long JSON payload arrives beginning mid-object. This joins the `text` blocks
    of every assistant event, in order, which is the whole answer. Thinking blocks carry no
    `text` and are skipped."""
    parts, result = [], {}
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") == "assistant":
            for b in (d.get("message") or {}).get("content") or []:
                if b.get("type") == "text" and isinstance(b.get("text"), str):
                    parts.append(b["text"])
        elif d.get("type") == "result":
            result = d
    return "".join(parts), result


def _claude_chat(payload: dict, timeout: float, max_tries: int) -> dict:
    model = payload["model"]
    msgs = payload.get("messages") or []
    system = "\n\n".join(m.get("content", "") for m in msgs if m.get("role") == "system")
    prompt = "\n\n".join(m.get("content", "") for m in msgs if m.get("role") != "system")
    join_parts = bool(payload.get("join_parts"))
    cmd = [_CLAUDE_EXE, "-p", "--model", model, "--output-format",
           "stream-json" if join_parts else "json",
           "--tools", ""]                        # no tools: the model answers, it does not act (2026-09-29)
    if join_parts:
        cmd += ["--verbose"]                      # stream-json is refused headless without it
    effort = payload.get("effort")
    if effort:
        if effort not in _EFFORT_LEVELS:
            raise RuntimeError(
                f"chat.post: effort {effort!r} is not one of {sorted(_EFFORT_LEVELS)}")
        cmd += ["--effort", str(effort)]
    if system:
        cmd += ["--system-prompt", system]
    schema = ((payload.get("response_format") or {}).get("json_schema") or {}).get("schema")
    if schema:
        cmd += ["--json-schema", json.dumps(schema)]

    last = None
    request_s = retry_s = 0.0
    attempts = 0
    for attempt in range(max_tries):
        if abort.aborted():
            raise abort.Aborted("claude call skipped — abort requested (pressed q)")
        attempts += 1
        r0 = time.perf_counter()
        try:
            r = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                               timeout=timeout, encoding="utf-8", cwd=_claude_cwd(),
                               # the MemPalace plugin's user-wide hooks fire on headless calls
                               # too; this is its own documented switch: pass through, save
                               # nothing. Judge and tagger calls carry gold (2026-10-04).
                               env={**os.environ, "MEMPALACE_HOOKS_AUTO_SAVE": "false"})
        except subprocess.TimeoutExpired as err:
            retry_s += time.perf_counter() - r0
            last = err
        else:
            spent = time.perf_counter() - r0
            if r.returncode != 0:
                retry_s += spent
                last = RuntimeError(
                    f"claude exit {r.returncode}: {(r.stderr or r.stdout)[:200]}")
            else:
                try:
                    if join_parts:
                        joined, data = join_stream(r.stdout)
                        if not data:
                            raise ValueError("no result event in the stream")
                        data = dict(data)
                        data["result"] = joined
                    else:
                        data = json.loads(r.stdout)
                except ValueError as err:
                    retry_s += spent
                    last = RuntimeError(f"claude envelope not JSON: {err} — {r.stdout[:200]}")
                else:
                    result = _FENCE.sub("", (data.get("result") or "").strip())
                    usage = data.get("usage") or {}
                    _record_timing(attempts, request_s + spent, 0.0, retry_s)
                    with _completed_lock:
                        _completed[0] += 1
                    cached = int(usage.get("cache_read_input_tokens") or 0)
                    prompt_tokens = (int(usage.get("input_tokens") or 0)
                                     + int(usage.get("cache_creation_input_tokens") or 0)
                                     + cached)
                    return {
                        "choices": [{"message": {"content": result},
                                     "finish_reason": "stop"}],
                        "usage": {"prompt_tokens": prompt_tokens,
                                  "completion_tokens": int(usage.get("output_tokens") or 0),
                                  "cached_input_tokens": cached},
                        "num_turns": data.get("num_turns"),
                        "stop_reason": data.get("stop_reason"),
                    }
        if attempt < max_tries - 1:
            s0 = time.perf_counter()
            time.sleep(2 ** attempt)
            retry_s += time.perf_counter() - s0
    _record_timing(attempts, request_s, 0.0, retry_s)
    raise RuntimeError(f"claude {model} gave up after {max_tries} tries: {last!r}")


def post(path: str, payload: dict, timeout: float = 120.0, max_tries: int | None = None,
         give_up_after_s: float | None = None) -> dict:
    """One chat call. `path` is kept for the call sites' shape; only /chat/completions exists.
    The model must be a full claude-* slug; anything else is refused out loud."""
    model = str(payload.get("model", ""))
    if path != "/chat/completions":
        raise RuntimeError(f"chat.post: no backend serves {path!r}; only /chat/completions exists")
    if not model.startswith("claude"):
        raise RuntimeError(
            f"chat.post: model {model!r} has no backend — the hosted NIM lane was purged on "
            f"2026-09-07; pass a full claude-* slug (aliases like 'haiku' are refused too)")
    return _claude_chat(payload, timeout, MAX_TRIES if max_tries is None else max(1, int(max_tries)))

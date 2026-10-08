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
from harness import capture

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


_cli_version: list = []


def cli_version() -> str | None:
    """What `claude --version` prints, asked once per process."""
    if not _cli_version:
        try:
            r = subprocess.run([_CLAUDE_EXE, "--version"], capture_output=True, text=True,
                               timeout=30, encoding="utf-8", cwd=_claude_cwd())
            _cli_version.append((r.stdout or r.stderr or "").strip() or None)
        except (OSError, subprocess.SubprocessError):
            _cli_version.append(None)
    return _cli_version[0]


# The CLI runs under a config folder of its own and logs in with the token of the environment
# (.env). It then has no stored login to read the account's e-mail address from, which it
# otherwise writes in front of every prompt, and no settings file of the user's. Its own
# transcripts of the calls land under this folder; they hold gold.
_CONFIG_DIR = Path.home() / ".claude-herb-lane"
_LOGIN_TOKEN = "CLAUDE_CODE_OAUTH_TOKEN"
# without it the CLI deletes its transcripts after 30 days
_CONFIG_SETTINGS = {"cleanupPeriodDays": 36500}

# Set for the CLI on every call. Each switch was seen to do its work in a logged request
# (2026-10-08, docs/2026-10-08-model-calls-found-and-fixed.md).
_ENV_FIXED = {
    # the MemPalace plugin's user-wide hooks fire on headless calls too; this is its own
    # documented switch: pass through, save nothing. Judge and tagger calls carry gold (2026-10-04).
    "MEMPALACE_HOOKS_AUTO_SAVE": "false",
    "CLAUDE_CODE_DISABLE_TERMINAL_TITLE": "1",  # no second request, to Haiku, for a session title
    "CLAUDE_CODE_ATTRIBUTION_HEADER": "0",      # no billing line in front of the system prompt
    "CLAUDE_CONFIG_DIR": str(_CONFIG_DIR),
}
# The switches a call sets when it asks for them. One the call does not set is taken out of the
# CLI's environment, so a value left in the shell that starts the run never reaches a call.
_ENV_PER_CALL = ("CLAUDE_CODE_EFFORT_LEVEL", "MAX_THINKING_TOKENS",
                 "CLAUDE_CODE_MAX_OUTPUT_TOKENS", "CLAUDE_CODE_EXTRA_BODY")
# A temperature is sent only to a model on which it was tried and accepted, with thinking off.
# claude-sonnet-5 answers 400 to any temperature, with thinking on or off.
_TEMPERATURE_ACCEPTED = ("claude-haiku-4-5",)
_PAYLOAD_KEYS = ("model", "messages", "response_format", "effort", "join_parts", "thinking",
                 "chat_template_kwargs", "max_tokens", "temperature")
# What the CLI puts into a call by itself, with no switch in this lane: seen in logged requests
# of the version named here. The date makes a call's input differ from one day to the next.
_CLI_ADDS = {
    "seen_with": "2.1.212 (Claude Code)",
    "system_prompt_first": "You are a Claude agent, built on Anthropic's Claude Agent SDK.",
    "in_front_of_the_prompt": "a <system-reminder> block with the day's date",
}


def lane_info() -> dict:
    """The lane a run's calls went through, for its manifest."""
    return {"exe": _CLAUDE_EXE, "cli_version": cli_version(), "cwd": str(_CLAUDE_CWD),
            "fixed_flags": ["-p", "--tools", "", "--safe-mode"],
            "system_prompt": "always passed, empty when the call has no system text",
            "stdin": "the prompt as UTF-8 bytes",
            "env_set": dict(_ENV_FIXED),
            "login": f"{_LOGIN_TOKEN} of the environment (.env); a call is refused without it",
            "config_settings": dict(_CONFIG_SETTINGS),
            "env_per_call": list(_ENV_PER_CALL),
            "per_call": "effort, thinking, output cap, temperature: each call's applied / not_applied",
            "cli_adds": dict(_CLI_ADDS),
            "max_tries_default": MAX_TRIES}


def call_settings(payload: dict) -> dict:
    """The argv and the environment variables of one call, and which of the caller's settings they
    carry (`applied`) or cannot carry (`not_applied`, with the reason)."""
    model = payload["model"]
    msgs = payload.get("messages") or []
    system = "\n\n".join(m.get("content", "") for m in msgs if m.get("role") == "system")
    prompt = "\n\n".join(m.get("content", "") for m in msgs if m.get("role") != "system")
    join_parts = bool(payload.get("join_parts"))
    cmd = [_CLAUDE_EXE, "-p", "--model", model, "--output-format",
           "stream-json" if join_parts else "json",
           "--tools", "",                        # no tools: the model answers, it does not act (2026-09-29)
           "--safe-mode"]                        # no user CLAUDE.md, skills, plugins, hooks or MCP
                                                 # servers (2026-10-05); it does not skip settings.json
    if join_parts:
        cmd += ["--verbose"]                      # stream-json is refused headless without it
    env_set = dict(_ENV_FIXED)
    applied, not_applied = {}, {}

    effort = payload.get("effort")
    if effort:
        if effort not in _EFFORT_LEVELS:
            raise RuntimeError(
                f"chat.post: effort {effort!r} is not one of {sorted(_EFFORT_LEVELS)}")
        cmd += ["--effort", str(effort)]
    else:
        # the caller names none, so none is sent: without this the CLI takes `effortLevel` from
        # the user's own settings.json (it was `medium` on every answer call of 2026-10-07)
        env_set["CLAUDE_CODE_EFFORT_LEVEL"] = "auto"
    applied["effort"] = effort or "none sent (the model's own default)"
    flags = cmd[1:]

    # an empty system text is passed too: without the flag the CLI sends its own system prompt
    cmd += ["--system-prompt", system]
    schema = ((payload.get("response_format") or {}).get("json_schema") or {}).get("schema")
    if schema:
        cmd += ["--json-schema", json.dumps(schema)]

    thinking_off = (payload.get("thinking") is False
                    or (payload.get("chat_template_kwargs") or {}).get("enable_thinking") is False)
    if thinking_off:
        env_set["MAX_THINKING_TOKENS"] = "0"
        applied["thinking"] = "off"
        if payload.get("max_tokens"):
            env_set["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(int(payload["max_tokens"]))
            applied["max_output_tokens"] = int(payload["max_tokens"])
        if payload.get("temperature") is not None:
            if model.startswith(_TEMPERATURE_ACCEPTED):
                env_set["CLAUDE_CODE_EXTRA_BODY"] = json.dumps({"temperature": payload["temperature"]})
                applied["temperature"] = payload["temperature"]
            else:
                not_applied["temperature"] = (f"{model} refuses a temperature; it is sent only to "
                                              f"{', '.join(_TEMPERATURE_ACCEPTED)}")
    else:
        applied["thinking"] = "the model decides"
        # with thinking on the API takes no temperature but 1, and a cap would count the thinking
        for key in ("max_tokens", "temperature"):
            if payload.get(key) is not None:
                not_applied[key] = "sent only on a call that asks for thinking off"
    for key in payload:
        if key not in _PAYLOAD_KEYS:
            not_applied[key] = "no such setting in this lane"
    return {"cmd": cmd, "flags": flags, "system": system, "prompt": prompt, "schema": schema,
            "join_parts": join_parts, "effort": effort, "env_set": env_set,
            "env_unset": [k for k in _ENV_PER_CALL if k not in env_set],
            "applied": applied, "not_applied": not_applied}


def _call_env(call: dict) -> dict:
    """The environment the CLI is started in for one call."""
    env = {k: v for k, v in os.environ.items() if k.upper() not in call["env_unset"]}
    env.update(call["env_set"])
    return env


def _login() -> None:
    """The token is there and the CLI's own config folder is made, or the call is refused."""
    _load_dotenv()
    if not os.environ.get(_LOGIN_TOKEN):
        raise RuntimeError(
            f"chat.post: no {_LOGIN_TOKEN} in the environment or in .env. The lane logs in with "
            f"it under its own config folder ({_CONFIG_DIR}); `claude setup-token` makes one")
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    settings = _CONFIG_DIR / "settings.json"
    if not settings.is_file():
        settings.write_text(json.dumps(_CONFIG_SETTINGS, indent=2), encoding="utf-8")


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
    _login()
    call = call_settings(payload)
    cmd, flags, system, prompt = call["cmd"], call["flags"], call["system"], call["prompt"]
    schema, join_parts, effort = call["schema"], call["join_parts"], call["effort"]

    # The whole call is kept: what was sent, every try, and all the CLI reported back. It goes
    # to the open capture of the question or evaluation cell and rides back under "call"
    # (2026-10-08: "i NEVER want to run this again").
    rec = {"kind": "chat", "model": model, "exe": _CLAUDE_EXE, "flags": flags,
           "system": system, "schema": schema, "prompt": prompt, "effort": effort,
           "join_parts": join_parts, "cwd": _claude_cwd(), "timeout_s": timeout,
           "max_tries": max_tries,
           "env_set": call["env_set"], "env_unset": call["env_unset"],
           "applied": call["applied"], "not_applied": call["not_applied"],
           "payload_dropped": sorted(call["not_applied"]),
           "started_at": capture.now(), "finished_at": None, "attempts": [], "ok": False,
           "text": None, "usage": None, "envelope": None, "stream": None,
           "stderr": None, "error": None}

    last = None
    request_s = retry_s = 0.0
    attempts = 0
    for attempt in range(max_tries):
        if abort.aborted():
            rec.update(finished_at=capture.now(), error="aborted before the try")
            capture.record(rec)
            raise abort.Aborted("claude call skipped — abort requested (pressed q)")
        attempts += 1
        tried = {"n": attempts, "started_at": capture.now(), "seconds": None, "outcome": None,
                 "returncode": None, "error": None, "stdout": None, "stderr": None}
        rec["attempts"].append(tried)
        r0 = time.perf_counter()
        try:
            # the prompt goes over as bytes: in text mode Windows turns every line end into
            # CR LF on the way, and the prompt kept in the record is then not what was sent
            r = subprocess.run(cmd, input=prompt.encode("utf-8"), capture_output=True,
                               timeout=timeout, cwd=_claude_cwd(), env=_call_env(call))
        except subprocess.TimeoutExpired as err:
            retry_s += time.perf_counter() - r0
            last = err
            tried.update(seconds=time.perf_counter() - r0, outcome="timeout", error=repr(err),
                         stdout=_text(err.stdout), stderr=_text(err.stderr))
        else:
            spent = time.perf_counter() - r0
            out, errtext = _text(r.stdout) or "", _text(r.stderr) or ""
            tried.update(seconds=spent, returncode=r.returncode)
            if r.returncode != 0:
                retry_s += spent
                last = RuntimeError(
                    f"claude exit {r.returncode}: {(errtext or out)[:200]}")
                tried.update(outcome="exit", error=repr(last), stdout=out, stderr=errtext)
            else:
                try:
                    if join_parts:
                        joined, data = join_stream(out)
                        if not data:
                            raise ValueError("no result event in the stream")
                        data = dict(data)
                        data["result"] = joined
                    else:
                        data = json.loads(out)
                except ValueError as err:
                    retry_s += spent
                    last = RuntimeError(f"claude envelope not JSON: {err} — {out[:200]}")
                    tried.update(outcome="bad_envelope", error=repr(last), stdout=out,
                                 stderr=errtext)
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
                    kept = {"prompt_tokens": prompt_tokens,
                            "completion_tokens": int(usage.get("output_tokens") or 0),
                            "cached_input_tokens": cached}
                    tried.update(outcome="ok")
                    rec.update(finished_at=capture.now(), ok=True, text=result, usage=kept,
                               envelope=data,
                               stream=out if join_parts else None, stderr=errtext)
                    capture.record(rec)
                    return {
                        "choices": [{"message": {"content": result},
                                     "finish_reason": "stop"}],
                        "usage": kept,
                        "num_turns": data.get("num_turns"),
                        "stop_reason": data.get("stop_reason"),
                        "call": rec,
                    }
        if attempt < max_tries - 1:
            s0 = time.perf_counter()
            time.sleep(2 ** attempt)
            retry_s += time.perf_counter() - s0
            tried["backoff_s"] = time.perf_counter() - s0
    _record_timing(attempts, request_s, 0.0, retry_s)
    rec.update(finished_at=capture.now(), error=repr(last))
    capture.record(rec)
    raise RuntimeError(f"claude {model} gave up after {max_tries} tries: {last!r}")


def _text(raw) -> str | None:
    if raw is None:
        return None
    return raw if isinstance(raw, str) else raw.decode("utf-8", "replace")


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

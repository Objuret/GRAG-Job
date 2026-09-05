from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import httpx

from harness import abort
BASE_URL = "https://integrate.api.nvidia.com/v1"

SECONDS_BETWEEN_CALLS = max(
    1.5, float(os.environ.get("NIM_SECONDS_BETWEEN_CALLS", "3.0")))

MAX_TRIES = 6
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
GIVE_UP_AFTER_S = 300.0
MAX_DEGRADED_RETRIES = 2

_pace_lock = threading.Lock()
_next_call_at: dict = defaultdict(float)
_completed = [0]

_key_pool: list | None = None
_bind_lock = threading.Lock()
_bound = threading.local()
_next_bind = [os.getpid()]


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


def _wait_my_turn(model: str = "", key_idx: int = 0) -> None:
    if abort.aborted():
        raise abort.Aborted("NIM call skipped — abort requested (pressed q)")
    with _pace_lock:
        now = time.monotonic()
        start_at = max(now, _next_call_at[(key_idx, model)])
        _next_call_at[(key_idx, model)] = start_at + SECONDS_BETWEEN_CALLS
    if start_at > now:
        time.sleep(start_at - now)


def _back_off(seconds: float, model: str = "", key_idx: int = 0) -> None:
    with _pace_lock:
        _next_call_at[(key_idx, model)] = max(
            _next_call_at[(key_idx, model)], time.monotonic() + seconds)


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


def require_key() -> str:
    return _keys()[0]


def _keys() -> list:
    global _key_pool
    if _key_pool is None:
        _load_dotenv()
        pool = []
        primary = os.environ.get("NVIDIA_API_KEY")
        if primary:
            pool.append(primary)
        for name in sorted(k for k in os.environ if k.startswith("NVIDIA_API_KEY_WORKER_")):
            if os.environ[name]:
                pool.append(os.environ[name])
        if not pool:
            raise RuntimeError("NVIDIA_API_KEY not set — NIM access needs it.")
        _key_pool = pool
    return _key_pool


def _thread_key() -> tuple:
    pool = _keys()
    idx = getattr(_bound, "idx", None)
    if idx is None or idx >= len(pool):
        with _bind_lock:
            idx = _next_bind[0] % len(pool)
            _next_bind[0] += 1
        _bound.idx = idx
    return idx, pool[idx]


_CLAUDE_EXE = shutil.which("claude") or str(Path.home() / ".local" / "bin" / "claude.exe")
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")

_CLAUDE_CWD = Path(tempfile.gettempdir()) / "herb-claude-lane"


def _claude_cwd() -> str:
    _CLAUDE_CWD.mkdir(parents=True, exist_ok=True)
    return str(_CLAUDE_CWD)


def _claude_chat(payload: dict, timeout: float, max_tries: int) -> dict:
    model = payload["model"]
    msgs = payload.get("messages") or []
    system = "\n\n".join(m.get("content", "") for m in msgs if m.get("role") == "system")
    prompt = "\n\n".join(m.get("content", "") for m in msgs if m.get("role") != "system")
    cmd = [_CLAUDE_EXE, "-p", "--model", model, "--output-format", "json"]
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
                               timeout=timeout, encoding="utf-8", cwd=_claude_cwd())
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
                    data = json.loads(r.stdout)
                except ValueError as err:
                    retry_s += spent
                    last = RuntimeError(f"claude envelope not JSON: {err} — {r.stdout[:200]}")
                else:
                    result = _FENCE.sub("", (data.get("result") or "").strip())
                    usage = data.get("usage") or {}
                    _record_timing(attempts, request_s + spent, 0.0, retry_s)
                    with _pace_lock:
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
                    }
        if attempt < max_tries - 1:
            s0 = time.perf_counter()
            time.sleep(2 ** attempt)
            retry_s += time.perf_counter() - s0
    _record_timing(attempts, request_s, 0.0, retry_s)
    raise RuntimeError(f"claude {model} gave up after {max_tries} tries: {last!r}")


def _delay_after(response: httpx.Response, attempt: int) -> float:
    header = response.headers.get("Retry-After", "").strip()
    if header.isdigit():
        return float(header)
    if header:
        from email.utils import parsedate_to_datetime
        try:
            return max(0.0, (parsedate_to_datetime(header)
                             - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError):
            pass
    return float(2 ** attempt)


def post(path: str, payload: dict, timeout: float = 120.0, max_tries: int | None = None,
         give_up_after_s: float | None = None) -> dict:
    if path == "/chat/completions" and str(payload.get("model", "")).startswith("claude"):
        return _claude_chat(payload, timeout,
                            MAX_TRIES if max_tries is None else max(1, int(max_tries)))
    key_idx, key = _thread_key()
    headers = {"Authorization": f"Bearer {key}"}
    model = payload.get("model", "")
    started = time.monotonic()
    last = None
    degraded_tries = 0
    request_s = wait_s = retry_s = 0.0
    attempts = 0
    max_tries = MAX_TRIES if max_tries is None else max(1, int(max_tries))
    give_up_after_s = GIVE_UP_AFTER_S if give_up_after_s is None else float(give_up_after_s)
    for attempt in range(max_tries):
        w0 = time.perf_counter()
        _wait_my_turn(model, key_idx)
        waited = time.perf_counter() - w0
        if attempt == 0:
            wait_s += waited
        else:
            retry_s += waited
        attempts += 1
        r0 = time.perf_counter()
        try:
            response = httpx.post(f"{BASE_URL}{path}", json=payload,
                                  headers=headers, timeout=timeout)
        except httpx.TransportError as err:
            retry_s += time.perf_counter() - r0
            last, delay = err, float(2 ** attempt)
        else:
            spent = time.perf_counter() - r0
            if response.status_code < 400:
                _record_timing(attempts, request_s + spent, wait_s, retry_s)
                with _pace_lock:
                    _completed[0] += 1
                return response.json()
            retry_s += spent
            degraded = (response.status_code == 400
                        and "DEGRADED function cannot be invoked" in response.text)
            if degraded and degraded_tries < MAX_DEGRADED_RETRIES:
                degraded_tries += 1
                last, delay = response, 3.0
            elif response.status_code not in RETRYABLE_STATUS:
                _record_timing(attempts, request_s, wait_s, retry_s)
                response.raise_for_status()
            else:
                last, delay = response, _delay_after(response, attempt)

        out_of_tries = attempt == max_tries - 1
        if out_of_tries or time.monotonic() - started + delay >= give_up_after_s:
            break
        _back_off(delay, model, key_idx)

    _record_timing(attempts, request_s, wait_s, retry_s)
    detail = (f"{last.status_code} {last.text[:200]}"
              if isinstance(last, httpx.Response) else repr(last))
    raise RuntimeError(f"NIM {path} gave up after {attempt + 1} tries / "
                       f"{time.monotonic() - started:.0f}s: {detail}")


if __name__ == "__main__":
    real_post, real_sleep, real_mono = httpx.post, time.sleep, time.monotonic
    real_gap = SECONDS_BETWEEN_CALLS
    os.environ.setdefault("NVIDIA_API_KEY", "x")
    _key_pool = ["x"]

    httpx.post = lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not call"))
    abort._flag.set()
    try:
        post("/x", {})
        raise AssertionError("aborted post should raise")
    except abort.Aborted:
        pass
    finally:
        abort._flag.clear()
    httpx.post = real_post

    SECONDS_BETWEEN_CALLS = 0.0
    time.sleep = lambda s: None

    def _tries_until_giveup(make_outcome):
        tries = {"n": 0}

        def fake_post(url, json, headers, timeout):
            tries["n"] += 1
            return make_outcome()

        httpx.post = fake_post
        try:
            post("/x", {})
        except RuntimeError as e:
            assert f"{MAX_TRIES} tries" in str(e), e
            return tries["n"]
        raise AssertionError("expected RuntimeError after retries")

    assert _tries_until_giveup(lambda: httpx.Response(503, text="busy")) == MAX_TRIES

    def _flap():
        raise httpx.ConnectError("down")

    assert _tries_until_giveup(_flap) == MAX_TRIES

    SECONDS_BETWEEN_CALLS, _next_call_at[(0, "")] = 0.0, 0.0
    clk, slept = {"t": 0.0}, []
    time.monotonic = lambda: clk["t"]

    def _adv(s):
        slept.append(s)
        clk["t"] += s

    time.sleep = _adv
    httpx.post = lambda url, json, headers, timeout: httpx.Response(
        429, headers={"Retry-After": "7"})
    try:
        post("/x", {})
    except RuntimeError:
        pass
    assert slept and all(s == 7 for s in slept), slept
    time.monotonic = real_mono

    _next_call_at[(0, "")] = 0.0
    base = 1000.0
    time.monotonic = lambda: base
    _back_off(30.0)
    assert _next_call_at[(0, "")] >= base + 30, _next_call_at[(0, "")]
    time.monotonic = real_mono

    time.sleep = lambda s: None
    deg = {"n": 0}

    def _degraded(url, json, headers, timeout):
        deg["n"] += 1
        return httpx.Response(400, text='{"detail": "DEGRADED function cannot be invoked"}',
                              request=httpx.Request("POST", url))

    httpx.post = _degraded
    try:
        post("/x", {})
        raise AssertionError("expected raise on sustained DEGRADED")
    except httpx.HTTPStatusError:
        pass
    assert deg["n"] == MAX_DEGRADED_RETRIES + 1, deg["n"]
    httpx.post = lambda url, json, headers, timeout: httpx.Response(
        400, text="bad request", request=httpx.Request("POST", url))
    try:
        post("/x", {})
        raise AssertionError("plain 400 should raise immediately")
    except httpx.HTTPStatusError:
        pass

    SECONDS_BETWEEN_CALLS, _next_call_at[(0, "")] = 5.0, 0.0
    clock, waits = {"t": 100.0}, []
    time.monotonic = lambda: clock["t"]

    def _advance(s):
        waits.append(s)
        clock["t"] += s

    time.sleep = _advance
    _wait_my_turn()
    assert waits == [], waits
    _wait_my_turn(); _wait_my_turn()
    assert waits == [5.0, 5.0], waits

    httpx.post, time.sleep, time.monotonic = real_post, real_sleep, real_mono
    SECONDS_BETWEEN_CALLS, _next_call_at[(0, "")] = 0.2, real_mono()
    fired = []

    def _fire():
        _wait_my_turn()
        fired.append(real_mono())

    threads = [threading.Thread(target=_fire) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    fired.sort()
    gaps = [b - a for a, b in zip(fired, fired[1:])]
    assert len(fired) == 5 and all(g >= 0.8 * SECONDS_BETWEEN_CALLS for g in gaps), gaps

    httpx.post, time.sleep, time.monotonic = real_post, real_sleep, real_mono
    SECONDS_BETWEEN_CALLS, _next_call_at[(0, "")] = real_gap, 0.0
    print("nim self-check OK")

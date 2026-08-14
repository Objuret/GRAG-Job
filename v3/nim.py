"""Talk to NVIDIA NIM's REST API (OpenAI-compatible).

The generator and the embedder both send their requests through here. This module
holds the API keys and POSTs with retries, while a per-(key, model) pacer keeps each
account's callers of each model under NIM's rate limit. httpx instead of the openai
SDK — same endpoints, one fewer dependency.

NIM's limits are per ACCOUNT, so extra accounts are extra lanes: the key pool is
`NVIDIA_API_KEY` (primary) plus every `NVIDIA_API_KEY_WORKER_*`, and each worker
thread binds to one key round-robin — 3 keys and 3 workers means three questions
genuinely in flight at once. The round-robin start is PID-offset so two processes
launched side by side tend to claim different accounts first (a tendency, not a
guarantee — the hard guarantee is within one process).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import httpx

import abort

BASE_URL = "https://integrate.api.nvidia.com/v1"

# Wait at least this long between calls, so requests go out evenly spaced — a sudden
# burst is what trips NIM's own limit into 429s. 5s is ~12 calls/min, well under NIM's
# 40/min. Set NIM_SECONDS_BETWEEN_CALLS to change the pace without editing code; the
# 1.5s floor is that 40/min ceiling (below it NIM 429s), so the override can slow the
# pace but not push past the floor.
SECONDS_BETWEEN_CALLS = max(
    1.5, float(os.environ.get("NIM_SECONDS_BETWEEN_CALLS", "3.0")))

# Retry a failing call this many times before giving up.
MAX_TRIES = 6
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
# A call's retries share one backoff budget: once the accumulated wait would pass
# this, give up rather than sleep again. Bounds the case where NIM keeps asking for
# long Retry-After waits. (A hung connection is bounded separately, by the per-try
# httpx timeout.)
GIVE_UP_AFTER_S = 300.0
# NIM answers 400 "DEGRADED function cannot be invoked" when a model is transiently
# down. Retry it a couple times (a brief blip self-heals), then fail fast — a sustained
# outage must not grind, since a judge metric can fan out to one call per retrieved
# context. The eval's circuit breaker stops the whole run if it persists.
MAX_DEGRADED_RETRIES = 2

_pace_lock = threading.Lock()
_next_call_at: dict = defaultdict(float)  # per (key_idx, model): monotonic time of that lane's next allowed call
_completed = [0]  # successful calls so far; a liveness counter for progress displays

_key_pool: list | None = None  # loaded lazily; primary key first, then WORKER_* sorted
_bind_lock = threading.Lock()
_bound = threading.local()     # each thread's key index, assigned round-robin on first call
_next_bind = [os.getpid()]     # PID offset decorrelates side-by-side processes


def completed_calls() -> int:
    """Count of successful NIM calls — a live heartbeat for a progress bar, since one
    metric can fan out to ~k calls before its cell lands."""
    return _completed[0]


# Per-thread transport accounting. A call's wall time is three different things —
# standing in the pacer queue, the request itself, and the cost of failures — and
# only the middle one is the model's own latency. Collapsed into one number they
# are unseparable, and the first is a function of --workers and lane congestion,
# so it makes runs at different concurrency incomparable. A caller brackets its
# work with reset_timing()/take_timing() and records the parts beside the total.
_call_timing = threading.local()


def reset_timing() -> None:
    """Zero this thread's transport accounting."""
    _call_timing.attempts = 0
    _call_timing.request_s = 0.0
    _call_timing.wait_s = 0.0
    _call_timing.retry_s = 0.0


def take_timing() -> dict:
    """This thread's transport accounting since its last reset, and zero it.
    `attempts` counts every try; `request_s` is time inside the request that
    succeeded — the model's own latency; `wait_s` is pacer queueing before the
    first try; `retry_s` is every failed try and the waiting its backoff caused."""
    out = {
        "attempts": getattr(_call_timing, "attempts", 0),
        "request_s": getattr(_call_timing, "request_s", 0.0),
        "wait_s": getattr(_call_timing, "wait_s", 0.0),
        "retry_s": getattr(_call_timing, "retry_s", 0.0),
    }
    reset_timing()
    return out


def _record_timing(attempts: int, request_s: float, wait_s: float, retry_s: float) -> None:
    """Add one call's parts to this thread's running totals — a caller that makes
    several calls (an embedding batch, a multi-pass interpret) accumulates them."""
    _call_timing.attempts = getattr(_call_timing, "attempts", 0) + attempts
    _call_timing.request_s = getattr(_call_timing, "request_s", 0.0) + request_s
    _call_timing.wait_s = getattr(_call_timing, "wait_s", 0.0) + wait_s
    _call_timing.retry_s = getattr(_call_timing, "retry_s", 0.0) + retry_s


def _wait_my_turn(model: str = "", key_idx: int = 0) -> None:
    """Block until this (key, model) lane's next call is allowed, leaving
    SECONDS_BETWEEN_CALLS between calls on THE SAME ACCOUNT TO THE SAME MODEL across
    all threads. NIM rate-limits per account per model, so each lane paces on its own
    clock: callers on different keys or different models run in parallel and never
    throttle each other. A caller claims its lane's next free slot under the lock,
    then sleeps until it — so calls on a lane queue evenly, no burst.

    A 'q' press unwinds the worker here before it waits, so an in-flight worker stops at
    the next call boundary rather than at the end of a fan-out."""
    if abort.aborted():
        raise abort.Aborted("NIM call skipped — abort requested (pressed q)")
    with _pace_lock:
        now = time.monotonic()
        start_at = max(now, _next_call_at[(key_idx, model)])
        _next_call_at[(key_idx, model)] = start_at + SECONDS_BETWEEN_CALLS
    if start_at > now:
        time.sleep(start_at - now)


def _back_off(seconds: float, model: str = "", key_idx: int = 0) -> None:
    """Push one (key, model) lane's next-call time out so every worker on THAT lane
    waits. A 429 means that account is over its limit for that model; backing off the
    lane's clock gives every caller of it the same self-throttle, while other lanes
    keep running unaffected."""
    with _pace_lock:
        _next_call_at[(key_idx, model)] = max(
            _next_call_at[(key_idx, model)], time.monotonic() + seconds)


_dotenv_loaded = False


def _load_dotenv() -> None:
    """Read KEY=VALUE lines from a sibling .env into the environment, once, without
    overwriting anything already set. Saves a python-dotenv dependency."""
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    env = Path(__file__).parent / ".env"
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
    """The primary NIM API key, or a loud failure — there is no offline mode."""
    return _keys()[0]


def _keys() -> list:
    """The key pool: NVIDIA_API_KEY first, then every NVIDIA_API_KEY_WORKER_* in
    name order. Loaded once; fails loud when no key is set at all."""
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
    """(key_idx, key) for the calling thread — bound round-robin on first use and
    kept for the thread's lifetime, so a worker stays in its own account lane."""
    pool = _keys()
    idx = getattr(_bound, "idx", None)
    if idx is None or idx >= len(pool):
        with _bind_lock:
            idx = _next_bind[0] % len(pool)
            _next_bind[0] += 1
        _bound.idx = idx
    return idx, pool[idx]


# --- claude lane (headless Claude Code CLI) ----------------------------------
# `claude-*` chat models run through the signed-in claude CLI instead of NIM — ONE
# lane shared by every caller (generator, interpreter, judge), so a transport fix
# lands everywhere at once. Subscription-billed. The caller's response_format
# schema rides `--json-schema` (enforced structured output); the prompt goes via
# stdin because a k=50 prompt outsizes the Windows command line. No temperature
# control exists on the CLI — claude answers are not bit-reproducible.

_CLAUDE_EXE = shutil.which("claude") or str(Path.home() / ".local" / "bin" / "claude.exe")
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


def _claude_chat(payload: dict, timeout: float, max_tries: int) -> dict:
    """One /chat/completions-shaped call on the claude CLI -> an OpenAI-shaped
    response dict ({choices, usage}), so call sites read it exactly like a NIM
    reply. NIM-only knobs in the payload (temperature, max/min_tokens,
    chat_template_kwargs) have no CLI equivalent and are dropped."""
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
    # This lane has no pacer — the CLI's own account limits govern — so wait_s is
    # structurally zero here, and recording it says so rather than leaving the two
    # backends silently different shapes.
    request_s = retry_s = 0.0
    attempts = 0
    for attempt in range(max_tries):
        if abort.aborted():
            raise abort.Aborted("claude call skipped — abort requested (pressed q)")
        attempts += 1
        r0 = time.perf_counter()
        try:
            r = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                               timeout=timeout, encoding="utf-8")
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
                    # The CLI splits input three ways — fresh, cache-write and
                    # cache-read — and `input_tokens` alone is only the fresh part,
                    # which for a prompt carrying retrieved contexts is a rounding
                    # error against the whole. prompt_tokens is the sum, so a call
                    # site reads the input it actually sent; the cache-read share
                    # rides alongside, since that is the part billed differently.
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
    _record_timing(attempts, request_s, 0.0, retry_s)  # a run that gave up still paid
    raise RuntimeError(f"claude {model} gave up after {max_tries} tries: {last!r}")


def _delay_after(response: httpx.Response, attempt: int) -> float:
    """How long to wait before retrying: obey NIM's Retry-After header if it sent
    one (plain seconds or an HTTP date), otherwise back off exponentially."""
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
    """POST payload to BASE_URL + path and return the parsed JSON body.

    Retries transient HTTP statuses (408/429/5xx) and network errors up to MAX_TRIES,
    or until GIVE_UP_AFTER_S has passed — whichever comes first — then raises loud.
    Every try waits its turn at the shared pacer first (NIM bills retries too), and a
    'q' press unwinds the wait (see _wait_my_turn).

    `claude-*` chat models route to the claude lane (see _claude_chat) — no NIM key,
    no pacer; the CLI's own account limits govern."""
    if path == "/chat/completions" and str(payload.get("model", "")).startswith("claude"):
        return _claude_chat(payload, timeout,
                            MAX_TRIES if max_tries is None else max(1, int(max_tries)))
    key_idx, key = _thread_key()  # the thread's own account lane
    headers = {"Authorization": f"Bearer {key}"}
    model = payload.get("model", "")  # rate limits are per account per model — pace the lane
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
        # queueing before the first try is this lane's own pacing; on a later try it
        # is the backoff a previous failure pushed onto the lane, so it is retry cost
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
        except httpx.TransportError as err:  # connect/read/protocol blip — retry
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
                last, delay = response, 3.0  # transient model blip — a few quick retries
            elif response.status_code not in RETRYABLE_STATUS:
                # real 4xx (or DEGRADED past its cap) — fail fast, but the tries it
                # already spent were billed and are recorded before the raise
                _record_timing(attempts, request_s, wait_s, retry_s)
                response.raise_for_status()
            else:
                last, delay = response, _delay_after(response, attempt)

        out_of_tries = attempt == max_tries - 1
        if out_of_tries or time.monotonic() - started + delay >= give_up_after_s:
            break
        _back_off(delay, model, key_idx)  # this lane's next _wait_my_turn (every caller of it)
        #                                   waits; other keys and models are unaffected

    _record_timing(attempts, request_s, wait_s, retry_s)  # a run that gave up still paid
    detail = (f"{last.status_code} {last.text[:200]}"
              if isinstance(last, httpx.Response) else repr(last))
    raise RuntimeError(f"NIM {path} gave up after {attempt + 1} tries / "
                       f"{time.monotonic() - started:.0f}s: {detail}")


if __name__ == "__main__":
    # Self-check — no network. The retry blocks monkeypatch httpx.post/sleep/clock;
    # the final block uses real threads and the real clock but makes no network call.
    real_post, real_sleep, real_mono = httpx.post, time.sleep, time.monotonic
    real_gap = SECONDS_BETWEEN_CALLS
    os.environ.setdefault("NVIDIA_API_KEY", "x")
    _key_pool = ["x"]  # pin the pool so a populated .env cannot spread the self-check threads

    # Abort: a set flag makes post() raise before it ever touches the network, so an
    # in-flight worker unwinds at the next call instead of finishing the fan-out.
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

    # Retries: a retryable failure exhausts every try, then raises loud.
    SECONDS_BETWEEN_CALLS = 0.0  # pacing is checked on its own below
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

    def _flap():  # a transport error must retry, not abort
        raise httpx.ConnectError("down")

    assert _tries_until_giveup(_flap) == MAX_TRIES

    # Retry-After drives the model's backoff: a 429's header pushes that model's next-call
    # time out, so the wait is enforced by the pacer (reaching every caller of the model),
    # not by a per-thread sleep. A fake clock that advances on each sleep keeps it
    # deterministic; with one caller each wait still equals the header.
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
    assert slept and all(s == 7 for s in slept), slept  # every wait == the header
    time.monotonic = real_mono

    # A model's backoff is shared across its callers: a 429 one caller of a model sees
    # delays that model's next-call time, so another worker on the SAME model is pushed
    # out too (a per-thread sleep would let them keep hammering one model).
    _next_call_at[(0, "")] = 0.0
    base = 1000.0
    time.monotonic = lambda: base
    _back_off(30.0)
    assert _next_call_at[(0, "")] >= base + 30, _next_call_at[(0, "")]
    time.monotonic = real_mono

    # DEGRADED 400 (NIM's transient model-down signal): retried MAX_DEGRADED_RETRIES
    # times then raised; a plain 400 raises at once (non-retryable).
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

    # Pacing math (fake clock, so the test itself never waits): back-to-back calls
    # are spaced exactly SECONDS_BETWEEN_CALLS apart.
    SECONDS_BETWEEN_CALLS, _next_call_at[(0, "")] = 5.0, 0.0
    clock, waits = {"t": 100.0}, []
    time.monotonic = lambda: clock["t"]

    def _advance(s):
        waits.append(s)
        clock["t"] += s

    time.sleep = _advance
    _wait_my_turn()                       # first call: clear, no wait
    assert waits == [], waits
    _wait_my_turn(); _wait_my_turn()      # next two: one gap each
    assert waits == [5.0, 5.0], waits

    # Pacing under concurrency (real threads): calls firing at once still come out
    # spaced, because each reserves the next slot under the lock. Checking the gap
    # between consecutive calls (not just total time) is what would catch a pacer
    # that serialized them behind one sleep and then let the rest burst.
    httpx.post, time.sleep, time.monotonic = real_post, real_sleep, real_mono
    SECONDS_BETWEEN_CALLS, _next_call_at[(0, "")] = 0.2, real_mono()
    fired = []

    def _fire():
        _wait_my_turn()
        fired.append(real_mono())  # list.append is atomic under the GIL

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

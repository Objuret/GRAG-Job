"""Talk to NVIDIA NIM's REST API (OpenAI-compatible).

The generator and the embedder both send their requests through here. This module
holds the API key and POSTs with retries, while a per-model pacer keeps callers of each
model under NIM's per-model rate limit. httpx instead of the openai SDK — same endpoints,
one fewer dependency.
"""
from __future__ import annotations

import os
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
_next_call_at: dict = defaultdict(float)  # per-model: monotonic time that model's next call may start
_completed = [0]  # successful calls so far; a liveness counter for progress displays


def completed_calls() -> int:
    """Count of successful NIM calls — a live heartbeat for a progress bar, since one
    metric can fan out to ~k calls before its cell lands."""
    return _completed[0]


def _wait_my_turn(model: str = "") -> None:
    """Block until this model's next call is allowed, leaving SECONDS_BETWEEN_CALLS
    between calls TO THE SAME MODEL across all threads. NIM's rate limit is per-model, so
    each model paces on its own clock: concurrent callers on different models run in
    parallel and one model never throttles another. A caller claims its model's next free
    slot under the lock, then sleeps until it — so calls to a model queue evenly, no burst.

    A 'q' press unwinds the worker here before it waits, so an in-flight worker stops at
    the next call boundary rather than at the end of a fan-out."""
    if abort.aborted():
        raise abort.Aborted("NIM call skipped — abort requested (pressed q)")
    with _pace_lock:
        now = time.monotonic()
        start_at = max(now, _next_call_at[model])
        _next_call_at[model] = start_at + SECONDS_BETWEEN_CALLS
    if start_at > now:
        time.sleep(start_at - now)


def _back_off(seconds: float, model: str = "") -> None:
    """Push a model's next-call time out so every worker on THAT model waits. A 429 means
    that model is over its own rate limit; backing off its clock gives every caller of it
    the same self-throttle, while callers of other models keep running unaffected."""
    with _pace_lock:
        _next_call_at[model] = max(_next_call_at[model], time.monotonic() + seconds)


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
    """The NIM API key, or a loud failure — there is no offline mode."""
    _load_dotenv()
    key = os.environ.get("NVIDIA_API_KEY")
    if not key:
        raise RuntimeError("NVIDIA_API_KEY not set — NIM access needs it.")
    return key


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
    'q' press unwinds the wait (see _wait_my_turn)."""
    headers = {"Authorization": f"Bearer {require_key()}"}
    model = payload.get("model", "")  # NIM rate-limits per model — pace on the model's own clock
    started = time.monotonic()
    last = None
    degraded_tries = 0
    max_tries = MAX_TRIES if max_tries is None else max(1, int(max_tries))
    give_up_after_s = GIVE_UP_AFTER_S if give_up_after_s is None else float(give_up_after_s)
    for attempt in range(max_tries):
        _wait_my_turn(model)
        try:
            response = httpx.post(f"{BASE_URL}{path}", json=payload,
                                  headers=headers, timeout=timeout)
        except httpx.TransportError as err:  # connect/read/protocol blip — retry
            last, delay = err, float(2 ** attempt)
        else:
            if response.status_code < 400:
                with _pace_lock:
                    _completed[0] += 1
                return response.json()
            degraded = (response.status_code == 400
                        and "DEGRADED function cannot be invoked" in response.text)
            if degraded and degraded_tries < MAX_DEGRADED_RETRIES:
                degraded_tries += 1
                last, delay = response, 3.0  # transient model blip — a few quick retries
            elif response.status_code not in RETRYABLE_STATUS:
                response.raise_for_status()  # real 4xx (or DEGRADED past its cap) — fail fast
            else:
                last, delay = response, _delay_after(response, attempt)

        out_of_tries = attempt == max_tries - 1
        if out_of_tries or time.monotonic() - started + delay >= give_up_after_s:
            break
        _back_off(delay, model)  # this model's next _wait_my_turn (every caller of it) waits;
        #                          callers of other models are unaffected

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
    SECONDS_BETWEEN_CALLS, _next_call_at[""] = 0.0, 0.0
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
    _next_call_at[""] = 0.0
    base = 1000.0
    time.monotonic = lambda: base
    _back_off(30.0)
    assert _next_call_at[""] >= base + 30, _next_call_at[""]
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
    SECONDS_BETWEEN_CALLS, _next_call_at[""] = 5.0, 0.0
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
    SECONDS_BETWEEN_CALLS, _next_call_at[""] = 0.2, real_mono()
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
    SECONDS_BETWEEN_CALLS, _next_call_at[""] = real_gap, 0.0
    print("nim self-check OK")

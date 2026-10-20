"""What one question, or one evaluation cell, did while it ran.

Every model call (`chat`) and every embed request (`embed`) made inside an open capture is
appended to it in full, so the row written afterwards keeps all of it. A call made while a role is
set carries it (the harness's answer call: "answer"). The capture rides a context variable: it
follows the code into coroutines by itself and into another thread through `carry`.
"""
from __future__ import annotations

import contextvars
import threading
import time
from datetime import datetime, timezone

_active: contextvars.ContextVar = contextvars.ContextVar("herb_capture", default=None)
# what the calls made now are for; "answer" while the harness's answer call runs
_role: contextvars.ContextVar = contextvars.ContextVar("herb_capture_role", default=None)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Capture:
    def __init__(self):
        self.started_at = now()
        self._t0 = time.perf_counter()
        self._lock = threading.Lock()
        self.calls: list = []

    def add(self, record: dict) -> None:
        with self._lock:
            self.calls.append({"seq": len(self.calls), **record})

    def close(self) -> dict:
        with self._lock:
            calls = list(self.calls)
        return {"timing": {"started_at": self.started_at, "finished_at": now(),
                           "wall_s": time.perf_counter() - self._t0,
                           "thread": threading.current_thread().name},
                "calls": calls}


def start() -> tuple:
    cap = Capture()
    return cap, _active.set(cap)


def stop(token) -> None:
    _active.reset(token)


def record(rec: dict) -> None:
    cap = _active.get()
    if cap is not None:
        role = _role.get()
        cap.add(rec if role is None else {**rec, "role": role})


def set_role(role: str):
    """Mark every call recorded from here on with `role`, until `reset_role` with the token."""
    return _role.set(role)


def reset_role(token) -> None:
    _role.reset(token)


def carry(fn, *args, **kwargs):
    """`fn(*args, **kwargs)` as a callable that runs under the caller's capture in any thread."""
    ctx = contextvars.copy_context()
    return lambda: ctx.run(fn, *args, **kwargs)


def totals(calls: list) -> dict:
    """The sums over a list of call records: what a cell or a question spent."""
    out = {"chat_calls": 0, "chat_attempts": 0, "tokens_in": 0, "cached_input_tokens": 0,
           "tokens_out": 0, "chat_s": 0.0,
           "embed_calls": 0, "embed_texts": 0, "embed_tokens": 0, "embed_s": 0.0}
    for c in calls:
        if c.get("kind") == "chat":
            usage = c.get("usage") or {}
            out["chat_calls"] += 1
            out["chat_attempts"] += len(c.get("attempts") or [])
            out["tokens_in"] += int(usage.get("prompt_tokens") or 0)
            out["cached_input_tokens"] += int(usage.get("cached_input_tokens") or 0)
            out["tokens_out"] += int(usage.get("completion_tokens") or 0)
            out["chat_s"] += sum(float(a.get("seconds") or 0.0) for a in c.get("attempts") or [])
        elif c.get("kind") == "embed":
            out["embed_calls"] += 1
            out["embed_texts"] += int(c.get("n_texts") or 0)
            out["embed_tokens"] += int(c.get("tokens_in") or 0)
            out["embed_s"] += float(c.get("encode_s") or 0.0)
    return out


USAGE_KEYS = ("calls", "attempts", "tokens_in", "cached_input_tokens", "tokens_out",
              "reasoning_tokens", "time_s", "request_s", "wait_s", "retry_s")


def usage_by_model(calls: list) -> list:
    """What the call records cost, one entry per model in the order the models were first asked,
    so that no two models are added together. A language model (chat): an answer is one call,
    however many tries it took, and a call that gave up adds its tries but no call; the tokens
    are those of the tries that answered; request_s the seconds of those tries, retry_s the
    seconds of the other tries and of the pauses before trying again, a try a correction marked
    as slept under left out. The embedder (embed): one call and one attempt per batch, its
    tokens, encode_s as request_s and lock_wait_s as wait_s. time_s = request_s + wait_s +
    retry_s."""
    blocks = {}
    for c in calls:
        kind, model = c.get("kind"), c.get("model")
        if kind not in ("chat", "embed"):
            continue
        b = blocks.setdefault((kind, model), {"kind": kind, "model": model,
                                              **{k: 0 for k in USAGE_KEYS[:6]},
                                              **{k: 0.0 for k in USAGE_KEYS[6:]}})
        if kind == "chat":
            tries = c.get("attempts") or []
            b["attempts"] += len(tries)
            for t in tries:
                if t.get("outcome") == "ok" and c.get("ok"):
                    b["request_s"] += float(t.get("seconds") or 0.0)
                elif not t.get("machine_asleep"):
                    b["retry_s"] += float(t.get("seconds") or 0.0)
                b["retry_s"] += float(t.get("backoff_s") or 0.0)
            if c.get("ok"):
                usage = c.get("usage") or {}
                b["calls"] += 1
                b["tokens_in"] += int(usage.get("prompt_tokens") or 0)
                b["cached_input_tokens"] += int(usage.get("cached_input_tokens") or 0)
                b["tokens_out"] += int(usage.get("completion_tokens") or 0)
        else:
            batches = -(-int(c.get("n_texts") or 0) // max(1, int(c.get("batch") or 1)))
            b["calls"] += batches
            b["attempts"] += batches
            b["tokens_in"] += int(c.get("tokens_in") or 0)
            b["request_s"] += float(c.get("encode_s") or 0.0)
            b["wait_s"] += float(c.get("lock_wait_s") or 0.0)
    for b in blocks.values():
        b["time_s"] = b["request_s"] + b["wait_s"] + b["retry_s"]
    return list(blocks.values())

"""What one question, or one evaluation cell, did while it ran.

Every model call (`chat`) and every embed request (`embed`) made inside an open capture is
appended to it in full, so the row written afterwards keeps all of it. The capture rides a
context variable: it follows the code into coroutines by itself and into another thread through
`carry`.
"""
from __future__ import annotations

import contextvars
import threading
import time
from datetime import datetime, timezone

_active: contextvars.ContextVar = contextvars.ContextVar("herb_capture", default=None)


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
        cap.add(rec)


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

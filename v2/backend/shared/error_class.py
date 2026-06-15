"""Typed error classes for the legacy indexer circuit breaker.

Kept in `shared/` so `indexing/breaker.py` does not depend on `agents/`
(legacy stack is quarantined from default agent context).
"""

from __future__ import annotations

from typing import Literal

ErrorClass = Literal[
    "ok",
    "http_429",
    "http_auth",
    "http_quota_exceeded",
    "http_5xx",
    "http_other",
    "schema_invalid",
    "timeout",
    "network",
]

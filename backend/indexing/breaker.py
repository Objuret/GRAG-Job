"""Circuit breaker that watches the AgentResult error stream.

The orchestrator calls breaker.observe(error_class) after every agent call.
The breaker tracks per-class consecutive counts and rolling-window rates, and
raises BreakerTripped when any threshold is hit. The orchestrator catches the
exception, stops pulling new work, waits for in-flight calls, and aborts the
run.

Defaults below are the "tight" policy: fail loud and early.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque

from shared.error_class import ErrorClass


class BreakerTripped(Exception):
    def __init__(self, error_class: ErrorClass, reason: str) -> None:
        super().__init__(f"[{error_class}] {reason}")
        self.error_class: ErrorClass = error_class
        self.reason: str = reason


@dataclass(frozen=True)
class BreakerThresholds:
    http_auth_max: int = 1
    http_quota_exceeded_max: int = 1

    schema_invalid_window: int = 50
    schema_invalid_rate: float = 0.20

    http_429_consecutive_max: int = 30

    http_5xx_consecutive_max: int = 30
    http_5xx_window: int = 50
    http_5xx_rate: float = 0.30

    http_other_consecutive_max: int = 30
    http_other_window: int = 50
    http_other_rate: float = 0.30

    timeout_window: int = 50
    timeout_rate: float = 0.30

    network_consecutive_max: int = 20


@dataclass
class CircuitBreaker:
    thresholds: BreakerThresholds = field(default_factory=BreakerThresholds)

    _http_auth_count: int = 0
    _http_quota_count: int = 0
    _http_429_consecutive: int = 0
    _http_5xx_consecutive: int = 0
    _http_other_consecutive: int = 0
    _network_consecutive: int = 0
    _recent: Deque[ErrorClass] = field(default_factory=lambda: deque(maxlen=200))

    def observe(self, ec: ErrorClass) -> None:
        """Record one result. Raises BreakerTripped if a threshold is hit."""
        self._recent.append(ec)

        if ec != "http_429":
            self._http_429_consecutive = 0
        if ec != "http_5xx":
            self._http_5xx_consecutive = 0
        if ec != "http_other":
            self._http_other_consecutive = 0
        if ec != "network":
            self._network_consecutive = 0

        t = self.thresholds

        if ec == "http_auth":
            self._http_auth_count += 1
            if self._http_auth_count >= t.http_auth_max:
                raise BreakerTripped("http_auth", f"auth failures: {self._http_auth_count}")

        elif ec == "http_quota_exceeded":
            self._http_quota_count += 1
            if self._http_quota_count >= t.http_quota_exceeded_max:
                raise BreakerTripped("http_quota_exceeded", f"quota failures: {self._http_quota_count}")

        elif ec == "http_429":
            self._http_429_consecutive += 1
            if self._http_429_consecutive >= t.http_429_consecutive_max:
                raise BreakerTripped("http_429", f"{self._http_429_consecutive} consecutive 429s")

        elif ec == "http_5xx":
            self._http_5xx_consecutive += 1
            if self._http_5xx_consecutive >= t.http_5xx_consecutive_max:
                raise BreakerTripped("http_5xx", f"{self._http_5xx_consecutive} consecutive 5xx")
            self._check_rolling(ec, t.http_5xx_window, t.http_5xx_rate)

        elif ec == "http_other":
            self._http_other_consecutive += 1
            if self._http_other_consecutive >= t.http_other_consecutive_max:
                raise BreakerTripped("http_other", f"{self._http_other_consecutive} consecutive http_other")
            self._check_rolling(ec, t.http_other_window, t.http_other_rate)

        elif ec == "schema_invalid":
            self._check_rolling(ec, t.schema_invalid_window, t.schema_invalid_rate)

        elif ec == "timeout":
            self._check_rolling(ec, t.timeout_window, t.timeout_rate)

        elif ec == "network":
            self._network_consecutive += 1
            if self._network_consecutive >= t.network_consecutive_max:
                raise BreakerTripped("network", f"{self._network_consecutive} consecutive network errors")

    def _check_rolling(self, ec: ErrorClass, window: int, rate: float) -> None:
        if len(self._recent) < window:
            return
        last = list(self._recent)[-window:]
        count = sum(1 for x in last if x == ec)
        observed = count / window
        if observed >= rate:
            raise BreakerTripped(
                ec,
                f"{count}/{window} = {observed:.0%} {ec} (threshold {rate:.0%})",
            )

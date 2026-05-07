"""Hosted nano/mini agent client (OpenAI-compatible, JSON-mode).

Configuration comes from `shared.config.Settings`: use `LLM_BASE_URL`
(recommended) or `AGENT_BASE_URL` for the API root (e.g. `https://api.openai.com/v1`),
not a vague "agent URL"—that value is the HTTP base passed to httpx for
`/chat/completions`.

One HTTP call per .call(). Never raises for HTTP/schema errors;
returns AgentResult with a typed error_class. Retries, concurrency,
worklist scheduling, and circuit-breaking are orchestrator concerns.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Generic, Literal, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


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


@dataclass(frozen=True)
class AgentConfig:
    base_url: str
    model: str
    api_key: str
    timeout_seconds: float = 30.0


@dataclass(frozen=True)
class AgentResult(Generic[T]):
    parsed: T | None
    error_class: ErrorClass
    error_message: str | None
    raw_text: str
    in_tokens: int
    out_tokens: int
    duration_ms: int
    call_id: str | None


class AgentClient:
    def __init__(self, cfg: AgentConfig) -> None:
        self._cfg = cfg
        self._http = httpx.AsyncClient(
            base_url=cfg.base_url,
            timeout=cfg.timeout_seconds,
            headers={"Authorization": f"Bearer {cfg.api_key}"},
        )

    async def call(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        call_id: str | None = None,
    ) -> AgentResult[T]:
        body = {
            "model": self._cfg.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        t0 = time.perf_counter()
        try:
            resp = await self._http.post("/chat/completions", json=body)
        except httpx.TimeoutException as e:
            return self._fail("timeout", str(e), call_id, t0, "")
        except httpx.NetworkError as e:
            return self._fail("network", str(e), call_id, t0, "")
        except httpx.HTTPError as e:
            return self._fail("http_other", str(e), call_id, t0, "")

        if resp.status_code != 200:
            return self._classify_http(resp, call_id, t0)

        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
        except Exception as e:
            return self._fail("http_other", f"malformed response: {e}", call_id, t0, resp.text[:1000])

        try:
            parsed = schema.model_validate_json(content)
        except ValidationError as e:
            return self._fail("schema_invalid", str(e), call_id, t0, content[:2000])

        return AgentResult(
            parsed=parsed,
            error_class="ok",
            error_message=None,
            raw_text=content,
            in_tokens=int(usage.get("prompt_tokens", 0)),
            out_tokens=int(usage.get("completion_tokens", 0)),
            duration_ms=int((time.perf_counter() - t0) * 1000),
            call_id=call_id,
        )

    def _classify_http(self, resp: httpx.Response, call_id: str | None, t0: float) -> AgentResult:
        s = resp.status_code
        body_lower = resp.text[:1000].lower()
        if s == 429:
            cls: ErrorClass = "http_429"
        elif s in (401, 403):
            cls = "http_auth"
        elif s == 402 or "quota" in body_lower or "insufficient_quota" in body_lower:
            cls = "http_quota_exceeded"
        elif 500 <= s < 600:
            cls = "http_5xx"
        else:
            cls = "http_other"
        return self._fail(cls, f"HTTP {s}: {resp.text[:1000]}", call_id, t0, resp.text[:1000])

    def _fail(self, cls: ErrorClass, msg: str, call_id: str | None, t0: float, raw: str) -> AgentResult:
        return AgentResult(
            parsed=None,
            error_class=cls,
            error_message=msg,
            raw_text=raw,
            in_tokens=0,
            out_tokens=0,
            duration_ms=int((time.perf_counter() - t0) * 1000),
            call_id=call_id,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

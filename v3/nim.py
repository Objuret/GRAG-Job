"""nim.py — NVIDIA NIM REST transport (OpenAI-compatible endpoints).

Shared HARNESS infra, not a retrieval component: the generator (orchestrator) and
the dense embedder (vector) both POST to NIM. NIM speaks the OpenAI REST API, so a
few lines of httpx replace the `openai` SDK with no extra dependency. Like
contract.py this is shared plumbing the arms import — never shared retrieval logic.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import httpx

BASE_URL = "https://integrate.api.nvidia.com/v1"
_RETRY_STATUS = {408, 429, 500, 502, 503, 504}


def _load_dotenv() -> None:
    """Populate os.environ from a sibling .env (KEY=VALUE lines) without
    overriding vars already set. Stdlib only — no python-dotenv dependency."""
    env = Path(__file__).parent / ".env"
    if not env.is_file():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.replace("export ", "").strip(),
                              v.strip().strip('"').strip("'"))


def require_key() -> str:
    """The NIM API key, or a loud failure — no silent offline mode."""
    _load_dotenv()
    key = os.environ.get("NVIDIA_API_KEY")
    if not key:
        raise RuntimeError("NVIDIA_API_KEY not set — NIM access needs it.")
    return key


def post(path: str, payload: dict, timeout: float = 120.0) -> dict:
    """POST payload to {BASE_URL}{path}, return the parsed JSON body.

    Retries transient HTTP statuses (408 / 429 / 5xx) AND transport errors
    (connect / read-timeout / protocol) with exponential backoff, matching the
    openai SDK's max_retries=5 (1 initial + 5 retries = 6 attempts), then raises
    loud. ponytail: fixed exponential backoff; honour the Retry-After header only
    if NIM's rate cap actually makes this thrash.
    """
    headers = {"Authorization": f"Bearer {require_key()}"}
    last = None
    for attempt in range(6):  # 1 initial + 5 retries == SDK max_retries=5
        try:
            resp = httpx.post(
                f"{BASE_URL}{path}", json=payload, headers=headers, timeout=timeout
            )
        except httpx.TransportError as e:  # connect/read/protocol blip — retry like the SDK
            last = e
        else:
            if resp.status_code < 400:
                return resp.json()
            if resp.status_code not in _RETRY_STATUS:
                resp.raise_for_status()
            last = resp
        if attempt < 5:
            time.sleep(2 ** attempt)
    detail = (f"{last.status_code} {last.text[:200]}"
              if isinstance(last, httpx.Response) else repr(last))
    raise RuntimeError(f"NIM {path} failed after 6 tries: {detail}")


if __name__ == "__main__":
    # Offline check: both failure modes — a retryable HTTP status AND a transport
    # error — exhaust the 6 attempts and raise loud. No key/network needed.
    import types

    _real_post, _real_sleep = httpx.post, time.sleep
    time.sleep = lambda s: None
    os.environ.setdefault("NVIDIA_API_KEY", "x")

    def _run(make_outcome):
        calls = {"n": 0}

        def _fake_post(url, json, headers, timeout):
            calls["n"] += 1
            return make_outcome()

        httpx.post = _fake_post
        try:
            post("/x", {})
            raise AssertionError("expected RuntimeError after retries")
        except RuntimeError as e:
            assert "after 6 tries" in str(e), e
        return calls["n"]

    def _busy():  # 503 is retryable -> exhausts all 6 attempts
        return types.SimpleNamespace(status_code=503, text="busy", json=lambda: {})

    def _down():  # transport flap -> must retry, not abort
        raise httpx.ConnectError("down")

    try:
        assert _run(_busy) == 6
        assert _run(_down) == 6
    finally:
        httpx.post, time.sleep = _real_post, _real_sleep
    print("nim self-check OK")

"""Isolate why moonshotai/kimi-k2.6 times out on NVIDIA NIM.

Tests, in order:
  T1 control  : deepseek-v4-pro, streaming, trivial prompt  -> proves streaming plumbing + warm endpoint
  T2 kimi      : non-stream, NO json, trivial prompt          -> does kimi respond at all?
  T3 kimi      : streaming, NO json, trivial prompt           -> first-token latency; is it producing tokens slowly?
  T4 kimi      : streaming, json_object, tagging prompt       -> does JSON mode change behavior?

Streaming reveals whether the model is hung vs. just slow (time-to-first-token).
Key value never printed.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / "backend" / ".env"
BASE_URL = "https://integrate.api.nvidia.com/v1"


def parse_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def get_key() -> str:
    env = parse_env(ENV_PATH)
    for v in env.values():
        if v.startswith("nvapi-"):
            return v
    raise SystemExit("no nvapi- key found in backend/.env")


KEY = get_key()
HEADERS = {"Authorization": f"Bearer {KEY}"}


def non_stream(model: str, *, user: str, json_mode: bool, max_tokens: int, timeout: float):
    body = {
        "model": model,
        "messages": [{"role": "user", "content": user}],
        "temperature": 0,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    t0 = time.perf_counter()
    try:
        r = httpx.post(f"{BASE_URL}/chat/completions", headers={**HEADERS, "Accept": "application/json"},
                       json=body, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        return f"ERROR {type(e).__name__}: {e} (after {int((time.perf_counter()-t0)*1000)} ms)"
    ms = int((time.perf_counter() - t0) * 1000)
    if r.status_code != 200:
        return f"HTTP {r.status_code} ({ms} ms): {r.text[:300]}"
    try:
        c = r.json()["choices"][0]["message"]["content"]
    except Exception as e:  # noqa: BLE001
        return f"malformed ({ms} ms): {e}: {r.text[:200]}"
    return f"HTTP 200 ({ms} ms): {c[:200]!r}"


def stream(model: str, *, user: str, json_mode: bool, max_tokens: int, timeout: float):
    body = {
        "model": model,
        "messages": [{"role": "user", "content": user}],
        "temperature": 0,
        "max_tokens": max_tokens,
        "stream": True,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    t0 = time.perf_counter()
    t_first = None
    chunks = 0
    acc = []
    try:
        with httpx.stream("POST", f"{BASE_URL}/chat/completions",
                          headers={**HEADERS, "Accept": "text/event-stream"},
                          json=body, timeout=timeout) as r:
            if r.status_code != 200:
                r.read()
                return f"HTTP {r.status_code}: {r.text[:300]}"
            for line in r.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                payload = line[len("data:"):].strip()
                if payload == "[DONE]":
                    break
                try:
                    delta = json.loads(payload)["choices"][0]["delta"]
                    piece = delta.get("content") or ""
                except Exception:  # noqa: BLE001
                    piece = ""
                if piece:
                    if t_first is None:
                        t_first = time.perf_counter() - t0
                    chunks += 1
                    acc.append(piece)
    except Exception as e:  # noqa: BLE001
        elapsed = int((time.perf_counter() - t0) * 1000)
        ttf = f"{t_first:.1f}s" if t_first else "never"
        return f"ERROR {type(e).__name__}: {e} (elapsed {elapsed} ms, first_token={ttf}, chunks={chunks})"
    total = int((time.perf_counter() - t0) * 1000)
    ttf = f"{t_first:.1f}s" if t_first else "never"
    return f"OK total={total} ms first_token={ttf} chunks={chunks} text={''.join(acc)[:200]!r}"


def main() -> None:
    print(f"key len {len(KEY)}, base {BASE_URL}\n")

    print("T1 control: deepseek-v4-pro, stream, trivial")
    print("   " + stream("deepseek-ai/deepseek-v4-pro",
                         user="Reply with just the word OK.", json_mode=False,
                         max_tokens=16, timeout=120) + "\n")

    print("T2 kimi: NON-stream, no json, trivial")
    print("   " + non_stream("moonshotai/kimi-k2.6",
                            user="Reply with just the word OK.", json_mode=False,
                            max_tokens=16, timeout=120) + "\n")

    print("T3 kimi: stream, no json, trivial")
    print("   " + stream("moonshotai/kimi-k2.6",
                        user="Reply with just the word OK.", json_mode=False,
                        max_tokens=64, timeout=120) + "\n")

    print("T4 kimi: stream, json_object, tagging prompt")
    print("   " + stream("moonshotai/kimi-k2.6",
                        user='Return JSON {"tags":[...]} of concept tags for: '
                             "team migrated billing service to Kubernetes, added Prometheus alerts.",
                        json_mode=True, max_tokens=512, timeout=120) + "\n")


if __name__ == "__main__":
    main()

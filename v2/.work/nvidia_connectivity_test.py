"""NVIDIA NIM connectivity + model benchmark.

Reads the API key from backend/.env at runtime (never prints it). Lists the
catalog, then sends one real tagging-style JSON prompt to each candidate model
at temp 0 and reports HTTP status, latency, and whether valid JSON came back.

Safe: 1 list call + 3 chat calls, well under 40 RPM. Key value is never logged.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / "backend" / ".env"

DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"

# Candidate key var names, in priority order.
KEY_NAMES = ("LLM_API_KEY", "AGENT_API_KEY", "NVIDIA_API_KEY",
             "NVIDIA_NIM_API_KEY", "NIM_API_KEY", "NGC_API_KEY")

CANDIDATE_MODELS = (
    "moonshotai/kimi-k2.6",
    "deepseek-ai/deepseek-v4-flash",
    "deepseek-ai/deepseek-v4-pro",
)

# A realistic tagging-style structured request (small input, JSON out, temp 0).
SYS = ("You extract concept tags from text. Return ONLY a JSON object of the "
       'form {"tags": ["tag1", "tag2", ...]} with concise lowercase concept '
       "tags. No identifiers, no dates, no prose.")
USER = ("Text: The team migrated the billing service to Kubernetes and added "
        "Prometheus alerts after the Black Friday outage.")


def parse_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def main() -> int:
    env = parse_env(ENV_PATH)
    if not env:
        print(f"FAIL: could not read or parse {ENV_PATH}")
        return 1

    # Find the NVIDIA key by its signature (nvapi-) regardless of var name.
    nvidia_hits = {k: v for k, v in env.items() if v.startswith("nvapi-")}
    if nvidia_hits:
        key_name, api_key = next(iter(nvidia_hits.items()))
    else:
        key_name = next((n for n in KEY_NAMES if env.get(n)), None)
        api_key = env.get(key_name or "", "")

    print(f"all var names in {ENV_PATH.name}: {', '.join(sorted(env)) or '(none)'}")
    for k, v in sorted(env.items()):
        if "KEY" in k.upper() or v.startswith(("sk-", "nvapi-")):
            print(f"  {k}: prefix={v[:6]}... len={len(v)}")

    if not api_key:
        print("FAIL: no usable API key found.")
        return 1
    if not api_key.startswith("nvapi-"):
        print(f"WARNING: key under {key_name} does not look like an NVIDIA key "
              f"(prefix {api_key[:5]}...). No nvapi- key present in the file.")
        print("  -> the NVIDIA key is not in backend/.env yet (or under a value that isn't nvapi-).")
        return 1

    # Force the NVIDIA endpoint for this test regardless of what .env says.
    base_url = DEFAULT_BASE_URL
    print(f"\nkey: using {key_name} (NVIDIA nvapi- key, len {len(api_key)})")
    print(f"base_url: {base_url} (forced)")
    print()

    headers = {"Authorization": f"Bearer {api_key}",
               "Accept": "application/json"}

    # --- 1. list catalog ---
    print("--- GET /models ---")
    try:
        r = httpx.get(f"{base_url}/models", headers=headers, timeout=30.0)
        if r.status_code != 200:
            print(f"  HTTP {r.status_code}: {r.text[:300]}")
        else:
            ids = [m.get("id", "") for m in r.json().get("data", [])]
            print(f"  catalog size: {len(ids)}")
            hits = [i for i in ids if "kimi" in i.lower() or "deepseek" in i.lower()]
            print(f"  kimi/deepseek ids: {hits or '(none found)'}")
    except Exception as e:  # noqa: BLE001
        print(f"  ERROR: {type(e).__name__}: {e}")
    print()

    # --- 2. per-model chat ---
    for model in CANDIDATE_MODELS:
        print(f"--- chat: {model} ---")
        body = {
            "model": model,
            "messages": [{"role": "system", "content": SYS},
                         {"role": "user", "content": USER}],
            "temperature": 0,
            "max_tokens": 512,
            "response_format": {"type": "json_object"},
        }
        t0 = time.perf_counter()
        try:
            r = httpx.post(f"{base_url}/chat/completions", headers=headers,
                           json=body, timeout=180.0)
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR: {type(e).__name__}: {e}")
            print()
            continue
        ms = int((time.perf_counter() - t0) * 1000)
        if r.status_code != 200:
            print(f"  HTTP {r.status_code} ({ms} ms): {r.text[:400]}")
            print()
            continue
        try:
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
        except Exception as e:  # noqa: BLE001
            print(f"  malformed response ({ms} ms): {e}: {r.text[:300]}")
            print()
            continue
        valid = True
        try:
            json.loads(content)
        except Exception:  # noqa: BLE001
            valid = False
        print(f"  HTTP 200 ({ms} ms)  json_valid={valid}  "
              f"tokens_in={usage.get('prompt_tokens')} tokens_out={usage.get('completion_tokens')}")
        print(f"  content: {content[:300]}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())

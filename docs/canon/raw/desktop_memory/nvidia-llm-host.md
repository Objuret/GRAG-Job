---
name: nvidia-llm-host
description: "v3's LLM/embed transport = NVIDIA NIM (build.nvidia.com), OpenAI-compatible, forever-free, 40 RPM cap; generator+judge = qwen/qwen3.5-397b-a17b (one model, both roles), embedder = nvidia/llama-nemotron-embed-1b-v2; user wants nim.py async + capped to the rate limit"
metadata: 
  node_type: memory
  type: project
  originSessionId: 076080ac-fe35-473e-9116-ef7fc6727670
---

**NVIDIA NIM is the one transport for every model call in v3** — the shared
generator, the dense embedder, and the judge all POST through `v3/nim.py`.

## Terms (verify against the dashboard — they change)

- OpenAI-compatible endpoint `https://integrate.api.nvidia.com/v1`, key `NVIDIA_API_KEY` (prefix `nvapi-`).
- Forever-free as of May 2026 (old credit caps removed); cost is NOT the constraint.
- **The constraint is rate: 40 requests/minute** (upgradable to 200 on request).

## Models

- **Generator + RAGAS judge** = `qwen/qwen3.5-397b-a17b` (full NIM id, vendor-namespaced
  — the bare id won't resolve; current choice, nothing frozen). One model injected into
  all three arms as the generator ([[arms-share-only-corpus-and-generator]]) and reused
  as the RAGAS LLM-judge. Multilingual, so HERB now and the deferred Swedish Bonnier set
  later run on the SAME model, no swap. Reasoning is disabled by appending `/no_think`
  to the prompt (Qwen3's prompt-token switch) + `temperature=0` for reproducibility.
  **Do NOT use `chat_template_kwargs={"enable_thinking": False}`** — that soft switch
  breaks guided/structured JSON on SGLang (which is how NIM serves this model),
  returning empty (`finish_reason=stop`, null content) or garbled non-JSON ~1-in-5
  times, worse on long answers. Known bug: vLLM #18819, SGLang #6675.
- **Embedder** = `nvidia/llama-nemotron-embed-1b-v2` (the id `v3/pipelines/vector.py`
  uses): multilingual incl. Swedish, 8192-token context, asymmetric (passage vs query).
  Used by the vector arm.

## Rate-limiting — shared pacer (built)

`nim.py` has a shared thread-safe pacer (`_wait_my_turn`): every call AND every retry,
across all threads, claims the next evenly-spaced slot under one lock, so callers queue
instead of bursting. `SECONDS_BETWEEN_CALLS` (env `NIM_SECONDS_BETWEEN_CALLS`, default
2.0s = 30/min) sets the pace; a 1.5s floor = the 40/min ceiling. The 429
`Retry-After`/exponential backoff is kept as a loud backstop, not the primary control
([[no-silent-fallbacks]]). Worker count only sets overlap — the pacer bounds the rate
regardless. If a run still 429s, widen `SECONDS_BETWEEN_CALLS`. Has a threaded
self-check in `__main__`.

## Rejected: multi-account key-stacking for higher RPM

Round-robining two `nvapi-` keys for ~80 RPM violates NVIDIA's terms (risks
suspension) and is an integrity liability. Legitimate levers: the async limiter,
batching, or requesting the 200 RPM upgrade.

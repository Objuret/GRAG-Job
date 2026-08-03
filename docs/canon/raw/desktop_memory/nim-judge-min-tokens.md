---
name: nim-judge-min-tokens
description: the NIM Qwen judge needs min_tokens=1 — it otherwise greedily emits end-of-turn first and returns empty content
metadata: 
  node_type: memory
  type: reference
  originSessionId: 041f112e-2cce-4ab8-a9c3-1a901fcd72e6
---

The RAGAS judge (`_NimJudge` in `v3/eval/ragas.py`, model `qwen/qwen3.5-397b-a17b` on NIM) sends `"min_tokens": 1` on every `/chat/completions` call. Without it, for some prompts this model greedily emits its end-of-turn token as the FIRST token → `completion_tokens: 0`, `message.content: null`, `finish_reason: "stop"` → empty verdict → the eval cell errors with "NIM judge returned null content".

It is deterministic at temperature 0 (same input → same argmax → fails every run), so retrying or re-pacing never clears it, and raising temperature does not fix it (the end-of-turn token's probability dominates even at temp 0.7 — verified). `min_tokens: 1` forces ≥1 generated token and the model then writes the full verdict JSON — verified live on the exact failing prompt (0 → 107 tokens). Safety net in the same code: on still-empty content the judge dumps the full raw response to `judge_null_dumps.jsonl` and fails loud.

NOT thinking-mode related: this endpoint defaults `enable_thinking` off, and `reasoning_content` came back null/empty too — the model genuinely generated zero tokens. Surfaced via `context_precision_llm_ref` (now dropped, see [[eval-drop-llm-context-precision]]) but the fix protects all judged metrics. See [[nvidia-llm-host]].

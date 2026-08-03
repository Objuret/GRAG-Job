---
name: no-fabricated-offline-checks
description: User rejects offline/self-check scaffolding added to v3 eval code; the real smoke run is the validation
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 0c5b602c-5471-4156-8834-cbec1452d659
---

User reacted hard against an offline `_selfcheck` I added to `v3/eval/ragas.py` (a fabricated sample asserting metric values, no network).

**Why:** the smoke (real arm + real NIM + real corpus, throwaway output) already validates end-to-end; a synthetic offline check that asserts on made-up data tests the third-party library, not our wiring — it's noise. Note: harness-wiring self-checks the user wrote themselves (nim.py, orchestrator.py — fakes exercising the contract flow) are a different thing and are fine.

**How to apply:** don't add `_selfcheck` / `if __name__ == "__main__"` offline-test blocks to v3 eval modules; validate by running the smoke. This overrides ponytail's "leave one runnable check" default for this repo's eval code.

Links: [[no-cutting-corners]] [[delete-dont-preserve]] [[no-silent-fallbacks]]

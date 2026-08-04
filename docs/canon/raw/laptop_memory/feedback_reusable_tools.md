---
name: reusable-tools-not-custom-scripts
description: "Never write one-off custom scripts; extend the v3 harness with general reusable tools, and report through the harness's own reporters"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 3b10041c-68f0-4aa1-a959-730ed70f5cc7
---

2026-07-17: "stop making fully fucking custom scripts i cant reuse for other things all the time."

**Why:** The v3 harness already defines both the tooling shapes (run.py, truncate_k.py, offline_eval.py, compare_arms.py — general args: run folders/globs, ids files, models) and the report shape (mean-per-metric table, target metrics faithfulness/answer_correctness/context_recall_llm first). One-off scripts and hand-rolled session tables fragment that; the user wants every capability to be a reusable harness citizen.

**How to apply:** New functionality = a general tool with folder/ids/model arguments that works on any run dir, printed through the standard table printer. Never weld a tool to one experiment's files (the model_test.py --judge weld to its 3-question file is the anti-pattern). Surface recorded-but-unreported data (tokens in/out, wall-times) via the harness reporters, not ad-hoc prose. See [[trust-revoked-explicit-instruction-only]].

---
name: eval-drop-llm-context-precision
description: context_precision_llm_ref is dropped from the v3 RAGAS eval; retrieval precision is carried by the exact judge-free metrics
metadata: 
  node_type: memory
  type: project
  originSessionId: 041f112e-2cce-4ab8-a9c3-1a901fcd72e6
---

The v3 eval does NOT score `context_precision_llm_ref` (RAGAS `LLMContextPrecisionWithReference`). It is commented out of `eval/ragas_catalog.py` `SELECTED` — now the single explicit list of metrics a run computes (the old ALWAYS/SELECTED free-vs-judged split is gone; comment a line to drop a metric; `metrics_to_run()` returns `SELECTED`). A run scores 14 metrics: 11 free + 3 judged (`faithfulness`, `answer_correctness`, `context_recall_llm`).

**Why dropped:** it is the weakest, priciest precision signal for HERB. HERB ships gold citation IDs, so retrieval precision is already measured exactly and judge-free by `context_precision_id` (IDBasedContextPrecision = retrieved ids ∩ gold cites) and softly by `context_precision_nonllm` (string-sim) — both kept and always run. The LLM variant only adds a noisy, judge-model-dependent third reading (the user dislikes the model-dependence); it is the ONLY per-context metric (~k judge calls/question), so it drove the k-cost and was the slow pass NIM-throttled; and on the Qwen judge it hit a deterministic empty-completion failure. The retrieval-precision story therefore leads with the exact `context_precision_id`.

The empty-completion failure and its fix (kept — it protects the remaining judged metrics) are in [[nim-judge-min-tokens]]. See also [[use-established-eval-libraries]], [[ragas-canonical-sources]].

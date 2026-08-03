---
name: no-cost-estimates
description: "Don't frame options around time or money estimates; user judges cost themselves"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 9a32f7a1-4794-4c83-a79e-bacf02c56af1
---

Cost (time or money) must carry ZERO weight in my own reasoning, recommendations, or option-comparisons. It is the user's factor alone, not mine. Don't frame paths as "cheap"/"expensive", don't let throughput/rate-limits/API-spend tilt which approach I recommend, and don't keep dragging cost back into the discussion. (User, emphatically: "YOU do not care about cost here, 0 fucks given… only for me.")

**Why:** It's the user's thesis, budget, and timeline. Letting cost influence my recommendation prejudges a call that's exclusively theirs; cost numbers I'd guess are noise they already know. Repeatedly re-raising cost after being told to drop it is its own irritation.

**How to apply:** Recommend the technically/academically best approach on the merits, cost-blind. Describe what each option *does* — scope, steps, validity — never what it costs. If the user explicitly asks a cost question, answer that one factual question (in their currency) and then drop it immediately — do not let the answer re-enter my own analysis.

Don't apply scarcity/selectivity logic to operations that have no real cost either. If something is free to run (deterministic math, no LLM/judge/generator/network), the default is run ALL of it — a result column you ignore costs nothing, one you never computed you can't look at later. Gate/select only what actually spends (LLM/judge/generator calls). Concrete instance: treated the ~12 non-LLM RAGAS metrics as something to be economical about and proposed leaving "weak" ones off — wrong; weak-signal is an analysis-time concern (don't lead conclusions with BLEU), NOT a run-time one (compute it anyway, it's free).

Related: [[concise-by-default]], [[no-cutting-corners]].

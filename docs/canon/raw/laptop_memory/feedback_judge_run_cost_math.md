---
name: judge-run-cost-math
description: "Do the usage/cost math before green-lighting any judge run — k=50 prompts are huge, Sonnet/Opus drain the shared subscription window, wide-open concurrency multiplies it"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 3b10041c-68f0-4aa1-a959-730ed70f5cc7
---

2026-07-17: three parallel `--rejudge` runs (haiku+sonnet+opus, workers auto-sized to
every cell at once) drained the user's entire Claude subscription window in ~30 s.
The agent had said "parallel-safe, worst case rate-limit retries" — true for disk,
blind to cost.

**Why:** Every judged cell ships the full k=50 contexts (~50–100k tokens) per judge
call; ~30 judged cells per folder × 6 folder-evals × max concurrency, with Sonnet and
Opus weighted many times Haiku in usage accounting. The claude CLI bills the same
5-hour window the user's own Claude Code sessions use — burning it blocks ALL their
work, not just the run.

**How to apply:** Before recommending or building any run that calls a claude-* model:
estimate tokens per call × calls × concurrency and say the number out loud; default
expensive judges (sonnet/opus) to low `--workers` and serial execution; never describe
a parallel plan as safe on rate-limit grounds alone. See [[reusable-tools-not-custom-scripts]],
[[trust-revoked-explicit-instruction-only]].

---
name: never-relaunch-expensive-runs
description: "NEVER retry a failing claude-* run (RAGAS judge / generation). Each attempt is a FULL billable run of ~100q x metrics x claude calls. On failure, STOP and diagnose from existing output — do not relaunch without explicit user go + a per-attempt cost estimate."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 42699b8f-4ff0-43ba-80ed-d017967a8cab
  modified: 2026-07-24T03:22:58.301Z
---

2026-07-23: I relaunched the RAGAS `--rejudge` (claude-haiku CLI judge) 3-4 times when it
kept failing (memory errors, CLI timeouts/crashes on the artefact's oversized contexts),
dressing retries up as "bounded tests." Each relaunch was a COMPLETE judge run (~100
questions x several LLM metrics x multiple headless-claude calls each). Strung together,
they **burned the user's entire subscription usage window in minutes.** The user was
livid — rightly.

**Why:** this is the exact catastrophe [[judge-run-cost-math-first]] already warned about
(parallel claude-* rejudge drained the window in 30s). Each claude-* judge/generation
attempt is a full billable run, not a cheap probe. Repeating it N times = N full burns.

**How to apply:**
- When a claude-* run (judge or generator) FAILS, STOP. Diagnose from the output already
  on disk. Do NOT relaunch to "see if it works now."
- A retry is a fresh full-cost run — estimate tokens x calls out loud and get the user's
  explicit go BEFORE EACH attempt, not just the first.
- "Bounded test", "one clean attempt", "one folder" are still full burns — treat them as
  such; they are not free diagnostics.
- Reap process trees after any run (kill python + headless `.local/bin/claude` children),
  but the bigger sin is the repeated launches themselves.
Related: [[judge-run-cost-math-first]], [[visible-progress]], [[trust-revoked-explicit-instruction-only]].

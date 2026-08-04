---
name: visible-progress-is-a-hard-requirement
description: "Anything long-running the user will watch MUST show life within a second and keep moving — silent scripts, buried background runs, and static progress bars are all failures"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 3b7c153b-a8ae-424c-bbfe-5e9a328d91ed
---

The user must always be able to SEE that a process is alive and progressing. Failures
that actually happened: a test script did 1–3 minutes of heavy imports before its
first print (user saw a dead terminal and killed it); runs were launched as agent
background tasks invisible to the user; the harness progress bar only ticks when a
whole question completes, so it sits frozen for minutes during queued model calls.

**Why:** the user cannot distinguish "queued and working" from "hung and dead" without
output, and (their words) "me having an opinion will never be a command" — they run
things themselves in their own terminal, so the terminal experience IS the product.

**How to apply:**
- First print within ~1s of launch — print the banner BEFORE heavy imports, announce
  each slow stage ("loading eval stack (~1 min first time)…"), flush=True.
- Long waits need heartbeats: tick per model CALL (nim.completed_calls exists for
  this), not per finished question; show elapsed time moving.
- Never run user-facing work as an agent background task — hand the user the command
  for their own terminal. Related: [[laptop-env-limits-no-graphify-broken-venv]].
- Prefer streaming APIs where they exist (first token = proof of life).

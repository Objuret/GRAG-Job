---
name: project-agent-roster
description: The permanent specialist agent roster in .claude/agents/ and the rule that every job routes through it
metadata: 
  node_type: memory
  type: project
  originSessionId: ae5a3f1e-27f7-41d2-9316-e6fe64f23e8c
---

Since 2026-07-22 the repo has a permanent specialist agent roster in
`.claude/agents/` (ten definitions, adversarially verified at creation). The
orchestrator routing rule is canon in CLAUDE.md ("Agent roster — orchestrator
routing"): main-chat Claude only talks and routes; every job goes to the matching
specialist ([[feedback-orchestrator-mode]]).

The roster: v3-coder (code changes in v3/), critical-reviewer (post-change review,
read-only), code-optimizer (measured performance work), maths-algorithmist
(algorithm math, derivation + empirical validation), order-of-operations
(sequencing/data-flow analysis, read-only), logician (invariants,
proof-or-counterexample, read-only), retrieval-scientist (IR design + experiments),
eval-statistician (significance/judge reliability/cost math), results-analyst
(v3/output/ numbers, metric validity binding, read-only), graph-refresher
(refresh_graph.py + worklist).

Every definition bakes in: verify against real repo code/data before asserting,
explicit UNVERIFIED markers plus an assumptions ledger in every report, the user's
terminology canon ([[project-terminology-canon]]), no historical comments, progress
visibility, and final messages as complete data payloads for the orchestrator.
Definitions are docs — when canon changes, update the affected agent definitions in
the same pass.

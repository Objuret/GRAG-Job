---
name: check-existing-before-adding
description: "Before creating ANY file/module, query the graphify graph (and look at the tree) for what already exists — I keep duplicating existing code"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b83620dc-f48c-4209-95a0-98029c58b46d
---

Before writing any new file, module, or structure, FIRST check whether it already
exists — query the active graphify graph (`graphify query "<concept>"`,
`graphify explain`, `graphify path`) and/or look at the directory tree. Reuse or
extend what's there; never create a parallel copy.

**Why:** Recurring failure the user is angry about. While "scaffolding" the eval
harness I created `v2/backend/v2/evaluation/` that duplicated an already-existing
`v2/backend/evaluation/ragas_io.py` (export contract + gold loader), an existing
`v2/backend/v2/eval/herb-gold100.jsonl` (the real gold-100 set — I made an empty
`chosen_questions.jsonl` beside it), and existing `run_gold_set()` runners in the
baselines. One graph query surfaced all of it instantly. The user: "you always
just fucking keep adding shit without EVER looking to see if there already exist..
even with the fucking graph you still wont just take a peek."

**How to apply:** The graphify graph exists precisely to surface these relationships
— USE it before creating, not after. CLAUDE.md even says query the active graph
FIRST. One peek (`graphify query`) before any Write. This compounds with
[[dont-over-engineer-stop-and-talk]] and [[delete-dont-preserve]]: less new code,
reuse what's there, keep it lean.

---
name: no-historical-or-defensive-comments
description: "HARD — comments/docs/commits describe ONLY the present state; never narrate a past mistake, a change, or a review finding"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 6cb452f8-96a0-447e-bd1e-19385fd699ca
---

Write every comment, docstring, doc line and commit message to describe ONLY what the
code is and does now — as if it had been written correctly the first time. Never encode
history or self-justification: no "previously X / now Y", "used to", "no longer",
"changed from", "deprecated", "NOT because…", "do NOT factor this out", "deliberately
independent", and no references to specific review findings or their labels.
When something was wrong, REMOVE the wrong thing and write the correct version plainly —
do not leave a comment narrating that it was caught and fixed.

**Why:** narrating a fix reads as if the mistake were a planned effort, invents fake
project history, and — because comments and docs feed the graphify graph and memory —
dilutes the context of every future conversation. The user treats this as actively
harmful, not cosmetic.

**How to apply:** after writing or editing, reread the comments and delete any that only
make sense to someone who knew a prior (wrong) version — a clean codebase carries no
scar tissue. See [[delete-dont-preserve]], [[docs-track-reality]].

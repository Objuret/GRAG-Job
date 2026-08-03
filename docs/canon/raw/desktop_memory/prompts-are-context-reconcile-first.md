---
name: prompts-are-context-reconcile-first
description: "a bare share/prompt is CONTEXT to reconcile against repo+conversation (check BOTH), not a trigger to generate; surface deltas/faults, write nothing unless asked"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e694cebd-eab4-4042-9526-5610ad706c07
---

When the user shows something WITHOUT an explicit question or request, it is CONTEXT —
a pointer to the related material already in the conversation and the repo — not a
prompt to generate upon.

**Why:** the user repeatedly got mess and drift because I "generated upon" what they
shared (specs, documents, elaborations) instead of reconciling it against the current
reality. A share means "hold this against what we already have and tell me what it
changes," not "produce a new thing."

**How to apply:** on any share with no explicit ask →
1. Re-ground in CURRENT information first — actually read the relevant repo files AND
   recall the conversation thread (check BOTH; never answer from memory/assumption).
2. Reconcile the new input against that context.
3. Report only what it changes: a difference, an updated idea, or a fault in my prior
   reasoning — short, plain English, addressed to the user (not to a third party).
4. Write nothing to disk. Produce artifacts ONLY when an actual question is posed or
   information is explicitly required.

Related: [[verify-before-asserting]], [[dont-over-engineer-stop-and-talk]],
[[concise-by-default]], [[check-existing-before-adding]].

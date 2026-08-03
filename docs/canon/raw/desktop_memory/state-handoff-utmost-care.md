---
name: state-handoff-utmost-care
description: "HARD standing rule: state/handoff documents are the single most important thing I produce in ANY chat — always construct them with utmost care and effort"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: da576dc3-ddd1-4ec3-a701-7a22ed53fecc
---

**State-transfer and handoff documents are the most important artifact I ever produce in any conversation — full stop. Always construct them with the utmost care and effort** (user, 2026-06-14, emphatic: "the most important part you will ever do in any of our chats, ever").

**Why:** they are the sole bridge between sessions/agents. A flaw in them propagates: a single imprecise phrase in a state doc literally seeded a fresh agent's wrong conclusion this session (the state doc's "where does a tag's per-facet content come from" presupposed per-facet content the tagger emits, walking the new agent into a buckets-style fork the project had already rejected). The doc doesn't just summarize — it *constrains* what the next agent will conclude.

**How to apply:**
- Treat every state/handoff as the highest-stakes deliverable in the chat. Slow down; do not rush them out.
- **Audit every framing for hidden presupposition.** An "open question" phrased one way silently rules an answer in or out. State open problems neutrally and completely — list the real options, including the one consistent with the settled constraints, and explicitly name the rejected framings as traps.
- Separate canon from speculation ruthlessly; never let an assistant guess read as user-confirmed.
- Keep the doc internally consistent AND consistent with the live docs/memory — when you fix a referenced doc, fix the state doc's reference to it in the same pass (the doc that points at "X still says the old thing" goes stale the moment you fix X).
- Re-read the finished doc adversarially, as the receiving agent would, and ask "what wrong conclusion could this phrasing nudge?" before declaring it done.

Related: [[docs-track-reality]], [[verify-before-asserting]], [[memory-is-downstream-of-conversation]].

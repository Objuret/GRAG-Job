---
name: docs-track-reality
description: "docs must be updated in the same change that alters reality — stale docs are a defect, never a follow-up"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c30735e5-0193-448a-85aa-f4537a0e36e9
---

When a change creates, removes, or redefines anything (code, concepts, schema, workflow), update the docs that describe it as part of the same change — all docs are in scope: `docs/**/status.md`, plan docs, concept docs, `docs/graph_schema.md`, and `AGENTS.md`.

**Why:** The user does not want stale documentation. Docs are treated as part of the deliverable; a doc that contradicts the code is a defect, not a backlog item. Aligns with [[no-silent-fallbacks]] — silently leaving docs wrong is the same failure mode as a silent fallback.

**How to apply:** Before considering a change done, ask which docs its reality touches and update them in the same pass. If a doc can't be fixed in the same pass, flag it explicitly rather than leaving it silently wrong. The repo-level form of this rule lives in `AGENTS.md` "Hard rules" (this project uses AGENTS.md, not CLAUDE.md, as the auto-loaded brief). See [[project-overview]] for the docs layout.

---
name: delete-dont-preserve
description: "Never keep legacy/superseded content, backups, fallbacks, or tests on my own initiative — delete and replace; preservation needs explicit approval"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: da67c924-204c-48ef-82ed-2c851601c35f
---

When superseding a decision or replacing code/content, **delete the old thing outright.** I must NEVER, on my own initiative: keep legacy/old/superseded content (even "demoted" or "for reference"), create backups, leave fallback paths, or leave tests/scripts in place. Any preservation of any kind requires the user's **explicit** approval first.

**Why:** This is a from-scratch thesis artefact ([[v2-build-pipeline]]). Legacy, fallbacks, backups, and stale tests are bloat that pollutes both the codebase and the record. The user has flagged this repeatedly and treats it as a hard rule, not a preference. Sharper extension of [[no-silent-fallbacks]] and [[no-cutting-corners]].

**How to apply:**
- Replacing X with Y → remove X. Do not demote it, comment it out, or keep a "superseded but informative" note.
- Do not invent fallbacks for a chosen path (e.g. "use Y, fall back to Z if slow"). Pick one; if it fails later that's a future decision.
- Do not add backups or leave test scripts behind unless asked.
- Stale defaults that point at the old choice are a defect to fix, not a fallback to keep ([[docs-track-reality]]).
- If preservation genuinely seems warranted, **ask first** — never assume permission.

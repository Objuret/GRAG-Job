---
name: Ground answers in current repo docs, not stale/git-archaeology
description: User burned repeatedly by analysis built on stale/legacy sources and piecemeal restores
type: feedback
originSessionId: 75e34ba8-8222-4dbe-aa92-f838e9ccdc20
---
Before giving design/architecture answers for this repo, read the CURRENT in-repo documentation and code on the correct branch. Do not reason from stale, legacy, or quarantined files; do not substitute git-log/diff archaeology for reading the actual docs.

**Why:** Multiple times this session, answers were built from old `main`-lineage / quarantined-legacy files, and a frontend-only restore created a frankenstein tree — this wasted the user's time and work and drew strong frustration. The user values correctness grounded in the real current source over fast guesses.

**How to apply:**
- When a doc/code reference can't be found in the working tree, say so plainly and resolve it (restore the right branch / ask) BEFORE analyzing — never improvise from whatever stale file is lying around.
- Restore/checkout coherent whole branches, not single subtrees, so docs/backend/frontend stay consistent.
- Git is fine as a tool; the earlier "stop gitting" was about using archaeology to *avoid* reading docs, not a ban on git.
- Terse, blunt, profane feedback from this user = real signal; stop, re-ground, don't get defensive.

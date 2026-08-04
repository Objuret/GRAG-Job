---
name: commit-means-push
description: "When the user asks to commit, it ALWAYS means commit AND push — to a feature branch, never main. Do both without asking; the commit request authorizes the push."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 42699b8f-4ff0-43ba-80ed-d017967a8cab
---

2026-07-23: the user was annoyed that a commit was made but not pushed. Standing rule:
**any time the user asks me to commit, commit AND push in the same pass** — to a feature
branch (e.g. `re-V1-k50`), NEVER main/legacy.

**Why:** they want the work backed up remotely every time, not sitting only in the local
tree; having to ask for the push separately is friction they've now called out.

**How to apply:** after `git commit`, run `git push -u origin HEAD` (current feature
branch). Do not ask permission for the push — "commit" already means both. Never push to
main. Keep the commit-message conventions in [[commit-style-thesis-repo]] (short, human,
no AI/Co-Authored-By footers). Related: [[source-of-truth-djuret-monorepo]].

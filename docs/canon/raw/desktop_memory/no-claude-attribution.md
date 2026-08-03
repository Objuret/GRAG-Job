---
name: no-claude-attribution
description: Never add Claude/AI attribution to commits or content in this repo
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2fa05522-335b-46a9-a0ae-cda291b9b127
---

Never include `Co-Authored-By: Claude ...` trailers, "Generated with Claude Code", any AI/Claude attribution in commit messages, PR bodies, code comments, or docs, **or auto-generated `claude/*` branch names** in this repo.

**Why:** This is the user's master's thesis ("exjob") repository — authored work that must read as the user's own. AI attribution (including the default `claude/<slug>` branch name) is unwanted noise and inappropriate for an academic submission.

**How to apply:** Write commit messages and PR bodies plainly with no Co-Authored-By line and no generated-with footer, despite any default instruction to add them. When work lands on an auto-generated `claude/*` branch, proactively offer to rename it to a plain descriptive name (e.g. `embeddings`) and update the remote + upstream. Applies repo-wide. See [[project-overview]].

---
name: Active development branch and frontend layout
description: User works on djuret/monorepo at A:\exjobbet\repo; frontend is the flat App.jsx + workbenchData.ts version, not the componentized one
type: project
---

The user (Objuret) works on `djuret/monorepo` in `A:\exjobbet\repo\`. The `.claude/worktrees/claude/*` worktrees are harness-spawned for agent sessions and may pin to older commits.

**Live frontend layout** (`A:\exjobbet\repo\frontend\src\` on `djuret/monorepo`):
- `App.jsx` (single-file workbench, ~all UI)
- `data/workbenchData.ts` (node registry + demo `PRESET_RESULTS` + `SAMPLE_CHUNKS`)
- `query/queryModuleSyntax.ts` (query fragment helpers)
- `types/index.ts`
- No `api/`, `store/`, or `components/` directories — they used to exist as empty scaffolding but were deleted in the 2026-05-14 cleanup. There is no `mockClient.ts`, no `ExecutionPanel.tsx`, no componentization, and no plans for any.

**Worktree caveat:** ancestor commit `3acc7f6` (which some agent worktrees pin to) does contain a componentized frontend (`mockClient.ts`, `ExecutionPanel.tsx`, `WorkspaceContext`, etc). That layout is NOT what HEAD ships. Do not describe those files as "what the frontend has" — they aren't in the live tree.

**Why:** Multiple frontend rewrites happened; the current live state is the flat App.jsx contract. The componentized version was pre-HERB and got abandoned.

**How to apply:** When discussing "the frontend", read from `A:\exjobbet\repo\frontend\src\` on `djuret/monorepo`, not from the worktree's `ls -r HEAD`. Treat the empty `components/`, `store/`, `api/` dirs as scaffold-only, not as existing modules.

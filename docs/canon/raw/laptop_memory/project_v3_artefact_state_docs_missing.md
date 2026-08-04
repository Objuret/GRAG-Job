---
name: v3-state-docs-location-onedrive
description: "docs/state + docs/handoff exist on this machine — flat, at the OneDrive additional working directory, not nested under docs/state/ as CLAUDE.md's paths literally suggest"
metadata: 
  node_type: memory
  type: project
  originSessionId: 27d6c6f5-ea37-416d-b391-9a5c122d821a
  modified: 2026-07-27T14:48:43.251Z
---

State-transfer docs are NOT missing on this machine — confirmed present 2026-07-27 at
`C:\Users\jocke\OneDrive - Högskolan Dalarna\Coding\state-transfer\GRAG-Job\*.md` (an additional
working directory in this environment). They sit flat in that folder, not nested under
`docs/state/` / `docs/handoff/` subpaths the way CLAUDE.md's prose names them — same content,
different physical layout on this machine. Confirmed present as of 2026-07-27:
`2026-06-20-v3-contract-vector-arm.md`, `2026-07-17-judge-shootout-rebuilt-artefact-v1-laptop.md`,
`2026-07-20-gold100-shipment-claude-lane.md`, `2026-07-20-v1-query-relative-areas.md`,
`2026-07-22-retrieval-literature-sweep.md`, `2026-07-22-v1-curve-walk-facets-and-cluster-k.md`,
`2026-07-25-combine-clusterk-hybrid-and-judged-eval-usage-burn.md`.

**Why:** an earlier session (21+ days ago) found `docs/state/` absent at that literal repo-nested
path and concluded the docs didn't exist on this machine at all — true for that exact path, false
for the docs' actual existence. Trusting that stale conclusion would mean re-deriving state from
code/output/git archaeology when a direct, authoritative state doc is sitting one directory away.

**How to apply:** when CLAUDE.md's "Session entry point" section names a `docs/state/<file>.md`,
look for `<file>.md` directly under the OneDrive `state-transfer\GRAG-Job\` folder, not under a
`docs/state/` subpath there. Read it before falling back to code/output reconstruction.

**Also worth knowing:** CLAUDE.md's line 1 still names
`2026-07-22-v1-curve-walk-facets-and-cluster-k.md` as the current entry point, but the
2026-07-25 doc (`...judged-eval-usage-burn.md`) says its own results supersede that doc's
curve-walk/cluster-K verdicts (fixed machinery reverses the old loss — see
[[project_v1_lineage_and_cost_delta]] and [[project_combine_sweep_and_hybrid_results]]). CLAUDE.md's
entry-point pointer was never updated to match — check for this drift rather than trusting line 1
literally; the newest-dated doc in the folder is the safer first read.

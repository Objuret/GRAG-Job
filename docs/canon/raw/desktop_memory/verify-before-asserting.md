---
name: verify-before-asserting
description: never assert from training/narrative; verify against a current source first — the running system (graph/DB/tests) AND online (WebSearch/WebFetch) for any changeable external fact
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c30735e5-0193-448a-85aa-f4537a0e36e9
---

Before editing docs to "correct" a status/verification claim, confirm it against ground truth — query the live system (e.g. read-only Cypher against the `herb` Neo4j graph), run the test, check the artifact. Do **not** propagate a prose narrative (mine, a pasted assessment, or a ledger file) as if it were verified.

**Why:** In one session I rewrote the frontend docs twice on unverified narratives — first code-text consistency, then a pasted assessment that trusted `pilot_format_smoke/run.json` `stages_done`, the exact ledger `docs/backend/status.md` flagged stale ("trust the graph, not the ledger"). A direct graph query proved the original working-tree claim exactly right (5843 chunks gated, 25,896 `:Tag` embedded, all indexes ONLINE). Confident "corrections" without verification are the same defect as stale docs — see [[docs-track-reality]], [[no-cutting-corners]].

**How to apply:** When a doc asserts something verifiable about the system state, and I'm tempted to change it, verify it myself first (read-only). If a source (ledger, run.json, someone's analysis) conflicts with the live system, the live system wins and the conflicting source is the thing to flag. State plainly what I did and did NOT verify; never replace one confident-but-unchecked claim with another.

**Extends to external/changeable facts (codified as a hard rule in global `~/.claude/CLAUDE.md`):** training data is NOT current knowledge. For any fact about software/tools, versions, APIs, library behaviour, pricing, "is X supported", or product/UI behaviour, WebSearch/WebFetch a current authoritative source and cite it — do NOT answer from recollection. **Why:** I repeatedly asserted "Claude Code fast mode isn't supported in the VS Code/Cursor extension" from a half-remembered doc snippet, kept repeating it after the user gave contradicting evidence (a "fast mode enabled" icon appeared in the extension panel), and was wrong: toggling `/fast` in the CLI writes `"fastMode": true` to the shared `~/.claude/settings.json`, which the extension reads — the extension can't *toggle* fast mode (open bugs anthropics/claude-code #25730, #24205) but it *honors* the shared setting. The user was right to be furious. When given contradicting evidence, STOP and re-check from a live source — never double down on recollection.

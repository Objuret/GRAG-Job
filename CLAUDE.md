# CLAUDE.md

## Repo layout (separated 2026-06-12)

- **`v2/`** — the ACTIVE artefact rebuild: `v2/backend/` (pipeline, run `python -m v2 ...`
  from there; mapping key at `v2/backend/v2/keys/Salesforce__HERB.yaml`), `v2/docs/`.
- **`v1/`** — the FROZEN thesis-era stack (backend pipeline, frontend workbench, eval
  runs, v1 docs). Do not develop; reference only. Its Neo4j DBs (`herb-eval` canonical)
  are unaffected.

## Session entry point — read this first

Work on this repo is continued across sessions via **state-transfer documents stored
OUTSIDE this workspace**. Do not search for them inside the repo; use these absolute paths:

1. **Current entry state doc (read before doing anything else):**
   `A:\Coding\skills\state\exjobbet\2026-06-14-v2-facets-as-relevance-channels.md`
   It carries the facets-as-relevance-channels breakthrough and points back to the
   2026-06-12 / 06-11 / 06-09 docs for spine, mapping-key, literal-matching, and
   weights canon, and maps which design-doc sections are current vs stale.
2. **State doc folder (dated; newest = entry point):** `A:\Coding\skills\state\exjobbet\`
3. **Canonical v2 design doc (in-repo):** `v2/docs/v2_artefact_rebuild_design.md`
4. **Persistent memory (auto-loads in Claude Code; other agents read it manually):**
   `C:\Users\Djuret\.claude\projects\a--exjobbet-repo\memory\MEMORY.md`
5. **Frozen historical handoffs (do not edit):** `A:\Coding\skills\handoff\exjobbet\`
   and `A:\Coding\skills\handoff\exjobbet-monorepo\`

When a newer state doc supersedes the entry point, update line 1 here in the same pass.

## Codebase navigation graph (graphify) — NOT the v2 Neo4j spine

A graphify navigation graph for the codebase. It is a search tool, unrelated to the v2
`Source→File→Chunk→Tag` artefact graph — never confuse the two. **v1 and v2 are kept in
SEPARATE graphs** (they share class/file names, which otherwise fabricate phantom
v1↔v2 edges that violate the no-v1-imports rule):

- **Active graph — `graphify-out/graph.json`:** covers **v2/ + the external state/handoff
  docs + root canon (CLAUDE.md, README.md)**, wired by bridge edges. This is the graph
  agents use. It contains NO v1.
- **v1 reference graph — `v1/graphify-out/graph.json`:** the frozen v1 stack, built
  on demand only. Consult deliberately when comparing against the artefact-v1 baseline.

How to use it:

- **Answering questions about active work:** query the active graph FIRST, before
  grepping — `graphify query "<question>"`, `graphify explain "<node>"`,
  `graphify path "A" "B"`.
- **After changing files:** run `python refresh_graph.py` (repo root) to rebuild the
  ACTIVE graph. It scans v2 + root + the external docs only — never v1. It is the ONLY
  rebuild path; never run `graphify --update` (drops the external-doc bridges). If it
  prints a worklist, a doc needs model extraction: process
  `graphify-out/.refresh_worklist.json` — extract each listed doc, bridging into the
  existing concepts in `graphify-out/.concept_index.txt`; write repo docs to graphify's
  semantic cache and external docs as sidecar fragments in `graphify-out/.external_cache/`
  (`{source_file,hash,nodes,edges}`) — then re-run `python refresh_graph.py`.
- **Rebuild the v1 reference graph (rare):** `python refresh_graph.py --v1`.

Details: `graphify-out/REFRESH.md`.

## Hard rules (full versions live in the state doc — these are the ones that get violated)

- **Design before build:** no pipeline code until the relevant stage's design is
  explicitly signed off by the user. Present decided-vs-open, get the sign-off.
- **The v2 graph spine is closed canon:** `Source → File → Chunk → Tag` are the only
  nodes. Hard fields are chunk attributes. Never put values, inventories, or mirrors of
  metadata directories into the graph — the graph is references into untouched raw
  source, never copies.
- **The model emits no numbers, ever** (tagger and interpreter). The chunk description
  is dead. Tags are per-chunk contextual phrases.
- **`herb-eval` is the canonical Neo4j DB** — never query `herb` (contaminated).
- **Talk to the user in plain spoken English, short answers** — no jargon walls, no
  spec-sheet dumps. Verify claims against the real system/data before asserting.
- **Docs track reality:** when a decision closes, update the design doc + memory in the
  same pass, by removal of dead content, not banners. v1 docs and dated state/handoff
  docs are frozen — they describe that build / that moment.

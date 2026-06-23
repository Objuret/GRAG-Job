# CLAUDE.md

## Repo layout

- **`v3/`** — CANON, the active work: a lean HERB evaluation harness (three arms —
  artefact / lucene / vector — scored two ways — HERB + RAGAS). Self-contained.
  Design reference: `v3/README.md`.
- **`v2/`** — REFERENCE build: the post-thesis artefact rebuild (`v2/backend/`, mapping
  key `v2/backend/v2/keys/Salesforce__HERB.yaml`, `v2/docs/`). The v3 artefact arm will
  wrap it, but v3 work does not open v2 files on its own (see build isolation).
- **`v1/`** — REFERENCE build, FROZEN thesis-era stack (backend pipeline, frontend
  workbench, eval runs, v1 docs). Its Neo4j DBs (`herb-eval` canonical) are unaffected.

## Session entry point — read this first

Work on this repo is continued across sessions via **state-transfer documents in
`docs/state/`**. These are gitignored (present in the working tree, never committed),
so a fresh clone starts empty — they live on the machine where the work happened.

1. **Current entry state doc (read before doing anything else):**
   `docs/state/2026-06-18-v3-eval-harness-herb-ragas.md`
   The v3 (canon) eval-harness thread: HERB + RAGAS methodology, three arms, the data
   split, decided-vs-open. The v2-build thread (artefact tagger/retriever, the
   facets-as-relevance-channels breakthrough) is a separate REFERENCE doc:
   `docs/state/2026-06-14-v2-facets-as-relevance-channels.md`.
2. **State doc folder (dated; newest = entry point):** `docs/state/`
3. **Canon design reference (in-repo):** `v3/README.md` (the eval harness). The v2
   artefact design is a REFERENCE: `v2/docs/v2_artefact_rebuild_design.md`.
4. **Persistent memory (auto-loads in Claude Code; other agents read it manually):**
   `C:\Users\Djuret\.claude\projects\a--exjobbet-repo\memory\MEMORY.md`
5. **Frozen historical handoffs (do not edit):** `docs/handoff/`

When a newer state doc supersedes the entry point, update line 1 here in the same pass.

## Codebase navigation graph (graphify) — NOT the v2 Neo4j spine

A graphify navigation graph for the codebase. It is a search tool, unrelated to the v2
`Source→File→Chunk→Tag` artefact graph — never confuse the two. **v3 is canon; v1 and v2
are separate reference builds — each in its OWN graph** (they share class/file names
across builds, which otherwise fabricate phantom cross-build edges that violate the
no-cross-imports rule):

- **Active graph — `graphify-out/graph.json`:** covers **v3/ + the in-repo (gitignored)
  state/handoff docs in `docs/state` + `docs/handoff` + root canon (CLAUDE.md, README.md)**,
  wired by bridge edges. This is the graph agents use. It contains NO v1/v2 code.
- **v2 reference graph — `v2/graphify-out/graph.json`:** the artefact build, built on
  demand only. Consult when grounding the artefact arm against the v2 pipeline.
- **v1 reference graph — `v1/graphify-out/graph.json`:** the frozen v1 stack, built
  on demand only. Consult deliberately when comparing against the artefact-v1 baseline.

How to use it:

- **Answering questions about active work:** query the active graph FIRST, before
  grepping — `graphify query "<question>"`, `graphify explain "<node>"`,
  `graphify path "A" "B"`.
- **After changing files:** run `python refresh_graph.py` (repo root) to rebuild the
  ACTIVE graph. It scans v3 + root + those gitignored docs only — never v1/v2. It is the
  ONLY rebuild path; never run `graphify --update` (drops the external-doc bridges). If it
  prints a worklist, a doc needs model extraction: process
  `graphify-out/.refresh_worklist.json` — extract each listed doc, bridging into the
  existing concepts in `graphify-out/.concept_index.txt`; write committed repo docs to
  graphify's semantic cache and the gitignored state/handoff docs as sidecar fragments in
  `graphify-out/.external_cache/` (`{source_file,hash,nodes,edges}`) — then re-run
  `python refresh_graph.py`.
- **Rebuild a reference build (rare):** `python refresh_graph.py --v2` or `--v1`.

Details: `graphify-out/REFRESH.md`.

## Hard rules (full versions live in the state doc — these are the ones that get violated)

- **Design before build:** no pipeline code until the relevant stage's design is
  explicitly signed off by the user. Present decided-vs-open, get the sign-off.
- **Build isolation — the conversation's scope tag is the authority:** v3 is canon and
  self-contained. An `@v3` / `@v2` / `@v1` tag on the conversation sets scope and OVERRIDES
  any doc pointer. Working in v3, NEVER open or read a v1 or v2 file on your own — the v2
  baselines are empty/dead and v2 docs are only partially true and only about v2; open a
  v1/v2 file ONLY if the user hands you that exact file. This overrides every
  grounding/reference pointer in state or handoff docs (e.g. a §9 "source-of-truth" list
  naming v2 artifacts, or a pasted answer name-dropping a v2 path — do NOT follow it).
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
- **No historical or defensive comments:** code, docs and commit messages state only the
  present — what the code is and does now, as if written correctly the first time. Never
  narrate a past mistake, a change, or a review finding — no "previously/now", "no longer",
  "NOT because", "do not factor out", no review-finding labels. Remove the mistake and
  write the correct version plainly; never annotate that something was caught and fixed —
  comments feed the graph and memory, so scar tissue pollutes every future session.
- **Always refresh the navigation graph after changing files:** after any edit to `v3/`,
  root canon, or the external state/handoff docs, run `python refresh_graph.py` (repo root)
  so the active graphify graph tracks reality. It is the ONLY rebuild path (never
  `graphify --update`). If it prints a worklist, process it before the change is done
  (full procedure in the graphify section above).
- **Critical-review the code you write:** after writing or changing code in `v3/`, before
  you report the work done, run `/critical-review` on the file(s) you just changed — you
  know which ones, pass them in. It spawns the read-only `critical-reviewer` and you resolve
  its findings with it until the code converges. Skip only for trivial non-logic edits
  (a rename, a comment, a one-line config tweak).

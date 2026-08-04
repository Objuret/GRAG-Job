---
name: v1-lineage-and-cost-delta
description: "How current artefact_v1 (re-V1-k50) relates to the original thesis v1/ on the v3 branch, and why the old eval was cheap while the current one is expensive"
metadata: 
  node_type: memory
  type: project
  originSessionId: 27d6c6f5-ea37-416d-b391-9a5c122d821a
  modified: 2026-07-27T14:49:12.027Z
---

Current `artefact_v1` and the original thesis `v1/` (still present on the `v3` branch —
confirmed via `git ls-tree v3 -- v1`, absent from this branch's working tree) are NOT two
different graphs. Both query the same Neo4j `herb-eval` database. `v3/pipelines/artefact_v1.py`
defaults to `NEO4J_DATABASE=herb-eval`, `HERB_TAG_RUN_ID=pilot_full_herb` (confirmed by grep,
line 106-108) and says so in its own module docstring. What changed between old and current is
the retrieval engine and the embeddings sitting on top of that graph, not the graph itself.

- **Old `v1/`** (browser workbench — `retrieval.ts` ~818 lines + `interpreter.ts`, deleted from
  this branch): two-pass interpret producing LLM facet scores per tag, per-facet kNN grounding
  (minSim ~0.78), one Cypher score product (w_query × facetScore × w_chunk × w_facet × relevance
  × sim), optional hard-gate filter, cut by whatever the UI asked for. e5-small embeddings, chunk
  text stored directly in the graph.
- **Current `artefact_v1`:** one-pass interpret emitting `{description, parts, gate}` — no
  numbers from the model. Per-part multi-k pooling (8/16/32/64) into an average-linkage
  dendrogram, a shared walk (anchors + widen tightest-first), plus description-area clustering.
  Stated scope corroborates (lifts matches) rather than hard-gates (filters) — the opposite of
  the old behavior. nemotron embeddings; chunk content is stripped from the live graph and
  resolved from raw source by locator/hash instead (references, not copies).
- `v3/artefact/` (native scan/probe/chunk/tag rebuild into a fresh `herb-v3` DB, per CLAUDE.md
  canon) is a separate, still-unfinished third thing — not what `artefact_v1` runs today. Don't
  conflate the two when discussing "the artefact arm."

**Why old was reported "cheap" vs current "expensive":** not a retrieval-efficiency difference —
mostly a fixed-evidence-budget effect.
- Old thesis eval: graph retrieved a median of 15 chunks vs Lucene's 40, AND the RAGAS export
  applied a matched cap to both arms (`answer_max_chunks=40`, 1800 chars/chunk — same rule for
  graph and Lucene). Graph's answer_in came out ~9.4k tokens vs baseline's ~24k (~0.39×) largely
  because its median sat under that shared cap while Lucene's filled it. The interactive
  workbench itself defaulted to no truncation (cap=0); only the eval export capped.
- Current artefact_v1 lost both advantages: it always fills k=50 from pools of often
  hundreds-to-thousands of candidates (no "returns fewer than k" discount), and ships full
  resolved raw chunk text with no truncation cap at all (reported median ~240k chars vs vector's
  ~13k, ~18×, since the shared generator's ~262k context window is treated as big enough). It
  also pays extra per-query costs the baselines don't: Haiku interpret (~26s/q off the det
  cache), NIM query embeds, and the Neo4j walk itself (seconds-to-tens-of-seconds vs vector's
  ~0.01s matmul or Lucene's BM25).

**Why this matters:** a naive "graph vs baseline cost" read from the thesis era doesn't carry
over — the old cheapness was partly a fixed-budget artifact of the export config, not proof the
graph is inherently efficient, and the current expense is structural (full-k, no cap, extra
pipeline stages), not a regression or a bug.

**How to apply:** the matched truncation cap was dropped when the harness was rewritten, not
disproven — reintroducing it (`answer_max_chunks` / `maxChunkChars`, or equivalent) is a
legitimate cost lever, but only if applied identically across all three arms, and only with the
caveat that capped-quality numbers are a different measurement than full-quality numbers (a cap
can cut exactly the chunk an answer needed). Treat this as an open, unresolved lever to surface
next time v1 cost comes up — not a decision already made, and not something to reintroduce
without the user signing off first (design-before-build). One concrete implementation constraint:
per [[project_terminology_canon]] and the 2026-07-25 state doc, `truncate_k` slicing
`context_ids[:k]` is INVALID for the artefact arm because its ids are not 1:1 with chunks (it
returns ~500 ids from ~50 chunks, vs baselines' 1:1 at k=50) — any reintroduced cap has to work
at the chunk/char level (like the old `maxAnswerChunks`/`maxChunkChars`), not by truncating the id
list.

Note on verification: the lineage/architecture claims and the ~500-ids-from-50-chunks id-budget
figure were confirmed directly against the repo and the 2026-07-25 state doc on 2026-07-27
(`git ls-tree`, grep on `artefact_v1.py`, state doc §4/§6). The specific cost multipliers (240k
chars median, ~18×, ~26s/q, etc.) are relayed from a separate analysis session and were NOT found
verbatim in the state doc — still not independently re-derived from raw run logs.

Related: [[project_benchmark_validity_caveats]], [[project_v1_machinery_fix_and_toggles]],
[[project_combine_sweep_and_hybrid_results]]

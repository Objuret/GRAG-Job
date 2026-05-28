# Retrieval Orchestration — Pain Map and Improvement Plan

**Status:** synthesis from repo evidence + observed run behaviour.
Research docs (`research_graph_rag.md`, `research_agentic_rag.md`,
`research_conference_papers.md`) are pending; citations marked **[R:gap]**
will be backfilled when those land.

**Last updated:** 2026-05-22.

---

## 1. Pain × Evidence × Symptom

| # | Pain | Repo evidence | Observable symptom |
|---|------|---------------|--------------------|
| P1 | **Gate is verbatim/LLM-only**; interpreter doesn't know the L0–L4 ontology of the corpus tree | `interpreter.ts` Pass-1 prompt has no corpus-structure vocabulary. `GATE_SECTIONS` is a flat string list, no hierarchy. | Model guesses `section`, mis-maps synonyms, emits null for valid constraints. Gate either over-scopes (scan everything) or mis-scopes (wrong product). |
| P2 | **`section` ≠ doc type**; section is a tree-level locator, not a content taxonomy | `graph_schema.md` `:Chunk` hard fields: `section` is a HERB tree path label (`prs`, `slack`, `documents`). No `doc_type` property. | A prompt asking "meeting notes about X" can't distinguish transcript vs chat vs document about a meeting. |
| P3 | **`employee_id` is misleading**; it's an org-tree locator, not a universal person key | `graph_schema.md`: `employee_id` is `eid_…` from org-tree chunks only. | Queries naming a person by name hit nothing through the gate; `employee_id` is opaque and absent on most chunks. |
| P4 | **Tag overlap `score>0` too soft**; filter lets 100+ chunks through | `retrieval.ts` `scoreCypher`: `WHERE score > 0`. `limit` defaults to `0` (no cap). `minWChunk`/`minRelevanceToFile` default to `0`. | Any chunk sharing one grounded tag with any positive facet score survives. Broad prompts return the entire gated corpus. |
| P5 | **`k=20` amputates because rank is bad** | `interpreter.ts` `DEFAULT_FILTERS.limit = 20`. Answer model sees truncated, badly ordered evidence. | Gold chunk at rank 43 of 100+ returned; `k=20` cuts it. Raising k just widens the haystack. |
| P6 | **Vectors only for Tag-name grounding, not chunk content** | `retrieval.ts` kNN is `db.index.vector.queryNodes('tag_emb_<facet>', …)` — queries `:Tag` nodes, never `:Chunk.content`. No chunk-content embedding index exists. | Retrieval can't find a chunk by what it says, only by which tags the tagger assigned. Chunk with relevant content but weak/missing tag coverage is invisible. |
| P7 | **Naive single-shot answer step** | `answer.ts`: one `chat()` call, `maxTokens: 1024`, no chain-of-thought, no self-critique, no evidence extraction step. Chunks sent as flat `<chunk>` XML. | CR≈1, F<0.5 on hard questions. Model fabricates or ignores evidence. Pays for 100 chunks of context the model doesn't actually use. |
| P8 | **L3 metadata (doc type, author, feedback role) not queryable** | `graph_schema.md`: no `doc_type`, `author`, `feedback_role` on `:Chunk` or `:File`. Data exists inside `locator_json` / chunk content but not materialized. | Can't filter "feedback from managers" or "design docs" without scanning chunk text. |
| P9 | **No shared ontology in code/types** | `types/index.ts` has `FacetDimension` but no type for section hierarchy, product enum, chunk kind taxonomy, or doc-type enum. `GATE_SECTIONS` lives as a string array in `interpreter.ts`. | Every new resolver needs to re-derive valid values. Prompt engineers build long few-shot examples instead of referencing a lookup. |
| P10 | **`minWChunk`/`minRelevanceToFile` inactive** (defaulted to 0) | `retrieval.ts` L488–489: `minWChunk: 0`, `minRelevanceToFile: 0`. `build_input` executor passes `num(node.data?.weightThreshold, 0)`. | The quality floors exist in the Cypher but are never engaged. Low-centrality junk tags contribute to score. |
| P11 | **HERB feedback blobs cause role attribution failure** | Chunk `content` concatenates multi-author feedback without per-message attribution. No `author` or `role` field materialized. | "What did manager X say about Y?" is unanswerable from chunk text alone. |
| P12 | **Paying for tokens the answer model doesn't use** | `answer.ts` sends all retrieved chunks. `maxAnswerChunks` exists but defaults to 0 (all). `maxChunkChars = 1800`. | At 100 chunks × 1800 chars ≈ 45k tokens of context. Model cites 2–4 chunks. 95% of billed input tokens are waste. |
| P13 | **Baseline uses same answer step** | `pipeline.ts` `runRunSpec`: both `tags` and `content` routes call the same `generateAnswer`. | Baseline comparison measures retrieval difference + shared answer noise. Can't isolate retrieval quality from answer quality. |

---

## 2. Pain × Research Concept × Solution Options

**[R:gap]** marks concepts that need paper/source citations from the pending
research docs. Options are ordered by expected impact.

| Pain(s) | Research concept | Solution options |
|---------|-----------------|------------------|
| P1, P9 | **Corpus ontology / schema-aware retrieval** [R:gap — Graph RAG, KAPING, ontology-grounded QA] | **A.** Build a typed `HerbOntology` module: product enum, section hierarchy (L0–L4), chunk-kind taxonomy, doc-type enum. Publish as a TS const + Neo4j `:Ontology` reference nodes. **B.** Feed ontology slice to Pass-1 as structured context (not few-shot examples). |
| P2, P3, P8 | **L3 structured metadata materialisation** [R:gap — RAFT, structured knowledge extraction] | **A.** New `materialize` stage: extract `doc_type`, `author` / `role`, `feedback_direction` from `locator_json` + chunk content heuristics → new `:Chunk` properties. **B.** Index the four new fields (RANGE). **C.** Extend `HardGate` and interpreter vocabulary. |
| P4, P5, P10 | **Reranking / score normalisation** [R:gap — ColBERT, cross-encoder reranking, RankGPT, Lost in the Middle] | **A.** Two-stage retrieve-then-rerank: broad recall (no score floor, high k) → LLM or cross-encoder rerank on top-N → truncate. **B.** Activate `minWChunk ≥ 0.15` and `minRelevanceToFile ≥ 0.1` as quality floors after rerank. **C.** Score normalisation: divide `edgeContrib` by max per prompt tag so prompt tags contribute proportionally. |
| P6 | **Hybrid retrieval (vector + graph + lexical)** [R:gap — HippoRAG, GraphRAG local/global, RAPTOR] | **A.** Add chunk-content embeddings (`Chunk.emb_content`, single vector index). Use as a parallel recall lane, merge with tag-overlap lane by RRF. **B.** Lexical BM25 over `chunk_fulltext` as third recall lane (already gated, underused). **C.** Final ranking = RRF(tag_overlap, content_kNN, lexical). |
| P7 | **Multi-step answer generation** [R:gap — Chain-of-Thought, Self-RAG, CRAG, Agentic RAG] | **A.** Pre-answer extraction step: for each retrieved chunk, extract the exact quote(s) relevant to the query → feed only quotes to the answer model. **B.** Structured output: answer + `evidence[]` with chunk-id + quote. **C.** Self-consistency check: if answer contradicts extracted evidence, retry or refuse. |
| P12 | **Context window management** [R:gap — Lost in the Middle, LongRAG] | **A.** After rerank, send only top-N (e.g. 10) chunks to answer. **B.** Extractive pre-step (P7-A) reduces each chunk to its relevant quote, cutting tokens 5–10×. **C.** Set `maxAnswerChunks = 10` as the default today (zero-code change). |
| P11 | **Multi-author attribution** [R:gap — entity-centric retrieval, dialogue-act tagging] | **A.** Backend: split feedback blobs into per-message chunks with `author` + `role` fields. **B.** Materialize `author` on `:Chunk` and index it. **C.** Extend gate: `author`, `role` become first-class filters. |
| P1, P13 | **Question routing / decomposition** [R:gap — Adaptive RAG, query classification, DSPy] | **A.** Route classifier before interpret: `structural` (gate-only, no tags needed) / `semantic` (current path) / `hybrid` / `sql` / `refusal`. **B.** Structural queries skip grounding and go straight to the materialised metadata. **C.** SQL arm for count/aggregate queries (existing `sql_agent` route, needs in-browser option or light API). |
| P5, P4 | **Iterative retrieval** [R:gap — IRCoT, FLARE, Active RAG] | **A.** If reranked top-10 has low max score, automatically broaden: relax gate, expand grounding k, try content embedding. **B.** If answer model says "insufficient evidence", trigger a second retrieval pass with relaxed constraints. |

---

## 3. What NOT to do

These are dead ends that look tempting but don't address root causes.

| Anti-pattern | Why it fails |
|--------------|-------------|
| **Verbatim gate as the sole structural lever** | The interpreter hallucinates gate values it hasn't been taught. Fixing it means teaching it the ontology (Wave 0), not adding more string fields to guess. |
| **Regex product/section extraction** | Brittle on synonyms, abbreviations, and multi-product queries. The ontology resolver (Wave 1) handles this properly with a lookup + fuzzy match, not regex. |
| **Raising `k` without reranking** | `k=50` returns 50 chunks the answer model can't use. The problem is rank quality, not recall volume. Rerank first (Wave 3), then decide k. |
| **100-chunk haystack to the answer model** | Costs tokens, degrades answer quality (Lost in the Middle). Solve with rerank + extractive pre-step, not by hoping the model will sort through noise. |
| **Lowering `score > 0` threshold** | It's already at rock bottom. The problem is that the scoring function gives positive scores to irrelevant chunks. Fix the scoring (normalise, rerank), don't lower the floor. |
| **One-shot k-only caps** | Setting `limit=20` without fixing rank puts a ceiling on recall with no floor on precision. The gold hit moves around; a static k amputates it. |
| **Building chunk-content vectors without tag-overlap** | Content vectors alone lose the structured facet signal. They're a complementary recall lane (RRF), not a replacement for the tag-overlap path. |
| **Prompt engineering the answer call** | The answer prompt is fine; the problem is what goes into it (badly ranked, un-extracted evidence). Fix upstream retrieval and add extraction before touching the answer prompt. |

---

## 4. Implementation Waves

Dependencies flow downward: each wave assumes the prior wave is done.

### Wave 0 — Ontology and types (no retrieval change, pure infrastructure)

**Goal:** every downstream wave has a shared vocabulary to reference.

| Task | Detail | Files touched |
|------|--------|---------------|
| 0-A. `HerbOntology` TS module | `product: string[]`, `sectionHierarchy: Record<L0, L1[]>`, `chunkKindTaxonomy`, `docTypeEnum`, `feedbackRoleEnum`. Exported as a const from `src/ontology/herb.ts`. | new `src/ontology/herb.ts`, update `types/index.ts` |
| 0-B. Ontology reference in Neo4j | `:OntologyNode` with `(kind, value)` key, linked to `:Source`. Optional — only if resolvers need graph-side lookup. | `schema/constraints.cypher`, `bootstrap_schema.py` |
| 0-C. Extend `HardGate` type | Add `doc_type`, `author`, `role` as nullable fields. Gate builder and validator updated. Inactive until Wave 2 materialises them. | `interpreter.ts`, `retrieval.ts` |
| 0-D. Typed section/product enums | Replace `GATE_SECTIONS` string array with `HerbOntology.sections`. Same for products. | `interpreter.ts` |

**Dependency:** none.
**Risk:** low — additive, no behaviour change.

### Wave 1 — Structural resolver (interpreter uses the ontology)

**Goal:** Pass-1 gate extraction is accurate and inspectable.

| Task | Detail |
|------|--------|
| 1-A. Ontology-aware Pass-1 prompt | Feed `HerbOntology` slice as structured context to the interpreter system message. Model picks from the enum, not from memory. |
| 1-B. Fuzzy resolver | Post-LLM: fuzzy-match the model's `product` / `section` output against the ontology enum. Levenshtein + alias map. Drops unknown values to null with a warning, never silently passes them. |
| 1-C. Route classifier | Before interpret: classify the prompt as `structural` / `semantic` / `hybrid` / `count_aggregate` / `refusal`. Structural queries skip grounding entirely and go straight to gate + metadata query. |
| 1-D. Active quality floors | Set `minWChunk = 0.15`, `minRelevanceToFile = 0.1` as defaults on `build_input`. Tunable in Run Builder. |

**Dependency:** Wave 0 (ontology types).
**Risk:** medium — changes interpreter output shape; needs eval pass.

### Wave 2 — L3 materialisation (doc type, author, role)

**Goal:** L3 metadata is queryable without scanning chunk text.

| Task | Detail |
|------|--------|
| 2-A. New `materialize` fields | `doc_type`, `author`, `role`, `feedback_direction` on `:Chunk`. Derived from `locator_json` + heuristics on `content` (e.g. "From: name" patterns in feedback, `kind` mapping for doc type). |
| 2-B. RANGE indexes | On the four new fields, same pattern as existing gate fields. |
| 2-C. Interpreter vocabulary | Extend Pass-1 prompt with `doc_type` and `author` vocabulary from the ontology. |
| 2-D. Gate integration | `buildGate` emits `AND c.doc_type = $g_doc_type` etc. `validateGate` validates against live corpus. |

**Dependency:** Wave 0 (types), Wave 1 (resolver).
**Risk:** medium — backend `materialize` stage needs to be extended and re-run. Heuristics for author extraction may need tuning per section type.

### Wave 3 — Rerank + extractive pre-step (the answer quality wave)

**Goal:** gold chunk appears in top-5; answer model sees only relevant quotes.

| Task | Detail |
|------|--------|
| 3-A. Broad recall | Remove `limit` from the scoring Cypher (already `0` = no cap). Use `minWChunk` / `minRelevanceToFile` as the recall floor (Wave 1-D). |
| 3-B. Cross-encoder or LLM rerank | After scoring, rerank top-50 (or all gated) with a cross-encoder (e.g. `ms-marco-MiniLM`) or LLM judge (`Is this chunk relevant to the query? Score 0–1.`). Keep top-10. |
| 3-C. Extractive pre-step | For each top-10 chunk, LLM extracts the exact quote(s) answering the query. Output: `{ chunkId, quote, relevance_reasoning }[]`. |
| 3-D. Slim answer call | Feed only the extracted quotes (not full chunks) to the answer model. Structured output: `{ answer, citations: { chunkId, quote }[] }`. Cuts input tokens 5–10×. |
| 3-E. Chunk-content vector lane (optional) | Add `Chunk.emb_content` (384-d e5). New vector index `chunk_emb_content`. Parallel recall merged with tag-overlap via RRF before rerank. |

**Dependency:** Wave 1 (quality floors active, route classifier can short-circuit).
**Risk:** high — adds latency (rerank + extraction = 2 extra LLM calls or 1 cross-encoder). Must be evaluated head-to-head vs single-shot.

### Wave 4 — Question routing + iterative retrieval

**Goal:** the system picks the right retrieval strategy per question type.

| Task | Detail |
|------|--------|
| 4-A. Router integration | Route classifier (Wave 1-C) drives the pipeline: `structural` → gate-only metadata query; `semantic` → full tag path; `hybrid` → both; `count_aggregate` → SQL arm; `refusal` → don't retrieve. |
| 4-B. Iterative retrieval | If reranked top-10 max score < threshold, automatically broaden: relax gate, expand grounding k, try content embedding. Cap at 2 iterations. |
| 4-C. SQL in-browser (optional) | Light SQL executor against a local SQLite (or the graph via Cypher aggregates) for count/aggregate queries without the Python `sql_agent` round-trip. |
| 4-D. Decomposition | For multi-part questions, decompose into sub-queries, retrieve independently, merge evidence, answer once. |

**Dependency:** Wave 3 (rerank provides the quality signal for iteration decisions).
**Risk:** high — agentic loop complexity; needs robust stopping criteria.

### Wave summary

```text
Wave 0 ─ ontology/types ──┐
                           ├─ Wave 1 ─ structural resolver ──┐
                           │                                  ├─ Wave 2 ─ L3 materialise
                           │                                  └─ Wave 3 ─ rerank/extract ──── Wave 4 ─ routing/iteration
                           └──────────────────────────────────────────────────────────────────────────────────────────────
```

**Minimum viable improvement for thesis eval:** Waves 0 + 1 + the `maxAnswerChunks=10` default (one line change in `answer.ts` or `build_input` node data). This fixes the gate accuracy, activates quality floors, and stops paying for 90 unused chunks — no reranker or new embeddings needed.

---

## 5. Open Questions (for user decision)

| # | Question | Options | Default recommendation |
|---|----------|---------|----------------------|
| Q1 | **Keep or kill the verbatim gate?** | A. Kill it, use ontology resolver only. B. Keep as a fast path for exact-match queries, resolver as fallback. | B — keep for exact matches but always validate through the ontology enum. |
| Q2 | **SQL arm scope** | A. Export-only (current). B. Light in-browser Cypher aggregates. C. Full in-browser SQL via sql.js. | B for thesis, C is optional and adds complexity. |
| Q3 | **Reranker: cross-encoder vs LLM?** | A. Cross-encoder (fast, ~50ms for 50 chunks, needs ONNX in browser). B. LLM rerank (slower, ~2s, richer signal). C. Both — cross-encoder as fast filter, LLM as final rerank on top-10. | A for thesis (latency), C for production. |
| Q4 | **Chunk-content embeddings** | A. Add them now (Wave 3-E). B. Skip — tag-overlap + rerank is sufficient for HERB's tag density. | B for thesis — HERB has ~47 tags/chunk average; tag coverage is high. Content vectors help more on sparse-tag corpora. |
| Q5 | **Author extraction heuristics** | A. Rule-based (regex on "From:", Slack message format). B. LLM extraction (accurate but costly re-tagging). | A — HERB feedback and Slack chunks have regular formats. |
| Q6 | **`maxAnswerChunks` default** | A. 10 (safe, saves tokens). B. 0 (no cap, current). C. Adaptive based on rerank scores. | A now, C when reranker lands. |
| Q7 | **Where does the extractive pre-step run?** | A. Browser (Anthropic call, same as interpret). B. Backend batch (cheaper for eval). | A for interactive, B for headless harness. |

---

## Appendix: Research gaps to fill

These docs should be written and will backfill **[R:gap]** citations above:

| Doc | Scope |
|-----|-------|
| `research_graph_rag.md` | Graph RAG (Microsoft), KAPING, HippoRAG, RAPTOR, G-Retriever — ontology-grounded and graph-structured retrieval. |
| `research_agentic_rag.md` | Self-RAG, CRAG, Adaptive RAG, IRCoT, FLARE, DSPy — multi-step and agentic retrieval patterns. |
| `research_conference_papers.md` | RAFT, Lost in the Middle, RankGPT, ColBERT v2, BGE reranker — reranking and context window management. |

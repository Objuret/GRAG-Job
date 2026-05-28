# Retrieval & Answer Pipeline — Pain Catalog + Solution Map

**Scope:** HERB graph-RAG monorepo (`a:/exjobbet/repo`). Code-evidenced pains
mapped to modern (2024–2026) solutions with recommended implementation
sequence.

**Generated:** 2026-05-22.

---

## 1. Pain Catalog

### P1 · Hard gate is broken (verbatim LLM extraction, no ontology awareness)

| | |
|---|---|
| **Severity** | High |
| **Files** | `interpreter.ts:117–137` (parseGate), `retrieval.ts:29–41` (buildGate), `retrieval.ts:49–91` (validateGate) |
| **Symptom** | Gate depends on the LLM producing exact materialized values (`section`, `employee_id`, `product`, `channel`). Section is a corpus-layout label (`slack`, `prs`, `documents`), not a document type. `employee_id` gates on org-tree `eid_…` values, but questions mention people *by role or name in text*, not by `eid_`. A question about "Slack chat" from someone named in a meeting transcript gets gated to `section=slack`, excluding the transcript. |
| **Eval evidence** | `gold_personalizeforce_34` permanently fails: interpreter emits a gate the corpus cannot satisfy. Eval report: "invalid hard gate". |
| **Root cause** | `parseGate()` is a regex/whitelist normaliser, not a corpus-resolved linker. `GATE_SECTIONS` is a hardcoded enum (`interpreter.ts:117–120`). The interpreter prompt says "map synonyms, e.g. pull requests → prs" — this is verbatim string matching, not entity resolution. |

### P2 · Ontology unclear across the chain (L0–L4 conflation)

| | |
|---|---|
| **Severity** | High (design) |
| **Files** | `graph_schema.md:72` (Chunk.kind), `graph_schema.md:84–106` (hard fields), `interpreter.ts` (gate vs tags), `retrieval.ts` (section ≠ kind ≠ format_family) |
| **Symptom** | Three separate axes are never named as a vocabulary: **surface type** (`format_family`: json, jsonl, parquet), **corpus section** (`section`: slack, documents, prs — a data-layout concept), and **record semantics** (`kind`: product_profile, qa_record, slack_thread_batch, document, meeting_transcript). The interpreter prompt conflates "section" with content type. A query about "meeting transcripts" maps to `section=meeting_transcripts` (correct) but can't express "find a *definition* in any meeting transcript" (that's kind + evidence facet). |
| **Root cause** | No typed ontology layer. The five HERB facets (topic/entities/activity/temporal/evidence) cover semantic tags but not structural metadata. `kind` is materialized on chunks but not gateable or filterable in retrieval (`retrieval.ts` WHERE clauses do not reference `c.kind`). |

### P3 · Tag overlap too soft (`score > 0` passes everything)

| | |
|---|---|
| **Severity** | High |
| **Files** | `retrieval.ts:253` (`WHERE score > 0`), `queryModuleSyntax.ts:47` (same), `pipeline.ts:488` (`minWChunk: 0`), `interpreter.ts:113` (`min_w_chunk: 0`) |
| **Symptom** | Default `minWChunk=0`, `minRelevanceToFile=0`, no score floor beyond `> 0`. 100+ chunks returned for broad queries. Eval report: "graph median ~120 chunks" at uncapped, precision@200 ~0.04–0.06. Even at k=40 the graph arm returns median 15 chunks but context_precision median is **0.00**. |
| **Root cause** | The scoring formula multiplies many soft floats (`w_query × facetScore × w_chunk × w_facet × relevance_to_file × scopeWeight`). Any non-zero product passes. There is no reranking or score-gap cutoff. The system relies on ORDER BY score DESC + LIMIT, but default limit is 0 (= no limit). |

### P4 · Vectors only for tag-name grounding, no chunk-level retrieval

| | |
|---|---|
| **Severity** | High |
| **Files** | `embeddings.ts` (tag-level embeddings only), `retrieval.ts:10–17` (TAG_VECTOR_INDEX per facet), `graph_schema.md:127–143` (Tag embedding vectors) |
| **Symptom** | e5-small-v2 embeds `:Tag` names — a vocabulary-level lookup. There are no chunk-level vectors. A question about a specific passage can only be found if a matching tag was minted during extraction. Lexical fallback (`chunk_fulltext`) is the only sub-tag path and is gated to hard-gate-only scenarios. |
| **Root cause** | Design decision: tag vocabulary grounding was the graph-RAG contribution. But it means retrieval is ceiling-bounded by tagger coverage — chunks with no matching tag are invisible to the weighted path. |

### P5 · Answer step is naive single-shot RAG

| | |
|---|---|
| **Severity** | High |
| **Files** | `answer.ts:80–123` (generateAnswer), `pipeline.ts:239–249` (answer executor) |
| **Symptom** | One LLM call. System prompt: "answer using only provided chunks, cite by id." No extractive pre-pass, no reranking, no verification, no multi-hop. Gold evidence at rank 43 while the answer comes from rank 19 (hypothetical from eval data — the system has no way to surface buried evidence). |
| **Root cause** | `generateAnswer()` takes sorted chunks, formats them as `<chunk>` XML, and sends one chat completion. `maxAnswerChunks` defaults to 200 in export, meaning the LLM receives enormous context with no prioritisation beyond score order. |

### P6 · CR=1, F<0.5 split (recall vs extraction failure)

| | |
|---|---|
| **Severity** | Medium-High |
| **Files** | `ragas_eval_report.md:180–184` (results table) |
| **Symptom** | Context_recall median is 1.00 for baseline, 0.86 for graph — the evidence IS often retrieved. But context_precision median is 0.00 for both, and faithfulness is ~0.80. The answer LLM has the evidence but can't extract it from the noise. |
| **Root cause** | Too many irrelevant chunks dilute the signal. The answer prompt doesn't highlight which chunks are most relevant. No extractive pass to surface gold passages before generation. |

### P7 · L3 not queryable (doc type, author, feedback not materialized for filter)

| | |
|---|---|
| **Severity** | Medium |
| **Files** | `graph_schema.md:84–106` (hard fields), `retrieval.ts:32` (only product/section/channel/employee_id gated) |
| **Symptom** | `kind` (document type: product_profile, meeting_transcript, qa_record), `doc_field`, `metadata_section`, `subsection` are materialized on chunks but **not filterable** in retrieval. The WHERE clause in `buildGate()` only knows four fields + years. A query like "find the market research report for ActionGenie" can't gate on `kind=document` or document type. |
| **Root cause** | Gate was designed for the four hardest constraints. `kind` and other structural fields were added in materialize but never wired into the retrieval gate. |

### P8 · Interpreter/agents lack schema (no shared contract)

| | |
|---|---|
| **Severity** | Medium |
| **Files** | `interpreter.ts:163–182` (system prompt is a long string), `interpreter.ts:200–213` (Pass 2 prompt) |
| **Symptom** | The interpreter system prompt describes the gate fields, facets, and output shape as prose in a string. No JSON Schema, no Pydantic model, no zod validation. Output is parsed with `extractJson()` which does brace-matching. The LLM can produce any shape; validation is post-hoc string matching. |
| **Root cause** | Browser-only architecture means no Python Pydantic. TypeScript interfaces (`QueryPlan`, `HardGate`) exist but aren't enforced at the LLM boundary. |

### P9 · Baseline uses the same dumb answer step

| | |
|---|---|
| **Severity** | Medium |
| **Files** | `pipeline.ts:496–511` (contentRoutePlan), `ragas-export.ts:249–265` (BASELINE_PLAN), `answer.ts:80–123` |
| **Symptom** | A/B comparison (graph vs Lucene baseline) uses identical `generateAnswer()`. Both arms suffer the same answer-quality ceiling. The comparison measures retrieval quality only, but the reported metrics (faithfulness, answer_correctness) are answer-quality metrics — they're bottlenecked by the shared answer step, not by retrieval. |
| **Root cause** | Intentional design for thesis fairness (same answer model). But it means the eval can't distinguish "retrieval found it but answer couldn't extract it" from "retrieval missed it". |

### P10 · k=20 hurt accuracy (rank failure, not k failure)

| | |
|---|---|
| **Severity** | Medium |
| **Files** | `interpreter.ts:113` (`limit: 20`), `retrieval.ts:457–459` (retrievalLimit) |
| **Symptom** | Default plan limit is 20. Gold evidence may be at rank 43. Increasing k doesn't help because the *ranking* is wrong — it pulls in more noise. |
| **Root cause** | No reranking. Score ordering is a product of soft weights, not a learned relevance function. |

### P11 · SQL agent exists as proper tool loop but separate arm

| | |
|---|---|
| **Severity** | Low-Medium |
| **Files** | `sql_agent.py:1–605` |
| **Symptom** | The SQL agent is a proper agentic loop (tool calls, schema introspection, iterative refinement) but lives in a completely separate Python process. The graph arm has no tool-use capability. The SQL agent demonstrates what agentic retrieval looks like — but only over a relational projection, not the graph. |
| **Root cause** | Architecture split: graph = browser-only TS, SQL = Python backend. No shared agent framework. |

### P12 · minWChunk / minRelevance often 0 — inactive filters

| | |
|---|---|
| **Severity** | Medium |
| **Files** | `interpreter.ts:113` (`min_w_chunk: 0, min_relevance_to_file: 0`), `pipeline.ts:175–176`, `retrieval.ts:488–489` |
| **Symptom** | Both threshold knobs default to 0. `retrieval.ts:239`: `AND coalesce(r.w_chunk, 0.0) >= $minWChunk` — with $minWChunk=0 this is always true. Same for relevance_to_file. The filters exist in the UI but are inactive by default, providing no selectivity. |
| **Root cause** | Conservative defaults to avoid false negatives. But it means every chunk with any tag match passes. |

### P13 · HERB feedback blobs cause role attribution failures

| | |
|---|---|
| **Severity** | Medium |
| **Files** | `answer.ts:31–48` (scrubApiText), `ragas_eval_report.md:85–89` (API JSON body rejection) |
| **Symptom** | HERB Slack exports contain broken unicode, surrogate pairs, and control characters that break OpenAI-compatible JSON bodies. 14 initial failures in export, 9 graph + 5 baseline. Even after scrub, large feedback blobs with interleaved speakers make it hard for the answer LLM to attribute statements to the right person. |
| **Root cause** | Raw corpus text quality. Chunker preserves original text verbatim. No speaker-role normalisation in the chunk pipeline. |

### P14 · Payment for tokens model doesn't use

| | |
|---|---|
| **Severity** | Medium |
| **Files** | `ragas_eval_report.md:56–61` (token stats), `answer.ts:53–67` (prepareChunksForAnswer) |
| **Symptom** | Graph arm: median 9,422 answer_in tokens. Baseline: median 24,289 tokens. At limit=0 pilot, chunks grow to 1,000+. `maxAnswerChunks` caps the count but default is 200. The answer model receives enormous context, most of which it ignores (citation pctUsed is typically <20%). |
| **Root cause** | No reranking or dynamic context selection. The system sends everything retrieval returns to the answer LLM. |

---

## 2. Solution Map

### S1 · Corpus-resolved entity linking (for P1, P7, P8)

**Problem:** Gate values must be exact materialized strings; no entity resolution.

| Approach | Fit for THIS repo | Effort | Effect |
|---|---|---|---|
| **A. Pre-index entity vocabulary + fuzzy lookup** — build a lookup table of (name → eid, role → eid, channel_name → channel_id) at materialize time. The interpreter calls a deterministic resolver, not the LLM. | **Best fit.** `stage_materialize()` already extracts structural fields. Add a vocabulary export step. The interpreter sends candidate names to a resolver function before emitting the gate. | Medium (2–3 days) | Fixes P1 directly; employee and channel gates work from natural language. |
| **B. BYOKG-RAG multi-strategy linking** (EMNLP 2025) — use LLM + graph retrieval tools to resolve entities iteratively. | Overkill for HERB's fixed vocabulary. Good reference for a future multi-corpus system. | High | Would handle open-domain entities but adds latency and complexity. |
| **C. Extend gate to `kind` + doc_type filter** — add `kind` and `doc_field` to the gateable fields in `buildGate()` and the interpreter prompt. | **Quick win.** 6 lines in `retrieval.ts`, 2 lines in interpreter prompt. | Low (hours) | Fixes P7 directly; enables "find meeting transcripts about X". |

**Recommendation:** A + C together. The resolver (A) handles people/channels; extended gate (C) handles structural filtering.

### S2 · Explicit ontology layer (for P2)

**Problem:** section ≠ kind ≠ format_family conflated; no named vocabulary.

| Approach | Fit | Effort | Effect |
|---|---|---|---|
| **A. Define L0–L4 as a typed schema** — corpus placement (dataset), container format (json/jsonl), surface type (section), record semantics (kind), semantic tags (facets). Export as a JSON schema; reference in interpreter prompt. | **Best fit.** Doesn't require new infrastructure — just naming what already exists. | Low-Medium | Makes the interpreter prompt precise; reduces hallucinated gate values. |
| **B. OG-RAG / OntoRAG** (EMNLP 2025) — derive a formal ontology from the corpus and anchor retrieval in it via hypergraph edges. | Academically interesting but the HERB corpus already has a well-defined structure. The ontology is implicit in `kind` + `section` + facets — it just needs to be named. | High | Would improve retrieval on an open-domain corpus; marginal here. |

**Recommendation:** A. This is a documentation + prompt + type-definition task, not an infrastructure build.

### S3 · Score-gap cutoff + reranking (for P3, P6, P10, P14)

**Problem:** `score > 0` passes everything; no reranking; gold buried at rank 43.

| Approach | Fit | Effort | Effect |
|---|---|---|---|
| **A. Cross-encoder reranker (Cohere Rerank 3.5 or BGE-reranker-v2)** — after graph retrieval returns N chunks, rerank the top-100 with a cross-encoder, keep top-k. | **Highest impact.** Directly addresses the "gold at rank 43" problem. Cohere API: trivial integration; local BGE: needs a Python sidecar or ONNX in browser. | Medium (1–2 days for API, 3–5 for local) | Fixes P3, P6, P10, P14 in one stroke. Expected: +15–30pp context_precision. |
| **B. Dynamic k selection** (SAGE, 2025) — classify the query and predict optimal k based on score distribution. | Good complement to A but not a substitute. | Medium | Reduces noise on easy queries; still needs reranking for hard ones. |
| **C. Score-gap / elbow cutoff** — after scoring, find the first large gap in the sorted score list and cut there. | **Quick win** that doesn't require an external model. | Low (hours) | Cheap noise reduction. Won't fix rank quality but reduces context size. |
| **D. Reciprocal Rank Fusion (RRF)** — fuse graph-scored and lexical results with `1/(k+rank)` weighting. | **Good complement** — adds a lexical recall signal to the graph ranking. | Low-Medium | Improves recall on literal queries where tags don't cover the term. |

**Recommendation:** C (immediate) → A (next) → D (complement). Score-gap cutoff is a one-function addition. Cross-encoder reranking is the single highest-ROI change for answer quality.

### S4 · Chunk-level dense retrieval (for P4)

**Problem:** No chunk embeddings; retrieval is ceiling-bounded by tagger coverage.

| Approach | Fit | Effort | Effect |
|---|---|---|---|
| **A. Hybrid: tag-scored + chunk-vector union** — embed chunks with e5 (same model), add a `chunk_emb` vector index, union top-50 from both paths, then rerank. | **Best fit.** MS-RAG (EMNLP 2025) shows multi-semantic recall (chunk + relation + entity) yields +10–30% over single-path. The model is already bundled. | Medium-High (3–5 days: embed ~5k chunks, add index, union logic) | Removes the tagger-coverage ceiling. Chunks with no matching tag become reachable. |
| **B. GraphRAG-V community detection** — cluster chunk vectors, retrieve communities. | Interesting for global queries ("summarize all security concerns"). Doesn't help point queries. | High | Marginal for this corpus size. |
| **C. Keep tag-only, improve tagger coverage** — re-run extraction with better prompts to mint more tags. | Cheap but doesn't solve the architectural gap. | Low | Incremental; still misses passages with no tag. |

**Recommendation:** A. The e5 model is already there; the main work is batch-embedding ~5k chunks and adding a vector index + union path in retrieval.ts.

### S5 · Extractive answer pass / agentic answer (for P5, P6, P9, P14)

**Problem:** Single-shot paste, no extractive pass, gold buried in noise.

| Approach | Fit | Effort | Effect |
|---|---|---|---|
| **A. Two-pass answer: extract then synthesize** — Pass 1: for each chunk, extract the sentence(s) that answer the question (extractive). Pass 2: synthesize from extracted sentences only. | **Best fit for thesis scope.** Directly addresses "evidence found but answer missed it". Can be done with the same Anthropic API. | Medium (2–3 days) | Fixes P5, P6. Expected: +10–20pp faithfulness, +20pp answer_correctness. Cuts token waste (P14). |
| **B. Full agentic loop (LangGraph-style)** — plan → retrieve → critique → re-retrieve → answer, with tool calls. | The SQL agent already shows this works. But building it for the graph arm in the browser is a major architecture change. | High (1–2 weeks) | Maximum quality ceiling. Overkill for thesis timeline. |
| **C. Rerank + truncate before answer** — use S3 reranking to select top-10 chunks, then feed only those to the answer LLM. | **Quick win** that composes with S3. | Low (hours, given S3) | Reduces token waste; doesn't improve extraction from within a chunk. |

**Recommendation:** C (immediate, couples with S3) → A (next). The extractive pass is the most impactful single change to answer quality after reranking.

### S6 · Question-type routing (for P10, P11)

**Problem:** All queries go through the same interpret → ground → score path.

| Approach | Fit | Effort | Effect |
|---|---|---|---|
| **A. Classify into lookup / semantic / aggregation / list** — use a lightweight classifier (TF-IDF + logistic regression achieves 93% accuracy per RAGRouter-Bench 2025). Route lookup queries to lexical + gate, semantic to tag-scored, aggregation to SQL agent. | **Good fit.** The SQL agent already exists as a proper tool-loop arm. Routing would let the pipeline pick the best arm per question instead of running all questions through the graph path. | Medium (2–3 days) | Fixes P10 for lookup queries; leverages P11's SQL agent; reduces unnecessary LLM calls. |
| **B. EA-GraphRAG adaptive routing** — use syntax-aware complexity analysis to choose between dense RAG and graph RAG dynamically. | Requires training a router on the HERB question distribution. | High | Academic interest; TF-IDF classifier is simpler and nearly as good. |

**Recommendation:** A. Simple classifier in the interpreter step; route to the existing SQL agent for structured lookups.

### S7 · Schema-enforced interpreter output (for P8)

**Problem:** Interpreter output is free-form JSON parsed by brace-matching.

| Approach | Fit | Effort | Effect |
|---|---|---|---|
| **A. Structured output / tool-use mode** — use Anthropic's tool-use API with a JSON schema for the plan. The model returns a tool call with typed fields; no parsing needed. | **Best fit.** Anthropic tool-use is production-ready. Drop `extractJson()` entirely. | Low-Medium (1 day) | Eliminates parse failures; enforces gate field types at the API level. |
| **B. Zod schema + runtime validation** — define the plan shape with zod, validate after extraction, retry on failure. | Good complement to A; adds a second validation layer. | Low (hours) | Catches edge cases the API schema doesn't cover. |

**Recommendation:** A + B. Tool-use for the LLM call; zod for the TypeScript boundary.

### S8 · Metadata-enriched filtering (for P7, P13)

**Problem:** Doc type, author, feedback structure not queryable; raw text quality issues.

| Approach | Fit | Effort | Effect |
|---|---|---|---|
| **A. LLM-generated chunk metadata** (Enterprise RAG, 2025) — during materialize, generate per-chunk metadata summaries (doc_type, author, topic keywords). Store as chunk properties. | Partially done: `description`, `relevance_to_file` already exist. Extend with `doc_type` from `kind` mapping. | Low-Medium | Makes P7 queryable without changing the gate architecture. |
| **B. Speaker-role normalisation for Slack/transcript chunks** — pre-process to tag speaker turns with resolved employee names/roles. | **Addresses P13 directly.** | Medium | Fixes attribution failures in feedback-heavy chunks. |

**Recommendation:** A (extend materialize) + B (for Slack chunks).

---

## 3. Recommended Implementation Sequence

### Phase 0 — Quick Wins (1–2 days, no architecture change)

1. **Score-gap cutoff** (S3-C): Add an elbow/gap detector after `scoreGroundedChunks`. Cut the result list at the first score gap > 50% of the running mean. Immediately reduces noise for P3, P12, P14.
2. **Activate default filters** (P12): Set `min_w_chunk: 0.05`, `min_relevance_to_file: 0.1` as interpreter defaults instead of 0. One-line changes in `interpreter.ts:113`.
3. **Extend gate to `kind`** (S1-C): Add `kind` to `buildGate()` and the interpreter prompt. 6 lines of code.
4. **Truncate answer context** (S5-C): Set `maxAnswerChunks: 15` as default in the answer path (not just export). Halves token cost immediately.

### Phase 1 — Reranking (3–5 days)

5. **Cross-encoder rerank** (S3-A): After graph + lexical retrieval, call Cohere Rerank 3.5 (or bundle BGE-reranker ONNX) on the top-100. Keep top-15. This is the single highest-ROI change.
6. **RRF fusion** (S3-D): Combine graph-scored and lexical results before reranking. Adds recall without noise.

### Phase 2 — Retrieval Architecture (1–2 weeks)

7. **Chunk-level embeddings** (S4-A): Batch-embed all chunks with e5. Add `chunk_emb` vector index. Union with tag-scored results before reranking.
8. **Entity resolver** (S1-A): Build vocabulary table at materialize time. Wire into interpreter gate emission.
9. **Schema-enforced interpreter** (S7): Switch to Anthropic tool-use for plan output.

### Phase 3 — Answer Quality (1 week)

10. **Extractive answer pass** (S5-A): Two-pass answer: extract relevant sentences per chunk, then synthesize from extracts only.
11. **Question-type router** (S6-A): Classify queries; route structured lookups to SQL agent.

### Phase 4 — Structural (defer unless thesis requires)

12. **Ontology layer** (S2-A): Define L0–L4 vocabulary as a formal schema.
13. **Speaker normalisation** (S8-B): Pre-process Slack/transcript chunks.
14. **Agentic answer loop** (S5-B): Full tool-use answer with graph queries.

---

## 4. Quick Wins vs Structural Fixes

| Change | Type | Effort | Pains Fixed | Expected Impact |
|---|---|---|---|---|
| Set `min_w_chunk: 0.05` | Quick win | Minutes | P3, P12 | −30% noise chunks |
| Set `maxAnswerChunks: 15` default | Quick win | Minutes | P5, P14 | −60% answer tokens |
| Score-gap cutoff | Quick win | Hours | P3, P6, P14 | −40% noise, +precision |
| Add `kind` to gate | Quick win | Hours | P7 | Enables doc-type filtering |
| Cross-encoder rerank | Structural | Days | P3, P6, P10, P14 | +15–30pp context_precision |
| RRF hybrid fusion | Structural | Days | P4 (partial) | +recall on literal queries |
| Chunk embeddings + union | Structural | Week | P4 | Removes tagger ceiling |
| Extractive answer pass | Structural | Days | P5, P6 | +10–20pp faithfulness |
| Entity resolver | Structural | Days | P1, P7 | Fixes gate failures |
| Tool-use interpreter | Structural | Day | P8 | Eliminates parse failures |
| Question-type routing | Structural | Days | P10, P11 | Right arm per query type |
| Ontology schema | Design | Days | P2 | Precise interpreter prompt |

---

## 5. What NOT to Do

- **Don't fix k.** Increasing `limit` from 20 to 100 doesn't help — it pulls in more noise. The problem is *ranking*, not *recall depth*. Reranking fixes this; k changes don't.
- **Don't add more regex/verbatim gates.** The gate architecture is fundamentally about exact string matching. Adding more string fields (`author`, `date`) doubles down on the wrong abstraction. Use entity resolution instead.
- **Don't embed chunks without reranking.** Adding chunk vectors without a reranking step just creates a second noisy candidate pool. The union needs a quality filter.
- **Don't build a full agentic loop before fixing answer input quality.** The SQL agent shows agentic works, but the graph arm's problem isn't "needs more tool calls" — it's "sends 200 chunks to a single-shot prompt". Fix the input first.
- **Don't chase `context_recall=1.00`.** The baseline achieves this by sending *everything* — it's a vacuous metric when k is large. Context_precision is the meaningful metric; fix that first.
- **Don't replace the graph with vector-only retrieval.** The graph structure (faceted tags, weight chain, hard gate) provides genuine selectivity that vector search alone can't. The fix is to *complement* it with vectors, not replace it.

---

## 6. References (Modern Approaches, 2024–2026)

| Topic | Source | Key Insight |
|---|---|---|
| Adaptive routing | EA-GraphRAG (arXiv 2602.03578, 2025) | Syntax-aware complexity routes between dense and graph RAG |
| Multi-granular retrieval | FlexStructRAG (arXiv 2604.16312, 2026) | Entity/edge/cluster retrieval combined adaptively |
| Hybrid retrieval fusion | CoRAG (EMNLP 2025) | Cooperative textual + graph retrieval with global scoring |
| Multi-semantic RAG | MS-RAG (EMNLP 2025) | Chunk + relation + entity indexes with mix recall; +10–30% |
| Tag-guided graph | TagRAG (arXiv 2601.05254, 2026) | Hierarchical tag chains; 78% win rate vs baselines |
| Community chunk vectors | GraphRAG-V (ASONAM 2025) | Chunk-level vectors + VLouvain; +11pp recall |
| Ontology-grounded | OG-RAG (EMNLP 2025) | Hypergraph ontology anchoring; +55% fact recall |
| LLM metadata enrichment | Enterprise RAG (arXiv 2512.05411, 2025) | Metadata-enriched retrieval; 82.5% precision vs 73.3% |
| Entity linking | BYOKG-RAG (EMNLP 2025) | Multi-strategy graph linking; +4.5% over single-strategy |
| Lost in the middle | Found in the Middle (arXiv 2406.16008) | Positional attention calibration; +15pp |
| Dynamic k selection | SAGE (arXiv 2503.01713, 2025) | Semantic-aware segmentation + dynamic chunk selection; +61% |
| Cross-encoder reranking | Cohere Rerank 3.5 (2024) | 4096-token cross-encoder; state-of-art on multilingual |
| Agentic RAG | LangGraph/LlamaIndex patterns (2025–2026) | Plan/retrieve/critique/re-retrieve loop with tool routing |
| Query routing | RAGRouter-Bench (2025) | TF-IDF classifier achieves 93% routing accuracy |
| Rule-driven source routing | arXiv 2510.02388 (2025) | Query-type → retrieval modality alignment |

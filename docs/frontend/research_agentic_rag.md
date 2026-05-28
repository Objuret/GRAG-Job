# Agentic RAG Research Brief — HERB Graph-RAG Pain Analysis

> Compiled 2026-05-22. Sources: 2024–2026 papers, production guides, benchmarks.

---

## HERB Pains Reference Key

| Pain | Shorthand |
|------|-----------|
| Gate failure (LLM says "relevant" to junk chunks) | **gate-fail** |
| Soft tag overlap (same tag name in multiple facets, cosine ≈ 0.9) | **tag-overlap** |
| 100-chunk haystack (too many chunks survive k=20→100 retrieval) | **haystack** |
| Role attribution on feedback blobs (multi-speaker chunks) | **role-attr** |
| k=20 amputation (hard cutoff drops relevant tail) | **k-amputate** |

---

## 1. Agentic RAG vs Single-Shot RAG

### What it is

An agent decides **when** to retrieve, **what tool** to call (vector search, Cypher query, full-text, web), evaluates result quality, and loops until satisfied or budget-exhausted.

### Key sources

| Source | URL | Year |
|--------|-----|------|
| GenAI Patterns – Agentic RAG | https://www.genaipatterns.dev/patterns/rag/agentic-rag | 2025 |
| InfoQ – Hierarchical Agentic RAG (84.5% vs 62.8% flat) | https://www.infoq.com/articles/building-hierarchical-agentic-rag-systems/ | 2025 |
| vpakspace/agentic-graph-rag (VectorCypher + Datalog routing, 96.7%) | https://github.com/vpakspace/agentic-graph-rag | 2025 |
| Azure SQL – Agentic RAG (SQL vs vector routing) | https://devblogs.microsoft.com/azure-sql/improve-the-r-in-rag-and-embrace-agentic-rag-in-azure-sql/ | 2025 |

### When mandatory (not just nice-to-have)

1. **Multi-hop** queries: "Which HERB files discuss both temporal patterns AND entity resolution?" — requires iterative sub-query + join.
2. **Mixed structured/unstructured**: "Files tagged > 5 entities in the `activity` facet" — needs Cypher SQL-like aggregation + chunk retrieval.
3. **Quality gate failure**: Agent detects retrieved chunks score below relevance threshold → retries with query reformulation or graph traversal.

### HERB pains addressed

| Pain | How |
|------|-----|
| **gate-fail** | Agent can evaluate retrieved set quality and discard/retry instead of blindly passing junk to generator |
| **haystack** | Agent iterates: narrow Cypher → targeted vector → stops at 5-10 high-quality chunks instead of dumping 100 |
| **k-amputate** | Agent uses adaptive retrieval rounds; no hard k ceiling |

### Build / Buy / Skip for thesis

**Build (lightweight).** The frontend already has Anthropic SDK + neo4j-driver in-browser. Implement a 2-3 tool loop:
1. `interpret_query` → facets + Cypher template
2. `vector_search` → embedding similarity on :Tag/:Chunk
3. `evaluate_and_refine` → LLM judges context sufficiency, optionally re-queries

No external framework needed. ~200 LOC prompt-loop in the WorkspaceContext layer. The agentic pattern is the single biggest lever for the haystack and gate-fail pains.

---

## 2. Extractive-then-Generate / Reranking

### What it is

Two-stage pipeline: Stage 1 retrieves broad candidate set (50-200 chunks); Stage 2 **reranks** by cross-encoder, ColBERT, or LLM scoring before passing top-N to generator.

### Key sources

| Source | URL | Year |
|--------|-----|------|
| "RAG Is More Than Retrieval — It's Search & Judge" | https://medium.com/@yu-joshua/rag-is-more-than-retrieval-its-search-judge-9f8e0364fe5b | 2026 |
| SciRerankBench (13 rerankers × 5 LLMs) | https://arxiv.org/html/2508.08742v1 | 2025 |
| ZeroEntropy – Cross-Encoder vs LLM rerankers comparison | https://zeroentropy.dev/articles/should-you-use-llms-for-reranking-a-deep-dive-into-pointwise-listwise-and-cross-encoders/ | 2025 |
| Galileo – Selecting a Reranking Model | https://galileo.ai/blog/mastering-rag-how-to-select-a-reranking-model | 2024 |
| LanceDB – Training Custom Rerankers | https://www.lancedb.com/blog/a-practical-guide-to-training-custom-rerankers | 2025 |

### Architecture comparison

| Method | Latency | Quality | Scalability |
|--------|---------|---------|-------------|
| Cross-encoder (ms-marco-MiniLM) | ~130ms/20 docs | NDCG@10 ≈ 0.78 | Good up to ~200 candidates |
| ColBERT (late interaction) | ~50ms/20 docs | Slightly below cross-encoder | Excellent (pre-computed token embeddings) |
| LLM pointwise (GPT-4-mini) | ~2s/20 docs | NDCG@10 ≈ 0.70 + format failures | Poor at scale |
| LLM listwise | ~3-5s/10 docs | Highest zero-shot | Only viable for ≤10 candidates |
| Cohere Rerank v3 (API) | ~200ms/100 docs | Competitive with cross-encoder | Unlimited (managed) |

### HERB pains addressed

| Pain | How |
|------|-----|
| **haystack** | Rerank 100 → 5-10 before generation; the generator never sees the haystack |
| **tag-overlap** | Cross-encoder sees query+chunk jointly; distinguishes "temporal" usage from "activity" usage of same tag |
| **gate-fail** | Reranker score threshold acts as principled gate; low-score chunks are dropped rather than LLM-judged as "relevant" |

### Build / Buy / Skip for thesis

**Build (in-browser LLM rerank).** Since Anthropic SDK is already in-browser:
- Retrieve top-50 via Neo4j vector index
- Send query + 50 chunk summaries to Claude as a **listwise rerank** prompt (structured output: ordered list of chunk IDs with relevance scores)
- Take top-5-8 for generation

Cost: ~1 extra API call per query. No Python cross-encoder server needed. For a thesis demo, LLM listwise rerank on ≤50 candidates is practical and avoids the infra of hosting a cross-encoder model.

**Buy: skip.** Cohere Rerank requires a separate API key + billing; adds dependency for marginal gain over LLM rerank at thesis scale.

---

## 3. Question-Type Routing

### What it is

Classify incoming query by type/complexity, route to different retrieval pipelines (no-retrieval / single-hop lookup / multi-hop iterative / summarization over community).

### Key sources

| Source | URL | Year |
|--------|-----|------|
| Adaptive-RAG (NAACL 2024) – complexity classifier | https://aclanthology.org/2024.naacl-long.389.pdf | 2024 |
| MBA-RAG (COLING 2025) – multi-armed bandit routing | https://aclanthology.org/2025.coling-main.218.pdf | 2025 |
| SymRAG – neuro-symbolic routing (97.6-100% acc) | https://arxiv.org/pdf/2506.12981 | 2025 |
| Self-Routing RAG – binding selective retrieval | https://arxiv.org/html/2504.01018 | 2025 |
| SkewRoute – training-free KG routing via score skewness | https://aclanthology.org/2025.findings-emnlp.606/ | 2025 |
| HLG – StatementGraphRAG (factoid) + TopicGraphRAG (exploratory) | https://arxiv.org/html/2506.08074v1 | 2025 |

### Question types in HERB context

| Type | Example | Pipeline |
|------|---------|----------|
| **Lookup/factoid** | "What files mention 'Dreamforce'?" | Direct full-text/tag search, no generation needed |
| **Faceted retrieval** | "Show chunks about temporal patterns in onboarding" | Vector search on :Tag embeddings filtered by facet=temporal |
| **Summarization** | "Summarize HERB's coverage of entity types" | Broad retrieval (k=50) → rerank → synthesize |
| **Multi-hop** | "Which activities involve entities that also appear in temporal patterns?" | Cypher traversal across HAS_TAG edges, iterative retrieval |
| **Exploratory** | "What themes emerge from the feedback data?" | GraphRAG community summary pattern |

### HERB pains addressed

| Pain | How |
|------|-----|
| **haystack** | Factoid queries skip heavy retrieval entirely; only summarization/multi-hop needs large candidate sets |
| **k-amputate** | Multi-hop route uses iterative retrieval with no fixed k; exploratory uses community summaries |
| **role-attr** | Multi-speaker feedback blobs routed to specialized pipeline that decomposes by speaker before tagging |

### Build / Buy / Skip for thesis

**Build (prompt-based classifier).** Add a routing step in the interpretation layer:
- Prompt classifies query into 3-4 types (the current `interpret` prompt can emit a `query_type` field)
- Switch statement in JS dispatches to appropriate retrieval function
- ~50 LOC routing logic + one extra field in the interpretation schema

No ML classifier needed at thesis scale. The Adaptive-RAG paper shows even a simple LLM-based classifier provides most of the benefit.

---

## 4. Context Packing / Evidence Selection

### What it is

After retrieval and reranking, select and arrange the final evidence window to maximize LLM utilization. Avoid the "lost-in-the-middle" position bias where the model ignores information placed in the center of the context.

### Key sources

| Source | URL | Year |
|--------|-----|------|
| "Lost in the Middle" (Liu et al., TACL 2024) | https://aclanthology.org/2024.tacl-1.9.pdf | 2024 |
| "Found in the Middle" – attention calibration (+10pp) | https://aclanthology.org/2024.findings-acl.890.pdf | 2024 |
| "Do RAG Systems Really Suffer From Positional Bias?" | https://aclanthology.org/2025.emnlp-main.1422.pdf | 2025 |
| Context-Picker (RL-based minimal sufficient subset) | https://arxiv.org/pdf/2512.14465 | 2024 |
| ECoRAG (evidentiality-guided compression) | https://aclanthology.org/2025.findings-acl.1365.pdf | 2025 |
| SEAL-RAG ("replace, don't expand" fixed-budget assembly) | https://huggingface.co/papers/2512.10787 | 2024 |
| Adaptive-k (score-distribution-based passage count) | https://aclanthology.org/2025.emnlp-main.1017.pdf | 2025 |

### Practical strategies

1. **Relevance ordering**: Place highest-relevance chunks at positions 1 and N (start/end of context). Middle positions for supporting evidence.
2. **Aggressive pruning**: 5-8 chunks beats 20 chunks if reranking is good. Adaptive-k shows 10× fewer tokens with same accuracy on factoid QA.
3. **Cite-or-abstain output format**: Force the LLM to cite chunk IDs for each claim or explicitly abstain. Detects when context is insufficient rather than hallucinating.
4. **Fixed-budget replacement**: When new evidence is found (multi-hop), swap out weakest existing chunk rather than expanding the window.

### Citation / Abstention sources

| Source | URL | Year |
|--------|-----|------|
| "Attribute or Abstain" (UKP Lab, EMNLP 2024) | https://github.com/UKPLab/emnlp2024-attribute-or-abstain | 2024 |
| Trust-Align (grounded attributions + learning to refuse) | https://arxiv.org/html/2409.11242v2 | 2024 |
| Contrastive Decoding with Abstention | https://aclanthology.org/2025.acl-long.479.pdf | 2025 |
| RECLAIM (sentence-level citations, 90% acc) | https://aclanthology.org/2025.findings-naacl.55.pdf | 2025 |

### HERB pains addressed

| Pain | How |
|------|-----|
| **haystack** | Prune from 100 → 5-8 with cite-or-abstain; LLM only uses what it can cite |
| **gate-fail** | Cite-or-abstain forces the model to ground claims; unjustifiable claims trigger abstention |
| **role-attr** | Position each speaker's content as a labeled block (start/end); cite by speaker+chunk_id |
| **k-amputate** | Replace "k=20 hard cap" with adaptive evidence budget based on query complexity |

### Build / Buy / Skip for thesis

**Build (structured output).** Already feasible with Anthropic's structured output:
- Response schema: `{ answer: string, citations: [{chunk_id, quote}], confidence: "high"|"low"|"abstain" }`
- Order chunks by relevance score (strongest first and last)
- Limit context to 5-8 chunks post-rerank

Zero infra cost. The cite-or-abstain pattern is the cheapest and highest-signal improvement for gate-fail detection.

---

## 5. RAG Evaluation Pitfalls

### The problem: metric divergence

| Scenario | Context Recall | Faithfulness | Answer Correctness | Diagnosis |
|----------|:-:|:-:|:-:|------------|
| Perfect retrieval, hallucinated answer | 1.0 | 0.0 | ~0.5 | Generator ignores context (gate-fail at generation stage) |
| Good retrieval, good generation from wrong chunks | 0.7 | 1.0 | 0.3 | Retriever returns related-but-wrong; reranking would fix |
| Perfect everything | 1.0 | 1.0 | 1.0 | Ideal |
| No relevant chunks exist | 0.0 | 1.0 | 0.0 | Corpus gap; should abstain |

### Key sources

| Source | URL | Year |
|--------|-----|------|
| RagChecker (NeurIPS 2024, claim-level metrics, 8 RAG systems) | https://arxiv.org/html/2408.08067v1 | 2024 |
| MIRAGE (context insensitivity, noise vulnerability) | https://aclanthology.org/2025.findings-naacl.157.pdf | 2025 |
| FRAMES (factuality + retrieval + reasoning unified) | https://aclanthology.org/2025.naacl-long.243.pdf | 2025 |
| GaRAGe (grounding annotations, 60% factuality F1) | https://aclanthology.org/2025.findings-acl.875.pdf | 2025 |
| RAG Evaluation Survey | https://arxiv.org/pdf/2405.07437 | 2024 |

### Key insights for HERB

1. **Claim-level evaluation** (RagChecker) is essential: response-level metrics hide per-claim failures. A 5-claim answer with 4 grounded claims and 1 hallucination scores "high" on coarse metrics but fails on the hallucinated claim.
2. **Context insensitivity** (MIRAGE): LLMs sometimes produce correct answers regardless of context — this means CR=1 F=1 but the system is actually ignoring retrieval. Test by perturbing context.
3. **Noise vulnerability**: Adding irrelevant chunks (the haystack pain) actively degrades both faithfulness and answer correctness. Fewer, better chunks > more chunks.
4. **GaRAGe finding**: Even SOTA models achieve only 60% Relevance-Aware Factuality Score — over-summarization is the default failure mode.

### HERB pains addressed

| Pain | How evaluation helps |
|------|-----|
| **gate-fail** | Claim-level faithfulness checking identifies which chunks the model actually used vs ignored |
| **haystack** | Noise vulnerability metrics quantify the penalty of over-retrieval |
| **tag-overlap** | Evaluation reveals when two overlapping tags lead to answer conflation |

### Build / Buy / Skip for thesis

**Build (lightweight).** Implement a mini eval harness:
- 10-20 gold QA pairs over the HERB graph
- Per-claim citation checking (does each answer sentence cite a real chunk?)
- Faithfulness = (cited claims) / (total claims)
- Context precision = (used chunks) / (retrieved chunks)

**Skip** full RagChecker/RAGAS framework — overkill for thesis scale. The structured cite-or-abstain output (§4) gives you per-claim grounding for free.

---

## 6. Production Patterns: Which Addresses What

### Pattern comparison matrix

| Pattern | Addresses | Mechanism | Thesis applicability |
|---------|-----------|-----------|---------------------|
| **Cohere Rerank** | bad rank | Managed API cross-encoder reranking | Skip (adds API dependency) |
| **RAG-Fusion** | bad rank, query ambiguity | Multi-query generation + RRF merging | Build (cheap: 1 LLM call generates 3-4 query variants) |
| **HyDE** | vocabulary mismatch | Generate hypothetical answer → embed → retrieve | Build if vocab mismatch is observed; skip otherwise |
| **Self-RAG** | bad answer, unnecessary retrieval | Reflection tokens decide when to retrieve / critique | Skip (requires fine-tuned model) |
| **CRAG** | bad rank → bad answer | Evaluate retrieval quality → correct/fallback | Build (the CRAG evaluator is just a prompt) |
| **GraphRAG** | summarization, global queries | Community summaries + entity graph | Already have (Neo4j graph is the community structure) |

### Key sources

| Source | URL | Year |
|--------|-----|------|
| Higress-RAG (enterprise CRAG + adaptive routing) | https://arxiv.org/pdf/2602.23374 | 2026 |
| ARAGOG (comparative eval: HyDE, multi-query, rerank) | https://arxiv.org/html/2404.01037 | 2024 |
| RAG-Fusion paper | https://arxiv.org/html/2402.03367v1 | 2024 |
| Self-RAG (ICLR 2024, reflection tokens) | https://selfrag.github.io/ | 2024 |
| CRAG paper (ACL 2024) | https://arxiv.org/pdf/2401.15884v2 | 2024 |
| Microsoft GraphRAG (community summaries) | https://arxiv.org/pdf/2404.16130 | 2024 |
| Neo4j GraphRAG Python (VectorCypherRetriever) | https://neo4j.com/developer/genai-ecosystem/graphrag-python/ | 2025 |
| Production reranker layer (cross-encoder + Cohere fallback + RRF) | https://dev.to/velsof/production-reranker-layer-for-rag-in-python-cross-encoder-cohere-fallback-and-reciprocal-rank-1a29 | 2025 |

### Detailed pattern analysis

#### RAG-Fusion (RECOMMEND for HERB)
- Generate 3-4 query variants from user query using LLM
- Run each through Neo4j vector search
- Merge with Reciprocal Rank Fusion (score = Σ 1/(k + rank_i))
- Addresses **tag-overlap** (different phrasings surface different facets) and **k-amputate** (union of results > single k=20)
- Cost: 1 extra LLM call + 3-4 vector searches (fast in Neo4j)

#### CRAG / Corrective RAG (RECOMMEND for HERB)
- After retrieval, classify result quality: Correct / Ambiguous / Incorrect
- Correct → proceed with generation
- Ambiguous → refine query, re-retrieve
- Incorrect → fallback (broader search, different facets, or abstain)
- Addresses **gate-fail** directly: the corrective evaluation IS the gate
- Cost: 1 classification prompt per query (lightweight)

#### HyDE (CONDITIONAL for HERB)
- Generate a hypothetical chunk that would answer the query
- Embed the hypothetical → retrieve similar real chunks
- Helps when user vocabulary diverges from corpus vocabulary
- **Risk for HERB**: If the HERB corpus has consistent terminology, HyDE adds latency without benefit
- Addresses **tag-overlap** (hypothetical document disambiguates intended facet)
- Cost: 1 generation + 1 embedding per query

#### Self-RAG (SKIP for thesis)
- Requires fine-tuned model with reflection tokens baked into weights
- Overkill for a browser-based thesis demo
- The *principle* (decide whether to retrieve, critique after generation) can be replicated with prompts in the agentic loop

---

## Synthesis: Recommended Architecture for HERB Frontend

```
User Query
    │
    ▼
┌─────────────────────┐
│ Interpret + Classify │  ← Question-type routing (§3)
│ (query_type, facets) │     + RAG-Fusion query expansion (§6)
└─────────┬───────────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
 Factoid    Multi-hop / Summary
    │           │
    ▼           ▼
 Cypher      Vector Search (3-4 variants)
 lookup         │
    │           ▼
    │        RRF Merge (top-50)
    │           │
    │           ▼
    │        LLM Rerank (§2)
    │        (listwise, top-8)
    │           │
    ▼           ▼
┌─────────────────────┐
│  CRAG Evaluator (§6)│  ← Is retrieved set sufficient?
│  Correct/Retry/Fail │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Generate + Cite    │  ← Context packing (§4)
│  (cite-or-abstain)  │     5-8 chunks, structured output
└─────────────────────┘
```

### Priority implementation order

| # | Component | LOC est. | Pains addressed | Effort |
|---|-----------|----------|-----------------|--------|
| 1 | Cite-or-abstain structured output | ~30 | gate-fail, haystack | Low |
| 2 | LLM listwise rerank (top-50 → top-8) | ~80 | haystack, tag-overlap, gate-fail | Low |
| 3 | RAG-Fusion query expansion | ~50 | k-amputate, tag-overlap | Low |
| 4 | CRAG evaluator (retrieval quality check) | ~60 | gate-fail | Low |
| 5 | Question-type router | ~50 | haystack, k-amputate | Low |
| 6 | Agentic loop (retry on low confidence) | ~200 | all pains | Medium |
| 7 | HyDE (conditional, if vocab mismatch observed) | ~40 | tag-overlap | Low |

### What to skip entirely

- **Cohere Rerank API**: Adds billing + dependency for no meaningful gain over LLM rerank at thesis scale
- **Self-RAG fine-tuning**: Requires model training; the principle is captured by the agentic loop
- **ColBERT/cross-encoder server**: Requires Python backend hosting; LLM rerank in-browser suffices
- **Full RAGAS/RagChecker framework**: Overkill; structured output gives per-claim evaluation for free
- **Attention calibration / hidden state scaling**: Model-level changes not applicable to API-based LLMs

---

## Appendix: ARAGOG Comparative Results (2024)

From the ARAGOG benchmark (Advanced RAG Output Grading):

- **HyDE**: Did NOT show significant improvement in their evaluation
- **Multi-query**: Underperformed single-query in their setup
- **Sentence-window retrieval**: Strong performance
- **Reranking (Cohere)**: No notable advantage over baseline in their specific setup

**Caveat**: These results are domain/dataset-specific. The HERB graph structure (faceted tags, multi-speaker chunks) differs significantly from ARAGOG's test corpus. The LLM rerank + CRAG combination is more appropriate for HERB's specific topology.

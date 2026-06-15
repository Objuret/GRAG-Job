# Graph-RAG Pain Analysis: Research Brief

> Web research compiled 2026-05-22. Focus: 2024–2026 sources applicable to a Neo4j chunk graph with HAS_TAG edges, gate fields, Lucene full-text baseline, and browser-side workbench.

---

## 1. Graph RAG / GraphRAG (Microsoft and successors)

### Sources

| # | Title | URL |
|---|-------|-----|
| 1 | From Local to Global: A Graph RAG Approach to Query-Focused Summarization (Edge et al., 2024) | https://www.microsoft.com/en-us/research/publication/from-local-to-global-a-graph-rag-approach-to-query-focused-summarization/ |
| 2 | LazyGraphRAG: Setting a new standard for quality and cost (Microsoft Research, 2024) | https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/ |
| 3 | RAG vs. GraphRAG: A Systematic Evaluation and Key Insights (arXiv 2502.11371, 2025) | https://arxiv.org/html/2502.11371v2 |
| 4 | HybridRAG: Integrating Knowledge Graphs and Vector RAG (arXiv 2408.04948, 2024) | https://arxiv.org/html/2408.04948 |
| 5 | When to use Graphs in RAG: A Comprehensive Analysis (arXiv 2506.05690, 2025) | https://arxiv.org/abs/2506.05690v1 |

### Takeaway for HERB

GraphRAG shines on **global/thematic queries** ("what are the main themes across this corpus?") but frequently **underperforms vanilla vector RAG on local/factual questions** (who, what, when, where). LazyGraphRAG eliminates the expensive upfront summarization step (0.1% of full GraphRAG indexing cost) and handles both query types via iterative deepening. For the HERB workbench — which already has chunk→tag edges and facet metadata — the graph structure is most valuable as a **routing/filtering scaffold** rather than a standalone retrieval mechanism. Hybrid approaches (vector + graph traversal) consistently outperform either alone in controlled evaluations.

### Hype vs. Proven

- **Proven:** Graph traversal improves multi-hop and thematic queries; hybrid > either alone; community summaries help global questions.
- **Hype:** "GraphRAG replaces vector search" — on local queries it's worse and 100–700× more expensive at query time. The marketing outpaces the benchmarks.

---

## 2. Ontology-Driven / Schema-Aware Retrieval

### Sources

| # | Title | URL |
|---|-------|-----|
| 1 | OG-RAG: Ontology-Grounded Retrieval-Augmented Generation (EMNLP 2025) | https://aclanthology.org/2025.emnlp-main.1674.pdf |
| 2 | Query Attribute Modeling: Improving search with Semantic Search and Metadata Filtering (arXiv 2508.04683, 2025) | https://arxiv.org/html/2508.04683 |
| 3 | CLEAR Principle: Semantic units for cognitive interoperability (J Biomed Semantics, 2025) | https://link.springer.com/article/10.1186/s13326-025-00340-7 |
| 4 | Semantic Operators over Data Lakes (VLDB 2025) | https://www.vldb.org/pvldb/vol18/p4171-patel.pdf |

### Takeaway for HERB

OG-RAG anchors retrieval in domain ontologies via hypergraph representations — factual recall improves 55% and correctness 40%. The key technique: **decompose the query into ontology-aligned attributes first, then constrain the embedding search**. For HERB this maps directly to the prompt-interpretation layer decomposing into the 5 facets (topic/entities/activity/temporal/evidence) before hitting the vector index. Query Attribute Modeling (QAM) shows 53% mAP@5 by auto-extracting structured metadata tags from free-text queries, confirming that LLM-driven facet extraction before search is a validated pattern, not just architectural preference.

### Hype vs. Proven

- **Proven:** Pre-filtering on typed metadata consistently improves precision with minimal recall loss; ontology-grounded retrieval measurably outperforms flat embedding search.
- **Hype:** "Full ontology required" — lightweight typed filters (your facets + source classification) capture most of the benefit without formal ontology engineering.

---

## 3. Entity Linking / Corpus-Resolved Routing

### Sources

| # | Title | URL |
|---|-------|-----|
| 1 | ARTER: Adaptive Routing and Targeted Entity Reasoning (EMNLP Industry 2025) | https://aclanthology.org/2025.emnlp-industry.59/ |
| 2 | R1-Router: Learning to Route Queries across Knowledge Bases (arXiv 2505.22095, 2025) | https://arxiv.org/html/2505.22095v1 |
| 3 | CoRAG: Cooperative Retriever Architecture (EMNLP Findings 2025) | https://aclanthology.org/anthology-files/anthology-files/pdf/findings/2025.findings-emnlp.872.pdf |
| 4 | DeepSieve: LLM-as-a-Knowledge-Router (arXiv 2507.22050, 2025) | https://arxiv.org/html/2507.22050 |
| 5 | UniversalRAG: Retrieval over Diverse Modalities and Granularities (arXiv 2504.20734, 2025) | https://arxiv.org/html/2504.20734 |

### Takeaway for HERB

Modern entity linking is **not verbatim string match** — ARTER routes "easy" mentions to lightweight linkers and "hard" mentions to targeted LLM reasoning, saving 50% of tokens vs. brute-force. For the HERB workbench, the parallel is: the prompt interpreter identifies named entities, then the system should resolve them against `:Tag` nodes (using embedding similarity on tag names, not exact match) to find the right graph neighbourhood. CoRAG's key insight: dynamically choosing between document search and graph traversal per sub-query outperforms static routing. DeepSieve's recursive sub-query decomposition maps to how the workbench already breaks prompts into faceted sub-queries.

### Hype vs. Proven

- **Proven:** Adaptive routing (easy/hard bifurcation) saves cost with no quality loss; multi-source routing via RL outperforms fixed retrieval.
- **Hype:** "Universal routers" that handle arbitrary modalities — in practice, a domain-tuned router over 2-3 known sources (your Lucene + vector + graph traverse) is sufficient and far simpler.

---

## 4. Metadata-First RAG

### Sources

| # | Title | URL |
|---|-------|-----|
| 1 | Intelligent Metadata Filtering with Amazon Bedrock (AWS, 2024) | https://aws.amazon.com/blogs/machine-learning/streamline-rag-applications-with-intelligent-metadata-filtering-using-amazon-bedrock/ |
| 2 | RAG with Metadata Filtering: Narrowing Search with Structured Attributes (Callsphere, 2025) | https://callsphere.ai/blog/rag-metadata-filtering-narrowing-search-structured-attributes.md |
| 3 | Metadata for RAG: Improve Contextual Retrieval (Unstructured, 2024) | https://unstructured.io/insights/how-to-use-metadata-in-rag-for-better-contextual-results |
| 4 | Google Vertex AI RAG Engine: Metadata Search (2025) | https://docs.cloud.google.com/vertex-ai/generative-ai/docs/rag-engine/use-metadata-search |
| 5 | Filter RAG Search Results with Document Metadata Tags (Markaicode, 2026) | https://markaicode.com/rag-metadata-filtering-document-tags/ |

### Takeaway for HERB

The consensus pattern: **pre-filter > post-filter**. Narrowing the candidate set before computing vector similarity ensures only matching documents are scored — this is faster and produces fewer distractor passages in the context. For HERB, the gate fields (`source_id`, `file_classification`, `facet` on HAS_TAG edges) are exactly the right pre-filter mechanism. The AWS approach of using LLM function-calling to dynamically extract metadata filters from natural language is identical to what the HERB prompt-interpretation layer does (decompose → structured Cypher WHERE clauses → then Lucene/vector). This is a **well-validated industry pattern** across all major cloud providers.

### Hype vs. Proven

- **Proven:** Pre-filtering on structured metadata before embedding search is universally recommended; LLM-driven filter extraction from queries works reliably.
- **Hype:** Very little — this is engineering best practice, not research frontier. The only risk is over-filtering (empty result sets from too-strict constraints), which requires fallback logic.

---

## 5. Neo4j + Vector Hybrid Patterns 2025

### Sources

| # | Title | URL |
|---|-------|-----|
| 1 | Hybrid Search (Neo4j Developer Guide) | https://neo4j.com/developer/genai-ecosystem/hybrid-search/ |
| 2 | Vector Search with Filters in Neo4j v2026.01 (Preview) | https://neo4j.com/blog/genai/vector-search-with-filters-in-neo4j-v2026-01-preview/ |
| 3 | Vector Search With Graph Traversal Using Neo4j GraphRAG Package | https://neo4j.com/blog/developer/graph-traversal-graphrag-python-package/ |
| 4 | Hybrid Retrieval Using the Neo4j GraphRAG Package for Python | https://neo4j.com/blog/developer/hybrid-retrieval-graphrag-python-package/ |
| 5 | Neo4j GraphRAG Python Package — VectorCypherRetriever | https://github.com/neo4j/neo4j-graphrag-python/blob/main/examples/retrieve/vector_cypher_retriever.py |

### Takeaway for HERB

Neo4j now supports three hybrid signals via **Weighted Reciprocal Rank Fusion (WRRF)**: (1) full-text/Lucene, (2) vector similarity, (3) graph-structural (FastRP embeddings). The `VectorCypherRetriever` pattern is directly applicable: vector-match chunks, then traverse HAS_TAG edges to collect tag context, scores, and facet metadata in a single Cypher query. Neo4j 2026.01 adds native `SEARCH ... WHERE` pre-filtering on vector indexes — meaning you can constrain vector search to a specific `source_id` or `file_classification` **before** ANN executes, not after. For the browser workbench (which runs Cypher via `neo4j-driver`), this means the retrieval can be a single Cypher statement combining pre-filter + vector + graph traversal, avoiding round-trips.

### Hype vs. Proven

- **Proven:** WRRF fusion of full-text + vector in Neo4j; VectorCypher traversal post-vector-match; Lucene full-text as a first-pass filter is battle-tested.
- **Hype/Emerging:** `SEARCH ... WHERE` pre-filter is 2026.01 preview — not yet GA. FastRP structural embeddings for retrieval are interesting but less validated than text embeddings for RAG specifically.

---

## 6. Failures: Retrieval Succeeds, Generation Fails

### Sources

| # | Title | URL |
|---|-------|-----|
| 1 | When Retrieval Succeeds and Fails: Rethinking RAG for LLMs (arXiv 2510.09106, 2025) | https://arxiv.org/html/2510.09106 |
| 2 | Lost in the Middle: How Language Models Use Long Contexts (Liu et al., TACL 2024) | https://aclanthology.org/2024.tacl-1.9.pdf |
| 3 | Do RAG Systems Really Suffer From Positional Bias? (EMNLP 2025) | https://aclanthology.org/2025.emnlp-main.1422.pdf |
| 4 | Mitigating Lost-in-Retrieval in Multi-Hop QA (ACL 2025) | https://aclanthology.org/2025.acl-long.1089.pdf |
| 5 | Optimizing RAG: Hyperparameter Impact on Performance (arXiv 2505.08445, 2025) | https://arxiv.org/html/2505.08445v1 |

### Takeaway for HERB

Three failure modes directly relevant to the workbench:

1. **Lost-in-the-middle:** Relevant chunks placed in the middle of the context window get ignored (U-shaped attention). Mitigation: keep retrieved context short (5–10 chunks max) and place highest-relevance chunks at start/end. The HERB workbench should order chunks by score descending and cap context aggressively.

2. **Precision@k vs Recall@k:** Retrieving more chunks increases recall but introduces distractor passages that confuse generation. For strong models (Claude), optimizing for **precision** (fewer, highly-relevant chunks) beats optimizing for recall. The gate-field pre-filter + Lucene baseline is exactly the right architecture to achieve high precision before semantic ranking.

3. **Preference gap:** What makes a chunk "relevant" by retrieval metrics doesn't always align with what helps the LLM generate correctly. Some indirectly-related context aids reasoning while some directly-matching text confuses it. This argues for **including structural context** (file title, surrounding tags, facet labels) alongside chunk text — which the HAS_TAG edge traversal naturally provides.

Recent work (EMNLP 2025) shows positional bias in real RAG deployments is more nuanced than lab studies suggest — mixed relevant/irrelevant passages partially offset position effects.

### Hype vs. Proven

- **Proven:** Lost-in-the-middle is real but partially mitigated in modern models (Claude 3.5+); precision > recall for generation quality; 5–10 chunks is the sweet spot.
- **Hype:** "Context windows are so large now that lost-in-the-middle doesn't matter" — it's reduced but not eliminated, and large contexts increase latency/cost.

---

## Cross-Cutting Synthesis for HERB Workbench

The research validates the existing HERB architecture choices:

| HERB Component | Validated Pattern | Confidence |
|----------------|-------------------|------------|
| Prompt → 5 facets decomposition | Query Attribute Modeling, OG-RAG ontology grounding | High (multiple 2025 papers) |
| Gate fields as pre-filter | Metadata-first RAG (industry consensus) | Very high |
| Lucene full-text baseline | Hybrid search signal #1 in WRRF | Very high |
| HAS_TAG edge traversal | VectorCypher retriever, CoRAG graph/text hybrid | High |
| Short context (cap chunks) | Precision > recall for generation | High |
| Browser-side Cypher | Single-statement pre-filter + vector + traverse | Feasible (Neo4j driver) |

**Primary gap identified:** The workbench currently lacks **tag-embedding vector search** as a second signal alongside Lucene. The `tagging embed-tags` step produces embeddings that could enable a WRRF-style fusion of (1) Lucene full-text on chunk body, (2) vector similarity on tag embeddings, and (3) graph traversal for structural context. This three-signal pattern is exactly what Neo4j's hybrid search documentation recommends.

**Secondary gap:** No explicit reranking or context-ordering step. Given lost-in-the-middle findings, the workbench prompt assembly should sort chunks by descending relevance score and hard-cap at ~8 chunks.

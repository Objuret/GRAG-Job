# Conference & arXiv Papers — RAG Engineering Research Brief

Curated 2023–2026 papers relevant to HERB graph-RAG workbench design decisions.
Each concept lists 2–4 papers with citation, venue, URL, and 2-sentence relevance note.

---

## 1. Graph-Augmented RAG / Knowledge-Graph Retrieval (Actual Routing)

| # | Paper | Authors | Year | Venue | URL |
|---|-------|---------|------|-------|-----|
| 1a | GNN-RAG: Graph Neural Retrieval for Large Language Model Reasoning on Knowledge Graphs | Mavromatis, Karypis | 2024/2025 | Findings of ACL 2025 (arXiv 2024) | https://arxiv.org/abs/2405.20139 |
| 1b | ReGraphRAG: Reorganizing Fragmented Knowledge Graphs for Multi-Perspective Retrieval-Augmented Generation | — | 2025 | Findings of EMNLP 2025 | https://aclanthology.org/2025.findings-emnlp.290.pdf |
| 1c | BYOKG-RAG (Bring-Your-Own-KG): Multi-Strategy Linking and Retrieval with LLMs | — | 2025 | EMNLP 2025 Main | https://aclanthology.org/2025.emnlp-main.1417.pdf |

**1a** — Uses GNNs to score KG subgraph nodes by relevance, then verbalises shortest paths as LLM context. Outperforms dense retrieval by 8.9–15.5 F1 on multi-hop KGQA while using 9× fewer tokens — directly relevant to our HAS_TAG graph traversal.

**1b** — Addresses fragmented KGs (like our chunk→tag graph) via perspective expansion and query-aware reranking over reorganised subgraphs. Shows that naive triple-bag retrieval from disconnected KG fragments loses coherence on multi-hop questions.

**1c** — LLM generates graph artefacts (entities, candidate answers, Cypher queries) while specialised tools handle actual graph retrieval. Demonstrates 4.5% improvement over prior KGQA with custom KGs — analogous to our browser-side Cypher generation.

---

## 2. Ontology/Schema-Aware or Metadata-First Filtering BEFORE Semantic Retrieval

| # | Paper | Authors | Year | Venue | URL |
|---|-------|---------|------|-------|-----|
| 2a | OG-RAG: Ontology-Grounded Retrieval-Augmented Generation for Large Language Models | Sharma, Kumar, Li | 2025 | EMNLP 2025 Main | https://aclanthology.org/2025.emnlp-main.1674/ |
| 2b | Multi-Meta-RAG: Improving RAG for Multi-Hop Queries using Database Filtering with LLM-Extracted Metadata | Poliakov, Shvai | 2024 | arXiv (ICTERI 2024 Posters) | https://arxiv.org/abs/2406.13213 |
| 2c | PolyRAG: Multi-Level Querying using a Knowledge Pyramid | — | 2024 | arXiv preprint | https://arxiv.org/abs/2407.21276 |

**2a** — Constructs hypergraph where hyperedges are fact clusters grounded in domain ontology; retrieves minimal hyperedge set. 55% recall improvement and 40% correctness boost — validates our facet-ontology as a pre-filter layer rather than post-hoc decoration.

**2b** — LLM extracts structured metadata (source type, date) from the query, applies DB filters to narrow retrieval scope before top-k. 17% Hits@4 gain on MultiHop-RAG — directly mirrors our planned facet-filter-then-vector pipeline.

**2c** — Waterfall retrieval through three layers: ontology → KG → raw chunks, with cross-layer condensation. 395% F1 improvement on domain tasks — supports the idea of hierarchical pre-filtering (facet→tag→chunk).

---

## 3. Tag/Facet-Weighted Retrieval vs Pure Dense/Sparse

| # | Paper | Authors | Year | Venue | URL |
|---|-------|---------|------|-------|-----|
| 3a | Multi-Field Adaptive Retrieval (mFAR) | Li, Chen, Van Durme, Xia | 2025 | ICLR 2025 | https://arxiv.org/abs/2410.20056 |
| 3b | FaBle: Multi-Facet Blending for Faceted Query-by-Example Retrieval | — | 2025 | ACL 2025 Long | https://aclanthology.org/2025.acl-long.1388.pdf |
| 3c | TaxoIndex: Taxonomy-Guided Semantic Indexing for Academic Paper Search | — | 2024 | EMNLP 2024 Main | https://aclanthology.org/2024.emnlp-main.407.pdf |
| 3d | SEAL: Structure and Element Aware Learning for Long Structured Document Retrieval | — | 2025 | EMNLP 2025 Main | https://aclanthology.org/2025.emnlp-main.429.pdf |

**3a** — Decomposes documents into independently indexed fields (title, body, headers); learns query-conditioned field weights at retrieval time. State-of-the-art on semi-structured data — directly analogous to our per-facet weight vectors (w_chunk, w_facet).

**3b** — Decomposes documents into facet-specific units and synthesises facet-level training pairs via LLM; retrieves by blending facet scores. Shows that facet-aware decomposition outperforms whole-document embeddings for concept-level matching.

**3c** — Creates a taxonomy-indexed semantic layer that matches queries to documents through extracted concept nodes rather than raw text similarity. Validates the idea of a structured concept vocabulary (like our :Tag nodes) as retrieval index.

**3d** — Contrastive learning that preserves semantic hierarchies (headings, structure) during embedding; enables element-level alignment. Relevant because our chunks carry structural metadata (file hierarchy, position) that pure dense ignores.

---

## 4. Entity Linking / Corpus Vocabulary Resolution (Fuzzy, Not Verbatim)

| # | Paper | Authors | Year | Venue | URL |
|---|-------|---------|------|-------|-----|
| 4a | ReLiK: Retrieve and LinK, Fast and Accurate Entity Linking and Relation Extraction on an Academic Budget | Navigli et al. | 2024 | Findings of ACL 2024 | https://aclanthology.org/2024.findings-acl.839.pdf |
| 4b | DynamicER: Resolving Emerging Mentions to Dynamic Entities for RAG | — | 2024 | EMNLP 2024 Main | https://aclanthology.org/2024.emnlp-main.762 |
| 4c | OneNet: A Fine-Tuning Free Framework for Few-Shot Entity Linking via LLM Prompting | — | 2024 | EMNLP 2024 Main | https://aclanthology.org/2024.emnlp-main.756.pdf |

**4a** — Retriever-reader entity linker achieving 40× speedup over prior art; candidate entities are represented alongside text in a single forward pass. Relevant to our tag-grounding problem: user says "Salesforce", graph has "Salesforce Inc." — need fuzzy retrieval over vocabulary.

**4b** — Temporal-segmented clustering for emerging entity mentions with continual adaptation; explicitly supports RAG by preventing retriever failure on novel mentions. Validates that a fixed entity vocabulary degrades over time without dynamic resolution.

**4c** — Zero-shot entity linking using LLM prompting with entity reduction + dual-perspective linking. Relevant to our browser-side approach where we resolve user terms to graph :Tag names without fine-tuning.

---

## 5. Hybrid Retrieval: Structured Gate + Vector + Lexical (When Each Wins)

| # | Paper | Authors | Year | Venue | URL |
|---|-------|---------|------|-------|-----|
| 5a | Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection | Asai et al. | 2024 | ICLR 2024 | https://arxiv.org/abs/2310.11511 |
| 5b | Adaptive-RAG: Learning to Adapt Retrieval-Augmented Large Language Models through Question Complexity | Jeong, Baek, Cho, Hwang, Park | 2024 | NAACL 2024 | https://aclanthology.org/2024.naacl-long.389.pdf |
| 5c | Balancing the Blend: An Experimental Analysis of Trade-offs in Hybrid Search | — | 2025 | arXiv preprint | https://arxiv.org/abs/2508.01405 |
| 5d | LTRR: Learning To Rank Retrievers for LLMs | — | 2025 | arXiv preprint | https://arxiv.org/abs/2506.13743 |

**5a** — LM learns when to retrieve (via reflection tokens) and when to rely on parametric knowledge. Demonstrates that always-retrieve hurts versatility — supports our gating logic where facet-match confidence determines whether to hit vector index.

**5b** — Classifier routes queries to no-retrieval / single-step / multi-step RAG based on predicted complexity. Validates our planned 3-tier approach: direct graph lookup → filtered vector → full multi-hop.

**5c** — Systematic benchmark revealing "weakest link" phenomenon: a single underperforming retrieval path disproportionately degrades fused results. Critical for our design: if structured filter produces zero hits, don't blend — fall through.

**5d** — Frames retriever selection as a learning-to-rank problem; includes no-retrieval option. XGBoost routing with answer-correctness optimisation generalises well OOD — lightweight approach we could adapt for query routing.

---

## 6. Reranking Within Retrieved Set / Extractive-Then-Generative

| # | Paper | Authors | Year | Venue | URL |
|---|-------|---------|------|-------|-----|
| 6a | RankRAG: Unifying Context Ranking with Retrieval-Augmented Generation in LLMs | Yu et al. | 2024 | NeurIPS 2024 | https://proceedings.neurips.cc/paper_files/paper/2024/hash/db93ccb6cf392f352570dd5af0a223d3-Abstract-Conference.html |
| 6b | DynamicRAG: Leveraging Outputs of LLMs as Feedback for Dynamic Reranking | — | 2025 | arXiv preprint | https://arxiv.org/abs/2505.07233 |
| 6c | DSLR: Document Refinement with Sentence-Level Re-ranking and Reconstruction | Hwang, Jeong, Cho, Han, Park | 2024 | KnowledgeNLP Workshop (ACL 2024) | https://aclanthology.org/2024.knowledgenlp-1.6.pdf |

**6a** — Single instruction-tuned LLM simultaneously ranks contexts and generates answers; small ranking-data fraction outperforms dedicated expert rankers. Shows we can rerank graph-retrieved chunks with the same Anthropic call that generates the answer.

**6b** — RL-based reranker uses LLM output quality as reward signal to dynamically adjust both document order and count (k). Addresses our concern: fixing large k then reranking is better than guessing optimal k upfront.

**6c** — Decomposes documents into sentences, filters irrelevant ones, reconstructs coherent passages — no training required. Directly applicable to our post-retrieval step: chunks are coarse, sentence-level filtering tightens context.

---

## 7. Agentic/Tool RAG for Structured Corpora vs Single-Shot Context Stuffing

| # | Paper | Authors | Year | Venue | URL |
|---|-------|---------|------|-------|-----|
| 7a | Self-RAG (see 5a above) | Asai et al. | 2024 | ICLR 2024 | https://arxiv.org/abs/2310.11511 |
| 7b | CRAG: Comprehensive RAG Benchmark (KDD Cup 2024) | Yang et al. (Meta) | 2024 | NeurIPS 2024 D&B Track | https://arxiv.org/abs/2406.04744 |
| 7c | ER-RAG: Enhance RAG with ER-Based Unified Modeling of Heterogeneous Data Sources | Peking Univ. / Huawei | 2025 | arXiv preprint | https://arxiv.org/abs/2504.06271 |

**7b** — Benchmark showing advanced LLMs achieve ≤34% accuracy; straightforward RAG only reaches 44%; best agentic solutions 63%. Proves single-shot context stuffing fails on complex factual QA — tool-augmented agents with structured access win.

**7c** — ER-model unifies heterogeneous sources (web, KG, DB) under GET/JOIN APIs; DPO-tuned module selects sources then generates API chains. Won KDD Cup CRAG all three tracks — validates our design of Cypher queries + structured filters as "tools" rather than blind context injection.

---

## 8. RAG Failure Modes: High Recall but Wrong Answer; Faithfulness vs Context-Recall Divergence; Lost-in-the-Middle

| # | Paper | Authors | Year | Venue | URL |
|---|-------|---------|------|-------|-----|
| 8a | Lost in the Middle: How Language Models Use Long Contexts | Liu, Lin, Hewitt, Paranjape, Bevilacqua, Petroni, Liang | 2024 | TACL 2024 / NAACL 2024 | https://aclanthology.org/2024.tacl-1.9.pdf |
| 8b | Sufficient Context: A New Lens on Retrieval Augmented Generation Systems | Joren, Zhang, Ferng, Juan, Taly, Rashtchian | 2025 | ICLR 2025 | https://openreview.net/forum?id=Jjr2Odj8DJ |
| 8c | Mitigating Lost-in-Retrieval Problems in Retrieval Augmented Multi-Hop QA | — | 2025 | ACL 2025 Long | https://aclanthology.org/2025.acl-long.1089.pdf |
| 8d | Generate but Verify: Answering with Faithfulness in RAG-based QA | — | 2025 | IJCNLP 2025 Long | https://aclanthology.org/2025.ijcnlp-long.56.pdf |

**8a** — Canonical finding: LMs exhibit U-shaped attention over long contexts; relevant information in the middle is effectively lost. Directly motivates our reranking and short-context strategy: don't dump 20 chunks; surface 3–5 top ones.

**8b** — Introduces "sufficient context" autorater separating retrieval failure from model utilisation failure. Large models hallucinate 15–40% when context is insufficient rather than abstaining — explains why high recall@k doesn't prevent wrong answers.

**8c** — Multi-hop questions with pronoun-heavy sub-questions cause "lost-in-retrieval" where correct documents exist but retriever fails to resolve them. Directly motivates our entity-resolution step before retrieval.

**8d** — Couples faithfulness prediction with answer generation; proposes precision/recall metrics for faithfulness. Validates our planned architecture of verifying generated answers against retrieved evidence before presenting to user.

---

## 9. Heterogeneous Enterprise JSON / Multi-Surface Corpora

| # | Paper | Authors | Year | Venue | URL |
|---|-------|---------|------|-------|-----|
| 9a | HERB: Benchmarking Deep Search over Heterogeneous Enterprise Data | Choubey, Peng, Bhagavath, Huang, Xiong, Wu | 2025 | EMNLP 2025 Industry Track | https://arxiv.org/abs/2506.23139 |
| 9b | ER-RAG (see 7c above) | Peking Univ. / Huawei | 2025 | arXiv preprint | https://arxiv.org/abs/2504.06271 |
| 9c | CRAG (see 7b above) | Yang et al. (Meta) | 2024 | NeurIPS 2024 D&B | https://arxiv.org/abs/2406.04744 |

**9a** — 39,190 enterprise artefacts spanning docs, meeting transcripts, Slack, GitHub, URLs with answerable + unanswerable queries. Best agentic methods score only 32.96 — retrieval over heterogeneous surfaces is the bottleneck, not generation. Directly validates our multi-format corpus challenge.

**9b** — Entity-Relationship model gives uniform GET/JOIN interface over heterogeneous backends; 5.5× faster retrieval. Shows that schema-level unification (like our :Source→:File→:Chunk graph) is the key enabler for multi-surface RAG.

**9c** — 4,409 QA pairs across five domains with mock web + KG APIs; measures entity popularity, temporal dynamism, and complexity. Industry-standard benchmark confirming that dynamic, multi-source QA needs structured access patterns, not just embeddings.

---

## 10. Evaluation Methodology: Matched-k Comparison; When recall@large-k Is Hollow

| # | Paper | Authors | Year | Venue | URL |
|---|-------|---------|------|-------|-----|
| 10a | eRAG: Evaluating Retrieval Quality in Retrieval-Augmented Generation | Salemi, Zamani | 2024 | SIGIR 2024 | https://dl.acm.org/doi/10.1145/3626772.3657957 |
| 10b | ARES: An Automated Evaluation Framework for Retrieval-Augmented Generation Systems | Saad-Falcon et al. | 2024 | NAACL 2024 | https://aclanthology.org/2024.naacl-long.20.pdf |
| 10c | RAGAS: Automated Evaluation of Retrieval Augmented Generation | Es et al. | 2024 | EACL 2024 Demo | https://aclanthology.org/2024.eacl-demo.16.pdf |
| 10d | MIRAGE: A Metric-Intensive Benchmark for Retrieval-Augmented Generation Evaluation | — | 2025 | Findings of NAACL 2025 | https://aclanthology.org/2025.findings-naacl.157.pdf |

**10a** — Evaluates each retrieved document individually via LLM, uses downstream task performance as relevance label. Shows traditional recall@k has weak correlation with actual RAG output quality — validates our concern that recall@20 is hollow if the LLM can't use all 20.

**10b** — LLM-judge evaluates context relevance, answer faithfulness, and answer relevance with confidence intervals. Prediction-powered inference addresses domain shift — gives us a methodology for automated eval without expensive human annotation.

**10c** — Reference-free metric suite (context precision, context recall, faithfulness, answer relevance). Foundational framework; context_recall and faithfulness can diverge — high context_recall doesn't guarantee faithfulness when irrelevant chunks dilute signal.

**10d** — 7,560 QA instances with metrics for noise vulnerability, context acceptability, context insensitivity, and context misinterpretation. Moves beyond single-number metrics to diagnose which RAG component fails — applicable to our per-facet evaluation.

---

## Summary of Publication Status

| Status | Count |
|--------|-------|
| Published (peer-reviewed venue) | ~28 |
| arXiv preprint only | ~5 |

Most papers are from ACL/EMNLP/NAACL/NeurIPS/ICLR/SIGIR 2024–2025. Preprints noted where applicable (Multi-Meta-RAG at ICTERI posters; LTRR, Balancing the Blend, ER-RAG, DynamicRAG on arXiv as of mid-2025).

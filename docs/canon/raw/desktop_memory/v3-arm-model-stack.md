---
name: v3-arm-model-stack
description: "v3 eval-harness model stack — shared generator AND RAGAS judge = qwen/qwen3.5-397b-a17b on NIM (one model, both roles; current choice, not frozen); vector-arm embedder = llama-nemotron-embed-1b-v2 (multilingual, 8192-ctx, whole-artifact, exact cosine); lucene = bm25s lucene-variant. all-MiniLM rejected."
metadata: 
  node_type: memory
  type: project
  originSessionId: 47b27a98-6b98-483d-b6a5-fe4ebcda6175
---

DECIDED 2026-06-22 for the v3 (canon) eval harness. The model choices split by
ROLE — not "same checkpoint for everything":

- **Shared generator + RAGAS judge (one model, both roles)** — `qwen/qwen3.5-397b-a17b`
  on NVIDIA NIM (current choice, nothing frozen). One generator injected by the
  orchestrator so the ONLY variable across arms is retrieval, and the same model is the
  RAGAS LLM-judge. Multilingual → HERB (English) now and the deferred Swedish Bonnier set
  later run on the same model, no swap. NIM host details: [[nvidia-llm-host]].
- **Vector-arm embedder** — `nvidia/llama-nemotron-embed-1b-v2` on NIM: multilingual,
  English-strong, 8192-token context. Embeds one document per artifact (mirrors the
  lucene unit); the 8192 context covers every HERB artifact whole (longest ~1.5k
  tokens) so NO truncation and NO chunking; exact brute-force cosine (the ~38.6k-artifact
  corpus is too small to need an ANN index). A deliberate "capable multilingual dense
  baseline" — NOT the English-only, 256-token `all-MiniLM` "textbook naive-RAG" default,
  which is REJECTED (it would truncate the long documents/transcripts and could not
  serve Swedish).
- **Lucene arm** — bm25s `method="lucene"` (the Lucene/Elasticsearch BM25 variant,
  bm25s's default; k1=0.9/b=0.4 BEIR reference defaults; reproduces Lucene's scoring,
  Lucene-*like* analysis not Lucene's Java analyzer). Unchanged by this decision.

**Scoring is HERB + RAGAS only** — every arm, including lucene, is scored by exactly
those two. BEIR/Kamalloo/Robertson are the PROVENANCE of the BM25 configuration, never
an evaluation target.

Why this overrides the earlier "ground references" the user pasted: that note named
`all-MiniLM-L6-v2` + sentence-transformers as the dense baseline. Dropped — English-only
+ 256-token cap is wrong on both axes for a Bonnier-portable, long-artifact corpus.

Still OPEN (not part of this decision): top-k, question set, judge-calibration subset.
The arms are artefact / lucene / vector ([[arms-share-only-corpus-and-generator]]).

"""v2 eval comparison arms for the v2 artefact (not v1).

The two retrieval baselines are Lucene (sparse) and Vector (dense / naive RAG).
Both are INDEPENDENT of the graph artefact and feed the arm-agnostic
`evaluation/ragas_io.py` export contract. The scoring method that reads that export
is a SEPARATE, undecided step (HERB's own per-type extraction-F1 / LLM-Likert,
IR metrics against citations, RAGAS-style judges, or some mix) — not baked in here.
`top-k` is a shared eval knob across both arms.

| Module | Arm | Retriever |
|---|---|---|
| `vector` | dense / naive RAG | SBERT `all-MiniLM-L6-v2`, exact cosine top-k |
| `lucene` | sparse | (to be rebuilt) |

`sql_agent` is DROPPED — no longer a comparison arm; the module is retained for
now but unused.
"""

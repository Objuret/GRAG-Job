---
name: ragas-canonical-sources
description: "canonical RAGAS sources — consult these (paper + official docs) for any RAGAS question, never blogs or memory; refs also live in eval/ragas.py"
metadata: 
  node_type: memory
  type: reference
  originSessionId: aa43d0a9-0963-4d0d-9f0d-c5f594555513
---

When answering ANYTHING about RAGAS, check the official sources — do not answer
from blogs, search summaries, or recollection. The user had to repeatedly redirect
me to the canonical RAGAS material; that's a defect.

Canonical sources (also written into `v3/eval/ragas.py`'s module docstring as a
References block, mirroring lucene.py / vector.py):

- **Paper (EACL 2024, the citation):** Es, S., James, J., Espinosa-Anke, L. &
  Schockaert, S. (2024). *RAGAs: Automated Evaluation of Retrieval Augmented
  Generation.* Proc. EACL 2024 System Demonstrations, 150-158.
  doi:10.18653/v1/2024.eacl-demo.16 ; aclanthology.org/2024.eacl-demo.16 ;
  arXiv:2309.15217. Introduces the reference-free faithfulness / answer-relevance /
  context-relevance metrics.
- **Official docs (metric definitions):** https://docs.ragas.io — Context Precision,
  Context Recall, and the NVIDIA metrics
  (`/concepts/metrics/available_metrics/nvidia_metrics/`). The docs match the pinned
  `ragas==0.4.3` behaviour the eval runs on.

Useful fact already verified there: RAGAS Context Precision is a mean of Precision@k
over the retrieved list; there is NO separate `@k`/cutoff parameter — the list
length IS K, so to score at a depth you truncate the retrieved list and re-score.

Ties to [[verify-before-asserting]] and [[use-established-eval-libraries]].

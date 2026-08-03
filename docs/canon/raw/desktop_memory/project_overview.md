---
name: project-overview
description: "Repo = v3/ HERB evaluation harness (the artefact vs Lucene + Vector baselines, scored by RAGAS ONLY — no HERB scorer); v1/ and v2/ deleted"
metadata: 
  node_type: memory
  type: project
  originSessionId: 076080ac-fe35-473e-9116-ef7fc6727670
---

Post-thesis Graph-RAG work. The repo is now **just `v3/`** — a lean, self-contained
HERB evaluation harness. (v1/ and v2/ were deleted 2026-06-23; their source survives
in git history. The artefact arm, formerly to "wrap v2", is rebuilt natively inside
v3 — see [[v2-graph-spine]] etc. for its design.)

**The harness** compares three answer-producing arms on HERB —
**artefact / lucene / vector** — scored by **RAGAS ONLY**. HERB is the benchmark
DATASET; there is **NO separate HERB scorer** (the old "HERB + RAGAS" framing is
dead — do not reintroduce it from stale docs). RAGAS includes the judge-free
id-based context precision/recall as the headline retrieval signal. The artefact is
the system under test; lucene (BM25) and vector (dense) are baselines, each with its
own index over the corpus. Arms share only the corpus on disk + the injected
generator ([[arms-share-only-corpus-and-generator]]).

Design reference `v3/README.md`; entry state doc
`docs/state/2026-06-18-v3-eval-harness-herb-ragas.md`.

**Why:** thesis is DONE ([[thesis-is-done]]); this is post-thesis canon.

**How to apply:** all work happens under `v3/`, self-contained. One graphify graph
(the codebase nav graph). Session entry: root `CLAUDE.md`.

---
name: arms-share-only-corpus-and-generator
description: HARD v3 rule — the three arms share ONLY the corpus on disk + the injected generator; no shared retrieval/corpus-reading CODE
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 6cb452f8-96a0-447e-bd1e-19385fd699ca
---

In the v3 eval harness the three arms (artifact / lucene / vector) share exactly two
things: the corpus files on disk and the generator the orchestrator injects (the
fairness control). Each arm reads, indexes and ranks the corpus with its own code —
including how it reads the raw product JSON into units. Arms never import or reuse
another arm's corpus-reading or retrieval code; the only shared import is
`contract.py` (the harness shapes), which is not a retrieval component.

**Why:** how each approach turns the one shared corpus into retrieved evidence is the
independent variable the experiment measures. Holding the reader or unit set constant
across arms would confound exactly that.

**How to apply:** keep each arm's reader/ranker self-contained; never propose moving one
into a shared module or having an arm import another's. Duplicated extraction logic
across arms is intended, not DRY debt. See [[v3-arm-model-stack]],
[[baseline-is-sql-agent]], [[no-silent-fallbacks]].

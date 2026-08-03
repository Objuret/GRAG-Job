---
name: ai-cost-boundary
description: "Per-item cost only exists where a model touches the item (interpretation or embedding); deterministic extraction is free and scales — design decisions must respect which side of that line they're on"
metadata: 
  node_type: memory
  type: project
  originSessionId: 5ece6d9f-4381-4d7a-ab13-69e1405e13c9
---

User principle (2026-06-12): "the cost for each extracted thing if using ai, matters. if it's just 'deterministic data extraction' it's one thing, but as soon as it has to be interpreted or embedded, it matters."

**Why:** The v2 pipeline's deterministic prefix (scan → probe → reference → structure → hard fields → chunking) can produce unlimited items at zero marginal cost. The metered operations are exactly two: one tagger LLM call per chunk, one embedding per phrase tag. Anything that adds model-touched items adds real cost; anything deterministic doesn't.

**How to apply:**
- Never propose embedding or LLM-interpreting data that is already exact (e.g. hard-field value vocabularies — proposed and killed 2026-06-12).
- Budget knobs live in the tagger contract: chunk count = LLM calls; tags-per-chunk = embeddings. Treat "sane tag count per chunk" as a cost decision, not only a quality one.
- Nodes-vs-attributes / graph-size questions on the deterministic side are graph-hygiene questions, not cost questions — don't conflate.
- Distinct from [[no-cost-estimates]]: that bans $/time framings at the user; this is a design principle about where per-item cost exists at all.

Related: [[v2-build-pipeline]], [[nvidia-llm-host]] (40 RPM rate limit makes per-call scarcity real even on the free tier).

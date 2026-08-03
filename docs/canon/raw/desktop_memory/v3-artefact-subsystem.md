---
name: v3-artefact-subsystem
description: "v3/artefact/ = the artefact, rebuilt natively from raw. The graph + retrieval (pass 1: lean graph, live facets) is BUILT and runs; precision is bad; pass 2 (curve, channels, relationships) is designed, not built. See [[artefact-pass2-design]]."
metadata: 
  node_type: memory
  type: project
  originSessionId: 1ac39408-276f-4166-abe7-d5ebb60b55ba
---

The artefact (system under test) lives in **`v3/artefact/`**, rebuilt natively from
raw. `herb-eval` is a contrast baseline only, never queried live
([[herb-eval-is-the-artefact]]).

**Deterministic spine — built + tested** (36 tests, `python -m pytest artefact/tests`
from `v3/`): `scan.py` (file catalog), `probe.py` (shape recovery), `chunk.py`
(coherence-episode chunking), `derive_corpus.py` (oracle strip),
`resolver_prototype.py` (hash-verified reference resolution),
`keys/Salesforce__HERB.yaml` (mapping key).

**The graph + retrieval — BUILT and runs (pass 1, 06-28, a parallel session), but
precision is unacceptable per the user's own verdict.** NOT the unbuilt stub this
memory previously described:
- `embed_tags.py` — embeds the tag corpus (22,235 tag instances / 5,377 chunks /
  13,776 unique phrases) with `nvidia/llama-nemotron-embed-1b-v2`.
- `artefact/index.py` — in-memory `PreparedIndex` (mean-centered tag matrix,
  chunk↔tag mappings, hash-verified on-demand reference resolution).
- `artefact/graph_store.py` — Neo4j ingest into a fresh `herb-v3` DB (spine +
  Tag-node-is-its-embedding, no phrase text on the node); DB build currently blocked
  on a local Neo4j server + `NEO4J_PASSWORD`, the in-memory index is the real query
  path and needs neither.
- `artefact/prepass.py` — deterministic exact-literal pre-pass (products/employees/
  customers directories).
- `artefact/interpreter.py` — one-shot NIM flagger (`meta/llama-3.3-70b-instruct`)
  emitting facet phrases + literals + date_range + answer_shape.
- `pipelines/artefact.py` — the combinator: interpret → embed facet phrases →
  mean-center → cosine vs tag matrix → max-pool (ONE pooled facet set, not
  per-channel) → flat accumulate per chunk → +1.0 additive product-literal boost →
  top-k. This flat-accumulate scoring is the precision problem.
- Gold-100 k=10 retrieval-only result: context_recall_id 0.199 vs lucene 0.035 /
  vector 0.045 (~4-5x), but context_precision_id 0.068 vs 0.102/0.148 (worse than
  both) and the nonllm text-overlap metrics worst-of-three. **User verdict: "more
  effective but way fucking worse" is not a good reference — do not cite these
  numbers as validating the design.** Runs slated for deletion.

**Pass 2 — designed, not yet built.** Full design:
`docs/state/2026-07-01-artefact-pass2-dials-curve-relationships.md` (current entry
point — read before touching any artefact code). Headline moves: an exponential
scoring curve (exact=max, steep tail-kill) replaces flat accumulate; per-facet
channels replace the pooled facet set; facets are reframed as relevance **dials**
("how much"), not category **labels** ("which" — entity-type/info-kind move to
structure/interpreter); a graph-relationships reopening (edges from the intra-file
tree, hub nodes for shared/id-space field values) is under live design; DIFFUSE-FACET
(a Personalized-PageRank walk over a mutual-kNN tag graph with per-facet edge
channels) is the gated next-architecture candidate if the curve alone doesn't fix
concentration.

See [[artefact-pass2-design]] (current facet-model canon), [[tag-facets-vs-routing]]
(superseded baseline), [[v2-graph-spine]], [[design-before-build]].

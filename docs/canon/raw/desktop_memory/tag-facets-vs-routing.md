---
name: tag-facets-vs-routing
description: "SUPERSEDED baseline (06-25 guide-link + content-profile): facets = weight+direction measured by geometry; tag-facets ≠ routing. See [[artefact-pass2-design]] for the current cut (facets are dials, not labels) and pass-1 as-built reality."
metadata: 
  node_type: memory
  type: project
  originSessionId: 1ac39408-276f-4166-abe7-d5ebb60b55ba
---

**Superseded 2026-07-01 by [[artefact-pass2-design]].** This memory preserves the
06-25 baseline as history; do not treat it as current. Full current state doc:
`docs/state/2026-07-01-artefact-pass2-dials-curve-relationships.md`.

**Still correct (carried forward):**
- **Model emits no numbers, ever** — weights are measured, downstream. v1 proof: only
  21 distinct w_facet values; agents cannot produce real weights.
- **Tag-facets ≠ routing** — a facet describes the tag's meaning; routing is a
  separate downstream consumer.
- **Topic is not a facet** — the phrase IS the topic; what's left = centrality
  (chunk-local, sibling-relative degree).
- **No hard filters** in ranking; "mandatory" = weight concentration + the cap.
- **The guide link** — a facet = a concept both tag and prompt are measured-close-to;
  hard-validated across independent research lanes; v1's per-facet grounding
  embeddings already were this design.

**Superseded by the pass-2 cut:**
- "Facets = weight + direction, one edge per tag carrying the full facet vector" —
  refined: a facet is specifically a **graded relevance dial** ("how much"); things
  that answer "which" (entity-type, info-kind) are **not facets** — they're
  structure/interpreter. See [[artefact-pass2-design]].
- "Core measure = sibling comparison" for the facet **value** — refined: sibling
  comparison is right for **centrality**, not for the facet value itself (which is an
  absolute projection). Three separate reference frames now: value=absolute,
  centrality=sibling-relative, distinctiveness=corpus-relative.
- The open "facet SET" question — resolved in shape (dials: process/activity +
  centrality safe, a concreteness dial candidate; postures were always interpreter).
- **The instrument** — the 06-25 "measured by geometry (sibling comparison)" was
  never fully realized this way. What's ACTUALLY built (pass 1, 06-28, a parallel
  session): graded facets are computed **live at query time** — the interpreter emits
  facet phrases, they're embedded and cosine-matched against the tag matrix, no
  baked per-tag facet vector exists in the graph at all. Pass 2 adds an exponential
  scoring curve + per-facet channels on top of that live mechanism.

Related: [[artefact-pass2-design]] (current), [[v2-graph-spine]],
[[v3-artefact-subsystem]], [[design-before-build]].

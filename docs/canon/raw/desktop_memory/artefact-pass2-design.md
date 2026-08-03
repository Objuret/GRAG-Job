---
name: artefact-pass2-design
description: "CURRENT artefact facet canon (07-01): facets are relevance DIALS not labels; exponential scoring curve; fuzzy=embedded; per-facet channels; graph-relationships reopening; DIFFUSE-FACET candidate. Pass-1's build exists but its precision is bad — not a good reference."
metadata:
  node_type: memory
  type: project
  originSessionId: 1abfe789-68fd-43ae-9c9b-eec32fb6d019
---

**Current state doc:** `docs/state/2026-07-01-artefact-pass2-dials-curve-relationships.md`
— read this before any artefact facet/retrieval work. It sits on top of a parallel
session's pass-1 build trio (same date family, `2026-06-28-artefact-*.md`) which
built and ran the lean-graph + live-facets arm; that trio's numbers are NOT a good
reference (see below) and its "next task" fork is overtaken by this doc.

**The load-bearing cut (user-established):** *"you HAVE to remember that the facets
are themed RELEVANCE weights.. meaning you have to think about them differently,
like info-kind and entity-type (are they even facets..?)"* — a facet is a **dial**
("how much": process-ness, centrality, concreteness), never a **label** ("which":
entity-type, info-kind). Labels are structure or interpreter concerns, not facets.
This is sharper than the 06-25/06-28 "categorical facet" framing and formally
unreconciled against it — flag, don't assume settled.

**The original multi-step relevance concept (verbatim, still the spirit):** *"the
tag-facets were to inform the RELEVANCE of the TAG, according to that facet, in
relation to it's chunk, and via the chunk's relevance to the file, get an actual
file-relevance too, but skipping the 'to file' part … the facet weight in
COMBINATION with the tag's chunk relevance weight would tell how relevant the tag
actually is in relation to the prompt based on the interpreters evaluation of which
facets are most relevant."* But: *"apparently it didnt work great, so this is not
the same creation anymore."* v1 died because the model emitted the weights (only 21
distinct values); the combinator concept itself was never the problem.

**Decided this session:**
- **The exponential evaluation curve** — per-tag score = a convex transfer of
  similarity, exact match = the ceiling, steep enough to kill the long tail of
  mediocre matches, THEN accumulate per chunk. Shape decided; steepness is a gold-set
  sweep, deliberately left open. Replaces flat cosine→accumulate (the precision
  killer) AND the discrete +1.0 literal boost (an exact match is just the curve's
  ceiling — one mechanism, not two).
- **Fuzzy = embedded, not edit-distance.** *"if it's a fucking 'perfect match' it's
  still a perfect match.. and the closer the better.. and if people spell so fucking
  wrong it's just the wrong product.. we kinda can't 'fix' that this easily.."* No
  typo-fixer — HERB's deliberate near-twins (ContentForce/ContextForce etc.) make
  aggressive correction dangerous. Embedding buys described-entity reach, not typo
  tolerance.
- **Per-facet channels kept up the line** — a chunk carries a facet-relevance
  *profile*, not one collapsed scalar; the combinator is prompt-emphasis ·
  chunk-profile. Collapsing early (like v1's `w_chunk`, like pass-1's max-pool-into-
  one-set) throws the guide link away above the tag tier.
- **Three reference frames, never collapsed:** facet value = absolute (fixed-anchor
  projection); centrality = sibling-relative (chunk-local — the geometry-robust leg,
  survives anisotropy because it's a *relative* local comparison); distinctiveness =
  corpus-relative (the fragile leg — tags are near-unique, so any counting stat needs
  tag-clustering first, and clustering alone gives topics not facets).
- **The graph-relationships reopening** — *"half the strength of a graph is beeing
  able to route/search based on relationships instead of structures."* Two parts: (a)
  the intra-file tree (channel/thread/episode), currently flattened into the
  materialized path, becomes real containment/adjacency edges; (b) hub nodes for
  shared field values in a mid-selectivity band (not near-unique, not
  near-universal — a `kind=slack` shared by every record in an all-Slack file is a
  stopword-node, earns nothing) and for id-space fields (author/product/customer
  ids). Disciplines: reference-never-copy, weighted-and-steep (never re-create the
  §14.1 typicality-smear a hub could flood). **Conflicts with the pass-1 session's
  explicit "no relationship layer" call** (§7 rejected node-per-record/entity as
  "the copies disease at the node level") — that rejection was about mirroring
  records, not derived topology over values with no richer home; the tension is
  real and needs an explicit sign-off, not silent resolution either way.
- **The corrected attribute rule:** repetition-ratio governs ONLY generic short
  scalars. Dates → time-range attribute, unconditionally. Id-space fields → id-set
  attribute, unconditionally. Long text → referenced content, never an attribute.
  Hub-node candidates = the generic-scalar case (mid-selectivity) + id-space fields.

**DIFFUSE-FACET (gated candidate, not yet built):** mutual-kNN graph over tag
embeddings; each facet = a different edge re-weighting channel; interpreter picks
entry tags + a channel blend; Personalized-PageRank restart walk; relevance = settled
mass, not a stored number. Realizes the original multi-step relevance concept as
*emergent* rather than *stored* — no per-tag scalar exists to fail to discriminate.
Build only if the curve + channels alone don't fix concentration (go/no-go test: does
a process-heavy vs specificity-heavy channel blend actually reorder top-k).

**Pass-1 verdict (override the build trio's "the mechanism works" framing):** *"the
precision was absolutely fucking terrible, having built a 'more effective but way
fucking worse' arm is not a good reference."* Pass 1 (flat cosine→accumulate, one
pooled facet set) is the crude query-time-facets baseline pass 2 must beat, not a
success to replicate. Its recall win (0.199 vs 0.035/0.045) came with worse precision
than BOTH baselines — do not cite it as validating the design.

**Do not overfit to HERB** — read facets off the tag's resolved segment (refs make
this free) when clause cues matter, not the bare 3-word phrase; keep the design at
the abstract's spirit level, not HERB's specific quirks.

Related: [[tag-facets-vs-routing]] (superseded baseline), [[v3-artefact-subsystem]]
(current build state), [[v2-graph-spine]], [[graph-is-references-not-copies]],
[[design-before-build]].

# End-to-end construction audit

This audit answers the user's question about how the pieces actually work
together. Rechecked against current executable code after area-first admission
and sponsor-first recovery. It describes our experimental `artefact_facet_joint`
and `artefact_facet_area`, not Claude's historical v3 sort chain. No additional
model calls or benchmark evaluations were made for this construction recheck.

Follow-up: `2026-09-22-graph-composition-diagnosis.md` proves that all 2,375
chat-adjacency links are numerically subsumed by the joint product/channel
groups. It also records the completed sponsor-before-recovery delivery repair.
The repaired behavior is described below. Completed full-arm validation is in
`2026-09-22-facet-area-smoke-results.md`; it does not validate facet semantics.

## Actual path and ownership

1. `artefact_facet_joint._interpret` makes a sought-content description and semantic
   tags, then per-tag/per-facet relevance readings against that description.
   Structural names are handled separately from the raw question. The two paths
   do not form one joint interpretation or a list of explicit answer requirements.
2. `_query_cosines` computes query-tag/graph-tag similarity, query-tag/chunk-description
   similarity and whole-query-description/chunk-description similarity over the
   frozen population. All 4,808 eligible chunks are available before ranking;
   this is not an iterative graph search discovering candidates.
3. `FrozenFacetReference.transform` replaces every graph edge column, including
   topic, with its percentile in a fixed reference distribution. Ordering is kept;
   original distances and zero semantics are not. No probability calibration is
   established by this transform.
4. `rank_facet_stream_envelope` obtains a separate best route for each facet and
   target chunk. A direct route uses query-tag/graph-tag cosine, query-tag/target-
   description cosine, that query tag's facet reading and the edge's facet percentile.
   A graph route transfers a seed's direct support over an actual relation, times
   0.5 and the target's query-tag/description match. These are one-hop offers from
   the best eligible seed in a joint product-and-channel group or adjacent chunk,
   not a repeated graph walk. Product and channel are not separate group routes.
5. For each facet, maxima over query tags and direct/graph routes leave one winner
   per chunk. The score is whole-description similarity times the sum of topic
   support and one quarter of each auxiliary's support. The facets have separate
   winning paths, **not separate delivered batches**. The first collapse to one
   chunk score occurs here, before scope nomination.
6. `_rank` then resolves structural names and forms an area. Scope does not alter
   the preceding cosines, paths or scores. The same chunk scores are ranked
   globally and within the area in `facet_joint`. `merge_frontiers` admits a chunk at its earliest
   rank in either list. For an area member, its area rank cannot exceed its global
   rank; scope therefore changes its admission depth. Score gaps between lists
   have no role in this decision. The optional `facet_area` instead orders positive
   in-area nominations before positive outside nominations, preserving score order
   within each phase. Outside access remains in the full order but the serving
   budget may expire before reaching it. Neither policy changes facet scores.
7. `recruit_with_record_context` assigns every contiguous part of a source-record
   component the earliest depth of any supported member. This can advance chunks
   without improving their own evidence scores. Original nominations now precede
   advanced siblings at each depth; IDs break ties within those classes. Recovery
   can advance an outside-area sibling with an in-area sponsor.
8. `answer_one_question` takes that flattened order, resolves actual source units,
   and applies the shared 72,000-character prefix cut. It can partially deliver
   the boundary unit. The generator sees those texts; ID evaluation credits only
   complete units under the existing harness contract.

## Composition findings

**Several rules replace the ordering produced by the previous rule.** Facet
weighting creates the score, scope converts it to relative admission ranks,
record recovery changes those ranks, and sponsor-first then chunk-ID order resolves within-depth
delivery before truncation. The final context is not simply the best weighted
chunks. Preserving all provenance makes these decisions inspectable, but does
not justify their combination.

**There is no explicit coverage of the query's distinct needs.** A best match to
one query tag can dominate a facet, and no selected-set stage checks whether the
context adds evidence for a different requested part. Whole-description cosine
can help implicitly; it is not an explicit coverage objective. This is a modeling
limitation, not evidence that all multi-part questions fail or that every chunk
must individually answer every part.

**Descriptions gate every facet path.** All direct routes share semantic match
factors, and every final score shares whole-description similarity. A zero final
description factor suppresses all facet support. Graph transfer additionally
depends on a seed's description match and the target's match. This may be a useful
compatibility rule, but means facets are not independent alternative routes around
bad description matching. Graph-route facet support is a proxy from the seed, not
a fresh measurement of the target edge.

**The numeric choices remain conventions.** Fixed percentiles, additive facet
maxima, topic coefficient 1, auxiliary coefficients 0.25 and hop discount 0.5 are
distinct assumptions. Neither code tests nor modest ID gains establish these as
calibrated relevance magnitudes. The operation adds independently chosen facet
support; it is not literally adjusting each individual edge's topic value before
all selection. Whether that operation is the right interpretation remains open.

**Recovery and the serving cut have different grouping guarantees.** Research
recovery can treat a depth as a complete frontier, but the arm requests an unlimited
order and later applies a partial prefix cut. The specific bug where an advanced
sibling could precede its sponsor by ID is repaired. Records/frontiers still are
not atomic under that serving cut. The repair changed no source-ID recall in the
85-case replay, so it is not the main measured recall explanation.

**The intermediate result is internally inconsistent.** `retrieve_prepared_query`
constructs unscoped recruitment, contexts and a policy. `_rank` replaces recruitment
with scoped recruitment while leaving those old contexts and policy attached.
Current final delivery correctly reads the replaced recruitment and resolves its
sources, so this does not corrupt the served texts. The stale fields and duplicated
work nevertheless show that the interfaces have not been cleanly composed.

Computing all scores before resolving scope is not by itself a ranking error:
reordering those computations would yield the same result unless scope changes
search, scoring or scheduling. The relevant issue is what scope is allowed to
influence, not merely the line order.

## What this changes about the work

The recent name/area repair restores one missing connection. It does not establish
that the overall construction implements a coherent evidence-selection rule.
The next reasoning step must specify what information should survive each boundary:
query needs into routes, route evidence into chunk selection, structural support
into ordering, and supporting chunks into the delivered context. Do not substitute
another coefficient comparison for that architectural decision, and do not replace
the largest measured scope effect with a small boundary bug merely because the
latter is easier to fix.

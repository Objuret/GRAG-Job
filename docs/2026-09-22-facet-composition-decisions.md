# Decisions after checking actual operator exposure

The preceding goal turn made progress: a topology proof and a sponsor-first
delivery repair changed the authoritative state. This turn checked whether the
topology issue is materially exposed in saved delivery before choosing a rebuild.

## Keep the full question, not just five numbers

The query readings mean relevance of a query tag to the described content through
a facet. The graph readings concern a tag's relationship to its own chunk. Both
may be strong for a report doing analysis and a record sharing the report. This
is consistent with the user's clarification; neither side should be relabelled
as a universal importance or usefulness score.

For one fixed facet and tag, `u * F` with nonnegative u cannot reverse the ordering
of two F values as the requested activity changes. This is a limitation of that
scalar interaction, not of the whole arm: relation-bearing tags, descriptions
and their matching embeddings can supply the distinction. Query-specific
usefulness therefore must be judged on the whole combination.

Independent review suggested a separate supports/conflicts/missing compatibility
operator. That proposal is not adopted as a new run: the existing CONDITIONAL.md
and FRESH.md experiments already tried related operators, and fresh-case behavior
was inadequate. Fixed-tag failures also omitted useful alternative tag paths.
Repeating a conditional reader would discard those lessons. No new model calls.

## Graph transfer is not the primary measured target

The saved-run route audit finds only two fully delivered chunks with a graph
winner among 1,383 delivered chunks. This does not prove graph transfer causally
irrelevant, but it prevents presenting its redundancy as the main explanation.
Structural scope and recovery remain active independently of these graph scores.

For a fixed query tag/facet and target with positive description match, a graph
route beats a direct route only when:

`best_local(M * F) < 0.5 * best_seed(M * F * D_seed)`

The common query relevance u and target-description factor cancel. The final
whole-description factor and the facet coefficient cannot change this local
comparison either. They can still change which query tag wins and the combined
chunk order. Thus adjusting a global facet coefficient is not a direct repair
for this graph-transfer suppression.

## Research informs a boundary, not a borrowed solution

[HippoRAG 2, sections 3.2-3.5](https://arxiv.org/html/2502.14802v1#S3) integrates
passages into its graph and uses query-to-triple and query-to-passage information
in retrieval. This is useful evidence for treating context and graph signals
together. Its triples, filtering and PPR are a different construction; its gains
do not validate this arm's facet products or supply our coefficients. We do not
replace the artefact with that system or import its hyperparameters.

## Current priority

1. The main unresolved composition is direct facet/tag/description evidence into
   structural area admission, then the real 72,000-character context. Earlier
   saved-trace stage comparisons show a much larger scope effect than auxiliary
   coefficient effects. This is the next implementation decision, not graph-hop
   tuning or another semantic reader.
2. Preserve static edge meanings, query-relative tag relevance and complete
   source provenance. Do not turn every generated tag into an equal required
   need or count multiple tag matches as independent evidence.
3. Any replacement admission policy must state its treatment of high-scoring
   outside candidates versus low-scoring inside candidates. Equal-depth lists,
   strict scope-first order and additive scope boosts embody different tradeoffs;
   none becomes valid merely by removing a tunable number. Literal node matches
   identify an area, not a calibrated numerical exchange rate with semantic fit.
4. Existing weights remain provisional. No new benchmark score has been produced,
   no trained facet has been declared invalid from out-of-distribution controls
   alone, and the research goal remains incomplete.

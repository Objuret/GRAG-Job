# Conditional edge placement and query binding

## Completed result

All 95 cases completed without errors and all frozen hashes stayed unchanged.
Independent recomputation verified the metrics, seed ranges, movement accounting
and all topic-only invariants.

In the recall-leading construction, real edge placement has an average recall
effect of −0.0633 percentage points at original coefficients (seed range −0.4375
to +0.4802), and +0.2763 points at group-selected coefficients (−0.2245 to +1.2792).
The corresponding query-tag binding effects are +0.6997 and +1.0912 points.
Edge shuffling changes full-chunk sets on 55/95 and 70/95 cases respectively.

This is weak evidence for a useful precise auxiliary edge placement beyond the
preserved tag/type distributions in these constructions. It is not proof that
all alternative delivered chunks are wrong or that the facet concepts are
invalid: reference source IDs are incomplete relevance judgments. The next
independent check is existing held-out facet-pair agreement within versus across
source kinds, with training/test provenance and sample counts verified.

## Question and predictions

The coefficient sweep did not establish a clear advantage for the intended
auxiliary query labels. This experiment asks a narrower causal-mechanism question:
does the actual placement of auxiliary values on edges and query tags help the
existing retrieval, beyond preserved graph-tag/source-kind distributions?

If within-tag/type edge placement contributes useful information, real placement
should outperform shuffled placement. If assigning query auxiliary vectors to
particular query tags matters, real assignment should outperform shuffled rows.
The crossed intervention measures whether those two assignments help together.

These are controlled changes to a retrieval computation, not an identification
of a causal semantic relationship in the corpus. In particular, edge shuffling
also breaks relationships with topic strength, products and graph position.

## Frozen design

- Same 95 saved successful queries and five preserved original interpretation failures.
- Canonical, recall-leading and F1-leading structural policies from the completed matrix.
- Original coefficients, topic-largest coefficients selected on other product groups,
  and topic-only. No coefficient is refitted on a shuffled condition.
- Eight deterministic seeds, 0 through 7. Each edge permutation is shared across
  every query/policy/coefficient regime. Each query permutation is shared across
  its paired real/shuffled-edge conditions.
- Four cells: RR (real edges, real query weights), RS (real edges, shuffled query
  weights), SR (shuffled edges, real query weights), SS (both shuffled).

Each edge's four auxiliary values move together within graph-tag × `source_kind`.
All 4,808 source kinds agree with `original_description_metadata.k`. Topic remains
on its original edge; the CDF, graph, areas, descriptions and 72k delivery contract
remain unchanged. Query controls move whole four-vectors between a query's tag
rows, leaving topic on its original row.

There are 57,204 semantic edges in 22,282 tag/type strata. Of these, 42,257 edges
belong to non-singleton strata and 14,947 cannot move. Across eight seeds,
34,738–35,140 auxiliary vectors actually change. The helper verifies the exact
joint vector multiset in every stratum, not just separate column means.

There are 21,375 actual deliveries. The saved metric array contains 27,360 cells
because each real/real reference is repeated across seeds for paired accounting.
Seeds are repeated interventions on 95 queries, not 760 independent queries.

## Integrity and analysis

Seventeen helper tests pass; all eight complete graph shuffles and all 760 query
shuffles were checked for preservation and reproducibility. Every case verifies
its real-condition original and group-selected metrics against the earlier
weight-grid output. Topic-only full orders and full-chunk sets must stay exactly
unchanged in all cells. Ranking does not receive gold, costs or source IDs;
reference IDs join after delivery. No new model calls or DB writes occur.

Report paired effects in recall percentage points, plus precision/F1, seed ranges,
case signs, and equal-product averages:

- Edge placement effect: RR − SR.
- Query-tag binding effect: RR − RS.
- Interaction: RR − RS − SR + SS. Positive interaction means the real assignments
  help more together on this metric scale; neither main effect must be positive.

Also report full-order movement and full-chunk-set changes. These do not capture
changes to the final partial-chunk prefix. Movable coverage and actual downstream
changes must qualify any null result. A positive result supports useful placement
under this construction; it does not, by itself, validate the facet concepts.

The frozen executable protocol and results live under
`output/research/2026-09-22-retrieval-matrix/edge-controls/`.

## Separate input-geometry diagnosis

All 775 query-tag rows were examined numerically, without question/source text or
gold. Only one has exactly equal auxiliary values. The median within-row range is
.35; raw auxiliary Pearson correlations range .042–.390. Within-row facet variance
is 1.70 times variance between tag means. This weakens broad near-uniformity as an
explanation for label-permutation robustness, but does not establish semantic
correctness or locate a suppression step. Formulas, quantiles, per-case summaries
and hashes are in the sibling `query-weight-geometry/results.json`.

The conditioning rationale follows the caution about correlated predictors in
[Strobl et al., Conditional variable importance for random forests](https://link.springer.com/article/10.1186/1471-2105-9-307).
This experiment borrows the conditional-comparison idea; it does not apply that
paper's random-forest estimator or claim its theoretical guarantees for retrieval.

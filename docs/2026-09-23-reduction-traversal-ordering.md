# Reduction placement, description gates and traversal feedback

> **Status update, 2026-09-24:** this population is complete on all 95 cases
> and independently verified in `output/research/2026-09-23-ordering-programs-v2/`.
> Running/pending language below records the original protocol history. Current
> cross-family findings and limitations are in `2026-09-24-structural-outcome.md`
> and `2026-09-24-construction-coverage.md`.

The earlier catalogs kept two consequential dependencies fixed: query evidence
was reduced after graph propagation, and propagation always consumed the query's
description similarity at each destination. These assumptions can affect which
tag/query supports a chunk and whether different queries can sponsor different
steps. They are now explicit alternatives in `tools/facet_ordering_programs.py`.

The declared comparison crosses:

- Query reduction before tag-edge aggregation, after edges but before traversal,
  or after traversal. Early reduction also reduces the destination query gate;
  it does not silently recreate independent query rows during traversal.
- Query-description gating at every step, once after the walk, or absent from
  traversal. Other description uses (tag/description matching and whole-question
  destination scoring) stay explicitly present in these matched contexts.
- One, two or four transport steps; either only the last step feeds the next,
  or original seeds rejoin by maximum before each additional step. Intermediate
  revisits are permitted. These are finite-depth hypotheses, not convergence
  claims or candidate limits; repeated walks are not counted as independent facts.
- Joint versus independent facet recruitment, product versus maximum matching,
  and channel versus Employee-intersection shared-membership projections.

This gives 360 structural constructions plus an unchanged canonical reference.
The contexts use mean query reduction, strongest edge aggregation, group paths,
direct/graph intersection, saved scope and area-first admission. Those fixed
context choices remain visible, and are not a claim of exhaustive exploration.
All operations run in the existing graph-only engine; no corpus body or gold is
added to retrieval input. The original sealed catalogs and engines are unchanged.

Three focused tests pass: exact reference transformation parity, execution of
every declared construction with early query axes remaining collapsed, and
noncommuting reduction/gate witnesses on a synthetic graph. The synthetic witness
uses opposing query-tag evidence to demonstrate that mean-before-maximum differs
from maximum-before-mean; the first fixture did not distinguish those placements.

The first smoke executed 360 programs but failed independent delta verification:
the generic verifier assumes the first row is the canonical reference, which the
new catalog omitted. Its evidence is preserved in `2026-09-23-ordering-smoke`;
the briefly started population run `2026-09-23-ordering-programs` was stopped and
marked retired. These outputs must not be reported as verified population results.
The additive `facet_ordering_lab_v2.py` entry point includes the canonical row;
use `ordering-smoke-v2` and `ordering-programs-v2` for subsequent verification.

The corrected one-case smoke passed independent verification of all 361
deliveries, hashes, metrics and boundary accounting. The full 95-case v2 run is
now executing. Smoke success establishes integration and accounting only, not a
population finding or preferred ordering.

The combined page reads the new run's status and will load the exact operation
graph from its completed results. Loading its factors alone would erase these
ordering changes, so custom programs travel with their leaderboard records.

Directed traversal, convergence-based numeric propagation and other recruitment
interleavings remain separate uncovered choices. This comparison addresses the
identified fixed dependencies; it does not finish the broader objective by itself.

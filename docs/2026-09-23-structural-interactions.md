# Verified dependencies between construction choices

`tools/facet_structural_findings.py` analyzes completed case outputs without
reading corpus text or changing retrieval. It includes the new ordering dimensions
in matched comparisons. It also identifies four-corner comparisons: change A in
two contexts that differ only in B, with all other declared dimensions fixed.
The analysis test checks that diagonal, confounded pairs are excluded and that a
known sign reversal is recovered. Parent population deliveries were independently
verified before this analysis.

## Graph projection depends on traversal order

On all 95 original cases, with independent facet recruitment, direct/graph
intersection and equal-depth scope admission:

| Shared-membership projection | Adjacency then group | Group then adjacency |
| --- | ---: | ---: |
| Employee-product | 825 (`route_118`) | 860 (`route_126`) |
| Product-channel | 1,036 (`route_022`) | 822 (`route_030`) |
| Change to Product-channel | +211 | -38 |

Cells count credited gold-source links summed across questions, each with its
own 72,000-character budget. Switching to channel groups helps in the first
traversal order and hurts in the second. The graph projection and traversal
order therefore cannot be selected independently from this evidence. These
particular contexts are not the overall leaders.

The four programs otherwise share product tag/description matching, strongest
edge and sponsor aggregation, maximum query reduction, separate facets, half
attenuation at each step, whole-question description scoring at destinations,
saved scope after traversal, automatic nomination and recovery. Here automatic
nomination means independent batches for the facet streams. Shared memberships
are symmetric projections, not a test of directed relationship traversal.

## Scope formation depends on admission

Changing area-only to equal-depth admission loses 454 gold-source hits with
saved scope (`program_036` to `program_000`) but gains 434 with query-seed
intersection scope (`program_676` to `program_034`). Those four programs share
all other declared settings. This does not show that exclusive scope is generally
good or bad: its usefulness depends on what defines that scope.

## Description recruitment depends on direct/graph joining

Moving whole-question description evidence from destination multiplication to
an independent recruitment stream loses 162 hits with direct/graph intersection
(`program_021` to `program_548`) but gains 641 with exclusive direct/graph support
(`program_023` to `program_554`). The independent description stream can recruit
outside the support remaining after that exclusive join. Under automatic
nomination this also changes a single joint stream into independent batches;
it is a declared compound construction change, not an isolated description-weight
effect. It does not establish that description-only recruitment is best overall.

## Inspect and continue

The page's interaction section loads each exact pair, pins its left construction
as baseline and replays the right one on the chosen case. Population deltas and
current-case delivery are labelled separately. Source pointers and chunk ranks
remain inspectable. The page shows a small selection of strongest reversals
across distinct pairs of interacting dimensions; full analysis files preserve
all matched effects, including neutral and consistently signed effects.

Evidence files: `structural-findings.json` in the completed
`2026-09-23-construction-programs-fast` and `2026-09-23-entity-route-programs-fast`
output directories. These are development-set source-ID diagnostics, not RAGAS
or evidence of generalization to unseen questions. The two active combined and
ordering comparisons must still finish before their population conclusions can
be added. The broad structural objective remains active.

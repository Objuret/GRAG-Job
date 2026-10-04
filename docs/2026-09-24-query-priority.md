# Query-relative multikey tag priority

This bounded comparison closes a specific remaining coverage gap. The old
120-permutation population used a fixed global facet order. Per-query facet
priority had been exercised in the older forum replay, on two diagnostic
questions, but not across the combined graph construction's original95 cases.

For each query tag, sort graph tags by their five outgoing-facet-qualified
query-match values. Compare facet columns lexicographically in descending order
of that query tag's captured facet relevance. Zero-relevance facets are omitted.
Equal relevance uses the canonical facet index (topic, temporal, why, activity,
concreteness); this is an explicit deterministic convention, not a validated
semantic preference. Exactly equal positive tuples share a complete tier.
All-zero tuples provide no evidence. No pool cap or score bands are introduced.

The scalar comparator is the unchanged outgoing_max / queries tag frontier.
Its positive per-facet constants are unnecessary in the lexicographic keys:
they cannot change comparisons within a column. Facet relevance determines key
priority instead. Query-only keys would be proportional copies of tag cosine,
so that redundant lexicographic condition is excluded.

Each of the two fixed selected downstream programs receives first-sponsor or
all-sponsor evidence. First uses the unchanged binary first-tier gate; all uses
the unchanged reciprocal-tier gate. Description, graph traversal, scope and
chunk nomination after this gate remain as in that parent. Thus the experiment
tests four new programs against four scalar controls, two unchanged parents and
the canonical guard: eleven programs. It does not claim to enumerate every
possible combination of lexicographic keys and graph operations.

Code: `test/artefact/facet_query_priority.py`, `tools/facet_query_priority_lab.py`.
The `query_priority` program field records method and sponsor choice. Retrieval
accepts only GraphInput and numeric readings; gold and 72k delivery happen later.
Tests cover priority permutation with distinct relevances, zero exclusion,
complete tied tiers, explicit equal-priority behavior and exact scalar gates.

Run `python tools/facet_query_priority_lab.py plan`, then `batch`. Independently
verify with `tools/verify_facet_program_results.py`; then use
`tools/facet_query_priority_parity.py --out output/research/2026-09-24-query-priority`
to compare all six unchanged controls against the original tag-frontier run.
Population completion and outcomes must be read from those generated artifacts;
this design document is not a completion claim.

## Verified original95 results

The population completed 95 x 11 = 1,045 independently verified deliveries.
All six scalar/unchanged controls reproduce their earlier full-order hashes and
delivery accounting across all 95 cases (570 comparisons).

| Downstream parent | Sponsors | Scalar hits | Lexicographic hits | Change | Macro recall change (0–1 scale) |
| --- | --- | ---: | ---: | ---: | ---: |
| Two-step joint / macro parent | First | 1941 | 1954 | +13 | +0.0060054 |
| Two-step joint / macro parent | All | 1816 | 1776 | -40 | -0.0113283 |
| Four-step facets / total-hit parent | First | 1840 | 1807 | -33 | -0.0090466 |
| Four-step facets / total-hit parent | All | 1782 | 1892 | +110 | +0.0224398 |

The strongest new rule is the two-step joint parent with lexicographic first
sponsors: 1,954 source-ID hits and 0.53621739 macro recall. Its unchanged parent
has 1,939 hits and 0.53232927 macro recall. These are source-ID retrieval metrics
under 72k serialized characters, not RAGAS. Selection used gold outcomes; the
fixed resulting retrieval rule requires no gold at runtime. The opposite signs
across sponsor and downstream contexts refute a universal preference for the
lexicographic operation. This is a structural interaction, not a weight sweep.

A follow-up in `tools/facet_query_priority_directed.py` crosses this one new
seed with two management bindings, three directions and three placements.
It retains the unchanged seed and canonical guard (20 programs; 19 seed
contexts). Maximum sponsor aggregation and .5 decay stay fixed in this bounded
bridge. Its plan and verification are separate artifacts under
`output/research/2026-09-24-query-priority-directed`.

## Verified priority and directed-route integration

The 95 x 20 bridge completed with 1,900 independently verified deliveries.
The canonical and unchanged lexicographic controls match all original full-order
hashes and delivery metrics (190 comparisons). Parent artifact hashes pass.
The explicit user stop left 66 saved case files; after the authorized resume,
all 66 are byte-for-byte unchanged (`resume-integrity.json`). The original
checkpoint timer was 1,098.44 seconds; the resumed timer was 472.57 seconds.
These are separate run segments, not a measured end-to-end walltime.

No tested management-route addition improves this seed's aggregate hits or
macro recall. All six parallel additions retain 1,954 hits and 0.53621739
macro recall. Equal scores do not imply identical full rankings: their full
order matches the parent on only 48–58 of 95 cases.

| Channel management route placed before existing walk | Hits | Macro recall | Cases gaining / losing / tied on hits versus seed |
| --- | ---: | ---: | --- |
| Forward | 1950 | 0.52995953 | 8 / 11 / 76 |
| Reverse | 1814 | 0.49003895 | 11 / 18 / 66 |
| Symmetric | 1951 | 0.53111242 | 9 / 11 / 75 |

Replacing the existing walk with management routes lowers total hits to
1,590–1,759 across these six replacements. Product-bound management before
the walk gives 1,914 hits and 0.51048638 macro recall for all three directions.
Direction and placement therefore affect the combined retrieval, but adding
the management relation is not automatically useful. This conclusion concerns
the 19 stated seed contexts; it is not a claim about every possible graph walk.
Evidence: `control-parity.json`, `resume-integrity.json`, `report.json`,
`matched-parent-effects.json`, and all immutable per-case delivery files.

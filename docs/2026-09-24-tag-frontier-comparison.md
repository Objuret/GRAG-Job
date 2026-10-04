# Graph-tag frontier construction comparison

This additive experiment tests a structural order that the previous operation
graph could not express: graph tags recruit before their `HAS_TAG` edges are
reduced to chunks. It changes only value-only retrieval. Source bodies, gold,
serialized lengths and source locators remain outside the retrieval engine.

## Declared alternatives

The first 27-program comparison includes the canonical reference, both fixed
rules exported in `output/research/2026-09-24-structural-selection/`, and 24
tag-frontier variants. For each selected rule, tag scores use either numeric
query-to-graph-tag matching alone or that matching qualified by the strongest
outgoing edge facet reading for each tag. Scores form a joint stream, independent
facet streams, or independent query-tag streams. Every positive complete score
tier participates; there is no top-k frontier. For each facet/query/chunk, the
`first` policy retains incident edges whose tag is in that chunk's earliest
positive tier. The `all` policy retains all positive-tag edges with reciprocal
tier depth. These gates multiply edge evidence **before** `edges_to_chunks` and
the selected rule's graph traversal. The original rules are unchanged controls.

The first comparison does not enforce final chunk order by tag arrival: the
selected rule's downstream scores and nomination still decide the order. Thus
it isolates evidence admission and is not alone a full tag-batch scheduler.

A separately versioned 75-program follow-up splits sponsor inclusion from tier
weighting: first/all sponsors × binary/reciprocal tier weight. It uses a
query-only tag score and crosses joint, facet and query-tag streams in each
parent. Each gate is
then evaluated with the original downstream nomination, with own tagged-chunk
arrival priority, and with earliest shared-group sponsor arrival priority.
Independent tag streams nominate their next unseen complete score tier per
round, sharing a visited tag set. Eligible chunks enter at their tag arrival
round; the original downstream chunk order breaks ties within a round. The
parents' area-first stratum remains outside the tag-round order. Record-linked
siblings inherit their component's earliest arrival. These are explicit
construction choices, not universal semantics for graph routes. The inherited
arrival is based on shared-group reachability among graph chunks; it is not a
claim that the earliest member supplied the winning numeric propagation path.

## Reproduce and interpret

From the repo root, with `PYTHONPATH=prod;test;tools`:

```powershell
.venv/Scripts/python.exe -B tools/facet_tag_frontier_lab.py plan --out output/research/2026-09-24-tag-frontier-programs
.venv/Scripts/python.exe -B tools/facet_tag_frontier_lab.py batch --out output/research/2026-09-24-tag-frontier-programs
.venv/Scripts/python.exe -B tools/verify_facet_program_results.py --out output/research/2026-09-24-tag-frontier-programs
.venv/Scripts/python.exe -B tools/facet_tag_frontier_followup.py plan --out output/research/2026-09-24-tag-frontier-followup
.venv/Scripts/python.exe -B tools/facet_tag_frontier_followup.py batch --out output/research/2026-09-24-tag-frontier-followup
.venv/Scripts/python.exe -B tools/verify_facet_program_results.py --out output/research/2026-09-24-tag-frontier-followup
```

The first population completed all 95 cases and all 2,565 deliveries passed
independent source-ID, input-hash and 72,000-character accounting checks. Its
best fixed total-hit rule, `tag_frontier_best-macro-recall_query_only_queries_all`,
gets **2,008** hits and 52.6991% macro recall, versus 1,939 hits and 53.2329%
for its unchanged parent. Across cases it wins 22, loses 20 and ties 53. The
first population's best macro rule,
`tag_frontier_best-macro-recall_query_only_queries_first`, gets **53.5435%**
macro recall and 1,934 hits; it wins three cases, loses one and ties 91 against
the unchanged parent. These are different choices with different tradeoffs.
The 75-program arrival-priority follow-up completed all 95 cases; all 7,125
deliveries passed independent source-ID, input-hash and 72,000-character
accounting checks. The gate-only 2,008-hit rule remained its total-hit leader.
Every one of the 48 matched `own` or `inherit` tag-arrival variants lost both
total hits and macro recall against the identical gate-only rule. The best
`own` variant reached 1,566 hits; the best `inherit` variant reached 1,760.
The least harmful matched arrival change still lost 96 hits. This supports
letting tag tiers alter evidence before edge reduction while leaving final
chunk order to the downstream construction in these tested contexts.

The follow-up also separates two mechanisms conflated in the first population.
In the macro parent's independent-query-stream context, all-positive/binary
support reproduces its 1,939 hits, first/binary support gives 1,934 hits and
the best macro recall of 53.5435%, while first/reciprocal and all/reciprocal
each give 2,008 hits and 52.6991% macro recall. The two reciprocal rules do
not have equivalent orders: they differ on all 95 cases and have identical
fully delivered chunk lists on only 65. Their aggregate equality is a tie on
the declared metrics, not a semantic equivalence.

The programs keep the selected parents' fixed facet coefficients, graph route,
scope, traversal length, recovery and 72,000-character serving rule. Results
are development-set comparisons on the same 95 cases that selected the parents;
they do not support held-out generalization or answer-quality claims. The
verifier checks source-ID metrics, complete/partial delivery and seals, but
does not independently rerun every numerical ranking. A unit-gate parity
script compares unchanged parent scores and full orders with the isolated
engine; a separate fast-versus-slow script checked all states and full orders
for 24 real-case gate variants before the follow-up population started.

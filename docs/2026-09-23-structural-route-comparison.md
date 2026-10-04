# Structural routes and query scope: evidence and running comparison

This continues the construction investigation while the sealed 693-program
operation-wiring comparison runs. Its inputs, code and checkpoints are unchanged.
Both experiments now have one combined page served by
`tools/facet_combined_workbench.py` at `http://127.0.0.1:8773`.

## Scope evidence that changed the next experiment

`tools/facet_scope_capture.py` applied the existing exact-name structural resolver
to all 95 queries, privately and mechanically. It exported only graph pointers,
ordinal landing IDs and numerical/provenance metadata. No query text, source
bodies or gold was exported or used to choose the scopes. Output is in
`output/research/2026-09-23-structural-scope-inputs/`.

All 95 queries landed on Product nodes; 18 also landed on Company nodes that have
no enabled route in this structural capture. No query landed on an Employee or
Channel using the existing exact-name resolver. The structural default matches
the current resolver on every case and differs from the old saved area in 18.

The 96 declared combinations of route filtering, route/binding/name joins,
unrouted-node treatment and empty-scope behavior collapse to only three masks
per case. This is a reason not to present a 96-way scope sweep as broad evidence
about employee/channel retrieval. It also exposes how an unrouted name can erase
an otherwise usable product-area nomination through the current intersection
and abstention rule. That observation is about the construction, not whether an
unrouted name is semantically a constraint.

## Shared-entity graph traversal comparison

The alternative entry is from recruited graph chunks through actual shared
structural memberships. No exact employee-name mention is required. These are
symmetric chunk-to-shared-entity-to-chunk projections; they do not establish
directed traversal semantics or invent relationships between source contents.

`tools/facet_structural_routes.py` builds the following projections from the
pinned structural graph. Duplicate membership sets are collapsed.

| Projection | Distinct nonsingleton groups | Chunks with a route |
|---|---:|---:|
| Shared Product+Channel | 252 | 2,620 |
| Shared Product | 30 | 4,808 |
| Shared Employee through Channel | 398 | 2,620 |
| Shared Employee through Product | 62 | 4,808 |
| Shared Employee, union of Channel/Product routes | 172 | 4,808 |
| Shared Employee, intersection of Channel/Product routes | 311 | 2,500 |
| Product+Channel plus Employee union routes | 424 | 4,808 |

Shared Channel alone has exactly the same projected groups as Product+Channel
in this pinned eligible graph. That equality is checked and its duplicate is
excluded from the batch (the page can still display it for inspection).

`tools/facet_route_program_lab.py` runs **224 matched programs**: seven distinct
projections crossed with four graph-route orderings (parallel, groups only,
adjacency then group, group then adjacency), two recruitment rules (joint,
independent facets), two direct/graph joins (union/intersection), and two scope
admissions (equal depth/area first). The reference is included and checked for
full-order equality to the old arm. Query maximum, edge maximum, sponsor maximum,
facet coefficients, description-at-destination and record recovery are controls
in this matched comparison; their alternatives belong to the operation-wiring
experiment and subsequent combined comparisons, not an implied completed cross.

The first case completed all 224 programs and passed independent source-ID and
72k partial-boundary accounting checks. The full 95-case run is underway. Read
its current status and verifier output before quoting population results.

The browser was exercised with the Employee union route: grouped access expanded
from 2,620 to 4,808 chunks on `case_001`, but reference union delivery remained
13/45 gold sources. This is a verified example where a different graph path
does not improve the delivered prefix, not evidence of a winning construction.

## Execution and continuation

```powershell
.venv/Scripts/python.exe -B -X utf8 tools/facet_route_program_lab.py
.venv/Scripts/python.exe -B -X utf8 tools/facet_combined_workbench.py --port 8773
.venv/Scripts/python.exe -B tools/verify_facet_program_results.py --out output/research/2026-09-23-entity-route-programs
```

Outputs: `output/research/2026-09-23-entity-route-programs/`. Plans and completed
case files are sealed/resumable; keep the older experiment intact. The combined
page shows both live completion states and, when each population completes,
their fixed-rule leaderboards sorted by total gold hits or macro recall.

Next: finish both population runs and independent verification; inspect matched
route effects and component interactions, then test the resulting higher-order
compositions. Do not select a different configuration for each case using gold
and call that a usable retrieval policy. Broader directed routes, iterative
evidence propagation, further recruitment interleavings and the four-case retry
capture remain unfinished. The existing structural capture postdates the original
numeric inputs: eligible/Product/Channel identity was checked, historical
Employee-edge equality was not established. Neither run is a RAGAS evaluation.

## Completed route results

The parity-verified faster continuation finished all **95 cases × 224 programs
= 21,280 deliveries**. Authoritative completed output:
`output/research/2026-09-23-entity-route-programs-fast/`. Independent verification
checked every source-ID metric, full/partial boundary credit and sealed input
hash. All reference score/order checks passed. The 224 settings produced 136
distinct population full-order signatures; setting count is not effective breadth.

The best fixed rule by total gold-source hits was `route_179`:

1. Combine tag-match, query-tag/chunk-description readings and facet evidence
   on graph edges using the reference product rule.
2. Keep the strongest graph-tag edge for each query/facet/chunk.
3. Propagate through adjacency, then through shared-Employee groups whose
   members are reached by **both** that employee's Channel and Product routes.
4. Require direct and graph support (minimum/intersection).
5. Use maximum across query tags, then the fixed facet sum; apply the whole-query
   description reading at the destination.
6. Admit the saved product area first, then outside; use joint nomination and
   recover linked record chunks. Apply the unchanged 72k serving cut afterwards.

This rule credited **1,780 of 3,765 per-question gold-source links** (47.2776%
micro recall); mean per-case recall was **48.6140%**. It is a fixed runtime rule,
selected using results on these same cases, not a gold-driven per-case selector.

| Matched contrast | Gold hits, left → right | Mean recall, left → right | Right wins / losses / ties |
|---|---:|---:|---:|
| Product+Channel → Employee intersection; same adjacency-then-group wiring | 1,679 → 1,780 | 44.0995% → 48.6140% | 30 / 22 / 43 |
| Group-then-adjacency → adjacency-then-group; same Employee intersection | 1,691 → 1,780 | 47.4319% → 48.6140% | 23 / 18 / 54 |
| Parallel → adjacency-then-group; same Employee intersection | 1,746 → 1,780 | 49.4006% → 48.6140% | 13 / 14 / 68 |
| Joint → independent facets in the highest-hit wiring | 1,780 → 1,771 | 48.6140% → 48.6031% | 10 / 13 / 72 |

The best mean-recall rule is `route_163`, the parallel version: 49.4006% mean
recall and 1,746 hits. Thus maximizing total hits and treating every query equally
select different orderings. Both are retained as candidates, not collapsed into
one claim about the universally correct order or concurrency.

Relative to the original reference (`route_000`, 1,059 hits and 29.5595% mean
recall), `route_179` changes several mechanisms together. Its +721 hits must not
be attributed solely to the Employee relation. The matched +101-hit contrast
above isolates that relation change within its stated context.

Independent facet recruitment helped the previously inspected single case but
is not universally better; in the highest-hit route context it loses nine total
hits. Likewise, broader Employee-union reach was weaker than requiring agreement
between its structural routes in this catalog. These are measured construction
effects, not semantic validation of the facet measurements.

The finite-catalog per-case oracle would credit 2,250 hits and 64.0536% mean
recall. It reads gold to select a setting per case and is **not deployable** or a
universal bound. The best fixed rules remain below the earlier 51.6586% mean
recall result from a different matching/query-reduction construction. Combining
those choices with these graph routes is still required; this route comparison
does not establish a new overall winner.

Full executable choices are saved in `best-by-gold-hits.json` and
`best-by-macro-recall.json` in the completed output directory. The combined page
now exposes the completed route leaderboard. The 693-program operation run is
still active; higher-order search awaits its complete population results.

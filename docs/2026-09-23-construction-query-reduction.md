# Retrieval construction: first structural comparison

This continues `state/2026-09-23-retrieval-construction.md` section 12 (section 5
in the shorter handoff). Previous evidence, scripts, sealed plans and outputs
remain intact. This is a contained experiment, not an approved serving design.

## Construction contract and coverage ledger

Intent comes from the state document's section 3: “the combination of the
tag-path, the chunk_description-manouver, graph-shape(scope etc) TOGETHER”;
“each facet recruit a batch of their own? or.. maybe not”; and the request to
explore combinations, orderings, relationships and dependencies. Alternatives
below are agent hypotheses, not additional user rulings.

| Intended role | Current operation and fixed assumption | Alternative family | Observable consequence and coverage |
|---|---|---|---|
| Tag paths and chunk descriptions together | `facet_operator_matrix.score_families`: product/min/max similarities; best edge per facet and query | Accumulate distinct edges, or retain joint witnesses | Edge maximum remains fixed in this first comparison; untested |
| Multiple query tags contribute | Same function: maximum over query tags after direct/graph join | Maximum, equal mean, minimum over distinct numeric readings | **Implemented here**: changes score/order and potentially positive support; preserves graph and all other operations |
| Facets recruit | Facet winners become a weighted sum or score streams before common depth scheduler | Independent materialized batches and interleaving, facet-specific access | Still untested; this experiment does not relabel score columns as independent recruitment |
| Graph relationships find evidence | `_graph_primitives`: undirected locator adjacency and shared Product+Channel, one hop, self excluded, 0.5 times seed support times destination description | More paths, direction, multi-stage traversal with cycle control | Live topology inspected; alternative traversal remains untested |
| Scope follows graph landings | Current arm resolves exact names; numerical replay reads historical saved membership | Discover/expand/merge scope during retrieval | Scope **discovery** unchanged; all/equal-depth/area-first admission crossed here |
| Evidence precedes context | `schedule`: component minimum depth advances touching/overlapping exact-record parts | Revisit evidence after context, evidence-first scheduling | Recovery on/off crossed; component rules unchanged |
| Comparable delivery | Full order followed by `facet_gold90_stage_budget.cut` | Delivery retained as common serving condition | Same 72,000 serialized characters; partial boundary earns no new IDs |

## Declared comparison (before population evaluation)

All 95 captured successful cases, with the original five failures explicitly
excluded. Four later successful interpretation retries are not numeric captures
and are not mixed into this population. No model calls or database writes.

Three reducers operate on `[facet, query-tag, chunk]` support **after** the
direct/graph join and **before** facet summation:

- Maximum: existing reference, including full-order parity checks.
- Mean: equally averages distinct numeric query readings. Tests shared support;
  does not claim that multiple supporting tags prove relevance or independence.
- Minimum: conjunctive control. A zero from any query reading vetoes that facet's
  support. Tests the consequence of treating every reading as necessary.

Exact duplicates of query-tag cosine rows, chunk-description cosine rows and
query-facet vectors count once. Distinct paraphrases can still repeat evidence;
this control is not semantic deduplication. The mean and sum differ only by a
query-constant positive factor in these scalar ranking contexts, so another sum
run would duplicate the comparison without adding a construction question.

Two existing route contexts: product/both/union and maximum/groups/intersection.
Each crosses all/equal-depth/area-first scope admission and recovery off/on:
12 contexts × 3 reducers × 95 cases = 3,420 deliveries. Coefficients remain
`[1, .25, .25, .25, .25]` throughout. The second route context was previously
outcome-selected; it is included as sensitivity analysis, not held-out evidence.
There is no coefficient search. These limits isolate the reducer across global,
mixed and strict scope priority and context recovery; they are not a claim to
exhaust the architecture space.

`case_001` is the mechanical trace case, chosen by manifest order before reading
outcomes. No question, answer, judge explanation or source body is inspected.
All case outcomes, including losses and unchanged deliveries, are saved.

## Executable artifacts

- `tools/facet_construction_lab.py`: numeric comparison, checkpointed case runner,
  sealed source/input hashes, trace and local browser/API.
- `tools/construction_lab.html`: swappable reducer/context, full chunk movement
  table, gold-linked filtering and ranking of completed settings.
- `test/tests/test_facet_construction_lab.py`: reference parity, duplicate and
  permutation controls, single-query equivalence, shared-support reversal and
  conjunctive access-loss example.
- `output/research/2026-09-23-construction-query-reduction/`: new outputs only.

From the repository root:

```powershell
.venv/Scripts/python.exe -B -X utf8 tools/facet_construction_lab.py batch
.venv/Scripts/python.exe -B -X utf8 tools/facet_construction_lab.py serve --port 8771
```

The separate lab preserves the earlier server and historical experiment hashes.
It reuses the existing input loader, scheduler, delivery and evaluator. Its API
is `/api/status`, `/api/leaderboard`, and `POST /api/replay` with `case_id`,
`policy` and `reducer`. Batch resume refuses changed input/source hashes.

## Interpretation limits

This experiment challenges a retained aggregation assumption. It does not
complete independent recruitment, alternative scope discovery, traversal,
facet measurement validation or the outstanding interpretation retry repair.
No winning setting is promoted to production. Source-ID metrics are incomplete
relevance observations on reused cases, not answer quality or generalization.

## Completed results

All 95 cases completed: 3,420 deliveries. Exact reference-score and full-order parity passed; all sealed source/input hashes were unchanged. Independent recomputation from saved delivered chunk IDs verified all source-ID metrics and partial-boundary accounting. 160 focused tests passed.

| Route and scope (recovery on) | Reducer | Recall | Precision | F1 | Recall wins/losses/ties |
|---|---|---:|---:|---:|---|
| product/both/union/equal_depth | maximum | 29.559% | 9.220% | 12.840% | 0/0/95 |
| product/both/union/equal_depth | mean | 30.139% | 9.706% | 13.240% | 27/18/50 |
| product/both/union/equal_depth | minimum | 19.802% | 7.013% | 9.380% | 25/43/27 |
| product/both/union/area_first | maximum | 40.208% | 12.701% | 17.602% | 0/0/95 |
| product/both/union/area_first | mean | 43.942% | 13.463% | 18.758% | 33/22/40 |
| product/both/union/area_first | minimum | 33.019% | 10.887% | 14.656% | 31/43/21 |
| maximum/groups/intersection/area_first | maximum | 48.774% | 11.458% | 16.899% | 0/0/95 |
| maximum/groups/intersection/area_first | mean | 51.659% | 12.777% | 18.700% | 29/14/52 |
| maximum/groups/intersection/area_first | minimum | 41.930% | 10.351% | 15.040% | 28/44/23 |

Denominators are 95 for every metric above. F1 is the mean of per-case F1, not F1 computed from macro precision/recall. Wins/losses/ties compare with maximum in the same context.

Best fixed observed setting here: **51.658615% recall**, **12.776532% precision**, **18.700451% F1**: mean query aggregation, maximum matching, groups, intersection, separate-facet sum, description multiplication, area-first, coefficients `[1,.25,.25,.25,.25]`; recovery on/off tie. Matched maximum with these coefficients reaches **48.773584%**: a **2.885031 percentage-point** difference, 29 wins / 14 losses / 52 ties. Mean changes full delivered sets on 91/95 cases in this context; candidate access changes on 0/95.

The previous full weight-cross best remains **51.034854%**, confirmed from its recorded report. The new observed best exceeds it by **0.623761 points**. That comparison changes coefficients as well as aggregation; the matched 2.885031-point comparison above isolates aggregation. Neither is held-out validation.

Across all declared contexts, mean has the same positive candidate access as maximum. Minimum changes access in every case in the displayed contexts and loses substantial aggregate recall. This distinguishes ranking changes from a conjunctive access veto. Gold-linked movement alone cannot establish semantic relevance.

## Mechanical trace and live graph

`case_001` has seven distinct numeric query readings and a saved area of 151 chunks. Before the whole-description gate, direct support reaches all 4,808 chunks, adjacency 3,189, and grouped support 2,620. The prepared graph has 2,787 undirected locator-neighbor pairs, 302 product/channel groups and 4,396 recovery components (including singletons). After description gating/recovery, the traced reference and mean each expose 4,807 chunks.

The first reference chunk `079df8921aa550c042139ad3` is a direct winner in all five facets. Its topic winner uses query row 3: tag cosine 0.287794 × chunk-description cosine 0.470389 × query topic 1.0 × edge-topic CDF 0.938579 = 0.127060 direct support. Its graph offers are smaller (adjacency 0.026805; group 0.029590). Temporal instead wins on query row 1. After facet combination and whole-description cosine 0.430959, maximum score is 0.082509; average is 0.023065. Nomination/recovered depth moves from 1 to 3. This is a numerical trace, not an interpretation of source content.

In this trace, the same 72k serving cut delivers 12 full chunks in both conditions, but credited reference IDs change 13/45 → 17/45. The mean partial boundary delivers 5,034 of 6,441 characters and earns no new ID credit. Complete movement records are in `case_001-trace.json`; intermediate arrays are in `case_001-stages.npz`.

Read-only live inventory: 4,869 Chunk nodes, 16,714 Tag nodes and 62,028 HAS_TAG edges. The 4,808 product-linked live chunk IDs exactly match the frozen eligible chunk IDs. This does not establish equality of live and frozen facet values or edges. Live Employee→Channel/Product/Employee and File→Chunk/structural relationships exist beyond the two score-transfer route types; current structural name landing uses some of these separately.

`construction-audit.json` contains the first inventory and numeric witnesses. Its initial ID equality check mistakenly queried absent `chunkId` instead of live `chunk_id`; `live-id-verification.json` explicitly corrects that diagnostic error with the verified equality. No drift conclusion is drawn from the bad query.

## Next structural question

The result supports examining retained query evidence, not more coefficient tuning. A distinct next comparison is actual independent recruitment and merge order, with explicit candidate provenance and duplicate controls. Multi-edge aggregation, broader paths and scope discovery remain open in the ledger above. The retry-five numeric capture repair is still separate and outstanding.

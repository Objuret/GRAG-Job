# Live retrieval construction matrix

For Claude Code, Cursor and terminal use, see
[RETRIEVAL-HARNESS.md](RETRIEVAL-HARNESS.md): launch commands, independent named
experiments, checkpoint/resume, result reports and continuation specifications.

## Completed results

The live leaderboard now combines the construction matrix and coefficient grid:
**11,764 distinct policy/weight settings on the same 95 cases**, with three
duplicate defaults removed. It sorts by source-ID recall, precision or per-query
F1, includes an all/topic-present/topic-largest coefficient filter, and loads
both the policy and its recorded weights. Equal-scoring settings stay separate.
The grid is 10,240 constructions plus 509 weights on three constructions, not
the full cross-product of every construction and every coefficient setting.

- Highest fixed recall: **50.99712%**, coefficients `[0, 1.5, 0, 0, 0.5]`.
- Highest fixed recall with topic a largest coefficient: **50.95510%**,
  coefficients `[0.75, 0.75, 0, 0, 0.5]`.
- Highest fixed precision: **13.88321%**; highest fixed F1: **19.36960%**.
  These are separately selected settings.
- Per-question best observed recall over the combined settings: **74.04507%**.
  The UI can load the reference-selected setting for the selected question.
  This diagnostic uses gold outcomes to select settings; it is neither a
  deployable selector nor a proven optimum. Retrieval itself stays gold-blind.

Independent numerical review verified every per-query choice and the leading
rows for all 27 metric/subset/cohort combinations. Eleven focused tests pass,
including six live replays of selected cells and coefficient/cache isolation.
No new model calls, generated answers, or DB writes were needed.

The subsequent coefficient experiment also completed: 152,475 deliveries, 509
coefficient ratios across three structures, and 26 fixed-weight query controls.
Within topic-largest settings the recall structure reaches 50.96% observed
recall, or 49.94% with coefficients chosen on other product groups. Unrestricted
weights reach 51.00% observed but only 47.41% under grouped selection. This is
not evidence for removing topic. See `2026-09-22-facet-weight-protocol.md` and
`output/research/2026-09-22-retrieval-matrix/weights/RESULTS.md`.

The live view now allows five nonnegative coefficient overrides for
`separate_facet_sum`, with independent pinned comparison coefficients. The
combined leaderboard carries each setting's coefficients. Load setting
restores current coefficients; reset restores both sides. Six real-cache/API tests
and six numerical-channel tests pass. Browser checks confirmed editing, pinning,
resetting, leaderboard defaults and disabled controls in unsupported modes.

All 972,800 retrievals completed successfully across 95 saved queries and 10,240
configurations. Frozen source hashes stayed unchanged. The following table is
the construction-only matrix at original coefficients, before the combined view:

| Construction | Source-ID recall | Precision | Per-query F1 |
|---|---:|---:|---:|
| Canonical | 29.56% | 9.22% | 12.84% |
| Area-first only | 40.21% | 12.70% | 17.60% |
| Highest fixed recall | 49.41% | 11.76% | 17.32% |
| Highest fixed precision / F1 | 44.17% | 13.45% | 18.76% |
| Best observed per query, selected by recall | 73.96% | 19.65% | 28.71% |

The highest-recall fixed policy is configuration 3664: maximum tag/description
matching, both graph topologies, direct/graph intersection, separate per-facet
maxima summed, whole-description multiplication, area-first delivery, recovery
off. It improves recall on 60 cases, loses on 14 and ties on 21 versus canonical.
The highest precision/F1 policy is configuration 2628: maximum matching, no
graph transfer, separate per-facet maxima summed, description multiplication,
area-first delivery, recovery on. These are usable replay policies, not automatic
production replacements.

Choosing a configuration on other product-prefix groups and applying it to the
excluded group yields 48.99% recall across 30 folds. This is retrospective
selection stability, not independent final validation. Per-query best observed
uses gold outcomes to choose and is not an implemented query-time selector.
The five original interpretation failures remain outside these 95-case means;
counting them as zero makes the fixed recall leader 46.94% over the original 100.

Within the recall leader, changing only to topic-only gives 47.49% recall;
removing whole-description multiplication gives 40.71%; changing area-first to
equal-depth gives 33.41%. These are conditional comparisons around a selected
winner. They identify concrete effects in this construction, not universal
importance weights. Coefficients were held fixed in this matrix.

Full results and selection details:
`output/research/2026-09-22-retrieval-matrix/analysis/RESULTS.md` and
`analysis/results.json`. These are source-ID retrieval metrics, independently
checked against installed RAGAS ID metrics; no new answer generation or LLM
judging was run for this matrix.

The user explicitly requested systematic free retrieval experiments and a live
view of how changing the construction moves chunks linked to gold sources. This
supersedes the earlier decision to stop at narrow interventions. Avoiding adaptive
claims is not a reason to avoid measuring alternative constructions.

## Usable live view

Run `python tools/facet_retrieval_lab_ranked.py --port 8770`, then open
`http://127.0.0.1:8770/`. The local server binds to loopback only. It does not call
an interpreter, generator or judge. Query text, reference answers and source text
are not exposed by the API. Existing numeric query inputs and source-ID pointers
are used. Initial cache construction reuses ten complete cached matrices and
reconstructs 85 with the pinned local embedder; all 95 saved vector hashes match.
Five original interpretation failures remain failures, making 95/100 available.

Controls change tag/description matching, graph topology and joins, facet
combination, whole-description use, scope admission and record recovery.
Comparisons show semantic nomination position separately from final delivery
position. Source-ID credit follows the existing 72,000-character serialized
prefix contract: the partial boundary text is delivered but adds no credited IDs.
The canonical score and complete delivery ordering are checked against current
reference operators before case evaluation. Existing archived delivery may differ
because it predates the sponsor-first recovery repair.

The leaderboard ranks the same completed cases by macro source-ID recall,
precision or per-query F1. Undefined precision for an empty retrieval is excluded
from its mean; F1 for that case is zero. Partial case counts remain visible.
Equivalent rows are collapsed only when their complete chunk orders match across
all completed cases, not merely because metrics happen to match. A row can load
its whole policy into live replay. No automatic production promotion occurs.

The separate **per-query best observed** display selects one whole configuration
per query by the requested metric, then reports that selection's coherent metrics.
It uses reference outcomes to choose and is not a deployable selection method or
a theoretical upper bound. The best single construction uses one policy for all
queries. This distinction makes the available potential visible without claiming
that retrieval already knows which policy will win on a new query.

## Declared experimental coverage

The primary factorial block contains 6,400 configurations:

- Five tag/description joins: product, minimum, maximum, tag-only, description-only.
- Four topology choices: no transfer, adjacency, joint product/channel groups, both.
- Three direct/graph joins where topology exists: maximum/union, minimum/intersection,
  graph-only. No-topology has only the meaningful direct/union condition.
- Four facet combinations: topic-only; sum on each path before maximum;
  separate per-facet maxima then sum; separate facet recruitment streams.
- Four whole-description policies: multiply scores, off, independent union of
  ordinal ranks, independent intersection using the worse ordinal rank.
- Four area schedules: global, equal-depth global/area, area-first, area-only.
- Record recovery on/off.

The ordering block contains all 120 permutations of the five facets, crossed
with the four description policies, four scopes and recovery on/off: 3,840
configurations. This block fixes tag matching to product and graph topology/join
to both/union. It is not a full crossing of lexical orders with every path policy.

Total: **10,240 declared configurations per query**, 972,800 retrievals for all
95 successful saved cases. All five facet columns and query readings stay fixed,
as do the population CDF, coefficients 1/.25/.25/.25/.25 and hop discount .5.
The space covers the stated compositional alternatives, not every possible
formula, new embedding, multi-hop algorithm, learned weighting or query parser.
In independent facet streams, positive constant facet coefficients do not alter
within-stream ranks; the policy changes which streams get admission rights.

Area membership is saved and held fixed. An unresolved area falls back globally;
area-only excludes outside chunks even after recovery. A known empty mask admits
nothing. Graph-only and intersection do not invent direct fallback when a target
has no graph support. Zero-support chunks enter only through enabled recovery.

## Measurement and verification

`tools/facet_retrieval_matrix_batch.py` freezes the full configuration list and
source hashes before running. Three CPU workers evaluate complete cases. Each
case writes an immutable numeric result matrix, full-order equivalence classes,
source/input hashes and current-helper parity results. Gold enters only after
the construction has produced the final order and delivery cut.

Artifacts: `output/research/2026-09-22-retrieval-matrix/inputs/` and `batch/`.
`batch/status.json` is live progress; `batch/completed.json` is terminal evidence.
Do not infer completion from a browser count of cached inputs. The complete raw
metric matrix is retained even when the UI displays only leading configurations.

Initial validation: 10 numerical-engine tests and 146 scheduling tests pass,
including current primitive parity, ties, zeros, self-exclusion, all 120 lexical
orders, sponsor-first recovery and exact global/area scheduling. A complete
10,240-policy execution on the first cached case passed without joining gold.
The browser was checked by changing scope and loading a leading policy, confirming
that metric cards and chunk positions update through real backend retrieval.

Independent verification subsequently passed 60 checks (ten cases times six
policies specified before outcomes), including 120 calls to installed RAGAS ID
metric classes. Four checks use the actual shared resolver and budget function,
mechanically confirming complete texts, boundary prefixes, source IDs and exact
character accounting without exporting any text. All frozen hashes remain
unchanged. Report: `verification/metric_delivery.json` under the matrix output.

These are exploratory results on reused cases. Large changes are still useful
diagnostic evidence. Subsequent conclusions should report which operators cause
the changes, interaction effects, losses and per-query variation; a high maximum
alone does not establish general validity of the facet measurements.

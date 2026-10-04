# Real gold smoke of the fixed tag-frontier rule

**Completed with one metric error.** The repaired run saved ten fresh answers;
all 140 metric cells are accounted for (139 successful, one faithfulness error).
Source-ID recall is 0.562171; answer correctness is 0.181971. All ten actual
numeric rankings and source deliveries match the selected experiment.
See [all metrics and prior-run comparison](2026-09-24-real-gold-smoke-results.md).
The preparation and first-attempt notes below are retained as history.

Current run after explicit user authorization to fix and rerun:
`output/k=chars/artefact_facet_program_v2__10smoke__cb72000__20260924T001226294548Z`.
The only arm change is converting the returned scope metadata set into a sorted
JSON list. The no-model harness serialization test passed with unchanged full
ranking and 72k delivery. The run generates its own answers and evaluates all
14 standard metrics; no recovered answers are inserted. Existing valid query
interpretation caches are used by the unchanged interpreter. Other structural
experiments remain stopped.

The first attempt below failed while serializing scope metadata, saved zero
answers and never started judging. Its original code, inputs and failure remain
preserved. Its model usage was not recorded by the crashed harness and must not
be represented as zero.

The user explicitly requested a real gold smoke on a strong, logically coherent
candidate during the structural investigation. The candidate is
`tag_frontier_best-macro-recall_query_only_queries_all`: 2,008 source hits and
52.699076% macro source recall over the original 95 development queries.
It is fixed for every question. Its JSON is preserved at
`output/research/2026-09-24-real-gold-smoke/selected-program.json`.

The rule applies query-relative graph-tag tiers as evidence before reducing
edges into chunks, retains all positive tag supporters with reciprocal tier
weighting, then uses the existing two-step joint graph/description construction.
This smoke uses the shared-membership graph route. A later management-route
integration reached 2,015 hits through a seven-hit change on one case; that is
preserved separately and does not change this already chosen smoke candidate.

The experimental adapter is `test/arms/artefact_facet_program.py`. It uses the
existing raw-query interpreter and pinned query embedder, passes only graph
values and numeric query readings into ranking, and resolves source text after
the full order is fixed. It uses the existing 72,000 serialized-character cut,
including an uncredited partial boundary context. Gold is available only to
evaluation. This is an API boundary, not operating-system process isolation.

`tools/facet_program_runner.py` registers the experimental arm only in its own
process and invokes the unchanged real harness. `tools/facet_program_gold_smoke.py`
freezes dependencies and runs the established `10smoke` procedure: new answers
with the configured `claude-sonnet-5` generator, followed by all 14 standard
RAGAS metrics with the configured `claude-haiku-4-5` judge. Valid query caches
may be reused and are recorded. No generated answer or judge result is reused.

Before model calls, check exact captured-input full-order parity and actual
source-resolved delivery. Also compare the current raw-query scope resolver with
the saved smoke input masks; saved-mask numeric parity alone does not establish
raw-query scope parity. All text-bearing logs and records remain private to the
mechanical runner; the agent inspects only aggregate statistics and opaque IDs.

Preflight passed: all 95 captured numeric full orders match; all ten smoke raw
inputs, scope masks, successful interpreter cache signatures, parsed outputs,
facet weights and saved-input orders match. One actual source-resolved delivery
also matched the saved 72k boundary. Fresh embedding output is checked after the
real run rather than assumed from this preflight.

The real run started in
`output/k=chars/artefact_facet_program__10smoke__cb72000__20260923T235256246922Z`.
The wrapper owns generation followed by judging; do not launch either phase
again. All declared inputs are sealed in that folder's `smoke_plan.json`.
No answer-quality result is claimed while this run is pending.
This reused ten-question smoke is neither held-out validation nor completion of
the broader structural investigation. Preserve all errors and report every
standard metric, including unavailable or failed cells.

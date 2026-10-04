# Critical diagnosis after the remaining-90 run

Update: the bounded structural landing repair is now implemented and checked;
see [repair record](2026-09-22-structural-landing-repair.md). The build mismatch
described below applies to the measured pre-repair arm. Equal-depth scheduling
and facet semantics remain open; no new benchmark was run after the repair.

The current arm is runnable, but the small aggregate facet gain is not an adequate
answer to the user's request. Further coefficient comparisons are stopped. The
next implementation work is the missing structural landing path, with its actual
effect on selection made explicit before another benchmark/model run.

## Concrete build mismatch

`querytagger.GENERATE_SYSTEM` excludes person, organisation, product, place and
channel names from semantic tags because they are "matched elsewhere". The current
`artefact_facet_joint` supplies only `_literal_area`: exactly one literal Product
name, or no area. It never calls the existing structural landing path. Its frozen
snapshot provides chunk Kind/Product/Channel membership, but no person-name
landing data. Description embeddings may retain name information incidentally;
this is not the explicit structural route the prompt assumes.

The recorded agreement at CLAUDE.md lines 114-116 accepts names landing on actual
structure nodes, traversal to their areas, and combining areas of distinct
landings. Literal name matching itself is therefore not the violation. The
incomplete path and omitted combinations are. The earlier review's description
of literal matching as inherently contrary to scope was too broad.

`test/artefact/landing.py` already contains relevant machinery, but is not a safe
blind import: nearest-unique misspelling selection lacks an abstention distance;
cache identity does not pin the frozen graph population; empty combined areas
conflict with the current nomination API's rejection of explicit empty areas.

The current scheduler also gives the global and single-product lists equal
nomination depth. Thus an early global candidate can be served beside an early
area candidate regardless of the difference in their underlying score ranks.
This is an agent-chosen scheduling convention, not a consequence of the facet
definitions or of the graph. It requires a justification that the small facet
comparisons did not provide.

## What the saved traces establish

All numbers below use the same 85 successful interpretations from the remaining
90 benchmark IDs. Five GENERATE responses lacked a JSON object and were not
retried. Diagnostic analysis never exported benchmark language or corpus text.

The completed fixed comparison gives successful-pair ID recall 29.148% with the
auxiliaries versus 27.274% without: +1.874 percentage points. Precision is 8.748%
versus 8.252%: +0.496 points. Recall improves on 23 questions, worsens on 12 and
ties on 50. With all five missing retrievals counted as zero, recall is 27.529%
versus 25.759%. These are actual installed RAGAS deterministic ID metrics, with
exact original recruitment and text-delivery parity on all 85 saved cases.

An exploratory decomposition of the saved orders uses the same 72,000 serialized
character accounting and source-ID credit rules at each stage:

| Saved-score assembly | Mean source-ID recall |
| --- | ---: |
| Topic-only score ordering | 9.279% |
| Joint facet score ordering | 10.383% |
| Joint ordering with current structural nomination | 29.610% |
| Structural nomination plus record recovery (actual delivery) | 29.148% |

The last stage reproduces the actual saved ID sets and budget records for all 85.
This is a controlled assembly diagnosis using fixed scores, not another fresh
retrieval or independent confirmation. Scope nomination changes recall by 19.227
points relative to score order alone. Recovery changes it by -0.462 points under
the current scope convention. These conditional effects do not make all graph
mechanisms interchangeable or establish the right replacement scheduler.

Across complete delivered units, 3,447,105 characters come from the benchmark ID's
product and 2,448,787 from other products: 41.5% of complete-unit characters are
outside that product. All 3,257 gold question/source links have a mapping within
the benchmark product. This is diagnostic metadata, never a retrieval input.
Other-product content is not automatically irrelevant, and this observation
does not authorize hard product filtering.

Auxiliary contributions are not trivially tiny: their median summed contribution
is 0.662 times topic among fully delivered chunks. Mean Pearson correlation of
joint and topic-only scores is 0.977 across whole candidate populations. This
describes magnitudes, not equal rankings: at the actual character budget, the
mean Jaccard of the two score-only complete-chunk sets is 0.628. The facets do
change selections; those changes produce modest additional source-ID coverage.
About half of auxiliary winners reuse the topic winner's path. These observations
do not prove semantic redundancy or validity.

Recovery-promoted full units occupy 279,459 characters, 4.6% of total delivered
characters. A real boundary defect exists: chunk-ID ordering inside a nomination
depth can leave a higher-scored member out while admitting a lower-scored one.
This happens on 18 questions, but the detected omitted members expose only one
otherwise uncredited gold link. It is not a supported explanation of most misses.

Earlier same-number-of-chunks statistics (only three score-top-K gold links lost
at delivery) are retained as rank diagnostics only. They do not control character
cost and must not be used to claim delivery is innocent or score order is the
sole cause. Likewise, median best source score rank 346 and earliest delivery
position 40 are different orders with independently minimized source mappings.

A separate gold-aware greedy packing witness covers a mean 98.627% of citation
IDs within the same serialized-unit budget, fully covering 77 of 85 questions.
Shared ID coverage is counted once. This uses forbidden-at-retrieval gold
knowledge and ignores normal routing/recovery: it is neither an optimal bound,
a realistic target nor proof of answer-bearing text. It establishes only that
the available budget can physically hold far more cited-source IDs in this
representation; low recall cannot be explained solely as insufficient space.

## Contained next repair

1. Capture actual structural name pointers and graph memberships against the
   same eligible Volmax population, with graph-version identity and no gold input.
2. Connect structural landing, traversal and combination to the existing content
   paths. Explicitly preserve no landing, ambiguous landing and empty intersection.
3. Audit nomination as a relevance decision: global access must remain available,
   but equal global/local rank is not automatically equal evidential support.
   Do not replace it with a hard product gate or an arbitrary new quota.
4. Verify the repaired path with deterministic graph cases and inspect how each
   decision can affect delivery before any further benchmark/model run. Keep
   facet coefficients unchanged during this fidelity repair.

This remains within the user's combined tag/description/graph retrieval scope.
It is not a new quest for perfect gold, and no individual source becomes a rescue
target. The restrictive activity gloss and validity of numeric facet readings
remain separate unresolved semantic issues; a scope repair cannot validate them.

## Evidence and operational repair

Run folder:
`output/k=chars/artefact_facet_joint__gold90__cb72000__20260922T090621382244Z`.
Paired metrics: `paired_id_analysis/results.json`.
Diagnosis: `bottleneck_diagnosis/results.json`, `stage_budget.json`,
`product_allocation.json`, `query_numeric_distribution.json`.
Tools: `facet_gold90_analysis.py`, `facet_gold90_bottlenecks.py`,
`facet_gold90_stage_budget.py` under `tools/`.

The final bookkeeping MemoryError has been repaired separately with streaming
JSONL iteration in `_done_ids` and `_n_exhausted`. Six focused regression tests
and thirteen existing telemetry tests pass. Both repaired functions processed
the original 1.44 GB trace, yielding 85 completed IDs and zero exhausted candidate
pools, without the bulk-read failure. Original harness files are retained under
`output/research/2026-09-22-gold90-harness-fix/original/`; the frozen retrieval
outputs and completed replay remain unmodified. This repair is not evidence of
retrieval quality and does not fix unrelated bulk-loading evaluator/resume paths.

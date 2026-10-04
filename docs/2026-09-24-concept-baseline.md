> **WITHDRAWN as an implementation of the intended artefact.** The user rejected the unsupported construction. Its code and run evidence remain historical evidence only. See [disposition](2026-09-24-agent-work-disposition.md). The exact pre-withdrawal document is preserved in `output/research/2026-09-24-concept-baseline/original-contract.md`; original run hashes refer to that version.

# Build the recovered concept before comparing variants

The user stopped the interpreter factorial and requested an implementation of the original idea first. That comparison is cancelled; its prepared files remain evidence, not an active run. No SCORE calls were made for it. Its control script stopped because the system Python lacked NumPy; the repository `.venv` provides the required runtime.

## Implemented flow

`test/arms/artefact_concept_baseline.py` is an isolated harness arm. It reuses the frozen artefact and shared source resolver, not either previously selected ranking program.

1. One interpretation call sees the original question throughout and produces a sought-content description, whole semantic tags and five relational readings per tag. It cannot see corpus text, inventories or gold. The prompt's relational clarification is explicit code, not an assertion that the exact wording was historically approved.
2. Structural names use the existing literal/nearest-unique matcher over names already bound to captured graph nodes. Actual captured node-route memberships define areas before numeric ranking. Matching provenance survives. Nearest-unique has no calibrated distance threshold; its existing capitalization/window heuristic remains a limitation.
3. Match query tags to graph tags and follow every eligible HAS_TAG edge. Keep raw topic cosine as the edge base. The four auxiliary ranks modulate that base in the query context. Preserve every edge contribution; do not select one winning tag/path or average queries before graph processing.
4. Description similarities strengthen direct evidence rather than making zero similarity a veto. Graph-area evidence derives from other chunks' support in each actual captured area, with self support excluded. Keep direct, area and graph evidence separately for each query tag until final aggregation.
5. Named areas are prioritized with outside candidates retained. Multiple named areas are an inclusive corroborating union, not an inferred hard Boolean filter. This is the baseline's stated answer to the still-open combination policy; it does not claim to understand AND/OR language.
6. Rank the combined evidence, without a later record-recovery rewrite. Resolve original source pointers and apply the existing serialized-character budget. The standard generator receives the original question and these resolved contexts.

## Necessary choices that history did not settle

The implementation makes these choices visible in `concept_baseline.POLICY`; they are not fitted to gold:

- Auxiliary adjustment is `topic * (1 + mean(query_auxiliary * graph_auxiliary_rank))`. Its multiplier is bounded from one to two. Equal auxiliary contributions and that bound are provisional, not derived relevance units. The raw topic value is retained in the trace.
- Query topic relevance scales matched edge strength. A zero score never removes a positively matched tag candidate from eligibility.
- All distinct matched edges contribute by addition. This preserves corroboration but does not claim statistically independent evidence; tagging density can affect the total.
- Each positive description cosine strengthens its corresponding direct evidence by `1 + cosine`. Description support can also admit a graph-supported chunk; it cannot remove a direct candidate.
- Graph support is the mean support from other chunks in an area, then the mean across areas containing the target. Identical membership sets are counted once. Area provenance retains the multiple original nodes/routes. This is a structural corroboration rule, not a fixed-hop graph walk or proof of query-relative facet clustering.
- Query-tag contributions are averaged only after direct and graph paths have been recorded. Exact duplicate numeric query rows count once. Distinct needs are not automatically treated as mandatory clauses.
- Named union precedes outside evidence; ties use stable chunk IDs. The final budget may still prevent outside evidence from being delivered.

## Integrity and limitations

The numeric core accepts only `ConceptGraph`, with immutable opaque IDs, endpoints, measurements and area memberships. It has no source locator, text, resolver or gold fields. The outer adapter handles name grounding and source resolution at the appropriate stages. This is an API boundary, not process isolation.

The existing learned auxiliary layer and its semantic uncertainties remain. No query prompt correction can retrospectively validate that layer. The existing 4,808-chunk eligibility and captured structural route coverage also remain; no new graph data is injected. These constrain what this first runnable baseline can demonstrate and are not presented as the complete intended corpus/graph design.

## Verification and remaining completion work

`tools/concept_baseline_verify.py` checks the actual ten saved query captures without models or gold: raw topic retention; complete edge accumulation; preservation of tag candidates; graph support never lowering direct support; duplicate-query invariance; area/outside ordering; rejection of rich source-bearing inputs; and actual pointer resolution/budget delivery. This is a dataflow check, not a fresh interpretation or quality result.

Remaining: independently check whether the chosen dataflow and explicit open choices fit the recovered decisions; exercise the new combined interpreter and full harness path; inspect the resulting trace; only then evaluate the fixed baseline. Do not mark the original-idea goal complete from numeric checks alone.

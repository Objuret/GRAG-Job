# Independent review of HERB gold-source pointers

2026-09-22. Scope: `tools/facet_gold_trace.py`, its HTML template, the shared resolver and recruitment/witness schemas, and the generated `verification.json` only. No benchmark question/answer/context text or raw corpus was inspected. No retrieval, embedding, model or DB calls were made. This review does not assess relevance or require perfect gold recall.

## Finding

The tool addresses the user's requested pointer tracing directly. It mechanically maps HERB citation IDs to eligible frozen graph chunks, static semantic tag edges, and existing retrieval stages. It does not substitute homemade questions or launch a new experiment. The source-to-chunk mapping and full/partial delivery distinction match the current shared resolver and harness contract.

Two bounded review items were sent to the implementing agent before delivery:

1. Validate the saved run's **arrays.npz** hash and resolver source hash against the current mapping inputs, in addition to graph.json. The first reviewed version checked only graph.json. Without the extra compatibility checks, a later run made with another facet overlay or resolver could be displayed against current static facets/unit lengths. Saved `meta.snapshot.snapshot_sha256` and `meta.snapshot.source_sha256` already contain the needed hashes; normalize path separators for the latter.
2. The source summary's best score rank and earliest recovered-order position are independent minima over possibly different chunks. Do not join them with an arrow that suggests one chunk followed that exact path. Label them as independent source summaries; retain actual per-chunk stages below.

These are provenance/display corrections, not requests to change retrieval or tune recall. Their final disposition is recorded in the addendum below once the implementation is rechecked.

## Mapping and stage semantics

- `build_index` reads only the chosen subset's IDs and matching citation IDs into its exported question index. It resolves every eligible snapshot chunk using AST-extracted, unchanged `_load_verified_doc`, `_nth_entry` and `_resolve_chunk` from `test/arms/artefact_v2.py`.
- The resolver checks each raw file's SHA, follows its stored locator, and returns the same source artifact IDs as serving. Ranged chunks map to their record ID; batched units can map to multiple IDs; multiple chunks can map to one ID. The reverse mapping retains this many-to-many relation instead of guessing from chunk IDs or names.
- Static tag links are selected by actual edge/chunk indices. The per-facet saved winning path retains its query-tag **index**, seed chunk, graph edge/tag, route type and numerical factors. Query-tag text is excluded.
- The trace distinguishes score order, nomination depth, recovered order and serialized budget admission. An unserved but nominated chunk is `outside_budget`; a chunk absent from the recovered order is `not_nominated`; a citation with no mapped eligible chunk is `not_in_frozen_graph`.
- `full_unit` means the entire serialized graph unit was delivered. It does not mean the entire cited source or its needed passage was delivered. The optional boundary unit is separate. ID credit equals the union from **fully** delivered units, exactly as `_budget_contexts` does; a partial unit contributes text but no new ID credit.
- Verification checks saved context counts/lengths, full-unit lengths, boundary identity/length and credited artifact-ID equality. It is an accounting verification, not an independent content-equality or relevance judgment. Context strings are processed mechanically for lengths, not exported.
- The artifact's `first_complete_unit_chars` is the cumulative cost of reaching the earliest mapped unit. It is not the cost of acquiring all evidence from that source or the cost of answering the question.

## Language boundary and presentation

The inspected export paths omit benchmark questions, reference answers, generated answers, saved contexts, query descriptions and query-tag phrases. They export citation IDs, graph/source metadata, stored graph tags, stage pointers and numerical factors. Those graph tags and metadata are corpus-derived labels, as required to make the pointers useful; “text omitted” should be understood as question/answer/source-body text, not as a claim that all labels are nonlinguistic.

Recruitment rows copied to output contain IDs, ranks, depths, stream names, recovery component IDs and trigger IDs, not hidden query language. The HTML uses `textContent` for corpus-derived labels, and escapes `<` in its JSON script payload. The graph-coverage table distinguishes questions without a saved retrieval run from traced questions. Explicit warnings correctly state that source-ID credit does not establish answer-bearing evidence coverage.

## Observed aggregate verification

The first generated verification report, whose code/template hashes matched the inspected files, reports:

| Quantity | Count |
| --- | ---: |
| Chosen gold questions | 100 |
| Distinct cited source IDs | 3,501 |
| IDs mapped to eligible graph units | 3,501 |
| Linked chunks | 802 |
| Semantic tag links | 9,281 |
| Eligible frozen graph chunks | 4,808 |
| SHA-verified raw source files | 30 |
| Saved questions traced | 10 |
| Source–question links in those traces | 508 |
| Credited source–question links | 164 |
| Outside-budget source–question links | 344 |
| Checked fully delivered units / partial units | 168 / 10 |
| Model / embedding / retrieval rerun calls | 0 / 0 / 0 |

All mapped source IDs is **mapping coverage**, not 100% retrieval recall. The 164/508 pooled link ratio is not the macro-averaged RAGAS context recall. No retrieval conclusion should substitute one denominator for the other.

## Final disposition

**PASS for the requested pointer diagnostic.** Both initial items are corrected: the code rejects a changed saved facet-array/resolver provenance, and the source summary explicitly calls its two minima independent. The regenerated verification report matches the final inspected code hash `ac312e1ad22459cf9cae19801e13c5056b557315d03e39ec8e2dd90f4f420e4f` and template hash `8b668e5ca51b97eed85e77343adc64602782f9525a02857b729ad561c9e4d3b4`. The aggregate counts above remain unchanged; index and unit-index hashes are also recorded in verification.json.

No broader experiment, perfect-recall gate or source-specific rescue is warranted by this review. This pass covers the inspected mapping, accounting, provenance and export logic plus its aggregate execution verification; rendered browser interaction is the root agent's separate check.

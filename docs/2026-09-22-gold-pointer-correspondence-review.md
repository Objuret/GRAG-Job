# Independent review: fixed facet-correspondence control

2026-09-22. Reviewed `tools/facet_gold_pointer_correspondence.py`, its declared protocol, and the actual independent-facet envelope, fixed-reference transform and final readout. The reviewer did not inspect benchmark questions, answers, saved contexts or raw corpus and made no model, embedding or retrieval calls. Only the aggregate comparison summary is eligible for outcome inspection in this review.

**The declared control and implementation are appropriate for a bounded correspondence diagnostic.** It addresses a different claim from auxiliary-off: whether the intended pairing of query and graph facet columns performs better than one fixed mismatched pairing on these same saved queries. It cannot validate every facet's meaning or estimate a permutation null distribution.

## Mathematical check

The final score is `Q * sum_f beta[f] * Z[f]`, where each `Z[f]` is computed independently from that facet's query readings and fixed-reference graph readings, with the same tag/description/graph routes. The rotation `P=[0,2,3,4,1]` retains topic in position zero.

- **Query-only treatment:** query column `f` receives old column `P[f]`, while graph readings and their reference remain in their original columns. This breaks intended auxiliary correspondence. It does not zero the auxiliaries, alter their coefficients, remove tag routes, or change the query description.
- **Joint symmetry control:** query columns, graph-facet columns and their fixed-reference columns all receive the same rotation. Rotating the reference with the graph readings is essential: the transformed ranks are then exactly the original ranks under the same relabeling. Each independent auxiliary envelope consequently becomes `Z[P[f]]`.
- Topic is fixed and all four auxiliary coefficients equal `.25`. Their sum is invariant to this relabeling. The joint condition should therefore recover the same combined scores apart from floating-point summation order. The code requires exact per-facet profile permutation, scores within `1e-12`, and exact recruitment/delivery equality. This would not be an invariant control if auxiliary coefficients differed without also being permuted.

The baseline uses original inputs. The tool requires its complete score order to match the saved order, not merely a similar top list. Failure of baseline or symmetry prevents completion of `numerical_outputs.json`, which the separate join phase requires; the declared tolerance is not adjusted after outcomes.

## Surrounding pipeline and provenance

The tool reconstructs cosines with the actual arm's pinned local CPU embedder in offline mode. Every reconstructed normalized vector bundle must have the exact saved embedding hash. It reuses saved interpretation fields; no fresh Claude interpretation or answer generation occurs. Numeric matrices are saved privately to avoid repeated reconstruction.

Prepared graph/source-code hashes must match saved provenance. A frozen plan covers the experiment code, protocol, saved run, graph arrays/vectors, unit index and imported retrieval dependencies. Inputs are rechecked after the numerical phase and before joining. A started marker and exclusive output writes prevent a silent restart/overwrite.

All three conditions reuse saved area membership/provenance, actual graph adjacency and record recovery. They recompute nomination and recovery from each condition's scores, then use the actual shared resolver and **72,000 serialized-character** budget. Baseline and joint control both require exact saved context strings, source IDs and budget metadata. Thus the comparison does not confuse saved-source research lengths with serving delivery, and does not hold an obsolete selected set fixed after changing the score.

The numerical phase does not load the gold source index or use cited-source IDs for ranking, scope or recovery. Gold joining is a separate command after all 30 numerical outputs are saved and hashed. The join checks those hashes, then measures source-ID credit. Saved query/source language is processed only internally; exported witnesses omit query-tag text and retain graph labels, IDs and numeric factors.

## Claims the outcome can support

This is ten already observed smoke queries with fixed interpretations, not new independent validation and not ten new stochastic query interpretations. It produces no new generated answers, Claude judgments or RAGAS answer-quality measurements.

An intended-pairing advantage would be conditional evidence for that pairing against this one control under source-ID credit. A tie or mismatch advantage would mean the earlier auxiliary-on/off gain does not establish useful named correspondence here. Neither result alone establishes semantic correctness/incorrectness of each facet, a general permutation distribution, calibrated coefficient values or answer-bearing content coverage. Source–question links and multiple chunks from a source are not independent trials. A higher net recall can coexist with individual source losses.

The mismatched condition is a diagnostic, not a proposed replacement policy. No further experiment or source-specific repair is recommended by this review.

## Execution outcome

**Completed; review passes within the stated scope.** The aggregate comparison reports all ten baseline and all ten joint-symmetry controls passing. The inspected implementation/protocol hashes remain unchanged from review.

| Outcome | Result |
| --- | ---: |
| Macro source-ID recall, intended correspondence | 0.33053887697655054 |
| Macro source-ID recall, query-only mismatch | 0.3123212282686233 |
| Intended minus mismatch | +0.01821764870792724 |
| Source–question links credited only by intended pairing | 19 |
| Source–question links credited only by mismatch | 14 |
| Questions with better intended / better mismatch / tied net recall | 2 / 1 / 7 |
| Language-model calls / new answers | 0 / 0 |
| Local embedding reconstructions with required saved hash parity | 10 |

The intended pairing has a small positive aggregate source-ID effect relative to this fixed mismatch, **with mixed outcomes**: one question favors mismatch and fourteen links are credited only by mismatch. This is limited functional evidence for intended correspondence under the present readout and these saved inputs. It is stronger than showing the auxiliary block changes scores, but it does not validate all named facets, their magnitudes, the selected coefficients or unseen-query generalization. The seven net-recall ties do not establish identical contexts or source sets.

Together with the separate auxiliary-off comparison, the supported statement is that the auxiliary block and its intended correspondence each have a modest positive aggregate source-ID effect against their respective fixed controls in this already observed smoke. The comparisons remain distinct; they are not independent replications and do not form a significance test. No new RAGAS answer score was produced, and no further condition, tuning or rescue follows from this review.

Reviewed implementation SHA-256: `c6fe9f40a853f8708c142362a5401662fe47207dddd30a58e429c5b66cf8becb`. Protocol SHA-256: `b78ead30c64c6080e5c4515113dc208a149a0410c0c0a53b26a1d2e5f707e8b5`.

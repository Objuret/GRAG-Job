# Fixed-program real gold smoke results

The serialization-only repair completed the standard ten-question, 72,000-character smoke with ten newly generated answers. All 14 metrics were attempted: 139 successful cells, one faithfulness error, zero missing cells. No recovered answers were inserted.

The same ten development questions were used in the earlier comparisons; this is not held-out validation. The generator and judge models match the prior runs. Answer and judge variability remain part of the comparison.

| Metric | Earlier joint arm | Earlier area arm | Selected fixed rule | New successful / errors |
| --- | ---: | ---: | ---: | ---: |
| context_precision_id | 0.131969 | 0.165209 | 0.195101 | 10 / 0 |
| context_recall_id | 0.330539 | 0.393175 | 0.562171 | 10 / 0 |
| context_precision_nonllm | 0.180254 | 0.222218 | 0.007143 | 10 / 0 |
| context_recall_nonllm | 0.050634 | 0.059358 | 0.003846 | 10 / 0 |
| semantic_similarity | 0.326964 | 0.328085 | 0.338636 | 10 / 0 |
| string_similarity | 0.123482 | 0.114199 | 0.106366 | 10 / 0 |
| bleu | 0.054862 | 0.066589 | 0.071190 | 10 / 0 |
| rouge | 0.130936 | 0.116549 | 0.095705 | 10 / 0 |
| chrf | 0.268310 | 0.252043 | 0.225883 | 10 / 0 |
| exact_match | 0.000000 | 0.000000 | 0.000000 | 10 / 0 |
| string_presence | 0.000000 | 0.000000 | 0.000000 | 10 / 0 |
| faithfulness | 0.876090 | 0.830564 | 0.826906 | 9 / 1 |
| answer_correctness | 0.221402 | 0.260430 | 0.181971 | 10 / 0 |
| context_recall_llm | 0.200000 | 0.266667 | 0.323333 | 10 / 0 |

Faithfulness means use 9 successful cases for both the new and earlier area runs, and 10 for the earlier joint run; these are not equal-success-subset comparisons. Other listed metrics have ten successful cases in each run.

Compared with the earlier area smoke, source-ID recall rose from 0.393175 to 0.562171, while answer correctness fell from 0.260430 to 0.181971. The retrieval improvement therefore does not establish an answer-quality improvement.

Integrity checks: all ten raw question inputs, fresh query embedding vector hashes, scopes, full ranking hashes, complete deliveries, partial boundaries, budgets and credited source-ID sets match the fixed selected experiment. Both interpreter cache stages were hits on all ten. All 51 sealed dependencies remained unchanged after the run. The source resolver and gold evaluation act after numeric ranking.

Execution: generation phase 161.718 seconds; judge phase 355.234 seconds; wrapper total 517.234 seconds. Ten generator calls and 59 judge calls were recorded. The earlier failed run is separate; its lost usage is unknown, not zero.

Artifacts:

- Run: `output/k=chars/artefact_facet_program_v2__10smoke__cb72000__20260924T001226294548Z`
- Exact metrics and comparison: `smoke_comparison.json` inside the run.
- Full run outcome and usage: `aggregate_report.json` inside the run.
- Numeric replay audit: `output/research/2026-09-24-real-gold-smoke/postgeneration-numeric-audit-artefact_facet_program_v2__10smoke__cb72000__20260924T001226294548Z.json`.
- Fixed rule: `output/research/2026-09-24-real-gold-smoke/selected-program.json`.

This smoke is complete with the reported metric error. The broader structural investigation remains unfinished and its other runs remain stopped.

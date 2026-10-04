# Completed area-arm smoke, 2026-09-22

Ten new area-arm answers completed with the standard Sonnet 5 generator, Haiku 4.5 judge, pinned local Nemotron embedder and 72,000-character delivery budget. Query interpretations were reused exactly; no new interpreter calls. RAGAS returned 139 successful metric cells and one faithfulness error. No missing cells; no automatic judge rerun.

All ten cases have identical query interpretations, graph inputs, complete chunk scores, resolved areas and budget against the earlier joint-arm smoke. Maximum absolute score change is zero. This supports attribution of deterministic retrieval changes to admission/recovery ordering. It does not isolate answer-generation or judge variation.

| RAGAS metric | Earlier joint | Area first | Valid new cells |
|---|---:|---:|---:|
| context_precision_id | 0.131969 | 0.165209 | 10/10 |
| context_recall_id | 0.330539 | 0.393175 | 10/10 |
| context_precision_nonllm | 0.180254 | 0.222218 | 10/10 |
| context_recall_nonllm | 0.050634 | 0.059358 | 10/10 |
| semantic_similarity | 0.326964 | 0.328085 | 10/10 |
| string_similarity | 0.123482 | 0.114199 | 10/10 |
| bleu | 0.054862 | 0.066589 | 10/10 |
| rouge | 0.130936 | 0.116549 | 10/10 |
| chrf | 0.268310 | 0.252043 | 10/10 |
| exact_match | 0.000000 | 0.000000 | 10/10 |
| string_presence | 0.000000 | 0.000000 | 10/10 |
| faithfulness | 0.876090 | 0.830564 | 9/10 |
| answer_correctness | 0.221402 | 0.260430 | 10/10 |
| context_recall_llm | 0.200000 | 0.266667 | 10/10 |

Faithfulness uses only nine successful new measurements, compared with ten old ones; these means are not a paired ten-case comparison. Answer correctness rises from 0.221402 to 0.260430; generation/judge variability remains. ID recall rises by 6.26 percentage points, precision by 3.32 points.

These ten questions are reused smoke cases, not a new holdout. The separate fixed 85-case replay measured an 11.16-point ID-recall effect; do not pool those results into a fresh generalization claim. Facet meanings and numerical coefficients remain unvalidated as retrieval utilities.

The original area attempt preserved nine answers plus one previously cached interpretation failure. Resume reused those nine answers and an existing exact-signature successful interpretation to generate only the missing answer. Source caches stayed unchanged through completion. Afterward, the known success was promoted to the normal cache; original failure bytes and promotion hashes are preserved under `output/private/facet_joint_cache/history/2026-09-22-exact-recovery/`.

Artifacts: `output/k=chars/artefact_facet_area__10smoke__cb72000__20260922T112609034165Z__cached-resume/{aggregate_report.json,smoke_comparison.json,completed.json}`. Normal runner supports `artefact_facet_area`; no additional benchmark run is queued.

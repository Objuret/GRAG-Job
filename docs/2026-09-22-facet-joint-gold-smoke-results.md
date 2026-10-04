# Joint-facet standard gold smoke: 2026-09-22

`artefact_facet_joint` completed the standard fixed `10smoke` with 10 answers and all 140 metric cells successful. The arm works end to end, but this smoke shows limited gold-evidence coverage and low answer correctness. High faithfulness alone does not establish useful answers.

## Setup

- Generator: `claude-sonnet-5`; judge: `claude-haiku-4-5`; unchanged standard RAGAS 0.4.3 evaluator and all 14 configured metrics.
- Embeddings: local CPU float32 `nvidia/llama-nemotron-embed-1b-v2`, revision `113abe4acafa848e77ead9c0623205e511932348`.
- Retrieval: frozen Volmax graph export, 4,808 chunks and 57,204 semantic edges. This is a snapshot-backed experimental arm, not a claim of live database retrieval.
- Unchanged split query prompts, joint route/description/facet scoring, coefficients `(1,.25,.25,.25,.25)`, literal Product scope and source-record recovery.
- Standard serialized-context budget: every answer received 72,000 characters and nonempty source artifact IDs. The evaluator's 60,000-character setting is a warning threshold, not a cap: `_check_judge_context_budget` logs large contexts and continues, while `_to_sample` passes the complete saved contexts to RAGAS. The earlier report incorrectly called it a cap; this sentence corrects that description without changing the run or its scores.
- Seven focused adapter tests passed before the run, including exact development-replay parity and shared budget/source-ID behavior.

## All metric means

| Metric | Mean | Successful | Errors | Missing |
|---|---:|---:|---:|---:|
| `context_precision_id` | 0.131969 | 10/10 | 0 | 0 |
| `context_recall_id` | 0.330539 | 10/10 | 0 | 0 |
| `context_precision_nonllm` | 0.180254 | 10/10 | 0 | 0 |
| `context_recall_nonllm` | 0.050634 | 10/10 | 0 | 0 |
| `semantic_similarity` | 0.326964 | 10/10 | 0 | 0 |
| `string_similarity` | 0.123482 | 10/10 | 0 | 0 |
| `bleu` | 0.054862 | 10/10 | 0 | 0 |
| `rouge` | 0.130936 | 10/10 | 0 | 0 |
| `chrf` | 0.268310 | 10/10 | 0 | 0 |
| `exact_match` | 0.000000 | 10/10 | 0 | 0 |
| `string_presence` | 0.000000 | 10/10 | 0 | 0 |
| `faithfulness` | 0.876090 | 10/10 | 0 | 0 |
| `answer_correctness` | 0.221402 | 10/10 | 0 | 0 |
| `context_recall_llm` | 0.200000 | 10/10 | 0 | 0 |

## Reliability and interpretation

The first attempt completed 9/10 answers. One GENERATE response contained no JSON, so that question never reached retrieval. A separate, explicitly recorded recovery retried only the missing case once with identical prompts and settings. The nine successful answers were copied byte-for-byte and reused; standard harness resume produced the tenth. The original failed run remains preserved. Thus first-attempt completion was 90%; completed coverage after one format retry was 100%.

No benchmark questions, gold contents, generated answers, retrieved benchmark contexts or per-question judge explanations were inspected by agents. Only the standard harness/evaluator processed them; reporting was mechanical and aggregate-only. No retrieval setting was tuned from these results.

This establishes a runnable, measurable experimental arm. It does not establish improvement over a baseline, validate facet semantics, or settle the coefficients. No matched baseline comparison was performed in this smoke.

## Run artifacts

- First attempt: `output/k=chars/artefact_facet_joint__10smoke__cb72000__20260922T071854164747Z/`.
- Completed recovery: `output/k=chars/artefact_facet_joint__10smoke__cb72000__20260922T071854164747Z__format-retry1/`.
- Standard judge results: the recovery folder name plus `__j-claude-haiku-4-5__10smoke`.
- Public aggregates: `aggregate_report.json`; frozen commands/provenance: original `smoke_plan.json` and recovery `recovery_plan.json`.
- Preparation/execution instructions: `docs/facet-joint-gold-smoke.md`.

Raw run files and private logs remain uninspected. Failed interpreter usage is recorded separately in the recovery aggregate so the successful-answer totals do not conceal that attempt.

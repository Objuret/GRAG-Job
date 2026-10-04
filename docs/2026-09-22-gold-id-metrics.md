# Exact RAGAS ID metrics for the three frozen retrieval conditions

These numbers are **`context_precision_id` and `context_recall_id`**, the repository
aliases for RAGAS `IDBasedContextPrecision` and `IDBasedContextRecall`. They are
deterministic set comparisons, not Claude judgments or generic “pairing scores.”
The installed **RAGAS 0.4.3 classes were executed locally** for all three conditions:
60 metric evaluations across ten questions, with zero language-model calls.

For each question:

```text
context_precision_id = |credited source IDs intersect gold IDs| / |credited source IDs|
context_recall_id    = |credited source IDs intersect gold IDs| / |gold IDs|
```

The reported values are the arithmetic means of those per-question scores, not
ratios pooled across all sources.

| Frozen retrieval condition | context_precision_id | context_recall_id |
| --- | ---: | ---: |
| Intended joint policy | 0.131969 | 0.330539 |
| Auxiliaries off | 0.126913 | 0.309877 |
| One auxiliary query/graph mismatch | 0.124216 | 0.312321 |

The original joint results match both ID metrics in the prior complete RAGAS smoke
to floating-point precision. Earlier control reports computed recall arithmetically;
this check now also runs the actual installed deterministic metric classes. It does
**not** rerun Claude judges, generate new answers, or supply new answer-correctness,
faithfulness or LLM context-recall scores for the controls.

## Tradeoffs hidden by the means

Against auxiliaries off, joint precision is higher on four questions, lower on five
and tied on one. Recall is higher on two and tied on eight. Thus the two improved
average metrics do not establish per-question dominance.

Against the mismatch, joint precision is higher on four, lower on one and tied on
five; recall is higher on two, lower on one and tied on seven.

The joint condition credits 164 gold and 1,088 non-gold question/source links;
auxiliaries off credits 155 gold and 1,068 non-gold links. Joint therefore retrieves
more of both in absolute source-ID counts, while its average precision is slightly
higher. The mismatch credits 159 gold and 1,131 non-gold links. All contexts use the
same 72,000 serialized-character budget. Source batching means equal text budgets
do not imply equal ID counts.

Non-gold means absent from the benchmark citation set; it does not establish that
a source is unrelated or useless. Gold artifact membership also does not prove
that the needed passage survives truncation. These metrics measure source-ID
retrieval, not exhaustive relevance, claim coverage, facet meaning or answer quality.

## Reproduction and evidence

Tool: `tools/facet_gold_id_metrics.py`.
Output: `output/research/2026-09-22-gold-source-trace/id_metrics/results.json`.
The plan fingerprints the installed metric implementations and recorded inputs.
The tool supplies only retrieved and reference IDs to `single_turn_ascore`, checks
each result against the set formula, and reconciles both baseline metric means.
The off-condition source lists are reconstructed through unchanged scope/recovery
and the actual shared delivery helper, preserving the previous recall results.

Retain the fixed candidate on this bounded evidence. Do not tune coefficients,
select a favorable metric or rescue individual sources from this comparison.

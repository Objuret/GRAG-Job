# Auxiliary facets: fixed comparison through gold-source pointers

Metric clarification: “source-ID recall” below is the repository's RAGAS
`context_recall_id`. These are retrieval ID scores, not generated-answer scores.
Both ID metrics have now been executed through installed RAGAS classes for all
three frozen conditions; see `docs/2026-09-22-gold-id-metrics.md`.

The auxiliary block improves mean source-ID recall from **0.309877 to 0.330539**
on the ten existing smoke questions: **+0.020662**, or 2.07 percentage points.
Two questions improve by net cited-source count; eight tie. The gains include
losses of other sources, so this is a measured tradeoff, not uniform retention.

| Quantity | Saved joint policy | Auxiliaries off |
| --- | ---: | ---: |
| Coefficients | 1, .25, .25, .25, .25 | 1, 0, 0, 0, 0 |
| Mean per-question source-ID recall | 0.330539 | 0.309877 |
| Credited question/source links | 164 | 155 |
| Delivered characters, each question | 72,000 | 72,000 |
| Mean delivered graph units, including partial boundary | 17.8 | 18.6 |

There are 21 links credited only with auxiliaries and 12 credited only without
them, for a net gain of nine. Both source-set changes occur in the two questions
with a positive net recall difference. The eight count ties retain the same gold
source sets; their other delivered content need not be the same.

## What moves

Across 136 distinct question/gold-linked-chunk combinations, 127 change score rank
and 121 change recovered delivery position. These are repeated graph observations,
not 136 independent questions. The pointer instrument therefore reveals much more
movement than the final recall count: many ranking changes remain on the same side
of the delivery boundary. It does not mistake every movement for useful retrieval.

Open `output/research/2026-09-22-gold-source-trace/auxiliary_off/index.html` and switch
between the saved joint run and the explicitly labeled counterfactual. The question
selection persists across conditions. Expand a source to follow the same chunk's
score rank, scope nomination, recovery and actual delivery, with its facet paths.
`comparison.json` contains all paired outcomes and source movements;
`aggregate_movement.json` contains the counts above.

## Why this is a valid controlled readout comparison

The current implementation obtains each facet's best route independently. The
coefficients are applied only after those maxima. Consequently, setting the four
auxiliary coefficients to zero leaves the topic maximum unchanged: the stored
topic contribution is exactly the required counterfactual score. This does not
hold for every possible retrieval design; it follows from this implementation's
actual separation of route selection and final combination.

The replay preserves the original query interpretation, graph, graph relations,
description factors, scope membership, record recovery and serialized budget.
Before computing comparisons it reproduces **10/10 full baseline recruitment
objects and exact delivered context strings, IDs and budget metadata**. The largest
saved score versus contribution-sum discrepancy is 2.78e-17. Original score values
are retained for baseline ordering, avoiding a change from floating-point summation.
Saved graph, facet-array, resolver and recruitment code hashes are verified.

Gold pointers are used only for downstream joins after each order and delivery
are fixed. No source-specific rule, coefficient search, prompt change, model call,
embedding call, new answer or new judge call occurred. The protocol was saved
before the comparison was calculated. The source texts used for parity stay out
of the exported report.

## What this establishes, and the remaining claim

This supplies direct evidence that the chosen auxiliary adjustment changes the
combined retrieval function and yields a modest positive source-ID effect in this
fixed smoke. It supports retaining the joint policy as a viable experimental
candidate. It does not establish optimal coefficients, independent generalization,
correct facet semantics, or improved generated answers. The auxiliary-off result
is reconstructed retrieval ID recall, not a new RAGAS answer-quality evaluation.

Source IDs can be batched into one graph chunk and cited across questions. Pooled
link counts are therefore not independent trials. Artifact credit is also coarser
than answer-bearing passage coverage. The method's declared coefficient policy
remains an explicit engineering choice; this comparison measures its consequence
rather than fitting those coefficients to gold. No individual miss becomes a new
repair target, and no demand for perfect gold follows from these results.

Independent review: `docs/2026-09-22-gold-pointer-ablation-review.md`.
Runnable tool: `tools/facet_gold_pointer_ablation.py`.

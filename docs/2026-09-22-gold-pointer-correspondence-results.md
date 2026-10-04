# Intended facet correspondence versus one fixed mismatch

Metric clarification: the recall numbers below are `context_recall_id`, not a
generic score of facet correctness. For exact definitions and locally executed
RAGAS precision/recall results for every condition, see
`docs/2026-09-22-gold-id-metrics.md`. No new Claude judge or answer-quality run occurred.

The intended query/graph facet pairing achieves **0.330539** mean source-ID recall,
versus **0.312321** when the four auxiliary query readings are rotated against the
graph facets. Topic, coefficients, scope, recovery and actual 72k delivery stay
fixed. The difference is **+0.018218**, or 1.82 percentage points.

Two questions favor the intended pairing, one favors the mismatch, and seven tie
by net cited-source count. There are 19 source-question links credited only with
the intended pairing and 14 only with the mismatch. Preserve both gains and losses;
the mismatch is a control, not a new policy chosen from its results.

Together with the prior on/off comparison:

| Fixed condition on the same ten saved query interpretations | Macro source-ID recall |
| --- | ---: |
| Intended joint policy | 0.330539 |
| One auxiliary query/graph mismatch | 0.312321 |
| Auxiliaries off | 0.309877 |

These comparisons address separate claims. On/off tests the auxiliary block's
effect. Query-only rotation tests its intended correspondence against one broken
correspondence. The small aggregate advantages favor retaining the intended policy
as the experimental candidate; they do not calibrate its coefficients or prove
that all five named measurements correctly represent their intended concepts.

## Controls and execution

- All ten query embedding reconstructions match their saved vector hashes using
  the same offline local Nemotron embedder, revision, CPU float32 recipe and prefix.
- All ten baseline runs reproduce original score order, complete recruitment,
  exact serialized context strings, credited IDs and budget metadata.
- Rotating both query and graph/reference auxiliary columns together preserves
  all ten recruitment/delivery results. This is the expected symmetry because the
  four auxiliary coefficients are equal.
- The query-only rotation is fixed at [0,2,3,4,1], with topic held unchanged.
  Each condition recomputes facet maxima; it does not merely relabel saved winning
  paths when the actual winning query tag may change.
- All 30 numerical outputs were frozen before the separate gold-pointer join.
  There were no Claude, generator or judge calls and no new answers. Ten local
  embedding reconstructions were required; their numeric matrices are now cached.

The independent review passed:
`docs/2026-09-22-gold-pointer-correspondence-review.md`.
Input fingerprints, output hashes and control receipts are in
`output/research/2026-09-22-gold-source-trace/correspondence/numerical_outputs.json`.

## Inspect and interpret

`output/research/2026-09-22-gold-source-trace/correspondence/index.html` combines the
original policy, auxiliary-off condition and this mismatch. Switch conditions to
follow the same gold-source pointers through score rank, scope nomination, record
recovery and delivery. Source-level minima remain distinct from per-chunk paths.

This is evidence on ten already observed smoke questions across six product-ID
groups (4,2,1,1,1,1 questions). It is not ten independent product-level replications,
an untouched validation set, a distribution of random permutations, a significance
test, or new RAGAS answer-quality results. Source-ID credit remains coarser than
answer-bearing passage coverage. One control cannot establish every facet's
semantics or rule out other explanations for its benefit.

The runnable policy and pointer measurement now have positive but bounded evidence
for both auxiliary contribution and intended correspondence. Retain the declared
weights; do not turn these outcomes into a weight sweep or source-specific rescue.

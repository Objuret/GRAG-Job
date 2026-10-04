# Facet coefficient and query-binding replay

The completed composition matrix changed routing and scheduling while keeping
facet coefficients fixed. This experiment targets that remaining assumption.
It uses the same 95 numeric query inputs, graph snapshot, saved areas, CDF and
72,000-character delivery contract. There are no new model calls or DB writes.

## Predictions fixed before execution

1. If coefficient attenuation limits useful facets, changing their relative
   coefficients should improve delivery, including when coefficients are chosen
   on other product-prefix groups. Report losses and precision/F1 as well as recall.
2. If named auxiliary query dimensions carry useful information, collapsing
   them to each tag's auxiliary mean or permuting their labels should hurt.
3. If the assignment of auxiliary vectors to query tags matters, moving the
   entire vectors between tags should hurt. This is distinct from label binding.

Failure of these controls to hurt is evidence about this retrieval construction,
not proof that the facet concepts are meaningless. Static edge validity and
record-kind confounding require a separate controlled edge intervention.

## Frozen conditions

Three structures: canonical, completed-matrix recall winner 3664, and precision/F1
winner 2628. All use separate facet maxima followed by a sum. The five winning
channels are therefore reusable for coefficient changes; no path rescore is needed.

The coefficient grid contains all five-component nonnegative integer vectors
summing to eight, interpreted up to positive common scale. It includes the actual
current ratio 4:1:1:1:1. Add all sixteen current-coefficient auxiliary subsets,
then remove proportional duplicates: 509 settings. This is an eighth-simplex
resolution, chosen to include the current coefficients exactly; it is not a claim
that eighths are semantically calibrated. Topic-zero and weights exceeding topic
are diagnostic alternatives, reported separately from topic-dominant settings.

At the original coefficients, run 26 auxiliary-query controls: all 23 nonidentity
permutations of the four facet labels; replace auxiliaries by their row mean;
rotate complete auxiliary rows by one; reverse auxiliary rows. Topic remains
unchanged in every control. Record changed-cell counts to distinguish no-ops.
These deterministic interventions are sensitivity tests, not exchangeability-based
significance tests. They do not replace a replicated shuffle experiment.

Total: 152,475 deliveries. Ordering receives no gold, lengths or source IDs.
Gold joins after the existing delivery cut. Each case verifies exact original
coefficient order parity for all three structures. Inputs, implementation hashes,
case metrics and controls are retained in `output/research/2026-09-22-retrieval-matrix/weights/`.

## Analysis

For each structure, report best observed coefficients separately by recall,
precision and per-query F1. Also select coefficients on other product-prefix
groups and apply them unchanged to each excluded group. Report unrestricted,
topic-positive, and topic-largest subsets distinctly. The structures and data
were already inspected; none of this is independent final validation.

Controls are evaluated at the original coefficients, without optimizing the
control conditions to compensate for the intervention. Their conclusions are
limited to that fixed weighting; selected-coefficient controls remain a next check.

## Research informing the design

[Bruch, Gai and Ingber, An Analysis of Fusion Functions for Hybrid Retrieval](https://arxiv.org/abs/2210.11934)
compares score combination and rank fusion and finds parameter sensitivity in
their retrieval settings. This supports measuring the coefficient choice rather
than assuming rank fusion removes the issue; it does not establish the right
weights for these facets.

[Strobl et al., Conditional variable importance for random forests](https://link.springer.com/article/10.1186/1471-2105-9-307)
motivates conditioning permutation controls when predictors are dependent. Here
the analogous caution is that shuffling edge facets across record kinds would
destroy both tag-specific information and kind association. A future edge control
must distinguish those effects and report how much of the graph can be shuffled.

## Completed findings and next discriminating check

All 95 cases completed with unchanged source hashes and original order parity in
all three structures. The top topic-largest weights for the recall structure are
(.75, .75, 0, 0, .5), giving 50.96% recall versus 49.41% at original coefficients;
group-excluded coefficient selection gives 49.94%. In the unrestricted grid the
observed winner has zero topic-facet coefficient (tag/description matching still
operates), but grouped selection falls to 47.41%. Neither is
a defensible reason to declare the facet weights correct or remove topic.

At original coefficients, the recall structure yields 49.16–50.05% under the
23 nonidentity auxiliary label permutations versus 49.41% under actual labels.
Collapsing each tag's auxiliary weights to its mean yields 49.08%. Thus this
construction does not exhibit a strong delivery dependence on correct named
auxiliary query dimensions. Assigning auxiliary rows to different query tags
reduces recall to 48.22% (rotation) or 48.59% (reversal); that effect is neither
large nor consistent across structures. These are sensitivity observations,
not statistical proof of semantic invalidity.

The next discriminating check is to hold the selected coefficients fixed and
compare real edge auxiliaries against joint shuffles within graph-tag × record
kind, with movable coverage reported. Cross this with a fixed replicated
query-row shuffle. This will distinguish edge-specific information, query-tag
binding, and their interaction while retaining kind associations. It must not
independently retune the shuffled controls. Query readings and edge score
semantics still require construct evidence beyond retrieval score gains.

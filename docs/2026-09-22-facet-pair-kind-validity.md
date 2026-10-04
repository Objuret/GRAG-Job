# What the stored pairwise results establish

The original round1 aggregate agreements reproduce exactly. Every frozen
auxiliary edge value also matches the saved score file behind overlay SHA
`352065af504b11020bb06103d320163362538dc1b034c2df377af0e3dd5bb0ec`.
This audit uses existing Opus labels and predictions, not new judgments or RAG gold.

## The comparison relevant to within-tag retrieval

Restrict the existing evaluation to the **same tag, different chunks, same
source kind**. There are 70 unique pairs per facet. The original metric excludes
judge ties and checks whether the predicted score difference has the correct sign.

| Facet | Original aggregate agreement | Relevant restricted agreement | Correct / decided | Judge ties excluded |
|---|---:|---:|---:|---:|
| Temporal | 82.4% | 66.7% | 22 / 33 | 37 |
| Why | 72.5% | 62.1% | 36 / 58 | 12 |
| Activity | 75.6% | 60.0% | 24 / 40 | 30 |
| Concreteness | 69.4% | 60.4% | 32 / 53 | 17 |

This does not establish chance-level performance or explain all retrieval errors.
It shows that the aggregate figures overstate the evidence available for this
specific distinction. Samples are small and dependent, and the many ties matter.
No IID confidence interval or significance claim is made.

The wider same-kind slice also has lower agreement than the across-kind slice:
temporal 70.6% vs 89.5%, why 68.3% vs 77.2%, activity 69.3% vs 82.2%, and
concreteness 68.5% vs 70.5%. Those slices differ in other ways, so this is not
proof that the heads merely classify record kind.

## Provenance corrections

All 3,000 evaluated first-presentation observations have both endpoint chunks
held out by the chunk-hash rule. There are zero shared chunks between gradient
fit and these held-out observations. However, `bakeoff_report.py` uses their A/B/C
outcomes to select the backbone. They are **gradient-heldout, model-selection-exposed**
evidence, not an untouched final test.

The internal fit/validation split has 24 shared chunks. The comment on
`training_val_split` says no chunk text is on both sides, but its OR assignment
allows a mixed pair's training endpoint to appear in validation. This does not
invalidate the zero-overlap outer heldout finding. It does contradict the claim
that the internal checkpoint-selection split is chunk-disjoint. This audit did
not silently change the historical split, refit heads or replace graph values.

## Consequence for the retrieval work

The conditional edge shuffle changed about 35,000 auxiliary vectors and altered
delivered full-chunk sets on 55/95 original-weight and 70/95 group-selected cases,
yet the strongest structure's average recall advantage for real placement was
−0.06 and +0.28 percentage points. The restricted pair agreement above provides
a separate reason to question the measurement's resolution for ordering the same
tag across comparable chunks. Neither result proves that all alternative chunks
are irrelevant or that facets cannot work.

The next measurement comparison should use matched same-tag/type pairs to ask
whether each auxiliary head adds information beyond the actual topic-cosine
edge value, retaining identical decided/tied populations and endpoint coverage.
That comparison can use existing numeric artifacts without changing prompts,
collecting new labels, tuning on retrieval gold or making model calls. Any later
head selection needs an evaluation population not already used for that selection.

Reproducer: `tools/facet_pair_kind_validity.py`. Machine-readable records and
source hashes: `output/research/2026-09-22-retrieval-matrix/pair-kind-validity/results.json`
and `orthogonal-strata.json`.

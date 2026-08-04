---
name: v1-curve-cut-experiment
description: "curve-decided K experiments through 2026-07-22: value-knee = flat-cut equivalent; ceiling-bound chord walk; third reading (HERB_CURVE_WALK=1 progressive frontier, walk-trajectory gap break, K = semantic pool) built clean — 10smoke: K finally spreads (5-50, med 14) but recall 0.51 vs constant-depth-23 control 0.65; area tightness does not track evidence need"
metadata: 
  node_type: memory
  type: project
  originSessionId: e54e69d3-47d3-4355-b080-b4f6eb69f86b
---

The user's curve-decides-K idea, first reading (2026-07-22, branch re-V1-k50):
`_curve_k` in v3/pipelines/artefact_v1.py, opt-in `HERB_CURVE_K=1` — head-to-tail
straight fit over the ranked chunk-value curve, cut at the largest break below it,
caller k the ceiling. Per-row provenance in `meta.curve_k` {pool, break, kept}.

Measured (det leg, gold-100, k=50):
- flat k=50 baseline: recall_id 0.6972, precision_id 0.0518
- curve cut: recall_id 0.6368, precision_id 0.0650, kept mean 37.1 / median 34, 21/100 ceiling-bound
- decisive control — flat k=37 truncation of the same ordering: recall_id 0.6397
  → the per-question K is equivalent to a constant; it does not find an evidence boundary.

Diagnosis (review-verified numerically): the ranked value curve mixes scale regimes —
tag-area contributions vs pool-normalized desc-surface supports (~1e-4 floor) — and the
chord break locks onto that seam, so K measures pool composition, not evidence. Fixes
shipped: 1e-9 noise guard in `_curve_k`, strict `== "1"` flag parse, test suite pins
`arm.CURVE_K = False`, docstrings updated.

Second reading (the height/curve walk, option 2) was built 2026-07-22 under the same
flag: per-part precomputed `_height_edge` chord, desc doors cut at their similarity
break, whole-need description door restored. Gold-100 det: recall 0.7005 / precision
0.0545 vs flat 0.6972 / 0.0518 — but kept hit the 50-ceiling on ALL 100 (stated scope
vouches 338 chunks mean; semantic paths' natural K ≈ 30). User verdict: the walk and
the straight-fit break rule are NOT helping each other. State doc:
`docs/state/2026-07-22-v1-curve-walk-facets-and-cluster-k.md`.

Third reading (2026-07-22 evening, built after offline analysis of the real runs):
`HERB_CURVE_WALK=1` (replaces `HERB_CURVE_K`; recorded in run_manifest
`retrieval_flags`). Clean one-scale design: all values raw multi-k support (per-door
sum-to-1 normalizations and the ×2 desc hint boost deleted under the flag), desc
neighborhoods clustered like tag pools, ONE progressive frontier cheapest-first,
stop = `_gap_break` (next gap > mean+2sd of walked gaps, ≥3 gaps warmup), K =
min(semantic pool, k), scope corroborates by summation and competes for slots but
never sets the count. Flag off byte-identical to shipped. 10smoke det verdict:
mechanism works (K 5–50, median 14, at-ceiling 3/10, stops fire) but recall_id
0.5058 vs flat@50 0.7751, and — the pre-registered bar — a CONSTANT flat cut at the
same mean depth (23) gives 0.6497. Per-question K is worse than constant: two
CoachForce questions got K=5 with recall 0.000 while flat@50 had 0.885/0.610. Also
curve-walk@K ≈ flat-baseline-cut-at-same-K (0.506 vs 0.500): the one-scale re-rank
bought nothing. Diagnosis: semantic-area tightness (dendrogram structure around the
query) is uncorrelated with evidence need on HERB gold questions — need is driven by
citation count and scope territory. Offline ground truth backing this: gold is spread
nearly linearly to rank 50 (recall@depth 0.22/5 → 0.69/50, oracle-K mean 31,
half the questions carry gold past rank 30; gold-100 median 25 citations, ~10
record-ids per chunk).

Also standing from 2026-07-21/22 probes: stored HAS_TAG w_facets are non-signal
(0.5–1.0 band, temporal on 555/20k edges; detE facet-channel run changed 5/100
retrieved sets, recall ±0.0000); the geometric det facet channel (detf/detR/detA)
moved recall ≤ +0.003. Facet placement, not facet values, is the open question.
Related: [[gold-100-results-and-judge-decision]], [[user-concepts-are-canon-not-substitutes]].

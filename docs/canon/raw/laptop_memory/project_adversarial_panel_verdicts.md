---
name: v1-adversarial-panel-verdicts
description: "2026-07-22 adversarial panel (4 scouts + 5 tier-A PhD specialists, ~1M tokens): curve-walk stop rule condemned (no spacing rule calibratable — permutation-proven), value system is an ordinal rank staircase with ~12:5:1 scope:desc:tag door bias, flat det = desc-kNN+scope retriever (widening 0/100), Neo4j contracts pinned live ((1+cos)/2, HNSW recall 61-63/64, 1e-6 floor unreachable), 3 canon conflicts await user decision"
metadata: 
  node_type: memory
  type: project
  originSessionId: 11c068bc-46e2-4d1d-9602-6a0ad8cc02b5
---

Method: 4 adversarial scouts (math/physics/engineering/logic) -> merged taxonomy of
13 review types -> tier A = 5 grounded specialists (scale-commensurability,
statistical stop rules, Neo4j contracts, effective-configuration/vacuity, canon
fidelity), each grounding in primary sources / live probes / full replays before
reviewing. Method log + agent ids: scratchpad adversarial_review_method.md
(session 11c068bc). The panel worked — high convergence, real derivations,
several of the orchestrating agent's own claims overturned. Candidate for
permanent agents.

Verdicts (all grounded, replayed on real artifacts):

1. **The curve-walk stop rule must not ship as the K-decider.** Exact false-stop
   14.6% at the n=3 warmup (t2 derivation; 31% of real stops happen there);
   first-gap transient (measured from height 0) changes 46/100 stop decisions;
   permutation test: shuffling each chain's gaps gives 60.1±4.1 stops vs 67
   real — the statistic carries almost no order information; a properly
   calibrated version is indistinguishable from both the miscalibrated one and
   pure noise. Measured cost: kept-K recall 0.5058 vs 0.7464 at kept-50 on the
   same questions. Stops are population-seam artifacts: thresholds fit to
   near-duplicate tag micro-clusters (two different CoachForce questions produced
   the IDENTICAL chain and identical K=5). Verdict: no spacing-based rule is
   calibratable on these chains (median 9 events). Paths: reference-null
   calibration (predicted low power) or stop-on-content (sufficiency review is
   the only mechanism that observes evidence). Prerequisite for ANY stop rule:
   per-event chunk membership logging -> recall-vs-stop-depth ground truth.
2. **The value system is an ordinal rank staircase, not a distance system.**
   support = m(rank)/d² (m = 4/3/2/1 by pool-relative rank; extend=True gives
   scope m up to 10 at N=2758 — 2.5x door inflation). Tag door damped by
   facetTerm×w_chunk×relevance (measured p50 0.194 det); built-in curve-walk
   door prior ~12.2:4.9:1 scope:desc:tag at equal rank+distance. Flat
   normalization erases absolute proximity (uniform d=0.9 pool bit-identical to
   d=0.15 pool). The 1/d² on (1-cos)/2 is really 16·chord^-4 — the Keller 1985
   "fuzzy k-NN" citation is false (it's Shepard IDW, wrong exponent).
   Prescription (Bruch TOIS 2023 grounded): per-door bounded cosine scores, w_facets
   renormalized per edge, theoretical-min-max normalization, tuned convex
   combination on gold-100; drop the multi-k staircase.
3. **What the shipped arms actually are** (liveness matrix): flat det =
   desc-kNN (67% of kept value) + product scope (32%) + ONE tag (~1%); widening
   0/100, cross-part summation vacuous (1 part), facets direction-vacuous
   (facet-count leakage flips 9.7% of within-tag pair orders). Flat haiku is a
   DIFFERENT retriever: tag door dominant (70% of value). Affinity boost is
   live: moved the anchor on 28/100 det questions. The old gold-100 haiku
   shipment (20260718) ran an older pipeline (meta fused/grounding/rankings) —
   no gold-100 haiku run of the current code exists.
4. **Neo4j contracts pinned live** (Kernel 2026.04.0, HNSW+quantization both
   indexes): index score AND vector.similarity.cosine = (1+cos)/2, so all
   support-side distances are HALF-scale while dendrogram heights are
   full-scale (rank-invariance saves it; docstring wrong). queryNodes ordering
   documented+probed. ANN recall@64 = 61-63/64; quantization noise ±1e-3 =
   ±40% support noise at tight distances (anchors can flip between near-ties).
   The 1e-6 floor is unreachable (closest real pair 3700x above) — the 1e12
   blowup is theoretical on this corpus. Single run_id/dataset confirmed.
   db.index.vector.queryNodes is DEPRECATED in the deployed version (SEARCH
   clause is the successor). Six cheap prepare-time assertion pins prescribed.
5. **Canon conflicts requiring USER decisions** (not agent calls): (a) "model
   emits no numbers, ever" vs pass-2 interpreter emitting 0.0-1.0 facet scores
   consumed in ranking; (b) "no answer-sufficiency oracle" canon vs the
   sufficiency review (which was RIGHT on VizForce — metric artifact, see
   [[v1-ordering-diagnosis]]); (c) "the chunk description is dead" vs an arm
   that hard-requires desc_emb and is desc-dominated. Plus doc debts: successor
   state doc owed (2026-07-22 doc describes deleted _curve_k/_height_edge),
   CLAUDE.md artefact section stale ("pipelines/artifact.py" misspelled +
   missing the v1 arms), "surface"/"door" coinages exported into meta keys and
   an env var name.

Related: [[v1-ordering-diagnosis]], [[v1-curve-cut-experiment]],
[[user-concepts-are-canon-not-substitutes]].

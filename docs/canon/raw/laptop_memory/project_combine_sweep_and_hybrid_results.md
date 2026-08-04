---
name: combine-sweep-and-hybrid-results
description: "2026-07-23 results after the normalized-combine rebuild: fixing the un-normalized sum gained +0.030 recall (det 0.7039->0.7339); haiku combine sweep verdict (global/none win, absolute/per-path lose, corroboration helps ordering, facets null, ~0.80 wall holds); NEW hybrid lucene+vector arm built and run — artefact beats it decisively at matched id-budget (0.68/0.73 vs vector 0.41 > hybrid 0.39 > lucene 0.27). ALL retrieval-only; no judged answer run yet."
metadata: 
  node_type: memory
  type: project
  originSessionId: 42699b8f-4ff0-43ba-80ed-d017967a8cab
---

All gold-100, retrieval-only (--no-eval), id-metrics computed locally. Metric: recall_id
(union) + nDCG@50 (ordering, from meta.chunk_ids; analyst script
scratchpad/rank_aware_sweep_analysis.py; conjunctive decision rule = permutation-Holm AND
BCa-CI AND sign AND Cliff). Baselines rebaselined to CURRENT code (old 0.7039 was stale).

**Combine rebuild payoff:** the un-normalized-sum combine was replaced by per-path
normalization + strength-graded modifiers (lerp `max(0,1+s(m-1))`) + weighted-sum over the
union. Net: det default 0.7039 -> 0.7339 (+0.030), the biggest single move of the day.

**Haiku combine sweep (cross-part LIVE — 3-8 parts/q, all 100):** baseline haiku default
(sum/relative/per_path) recall 0.6039, nDCG 0.416.
- global-norm: recall 0.6812 (+0.077), nDCG +0.046 — BETTER both (all gates).
- none (raw): recall 0.6536 (+0.050), nDCG +0.049 — BETTER both.
- absolute: recall 0.5359 (-0.068) — worse. max+absolute: 0.5246 WORSE both.
- max (corroboration off): recall ns, nDCG -0.026 WORSE -> **corroboration (sum) helps
  ORDERING**; user's cross-part idea validated on nDCG.
- facets STR_FACET=1.0: ns both (flat facet data, as predicted; all w_facets 0.3-1.0 >=0).
Verdict: the "principled" per-path/absolute normalization LOSES; winning = let stated-scope
(strongest signal) dominate (global/none). Contradicts the maths adversary's theory
recommendation. Best haiku 0.68 still < det 0.73; whole family under the ~0.80 re-rank wall.

**NEW hybrid arm** (`v3/pipelines/hybrid.py`, ARMS+=hybrid): min-max late fusion of
lucene+vector, `HERB_HYBRID_ALPHA` (0=lucene, 1=vector, 0.5 default), union gated on
positive arm-weight so endpoints reduce exactly. 154 tests green. Ran gold-100.
**Matched id-budget (~500 ids each, the FAIR comparison):** artefact haiku-global 0.6812,
artefact det 0.7339, pure vector 0.4100, hybrid a=0.5 0.3883, pure lucene 0.2742.
-> **Artefact beats a properly-built strong hybrid baseline by ~0.27 at matched budget —
the lead is NOT an id-budget artifact.** Fusion is a wash (0.5 ~= pure vector; weak lucene
drags it). Nuance for rigor: artefact retrieves chunks-of-bundled-ids vs baselines' single
ids — flag but 0.68 vs 0.41 isn't granularity noise.

**Cluster-K / best-fit (HERB_CURVE_WALK) tested on the FIXED machinery — REVERSES the old
result.** cluster-K 0.7341 / nDCG 0.4748; cluster-K + global-norm **0.7492 / nDCG 0.4756 —
the best artefact haiku result of all, beating flat-global (0.6812) and even det-default
(0.7339), same id-budget, both metrics.** BUT K=50 on all 100 questions — the "curve
decides K" mechanism is INERT (never cuts below ceiling); the gain is the curve-walk's
progressive-frontier ORDERING over normalized values, NOT the K-selection. This reverses
[[v1-curve-cut-experiment]] (broken machinery: K spread 5-50 but recall 0.51); fixing the
values flipped it to "K stays 50 but orders well -> 0.75". Open: whether making the K-cut
actually fire adds anything, or K=50 + good ordering is just right.

**Why / open:** everything above is retrieval recall/ordering, NOT answer quality — the
artefact's bottleneck was measured as EXTRACTION not retrieval, so the lead may not survive
into judged answers. Judged run 2026-07-23: NIM generator backend was DOWN (404 on
integrate.api.nvidia.com), so generation was re-run with --generator claude-haiku-4-5 (same
for all 3 arms = fair, but NOT comparable to the June NIM-generator shipment); rejudge on
common id-set with claude-haiku judge in progress (artefact-global vs hybrid vs vector).

**How to apply:** re-runs are cheap (embed + interp caches warm on gold-100); haiku warmup
was 100q. Loose ends: hybrid micro-fix re-review + graph refresh deferred. Code uncommitted
on branch re-V1-k50. Related: [[v1-machinery-fix-and-toggles]], [[v1-ordering-diagnosis]],
[[final-audit-panel-before-conclusions]], [[benchmark-validity-caveats]].

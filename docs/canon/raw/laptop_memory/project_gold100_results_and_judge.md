---
name: gold100-results-and-judge
description: "gold-100 three-arm headline numbers, the settled judge decision, and where the shipment data lives"
metadata: 
  node_type: memory
  type: project
  originSessionId: 3b10041c-68f0-4aa1-a959-730ed70f5cc7
---

Gold-100 (k=50) three-arm result, committed on `re-V1-k50` (14dd887 code, 7879dfe data),
pushed 2026-07-20. Analyst shipment doc: `v3/output/DATA_README.md`.

**Headline (cross-arm valid):** artefact_v1 leads every valid metric.
context_recall_id 0.636 vs lucene 0.089 / vector 0.113 (7× / 5.6×) — generator-independent,
the cleanest result. Single-judge (haiku) judged metrics: faithfulness 0.90 / 0.71 / 0.67,
context_recall_llm 0.49 / 0.21 / 0.36, answer_correctness 0.24 / 0.19 / 0.20.

**Superseded on retrieval 2026-07-21 by the deterministic redesign** (user's
query-relative area design: levels/fuzzy clusters/stated scope/cross-part value, zero
interpreter calls): `artefact_v1_det` gold-100 recall_id **0.697** (per-type: pr 0.713 vs
committed 0.421, company 0.855, url 0.851, content 0.733; person 0.553 slightly down),
~6 s/question, byte-repeatable (2 runs identical). Runs
`artefact_v1_det__gold100__20260721T173011Z` (+`detf` twin = facet channel, measured
+0.003 ≈ nil; facet layer empirically inert at query time — see session analysis).
Answer-side/judged metrics for det arm still unmeasured (retrieval-only runs).

**Judge decision — SETTLED:** claude-haiku-4-5 is the daily + shipment judge. Shoot-out
(n=10, 4 judges) then full n=100 confirm it tracks the canon qwen-397B judge within
0.00–0.15 mean per-cell; sonnet/opus drift more lenient and buy nothing; qwen-on-NIM
never completed a judged eval on the laptop. Canon stays citable as a second opinion.
All three arms now haiku-judged (June lucene/vector re-judged into `__j-claude-haiku-4-5`
dirs). See [[judge-run-cost-math]], [[benchmark-validity-caveats]], [[headless-claude-models]].

**Confounds carried into the table** (in DATA_README, not yet fixed): artefact answers =
claude-sonnet-5, baselines = qwen — a generator confound on the *answer* metrics only.
Killing it means regenerating lucene/vector with sonnet (~200 calls through the new claude
lane); user's open call to ship-with-caveat vs regenerate-first.

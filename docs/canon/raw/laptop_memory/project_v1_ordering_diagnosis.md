---
name: v1-ordering-diagnosis
description: "2026-07-22 door-trace diagnosis (10smoke, both legs): pool ceiling recall = 1.0 everywhere, all missing recall is ordering; scope door covers 100% of gold (AUC ~0.83-0.87), det-leg tag door touches 1 junk chunk/q, haiku-leg tag door covers 88%; every ranking recipe over existing door values caps at ~0.79-0.80; haiku leg 0.677 < det 0.775 (cross-part summation drowns scope; sufficiency review wrongly cut VizForce 50->16, 0.851->0.402)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 11c068bc-46e2-4d1d-9602-6a0ad8cc02b5
---

Door-trace instrumentation (2026-07-22, uncommitted with the curve-walk work):
`HERB_DOOR_TRACE=1` on artefact_v1/artefact_v1_det dumps per-pool-chunk door values
(tag/desc/scope) + resolve pointers into `meta.door_trace`; observability only,
flag recorded in run_manifest `retrieval_flags`. Runs:
`output/artefact_v1_detTRACE__10smoke__20260722T050703Z` (verified byte-identical
kept sets to the flat baseline — the curve-walk refactor is regression-clean) and
`output/artefact_v1_haikuTRACE__10smoke__20260722T130200Z`.

Measured (10smoke, k=50):

- **Pool ceiling recall = 1.000 on every question, both legs.** Membership is
  solved; the whole gap (det 0.775, haiku 0.677) is ordering inside the pool.
- **Stated scope is the spine:** touches ~614 chunks/q, covers 100% of gold
  chunks, touched-AUC 0.82 (det) / 0.87 (haiku). Scope-only chunks carry 0.27
  of recall — scope must stay a membership door.
- **Det-leg tag door is dead:** touches exactly 1 chunk/q (anchor only; widening
  never fires — scope fills pool ≥ k), never gold. Haiku-leg tag door lives:
  87.7% gold coverage, touched-AUC 0.677. Desc door: 64-wide, ~62% coverage,
  AUC ~0.67-0.80.
- **The ordering wall: ~0.79-0.80.** Offline re-ranking of the full traced pools
  with every principled recipe (normalized convex combination, Borda,
  corroboration products/sums/tiebreaks, scope-gated variants) caps at 0.7926
  (det) / 0.7999 (haiku) vs current 0.7751 / 0.7071. Scope-alone is the best
  single scalar. The remaining ~0.20 of gold sits low in EVERY door's values —
  no re-mix of existing signals reaches it; a finer within-scope relevance
  signal is required (candidates: better tag/description layer from the build
  side; the raw-text lexical channel is outside the artefact's
  references-not-content design).
- **Haiku leg loses to det (0.677 vs 0.775)** because cross-part summation
  drowns scope value under part mass (its own re-rank "current total" = 0.707 <
  scope-alone 0.796). Per-question it splits: haiku fixed two ActionGenie
  questions det failed (0.42->0.70, 0.71->0.82) and broke others.
- **The VizForce sufficiency cut (kept 16, recall 0.851 -> 0.402) was a CORRECT
  answer-sufficiency verdict** (adversarial-panel replay, 2026-07-22): all
  three gold demo URLs sit inside kept chunk 11, two visible in the judge's
  240-char digest; the lost 26 citations are co-cited slack messages carrying
  no answer content. The harm is to citation recall — a metric the review
  cannot see — not a judge error. The review is otherwise near-inert (9/10
  questions "never sufficient" -> kept 50).

**Why:** these numbers say where artefact improvement lives — not in retrieval
math over current values (exhausted at +0.02), but in (a) a sound value system
(see [[v1-adversarial-panel-verdicts]] for the prescribed rebuild), (b)
build-side signal quality (tag layer: 12.6% URL junk; desc embeddings are
model-emitted phrases).

**How to apply:** any ranking-change proposal must beat scope-alone (0.7926 det
10smoke) before it's interesting; validate on gold-100 det retrieval-only
(cheap). Don't tune recipes on 10smoke — the wall is the finding.
Related: [[v1-curve-cut-experiment]], [[gold-100-results-and-judge-decision]],
[[benchmark-validity-caveats]].

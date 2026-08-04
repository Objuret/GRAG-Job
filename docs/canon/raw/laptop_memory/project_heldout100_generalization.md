---
name: heldout100-generalization
description: 2026-07-29/30 held-out 100 run — artefact retrieval lead generalizes to untouched questions; per-type deltas small; det held-out run died
metadata: 
  node_type: memory
  type: project
  originSessionId: 579f6380-b677-4892-9088-30ad076873ab
  modified: 2026-07-29T23:07:57.544Z
---

The generalization check the audit demanded is done: all three arms ran retrieval-only (k=50) on `data/heldout100.jsonl` — 100 answerable questions, zero gold-100 overlap, type-balanced (20/20/20/19 url/21 content), seed 20260729.

**recall_id (cross-arm valid): artefact_v1 (interpreting, haiku) 0.594 vs vector 0.112 / lucene 0.074 — artefact wins all five type cells, 3–20×.** Type-matched deltas vs gold-100 interpreting run: company +0.052, person +0.036, pr −0.046, content −0.043 — no collapse; the 0.636→0.594 aggregate dip is type-mix (gold 55% content). Baselines flat across sets (sets comparably hard). First real url sample: 0.463 (n=19; gold url was n=1 anecdote). pr is the weakest artefact cell on both sets (0.375 held-out).

Folders: artefact_v1__heldout100__20260729T205930Z, lucene__heldout100__20260729T223312Z, vector__heldout100__20260729T224153Z (all 100/100, retrieval-only, id-sets verified = heldout100.jsonl). **artefact_v1_det__heldout100__20260729T180505Z is DEAD (1 ran / 99 failed, no eval) — never cite; re-run needed for a det held-out number.** No hybrid held-out run. Interpretations + embeds for the set are now cached, so reruns are cheap.

Thesis: the matched-budget lead is now backed by held-out validation; the "tuned-on-gold-100" caveat is answered for the arm-level claim (config-level deltas remain in-sample only). [[audit-panel-2026-07-28]] [[corroboration-probe-verdict]]

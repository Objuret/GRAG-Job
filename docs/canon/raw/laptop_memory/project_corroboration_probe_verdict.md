---
name: corroboration-probe-verdict
description: 2026-07-29 corroboration probe result — rare-tag sharing is a real but redundant discriminator; desc already carries it; oracle headroom +0.21 quantified; complementarity is the one lead
metadata: 
  node_type: memory
  type: project
  originSessionId: 579f6380-b677-4892-9088-30ad076873ab
  modified: 2026-07-29T16:28:11.362Z
---

2026-07-29, corroboration probe per [[audit-panel-2026-07-28]] absorption doc §6, run offline on the committed baseline (detCUR 0.7339, gold-100): **rare-tag corroboration is a real signal but a redundant discriminator — verdict binds this operationalization (capped shared-tag counts vs top-ranked seeds), not the user's corroboration concept.**

- Signal real: beats random territory fill +0.029..+0.041 (p≤0.003 all tails); stage-1 AUC 0.64 at best config (cap50_top10_weighted).
- Fails the pre-declared bar: corr − desc-distance ≤ +0.014, n.s. at every tail — description distance already expresses whatever event structure capped tag-sharing reaches.
- "Rareness" is not where event info lives: AUC rises monotonically with degree cap; deg≤5 tags miss 82% of missed-gold chunks entirely.
- **Oracle headroom quantified: +0.2125 recall from a 10-slot in-territory swap** (0.7339→0.9463) — the territory contains the gain; no found discriminator captures more than ~5% of it. Part-J step-(3) discriminator remains unfound.
- The ~0.80 wall stands: best fill 0.7435 < clusterKglob 0.7492.
- Combination follow-up (stage 3, same day, pre-registered): complementarity is REAL — per-question oracle chooser worth +0.041 (ceiling 0.7845, ≈ the historical ~0.79 wall) — but INACCESSIBLE to question-independent rules: score fusion −0.005, rank fusion +0.005 (both p≈0.7), fitted per-type routing only +0.011. Mean corr∩desc top-10 overlap 1.51 chunks — the orderings disagree, but nothing in the two score vectors says which to trust per question. Verdict: corr×desc fusion CLOSED; a gain requires a new per-question regime signal; the ceiling captures only 20% of the T=10 oracle headroom anyway.
- Committed-baseline corrections to the rewrite-era §5 numbers: dominant retrieved file = gold file 100/100; gold spans exactly 1 file 100/100.
- The null survives the tag-contamination caveat (tags descend partly from the oracle-reading tagger), which strengthens it.

Scripts + per-question intermediates in the 2026-07-29 session scratchpad (corroboration_stage1/2.py, corrob_stage1_intermediate.json).

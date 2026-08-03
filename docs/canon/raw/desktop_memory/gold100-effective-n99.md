---
name: gold100-effective-n99
description: "gold-100 paired comparison was n=99: gold_personalizeforce_34 aborted on the v1 graph arm (hard gate on eid_bac7c6c4, 'absent from herb-eval') — but the eid exists ~395x in raw; a v1 graph hole + hard-filter brittleness, both designed out in v2"
metadata: 
  node_type: memory
  type: project
  originSessionId: 451fee55-ec50-4aa5-9778-212330c505d6
---

**The v1 gold-100 paired eval was effectively n=99.** `gold_personalizeforce_34` was permanently skipped on the graph arm: the v1 interpreter hard-gated on employee `eid_bac7c6c4`, which had no node in `herb-eval`, so retrieval aborted before answering (v1/docs/backend/ragas_eval_report.md — "invalid hard gate / permanent skip"; paired n=99, the cohort file still holds 100 ids; Lucene baseline answered it).

**Verified 2026-06-12: the eid is NOT missing from the data.** It's in employee.json, salesforce_team.json, and ~395 mentions across PersonalizeForce (180), EdgeForce (150), FeedbackForce (65). So the skip was a **v1 graph-construction hole** (employee lost between ingestion and the herb-eval filter) compounded by **hard-gate brittleness** turning the hole into a total abort.

**How to apply:** this knowledge lives ONLY here and in v1's frozen records — **NEVER in v2** (user, hard, 2026-06-12: "don't mention shit if it will work WITHOUT mentioning it"). No skip lists, no special-casing, no doc mentions: v2 runs all 100 cohort questions as ordinary questions, because its design already kills the failure class (no hard filters — unresolved literal = no boost + loud log, retrieval continues; directories read from raw — entries can't be "lost"). If the question fails on v2 anyway, that's a loud bug to fix, never an exception to document. Generalize the principle: v2 gets no baked-in knowledge that correct behavior makes unnecessary. Only use for reading v1 numbers: v1's paired n was 99. Related: [[retriever-routing-model]], [[v2-graph-spine]], [[herb-eval-is-the-artefact]], [[no-silent-fallbacks]].

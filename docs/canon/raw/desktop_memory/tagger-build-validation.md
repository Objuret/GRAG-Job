---
name: tagger-build-validation
description: "How to test the v2 tagger (phrase tags + measured weights; cost = wall-clock under 40 RPM) cheaply — catch errors on the first chunks, not after a full corpus run. Full text in design doc §16."
metadata: 
  node_type: memory
  type: project
  originSessionId: b08ba78a-3d52-48aa-935f-dc4054c4d871
---

**Resolved 2026-06-08; full text in design doc §16 of [docs/v2_artefact_rebuild_design.md](../../../../../exjobbet/repo/docs/v2_artefact_rebuild_design.md).** How the expensive tagging stage is validated DURING the build so a small error surfaces on the first chunks, not after the whole corpus is tagged. The dichotomy "bulletproof everything vs run blind" is FALSE.

**Two materials.** Deterministic prefix (probe→reference→structure→chunk) = pure functions over sacred source → run on the whole corpus FREE (no LLM), dump artifacts, golden-test; robust *because* running is free. The tagger is the ONLY expensive/stochastic part, and its quality is an empirical unknown (same unknown the §9.1 cap sweep measures) — only validated by running + looking. A sample run IS the method, not a compromise short of bulletproof.

**The expensive call's outputs, each with its cheapest test (description arm REMOVED 2026-06-11 — the description is dead; tagger emits phrase tags only, no numbers):**
- **tags (phrases)** → data-quality assertions in code, no LLM, instant at N=1: MUST-NOT rules (no employee-ids/dates/PR-numbers as concepts), closed-vocab membership where a closed set applies. SPADE pattern. Wire as promptfoo assertions → the prompt-regression net (re-runs on every prompt edit).
- **weights (measured, never model-emitted)** → NO isolated unit test for "is this weight correct." Cheaply assert only invariants (weights must discriminate — uniform = bug; a chunk plainly about X must outweigh a tangential one). Real validation is end-to-end via gold-100 retrieval → so a thin retrieve path is needed as a TEST INSTRUMENT earlier than the [[retriever-routing-model]] / §14 ordering implies.

**Error-analysis-by-reading PRECEDES the assertions** (Hamel Husain — "the most important activity in evals"): run the real tagger on ~20–40 chunks across content-kinds, read each output vs its source, journal → failure taxonomy → count. The assertions are DISCOVERED by looking, not specified up front. ~100 traces to saturation.

**Sample size: catching ≠ measuring.** ~30 draws catches a frequent bug (binomial — a 20%-prevalence error can't hide in 30); measuring a rate with a tight interval needs 250–500 (Clopper–Pearson exact small-n). gold-100 ([[herb-eval-is-the-artefact]]) is the ready-made in-distribution gold set for the measurement arm.

**Time levers (revised 2026-06-12 — NIM is free; the budget is WALL-CLOCK under the 40 RPM limiter):** response-cache keyed on chunk-hash + prompt-version so a re-run only re-spends time on what changed; small fast model first for structural/vocab/wiring bugs (model-independent); the corpus pass is the only long run and happens once per prompt version that survives the sample reads. Fail loud throughout ([[no-silent-fallbacks]] — the smoketest instinct).

**Progression (walking skeleton / tracer bullet):** full pipeline on ONE input → stratified per-content-kind sample (look HERE) → full corpus LAST. Corpus breadth = rollout dial, not smoketest.

**The one design blocker before any run** = the tagger prompt + output contract (the phrase-tag contract: phrase definition/granularity, MUST-NOTs, input rendering per content-kind → actual prompt + returned JSON; phrases only, no description, no numbers). Everything else open in §15 is impl or downstream of the run.

## Related
- [[v2-chunking-model]] — decision #14 (one stateless call per chunk) is the PRECONDITION for this whole strategy
- [[v2-build-pipeline]] — the build this validates
- [[retriever-routing-model]] — the thin retrieve path that validates weights
- [[no-silent-fallbacks]] — fail loud; the smoketest instinct
- [[herb-eval-is-the-artefact]] — gold-100 oracle = the measurement gold set

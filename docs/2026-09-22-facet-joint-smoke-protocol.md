# Standard gold smoke for the joint-facet candidate

User steering on 2026-09-22 asks specifically for the gold smoke, RAGAS numbers,
and an actual working artefact arm. Research retrieval replays do not satisfy
that request. Expose the existing candidate as `artefact_facet_joint` through
the standard harness and run the existing fixed `10smoke` set once.

## Fixed candidate before benchmark access

- Frozen Volmax eligible graph export: 4,808 chunks and 57,204 semantic edges;
  saved graph facet overlay and pinned embeddings. Record snapshot hashes and
  origin; do not describe the snapshot-backed arm as a live database retriever.
- Unchanged current split GENERATE and SCORE prompts, one Haiku call each per
  uncached raw question. No phrase-preservation prompt trial or manual query fixes.
- Fresh query embeddings from the existing pinned local model and query prefix;
  original graph vectors, reference distribution and neighbor relations.
- Existing joint policy: per-facet maximum route profile, outer description
  factor, coefficients `(1,.25,.25,.25,.25)`, exact-record recovery, and original
  literal-Product area resolution with global access and unresolved fallback.
- No new literal-Tag scope fallback, coefficient search or source-specific rescue.

The new arm must accept arbitrary raw questions through the normal harness
interface. It must not use the seven development questions or saved reading IDs
as an allowlist. Only validated interpretation results may be reused from its
own correctly keyed cache; preserve ambiguous/failed attempts without silently
retrying them.

## Standard delivery and evaluation

Return the complete recovered ranking to the existing source resolver and shared
character-budget function. Use the standard 72,000 resolved-context-character
cut, including its boundary truncation and artifact-ID crediting behavior.
This differs from the research replay's whole-frontier saved-text cut. Preserve
that distinction in reports; old acquisition-cost tables are not directly the
standard smoke's budget accounting.

Use standard answer generation (`claude-sonnet-5`) and the configured RAGAS
catalog (14 metrics), with the existing `claude-haiku-4-5` judge. First generate
answers, then run standard rejudging on the same ten IDs. Record versions, model
usage, failures, successful metric counts and missing/error counts with means.
Execution failure must not be reported as zero quality or perfect success.

The harness and evaluator may read their usual questions/gold internally. Agents
must not inspect benchmark questions, gold, generated answers, retrieved benchmark
contexts, `arm_outputs.jsonl` contents or per-question judge explanations. A
mechanical reporting wrapper may count records and extract aggregate numeric
metrics/usage. Child logs remain private because exceptions may contain inputs.

## Completion evidence

Before the run, test the arm against existing non-benchmark development arrays,
standard context-budget/ID behavior, caching and concurrent embedding access.
Verify that the harness can import and select the arm. Freeze the run commands
and relevant source hashes. One completed ten-question generation run followed
by its RAGAS result table is the requested smoke deliverable. Preserve failures;
do not choose or tune the design from benchmark outcomes.

This closes an integration/evaluation gap. RAGAS numbers do not by themselves
validate the facet meanings or establish uniquely correct facet coefficients.

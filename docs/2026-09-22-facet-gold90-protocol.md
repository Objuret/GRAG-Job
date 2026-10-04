# Frozen remaining-90 retrieval comparison

After closing the ten-question diagnostic loop, evaluate the unchanged candidate
on exactly `gold100 minus 10smoke`, preserving gold100 order. This expands query
coverage within the chosen HERB benchmark; it is not a new corpus or a claim that
these sources were absent from facet training or every previous repository run.

Freeze all arm/harness/dependency code, graph snapshots, prompt settings, ID lists
and benchmark-file hashes before execution. Keep the existing `(1,.25,.25,.25,.25)`
policy, literal Product scope, graph relations/recovery, local pinned Nemotron
embedder, Claude Haiku interpreter and **72,000 serialized characters** unchanged.
Use the standard harness with `--retrieval-only --no-eval`, four question workers,
and a fresh private interpreter cache. There is no answer generator or model judge.

Each distinct uncached interpreter request has one transport attempt through the
existing arm; no automatic retries or replacement questions. Record failures in
the 90-question denominator. Compare auxiliaries on/off using each successfully
saved interpretation, so query-reading noise cannot masquerade as a weighting
effect. The off score is the recorded topic contribution, as verified in the prior
smoke's independent-envelope audit. Scope and actual serving delivery remain fixed.

Use gold pointers only after ranking/recovery/delivery. Evaluate the installed
RAGAS `context_precision_id` and `context_recall_id`; report per-question paired
changes, success/failure counts, means over successful paired cases and explicit
failure-inclusive recall with a missing retrieval counted as zero. Do not invent
precision values for undefined/empty retrievals. Include product-group aggregates
to expose concentration rather than treating source IDs as independent trials.

No coefficient, prompt, scope, candidate-size or budget tuning follows these
outcomes. No new permutation search or individual source rescue. Positive, null
and mixed results all finish this checkpoint. Source-ID metrics are bounded
retrieval measures, not exhaustive semantic relevance, facet construct validity
or generated-answer quality. A missing gold source is not by itself a defect.

The raw harness output and logs remain private inputs to mechanical processing.
Do not inspect or export benchmark question text, reference answers, generated
contexts or source bodies. Numeric progress, provenance, source pointers and
aggregate results can be reported.

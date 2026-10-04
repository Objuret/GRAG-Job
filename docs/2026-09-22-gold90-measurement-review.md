# Remaining-90 measurement review

The independent read-only review of `facet_gold90_analysis.py` passed the paired
comparison design: identical saved interpretations, reconstruction of the complete
original recruitment and delivered text, an auxiliary-off score from the independent
topic contribution, and gold-ID comparison only after both deliveries finish.
It uses the installed deterministic RAGAS ID metric classes, with missing retrievals
reported explicitly rather than silently replacing failed questions.

The review mechanically confirmed that the 90 IDs form 29 product-prefix groups
and all have nonempty reference ID sets. These groups expose concentration; they
are not proof that products or individual questions are independent samples.

The suggested rank check was added before analysis started: each saved rank must
match sorting by descending score and ascending chunk ID, and the saved complete
ranked-ID sequence. This protects the exported source-pointer rank traces as well
as the delivered metrics.

The frozen protocol's phrase "all ... dependency code" is too broad. The manifest
captures declared repository dependencies and artifacts, not the entire installed
environment. The analysis additionally records the installed RAGAS version and
hashes the two metric implementations. The original protocol remains unchanged
to preserve the experiment's recorded hashes.

This comparison measures the retrieval effect of the four auxiliary contributions
under the current pipeline. It cannot establish uniquely optimal coefficients,
semantic validity of the facet readings, unseen-corpus generalization, exhaustive
relevance, or generated-answer quality.

## Execution failures

The standard retrieval run wrote 85 valid records and five distinct failure
records, together accounting for all 90 planned IDs. All 85 saved contexts have
72,000 serialized characters. Mechanical classification of the private interpreter
cache found five GENERATE-stage `ValueError` failures with no JSON object in the
response. No response text was inspected or exported, and none was retried.

After retrieval, final bookkeeping raised `MemoryError` in
`orchestrator._done_ids -> jsonl.load -> Path.read_text` while loading the complete
1,444,671,154-byte output. This prevented the normal run manifest from being written.
The wrapper retained terminal status and unchanged-input hashes. Independent
streaming validation parsed all 85 saved records successfully, without altering
them or rerunning retrieval. The downstream analysis preserves the nonzero process
exit and checks exact replay before scoring.

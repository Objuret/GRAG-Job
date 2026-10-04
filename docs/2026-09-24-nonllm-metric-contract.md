# Non-LLM context metric comparability, fixed 10-smoke

This is a post-retrieval metric-contract audit, not a retrieval intervention. It uses the ten fixed answers from `artefact_facet_program_v2__10smoke__cb72000__20260924T001226294548Z`. The audit made no model calls, changed no answer or score, and exported no question, answer, source, or interpretation text.

## Verified contract

- `prod/eval/ragas.py:499-541` builds one reference context per cited corpus artifact by recursively joining **all string leaves** of the complete artifact record. It passes delivered context strings unchanged as `retrieved_contexts` and credited artifact IDs separately as `retrieved_context_ids`. `prod/eval/ragas.py:443-444,570,658` constructs the default non-LLM metrics over these samples.
- Installed RAGAS **0.4.3** uses `NonLLMStringSimilarity`, normalized Levenshtein similarity `1 - normalized_distance` (`.venv/Lib/site-packages/ragas/metrics/_string.py:62-95`). `NonLLMContextPrecisionWithReference` takes each retrieved context's best similarity to any full reference artifact, calls a match at **>= 0.5**, and computes rank-sensitive average precision over those binary matches (`_context_precision.py:186-248`). `NonLLMContextRecall` takes each reference artifact's best similarity to any delivered context and counts matches only at **> 0.5** (`_context_recall.py:165-223`). The repository passes no threshold or distance override.
- The fixed-program arm resolves graph chunks into contexts: a chunk can be a character range of one artifact, one record, or multiple JSON records; metadata chunks can carry no artifact ID (`test/arms/artefact_v2.py:1812-1842`). Its 72k cut can include a partial final context, but source IDs are credited only from fully delivered chunks (`test/arms/artefact_v2.py:1844-1863`, `prod/harness/char_budget.py:14-34`). Thus an ID hit asserts artifact membership, not delivery of that artifact's entire text.
- Lucene and vector construct one text unit per artifact or directory record and return one context per ranked unit (`prod/arms/lucene.py:64-106,253-304`, `prod/arms/vector.py:70-95,278-331`). Their artifact-context text is flattened artifact text, whereas the fixed-program context may be a short excerpt or JSON serialization. None of these delivered formats is identical by construction to the evaluator's all-string-leaves reference; the segmentation difference is the specific comparability issue.

## Length-only bound on the actual ten answers

For normalized Levenshtein similarity between strings of lengths `a` and `b`, the score cannot exceed `min(a,b)/max(a,b)`. This follows from the minimum `|a-b|` insertions or deletions. A context less than half as long as a reference cannot pass either 0.5 threshold even if it is a perfect excerpt. A context over twice as long has the same barrier. Precision allows equality at 0.5; recall does not.

`tools/facet_nonllm_length_audit.py` read the existing fixed ten answer records and used the same corpus artifact/string-leaf and citation construction solely to count lengths. It reported:

| Fixed ten-answer quantity | Count |
| --- | ---: |
| Delivered contexts / full reference artifacts | 134 / 508 |
| Contexts with no length-compatible reference for precision | 53 / 134 |
| References with no length-compatible context for recall | 453 / 508 |
| All context-reference pairs ruled out by length alone | 6,411 / 6,793 |
| Fully delivered chunk/reference pairs sharing a credited gold artifact ID, ruled out by length alone | 300 / 300 |

These are **hard upper-bound failures**, not observed Levenshtein scores. They establish that unit length alone prevents many string matches, including every same-ID complete-chunk pair in this run. They do **not** quantify how much of the reported precision 0.0071 or recall 0.0038 gap against Lucene/vector is caused by segmentation. Remaining length-compatible pairs can still fail because of differing text content, JSON formatting, or edit distance. The metric also allows a context to match a different reference artifact, so the 300 same-ID failures do not individually prove 300 metric failures.

The source-ID recall and these string metrics measure different contracts. The bound explains why high source-ID recall can coexist with very low whole-string similarity; it does not explain the answer-correctness deficit. Answer correctness needs its own assessment on the unchanged standard run.

# Fixed facet-correspondence control on the existing smoke

Declared before this control's outcomes. The prior auxiliary-off comparison tested
whether the block contributes. This check tests a different question: does its
intended query/graph facet correspondence outperform one deliberately mismatched
correspondence under the same measurement?

Use only the existing ten saved query interpretations. Reconstruct their cosines
with the same pinned local CPU embedder, offline, and require the saved normalized
embedding hash to match for every query. No Claude/interpreter/generator/judge
calls, new query text, new labels, coefficient search or alternate permutation.
Save numeric matrices privately so this reconstruction need not be repeated.

Three conditions: baseline; query-only permutation [0,2,3,4,1]; and joint query,
graph-facet/reference permutation [0,2,3,4,1] as a relabeling symmetry check.
Topic remains column zero. Coefficients remain (1,.25,.25,.25,.25), scope remains
the saved area, and delivery uses the actual shared 72k helper. The baseline must
reproduce all original score ranks, recruitment and exact context strings/IDs.
The symmetry check must preserve recruitment/delivery and scores within 1e-12.
Stop before gold joining if either control fails; do not adjust tolerances to
obtain a desired result. Retain per-facet witnesses with query-tag text omitted.

Freeze numerical outputs before joining the existing gold pointers. Report paired
source-ID recall, gained/lost links and rank/delivery movement. Query/answer/context
text remains unexported. This is an already observed smoke, not untouched validation.
One mismatch does not estimate a permutation null distribution or establish every
facet's semantics. Infer only the direction and scope supported by the comparison.

If intended correspondence does not help here, report that the earlier on/off gain
does not demonstrate useful named correspondence. Do not adopt the mismatched
version, search permutations, tune weights or repair a missed source. A source-ID
result is not a new RAGAS answer-quality result or proof of answer-bearing content.

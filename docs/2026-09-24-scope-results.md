# Completed graph-grounded scope comparison

All 95 cases completed and all 13,775 deliveries passed independent verification
of seals, source-ID metrics and serialized 72k boundary accounting. The 145
programs produced 40 distinct full-population order signatures. This is effective
behavioral diversity on the pinned population, not 145 different useful outcomes.

Evidence: `output/research/2026-09-23-scope-programs/`, including the sealed plan,
five scope-mask sequences and their 96 policy aliases, complete case outputs,
`independent-verification.json`, and `structural-findings.json`.

No tested scope construction exceeded the earlier 1,890-hit / 51.6586% macro
recall result in these contexts. This does not invalidate the separate ordering
improvement to 1,945 hits, nor prove that scope cannot interact with that ordering.

## Matched scope-input comparison

Hold maximum tag/description matching, mean query evidence, group propagation,
direct/graph intersection, joint recruitment, area-first admission and scope
after traversal fixed:

| Scope input | Total gold-source hits | Macro recall |
| --- | ---: | ---: |
| Frozen scope, `scope_0019` | 1,890 | 51.6586% |
| Graph-name resolver; unrouted bindings veto, empty scope abstains, `scope_0020` | 1,773 | 45.5069% |
| Same, empty scope vetoes, `scope_0021` | 1,773 | 45.5069% |
| Graph-name resolver; unrouted bindings abstain, `scope_0022` | 1,890 | 51.6586% |
| Channel routes only, either empty-scope policy, `scope_0023/0024` | 561 | 15.3888% |

These policies operate on graph-name landings and pointer routes, not corpus
content. With area-first admission, an empty local area still permits the global
lane; identical results for empty-veto and empty-abstain here do not establish that
those semantics are equivalent under area-only admission. All such admissions
and before/after traversal timing were included in the comparison.

The frozen and unrouted-abstention constructions tie on metrics in this context.
Do not infer universal mask or full-order equivalence solely from a metric tie;
the analysis files retain order signatures and explicit aliases separately.

Only Product and some unrouted Company names were present in these captures.
These results do not evaluate Employee-name or Channel-name grounding on questions
that never produced those landings. Shared-entity traversal was tested separately.

Next: combine these scope inputs and their admission/timing alternatives with
the supported ordering/depth constructions. Do not select a per-case scope using
gold. These are development source-ID results, not RAGAS or held-out validation.

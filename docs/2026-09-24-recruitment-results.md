# Completed recruitment-before-traversal comparison

All 95 cases completed. Independent verification passed for all 2,565 deliveries,
input hashes, source-ID metrics and 72k boundary accounting. The 27 programs
produced 18 distinct full-population rankings. Both unchanged parent leaders
reproduced their full-order hashes and deliveries on all 95 cases (190 checks).

No early-recruitment variant exceeded either unchanged leader. The highest-hit
early variant, `feedback_0002` (tied with `feedback_0003`), preserves raw scores
only from first-recruiting facet sponsors on the graph branch. It gets 1,886 hits
and 51.0768% macro recall, compared with its unchanged two-step parent at 1,939
hits and 53.2329%. The unchanged four-step facet leader remains at 1,945 hits.

This is evidence against inserting the tested first-admission filter before
propagation in these contexts. It is not proof that every possible early frontier
or dynamic recruitment method is inferior. The tested alternatives include
first sponsors versus all positive supporters, retained strength versus inverse
admission priority, graph-only versus all-path placement, and both final schedulers.
They do not use gold or character costs to choose the early frontier.

Evidence directory: `output/research/2026-09-24-recruitment-programs/`, including
`engine-parent-parity.json`, `independent-verification.json`, `structural-findings.json`
and complete fixed-program outputs. The live page loads these exact programs and
displays the early recruitment stages and their gold-pointer support afterward.

The broader combined-neighbor and integrated graph/scope comparisons remain
unfinished. These findings inform their final comparison; they do not complete
the overall objective or establish a global optimum.

# Graph composition diagnosis and delivery repair

## Measured exposure changes the priority

A subsequent mechanical scan of the 85 saved successful remaining-90 records
found graph winners in **only 2 of 1,383 fully delivered chunks**. There are three
winning facet paths among those two chunks: one adjacency topic path, one
adjacency concreteness path and one shared-product/channel why path. Every
delivered activity winner and every supported delivered temporal winner is
direct. Across the entire candidate population, graph wins 2,218 of 2,043,400
chunk/facet positions (including unsupported positions in that denominator).

This is exposure to an operator, not a causal ablation: changing non-delivered
candidates could still change ranks. It also excludes scope nomination and
record recovery, which remain separate and substantially active. Nevertheless,
there is little evidence here for spending the next iteration tuning graph
transfer as the main explanation of poor delivered evidence. The topology
redundancy below is real but should not be inflated into that claim.

Reproduction: `tools/facet_saved_route_audit.py` streams the existing 1.44 GB
trace, exports only aggregate route counts and score totals, and hashes its
input. It does not rerank, read gold or expose question/source content. Output:
`output/k=chars/artefact_facet_joint__gold90__cb72000__20260922T090621382244Z/graph_route_diagnosis/route_audit.json`.
The result describes the archived pre-repair run; no new serving-quality claim.

## A construction finding, independent of benchmark scores

The serving arm builds 302 **joint product-and-channel groups**, covering 2,669
of 4,808 chunks. It does not build separate product cliques and channel cliques.
The broad-route hypothesis was checked against this actual construction before
drawing conclusions.

Every one of the 2,375 chat adjacency pairs is inside one of those groups.
Both operators offer the same value from seed s to target c:

`0.5 * direct_support(s) * query_tag_description_match(c)`

The group maximizes over every eligible seed except the target itself. An
adjacent seed is already in that set. Adding its adjacency offer cannot raise
the maximum. This holds for every query tag and every facet, for arbitrary valid
query readings and cosine values. Changing auxiliary weights cannot restore
information discarded by this relation aggregation.

Consequently **local chat adjacency has no additional influence on scores or
ranks in the current arm**. A distant chunk in the same product/channel group
can provide exactly the same kind of support as an adjacent message chunk. A
route label may change on a tie; that is provenance, not scoring influence.

The conclusion is limited to chat adjacency. All 386 document adjacency pairs
and all 26 transcript adjacency pairs add endpoints outside these groups.
Scope landing and record recovery are separate operations and are not proved
redundant by this result.

Reproduction: `tools/facet_graph_composition_audit.py` loads the actual pinned
prepared topology, verifies endpoint containment, and checks the actual scoring
primitive with deterministic synthetic inputs over the full topology. Removing
only the covered links leaves direct scores, graph scores, total scores and
ranks bit-for-bit equal. Counts, code hashes and the algebraic argument are in
`output/research/2026-09-22-graph-composition/audit.json`. No benchmark questions,
answers, gold or model calls are involved.

## Consequence for the next design decision

The observed exposure above takes priority over this initially proposed focus:
do not rebuild graph transfer merely because a defect is easy to demonstrate.
Direct query-tag/description composition and scope admission govern almost all
of the saved delivered winners and remain the primary construction targets.

This disproves the assumption that merely providing both relation types lets
local conversation shape help independently. It does not prove that removing
the group route improves retrieval, or that adjacency should always win.

The next construction must explicitly distinguish **area access** from
**evidence transferred between chunks**. If channel membership supplies access,
its job is to make candidates available; if it supplies evidence, the meaning of
transferring a distant seed's facet reading must be justified. An arbitrary
larger adjacency coefficient would hide this unresolved distinction rather than
answer it. This finding motivates that architecture decision before any new
coefficient sweep or benchmark run.

Likewise, preserving distinct query needs must not become a count of matching
query tags. The recorded user contract rejects that count as evidence of fit.
Any eventual coverage rule concerns complementary evidence in the selected set,
and would need an explicit interpretation of needs rather than treating every
generated tag as an equally important requirement.

## Bounded delivery repair completed

An independent executable counterexample used two touching chunks of one
record: an eight-character supporting chunk with positive nomination and an
eight-character sibling with zero nomination. At an eight-character serving
budget, the old code could deliver only the sibling. Swapping their IDs changed
which text was delivered, with every meaningful input held constant.

`facet_recruitment_candidate.py` now orders original nominations before context
advanced by recovery **within each unchanged frontier**. Recovered metadata rows
use the same order. Nomination scores, depths, structural scope, recovery
membership and the complete-frontier research budget are unchanged. The actual
serialized serving prefix can change, intentionally.

This does not make records atomic, guarantee every sponsor fits, eliminate ties
between original nominations, or establish a large recall improvement. It fixes
the specific reversal of evidence and its supplementary context. Old benchmark
results belong to the old order and have not been relabelled as new results.

The adapter replay test now checks exact saved score arrays and exact per-chunk
metadata, frontier membership/costs and original nominations, while separately
requiring sponsor-first order. It no longer requires equality to the known-bad
archived ID ordering. The synthetic regression uses the actual harness character
cut for both ID assignments.

Validation: 39 tests pass across recruitment, scope recruitment, prepared-query
pipeline and serving adapter. No new benchmark quality or answer-generation
measurement was performed.

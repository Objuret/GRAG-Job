# Structural landing path restored in the facet arm

The runnable `artefact_facet_joint` arm now connects structural names to actual
captured graph routes. Previously the querytagger removed these names from
semantic tags while the arm only supplied a single Product-name lookup. This
repair implements the omitted person/channel path and combinations without
changing facet scores, embeddings, query prompts or the 72,000-character budget.

## Captured graph evidence

`tools/facet_structural_snapshot.py` made one read-only capture against
`herb-eval-volmax`, resolving structural names through File pointers into local
corpus JSON. It did not read benchmark questions/gold, invoke models, write to
the database, or reuse the legacy name cache.

The live eligible population exactly matches the original 4,808 chunks. All
7,485 Product/Channel memberships match the original frozen snapshot. The new
supplement contains 992 nodes and 1,642 name entries (561 distinct lexical names),
with 222,080 node-route-chunk endpoints and hashes for 32 name-source files.
These additional Employee routes are a later capture, not a claim about the
historical Employee graph at the time of the original snapshot. The timestamp,
matching checks and that limitation propagate into retrieval metadata.

Artifact: `output/research/2026-09-22-structural-landings/structural_snapshot.json`

SHA256: `9c9e9ff8415002cdc6203ecfdc29ef6a933d9eaf8859e3d1cf8d6678037f33ce`

## Current behavior

- Match exact whole structural names using consistent Unicode casefold, retaining
  original text spans. Unknown capitalized words are not guessed to be names.
- Suppress a short alias only where it occurs inside a longer matched name.
  A separate occurrence of that short name remains an independent mention.
- Union the actual graph nodes bound by one lexical name, including names shared
  across labels. No node is selected because it gives favorable retrieval.
- Intersect the reachable chunk sets of distinct names. Person plus product plus
  channel therefore combines their graph areas rather than dropping all but product.
- Record no landing, an unreachable landing, a disjoint intersection, and resolved
  names with multiple node bindings separately. An empty area supplies no additional
  nomination stream; it does not exclude any globally eligible chunks.
- Keep provenance for the name bindings and their actual route memberships. The
  arm validates the supplement's hash, graph hash and eligible chunk universe
  before query/model work.

The default routes are Employee-to-Channel-to-Chunk,
Employee-to-Product-to-Chunk through document/meeting relations, Channel-to-Chunk
and Product-to-Chunk. All endpoints are in the pinned eligible population.
130 Customer/Company nodes have no enabled route definition, and 18 additional
nodes have no eligible endpoint. They remain observable as unresolved structural
support. No relationship is invented to make them reach a chunk. A separate
read-only topology check records their actual Company/Customer/File/Role edges;
it does not reinterpret shared roles as evidence of relevant content.

## Verification

22 focused tests pass across `test_facet_structural_landing.py` and
`test_artefact_facet_joint.py`. They cover multi-node aliases, nested/separate name
occurrences, cross-kind lexical ambiguity, empty/unreachable states, global access,
graph/hash mismatches, Unicode expansions, and the arm's actual call to the resolver.
The existing frozen development replay retains exactly the same facet scores and
original product-only nomination result. It is restoration evidence, not another
quality benchmark.

An independent reviewer round-tripped all 561 unique names against the actual
pinned capture, comparing each isolated literal with the expected union of its
nodes: zero mismatches (322 resolved, 110 resolved with multiple nodes, 129
unreachable). No model or benchmark calls were made for this check.

Original arm and adapter test files are retained under the supplement's
`pre-repair/` directory. Earlier gold metrics describe that earlier arm, not this
repaired one. No retrieval-quality improvement is claimed from these tests.

## Still unresolved

The global/area scheduler remains the prior equal-depth convention. Connecting
the missing path does not justify that scheduling rule or solve the measured
allocation problem. Its decision must be examined next without coefficient
tuning or another broad benchmark repetition.

Intersecting distinct names is not a natural-language Boolean interpreter. Two
disjoint product names in a comparison currently yield a recorded empty
intersection and global fallback. First-name matches remain ambiguous lexical
evidence, not verified identity. No arbitrary fuzzy-match threshold was added.
Facet semantic validity, including the restrictive activity gloss, is likewise
not established by this structural repair.

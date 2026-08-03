---
name: design-hard-fields-before-tagging
description: Core HERB design intent — hard structured fields must be materialized as queryable Chunk properties BEFORE tagging
metadata: 
  node_type: memory
  type: project
  originSessionId: e7d7149c-2a8b-4996-aee6-024506f64358
---

The user's intended HERB architecture: structured "hard" fields extracted from
source records (product, section, channel, employee_id, dates, ids, etc.) must
be **materialized as first-class, indexed, queryable `:Chunk` properties as a
stage that runs BEFORE tagging** — so retrieval can hard-gate on them
deterministically before any tag/embedding step.

This is a deliberate design choice the user owns and did not abandon. The
current shipped graph does NOT do this: hard fields sit only inside
`Chunk.content` (verbatim blob) and `Chunk.locator_json` (provenance string),
neither of which is searchable. Consequence: a prompt about a literal that was
never tagged (e.g. a year like "1940") cannot retrieve the chunk that contains
it — recall is capped by tagger coverage, not corpus content.

The Non-Contamination Rule ([[noncontamination-rework-unapproved]]) is NOT a
valid reason against this: keeping field names out of the *tagging model
prompt* and materializing fields as *queryable Chunk properties* are
independent goals. Both can hold at once. Restoring the user's design = add a
pre-tagging field-materialization stage + indexed Chunk props + a structured
hard-gate in retrieval/interpreter, while leaving Non-Contamination on the
tagger input intact.

Related: [[no-silent-fallbacks]] — the hard gate must fail loud when a prompt
constraint names a field/value absent from the corpus enum, not silently scan
everything.

## CONFIRMED as the carrier (2026-06-12)
The v2 graph-spine decision ([[v2-graph-spine]]) lands exactly here: hard fields are
**indexed chunk attributes** — not entity nodes, not edges. The materialization stance
holds; which fields matter is decided by the probe's classing + the mapping key.

## SUPERSEDED on the retrieval-gate point (2026-06-01)
The "structured hard-gate in retrieval/interpreter" above is **superseded**: in
RETRIEVAL, hard fields participate as soft **boosts**, never gates — see
[[retriever-routing-model]]. The materialization stance (lift hard fields to
queryable structure BEFORE tagging) is UNCHANGED and load-bearing; only the
retrieval-time *use* changed from gate→boost. True exact-match (a gate) lives on
the separate **structured-query / aggregation path**, not on retrieval ranking.

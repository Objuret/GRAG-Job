# Plans — Next Steps

> **State (2026-05-18):** the stack below is **code in the working tree,
> uncommitted**. Its graph prerequisites (`materialize`, `embed-tags`) are
> **verified done on the live `herb` graph** (5843 chunks gated, 25,896 `:Tag`
> embedded, all indexes ONLINE — see [`status.md`](status.md)). The
> `pilot_format_smoke/run.json` ledger is stale; trust the graph.

## Coded, graph layer verified on `herb`

1. Browser-direct Neo4j read (`neo4j-driver`) — [`services/neo4j.ts`](../../frontend/src/services/neo4j.ts).
2. Browser-direct two-pass Anthropic interpretation — [`services/interpreter.ts`](../../frontend/src/services/interpreter.ts).
3. Retrieval scoring in Cypher (weighted overlap) — [`services/retrieval.ts`](../../frontend/src/services/retrieval.ts), grounded by [`services/embeddings.ts`](../../frontend/src/services/embeddings.ts). Grounding mandatory; no exact-name fallback.
4. Answer call per `answer_job` — [`services/answer.ts`](../../frontend/src/services/answer.ts).
5. Replace demo state — live calls drive the lanes.
6. Field-name pass — HERB names (`facet`, `w_chunk`, `w_facet`, `relevance_to_file`) throughout.
7. Hard-gate + lexical recall — Pass-1 `gate` in [`services/interpreter.ts`](../../frontend/src/services/interpreter.ts); deterministic pre-tag gate on materialized `:Chunk` fields, fail-loud validation, gated `chunk_fulltext` lexical path in [`services/retrieval.ts`](../../frontend/src/services/retrieval.ts); backend `python -m tagging materialize` (see [`../graph_schema.md`](../graph_schema.md)). Hard fields + `chunk_fulltext` confirmed present on `herb`.

## Required to call this shippable

- **Commit the feature.** Currently working-tree only — one disruption and it is gone.
- **Resolve `frontend/public/models/` tracking.** Untracked and not gitignored; with `allowRemoteModels=false` a fresh checkout has no model and grounding hard-fails. Commit the quantized ONNX, or gitignore + document a fetch step.
- **Click through the browser prompt → answer loop on `herb`** and record the actual result in [`status.md`](status.md) (only the graph data layer was verified, not a full UI run).

## Known quality issues (acknowledged, not fixed)

- **`min_sim` is near-meaningless.** e5-small cosine on this corpus is compressed (~0.8 mean to random tags); default floor 0.78 barely filters noise — grounding leans entirely on top-k.
- **Lexical/tag union truncation.** Year-gate lexical hits are appended after tag hits then `.slice(0, limit)`. If tag hits fill `limit`, the literal-recall chunks the path exists to add are dropped — silently defeating the feature for limit-bound queries.

## Optional

- **Persistence.** Save canvas/module state to `localStorage`, or skip — the app is local-only.

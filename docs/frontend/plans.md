# Plans — Next Steps

1. **Browser-direct Neo4j read.** Add `neo4j-driver` to `package.json`. Wire `App.jsx` to read datasets, files, chunks, and tag summaries from the local Neo4j (read-only user). Use the field names in [`../graph_schema.md`](../graph_schema.md): `facet`, `w_chunk`, `w_facet`, `relevance_to_file`.
2. **Browser-direct Anthropic interpretation.** Add `@anthropic-ai/sdk` with `dangerouslyAllowBrowser: true`. Implement the two-pass prompt interpretation method (Pass 1 → flat tags, Pass 2 → 5-facet scoring, code derives `w_query`). Spec: [`query_interpretation_layer.md`](query_interpretation_layer.md).
3. **Retrieval scoring in Cypher.** Translate the deterministic weighted-overlap formula into a Cypher query the browser issues. Surface the query plan in the UI beside the retrieved chunks.
4. **Answer call.** Third Anthropic call: retrieved chunks + plan → answer per `answer_job.mode`, defaults `evidence_policy=retrieved_only`, `missing_evidence_policy=say_insufficient_evidence`.
5. **Replace demo state.** Once live calls return, trim `PRESET_RESULTS` / `SAMPLE_CHUNKS` from `workbenchData.ts` — keep only node-registry/UI metadata.
6. **Field-name pass.** Drop legacy `cluster`, `canonicalId`, `weightLocal` from `types/index.ts` and `workbenchData.ts` in favour of the HERB names.
7. **Persistence.** Save canvas/module state to `localStorage` (or skip — it's local-only).

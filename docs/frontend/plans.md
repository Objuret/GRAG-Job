# Plans - Next Steps

> **State (2026-05-19):** the workbench stack is implemented and targets the
> eval-safe `herb-eval` graph by default for thesis RAG scoring. The full
> `herb` graph remains available for exploration but contains QA/oracle
> sections.

## Coded, graph layer verified on `herb-eval`

1. Browser-direct Neo4j read (`neo4j-driver`) - [`services/neo4j.ts`](../../frontend/src/services/neo4j.ts).
2. Browser-direct two-pass Anthropic interpretation - [`services/interpreter.ts`](../../frontend/src/services/interpreter.ts).
3. Retrieval scoring in Cypher (weighted overlap) - [`services/retrieval.ts`](../../frontend/src/services/retrieval.ts), grounded by [`services/embeddings.ts`](../../frontend/src/services/embeddings.ts). Grounding mandatory; no exact-name fallback.
4. Answer call per `answer_job` - [`services/answer.ts`](../../frontend/src/services/answer.ts).
5. Live Usage canvas execution - `services/pipeline.ts` runs the wired DAG.
6. Field-name pass - HERB names (`facet`, `w_chunk`, `w_facet`, `relevance_to_file`) throughout.
7. Hard-gate + lexical recall - Pass-1 `gate`, deterministic pre-tag gate, fail-loud validation, gated `chunk_fulltext` lexical path, and zero-result lexical fallback.
8. Retrieval lane input contract - `RetrievalInput = plan + graph scope + lane controls + hard gate`, consumed by semantic and enriched-baseline retrieval.
9. RAG-eval leakage guard - semantic, enriched baseline, lexical, and default Query-module retrieval exclude `answerable_questions`, `unanswerable_questions`, and `product_profile`; custom Query modules are post-checked.
10. Result console - resizable Comparison / Logs / History tabs, chunk filtering/detail, copy actions, history restore, and copyable full-error popover.
11. Headless RAGAS harness - `frontend/scripts/ragas-export.ts` runs graph, direct-content baseline, or SQL-agent batches and writes JSONL with `reference` + `meta`; `backend/baselines/sql_agent.py` is the SQL baseline; `backend/evaluation/build_gold_set.py` builds HERB gold sets; `backend/evaluation/ragas_eval.py` scores faithfulness plus reference metrics. Graph and SQL exports share ceiling defaults (0 = no count cap).
12. Run Builder - interactive N-run comparison: a `RunSpec` per run captures every node lever + per-run database + route (`tags`/`baseline`/`content`/`module`/`sql_agent`); **Run all** on one shared prompt, side-by-side answers/metrics + pairwise chunk overlap, per-run History and RAGAS export (`pipeline.ts:runRunSpec`/`compareRuns`). SQL route is export-only. The interactive counterpart to the headless harness; the A/B `runUsageGraph` path is unchanged.

## Required to call this shippable

- Click through the browser prompt -> answer loop on `herb-eval` and record the actual result in [`status.md`](status.md).
- Run the thesis eval harness end to end against `herb-eval` after creating/verifying `chunk_content_ft`, then record graph-vs-baseline RAGAS results and command lines.

## Known quality issues

- `min_sim` is near-meaningless. e5-small cosine on this corpus is compressed, so grounding leans heavily on top-k.
- Deterministic answer/citation metrics are still missing. RAGAS covers judge metrics; exact ID/link/entity F1, citation hit@k, and refusal accuracy still need a small local scorer.

## Optional

- Persistence. Save canvas/module state to `localStorage`, or skip - the app is local-only.

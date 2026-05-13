# Status

**TL;DR.** On 2026-05-07 the configured Neo4j database (`bonnier`) was dropped/recreated, schema bootstrap was re-run, and preflight completed cleanly against the current `data/raw/` tree. A post-cap file-scoped LLM smoke was run against `Salesforce__HERB/products/ActionGenie.json`; after renaming ambiguous `propose` semantics to `canonical_missing`, all 10 chunk extractions and the file orchestration completed.

**When to read this.** Before promising a feature is "done". Before estimating remaining work. After every significant code change, update this doc.

**Last updated:** 2026-05-13.

## Touched paths

This doc references everything; updates affect `docs/status.md` only.

## What is verified working

| Item | Evidence |
|---|---|
| Fresh DB reset + schema bootstrap | On 2026-05-07 the configured database `bonnier` was dropped/recreated via the `system` database, then [`scripts/bootstrap_schema.py`](../scripts/bootstrap_schema.py) reported `Applied 18 schema statements; merged 32 canonical tags.` |
| Fresh preflight against current raw data | [`scripts/run_preflight.py`](../scripts/run_preflight.py) reported `files_seen=44`, `files_new=44`, `skipped_no_chunks=3`, `chunks_created=157681`, `work_items_seeded=157722`, `failures=0`. The 3 skipped files are chunkless payloads such as images/archive. |
| Global chunk content cap | Current graph verification reported `max(size(c.content))=6029`, `max(c.token_estimate)=1507`, `p95(size(c.content))=4549`, `p95(c.token_estimate)=1137`. JSON, JSONL, and parquet are now bounded; the prior FEVEROUS JSONL chunks up to ~98k chars are gone from the current graph. |
| Parquet preflight for DocVQA | [`indexing/chunker.py`](../indexing/chunker.py) now omits parquet columns whose Arrow type contains binary data, for example image bytes, and chunks the remaining textual columns. This fixed the prior `ArrowNotImplementedError` / `MemoryError` on `VLR-CVC__DocVQA-2026/test.parquet` and `val.parquet` in the fresh preflight. |
| Post-cap file-scoped LLM smoke | Initial run `2026-05-07T13-26-16Z-9598ed` completed file orchestration but had 2 schema-invalid chunks because `propose` was semantically ambiguous. After changing the prompt/schema to `canonical_missing`, retry run `2026-05-07T13-52-46Z-7ec1b8` processed the 2 failed chunks and reran file orchestration with `chunks_done=2`, `chunks_failed=0`, `files_done=1`, `files_failed=0`. The target file now has 10/10 chunk WorkItems done, 1/1 file WorkItem done, 62 `HAS_TAG` edges, 56 `TAGGED` edges, and relevance for all 10 chunks. Details are in [`.plan/post_cap_smoke_2026-05-07.md`](../.plan/post_cap_smoke_2026-05-07.md). |
| Missing-canonical proposal path | The retry created two `:CanonicalTagProposal` nodes: `employee_role_in_review` and `user_education`, both in `information_need`. This verifies the `canonical_missing=true` path. |
| Pydantic schema enforcement at the agent boundary | [`agents/client.AgentClient.call`](../agents/client.py) validates model output via `schema.model_validate_json` and produces `error_class="schema_invalid"` on failure. Covered by validators in [`agents/schemas.py`](../agents/schemas.py). |
| Idempotency rules | [`Chunker.chunk_file`](../indexing/chunker.py) skips files that already have chunks; preflight upserts `:Source` and `:File` with `MERGE`; bootstrap uses `IF NOT EXISTS` everywhere. |
| Query layer smoke | [`clustering/query.py`](../clustering/query.py) imports cleanly; `python -m clustering.query --help` works. Named query files live under [`clustering/queries/`](../clustering/queries/). |
| RAGAS harness smoke | [`evaluation/ragas_eval.py`](../evaluation/ragas_eval.py) compiles; `python -m evaluation.ragas_eval --help` works; [`evaluation/sample_queries.yaml`](../evaluation/sample_queries.yaml) loads 10 query definitions. |

## What is built but not yet end-to-end verified

- **Full end-to-end run.** The full corpus has 157681 chunk WorkItems. A complete LLM run has not been attempted after the fresh reset because that would issue a large number of model calls.

## Known gaps

- **Parquet visual-content omission.** [`Chunker._chunk_parquet`](../indexing/chunker.py) now omits Arrow columns that contain binary data, so image bytes are not embedded in `Chunk.content`. This is intentional for prompt/memory safety, but queries over visual content will need a future image-aware path.
- **Non-binary nested parquet rows.** The chunker now caps string length, list length, and recursion depth during JSON conversion. This prevents the observed DocVQA failures, but future parquet schemas may still need schema-specific flattening for better retrieval quality.
- **`exports/`.** Not built. No JSON snapshots are produced anywhere in the live pipeline.
- **`provenance.json`.** No per-run provenance dump is written today. `:Run` properties cover the basics, but a structured provenance file is not.
- **Vector indexes / embeddings.** [`schema/vector_indexes.cypher`](../schema/vector_indexes.cypher) is intentionally empty. `EMBEDDING_MODEL` env var is loaded into `Settings.embedding_model` but consumed nowhere.

## Decisions to revisit later

- **Agent-negotiated chunking for sequential files.** Today every file is chunked deterministically. For long-form text, the orchestrator passes a continuity hint, but true agent-negotiated chunk boundaries are deferred.
- **Vector indexes and embeddings.** Likely useful once the canonical vocabulary and query workload are stable.
- **Cascade classifier.** Today extraction and canonical mapping happen in one agent call. If schema-invalid rates or canonical mapping quality become a problem, revisit a separate classification prompt.
- **Sequential dispatch for long-form files.** Today `dispatch_mode='sequential'` changes prompt content, not call ordering.
- **Full corpus LLM cost.** A full run means one model call per chunk plus one per chunk-bearing file. Confirm budget/concurrency before launching.

## Last verified action

2026-05-07: after adding the JSONL content cap, dropped/recreated `bonnier`, ran bootstrap, ran preflight with zero failures, then ran and retried one post-cap file-scoped smoke. Current graph has 10 done chunk WorkItems, 157671 unrun chunk WorkItems, 1 done file WorkItem, 40 unrun file WorkItems, 0 failed WorkItems, 62 `HAS_TAG` edges, and 56 `TAGGED` edges.

## Next recommended step

1. Launch a broader but still bounded LLM batch with conservative concurrency and cost monitoring.
2. Watch `schema_invalid`, `http_429`, and `timeout` rates during that batch.
3. Use `python -m clustering.review` after enough `:CanonicalTagProposal` examples exist to review meaningfully.
4. Run `python -m evaluation.ragas_eval --dry-run` once Stage 1 extraction has produced chunk descriptions, then run a narrow RAGAS sample before a full evaluation.

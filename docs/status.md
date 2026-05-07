# Status

**TL;DR.** On 2026-05-07 the configured Neo4j database (`bonnier`) was dropped/recreated, schema bootstrap was re-run, and preflight completed cleanly against the current `data/raw/` tree. A post-cap file-scoped LLM smoke was then run against `Salesforce__HERB/products/ActionGenie.json`; file orchestration completed, but 2 of 10 chunk extractions failed schema validation.

**When to read this.** Before promising a feature is "done". Before estimating remaining work. After every significant code change, update this doc.

**Last updated:** 2026-05-07.

## Touched paths

This doc references everything; updates affect `docs/status.md` only.

## What is verified working

| Item | Evidence |
|---|---|
| Fresh DB reset + schema bootstrap | On 2026-05-07 the configured database `bonnier` was dropped/recreated via the `system` database, then [`scripts/bootstrap_schema.py`](../scripts/bootstrap_schema.py) reported `Applied 18 schema statements; merged 32 canonical tags.` |
| Fresh preflight against current raw data | [`scripts/run_preflight.py`](../scripts/run_preflight.py) reported `files_seen=44`, `files_new=44`, `skipped_no_chunks=3`, `chunks_created=157681`, `work_items_seeded=157722`, `failures=0`. The 3 skipped files are chunkless payloads such as images/archive. |
| Global chunk content cap | Current graph verification reported `max(size(c.content))=6029`, `max(c.token_estimate)=1507`, `p95(size(c.content))=4549`, `p95(c.token_estimate)=1137`. JSON, JSONL, and parquet are now bounded; the prior FEVEROUS JSONL chunks up to ~98k chars are gone from the current graph. |
| Parquet preflight for DocVQA | [`indexing/chunker.py`](../indexing/chunker.py) now omits parquet columns whose Arrow type contains binary data, for example image bytes, and chunks the remaining textual columns. This fixed the prior `ArrowNotImplementedError` / `MemoryError` on `VLR-CVC__DocVQA-2026/test.parquet` and `val.parquet` in the fresh preflight. |
| Post-cap file-scoped LLM smoke | `python scripts/run_index.py --file-id 960f223de786daa74a7d0f70 --chunk-limit 10 --file-limit 1 --concurrency 2` ran on the capped graph. Run `2026-05-07T13-26-16Z-9598ed` finished `ok`: `chunks_done=8`, `chunks_failed=2`, `files_done=1`, `files_failed=0`, tokens `20225/3519`, rollup wrote 48 `TAGGED` edges. Details are in [`.plan/post_cap_smoke_2026-05-07.md`](../.plan/post_cap_smoke_2026-05-07.md). |
| Pydantic schema enforcement at the agent boundary | [`agents/client.AgentClient.call`](../agents/client.py) validates model output via `schema.model_validate_json` and produces `error_class="schema_invalid"` on failure. Covered by validators in [`agents/schemas.py`](../agents/schemas.py). |
| Idempotency rules | [`Chunker.chunk_file`](../indexing/chunker.py) skips files that already have chunks; preflight upserts `:Source` and `:File` with `MERGE`; bootstrap uses `IF NOT EXISTS` everywhere. |

## What is built but not yet end-to-end verified

- **Schema-invalid proposal pattern.** The post-cap smoke still produced 2 `schema_invalid` chunk failures where the model emitted `propose=true` with a non-null `canonical`. This must be fixed or explicitly handled before a broader run.
- **Full end-to-end run.** The full corpus has 157681 chunk WorkItems. A complete LLM run has not been attempted after the fresh reset because that would issue a large number of model calls.
- **Proposal path.** The smoke runs did not deliberately exercise a valid `propose=true` result. The prompt was tightened after repeated invalid `propose=true` + non-null `canonical` outputs.

## Known gaps

- **Parquet visual-content omission.** [`Chunker._chunk_parquet`](../indexing/chunker.py) now omits Arrow columns that contain binary data, so image bytes are not embedded in `Chunk.content`. This is intentional for prompt/memory safety, but queries over visual content will need a future image-aware path.
- **Non-binary nested parquet rows.** The chunker now caps string length, list length, and recursion depth during JSON conversion. This prevents the observed DocVQA failures, but future parquet schemas may still need schema-specific flattening for better retrieval quality.
- **Proposal triage CLI.** [`clustering/canonical_seed.yaml`](../clustering/canonical_seed.yaml) refers to `python -m clustering.review` as the entry point for promoting `:CanonicalTagProposal` nodes into the seed. No such module exists in the repo.
- **`clustering/queries/*.cypher`.** Not built. Planned named views are `by_theme`, `by_information_need`, `recent_active`, `multidim`.
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

2026-05-07: after adding the JSONL content cap, dropped/recreated `bonnier`, ran bootstrap, ran preflight with zero failures, then ran one post-cap file-scoped smoke. Current graph has 8 done chunk WorkItems, 2 failed chunk WorkItems, 157671 unrun chunk WorkItems, 1 done file WorkItem, 40 unrun file WorkItems, 48 `HAS_TAG` edges, and 48 `TAGGED` edges.

## Next recommended step

1. Decide how to handle the invalid `propose=true` + non-null `canonical` pattern.
2. Retry the 2 failed ActionGenie chunk WorkItems and, if they pass, reset/rerun that file orchestration item so relevance covers all non-empty chunks.
3. Only then launch a broader LLM batch with conservative concurrency and cost monitoring.

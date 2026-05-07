# Status

**TL;DR.** On 2026-05-07 the configured Neo4j database (`bonnier`) was dropped/recreated, schema bootstrap was re-run, and preflight completed cleanly against the current `data/raw/` tree. The current graph is preflight-only after applying the global chunk content cap across JSON, JSONL, and parquet; no LLM indexing has been run after this final reset.

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
| File-scoped dispatcher smoke code path | `run_index.py --file-id ...` was added and tested before the final JSONL-cap reset. Those smoke results were intentionally wiped by the final reset, so the current graph has `Run=0`, `HAS_TAG=0`, and `TAGGED=0`. |
| Pydantic schema enforcement at the agent boundary | [`agents/client.AgentClient.call`](../agents/client.py) validates model output via `schema.model_validate_json` and produces `error_class="schema_invalid"` on failure. Covered by validators in [`agents/schemas.py`](../agents/schemas.py). |
| Idempotency rules | [`Chunker.chunk_file`](../indexing/chunker.py) skips files that already have chunks; preflight upserts `:Source` and `:File` with `MERGE`; bootstrap uses `IF NOT EXISTS` everywhere. |

## What is built but not yet end-to-end verified

- **Post-cap LLM smoke.** The file-scoped smoke worked before the final JSONL-cap reset, but has not been re-run against the current capped graph.
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

2026-05-07: after adding the JSONL content cap, dropped/recreated `bonnier`, ran bootstrap, and ran preflight with zero failures. Final verification showed 157681 chunks, 157681 unrun chunk WorkItems, 41 unrun file WorkItems, no runs, and max chunk content of 6029 chars / 1507 estimated tokens.

## Next recommended step

1. Re-run one targeted post-cap LLM smoke with `run_index.py --file-id ... --chunk-limit 10 --file-limit 1 --concurrency 2`.
2. If green, launch a broader LLM batch with conservative concurrency and cost monitoring.
3. Watch `schema_invalid`, `http_429`, and `timeout` rates during the next batch; the breaker should abort if they become systemic.

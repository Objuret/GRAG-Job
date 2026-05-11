# Status

**TL;DR.** On 2026-05-07 the configured Neo4j database (`bonnier`) was dropped/recreated, schema bootstrap was re-run, and preflight completed cleanly against the current `data/raw/` tree. On 2026-05-11 the cluster dimensions were renamed to `topic`, `entities`, `activity`, `temporal`, `evidence` in code/docs and in the configured Neo4j database.

**When to read this.** Before promising a feature is "done". Before estimating remaining work. After every significant code change, update this doc.

**Last updated:** 2026-05-11.

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
| Missing-canonical proposal path | The retry created two `:CanonicalTagProposal` nodes: `employee_role_in_review` and `user_education`, both in `evidence`. This verifies the `canonical_missing=true` path. |
| Cluster dimension rename contract | On 2026-05-11 the live cluster strings were renamed to `topic`, `entities`, `activity`, `temporal`, `evidence` across schema, prompts, canonical seed, backend order, frontend types, docs, the configured Neo4j database, and `graph_export/grag_graph_latest.zip`. The DB migration updated 62 `HAS_TAG` edges, 56 `TAGGED` edges, 32 `CanonicalTag` nodes, and 2 `CanonicalTagProposal` nodes. Verified with `python -m compileall agents indexing scripts`, a stdlib contract check that `Cluster == CLUSTER_ORDER == canonical_seed keys`, `npm run build`, `npm run lint`, bootstrap seeding, Neo4j readback showing zero retired cluster strings, and export-zip readback showing zero retired `properties.cluster` values. |
| Pydantic schema enforcement at the agent boundary | [`agents/client.AgentClient.call`](../agents/client.py) validates model output via `schema.model_validate_json` and produces `error_class="schema_invalid"` on failure. Covered by validators in [`agents/schemas.py`](../agents/schemas.py). |
| Idempotency rules | [`Chunker.chunk_file`](../indexing/chunker.py) skips files that already have chunks; preflight upserts `:Source` and `:File` with `MERGE`; bootstrap uses `IF NOT EXISTS` everywhere. |

## What is built but not yet end-to-end verified

- **Full end-to-end run.** The full corpus has 157681 chunk WorkItems. A complete LLM run has not been attempted after the fresh reset because that would issue a large number of model calls.

## Known gaps

- **Parquet visual-content omission.** [`Chunker._chunk_parquet`](../indexing/chunker.py) now omits Arrow columns that contain binary data, so image bytes are not embedded in `Chunk.content`. This is intentional for prompt/memory safety, but queries over visual content will need a future image-aware path.
- **Non-binary nested parquet rows.** The chunker now caps string length, list length, and recursion depth during JSON conversion. This prevents the observed DocVQA failures, but future parquet schemas may still need schema-specific flattening for better retrieval quality.
- **Proposal triage CLI.** [`clustering/canonical_seed.yaml`](../clustering/canonical_seed.yaml) refers to `python -m clustering.review` as the entry point for promoting `:CanonicalTagProposal` nodes into the seed. No such module exists in the repo.
- **`clustering/queries/*.cypher`.** Not built. Planned named views are `by_topic`, `by_evidence`, `recent_active`, `multidim`.
- **`exports/`.** Not built. No JSON snapshots are produced anywhere in the live pipeline.
- **`provenance.json`.** No per-run provenance dump is written today. `:Run` properties cover the basics, but a structured provenance file is not.
- **Vector indexes / embeddings.** [`schema/vector_indexes.cypher`](../schema/vector_indexes.cypher) is intentionally empty. `EMBEDDING_MODEL` env var is loaded into `Settings.embedding_model` but consumed nowhere.
- **Existing graph compatibility after cluster rename.** The configured Neo4j database was migrated on 2026-05-11. Other databases or exported snapshots written before this date may still contain retired cluster strings on `HAS_TAG`, `TAGGED`, `CanonicalTag`, or `CanonicalTagProposal`; rebuild or migrate them before use.

## Decisions to revisit later

- **Agent-negotiated chunking for sequential files.** Today every file is chunked deterministically. For long-form text, the orchestrator passes a continuity hint, but true agent-negotiated chunk boundaries are deferred.
- **Vector indexes and embeddings.** Likely useful once the canonical vocabulary and query workload are stable.
- **Cascade classifier.** Today extraction and canonical mapping happen in one agent call. If schema-invalid rates or canonical mapping quality become a problem, revisit a separate classification prompt.
- **Sequential dispatch for long-form files.** Today `dispatch_mode='sequential'` changes prompt content, not call ordering.
- **Full corpus LLM cost.** A full run means one model call per chunk plus one per chunk-bearing file. Confirm budget/concurrency before launching.

## Last verified action

2026-05-11: renamed the cluster dimension keys in code/docs, migrated the configured Neo4j database, re-exported `graph_export/latest/`, and rebuilt `graph_export/grag_graph_latest.zip`. Readback after bootstrap showed `old_cluster_relationships=0` and `old_cluster_nodes=0`; export readback showed no retired `properties.cluster` values.

## Next recommended step

1. Launch a broader but still bounded LLM batch with conservative concurrency and cost monitoring.
2. Watch `schema_invalid`, `http_429`, and `timeout` rates during that batch.
3. Start proposal triage only after enough `:CanonicalTagProposal` examples exist to review meaningfully.

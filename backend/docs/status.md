# Status

**TL;DR.** HERB is currently verified as a preflight/chunking graph only. The `herb` database contains the fresh `Salesforce__HERB` `:Source`, `:File`, and `:Chunk` artefacts, and the old generic extraction/tagging path is blocked for HERB unless explicitly overridden.

**When to read this.** Before promising a feature is "done". Before estimating remaining work. After every significant code change, update this doc.

**Last updated:** 2026-05-13.

## Touched paths

This doc references everything; updates affect `docs/status.md` only.

## What is verified working

| Item | Evidence |
|---|---|
| Fresh DB reset + schema bootstrap | [`scripts/bootstrap_schema.py`](../scripts/bootstrap_schema.py) now applies schema only; it no longer seeds canonical tag nodes. |
| Fresh preflight against current raw data | [`scripts/run_preflight.py`](../scripts/run_preflight.py) reported `files_seen=44`, `files_new=44`, `skipped_no_chunks=3`, `chunks_created=157681`, `working_items_seeded=157722`, `failures=0` at the time. Current code writes those scheduler items to `backend/.work/`, not to graph nodes. The 3 skipped files are chunkless payloads such as images/archive. |
| Global chunk content cap | Current graph verification reported `max(size(c.content))=6029`, `max(c.token_estimate)=1507`, `p95(size(c.content))=4549`, `p95(c.token_estimate)=1137`. JSON, JSONL, and parquet are now bounded; the prior FEVEROUS JSONL chunks up to ~98k chars are gone from the current graph. |
| Parquet preflight for DocVQA | [`indexing/chunker.py`](../indexing/chunker.py) now omits parquet columns whose Arrow type contains binary data, for example image bytes, and chunks the remaining textual columns. This fixed the prior `ArrowNotImplementedError` / `MemoryError` on `VLR-CVC__DocVQA-2026/test.parquet` and `val.parquet` in the fresh preflight. |
| Post-cap file-scoped LLM smoke | Initial run `2026-05-07T13-26-16Z-9598ed` completed file orchestration but had 2 schema-invalid chunks because `propose` was semantically ambiguous. After changing the prompt/schema to `canonical_missing`, retry run `2026-05-07T13-52-46Z-7ec1b8` processed the 2 failed chunks and reran file orchestration with `chunks_done=2`, `chunks_failed=0`, `files_done=1`, `files_failed=0`. The target file produced 62 `HAS_TAG` edges, 56 `TAGGED` edges, and relevance for all 10 chunks. Details are in [`.plan/post_cap_smoke_2026-05-07.md`](../.plan/post_cap_smoke_2026-05-07.md). |
| HERB legacy tagger guard | [`scripts/run_index.py`](../scripts/run_index.py) refuses to run the old generic extraction/tagging path against `Salesforce__HERB` or the `herb` database unless `--allow-legacy-herb-tagging` is explicitly passed. |
| HERB tagging frame design | [`docs/herb_tagging_frames.md`](herb_tagging_frames.md) records the current tagging direction: internal chunk shape routes to deterministic agent-facing frames, and the model receives only relevant source evidence. |
| Pydantic schema enforcement at the agent boundary | [`agents/client.AgentClient.call`](../agents/client.py) validates model output via `schema.model_validate_json` and produces `error_class="schema_invalid"` on failure. Covered by validators in [`agents/schemas.py`](../agents/schemas.py). |
| Idempotency rules | [`Chunker.chunk_file`](../indexing/chunker.py) skips files that already have chunks; preflight upserts `:Source` and `:File` with `MERGE`; bootstrap uses `IF NOT EXISTS` everywhere. |

## What is built but not yet end-to-end verified

- **HERB-aware chunking.** [`indexing/chunker.py`](../indexing/chunker.py) now chunks `Salesforce__HERB` by actual product/metadata evidence sections instead of one JSON row per chunk. HERB chunks include stable `parent_ref`/`chunk_ref` locators (for example `product.ActionGenie.documents.item0001.part00`) and split instead of truncating when the token budget is hit. After clearing the prior HERB chunks and HERB worklist items in the `herb` database, `NEO4J_DATABASE=herb python scripts/run_preflight.py --dataset-id Salesforce__HERB` wrote 5843 chunks and seeded 5876 work items with zero failures. Graph verification reported `max(token_estimate)=1450`, zero truncation markers, zero missing refs, and zero duplicate `chunk_ref` values per file.
- **Full end-to-end run.** The full corpus has 157681 chunk jobs. A complete LLM run has not been attempted after the fresh reset because that would issue a large number of model calls.

## Known gaps

- **Parquet visual-content omission.** [`Chunker._chunk_parquet`](../indexing/chunker.py) now omits Arrow columns that contain binary data, so image bytes are not embedded in `Chunk.content`. This is intentional for prompt/memory safety, but queries over visual content will need a future image-aware path.
- **Non-binary nested parquet rows.** The chunker now caps string length, list length, and recursion depth during JSON conversion. This prevents the observed DocVQA failures, but future parquet schemas may still need schema-specific flattening for better retrieval quality.
- **HERB-specific extraction/tagging.** Not built yet. Do not treat the legacy generic tagger as HERB-quality evidence.
- **`clustering/queries/*.cypher`.** Not built. Planned named views are `by_topic`, `by_evidence`, `recent_active`, `multidim`.
- **Graph export freshness.** Portable JSONL export/import exists via [`scripts/export_graph_json.py`](../scripts/export_graph_json.py), [`scripts/import_graph_json.py`](../scripts/import_graph_json.py), and the tracked monorepo export at `../../graph_export/grag_graph_latest.zip`. It is an operator snapshot, not part of the indexing path. Re-export it whenever the graph contract changes.
- **`provenance.json`.** No per-run provenance dump is written today. `:Run` properties cover the basics, but a structured provenance file is not.
- **Vector indexes / embeddings.** [`schema/vector_indexes.cypher`](../schema/vector_indexes.cypher) is intentionally empty. `EMBEDDING_MODEL` env var is loaded into `Settings.embedding_model` but consumed nowhere.
- **Legacy tag graph compatibility.** Older databases or exports may still contain `Tag`, `HAS_TAG`, `TAGGED`, `CanonicalTag`, or `CanonicalTagProposal` artefacts from the old generic path; rebuild or clean them before using HERB results.

## Decisions to revisit later

- **Agent-negotiated chunking for sequential files.** Today every file is chunked deterministically. For long-form text, the orchestrator passes a continuity hint, but true agent-negotiated chunk boundaries are deferred.
- **Vector indexes and embeddings.** Deferred until the HERB query workload is clearer.
- **Cascade classifier.** Today extraction and canonical mapping happen in one agent call. If schema-invalid rates or canonical mapping quality become a problem, revisit a separate classification prompt.
- **Sequential dispatch for long-form files.** Today `dispatch_mode='sequential'` changes prompt content, not call ordering.
- **Full corpus LLM cost.** A full run means one model call per chunk plus one per chunk-bearing file. Confirm budget/concurrency before launching.

## Last verified action

2026-05-13: cleaned the `herb` database back to fresh HERB chunking artefacts only. Verified node labels are only `Source`, `File`, and `Chunk`; relationship types are only `CONTAINS`, `HAS_CHUNK`, and `NEXT`; worklist is reset to `5843` unrun chunk jobs and `33` unrun file jobs.

## Next recommended step

1. Design the HERB-specific extraction/tagging path.
2. Keep `herb` as source/file/chunk-only until that path exists.
3. Run bounded HERB tests only through the HERB-specific path.

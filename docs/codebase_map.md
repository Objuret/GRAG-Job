# Codebase Map

**TL;DR.** Every top-level directory has its own section. For each file: a one-line role, the key public symbols, and what calls them. Use this as the index when you want to navigate the source.

**When to read this.** When you know what you want to change and need to find the right file.

**Last updated:** 2026-05-07.

## Touched paths

`agents/`, `indexing/`, `clustering/`, `data_access/`, `prompts/`, `schema/`, `scripts/`, `shared/`.

## `agents/`

OpenAI-compatible LLM client and the pydantic schemas every agent call returns.

| File | Role | Key symbols | Called by |
|---|---|---|---|
| [`agents/__init__.py`](../agents/__init__.py) | Package marker. | — | — |
| [`agents/client.py`](../agents/client.py) | One async HTTP call per `.call()`. **Never raises** — returns `AgentResult` with a typed `error_class`. JSON-mode (`response_format=json_object`). | `AgentConfig`, `AgentClient`, `AgentResult`, `ErrorClass` | [`scripts/run_index.py`](../scripts/run_index.py) (constructs the client), [`indexing/orchestrator.py`](../indexing/orchestrator.py) (calls `agent.call`). |
| [`agents/schemas.py`](../agents/schemas.py) | Pydantic models the agent returns. The contract between [`prompts/`](../prompts/) and the orchestrator. | `Cluster` (Literal), `Tag`, `ChunkExtraction`, `FileOrchestrationOutput` | [`indexing/orchestrator.py`](../indexing/orchestrator.py), [`indexing/extraction_writer.py`](../indexing/extraction_writer.py), [`indexing/file_writer.py`](../indexing/file_writer.py). |

## `indexing/`

The core pipeline.

| File | Role | Key symbols | Called by |
|---|---|---|---|
| [`indexing/__init__.py`](../indexing/__init__.py) | Package marker. | — | — |
| [`indexing/breaker.py`](../indexing/breaker.py) | Per-error-class circuit breaker. Defaults are the "tight" policy. | `BreakerThresholds`, `CircuitBreaker.observe`, `BreakerTripped` | [`indexing/orchestrator.py`](../indexing/orchestrator.py) (calls `observe` after every agent call). |
| [`indexing/worklist.py`](../indexing/worklist.py) | `(:WorkItem)` repository. Seed/pull/mark transitions. | `WorkList`, `WorkItemRecord`, `make_work_item_id` | [`indexing/preflight.py`](../indexing/preflight.py) (seeds), [`indexing/orchestrator.py`](../indexing/orchestrator.py) (pulls and marks). |
| [`indexing/runs.py`](../indexing/runs.py) | `(:Run)` repository: `start_run` / `finish_run`, `RunSummary`. | `RunRepository`, `RunSummary`, `make_run_id` | [`scripts/run_index.py`](../scripts/run_index.py). |
| [`indexing/chunker.py`](../indexing/chunker.py) | Per-format deterministic chunker. Rule: re-chunk only if no chunks exist. | `Chunker`, `ChunkPolicy`, `ChunkRecord`, `dispatch_mode_for` | [`indexing/preflight.py`](../indexing/preflight.py). |
| [`indexing/preflight.py`](../indexing/preflight.py) | Scan raw catalog → upsert `:Source`/`:File` → chunk → seed WorkItems. Per-file fault isolation. | `run_preflight`, `PreflightResult`, `upsert_source_node`, `upsert_file_node` | [`scripts/run_preflight.py`](../scripts/run_preflight.py). |
| [`indexing/orchestrator.py`](../indexing/orchestrator.py) | Three-stage dispatcher. Concurrency via `asyncio.Semaphore`; breaker observed under a lock. Renders user messages including the canonical-vocab block. | `Orchestrator.run`, `_run_chunk_stage`, `_run_file_stage`, `_load_canonical_vocab`, `CHUNK_BATCH_SIZE`, `FILE_BATCH_SIZE`, `PREV_TAIL_CHARS`, `CLUSTER_ORDER` | [`scripts/run_index.py`](../scripts/run_index.py). |
| [`indexing/extraction_writer.py`](../indexing/extraction_writer.py) | Writes `ChunkExtraction` results. Idempotent: wipes prior `HAS_TAG` edges before re-writing. Creates `:CanonicalTagProposal` nodes for proposals. | `ExtractionWriter.write_chunk_extraction` | [`indexing/orchestrator.py`](../indexing/orchestrator.py). |
| [`indexing/file_writer.py`](../indexing/file_writer.py) | Writes `FileOrchestrationOutput`. Sets `(:File).description` and `(:Chunk).relevance_to_file`. | `FileExtractionWriter.write_file_orchestration` | [`indexing/orchestrator.py`](../indexing/orchestrator.py). |
| [`indexing/file_rollup.py`](../indexing/file_rollup.py) | Deterministic rollup `HAS_TAG → TAGGED`, weighted by `relevance_to_file`. Delete-and-rebuild within scope. No agent calls. | `FileRollup.run` | [`indexing/orchestrator.py`](../indexing/orchestrator.py) (Stage 3). |

## `clustering/`

Canonical tag vocabulary.

| File | Role | Key symbols | Called by |
|---|---|---|---|
| [`clustering/__init__.py`](../clustering/__init__.py) | Package marker. | — | — |
| [`clustering/canonical_seed.yaml`](../clustering/canonical_seed.yaml) | Source of truth for the canonical tag vocabulary. Five top-level keys (one per cluster). Hybrid seed-and-grow: proposals enter only via a triage CLI (TODO). | — | [`scripts/bootstrap_schema.py`](../scripts/bootstrap_schema.py) `seed_canonical_tags`. |

## `data_access/`

Upstream layer — data sync, classification, profiling. Indexing only consumes the catalog returned by `scan_raw_tree`.

| File | Role | Key symbols | Called by |
|---|---|---|---|
| [`data_access/__init__.py`](../data_access/__init__.py) | Package marker. | — | — |
| [`data_access/raw/__init__.py`](../data_access/raw/__init__.py) | Re-exports the public API. | `build_dataset_run`, `scan_raw_tree`, `snapshot_raw_hash_map`, `sync_sources` | [`indexing/preflight.py`](../indexing/preflight.py), the `__main__` CLI. |
| [`data_access/raw/api.py`](../data_access/raw/api.py) | HF/external sync, raw-tree scan, dataset-run builder. | `sync_sources`, `scan_raw_tree`, `snapshot_raw_hash_map`, `build_dataset_run`, `download_url` | [`data_access/raw/__main__.py`](../data_access/raw/__main__.py), [`indexing/preflight.py`](../indexing/preflight.py). |
| [`data_access/raw/__main__.py`](../data_access/raw/__main__.py) | CLI: `python -m data_access.raw sync|build`. | `make_arg_parser`, `main` | shell. |
| [`data_access/raw/adapters.py`](../data_access/raw/adapters.py) | Per-dataset payload-discovery regex patterns. | `PAYLOAD_PATTERNS`, `discover_payload`, `summarize_payload` | `build_dataset_run`. |
| [`data_access/raw/classification.py`](../data_access/raw/classification.py) | File classification (payload_data / repo_meta_code / cache_meta), format_family, split inference. | `classify_file`, `detect_format_family`, `infer_split_from_path` | `scan_raw_tree`. |
| [`data_access/raw/registry.py`](../data_access/raw/registry.py) | Hardcoded list of HF datasets and external file URLs. | `HF_DATASETS`, `EXTERNAL_FILES`, `HFDatasetSource`, `ExternalFileSource` | `sync_sources`. |

## `prompts/`

LLM system prompts. JSON shapes here MUST match the pydantic schemas in [`agents/schemas.py`](../agents/schemas.py).

| File | Role | Output schema |
|---|---|---|
| [`prompts/extract_chunk.md`](../prompts/extract_chunk.md) | Per-chunk extraction (Stage 1). Five-cluster tag set + chunk description + empty verdict. | `ChunkExtraction` |
| [`prompts/file_descriptor.md`](../prompts/file_descriptor.md) | Per-file orchestration (Stage 2). 3-5 sentence file description + chunk_relevance map. | `FileOrchestrationOutput` |

See [`prompts.md`](prompts.md) for editing rules and validation behaviour.

## `schema/`

Cypher applied by `bootstrap_schema.py`.

| File | Role |
|---|---|
| [`schema/constraints.cypher`](../schema/constraints.cypher) | Uniqueness constraints (Source, File, Chunk, Run, WorkItem, CanonicalTagProposal, Tag) plus the `(label, cluster)` NODE KEY on `:CanonicalTag`. |
| [`schema/indexes.cypher`](../schema/indexes.cypher) | B-tree indexes on hot lookup properties (File.dataset_id, Chunk.file_id, WorkItem.status, etc.) plus relationship indexes on `HAS_TAG.cluster`, `HAS_TAG.canonical_id`, `TAGGED.cluster`. |
| [`schema/vector_indexes.cypher`](../schema/vector_indexes.cypher) | **Empty** — embeddings deferred. |
| [`schema/create_database.cypher`](../schema/create_database.cypher) | One statement to create a fresh empty database (`exjobbet_index`) on Neo4j Enterprise. Run from the `system` database in Neo4j Browser; not invoked by any Python script. |

## `scripts/`

Operator entry points. Each one is small (initialise → call layer code → close clients).

| File | Role |
|---|---|
| [`scripts/bootstrap_schema.py`](../scripts/bootstrap_schema.py) | Apply constraints + indexes + seed canonical tags. Idempotent. Reports `Applied N schema statements; merged M canonical tags.` |
| [`scripts/run_preflight.py`](../scripts/run_preflight.py) | Run [`indexing.preflight.run_preflight`](../indexing/preflight.py) and print summary + per-file failures. Idempotent. |
| [`scripts/run_index.py`](../scripts/run_index.py) | The dispatcher. Validates API key → opens Neo4j + agent client → starts a `:Run` → runs orchestrator → records `ok`/`aborted`. Args: `--dataset-id`, `--chunk-limit`, `--file-limit`, `--concurrency`. |
| [`scripts/verify_graph.py`](../scripts/verify_graph.py) | Quick sanity counts: `:Source`, `:File`, `:Chunk`, unrun WorkItems, `:CanonicalTag` by cluster, file/chunk breakdowns, sample chunk previews. Read-only. |

## `shared/`

| File | Role | Key symbols | Called by |
|---|---|---|---|
| [`shared/__init__.py`](../shared/__init__.py) | Package marker. | — | — |
| [`shared/config.py`](../shared/config.py) | `pydantic-settings`-backed `Settings` loaded from `.env`. Aliases `LLM_*` ↔ `AGENT_*` (LLM wins). | `Settings`, `REPO_ROOT`, `DEFAULT_DATA_ROOT`, `resolve_data_root` | every script and `indexing/runs.py`. |
| [`shared/neo4j_client.py`](../shared/neo4j_client.py) | Thin async wrapper around `neo4j.AsyncGraphDatabase`. | `Neo4jClient`, `Neo4jClient.session`, `Neo4jClient.close` | every script and every `indexing/` writer. |
| [`shared/utils.py`](../shared/utils.py) | Time/hash/JSON helpers. | `utc_now`, `iso_utc`, `stable_short_hash`, `sha256_file`, `hash_tree`, `compare_hash_maps`, `make_json_safe`, `write_json`, `read_json`, `deep_merge`, `find_latest_run_id`, `ensure_dir` | shared across the codebase. |

## Repo-root files

| File | Role |
|---|---|
| [`README.md`](../README.md) | Short landing page; points at `docs/`. |
| [`AGENTS.md`](../AGENTS.md) | Agent pointer file; points at `docs/agent_brief.md`. |
| [`.env.example`](../.env.example) | Template for `.env`. Documented in [`env_and_config.md`](env_and_config.md). |
| [`.gitignore`](../.gitignore) | Ignores `data/` payload subdirectories, `.env`, `__pycache__/`, etc. |
| [`requirements.txt`](../requirements.txt) | Pinned-min-version Python deps. |
| [`pyproject.toml`](../pyproject.toml) | Package metadata (`thesis-pipeline`, Python ≥ 3.10). No build-time deps. |

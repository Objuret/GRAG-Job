# Codebase Map

**TL;DR.** Every top-level directory has its own section. For each file: a one-line role, the key public symbols, and what calls them. Use this as the index when you want to navigate the source.

**When to read this.** When you know what you want to change and need to find the right file.

**Last updated:** 2026-05-14.

## Touched paths

`agents/`, `indexing/`, `tagging/`, `clustering/`, `data_access/`, `prompts/`, `schema/`, `scripts/`, `shared/`, monorepo `graph_export/`.

## `agents/`

OpenAI-compatible LLM client and the pydantic schemas the legacy indexing path returns. HERB tagging uses the separate `tagging/` Anthropic pilot.

| File | Role | Key symbols | Called by |
|---|---|---|---|
| [`agents/__init__.py`](../../backend/agents/__init__.py) | Package marker. | — | — |
| [`agents/client.py`](../../backend/agents/client.py) | **Shim** → loads archived client from [`quarantine/legacy_mirror/backend/agents/client.py`](../../quarantine/legacy_mirror/backend/agents/client.py). OpenAI-compatible; legacy path only. | `AgentConfig`, `AgentClient`, `AgentResult` | [`scripts/run_index.py`](../../backend/scripts/run_index.py), [`indexing/orchestrator.py`](../../backend/indexing/orchestrator.py). |
| [`agents/schemas.py`](../../backend/agents/schemas.py) | **Shim** → loads archived schemas from `quarantine/legacy_mirror/.../schemas.py`. | `Cluster`, `Tag`, `ChunkExtraction`, `FileOrchestrationOutput` | [`indexing/orchestrator.py`](../../backend/indexing/orchestrator.py), writers. |

## `indexing/`

The core pipeline.

| File | Role | Key symbols | Called by |
|---|---|---|---|
| [`indexing/__init__.py`](../../backend/indexing/__init__.py) | Package marker. | — | — |
| [`indexing/breaker.py`](../../backend/indexing/breaker.py) | Per-error-class circuit breaker. Defaults are the "tight" policy. | `BreakerThresholds`, `CircuitBreaker.observe`, `BreakerTripped` | [`indexing/orchestrator.py`](../../backend/indexing/orchestrator.py) (calls `observe` after every agent call). |
| [`indexing/worklist.py`](../../backend/indexing/worklist.py) | Local working-file job ledger under `backend/.work/`. Seed/pull/mark transitions. | `WorkList`, `JobRecord`, `make_work_item_id` | [`indexing/preflight.py`](../../backend/indexing/preflight.py) (seeds), [`indexing/orchestrator.py`](../../backend/indexing/orchestrator.py) (pulls and marks). |
| [`indexing/runs.py`](../../backend/indexing/runs.py) | `(:Run)` repository: `start_run` / `finish_run`, `RunSummary`. | `RunRepository`, `RunSummary`, `make_run_id` | [`scripts/run_index.py`](../../backend/scripts/run_index.py). |
| [`indexing/chunker.py`](../../backend/indexing/chunker.py) | Per-format deterministic chunker. Rule: re-chunk only if no chunks exist. | `Chunker`, `ChunkPolicy`, `ChunkRecord`, `dispatch_mode_for` | [`indexing/preflight.py`](../../backend/indexing/preflight.py). |
| [`indexing/preflight.py`](../../backend/indexing/preflight.py) | **Access layer:** scan → upsert `:Source`/`:File`. **Indexing:** chunk → seed worklist. Per-file fault isolation. | `run_preflight`, `PreflightResult`, `upsert_source_node`, `upsert_file_node` | [`scripts/run_preflight.py`](../../backend/scripts/run_preflight.py). |
| [`indexing/orchestrator.py`](../../backend/indexing/orchestrator.py) | **Shim** → [`quarantine/legacy_mirror/.../orchestrator_legacy.py`](../../quarantine/legacy_mirror/backend/indexing/orchestrator_legacy.py). Legacy three-stage dispatcher. Blocked for HERB unless `--allow-legacy-herb-tagging`. | `Orchestrator`, batch constants | [`scripts/run_index.py`](../../backend/scripts/run_index.py). |
| [`indexing/extraction_writer.py`](../../backend/indexing/extraction_writer.py) | **Shim** → `quarantine/legacy_mirror/.../extraction_writer_legacy.py`. | `ExtractionWriter` | Orchestrator. |
| [`indexing/file_writer.py`](../../backend/indexing/file_writer.py) | **Shim** → `.../file_writer_legacy.py`. | `FileExtractionWriter` | Orchestrator. |
| [`indexing/file_rollup.py`](../../backend/indexing/file_rollup.py) | **Shim** → `.../file_rollup_legacy.py`. | `FileRollup.run` | Orchestrator. |

## `clustering/`

No active HERB clustering implementation lives here. The old canonical seed file has been removed.

| File | Role | Key symbols | Called by |
|---|---|---|---|
| [`clustering/__init__.py`](../../backend/clustering/__init__.py) | Package marker. | — | — |

## `tagging/`

HERB-specific Anthropic tagging pilot. This is separate from the legacy
`indexing/orchestrator.py` path.

| File | Role | Key symbols | Called by |
|---|---|---|---|
| [`tagging/__init__.py`](../../backend/tagging/__init__.py) | Package marker. | - | - |
| [`tagging/__main__.py`](../../backend/tagging/__main__.py) | CLI for `python -m tagging verify-chunks|select|extract|describe|score|analyze`. | `STAGES`, `main` | shell. |
| [`tagging/pipeline.py`](../../backend/tagging/pipeline.py) | HERB pilot pipeline: sample selection, model-facing frame rendering, Anthropic forced-tool calls, graph writes, and analysis report generation. | `stage_verify_chunks`, `stage_select`, `stage_extract`, `stage_describe`, `stage_score`, `stage_analyze`, `render_chunk_user_message`, `ClaudeCaller` | [`tagging/__main__.py`](../../backend/tagging/__main__.py). |

## `data_access/`

**Access layer** — most of the inventory side: sync, scan, classification, payload rules, `raw_dataset_runs` catalogues. The `:Source` / `:File` Neo4j upsert that completes the access layer lives in [`indexing/preflight.py`](../../backend/indexing/preflight.py); see [`docs/backend/architecture.md`](architecture.md) (“Access layer”). Indexing consumes `scan_raw_tree` and then segments into `(:Chunk)`.

| File | Role | Key symbols | Called by |
|---|---|---|---|
| [`data_access/__init__.py`](../../backend/data_access/__init__.py) | Package marker. | — | — |
| [`data_access/raw/__init__.py`](../../backend/data_access/raw/__init__.py) | Re-exports the public API. | `build_dataset_run`, `scan_raw_tree`, `snapshot_raw_hash_map`, `sync_sources` | [`indexing/preflight.py`](../../backend/indexing/preflight.py), the `__main__` CLI. |
| [`data_access/raw/api.py`](../../backend/data_access/raw/api.py) | HF/external sync, raw-tree scan, dataset-run builder. | `sync_sources`, `scan_raw_tree`, `snapshot_raw_hash_map`, `build_dataset_run`, `download_url` | [`data_access/raw/__main__.py`](../../backend/data_access/raw/__main__.py), [`indexing/preflight.py`](../../backend/indexing/preflight.py). |
| [`data_access/raw/__main__.py`](../../backend/data_access/raw/__main__.py) | CLI: `python -m data_access.raw sync|build`. | `make_arg_parser`, `main` | shell. |
| [`data_access/raw/adapters.py`](../../backend/data_access/raw/adapters.py) | Per-dataset payload-discovery regex patterns. | `PAYLOAD_PATTERNS`, `discover_payload`, `summarize_payload` | `build_dataset_run`. |
| [`data_access/raw/classification.py`](../../backend/data_access/raw/classification.py) | File classification (payload_data / repo_meta_code / cache_meta), format_family, split inference. | `classify_file`, `detect_format_family`, `infer_split_from_path` | `scan_raw_tree`. |
| [`data_access/raw/registry.py`](../../backend/data_access/raw/registry.py) | Hardcoded list of HF datasets and external file URLs. | `HF_DATASETS`, `EXTERNAL_FILES`, `HFDatasetSource`, `ExternalFileSource` | `sync_sources`. |

## `prompts/`

LLM system prompts. JSON shapes here MUST match the pydantic schemas in [`agents/schemas.py`](../../backend/agents/schemas.py).

| File | Role | Output schema |
|---|---|---|
| [`prompts/extract_chunk.md`](../../backend/prompts/extract_chunk.md) | Per-chunk extraction (Stage 1). Five-cluster tag set + chunk description + empty verdict. | `ChunkExtraction` |
| [`prompts/extract_chunk_tags_only.md`](../../backend/prompts/extract_chunk_tags_only.md) | Non-mutating pilot prompt. Five cluster-keyed keyword lists only; no graph writes. | `TagsOnlyExtraction` in [`scripts/run_tags_only_pilot.py`](../../backend/scripts/run_tags_only_pilot.py) |
| [`prompts/file_descriptor.md`](../../backend/prompts/file_descriptor.md) | Per-file orchestration (Stage 2). 3-5 sentence file description + chunk_relevance map. | `FileOrchestrationOutput` |

See [`prompts.md`](prompts.md) for editing rules and validation behaviour.

## `schema/`

Cypher applied by `bootstrap_schema.py`.

| File | Role |
|---|---|
| [`schema/constraints.cypher`](../../backend/schema/constraints.cypher) | Uniqueness constraints (Source, File, Chunk, Run, CanonicalTagProposal, Tag) plus the `(label, cluster)` NODE KEY on `:CanonicalTag`. |
| [`schema/indexes.cypher`](../../backend/schema/indexes.cypher) | B-tree indexes on hot lookup properties (File.dataset_id, Chunk.file_id, etc.) plus relationship indexes on `HAS_TAG.cluster`, `HAS_TAG.canonical_id`, `TAGGED.cluster`. |
| [`schema/vector_indexes.cypher`](../../backend/schema/vector_indexes.cypher) | **Empty** — embeddings deferred. |
| [`schema/create_database.cypher`](../../backend/schema/create_database.cypher) | One statement to create a fresh empty database (`exjobbet_index`) on Neo4j Enterprise. Run from the `system` database in Neo4j Browser; not invoked by any Python script. |

## `scripts/`

Operator entry points. Each one is small (initialise → call layer code → close clients).

| File | Role |
|---|---|
| [`scripts/bootstrap_schema.py`](../../backend/scripts/bootstrap_schema.py) | Apply constraints + indexes. Idempotent. Does not seed tag vocabularies. |
| [`scripts/export_graph_json.py`](../../backend/scripts/export_graph_json.py) | Export the current Neo4j graph to portable JSONL files under monorepo `graph_export/latest/`. |
| [`scripts/import_graph_json.py`](../../backend/scripts/import_graph_json.py) | Import a JSONL graph export directory or zip into Neo4j; supports `--wipe`. |
| [`scripts/migrate_cluster_names.py`](../../backend/scripts/migrate_cluster_names.py) | One-time/idempotent data migration from retired cluster strings to `topic`, `entities`, `activity`, `temporal`, `evidence`. Also rewrites proposal IDs derived from cluster names. |
| [`scripts/run_preflight.py`](../../backend/scripts/run_preflight.py) | Run [`indexing.preflight.run_preflight`](../../backend/indexing/preflight.py) and print summary + per-file failures. Idempotent. |
| [`scripts/run_index.py`](../../backend/scripts/run_index.py) | **Shim** (`runpy` → `quarantine/legacy_mirror/.../run_index_legacy.py`). Legacy dispatcher; refuses HERB unless `--allow-legacy-herb-tagging`. |
| [`scripts/run_tags_only_pilot.py`](../../backend/scripts/run_tags_only_pilot.py) | **Shim** (`runpy` → `quarantine/legacy_mirror/.../run_tags_only_pilot_legacy.py`). Non-mutating pilot. |
| [`scripts/run_tags_only_structured_matrix.py`](../../backend/scripts/run_tags_only_structured_matrix.py) | Controlled structured-output model matrix runner for the tags-only pilot. Writes comparison reports under `backend/.plan/`. |
| [`scripts/verify_graph.py`](../../backend/scripts/verify_graph.py) | Quick sanity counts: `:Source`, `:File`, `:Chunk`, working-file item statuses, file/chunk breakdowns, sample chunk previews. Read-only. |

## `shared/`

| File | Role | Key symbols | Called by |
|---|---|---|---|
| [`shared/__init__.py`](../../backend/shared/__init__.py) | Package marker. | — | — |
| [`shared/config.py`](../../backend/shared/config.py) | `pydantic-settings`-backed `Settings` loaded from `.env`. Aliases `LLM_*` ↔ `AGENT_*` (LLM wins). | `Settings`, `REPO_ROOT`, `DEFAULT_DATA_ROOT`, `resolve_data_root` | every script and `indexing/runs.py`. |
| [`shared/neo4j_client.py`](../../backend/shared/neo4j_client.py) | Thin async wrapper around `neo4j.AsyncGraphDatabase`. | `Neo4jClient`, `Neo4jClient.session`, `Neo4jClient.close` | every script and every `indexing/` writer. |
| [`shared/error_class.py`](../../backend/shared/error_class.py) | `ErrorClass` literal for `indexing/breaker.py` (decoupled from `agents/`). | `ErrorClass` | [`indexing/breaker.py`](../../backend/indexing/breaker.py), [`agents/client.py`](../../backend/agents/client.py) (archived copy). |
| [`shared/legacy_mirror_boot.py`](../../backend/shared/legacy_mirror_boot.py) | `importlib` helper to load quarantined legacy modules from `quarantine/legacy_mirror/backend/`. | `load_module` | [`indexing/orchestrator.py`](../../backend/indexing/orchestrator.py) shim, other indexing shims. |

## Backend-root files

| File | Role |
|---|---|
| [`README.md`](../../backend/README.md) | Short landing page; points at `/docs/`. |
| [`AGENTS.md`](../../backend/AGENTS.md) | Module pointer; points at `/AGENTS.md` and `/docs/backend/`. |
| [`.env.example`](../../backend/.env.example) | Template for `.env`. Documented in [`env_and_config.md`](env_and_config.md). |
| [`requirements.txt`](../../backend/requirements.txt) | Direct Python dependency floor for maintainers updating the lock. |
| [`requirements-lock.txt`](../../backend/requirements-lock.txt) | Fully pinned Python dependency set for reproducible installs. |
| [root `.gitignore`](../../../.gitignore) | Monorepo ignore rules for backend paths such as `backend/data/raw/`, `backend/.env`, bytecode, and virtual environments. |
| [`pyproject.toml`](../../backend/pyproject.toml) | Package metadata (`thesis-pipeline`, Python ≥ 3.10). No build-time deps. |

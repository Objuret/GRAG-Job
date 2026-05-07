# Graph Schema

**TL;DR.** This is the Neo4j artefact contract. Every node label and edge type is documented below with properties, types, constraints, indexes, who writes it, and who reads it. The schema is applied by [`scripts/bootstrap_schema.py`](../scripts/bootstrap_schema.py) reading [`schema/constraints.cypher`](../schema/constraints.cypher), [`schema/indexes.cypher`](../schema/indexes.cypher), [`schema/vector_indexes.cypher`](../schema/vector_indexes.cypher).

**When to read this.** Any time you write Cypher, change a writer, or design a new query. This is the source of truth for shape.

**Last updated:** 2026-05-07.

## Touched paths

`schema/`, `indexing/` (every writer), `scripts/bootstrap_schema.py`, `scripts/verify_graph.py`.

## Conventions

- All identifiers are **strings**. Hashes are SHA-256 hex prefixes from [`shared/utils.stable_short_hash`](../shared/utils.py).
- Timestamps are ISO-8601 UTC strings produced by [`shared/utils.iso_utc`](../shared/utils.py) (e.g. `2026-05-07T08:00:00Z`).
- "Who writes" / "Who reads" lists the source files; cross-check there for any property you don't see below.

## Node labels

### `:Source`

One per dataset (`Salesforce__HERB`, `wenhu__hybrid_qa`, …).

| Property | Type | Notes |
|---|---|---|
| `source_id` | string | **UNIQUE constraint.** Equals the dataset_id (top-level dir under `data/raw/`). |
| `dataset_id` | string | Same value as `source_id` today; kept for compatibility. |
| `created_at` | iso8601 string | Set on create. |

- **Constraint:** `REQUIRE n.source_id IS UNIQUE` ([`schema/constraints.cypher`](../schema/constraints.cypher)).
- **Indexes:** none beyond the uniqueness constraint.
- **Who writes:** [`indexing/preflight.py`](../indexing/preflight.py) `upsert_source_node`.
- **Who reads:** [`indexing/worklist.py`](../indexing/worklist.py) (`pull_unrun_*` with `dataset_id_filter`), [`indexing/orchestrator.py`](../indexing/orchestrator.py).

### `:File`

One per payload file (`file_class == 'payload_data'`).

| Property | Type | Notes |
|---|---|---|
| `file_id` | string | **UNIQUE constraint.** First 24 hex chars of `sha256`. |
| `sha256` | string | Full SHA-256 of file bytes. |
| `dataset_id` | string | Foreign key to `:Source.source_id`. |
| `rel_path` | string | Posix-style relative path under `data/raw/`. |
| `file_path` | string | Absolute resolved path on the host where preflight ran. |
| `format_family` | string | One of `json`, `jsonl`, `parquet`, `yaml`, `image`, `archive`, `unknown`, etc. (See [`data_access/raw/classification.py`](../data_access/raw/classification.py).) |
| `size_bytes` | int | |
| `dispatch_mode` | string | `parallel` or `sequential`. (See [`indexing/chunker.dispatch_mode_for`](../indexing/chunker.py).) |
| `created_at` | iso8601 | Set on create. |
| `description` | string \| null | Written by the file orchestrator (Stage 2). |
| `description_run_id` | string \| null | Run that produced the description. |

- **Constraint:** `REQUIRE n.file_id IS UNIQUE`.
- **Indexes:** `(n.dataset_id)`, `(n.format_family)`.
- **Who writes:** preflight (creation, base properties), [`indexing/file_writer.py`](../indexing/file_writer.py) (description), [`indexing/file_rollup.py`](../indexing/file_rollup.py) reads it.
- **Who reads:** orchestrator (file context), rollup, worklist filtering, [`scripts/verify_graph.py`](../scripts/verify_graph.py).

### `:Chunk`

One per deterministic chunk produced by [`indexing/chunker.py`](../indexing/chunker.py).

| Property | Type | Notes |
|---|---|---|
| `chunk_id` | string | **UNIQUE constraint.** `stable_short_hash(f"{file_id}:{ordinal}:{start_offset}", 24)`. |
| `file_id` | string | Foreign key to `:File`. |
| `ordinal` | int | 0-based position within the file. |
| `kind` | string | `record`, `object`, `section`, `paragraph`, `table`, `image`, `raw`. |
| `start_offset` | int | Byte/char offset within the source file (semantics depend on format). |
| `end_offset` | int | The agent **must echo this** as `chunk_end_offset` in `ChunkExtraction`. |
| `content` | string | Full chunk text. Stored directly per [decision D10](architecture.md#d10--storing-chunkcontent-directly-vs-offsets). |
| `token_estimate` | int | `len(text) // 4`, min 1. |
| `locator_json` | string | JSON-serialised locator (line, row, char_range, etc.). |
| `empty` | bool | Set by ExtractionWriter; `false` initially. |
| `empty_reason` | string \| null | One-line reason when `empty=true`. |
| `description` | string \| null | 1-3 sentence chunk description from the agent. |
| `relevance_to_file` | float \| null | In [0, 1]. Written by FileExtractionWriter. |
| `created_at` | iso8601 | Set on create by chunker. |

- **Constraint:** `REQUIRE n.chunk_id IS UNIQUE`.
- **Indexes:** `(n.file_id)`, `(n.empty)`.
- **Who writes:** [`indexing/chunker.py`](../indexing/chunker.py) (creation), [`indexing/extraction_writer.py`](../indexing/extraction_writer.py) (`empty`, `empty_reason`, `description`), [`indexing/file_writer.py`](../indexing/file_writer.py) (`relevance_to_file`).
- **Who reads:** orchestrator, worklist (chunk inventory), rollup.

### `:Tag`

One per **distinct tag name** across the corpus. Cluster is on the **edge**, not on the node — see [decision D2](architecture.md#d2--tag-uniqueness-on-name-only-cluster-on-edges).

| Property | Type | Notes |
|---|---|---|
| `name` | string | **UNIQUE constraint.** snake_case label, e.g. `q2_2025`, `revenue_decline`. |

- **Constraint:** `REQUIRE n.name IS UNIQUE`.
- **Indexes:** none beyond uniqueness.
- **Who writes:** [`indexing/extraction_writer.py`](../indexing/extraction_writer.py) (`MERGE (t:Tag {name: tag.name})`).
- **Who reads:** rollup, future cluster query views.

### `:CanonicalTag`

The seeded vocabulary plus any promoted proposals.

| Property | Type | Notes |
|---|---|---|
| `label` | string | Part of the node key. |
| `cluster` | string | Part of the node key. One of the five clusters. |
| `gloss` | string | Optional one-line definition. |
| `source` | string | `"seed"` for entries from [`clustering/canonical_seed.yaml`](../clustering/canonical_seed.yaml). |

- **Constraint:** `REQUIRE (n.label, n.cluster) IS NODE KEY` ([`schema/constraints.cypher`](../schema/constraints.cypher)).
- **Indexes:** `(n.cluster)`.
- **Who writes:** [`scripts/bootstrap_schema.py`](../scripts/bootstrap_schema.py) `seed_canonical_tags`. Future: a triage CLI promoting `:CanonicalTagProposal` nodes (TODO).
- **Who reads:** orchestrator's `_load_canonical_vocab` builds the user-message vocabulary block from these.

### `:CanonicalTagProposal`

Created when the agent emits a tag with `propose=True`.

| Property | Type | Notes |
|---|---|---|
| `proposal_id` | string | **UNIQUE constraint.** `stable_short_hash(f"{cluster}:{name}", 24)`. |
| `label` | string | Same as the tag `name`. |
| `cluster` | string | One of the five. |
| `gloss` | string | Required when proposing. |
| `rationale` | string \| null | Optional. |
| `observed_count` | int | Incremented every time the proposal is re-emitted. |
| `first_seen` | iso8601 | |
| `last_seen` | iso8601 | |
| `run_id` | string | Run that first created the proposal. |

- **Constraint:** `REQUIRE n.proposal_id IS UNIQUE`.
- **Indexes:** none beyond uniqueness.
- **Who writes:** [`indexing/extraction_writer.py`](../indexing/extraction_writer.py).
- **Who reads:** Future triage CLI (TODO — see [`status.md`](status.md)).

### `:WorkItem`

The "what to do" register. One row per chunk extraction and one per file orchestration for files that have at least one chunk. Files that produce zero chunks have no LLM WorkItem.

| Property | Type | Notes |
|---|---|---|
| `work_item_id` | string | **UNIQUE constraint.** `f"{kind}:{target_id}"`. |
| `kind` | string | `chunk_extraction` or `file_orchestration`. |
| `target_id` | string | `chunk_id` or `file_id`. |
| `file_id` | string | The owning file (== `target_id` for `file_orchestration` items). |
| `status` | string | `unrun`, `done`, `failed`. |
| `created_at` | iso8601 | Set on create. |
| `assigned_at` | iso8601 \| null | Stamped when the orchestrator pulls the item. |
| `completed_at` | iso8601 \| null | Stamped on `mark_done` / `mark_failed`. |
| `run_id` | string \| null | Most recent toucher; reset to null on `reset_failed_to_unrun`. |
| `in_tokens`, `out_tokens` | int | Per-call token counts. |
| `duration_ms` | int | Per-call duration. |
| `error_class` | string \| null | One of the `ErrorClass` literals or `schema_validation`. |
| `error_message` | string \| null | Truncated to 5000 chars. |

- **Constraint:** `REQUIRE n.work_item_id IS UNIQUE`.
- **Indexes:** `(n.status)`, `(n.kind)`.
- **Who writes:** [`indexing/worklist.py`](../indexing/worklist.py).
- **Who reads:** orchestrator, `verify_graph.py`.

### `:Run`

One per `python scripts/run_index.py` invocation.

| Property | Type | Notes |
|---|---|---|
| `run_id` | string | **UNIQUE constraint.** ISO timestamp + 6-char hash. |
| `status` | string | `started`, `ok`, `aborted`. |
| `started_at`, `finished_at` | iso8601 | |
| `git_commit` | string | `git rev-parse HEAD` at run start, or empty. |
| `agent_model` | string | From `Settings.agent_model`. |
| `agent_max_concurrency` | int | From `Settings.agent_max_concurrency`. |
| `abort_reason` | string | Empty when `status='ok'`. |
| `chunks_done`, `chunks_failed` | int | From `RunSummary`. |
| `files_done`, `files_failed` | int | From `RunSummary`. |
| `total_in_tokens`, `total_out_tokens`, `total_duration_ms` | int | |

- **Constraint:** `REQUIRE n.run_id IS UNIQUE`.
- **Indexes:** none beyond uniqueness.
- **Who writes:** [`indexing/runs.py`](../indexing/runs.py).
- **Who reads:** humans inspecting the graph; the orchestrator stamps `run_id` onto WorkItems but does not re-read `:Run` properties.

## Edge types

### `(:Source)-[:CONTAINS]->(:File)`

- **Properties:** none.
- **Who writes:** preflight `upsert_file_node`.
- **Who reads:** worklist filters; future cluster queries.

### `(:File)-[:HAS_CHUNK]->(:Chunk)`

- **Properties:** none.
- **Who writes:** [`indexing/chunker.py`](../indexing/chunker.py) `_write_chunks`.
- **Who reads:** orchestrator, file rollup, worklist seeding.

### `(:Chunk)-[:NEXT]->(:Chunk)`

Linked-list within a file; ordinal-ordered.

- **Properties:** none.
- **Who writes:** [`indexing/chunker.py`](../indexing/chunker.py) (the second pass after MERGE-ing the chunk batch).
- **Who reads:** orchestrator's `_load_chunk_context` reads `(prev:Chunk)-[:NEXT]->(c)` to fetch the previous chunk's content for the continuity hint when `dispatch_mode='sequential'`.

### `(:Chunk)-[:HAS_TAG]->(:Tag)`

The per-chunk tagging edge. **One edge per (chunk, tag-occurrence)** — re-extracting a chunk wipes existing edges before creating fresh ones.

| Property | Type | Notes |
|---|---|---|
| `cluster` | string | One of the five clusters. The cluster lives on the **edge**, not the Tag node. |
| `canonical_id` | string \| null | The canonical label the agent mapped to, or `null` when proposing. **Indexed.** |
| `weight_local` | float | Saliency in [0, 1] for this chunk. |
| `run_id` | string | Run that wrote the edge. |

- **Indexes:** `(r.cluster)`, `(r.canonical_id)`.
- **Who writes:** [`indexing/extraction_writer.py`](../indexing/extraction_writer.py) `_write_non_empty`.
- **Who reads:** [`indexing/file_rollup.py`](../indexing/file_rollup.py), orchestrator's file_context loader (chunk inventory).

### `(:File)-[:TAGGED]->(:Tag)`

Derived edge from the deterministic file rollup. Pure function of `HAS_TAG` + `Chunk.relevance_to_file`.

| Property | Type | Notes |
|---|---|---|
| `cluster` | string | Carried through from `HAS_TAG.cluster`. |
| `canonical_id` | string \| null | Carried through. |
| `weight_global` | float | `sum(coalesce(c.relevance_to_file, 0.5) * r.weight_local) / count(c)` per (file, tag, cluster, canonical_id) group. |
| `n_chunks` | int | Number of chunks in this file that contributed this tag. |
| `run_id` | string | Run that performed the rollup. |
| `updated_at` | iso8601 | |

- **Indexes:** `(r.cluster)`.
- **Who writes:** [`indexing/file_rollup.py`](../indexing/file_rollup.py). The rollup **deletes all in-scope `TAGGED` edges first** then creates fresh ones (Cypher MERGE semantics around null `canonical_id` are awkward; pure delete-and-rebuild is safer).
- **Who reads:** future cluster query views (not built yet — planned under `clustering/queries/`).

### `(:WorkItem)-[:TARGETS]->(:Chunk | :File)`

Pointer from the work register to the work target.

- **Properties:** none.
- **Who writes:** [`indexing/worklist.py`](../indexing/worklist.py) `seed_chunk_extraction_items`, `seed_file_orchestration_item`.
- **Who reads:** debugging only — the orchestrator uses `target_id` directly.

### `(:CanonicalTagProposal)-[:OBSERVED_IN]->(:Chunk)`

One edge per proposing-occurrence; lets us trace where a proposal came from.

- **Properties:** none (the proposal node carries `observed_count`).
- **Who writes:** [`indexing/extraction_writer.py`](../indexing/extraction_writer.py).
- **Who reads:** Future triage CLI.

## Indexes summary

From [`schema/indexes.cypher`](../schema/indexes.cypher):

```cypher
CREATE INDEX IF NOT EXISTS FOR (n:File)         ON (n.dataset_id);
CREATE INDEX IF NOT EXISTS FOR (n:File)         ON (n.format_family);
CREATE INDEX IF NOT EXISTS FOR (n:Chunk)        ON (n.file_id);
CREATE INDEX IF NOT EXISTS FOR (n:Chunk)        ON (n.empty);
CREATE INDEX IF NOT EXISTS FOR (n:WorkItem)     ON (n.status);
CREATE INDEX IF NOT EXISTS FOR (n:WorkItem)     ON (n.kind);
CREATE INDEX IF NOT EXISTS FOR (n:CanonicalTag) ON (n.cluster);
CREATE INDEX IF NOT EXISTS FOR ()-[r:HAS_TAG]-() ON (r.cluster);
CREATE INDEX IF NOT EXISTS FOR ()-[r:HAS_TAG]-() ON (r.canonical_id);
CREATE INDEX IF NOT EXISTS FOR ()-[r:TAGGED]-()  ON (r.cluster);
```

[`schema/vector_indexes.cypher`](../schema/vector_indexes.cypher) is intentionally empty — embeddings are deferred (see [`status.md`](status.md)).

## Quick reference for property placement

| Concept | Lives on | Why |
|---|---|---|
| `dispatch_mode` | `:File` property | Determined per file at preflight; the orchestrator branches on it. |
| `relevance_to_file` | `:Chunk` property | Per-chunk score from the file orchestrator. Used by rollup. |
| `weight_local` | `(:Chunk)-[:HAS_TAG]->(:Tag)` edge property | Per-chunk tag saliency. |
| `weight_global` | `(:File)-[:TAGGED]->(:Tag)` edge property | Aggregate of `relevance_to_file * weight_local`. |
| `canonical_id` | `(:Chunk)-[:HAS_TAG]->(:Tag)` and `(:File)-[:TAGGED]->(:Tag)` edges | Per-attribution mapping; `null` when the tag is a proposal. |
| `cluster` | `(:Chunk)-[:HAS_TAG]->(:Tag)` and `(:File)-[:TAGGED]->(:Tag)` edges | The same Tag name can be in different clusters across occurrences. |

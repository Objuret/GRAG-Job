# Graph Schema

**TL;DR.** This is the Neo4j artefact contract. Every node label and edge type is documented below with properties, types, constraints, indexes, who writes it, and who reads it. The schema is applied by [`scripts/bootstrap_schema.py`](backend/scripts/bootstrap_schema.py) reading [`schema/constraints.cypher`](backend/schema/constraints.cypher), [`schema/indexes.cypher`](backend/schema/indexes.cypher), [`schema/vector_indexes.cypher`](backend/schema/vector_indexes.cypher).

**When to read this.** Any time you write Cypher, change a writer, or design a new query. This is the source of truth for shape.

**Last updated:** 2026-05-13.

## Touched paths

`schema/`, `indexing/` (every writer), `scripts/bootstrap_schema.py`, `scripts/verify_graph.py`.

## Conventions

- All identifiers are **strings**. Hashes are SHA-256 hex prefixes from [`shared/utils.stable_short_hash`](backend/shared/utils.py).
- Timestamps are ISO-8601 UTC strings produced by [`shared/utils.iso_utc`](backend/shared/utils.py) (e.g. `2026-05-07T08:00:00Z`).
- "Who writes" / "Who reads" lists the source files; cross-check there for any property you don't see below.

## Node labels

### `:Source`

One per dataset (`Salesforce__HERB`, `wenhu__hybrid_qa`, …).

| Property | Type | Notes |
|---|---|---|
| `source_id` | string | **UNIQUE constraint.** Equals the dataset_id (top-level dir under `data/raw/`). |
| `dataset_id` | string | Same value as `source_id` today; kept for compatibility. |
| `created_at` | iso8601 string | Set on create. |

- **Constraint:** `REQUIRE n.source_id IS UNIQUE` ([`schema/constraints.cypher`](backend/schema/constraints.cypher)).
- **Indexes:** none beyond the uniqueness constraint.
- **Who writes:** [`indexing/preflight.py`](backend/indexing/preflight.py) `upsert_source_node`.
- **Who reads:** [`indexing/orchestrator.py`](backend/indexing/orchestrator.py).

### `:File`

One per payload file (`file_class == 'payload_data'`).

| Property | Type | Notes |
|---|---|---|
| `file_id` | string | **UNIQUE constraint.** First 24 hex chars of `sha256`. |
| `sha256` | string | Full SHA-256 of file bytes. |
| `dataset_id` | string | Foreign key to `:Source.source_id`. |
| `rel_path` | string | Posix-style relative path under `data/raw/`. |
| `file_path` | string | Absolute resolved path on the host where preflight ran. |
| `format_family` | string | One of `json`, `jsonl`, `parquet`, `yaml`, `image`, `archive`, `unknown`, etc. (See [`data_access/raw/classification.py`](backend/data_access/raw/classification.py).) |
| `size_bytes` | int | |
| `dispatch_mode` | string | `parallel` or `sequential`. (See [`indexing/chunker.dispatch_mode_for`](backend/indexing/chunker.py).) |
| `created_at` | iso8601 | Set on create. |
| `description` | string \| null | Written by the file orchestrator (Stage 2). |
| `description_run_id` | string \| null | Run that produced the description. |

- **Constraint:** `REQUIRE n.file_id IS UNIQUE`.
- **Indexes:** `(n.dataset_id)`, `(n.format_family)`.
- **Who writes:** preflight (creation, base properties), [`indexing/file_writer.py`](backend/indexing/file_writer.py) (description), [`indexing/file_rollup.py`](backend/indexing/file_rollup.py) reads it.
- **Who reads:** orchestrator (file context), rollup, [`scripts/verify_graph.py`](backend/scripts/verify_graph.py).

### `:Chunk`

One per deterministic chunk produced by [`indexing/chunker.py`](backend/indexing/chunker.py).

| Property | Type | Notes |
|---|---|---|
| `chunk_id` | string | **UNIQUE constraint.** `stable_short_hash(f"{file_id}:{ordinal}:{start_offset}", 24)`. |
| `file_id` | string | Foreign key to `:File`. |
| `ordinal` | int | 0-based position within the file. |
| `kind` | string | Base kinds: `record`, `object`, `section`, `paragraph`, `table`, `image`, `raw`. HERB-aware kinds include `product_profile`, `directory_batch`, `org_tree`, `slack_thread_batch`, `document`, `document_part`, `meeting_transcript`, `meeting_transcript_part`, `meeting_chat_batch`, `url_batch`, `pr_batch`, `qa_record`, `qa_record_part`, `qa_batch`, `unanswerable_question_batch`. |
| `start_offset` | int | Byte/char offset within the source file (semantics depend on format). |
| `end_offset` | int | The agent **must echo this** as `chunk_end_offset` in `ChunkExtraction`. |
| `content` | string | Full chunk text. Stored directly per [decision D10](backend/architecture.md#d10--storing-chunkcontent-directly-vs-offsets). |
| `token_estimate` | int | `len(text) // 4`, min 1. |
| `locator_json` | string | JSON-serialised locator (line, row, char_range, HERB `parent_ref`/`chunk_ref`, etc.). |
| `empty` | bool | Set by ExtractionWriter; `false` initially. |
| `empty_reason` | string \| null | One-line reason when `empty=true`. |
| `description` | string \| null | 1-3 sentence chunk description from the agent. |
| `relevance_to_file` | float \| null | In [0, 1]. Written by FileExtractionWriter. |
| `created_at` | iso8601 | Set on create by chunker. |

**Hard fields (materialized).** Written by `python -m tagging materialize` ([`tagging/pipeline.py`](backend/tagging/pipeline.py) `stage_materialize`), no LLM, idempotent. Two parts with different dependencies (stated honestly, not papered over):

- **Scalars — pre-tagging.** Lifted from the keys the chunker already parsed into `locator_json`. Depends only on chunking.
- **`years` — post-tagging.** A denormalized projection of the literal 4-digit year tokens in this chunk's `temporal`-facet `:Tag` names (`2023_2028` → `[2023, 2028]`; **no range expansion**). Needs `extract` to have written `HAS_TAG` edges; the tags stay authoritative, this is a fast-filter copy. The earlier regex-over-`content` `years` (which scraped IDs/ports/prices) was removed.

Retrieval hard-gates on these **before** any tag/embedding scoring. Does not affect tagging (see the Non-Contamination clarification in [`herb_tagging_frames.md`](backend/herb_tagging_frames.md)).

| Property | Type | Notes |
|---|---|---|
| `product` | string \| null | Product the chunk belongs to (`locator.product`). |
| `section` | string \| null | HERB section (`slack`, `documents`, `prs`, `answerable_questions`, …). |
| `channel` | string \| null | Slack channel (slack chunks only). |
| `employee_id` | string \| null | `eid_…` (org-tree chunks). |
| `parent_ref` / `chunk_ref` | string \| null | HERB tree address (exact navigation). |
| `metadata_section` | string \| null | Corpus-level table marker (`locator.metadata`, e.g. `salesforce_team`). |
| `subsection` | string \| null | Org-tree subsection. |
| `doc_field` | string \| null | Source text field for document/transcript parts (`locator.field`). |
| `item_index` | int \| null | `locator.index`. |
| `msg_index_start` / `msg_index_end` | int \| null | Batch message range (`locator.index_start`/`index_end`). |
| `part_index` | int \| null | `locator.part` for `*_part` chunks. |
| `question` | string \| null | QA question text (qa chunks). |
| `years` | list<int> \| absent | Literal 4-digit years from this chunk's `temporal`-facet tag names; absent (not `[]`) when none. |

All scalars are sparse: a property is **absent** on a chunk that had no value (Neo4j drops `null` on `SET +=`). `years` follows the same rule — absent, never an empty list.

- **Constraint:** `REQUIRE n.chunk_id IS UNIQUE`.
- **Indexes:** `(n.file_id)`, `(n.empty)`, `(n.kind)`, plus RANGE on the **four gated** scalars only (`product`, `section`, `channel`, `employee_id`) and the `chunk_fulltext` FULLTEXT index on `[content, description, question]`. The other scalar hard fields are materialized and queryable but **deliberately not indexed** (retrieval does not filter on them; an earlier version indexed them and that unused surface was removed). `years` is a list — not range-indexable; scanned (corpus is small). See [`schema/indexes.cypher`](backend/schema/indexes.cypher).
- **Who writes:** [`indexing/chunker.py`](backend/indexing/chunker.py) (creation), [`indexing/extraction_writer.py`](backend/indexing/extraction_writer.py) (`empty`, `empty_reason`, `description`), [`indexing/file_writer.py`](backend/indexing/file_writer.py) (`relevance_to_file`).
- **Who reads:** orchestrator, rollup.

### `:Tag`

One per **distinct tag name** across the corpus. Cluster is on the **edge**, not on the node — see [decision D2](backend/architecture.md#d2--tag-uniqueness-on-name-only-cluster-on-edges).

| Property | Type | Notes |
|---|---|---|
| `name` | string | **UNIQUE constraint.** snake_case label, e.g. `q2_2025`, `revenue_decline`. |

- **Constraint:** `REQUIRE n.name IS UNIQUE`.
- **Indexes:** none beyond uniqueness.
- **Who writes:** [`indexing/extraction_writer.py`](backend/indexing/extraction_writer.py) (`MERGE (t:Tag {name: tag.name})`).
- **Who reads:** rollup, future cluster query views.

### `:CanonicalTag`

Legacy vocabulary node type from the generic tagger path. HERB preflight/chunking does not create these nodes.

| Property | Type | Notes |
|---|---|---|
| `label` | string | Part of the node key. |
| `cluster` | string | Part of the node key. One of `topic`, `entities`, `activity`, `temporal`, `evidence`. |
| `gloss` | string | Optional one-line definition. |
| `source` | string | Legacy source marker. |

- **Constraint:** `REQUIRE (n.label, n.cluster) IS NODE KEY` ([`schema/constraints.cypher`](backend/schema/constraints.cypher)).
- **Indexes:** `(n.cluster)`.
- **Who writes:** No active HERB path. The old bootstrap seed path has been removed.
- **Who reads:** orchestrator's `_load_canonical_vocab` builds the user-message vocabulary block from these.

### `:CanonicalTagProposal`

Created when the agent emits a tag with `canonical_missing=True`. Raw tag names are expected to be specific and often new; this node is only for proposing a missing broad canonical label.

| Property | Type | Notes |
|---|---|---|
| `proposal_id` | string | **UNIQUE constraint.** `stable_short_hash(f"{cluster}:{name}", 24)`. |
| `label` | string | Same as the tag `name`. |
| `cluster` | string | One of `topic`, `entities`, `activity`, `temporal`, `evidence`. |
| `gloss` | string | Required when proposing. |
| `rationale` | string \| null | Optional. |
| `observed_count` | int | Incremented every time the proposal is re-emitted. |
| `first_seen` | iso8601 | |
| `last_seen` | iso8601 | |
| `run_id` | string | Run that first created the proposal. |

- **Constraint:** `REQUIRE n.proposal_id IS UNIQUE`.
- **Indexes:** none beyond uniqueness.
- **Who writes:** [`indexing/extraction_writer.py`](backend/indexing/extraction_writer.py).
- **Who reads:** Future triage CLI (TODO — see [`status.md`](backend/status.md)).

### Working File

Scheduler state is not part of the graph. Chunk/file agent jobs live in `backend/.work/worklist_<neo4j_database>.json`, written by [`indexing/worklist.py`](backend/indexing/worklist.py). There are no `:WorkItem` nodes in the graph contract.

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
- **Who writes:** [`indexing/runs.py`](backend/indexing/runs.py).
- **Who reads:** humans inspecting the graph.

## Edge types

### `(:Source)-[:CONTAINS]->(:File)`

- **Properties:** none.
- **Who writes:** preflight `upsert_file_node`.
- **Who reads:** future cluster queries.

### `(:File)-[:HAS_CHUNK]->(:Chunk)`

- **Properties:** none.
- **Who writes:** [`indexing/chunker.py`](backend/indexing/chunker.py) `_write_chunks`.
- **Who reads:** orchestrator, file rollup.

### `(:Chunk)-[:NEXT]->(:Chunk)`

Linked-list within a file; ordinal-ordered.

- **Properties:** none.
- **Who writes:** [`indexing/chunker.py`](backend/indexing/chunker.py) (the second pass after MERGE-ing the chunk batch).
- **Who reads:** orchestrator's `_load_chunk_context` reads `(prev:Chunk)-[:NEXT]->(c)` to fetch the previous chunk's content for the continuity hint when `dispatch_mode='sequential'`.

### `(:Chunk)-[:HAS_TAG]->(:Tag)`

The per-chunk tagging edge. **One edge per (chunk, tag, facet) occurrence** in
the current HERB pilot. Re-extracting a chunk wipes existing edges before
creating fresh ones.

| Property | Type | Notes |
|---|---|---|
| `facet` | string | HERB facet: `topic`, `entities`, `activity`, `temporal`, or `evidence`. |
| `w_chunk` | float | HERB derived centrality score computed from the five-facet vector. |
| `w_facet` | float | HERB model-emitted fit score for this tag/facet edge. |
| `run_id` | string | Run that wrote the edge. |
| `cluster` | string \| null | Legacy generic tagger field; not written by current HERB pilot. |
| `canonical_id` | string \| null | Legacy generic tagger field; not written by current HERB pilot. |
| `weight_local` | float \| null | Legacy generic tagger field; not written by current HERB pilot. |

- **Indexes:** `(r.facet)`, `(r.run_id)` for HERB retrieval; legacy indexes may
  still exist on `(r.cluster)` and `(r.canonical_id)`.
- **Who writes:** HERB pilot [`tagging/pipeline.py`](backend/tagging/pipeline.py);
  legacy generic path [`indexing/extraction_writer.py`](backend/indexing/extraction_writer.py).
- **Who reads:** planned retrieval API; legacy [`indexing/file_rollup.py`](backend/indexing/file_rollup.py)
  reads the old generic shape.

### `(:File)-[:TAGGED]->(:Tag)`

Legacy derived edge from the deterministic file rollup. Pure function of the
legacy `HAS_TAG` shape + `Chunk.relevance_to_file`. The current HERB pilot does
not write `TAGGED` rollups; HERB retrieval should read `HAS_TAG` directly.

| Property | Type | Notes |
|---|---|---|
| `cluster` | string | Carried through from `HAS_TAG.cluster`. |
| `canonical_id` | string \| null | Carried through. |
| `weight_global` | float | `sum(coalesce(c.relevance_to_file, 0.5) * r.weight_local) / count(c)` per (file, tag, cluster, canonical_id) group. |
| `n_chunks` | int | Number of chunks in this file that contributed this tag. |
| `run_id` | string | Run that performed the rollup. |
| `updated_at` | iso8601 | |

- **Indexes:** `(r.cluster)`.
- **Who writes:** [`indexing/file_rollup.py`](backend/indexing/file_rollup.py). The rollup **deletes all in-scope `TAGGED` edges first** then creates fresh ones (Cypher MERGE semantics around null `canonical_id` are awkward; pure delete-and-rebuild is safer).
- **Who reads:** future cluster query views (not built yet — planned under `clustering/queries/`).

### `(:CanonicalTagProposal)-[:OBSERVED_IN]->(:Chunk)`

One edge per proposing-occurrence; lets us trace where a proposal came from.

- **Properties:** none (the proposal node carries `observed_count`).
- **Who writes:** [`indexing/extraction_writer.py`](backend/indexing/extraction_writer.py).
- **Who reads:** Future triage CLI.

## Indexes summary

From [`schema/indexes.cypher`](backend/schema/indexes.cypher):

```cypher
CREATE INDEX IF NOT EXISTS FOR (n:File)         ON (n.dataset_id);
CREATE INDEX IF NOT EXISTS FOR (n:File)         ON (n.format_family);
CREATE INDEX IF NOT EXISTS FOR (n:Chunk)        ON (n.file_id);
CREATE INDEX IF NOT EXISTS FOR (n:Chunk)        ON (n.empty);
CREATE INDEX IF NOT EXISTS FOR (n:CanonicalTag) ON (n.cluster);
CREATE INDEX IF NOT EXISTS FOR ()-[r:HAS_TAG]-() ON (r.facet);
CREATE INDEX IF NOT EXISTS FOR ()-[r:HAS_TAG]-() ON (r.run_id);
CREATE INDEX IF NOT EXISTS FOR ()-[r:HAS_TAG]-() ON (r.cluster);
CREATE INDEX IF NOT EXISTS FOR ()-[r:HAS_TAG]-() ON (r.canonical_id);
CREATE INDEX IF NOT EXISTS FOR ()-[r:TAGGED]-()  ON (r.cluster);

// HERB hard-field gate (materialize stage) — only the gated fields:
CREATE INDEX chunk_product/section/channel/employee_id/kind ...;
CREATE FULLTEXT INDEX chunk_fulltext FOR (c:Chunk) ON EACH [c.content, c.description, c.question];
```

`schema/vector_indexes.cypher` is **no longer empty**: it creates `tag_embedding`, the native 384-d cosine VECTOR index on `:Tag(embedding)` written by `python -m tagging embed-tags` (the prompt-tag grounding bridge). Embeddings are live, not deferred — the older "deferred" note is obsolete.

## Quick reference for property placement

| Concept | Lives on | Why |
|---|---|---|
| `dispatch_mode` | `:File` property | Determined per file at preflight; the orchestrator branches on it. |
| `relevance_to_file` | `:Chunk` property | Per-chunk score from the file orchestrator. Used by rollup. |
| `facet` | HERB `(:Chunk)-[:HAS_TAG]->(:Tag)` edge property | The retrieval dimension for the tag occurrence. |
| `w_chunk` | HERB `(:Chunk)-[:HAS_TAG]->(:Tag)` edge property | Derived centrality of the tag in the chunk. |
| `w_facet` | HERB `(:Chunk)-[:HAS_TAG]->(:Tag)` edge property | Fit of the tag to this facet. |
| `weight_local` | Legacy `(:Chunk)-[:HAS_TAG]->(:Tag)` edge property | Per-chunk tag saliency in the old generic path. |
| `weight_global` | Legacy `(:File)-[:TAGGED]->(:Tag)` edge property | Aggregate of `relevance_to_file * weight_local`. |
| `canonical_id` | Legacy `(:Chunk)-[:HAS_TAG]->(:Tag)` and `(:File)-[:TAGGED]->(:Tag)` edges | Per-attribution mapping; `null` when the tag is a proposal. |
| `cluster` | Legacy `(:Chunk)-[:HAS_TAG]->(:Tag)` and `(:File)-[:TAGGED]->(:Tag)` edges | The same Tag name can be in different clusters across occurrences. |

# Status

**TL;DR.** Truthful snapshot of what is verified, what is built but unverified end-to-end, and what is open. The bootstrap path (constraints + indexes + canonical seed) is verified. The full chunk → file → rollup pipeline is built and unit-shaped, but a fresh end-to-end run on the current clean DB has not been re-confirmed in this documentation pass. Use the "next recommended step" at the bottom as a starting point.

**When to read this.** Before promising a feature is "done". Before estimating remaining work. After every significant code change — update this doc.

**Last updated:** 2026-05-07.

## Touched paths

This doc references everything; updates affect `docs/status.md` only.

## What is verified working

| Item | Evidence |
|---|---|
| `scripts/bootstrap_schema.py` applies the schema | Last manual run reported `Applied 18 schema statements; merged 32 canonical tags.` 18 = 7 uniqueness constraints (`Source`, `File`, `Chunk`, `Run`, `WorkItem`, `CanonicalTagProposal`, `Tag`) + 1 NODE KEY (`CanonicalTag`) + 7 node indexes + 3 relationship indexes (`vector_indexes.cypher` is empty). 32 = full canonical tag count from [`clustering/canonical_seed.yaml`](../clustering/canonical_seed.yaml) (theme 6 + object_entity 7 + event_process 7 + time_relevance 5 + information_need 7). |
| Neo4j auth via `neo4j://` | Reported working against a local self-hosted Neo4j 5.x using `neo4j://localhost:7687` with the `NEO4J_DATABASE=exjobbet_index` multi-DB setup created via [`schema/create_database.cypher`](../schema/create_database.cypher). |
| Pydantic schema enforcement at the agent boundary | [`agents/client.AgentClient.call`](../agents/client.py) validates the model output via `schema.model_validate_json` and produces `error_class="schema_invalid"` on failure. Covered by the schema validators in [`agents/schemas.py`](../agents/schemas.py). |
| Idempotency rules | [`Chunker.chunk_file`](../indexing/chunker.py) early-returns when chunks exist; preflight upserts `:Source` and `:File` with `MERGE`; bootstrap uses `IF NOT EXISTS` everywhere. |

## What is built but not yet end-to-end verified

The following are written, type-clean, and reviewed in source but no green run-against-current-clean-DB result is recorded for this documentation pass:

- **Orchestrator + writers + rollup.** [`indexing/orchestrator.py`](../indexing/orchestrator.py), [`indexing/extraction_writer.py`](../indexing/extraction_writer.py), [`indexing/file_writer.py`](../indexing/file_writer.py), [`indexing/file_rollup.py`](../indexing/file_rollup.py). Three-stage pipeline with `BreakerTripped` propagation and per-batch `asyncio.gather`. Schema-validation-then-write logic (chunk_end_offset echo, chunk_relevance set equality) is in place but a smoke run that exercises both the propose path and the empty-verdict path against a real LLM has not been re-confirmed today.
- **Preflight against the current clean DB.** [`scripts/run_preflight.py`](../scripts/run_preflight.py). Per-file fault isolation is implemented; the `failures` list is printed at the end. Whether the four bundled datasets (`Salesforce__HERB`, `VLR-CVC__DocVQA-2026`, `wenhu__hybrid_qa`, `fever__feverous`) all preflight cleanly today depends on their current contents under `data/raw/`.
- **Small `run_index` smoke.** With `--chunk-limit 5 --file-limit 1` against a tiny dataset, the path should complete and produce non-empty `:Run` totals plus a few `(:File)-[:TAGGED]->(:Tag)` edges. Recommended as the first verification step after re-bootstrap.

## Known gaps

- **Parquet streaming for very large files.** [`Chunker._chunk_parquet`](../indexing/chunker.py) iterates `pyarrow.ParquetFile.iter_batches(batch_size=512)` and converts to Python dicts row-by-row. Bytes/bytearray are placeholdered with `<bytes N bytes>`. Files with deeply nested struct rows (lists of dicts of arrays of …) can still produce huge JSON content per row; nothing today caps `content` size. Failure is per-file isolated by preflight.
- **Nested-struct → JSON conversion.** Same code path. A schema-aware flattener or a hard cap on chunk `content` length would make HF parquet rows safer.
- **Proposal triage CLI.** [`clustering/canonical_seed.yaml`](../clustering/canonical_seed.yaml) refers to `python -m clustering.review` as the entry point for promoting `:CanonicalTagProposal` nodes into the seed. **No such module exists** in the repo. Today, proposals accumulate but never get promoted.
- **`clustering/queries/*.cypher`.** Not built. Planned named views are `by_theme`, `by_information_need`, `recent_active`, `multidim`.
- **`exports/`.** Not built. No JSON snapshots are produced anywhere in the live pipeline.
- **`provenance.json`.** No per-run provenance dump is written today. `:Run` properties cover the basics (run_id, model, concurrency, summary counters), but a structured provenance file is not.
- **Vector indexes / embeddings.** [`schema/vector_indexes.cypher`](../schema/vector_indexes.cypher) is intentionally empty. `EMBEDDING_MODEL` env var is loaded into `Settings.embedding_model` but consumed nowhere. Reintroduction candidates: `Chunk.embedding`, `CanonicalTag.label_embedding`.

## Decisions to revisit later

- **Agent-negotiated chunking for sequential files.** Today every file is chunked deterministically (Path A). For long-form text (PDF/HTML/DOCX/MD/TXT) we already pass a continuity hint; the next step is letting the agent propose splits that respect semantic boundaries. Defer until we have a query workload to optimise against. See [`architecture.md`](architecture.md#d1--path-a-deterministic-chunker).
- **Vector indexes and embeddings.** Will likely re-enter the design once the canonical vocabulary is stable enough that semantic similarity becomes useful for "is this raw tag the same as canonical X?" decisions.
- **Cascade classifier.** Decision today is one-shot extraction-and-mapping ([decision D5](architecture.md#d5--one-shot-agent-call-extraction--canonical-mapping)). If schema_invalid rates climb or canonical mapping accuracy lags, revisit and add a separate classification prompt.
- **Sequential dispatch for long-form files.** Today `dispatch_mode='sequential'` only changes the prompt content (continuity hint), not the dispatch order. True serial dispatch with shared context across chunks is open.
- **Token / size caps on `Chunk.content`.** Storing the full content (decision D10) is fine until a single chunk blows the prompt budget. We need a hard cap or a smarter chunker for the worst-case parquet rows.

## Last verified action

`scripts/bootstrap_schema.py` — produced `Applied 18 schema statements; merged 32 canonical tags.` against the `exjobbet_index` database via `neo4j://`. Auth is confirmed working with the credentials currently in `.env`.

## Next recommended step

Re-run, in order, against the current clean DB:

1. `python scripts/run_preflight.py` and confirm `failures = 0` (or note which files fail and why).
2. `python scripts/run_index.py --chunk-limit 5 --file-limit 1` (smoke).
3. `python scripts/verify_graph.py` and check `(:Source)`, `(:File)`, `(:Chunk)` counts plus a non-zero number of `(:Chunk)-[:HAS_TAG]->(:Tag)` and `(:File)-[:TAGGED]->(:Tag)` edges.
4. Update this `status.md` with the result (move items from "built but not yet end-to-end verified" into "verified working").

If step 1 surfaces parquet OOM/nested-struct failures, that's the first known gap to close — see "Known gaps" above.

## Self-flagged half-truths in this doc

(Things the human reviewer may want to challenge.)

- The "18 statements + 32 tags" numbers are **derived from the source files**, not from a freshly observed run today. They should be true given the current state of [`schema/constraints.cypher`](../schema/constraints.cypher), [`schema/indexes.cypher`](../schema/indexes.cypher), [`schema/vector_indexes.cypher`](../schema/vector_indexes.cypher), and [`clustering/canonical_seed.yaml`](../clustering/canonical_seed.yaml). If you change any of those, this number drifts.
- The "auth via `neo4j://` confirmed" claim is carried over from prior context. If you've recently rotated credentials or moved the Neo4j instance, re-verify.
- "What is built but not yet end-to-end verified" is asserted on the basis of source review during this documentation pass; no live LLM calls were issued. A green smoke run remains the only way to *verify*.
- The list of bundled datasets matches [`data_access/raw/registry.py`](../data_access/raw/registry.py) and the directory listing under `data/raw/`. Whether the files are *current* (matching upstream HF revisions) is not checked here.

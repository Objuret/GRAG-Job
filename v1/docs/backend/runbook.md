# Runbook

**TL;DR.** HERB thesis path: first-time setup → bring up Neo4j → fill `.env` → bootstrap schema → preflight `Salesforce__HERB` → `python -m tagging materialize` → `python -m tagging extract` → `python -m tagging embed-tags`. The legacy generic path uses `run_index.py` and is not the HERB thesis path. Common failures and recovery steps below.

**When to read this.** Before running anything that talks to Neo4j or OpenAI; when something fails and you need to recover.

**Last updated:** 2026-05-19.

## Touched paths

`.env`, `.env.example`, `scripts/`, `schema/`, `data/raw/`, `indexing/preflight.py`, `indexing/orchestrator.py`, `tagging/`.

## 1. First-time setup

```bash
git clone <this-repo>
cd repo
cd backend

python -m venv .venv
. .venv/Scripts/activate    # Windows
# . .venv/bin/activate      # macOS/Linux

pip install -r requirements-lock.txt

cp .env.example .env
# Edit .env — set at minimum: NEO4J_PASSWORD, NEO4J_DATABASE.
# Add ANTHROPIC_API_KEY for HERB LLM tagging stages.
# Add LLM_API_KEY only for the legacy generic run_index.py path.
# See docs/env_and_config.md for the full table.
```

`.env` is gitignored. Never commit it. Never echo it to logs.

## 2. Bring up Neo4j

Any Neo4j 5.x instance works. Two options:

**Option A — single-DB community.** Use the default `neo4j` database. Set `NEO4J_DATABASE=neo4j` in `.env`. To wipe between experiments: `MATCH (n) DETACH DELETE n` from Browser.

**Option B — multi-DB enterprise.** Create a dedicated database for this project so you don't have to wipe.

```cypher
// In Neo4j Browser, with the top dropdown set to "system":
CREATE DATABASE exjobbet_index IF NOT EXISTS WAIT;
```

Then set `NEO4J_DATABASE=exjobbet_index` in `.env`. The same Cypher lives in [`schema/create_database.cypher`](../../backend/schema/create_database.cypher).

### URI choice: `neo4j://` vs `bolt://`

- `NEO4J_URI=neo4j://localhost:7687` — routing-aware. Recommended even for single-node setups; works with Aura and clusters.
- `NEO4J_URI=bolt://localhost:7687` — direct connection. Sometimes needed for older self-hosted setups or when the routing handshake fails (e.g. behind certain proxies).

Try `neo4j://` first; switch to `bolt://` only if you see `ServiceUnavailable: Unable to retrieve routing information`.

## 3. Bootstrap the schema

```bash
python scripts/bootstrap_schema.py
```

Applies [`schema/constraints.cypher`](../../backend/schema/constraints.cypher), [`schema/indexes.cypher`](../../backend/schema/indexes.cypher), and [`schema/vector_indexes.cypher`](../../backend/schema/vector_indexes.cypher), including the per-facet `tag_emb_<facet>` `:Tag` vector indexes used by the workbench grounding path. It does not seed tag vocabularies.

Expected output (paraphrased):

```
Applied 15 schema statements.
```

The exact count depends on the checked-in schema files.

Idempotent. Re-run after editing schema files.

## 4. Preflight: chunk + seed work

Place datasets under `data/raw/<dataset_id>/...`. The expected layout per `data_access/raw/registry.py` is:

```
data/raw/Salesforce__HERB/...
data/raw/VLR-CVC__DocVQA-2026/...
data/raw/wenhu__hybrid_qa/...
data/raw/fever__feverous/...
```

You can use `python -m data_access.raw sync` to download via HuggingFace Hub + curl-style direct URLs (requires `HF_TOKEN` env var or `--hf-token` for private repos). It is not required to use the bundled syncer; any directory tree under `data/raw/<dataset_id>/` works.

Then:

```bash
python scripts/run_preflight.py
```

Output (paraphrased):

```
Pre-flight complete:
  files_seen        = 12
  files_new         = 12
  skipped_no_chunks = 0
  chunks_created    = 542
  working_items_seeded = 554
  failures          = 0
```

If any per-file step raises, preflight prints `[preflight] FAIL <rel_path>: <ErrorClass>: <first line>` and continues with the next file. The full list lands in `result.failures`. Re-running picks up new files and skips files that are already chunked (idempotency rule from [decision D9](architecture.md#d9--re-chunk-only-if-no-chunks-exist-idempotency)).

## 5. HERB thesis tagging path

For the thesis HERB graph, do not use `run_index.py`. Use the HERB-specific
pipeline:

```bash
python scripts/run_preflight.py --dataset-id Salesforce__HERB
python -m tagging materialize
python -m tagging extract
python -m tagging embed-tags
```

`materialize` and `embed-tags` are non-LLM graph maintenance stages.
`extract`, `describe`, and `score` require `ANTHROPIC_API_KEY`.

The current full thesis artefact is already live in Neo4j database `herb` under
`run_id = "pilot_full_herb"`; do not re-run extraction/scoring just to create
an evaluation graph.

## 6. Create the eval-safe HERB graph

For RAG evaluation, build a separate pruned database from the full HERB graph so
retrieval cannot return QA records or upstream oracle product profiles:

```powershell
python scripts/create_herb_eval_db.py --source-db herb --target-db herb-eval --dry-run
python scripts/create_herb_eval_db.py --source-db herb --target-db herb-eval
$env:NEO4J_DATABASE='herb-eval'; python -m tagging embed-tags
```

The builder never mutates `herb`; it copies existing safe chunks, chunk
descriptions, `HAS_TAG` edges, and weights, excluding `answerable_questions`,
`unanswerable_questions`, and `product_profile`. It refuses to overwrite a
non-empty target database unless `--replace` is explicitly passed. File-level
LLM descriptions and old embeddings are intentionally not copied; facet-aware
`:Tag.emb_*` grounding vectors are regenerated on `herb-eval` so prompt
grounding is based only on eval-safe contexts. Verified target after the
current run: 4,869 chunks, 0 excluded chunks, 229,249 `HAS_TAG` edges, 24,781
tags, 96,790 grounding vectors (72,009 facet + 24,781 `all`), 0 file
descriptions, and the six `tag_emb_<facet>` vector indexes ONLINE.

On the current Windows workstation, use the repo-root CUDA venv
(`a:\exjobbet\repo\.venv`) for `embed-tags`; it has `torch 2.6.0+cu124` and
`sentence-transformers 5.5.0`, and `SentenceTransformer` auto-selects the GTX
1080 Ti. Avoid reinstalling plain PyPI `torch` there because it can downgrade
the environment to CPU-only.

## 7. Dispatch the legacy generic indexing run

```bash
python scripts/run_index.py
```

Optional flags:

- `--dataset-id <id>` — limit work to one dataset (matches `:Source.source_id`).
- `--file-id <id>` — limit work to one file (matches `:File.file_id`). Useful for targeted smoke tests.
- `--chunk-limit N` — cap chunk_extraction working-file items this run.
- `--file-limit N` — cap file_orchestration working-file items this run.
- `--concurrency N` — override `LLM_MAX_CONCURRENCY` for this run only.

The legacy generic indexing script:

1. Validates `LLM_API_KEY` (or `AGENT_API_KEY`). Missing → exit code 2 with a Swedish/English error.
2. Opens Neo4j and the agent HTTP client.
3. Creates a `:Run` node (`status='started'`).
4. Resets all `failed` working-file items to `unrun` (auto-retry policy).
5. Loads the legacy extraction prompt context.
6. Runs Stage 1 (chunks) → Stage 2 (files) → Stage 3 (deterministic rollup).
7. Closes everything in `finally`. `:Run.status` becomes `ok` or `aborted`.

Expected console signal:

```
Run started: 2026-05-07T08-12-04Z-9f1a02
[orchestrator] reset N failed work items to unrun
[orchestrator] legacy tag context loaded; dataset_id filter = None
[orchestrator] chunk stage: processed=200 done=199 failed=1
...
[orchestrator] file stage: processed=50 done=50 failed=0
[orchestrator] rollup wrote 1234 (:File)-[:TAGGED]->(:Tag) edges
Run finished: ok
  chunks_done=..., chunks_failed=...
  files_done=..., files_failed=...
  tokens in/out = .../..., duration_ms = ...
```

A `BREAKER TRIPPED:` line on stderr means the orchestrator caught a `BreakerTripped` and the run finished as `aborted`. Exit code 1.

For HERB, `run_index.py` refuses to run the legacy generic tagging path by default. HERB-specific tagging experiments use the separate Anthropic pilot CLI (`python -m tagging <stage>` from `backend/`) documented in [`herb_tagging_schema.md`](herb_tagging_schema.md). The escape hatch `--allow-legacy-herb-tagging` is only for explicit throwaway experiments.

## 8. Verify

```bash
python scripts/verify_graph.py
```

Read-only. Prints source/file/chunk counts, working-file items by kind/status, file breakdown by `format_family`, chunk breakdown by `kind`, and three sample chunk previews.

## Common failure modes and fixes

| Symptom | Likely cause | Fix |
|---|---|---|
| `neo4j.exceptions.AuthError: ... The client is unauthorized due to authentication failure` | Wrong `NEO4J_USER` / `NEO4J_PASSWORD`. | Check `.env`. Reset password in Neo4j Browser if needed. |
| `neo4j.exceptions.ServiceUnavailable: Unable to retrieve routing information` | `neo4j://` routing handshake failed. | Switch `NEO4J_URI` to `bolt://localhost:7687`. |
| `neo4j.exceptions.ConfigurationError: ... database 'exjobbet_index' does not exist` | Multi-DB instance but you skipped the `CREATE DATABASE`. | Run [`schema/create_database.cypher`](../../backend/schema/create_database.cypher) from the `system` DB. |
| `Schema warnings about deprecated CREATE INDEX syntax` | Older Neo4j version. | Upgrade to 5.x. The bootstrap script tolerates idempotent `IF NOT EXISTS` re-runs. |
| `FEL: API-nyckel saknas` / `ERROR: Missing API key` | `LLM_API_KEY`/`AGENT_API_KEY` not set. | Set it in `.env` or as an env var. The script exits early with code 2; nothing was written to Neo4j. |
| `BreakerTripped [http_auth]` | Auth failure to the LLM endpoint. The breaker trips after **1** occurrence. | Verify the API key, base URL, and that the model name is valid for the provider. Re-run. |
| `BreakerTripped [http_quota_exceeded]` | Provider quota / billing problem. Trips after 1 occurrence. | Top up the provider account or rotate the key. |
| `BreakerTripped [http_429]` | 30 consecutive 429s. | Lower `LLM_MAX_CONCURRENCY` (e.g. from 32 to 8). Wait, then re-run. The auto-retry-all on next-run start picks up the failed items. |
| `BreakerTripped [schema_invalid]` | The model is returning JSON that fails pydantic validation > 20% of the last 50 calls. | Inspect failed items in `backend/.work/worklist_<neo4j_database>.json`; their `error_message` shows the validation error. If the prompt drifts, fix [`prompts/extract_chunk.md`](../../backend/prompts/extract_chunk.md) **and** [`agents/schemas.py`](../../backend/agents/schemas.py) in lockstep. |
| Preflight: parquet OOM / nested-struct error | Chunker reads pyarrow batches; deeply nested struct rows can still produce huge JSON content per row. | Today the failure is per-file isolated (preflight continues). Skip the file or refactor `_chunk_parquet` to flatten / cap nested values. See [`status.md`](status.md). |
| Preflight: `_chunk_parquet` reports a chunk too large for Neo4j | Same as above (a single row's JSON exceeds practical size). | Same. Consider truncating `content` in the chunker for parquet rows beyond an ad-hoc cap. |
| Orchestrator silently does nothing | The worklist is empty (all items already `done`). | Check with `python scripts/verify_graph.py` — look at unrun counts. Add new files under `data/raw/`, re-run preflight. |
| `chunk_end_offset mismatch` failures | The model echoed a different number than the orchestrator told it to use. | Usually a transient model glitch; the auto-reset policy will retry next run. If sustained, tighten the wording in [`prompts/extract_chunk.md`](../../backend/prompts/extract_chunk.md). |
| `chunk_relevance must cover every chunk_id exactly once` | The file orchestrator skipped a `chunk_id` or invented one. | Same — usually transient. If sustained, sharpen the file prompt. |

## Re-run after partial failure

You don't need a special command. Just re-run `python scripts/run_index.py`:

1. The orchestrator calls `WorkList.reset_failed_to_unrun` and resets every `failed` item to `unrun`.
2. Items that were already `done` stay `done` and are not pulled.
3. Stage 3 (rollup) re-runs and **deletes all in-scope `TAGGED` edges before recreating them** — this is intentional, see [`indexing/file_rollup.py`](../../backend/indexing/file_rollup.py). It's safe because TAGGED is a pure derivative of HAS_TAG + relevance_to_file.

If the same items keep failing run after run, look at their working-file `error_class` and `error_message` to investigate. Don't paper over a real bug with reruns.

## Wipe and restart cleanly

**Multi-DB enterprise:**

```cypher
:use system
DROP DATABASE exjobbet_index IF EXISTS;
CREATE DATABASE exjobbet_index WAIT;
```

Then re-run `bootstrap_schema.py`, `run_preflight.py`, `run_index.py`.

**Single-DB community:**

```cypher
MATCH (n) DETACH DELETE n;
```

Then re-run bootstrap and preflight.

## Cost / token notes

- One LLM call per chunk + one per chunk-bearing file. With a typical small dataset (~500 chunks, ~50 chunk-bearing files), that's ~550 calls per run.
- `LLM_MAX_CONCURRENCY=32` is the default — high enough to be fast, low enough that 429s are rare on a paid OpenAI account. If the provider rate-limits aggressively, drop to 8–16.
- Token usage per chunk depends on chunk content size and prompt context. The orchestrator records `in_tokens`, `out_tokens`, `duration_ms` per working-file item and sums them on `:Run`.
- Breaker thresholds are documented in [`architecture.md`](architecture.md#d7--tight-circuit-breaker-thresholds-table). Trips abort the run; nothing partial is lost — completed working-file items remain `done`, failed ones are reset on next run.

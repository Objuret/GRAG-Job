# Agents

Project-wide brief for the thesis monorepo. Two halves:

- **`backend/`** — offline Python pipeline. Chunks raw datasets, runs LLM tagging, writes the durable graph to Neo4j.
- **`frontend/`** — Vite/React workbench. Local-only. The browser talks directly to Neo4j (`neo4j-driver`) and Anthropic (`@anthropic-ai/sdk`); there is no HTTP server between them.

All production documentation lives in [`docs/`](docs/README.md).

## Mission

Bridge heterogeneous, noisy datasets with a queryable graph artefact. Every payload file becomes a chain of `(:Chunk)` nodes with stable locators and source/file structure. The current HERB semantic layer is the completed `pilot_full_herb` run, archived at `backend/data/tagging_runs/pilot_full_herb_snapshot_20260514T052226Z.zip` and live in the `herb` Neo4j database under `run_id = "pilot_full_herb"`. The frontend reads that graph and runs prompt interpretation in the browser.

## Hard rules

- **Neo4j is the only durable store.** All indexing artefacts live in the graph. Scheduler/job state lives in `backend/.work/`, not in the graph.
- **Fail loud.** One model provider per runner: the legacy indexing path uses one OpenAI-compatible LLM endpoint (configured via `LLM_*` env; legacy `AGENT_*` honoured, `LLM_*` wins). The HERB tagging pilot uses Anthropic via `ANTHROPIC_*`. No local-model fallback, no mocks, no parquet/JSON side artefacts.
- **The agent client returns, never raises.** [`backend/agents/client.py`](backend/agents/client.py) catches every `httpx`/schema error and returns a typed `AgentResult` with an `error_class`. The orchestrator decides what to do.
- **Per-error-class circuit breaker.** Tight thresholds in [`backend/indexing/breaker.py`](backend/indexing/breaker.py). Trips raise `BreakerTripped`; the run finishes as `aborted` and exits with code 1.
- **Working-file job ledger drives scheduling.** Files that produce zero chunks (images, archives) remain in the graph as `:File` metadata but are skipped by the LLM worklist. Auto-retry-all on the next run.
- **Cluster lives on the HAS_TAG edge.** `(:Tag)` is unique on `name` only; the cluster/facet is a per-occurrence edge property — the same tag name can be `temporal` in one chunk and `activity` in another.
- **Frontend is local-only and browser-direct.** Neo4j and Anthropic are reached directly from the browser. Credentials in the local bundle are acceptable because the app is not deployed publicly.
- **HERB field-name discipline.** HERB retrieval uses `facet`, `w_chunk`, `w_facet`, `relevance_to_file`. Legacy `cluster`, `canonical_id`, `weight_local`, `weight_global` belong only to the old generic-tagger path.
- **Secrets are gitignored and unloggable.** `.env` is never committed and never echoed into output, logs, or graph properties.

## High-level architecture

```mermaid
flowchart LR
    raw["backend/data/raw/<br/>payload files"] --> preflight["preflight<br/>(scan + upsert + chunk + seed worklist)"]
    preflight --> herb["tagging/pipeline.py<br/>(HERB Anthropic two-pass)"]
    preflight -. "legacy/non-HERB only" .-> orch["indexing/orchestrator.py<br/>(legacy three-stage dispatcher)"]
    herb --> graph["Neo4j<br/>(:Source)-[:CONTAINS]->(:File)-[:HAS_CHUNK]->(:Chunk)-[:HAS_TAG]->(:Tag)"]
    orch --> graph
    graph --> browser["frontend (browser)<br/>neo4j-driver + @anthropic-ai/sdk<br/>prompt interpretation + retrieval"]
```

## The five facets

| Facet | Meaning |
|---|---|
| `topic` | Subject matter |
| `entities` | Named people, organisations, products, systems, places |
| `activity` | Actions, processes, events |
| `temporal` | Dates and time expressions |
| `evidence` | Information kind: definition, example, metric, argument, procedure, case study, citation, link, etc. |

Same five facets are used by HERB chunk tagging and browser-side prompt interpretation. Defined positively in `backend/agents/schemas.py` (`Cluster` Literal) and used as edge properties on `(:Chunk)-[:HAS_TAG]->(:Tag)`.

## Where to look

- Graph contract: [`docs/graph_schema.md`](docs/graph_schema.md)
- Backend architecture + decision log: [`docs/backend/architecture.md`](docs/backend/architecture.md)
- Frontend architecture: [`docs/frontend/architecture.md`](docs/frontend/architecture.md)
- Prompt interpretation (browser-side): [`docs/frontend/query_interpretation_layer.md`](docs/frontend/query_interpretation_layer.md)
- HERB tagging method: [`docs/backend/herb_tagging_schema.md`](docs/backend/herb_tagging_schema.md), [`docs/backend/herb_tagging_frames.md`](docs/backend/herb_tagging_frames.md)
- Current HERB artefact: [`docs/backend/pilot_full_herb_report.md`](docs/backend/pilot_full_herb_report.md)
- Backend runbook + env: [`docs/backend/runbook.md`](docs/backend/runbook.md), [`docs/backend/env_and_config.md`](docs/backend/env_and_config.md)
- Backend file-by-file map: [`docs/backend/codebase_map.md`](docs/backend/codebase_map.md)
- LLM prompts catalogue: [`docs/backend/prompts.md`](docs/backend/prompts.md)
- Live status: [`docs/backend/status.md`](docs/backend/status.md), [`docs/frontend/status.md`](docs/frontend/status.md)
- Next steps: [`docs/frontend/plans.md`](docs/frontend/plans.md)

## End-to-end (backend pipeline)

```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate         # Linux/macOS: . .venv/bin/activate
pip install -r requirements-lock.txt
cp .env.example .env                                      # set NEO4J_PASSWORD, ANTHROPIC_API_KEY, LLM_API_KEY

python scripts/bootstrap_schema.py                        # idempotent
python scripts/run_preflight.py                           # idempotent
python -m tagging extract                                 # HERB Anthropic pilot (current path)
python scripts/run_index.py                               # legacy generic path; refuses HERB unless --allow-legacy-herb-tagging
python scripts/verify_graph.py                            # read-only counts
```

## End-to-end (frontend)

```bash
npm install
npm run dev                                               # http://127.0.0.1:5173/
```

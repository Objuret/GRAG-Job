# Thesis Indexing Pipeline

Multi-layer indexing/clustering pipeline that takes heterogeneous datasets under `data/raw/`, deterministically chunks every payload file, asks one OpenAI-compatible LLM to extract a five-cluster tag set (`topic`, `entities`, `activity`, `temporal`, `evidence`) per chunk plus a file-level relevance map, and rolls everything up into a queryable Neo4j graph. **Neo4j is the only durable artefact.** No fallbacks, no mocks, fail loud.

## Documentation

Full documentation lives in **[`docs/`](docs/README.md)**. If you are an AI agent picking up this codebase, start with **[`docs/agent_brief.md`](docs/agent_brief.md)**. The graph schema is the contract — see **[`docs/graph_schema.md`](docs/graph_schema.md)**.

## Quick start

```bash
git clone <this-repo> && cd repo
cd backend
python -m venv .venv
. .venv/Scripts/activate           # Windows; macOS/Linux: . .venv/bin/activate
pip install -r requirements-lock.txt

cp .env.example .env
# Fill in: LLM_API_KEY, NEO4J_PASSWORD, NEO4J_DATABASE.
# See docs/env_and_config.md for every variable.

# (Optional) Sync the bundled datasets from HuggingFace + direct URLs.
python -m data_access.raw sync

# Apply schema + seed canonical tags. Idempotent.
python scripts/bootstrap_schema.py

# Scan data/raw/, upsert :Source/:File, chunk, seed WorkItems. Idempotent.
python scripts/run_preflight.py

# Dispatch agent calls (chunks then files), then deterministic rollup.
python scripts/run_index.py

# Inspect.
python scripts/verify_graph.py
```

`run_index.py` accepts `--dataset-id`, `--chunk-limit`, `--file-limit`, `--concurrency`. Failures auto-retry on the next run. See [`docs/runbook.md`](docs/runbook.md) for failure modes and recovery.

## Layout

- `agents/` — single OpenAI-compatible HTTP client and pydantic schemas.
- `indexing/` — chunker, worklist, runs, orchestrator, writers, deterministic rollup, circuit breaker.
- `clustering/` — canonical tag vocabulary; future query views.
- `data_access/` — dataset sync and profiling (upstream of the index).
- `prompts/` — LLM system prompts (one per orchestrator stage).
- `schema/` — Cypher constraints/indexes applied at bootstrap.
- `scripts/` — operator entry points.
- `shared/` — config, Neo4j client, small utilities.
- `docs/` — this project's durable, agent-readable documentation.

## License / status

Research code in active development. Treat the graph schema (`docs/graph_schema.md`) as the public contract; everything else may move.

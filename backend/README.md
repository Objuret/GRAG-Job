# Thesis indexing pipeline

Offline Python pipeline. Chunks raw datasets under `data/raw/`, tags chunks with LLMs (HERB via Anthropic; legacy generic path via OpenAI-compatible HTTP), and writes the durable graph to Neo4j. Neo4j is the only durable artefact.

```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate    # Linux/macOS: . .venv/bin/activate
pip install -r requirements-lock.txt
cp .env.example .env                                 # set NEO4J_PASSWORD, ANTHROPIC_API_KEY, LLM_API_KEY

python scripts/bootstrap_schema.py
python scripts/run_preflight.py
python -m tagging extract                            # HERB Anthropic path (current)
python scripts/verify_graph.py                       # read-only counts
```

`scripts/run_index.py` runs the legacy generic tagging path; it refuses HERB unless `--allow-legacy-herb-tagging` is passed.

Docs: [`../docs/`](../docs/README.md) (backend-specific under `../docs/backend/`). Agents: [`../AGENTS.md`](../AGENTS.md).

## Layout

- `agents/` — single OpenAI-compatible HTTP client and pydantic schemas (legacy path).
- `indexing/` — chunker, worklist, runs, orchestrator, writers, deterministic rollup, circuit breaker.
- `tagging/` — HERB Anthropic tagging pilot harness.
- `clustering/` — placeholder for future HERB query views.
- `data_access/` — dataset sync, raw-tree scan, classification.
- `prompts/` — LLM system prompts (one per orchestrator stage; plus pilot variants).
- `schema/` — Cypher constraints/indexes applied at bootstrap.
- `scripts/` — operator entry points.
- `shared/` — config, async Neo4j wrapper, small utilities.

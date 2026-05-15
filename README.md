# Thesis monorepo

Two halves of one system:

- **`backend/`** — offline Python pipeline. Chunks raw datasets, tags with LLMs, writes the durable graph to Neo4j.
- **`frontend/`** — Vite/React workbench. Local-only browser app. Reads the graph and runs prompt interpretation directly from JavaScript (`neo4j-driver` + `@anthropic-ai/sdk`); no HTTP server between them.

Documentation: **[`docs/`](docs/README.md)**. AI agents start at **[`AGENTS.md`](AGENTS.md)**. **HERB-first** joint map: **[`docs/system_map.md`](docs/system_map.md)**. **Legacy stack:** excluded from Cursor indexing via **`.cursorignore`** — manifest [`quarantine/DO_NOT_READ_UNLESS_LEGACY.md`](quarantine/DO_NOT_READ_UNLESS_LEGACY.md).

## Quick start

```bash
git clone <this-repo> && cd repo

# Backend pipeline — one-time, builds the Neo4j graph
cd backend
python -m venv .venv && . .venv/Scripts/activate           # Linux/macOS: . .venv/bin/activate
pip install -r requirements-lock.txt
cp .env.example .env                                       # fill in NEO4J_PASSWORD, ANTHROPIC_API_KEY
python scripts/bootstrap_schema.py
python scripts/run_preflight.py
python -m tagging extract                                  # HERB tagging (current path)

# Frontend — the app
cd ../
npm install
npm run dev                                                # http://127.0.0.1:5173/
```

## Layout

- `backend/` — Python indexing pipeline; runs offline to build/refresh the Neo4j graph artefact.
- `frontend/` — Vite/React workbench (`src/App.jsx`); two-lane canvas, draggable query modules. Browser-direct architecture.
- `docs/` — project-wide reference. Module-specific docs under `docs/backend/` and `docs/frontend/`. The cross-cutting Neo4j contract is `docs/graph_schema.md`.
- `graph_export/` — portable graph snapshots; operator artefact, not part of the indexing path.

## Branches

- `main` — stable history.
- `dev` — shared integration.
- personal branches off `dev` (e.g. `djuret/monorepo`).

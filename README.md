# Exjobbet Monorepo

This repository contains the thesis indexing system and its interface in one tree.

## Layout

- [`backend/`](backend/) - Python indexing pipeline. It chunks raw datasets, calls one OpenAI-compatible LLM endpoint, and writes the durable graph to Neo4j.
- [`frontend/`](frontend/) - Vite/React workbench interface. It is currently a frontend prototype using synthetic mock data.

Root is intentionally small: repo-level `README.md`, `AGENTS.md`, `.gitignore`, and Git metadata live here. Service-specific files live under their service folder.

## Fresh Clone

```bash
git clone <this-repo>
cd repo
npm install
npm run dev
```

The frontend opens at http://127.0.0.1:5173/.

Use the root npm commands as the project default:

- `npm install` - install frontend workspace dependencies.
- `npm run dev` - start the frontend dev server.
- `npm run build` - type-check and build the frontend.

## Backend

```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements-lock.txt

cp .env.example .env
python scripts/bootstrap_schema.py
python scripts/run_preflight.py
python scripts/run_index.py
```

Backend docs start at [`backend/docs/README.md`](backend/docs/README.md). Agents should start with [`backend/docs/agent_brief.md`](backend/docs/agent_brief.md).

## Frontend

```bash
npm run dev
```

Frontend docs start at [`frontend/docs/README.md`](frontend/docs/README.md). Agents should start with [`frontend/AGENTS.md`](frontend/AGENTS.md).

## Branches

- `main` - stable history.
- `dev` - shared integration branch.
- personal branches - branch from `dev`, for example `djuret/monorepo`.

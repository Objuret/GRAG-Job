# Agents

This is now a monorepo with two project roots:

- [`backend/`](backend/) - the Neo4j-backed Python indexing pipeline.
- [`frontend/`](frontend/) - the Vite/React workbench interface.

## Start Here

- Backend work: read [`backend/AGENTS.md`](backend/AGENTS.md), then [`backend/docs/agent_brief.md`](backend/docs/agent_brief.md).
- Frontend work: read [`frontend/AGENTS.md`](frontend/AGENTS.md), then [`frontend/docs/README.md`](frontend/docs/README.md).
- Cross-cutting work: read both service-specific `AGENTS.md` files before editing.

## Root Rules

- Keep service-specific code, docs, config templates, and commands inside `backend/` or `frontend/`.
- Keep only monorepo-wide orientation and ignore rules at the repository root.
- Never echo `.env` contents, API keys, tokens, or passwords into any file or log.
- Backend durability still means Neo4j only. Do not add parquet/JSON side artefacts to the indexing path.

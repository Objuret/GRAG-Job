# Antigrav Interface

Vite/React workbench prototype for the thesis pipeline interface.

The app currently uses synthetic mock data only. Keep real datasets, credentials, local paths, and run IDs out of the frontend unless the API/client contract is intentionally changed.

## Quick Start

From the monorepo root:

```bash
npm install
npm run dev
```

The dev server opens at http://127.0.0.1:5173 by default. After installing from the root, `npm run dev` also works inside `frontend/`.

## Docs

- [`AGENTS.md`](AGENTS.md) - implementation rules for agents and humans.
- [`docs/README.md`](docs/README.md) - frontend documentation index.
- [`docs/api.md`](docs/api.md) - current mock API contract and backend swap guide.

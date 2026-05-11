# HTTP API (planned)

The workbench UI (`src/App.jsx`) currently reads the **node registry and demo samples** from `src/data/workbenchData.ts` and does not call a server.

When a thin query service exists (recommended: Node + `neo4j-driver` in front of the same Neo4j database the Python `backend/` pipeline writes to), it should expose something like the following so the UI can drop static demo text and show real graph state.

---

## Shape (sketch)

| Method | Route | Purpose |
|--------|--------|--------|
| `GET` | `/api/health` | Liveness |
| `GET` | `/api/datasets` | List `(:Source)` with counts |
| `GET` | `/api/datasets/:id/files` | Files for a source, optional format filter |
| `GET` | `/api/files/:id/chunks` | Chunks + `HAS_TAG` for a file |
| `GET` | `/api/files/:id/tags` | File-level `TAGGED` rollups |
| `POST` | `/api/retrieval` | Body: `RetrievalConfig` from `src/types/index.ts` — returns `RetrievalResult` |

Response JSON must match the interfaces in `src/types/index.ts`.

---

## CORS

Allow the Vite dev origin (`http://localhost:5173`) when the API runs on another port.

---

## UI integration

1. Add a small `fetch` client module (e.g. `src/api/client.ts`) with typed methods.  
2. Replace reads of `workbenchData.ts` for **live** paths (datasets, chunks, retrieval) with that client.  
3. Keep `workbenchData.ts` for **node metadata** (labels, `STAGE_PAYLOADS` structure) or move that into a static `registry` object only.

This file used to describe a `mockApi` class; that layer was removed as redundant with no backend and a dead TS shell.

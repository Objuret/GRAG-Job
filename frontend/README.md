# Antigrav Interface

Vite/React workbench for graph-RAG (`backend/` writes Neo4j; this UI is the exploration shell).

## Current stack

- **Entry:** `src/main.tsx` → `src/App.jsx`  
- **Lanes:** Pipeline (Dataset ... Clusters) + Usage (Prompt ... Output) + bridge edge
- **Query modules:** draggable query containers with fragment steps for `topic`, `entities`, `activity`, `temporal`, and `evidence`
- **Data:** `src/data/workbenchData.ts` — node/query registry + demo samples until a query API exists
- **Composition:** `src/query/queryModuleSyntax.ts` — query-fragment Cypher defaults and human-readable summaries

## Dev

```bash
npm install   # from repo root or frontend/
npm run dev
```

http://127.0.0.1:5173/

## Docs

- [`AGENTS.md`](AGENTS.md)  
- [`docs/README.md`](docs/README.md)  

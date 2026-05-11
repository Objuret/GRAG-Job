# AGENTS.md — Onboarding for AI Models

Read this before touching any code.

---

## What This Is

A **frontend-only workbench** for graph-backed retrieval. The shipped UI is **`src/App.jsx`** (`main.tsx`). It uses `@xyflow/react` with two lanes plus draggable query modules:

1. **Pipeline:** Dataset → Access Layer → Index Layer → Tags → Clusters  
2. **Usage:** Prompt → Interpreter → Graph Query → Retrieval → Output  

A dashed edge connects **Clusters → Graph Query**.

**Data:** Node definitions, query-fragment registry, and demo samples live in **`src/data/workbenchData.ts`** (synthetic labels until a query API exists). Query-module Cypher/narrative composition lives in **`src/query/queryModuleSyntax.ts`**. There is **no** mock API client — that layer was removed as redundant.

The Python **`backend/`** builds Neo4j; nothing in this bundle queries Neo4j yet.

```
npm run dev
```

→ http://localhost:5173/

---

## File Map

```
src/
├── main.tsx                 ← Vite entry
├── App.jsx                  ← Active workbench (canvas + panels inline)
├── data/workbenchData.ts    ← PIPELINE_NODES, USAGE_NODES, query fragments, demo payloads
├── query/queryModuleSyntax.ts ← Query module fragment defaults + composition helpers
├── types/index.ts           ← Shared TypeScript types
├── api/                     ← Empty placeholder — add typed fetch client when HTTP exists
├── index.css
docs/                        ← See docs/README.md
```

---

## Rules

1. **Registry data** — extend `workbenchData.ts` for node/query metadata; keep synthetic ids for demos.
2. **Types** — shared shapes live in `types/index.ts`.
3. **Query fragments** — keep default Cypher and human-readable wording in `query/queryModuleSyntax.ts`.
4. **One active shell** — `src/main.tsx` routes to `src/App.jsx`; `frontend/updated/` is a tracked legacy static prototype, not the app.

---

## React Flow

**`@xyflow/react` 12.x** — see `docs/architecture.md`.

---

## Read Next

- `docs/architecture.md`  
- `docs/status.md`  
- `docs/api.md` — planned HTTP surface  
- `src/types/index.ts`  

# AGENTS.md — Onboarding for AI Models

Read this before touching any code.

---

## What This Is

A **frontend-only workbench** for graph-backed retrieval. The shipped UI is **`src/App.jsx`** (`main.tsx`). It uses `@xyflow/react` with two lanes:

1. **Pipeline:** Dataset → Access Layer → Index Layer → Tags → Clusters  
2. **Usage:** Prompt → Interpreter → Graph Query → Retrieval → Output  

A dashed edge connects **Clusters → Graph Query**.

**Data:** Node definitions and demo samples live in **`src/data/workbenchData.ts`** (synthetic labels until a query API exists). There is **no** mock API client — that layer was removed as redundant.

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
├── data/workbenchData.ts    ← PIPELINE_NODES, USAGE_NODES, STAGE_PAYLOADS, PRESET_RESULTS, SAMPLE_CHUNKS
├── types/index.ts           ← Shared TypeScript types
├── api/                     ← Empty placeholder — add typed fetch client when HTTP exists
├── index.css
docs/                        ← See docs/README.md
```

---

## Rules

1. **Registry data** — extend `workbenchData.ts` for node metadata; keep synthetic ids for demos.
2. **Types** — shared shapes live in `types/index.ts`.
3. **No duplicate shells** — do not reintroduce a parallel `Workbench.tsx` + fake API without wiring it to `main.tsx`.

---

## React Flow

**`@xyflow/react` 12.x** — see `docs/architecture.md`.

---

## Read Next

- `docs/architecture.md`  
- `docs/status.md`  
- `docs/api.md` — planned HTTP surface  
- `src/types/index.ts`  

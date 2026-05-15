# Architecture

## Overview

**Entry:** `src/main.tsx` → **`src/App.jsx`**.

Single-file workbench: React Flow canvas, inline catalog, inspector, query-module editor, edge drawer, and bottom comparison strip. Demo copy and registry live in **`src/data/workbenchData.ts`**.

The app is **local-only**. The browser talks directly to:

- **Neo4j** via [`neo4j-driver`](https://www.npmjs.com/package/neo4j-driver) (bolt-ws to localhost) as a **read-only** Neo4j user.
- **Anthropic** via [`@anthropic-ai/sdk`](https://www.npmjs.com/package/@anthropic-ai/sdk) with `dangerouslyAllowBrowser: true`. API key in `.env.local` as `VITE_ANTHROPIC_API_KEY`.

There is no HTTP server in the middle. The Python `backend/` is an **offline pipeline** that builds the Neo4j graph; it is not part of running the app.

---

## Canvas: two lanes + bridge

**Pipeline:** Dataset → Access Layer → Index Layer → Tags → Facets  

**Usage:** Prompt → Interpreter → Retrieval → Graph Query → Output  

**Bridge:** Facets → Graph Query (dashed).

In this canvas, the pipeline node **Access Layer** names the backend **access layer** (inventory, typing, stable keys, paths, payload rules, and `:Source` / `:File` anchors so the graph points at real files). It is not “only” a folder listing and not semantic tagging. **Index Layer** is the Neo4j graph artefact. **Tags** and **Facets** are graph-scope controls used to include, remove, or compare `HAS_TAG` facet dimensions.

Registry splits: `PIPELINE_NODES`, `USAGE_NODES`, combined as `NODE_TYPES`.

**Query modules:** draggable `queryGroup` containers can sit between Retrieval and Graph Query. A module gets an auto-seeded `qf_start` fragment and can contain chained fragment nodes for `topic`, `entities`, `activity`, `temporal`, and `evidence`. The inspector has a plain-language view plus a technical Cypher view.

---

## Module map

```
src/
├── main.tsx
├── App.jsx                    # All UI composition
├── data/workbenchData.ts      # Node registry + demo payloads (PRESET_RESULTS, SAMPLE_CHUNKS, …)
├── query/queryModuleSyntax.ts # Query fragment defaults and composition helpers
├── types/index.ts
└── index.css
```

---

## Data flow

```
workbenchData.ts       ──imports──▶  App.jsx  (registry + demo lane results)
queryModuleSyntax.ts   ──imports──▶  App.jsx  (query module composition)
```

When the live path is wired, `App.jsx` will:

1. Use `neo4j-driver` directly to read datasets / files / chunks / tags from the local Neo4j.
2. Use `@anthropic-ai/sdk` directly for prompt interpretation and answer generation. See [`query_interpretation_layer.md`](query_interpretation_layer.md) for the two-pass method and plan shape.
3. Display the query plan beside the retrieved results, so the user can see what the model thought the prompt meant.

Field-name discipline: the HERB graph uses `facet`, `w_chunk`, `w_facet`, `relevance_to_file`; the frontend read path should use those names.

---

## State

Local React state in `App.jsx` only (`useState` / `useMemo` / refs for undo, redo, and clipboard). No workspace persistence in the current entrypoint.

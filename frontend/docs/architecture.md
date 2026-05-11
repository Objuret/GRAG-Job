# Architecture

## Overview

**Entry:** `src/main.tsx` → **`src/App.jsx`**.

Single-file workbench: React Flow canvas, inline catalog, inspector, query-module editor, edge drawer, and bottom comparison strip. **No HTTP client** in-tree yet — demo copy and registry live in **`src/data/workbenchData.ts`**.

Indexing / Neo4j writes live in **`backend/`** (Python). A future **Node (or other) query API** should read the same Neo4j database; see `docs/api.md`.

---

## Canvas: two lanes + bridge

**Pipeline:** Dataset → Access Layer → Index Layer → Tags → Clusters  

**Usage:** Prompt → Interpreter → Graph Query → Retrieval → Output  

**Bridge:** Clusters → Graph Query (dashed).

Registry splits: `PIPELINE_NODES`, `USAGE_NODES`, combined as `NODE_TYPES`.

**Query modules:** draggable `queryGroup` containers can sit between Interpreter and Graph Query. A module gets an auto-seeded `qf_start` fragment and can contain chained fragment nodes for `topic`, `entities`, `activity`, `temporal`, and `evidence`. The inspector has a plain-language view plus a technical Cypher view.

---

## Module map

```
src/
├── main.tsx
├── App.jsx                    # All UI composition
├── data/workbenchData.ts      # Node registry + demo payloads (PRESET_RESULTS, SAMPLE_CHUNKS, …)
├── query/queryModuleSyntax.ts # Query fragment defaults and composition helpers
├── types/index.ts
├── api/                       # Placeholder — typed fetch client goes here later
└── index.css
```

---

## Data flow

```
workbenchData.ts       ──imports──▶  App.jsx  (registry + demo lane results)
queryModuleSyntax.ts   ──imports──▶  App.jsx  (query module composition)
```

When live: **`src/api/client.ts`** (to be added) **`fetch` → query service → Neo4j**.

---

## State

Local React state in `App.jsx` only (`useState` / `useMemo` / refs for undo, redo, and clipboard). No workspace persistence in the current entrypoint.

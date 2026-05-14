---
trigger: always_on
---

The shipped workbench is **`src/App.jsx`** — two lanes (pipeline vs usage) plus a **Clusters → Graph Query** bridge.

The browser is the whole runtime: it calls Neo4j via `neo4j-driver` (bolt-ws, read-only user) and Anthropic via `@anthropic-ai/sdk` (`dangerouslyAllowBrowser: true`). Live integration goes directly in the workbench or in `src/lib/`.

Demo state lives in `src/data/workbenchData.ts` using synthetic labels.

Two-pass prompt interpretation method: `docs/frontend/query_interpretation_layer.md`.

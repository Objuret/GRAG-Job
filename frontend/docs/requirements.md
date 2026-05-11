# Requirements & Rationale

## Purpose

Frontend workbench modeling **pipeline construction** vs **query usage** as separate lanes, aligned with the thesis Neo4j graph built by **`backend/`**.

## Principles

1. **Two lanes** — graph build vs runtime query; bridge at Clusters → Graph Query.  
2. **Query modules** — users can compose query-plan fragments for `topic`, `entities`, `activity`, `temporal`, and `evidence`.
3. **Registry in data** — `workbenchData.ts` holds node metadata, query-fragment metadata, and demo samples.
4. **Honest demos** — synthetic ids until a real API exists.

## Tech

Vite, React (`App.jsx`), `@xyflow/react`, custom CSS.

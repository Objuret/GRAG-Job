# Requirements & Rationale

## Purpose

Frontend workbench modeling **pipeline construction** vs **query usage** as separate lanes, aligned with the thesis Neo4j graph built by **`backend/`**.

## Principles

1. **Two lanes** — graph build vs runtime query; bridge at Clusters → Graph Query.  
2. **Registry in data** — `workbenchData.ts` holds node metadata and demo samples.  
3. **Honest demos** — synthetic ids until a real API exists.  

## Tech

Vite, React (`App.jsx`), `@xyflow/react`, custom CSS.

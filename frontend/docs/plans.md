# Plans — Next Steps

1. **Query service** — small HTTP API over Neo4j (see `docs/api.md`).  
2. **`src/api/client.ts`** — typed `fetch` matching `src/types/index.ts`.  
3. **`App.jsx`** — call the client for datasets, chunks, retrieval; keep `workbenchData.ts` for node shapes / labels only (or trim further).  
4. **Query module execution** — decide whether `queryModuleSyntax.ts` remains client-authored template composition or becomes a server-owned query-plan contract.
5. **Persistence** — save canvas/module state once the query API exists.

# Frontend documentation

| File | Purpose |
|------|---------|
| [architecture.md](./architecture.md) | Entrypoint, lanes, query modules, data flow |
| [status.md](./status.md) | What works vs planned |
| [api.md](./api.md) | Planned HTTP surface for Neo4j queries |
| [plans.md](./plans.md) | Next implementation steps |
| [requirements.md](./requirements.md) | Short rationale |

**Stack:** Vite · React · `@xyflow/react`

**Entry:** `src/main.tsx` → `src/App.jsx`

**Registry + demos:** `src/data/workbenchData.ts`

**Query composition:** `src/query/queryModuleSyntax.ts`

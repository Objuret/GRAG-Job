# Frontend agents

Local-only Vite/React workbench. The browser talks directly to Neo4j (`neo4j-driver`, bolt-ws to localhost, read-only user) and Anthropic (`@anthropic-ai/sdk` with `dangerouslyAllowBrowser: true`, key in `.env.local` as `VITE_ANTHROPIC_API_KEY`). There is no HTTP server in the middle.

- Project brief: [`../AGENTS.md`](../AGENTS.md)
- Frontend architecture: [`../docs/frontend/architecture.md`](../docs/frontend/architecture.md)
- Prompt interpretation method: [`../docs/frontend/query_interpretation_layer.md`](../docs/frontend/query_interpretation_layer.md)
- Graph contract: [`../docs/graph_schema.md`](../docs/graph_schema.md)
- Status / plans: [`../docs/frontend/status.md`](../docs/frontend/status.md), [`../docs/frontend/plans.md`](../docs/frontend/plans.md)

Graph scope levers (dataset, facets, run id) live on the canvas **Build input** node and in **Run Builder**; offline graph construction vocabulary matches [`../docs/backend/architecture.md`](../docs/backend/architecture.md).

## Source layout

```
src/
├── main.tsx                       Vite entry
├── App.jsx                        Active workbench (canvas + panels inline)
├── data/workbenchData.ts          USAGE_NODES, query fragments, Run Builder schema
├── query/queryModuleSyntax.ts     Query module fragment defaults + composition helpers
├── types/index.ts                 Shared TypeScript types
└── index.css                      Design system
```

Auto-loaded agent rules live in `.agents/rules/`. The shipped workbench is `src/App.jsx`; `frontend/updated/` is a tracked legacy static prototype that `main.tsx` does not import.

```bash
npm run dev    # http://127.0.0.1:5173/
```

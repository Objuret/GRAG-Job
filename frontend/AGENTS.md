# AGENTS.md — Onboarding for AI Models

Read this before touching any code. It tells you what this project is, how it is structured, what patterns it uses, and what you must not break.

---

## What This Is

A **frontend-only workbench prototype** for a modular artifact pipeline. It runs on synthetic mock data. There is no backend. There are no real datasets, credentials, run IDs, or file paths.

The purpose is to design a future-ready interface: typed contracts, a registry-driven stage catalog, a mock API client that can be swapped for a real HTTP client later, and a UI that is honest about what each stage can and cannot do.

Start the dev server with:

```
npm run dev
```

App opens at http://localhost:5173/

---

## File Map — Where Things Live

```
src/
├── types/index.ts              ← ALL types live here. Read this first.
├── data/mockData.ts            ← All mock stages, artifacts, executions
├── api/mockClient.ts           ← The only place components get data from
├── store/WorkspaceContext.tsx  ← UI state + localStorage persistence
├── components/
│   ├── layout/WorkbenchLayout.tsx  ← Grid shell
│   ├── layout/TopStrip.tsx         ← Status bar
│   ├── catalog/NodeCatalog.tsx     ← Left panel
│   ├── canvas/WorkflowCanvas.tsx   ← @xyflow/react canvas
│   ├── canvas/StageNode.tsx        ← Custom node type
│   ├── panel/InspectorPanel.tsx    ← Right panel (multi-mode)
│   └── logs/ExecutionPanel.tsx     ← Bottom panel
├── App.tsx                     ← Root assembly
└── index.css                   ← All styles — read before adding any CSS
docs/
├── architecture.md             ← Component graph, data flow, layout diagram
├── status.md                   ← What is built, mocked, and missing
├── api.md                      ← Full API contract and backend swap guide
├── requirements.md             ← Design principles, decisions, rationale
└── plans.md                    ← Prioritised next steps with file-level detail
```

---

## The Rules

### 1. Components never import from `mockData.ts`
All data access goes through `mockApi` from `src/api/mockClient.ts`. This is what makes the backend swap possible. If you add a new component, it calls `mockApi.someMethod()`, not `mockData.someArray`.

### 2. All types live in `src/types/index.ts`
Do not define ad-hoc types inline in components. If a new shape is needed, add it to `types/index.ts` first.

### 3. The stage registry is data, not code
Stages are objects in `mockData.ts`. To add, remove, or modify a stage: edit that array. Do not add stage-specific logic to components. Components read `stage.capabilityState`, `stage.configSchema`, etc. — they do not check `stage.id === 'stage_tagging'`.

### 4. Capability states are enforced, not advisory
`capabilityState` on a stage determines whether the Run button is enabled. Do not make a stage appear runnable unless its `capabilityState` is `'runnable'`. This is a hard design requirement.

### 5. CSS state classes follow a naming convention
State classes in `index.css` follow the pattern `.state-{value}`. Examples: `.state-runnable`, `.state-unavailable`, `.state-valid`, `.state-missing`. Apply them as `className={`state-${stage.capabilityState}`}`. Do not hardcode colors inline.

### 6. No real data
Never introduce real dataset names, run IDs, machine paths, credentials, or repository names. Use generic synthetic names like `raw_source_demo`, `ingestion_run_demo`, `exec_ingest_001`.

### 7. Workspace persistence is versioned
The localStorage key is `artifact_pipeline_workspace`. The format is:
```json
{ "schemaVersion": 1, "workspace": { ... } }
```
If you change the workspace shape, bump `schemaVersion` and handle migration in `WorkspaceContext.tsx`.

### 8. Workspace persistence strips React Flow internals
When saving nodes to localStorage, only persist: `{ id, type, position, parentId, extent, style, data }`. Do NOT persist React Flow internal fields like `measured`, `dragging`, `selected`, `positionAbsolute`, `internals`, `width`, `height`. These are reconstructed by React Flow on mount. Persisting them causes stale state conflicts.

---

## React Flow — Version & API Rules

**Version: `@xyflow/react` 12.10.2** (not v10, not v11 — the API is different)

### Correct v12 patterns
| Feature | Correct v12 API | Wrong (v10/v11) |
|---|---|---|
| Edge reconnection | `onReconnect` + `reconnectEdge()` | ~~`onEdgeUpdate`~~ |
| Node dimensions | `node.measured.width` | ~~`node.width`~~ |
| Connection mode enum | `ConnectionMode.Loose` | ~~`'loose'`~~ (string) |
| Node types object | Stable ref via `useMemo(() => ({ ... }), [])` | Inline object |
| Custom nodes | Wrapped in `memo()`, declared OUTSIDE component | Inside component |
| Sub-flows (groups) | `parentId` + `extent: 'parent'` on child nodes | Custom containment logic |

### CSS rules for React Flow
- **NEVER use `!important` on React Flow internal classes** (`.react-flow__handle`, `.react-flow__resize-control`, `.react-flow__connection-line`, `.react-flow__edge-path`, etc.)
- Use CSS specificity instead: `.canvas-wrapper .react-flow__handle { ... }`
- **NEVER use `transform: scale()` on handles** — it shifts the click target away from where React Flow expects it, breaking connections and edge reconnection
- Let React Flow control handle positioning — do not set `position: absolute` on handles

### Node resizing
- Use `<NodeResizer />` inside custom nodes
- Remove any `min-width` / `min-height` from CSS on the node wrapper — let `NodeResizer` control min dimensions via its `minWidth`/`minHeight` props
- Do NOT trigger persistence on `dimensions` change type — NodeResizer fires continuous dimension changes during drag

### Group nodes (sub-flows)
- Groups use a custom `groupNode` type with `<NodeResizer>` and `<Handle>` components
- Child nodes set `parentId` and `extent: 'parent'` to be nested
- Group nodes MUST have explicit `style: { width, height }` for React Flow to size them
- Groups must come before their children in the nodes array

---

## Key Patterns

### Reading data in a component
```tsx
const [stages, setStages] = useState<Stage[]>([]);
useEffect(() => {
  mockApi.getStageCatalog().then(setStages);
}, []);
```

### Accessing workspace/selection state
```tsx
const { workspace, updateWorkspace, selectedTool, setSelectedTool } = useWorkspace();
```

### Updating workspace (also saves to localStorage automatically)
```tsx
updateWorkspace({ selectedNodeId: node.id });
```

### Applying state-based styling
```tsx
<div className={`catalog-item state-${stage.capabilityState}`}>
```

---

## What Is Currently Mocked / Incomplete

See `docs/status.md` for the full list. Short version:

- `startExecution()` does not persist the result or update the execution list
- `compareArtifacts()` ignores its arguments and always returns the same diff
- Config form inputs render but values are not tracked or sent
- Canvas node positions are not saved on drag (only on selection change)
- `selectedArtifactId` and `selectedExecutionId` in WorkspaceState are never set by any interaction

Do not assume these work. Do not build on top of them without fixing the underlying issue first.

---

## What To Read Next

- `docs/architecture.md` — component dependency graph and data flow diagram
- `docs/plans.md` — what to build next, in priority order, with exact files to touch
- `docs/api.md` — the full API contract and how to swap in a real backend
- `src/types/index.ts` — the type definitions for everything

If something is not in a doc, check `docs/status.md` under "Known Issues" before making assumptions.

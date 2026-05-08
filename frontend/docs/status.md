# Status — What Is Built, Mocked, and Missing

---

## Built and Working

### Layout
- [x] Full workbench grid: top strip, left catalog, center canvas, right panel, bottom logs
- [x] Responsive column sizing
- [x] Custom CSS design system with dark palette and state color tokens

### Top Strip
- [x] Loads app name, version, environment via `getBootstrap()`
- [x] Displays on every page load

### Node Catalog (left panel)
- [x] Fetches stage catalog via `getStageCatalog()`
- [x] Groups stages by category
- [x] Shows capability state badge per stage
- [x] Stages are draggable onto the canvas (HTML5 drag API)
- [x] Tool buttons for Artifact Inspector and Run Comparator
- [x] Tool buttons toggle active state in `WorkspaceContext`

### Workflow Canvas (center)
- [x] `@xyflow/react` canvas with custom `stageNode` type
- [x] Pre-populates the full pipeline on first load (6 stages, 5 edges)
- [x] Nodes visually reflect `capabilityState` (border color, opacity)
- [x] Nodes are selectable — selection updates `WorkspaceContext.selectedNodeId`
- [x] Extra nodes can be dragged in from the catalog
- [x] Edges can be drawn between nodes manually
- [x] Background grid and zoom/pan controls

### Inspector Panel (right panel)
- [x] Switches view based on `selectedTool` and `selectedNodeId`
- [x] **Stage view:** label, description, capability badge, config fields (from `configSchema`), Run button
- [x] **Run button:** disabled and relabelled if stage is not `runnable`
- [x] **Artifact Inspector tool:** lists all artifacts with state badge and preview table
- [x] **Run Comparator tool:** shows hardcoded comparison result table

### Execution Panel (bottom)
- [x] Lists all executions from `getExecutions()`
- [x] Shows execution ID, status, logs, and error
- [x] Polls every 5 seconds (no live updates since data is static)

### Persistence
- [x] Workspace saved to `localStorage` on every `updateWorkspace()` call
- [x] Loaded on boot with `schemaVersion` check
- [x] Versioned JSON format (`schemaVersion: 1`)

---

## Mocked / Simulated

| Feature | What It Does | What's Fake |
|---|---|---|
| `getBootstrap()` | Returns app name/version/env | Hardcoded static object |
| `getStageCatalog()` | Returns stage list | Static array in `mockData.ts` |
| `getArtifacts()` | Returns artifact list | Static array in `mockData.ts` |
| `getArtifact(id)` | Returns single artifact | Array `.find()` — no DB |
| `getExecutions()` | Returns execution list | Static array in `mockData.ts` |
| `getExecution(id)` | Returns single execution | Array `.find()` — no DB |
| `startExecution()` | Returns a new execution object | Returns instantly, never updates state, never persists |
| `compareArtifacts()` | Returns diff result | Always returns the same hardcoded diff regardless of inputs |
| Execution polling | Calls `getExecutions()` every 5s | Data never changes so UI never updates |
| Config inputs | Renders input fields | Values are not stored or used anywhere |

---

## Missing / Not Implemented

### Execution state machine
- `startExecution()` returns a `running` execution but there is no timer or state machine that advances it to `succeeded` or `failed`
- The returned execution is not added to the execution list — it disappears
- No notification or feedback in the UI after clicking Run

### Artifact state on canvas nodes
- Nodes show `capabilityState` (a stage property) but not the state of the most recent output artifact (`valid`, `missing`, `stale`, etc.)
- Ideally each node badge reflects what has actually been produced

### Config form state
- `configSchema` is used to render input fields in the inspector
- Input values are not tracked in state — changes are lost on re-render or selection change

### Run Comparator selectors
- Comparator always shows the same hardcoded diff
- There are no dropdowns to select which two artifacts/runs to compare
- No concept of "left" and "right" references in the UI

### Artifact Inspector — stage-scoped view
- Shows all artifacts flat regardless of which stage is selected
- Should filter to show only artifacts produced by or required by the currently selected stage

### Lineage graph
- `Artifact.lineage.parentArtifactIds` is populated in the data
- No visual lineage graph is rendered — only raw data is stored

### Edge validation (artifact type enforcement)
- [x] Canvas validates connections: source `outputArtifactTypes` must overlap with target `inputArtifactTypes`
- [x] Invalid connections are rejected via `isValidConnection` callback

### Node position persistence
- [x] Node positions are persisted via debounced `onNodesChange` handler (fires on position, add, remove)
- [x] Edge changes (add, remove) are also persisted
- [x] Uses `screenToFlowPosition` for correct drop placement at any zoom/pan level

### `selectedArtifactId` and `selectedExecutionId`
- Both exist in `WorkspaceState` and types
- Neither is driven by any UI interaction yet

### Artifact preview — real data
- Preview tables show 2 hardcoded rows from `mockData.ts`
- No pagination, sorting, or column controls

### Stale / partial artifact detection logic
- `ArtifactState` includes `stale` and `partial`
- No rule engine computes these — they must be set manually in `mockData.ts`

---

## Known Issues

| Issue | Location | Impact |
|---|---|---|
| ~~Canvas node positions not saved on drag~~ | ~~`WorkflowCanvas.tsx`~~ | **Fixed** — debounced persistence on all node/edge changes |
| `startExecution()` result not added to execution list | `InspectorPanel.tsx` | Run button has no visible effect |
| Execution poll is cosmetic | `ExecutionPanel.tsx` | Always shows same two executions |
| `workspace.nodes` stores full ReactFlow internal state | `WorkspaceContext.tsx` | Brittle — internal ReactFlow fields bleed into persisted JSON |

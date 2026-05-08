# Plans — Next Steps & Improvements

Priority ordered. Each item includes what needs to change and why.

---

## P1 — Execution state machine

**Problem:** Clicking "Run Stage" fires `startExecution()` but the execution disappears. There is no feedback. Nothing in the log panel updates.

**Fix:**
1. `startExecution()` should push the new execution into a mutable in-memory store (not just the static `mockExecutions` array)
2. A `setTimeout` chain should advance the execution through `queued → running → succeeded/failed` every 1–2 seconds, appending log lines as it goes
3. `ExecutionPanel` should subscribe to that store (e.g. via context or a simple event emitter) so it re-renders when state changes
4. `InspectorPanel` should show a toast or status update after clicking Run

**Files affected:** `mockClient.ts`, `ExecutionPanel.tsx`, `InspectorPanel.tsx`, `WorkspaceContext.tsx`

---

## P1 — Node position persistence on drag

**Problem:** If you drag nodes around and refresh, positions revert to the pre-populated layout.

**Fix:**  
Wire `onNodesChange` in `WorkflowCanvas` to call `updateWorkspace({ nodes })` with a debounce (e.g. 500ms) so positions are saved continuously without flooding localStorage.

**Files affected:** `WorkflowCanvas.tsx`

---

## P1 — Config form state

**Problem:** Config field inputs render but values are immediately lost. Clicking Run sends empty config.

**Fix:**  
Add a `configValues` state in `InspectorPanel` (or `WorkspaceContext`) keyed by `stageId`. Persist to workspace JSON so config survives reloads.

**Files affected:** `InspectorPanel.tsx`, `WorkspaceContext.tsx`, `types/index.ts`

---

## P2 — Artifact state overlay on canvas nodes

**Problem:** Canvas nodes show `capabilityState` (a stage property) but not whether the stage's output artifact actually exists, is valid, or is stale.

**Fix:**  
`WorkflowCanvas` should fetch `getArtifacts()` on mount and pass each artifact's state to its matching node. `StageNode` should render a second badge (bottom-right corner) showing the output artifact state: `valid` (green dot), `missing` (amber), `invalid` (red), `stale` (grey).

**Files affected:** `WorkflowCanvas.tsx`, `StageNode.tsx`

---

## P2 — Stage-scoped artifact list in inspector

**Problem:** The Artifact Inspector tool shows all artifacts flat. When a stage is selected, it should show only artifacts relevant to that stage.

**Fix:**  
When a stage is selected, filter `getArtifacts()` by `artifact.lineage.sourceStageId === selectedStageId`. Show required inputs (from `stage.inputArtifactTypes`) separately from produced outputs.

**Files affected:** `InspectorPanel.tsx`

---

## P2 — Run Comparator selectors

**Problem:** The comparator always shows the same hardcoded diff. There are no controls to select which artifacts or runs to compare.

**Fix:**  
Add two `<select>` dropdowns in the comparator view populated from `getArtifacts()` filtered to artifacts with `state: 'valid'`. Call `compareArtifacts(leftId, rightId)` when both are selected. Update `mockClient.ts` to return different diffs based on the input IDs.

**Files affected:** `InspectorPanel.tsx`, `mockClient.ts`

---

## P2 — Clean up workspace persistence

**Problem:** `workspace.nodes` stores the full ReactFlow internal node objects, including internal fields like `selected`, `dragging`, `positionAbsolute`. This makes the persisted JSON fragile and tied to ReactFlow internals.

**Fix:**  
On save, serialize only: `{ id, type, position, data.stage.id }`. On load, reconstruct full node objects by re-fetching the stage catalog and merging with saved positions.

**Files affected:** `WorkspaceContext.tsx`, `WorkflowCanvas.tsx`

---

## P3 — Edge validation (artifact type enforcement)

**Problem:** The canvas allows any node to connect to any other. `inputArtifactTypes` and `outputArtifactTypes` are stored on stages but never checked.

**Fix:**  
In `onConnect` in `WorkflowCanvas`, look up the source and target stage, and validate that the source's `outputArtifactTypes` intersects with the target's `inputArtifactTypes`. If not, reject the connection and show an inline error.

**Files affected:** `WorkflowCanvas.tsx`

---

## P3 — Lineage graph view

**Problem:** `Artifact.lineage.parentArtifactIds` is populated in the data but there is no visual lineage trace.

**Fix:**  
In the artifact inspector view, render a compact vertical lineage chain below the artifact metadata. Walk `parentArtifactIds` up to the root and display as a chain: `raw_source_demo → ingestion_run_demo → index_artifact_demo`.

Could later become a mini canvas (ReactFlow sub-graph) if lineage is complex.

**Files affected:** `InspectorPanel.tsx`, potentially a new `LineageTrace.tsx` component

---

## P3 — `selectedArtifactId` and `selectedExecutionId`

**Problem:** Both exist in `WorkspaceState` but are never set by any UI interaction.

**Fix:**  
- Clicking an artifact in the inspector should set `selectedArtifactId` and switch the right panel to artifact detail view
- Clicking an execution log card should set `selectedExecutionId` and show its full detail (all logs, produced artifacts as clickable links)

**Files affected:** `WorkspaceContext.tsx`, `InspectorPanel.tsx`, `ExecutionPanel.tsx`

---

## P4 — Real backend integration

**When:** When a real execution backend exists.

**What to do:**
1. Define `IApiClient` interface matching all current method signatures
2. Implement `HttpApiClient` that calls `fetch()` against a real API base URL
3. Switch `mockApi` export based on `VITE_USE_MOCK` environment variable
4. Ensure backend returns the exact same JSON shapes defined in `src/types/index.ts`

No component changes should be needed if the contract is respected.

**Files affected:** `mockClient.ts` (add interface + new class), `vite.config.ts` (env variable)

---

## P4 — Dynamic `panelDefinition` renderer

**Problem:** `panelDefinition` is stored on each stage but not used. Config fields are rendered by manually iterating `configSchema` keys with a generic `<input>`.

**Fix:**  
Build a `DynamicForm` component that reads `panelDefinition.type` (`'form'` vs `'editor'`) and `panelDefinition.fields` to render appropriate inputs — text, number, textarea for prompt templates, file pickers, etc.

**Files affected:** New `src/components/panel/DynamicForm.tsx`, `InspectorPanel.tsx`

---

## P5 — Pipeline export

Add a button to export the current canvas pipeline as a JSON definition:

```json
{
  "version": 1,
  "stages": ["stage_raw_data", "stage_ingestion", ...],
  "edges": [{ "source": "stage_raw_data", "target": "stage_ingestion" }],
  "config": { "stage_raw_data": { "bucketName": "demo" } }
}
```

This could later be used to submit a full pipeline run to a backend in one call.

**Files affected:** New export utility, `TopStrip.tsx` or `WorkflowCanvas.tsx`

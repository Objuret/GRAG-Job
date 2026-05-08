# API Contract

This document defines the full API surface used by the workbench. The current implementation is a mock client. When a real backend is built, it must implement this contract exactly. Components should not need to change.

---

## Client Location

`src/api/mockClient.ts` — exports a singleton `mockApi`.

All components import and call `mockApi.methodName()`. Nothing imports from `mockData.ts` directly.

---

## Methods

### `getBootstrap(): Promise<BootstrapData>`

Returns application metadata for the current environment.

```ts
interface BootstrapData {
  appName: string;
  version: string;
  environment: string; // e.g. 'local-mock', 'dev', 'prod'
}
```

**Called by:** `TopStrip`  
**Mock behavior:** Returns a hardcoded object after 200ms.  
**Real behavior:** `GET /api/bootstrap`

---

### `getStageCatalog(): Promise<Stage[]>`

Returns the full list of registered pipeline stages.

```ts
interface Stage {
  id: string;
  type: string;
  label: string;
  category: string;
  description: string;
  adapterKey: string;
  capabilityState: 'runnable' | 'inspectable' | 'unavailable' | 'pending';
  inputArtifactTypes: string[];
  outputArtifactTypes: string[];
  configSchema: Record<string, any>;   // field name → type string (e.g. { batchSize: 'number' })
  panelDefinition: Record<string, any>; // hints for rendering config panel
  lineageRules: Record<string, any>;
}
```

**Called by:** `NodeCatalog`, `WorkflowCanvas`  
**Mock behavior:** Returns static array after 300ms.  
**Real behavior:** `GET /api/stages`

---

### `getArtifacts(): Promise<Artifact[]>`

Returns all known artifacts across all stages.

```ts
interface Artifact {
  id: string;
  type: string;                          // e.g. 'raw_bundle', 'standard_records'
  label: string;
  state: 'valid' | 'invalid' | 'partial' | 'missing' | 'stale';
  metadata: Record<string, any>;         // size, format, item count, etc.
  lineage: {
    sourceStageId?: string;
    parentArtifactIds: string[];
  };
  summary: Record<string, any>;          // human-readable summary fields
  preview?: {
    columns: string[];
    rows: any[][];
  };
}
```

**Called by:** `InspectorPanel` (Artifact Inspector tool)  
**Mock behavior:** Returns static array after 300ms.  
**Real behavior:** `GET /api/artifacts`

---

### `getArtifact(id: string): Promise<Artifact | null>`

Returns a single artifact by ID, or null if not found.

**Called by:** Not yet called directly — used by `InspectorPanel` in future per-stage artifact view.  
**Mock behavior:** Array `.find()` after 200ms.  
**Real behavior:** `GET /api/artifacts/:id`

---

### `getExecutions(): Promise<Execution[]>`

Returns all execution records.

```ts
interface Execution {
  id: string;
  stageId: string;
  status: 'idle' | 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';
  timestamps: {
    queued?: string;    // ISO 8601
    started?: string;
    completed?: string;
  };
  logs: string[];
  inputs: Record<string, string>;      // argName → artifactId
  config: Record<string, any>;
  producedArtifactIds: string[];
  error?: string;
}
```

**Called by:** `ExecutionPanel`  
**Mock behavior:** Returns static array after 300ms.  
**Real behavior:** `GET /api/executions` (or WebSocket subscription for live updates)

---

### `getExecution(id: string): Promise<Execution | null>`

Returns a single execution by ID, or null.

**Called by:** Not yet wired — planned for clicking an execution in the log panel.  
**Mock behavior:** Array `.find()` after 200ms.  
**Real behavior:** `GET /api/executions/:id`

---

### `startExecution(request): Promise<Execution>`

Starts a new execution for a stage.

```ts
// Request
{
  stageId: string;
  config: Record<string, any>;   // current config field values
  inputs: Record<string, string>; // argName → artifactId
}

// Response
Execution  // with status: 'queued' or 'running'
```

**Called by:** `InspectorPanel` Run button  
**Mock behavior:** Validates that the stage is `runnable`, returns a fake execution object after 500ms. Does NOT add to the execution list. Does NOT advance state.  
**Real behavior:** `POST /api/executions`

> ⚠️ Current gap: the returned execution is not persisted or surfaced anywhere in the mock. The execution list in `ExecutionPanel` will not update after calling this.

---

### `compareArtifacts(leftRef: string, rightRef: string): Promise<ComparisonResult>`

Compares two artifact references and returns a structured diff.

```ts
interface ComparisonResult {
  metadataDiff: Record<string, any>;  // size, format, etc.
  countDiff: Record<string, any>;     // item counts
  schemaDiff: Record<string, any>;    // column presence/absence
  lineageDiff: Record<string, any>;   // same source? same parent?
  summaryDiff: Record<string, any>;   // error counts, validation results
}
```

**Called by:** `InspectorPanel` (Run Comparator tool)  
**Mock behavior:** Ignores `leftRef` and `rightRef`. Always returns the same hardcoded diff after 400ms.  
**Real behavior:** `GET /api/artifacts/compare?left=:leftRef&right=:rightRef`

> ⚠️ Current gap: `leftRef` and `rightRef` are hardcoded as `'left'` and `'right'` at the call site. The UI has no selectors for choosing which artifacts to compare.

---

## How to Swap in a Real Backend

1. Replace `MockApiClient` in `src/api/mockClient.ts` with an `HttpApiClient` that makes `fetch()` calls to the same method names.
2. All method signatures remain identical.
3. No component files need to change.
4. The `mockApi` export is the only coupling point.

Recommended approach: define an interface `IApiClient` and implement both `MockApiClient` and `HttpApiClient` against it. Switch via environment variable or build flag.

```ts
// Future
export const mockApi: IApiClient = import.meta.env.VITE_USE_MOCK === 'true'
  ? new MockApiClient()
  : new HttpApiClient(import.meta.env.VITE_API_BASE_URL);
```

---

## Data Not Yet in the API

These things exist in the type definitions but have no corresponding API method yet:

| Data | Where Defined | Notes |
|---|---|---|
| Artifact lineage graph | `Artifact.lineage` | Data is there, no API query for traversal |
| Stage-scoped artifact list | `Stage.id` + `Artifact.lineage.sourceStageId` | Could be `GET /api/stages/:id/artifacts` |
| Execution cancellation | `ExecutionState: 'cancelled'` | No `cancelExecution(id)` method |
| Workspace save/load (server-side) | `WorkspaceState` | Currently only localStorage |

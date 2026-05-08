# Architecture

## Overview

The app is a **frontend-only workbench** driven by a typed stage registry and a mock API client. All data is synthetic. Components never talk to each other directly — they read through `mockApi` and write through `WorkspaceContext`.

---

## Module Map

```
src/
├── types/
│   └── index.ts              # All typed contracts (Stage, Artifact, Execution, etc.)
│
├── data/
│   └── mockData.ts           # Static mock stages, artifacts, and executions
│
├── api/
│   └── mockClient.ts         # MockApiClient class — async wrapper over mockData
│
├── store/
│   └── WorkspaceContext.tsx  # React context — UI state + localStorage persistence
│
├── components/
│   ├── layout/
│   │   ├── WorkbenchLayout.tsx   # Top/left/center/right/bottom grid shell
│   │   └── TopStrip.tsx          # Environment/version status bar
│   │
│   ├── catalog/
│   │   └── NodeCatalog.tsx       # Left panel — stages grouped by category + tool buttons
│   │
│   ├── canvas/
│   │   ├── WorkflowCanvas.tsx    # @xyflow/react canvas with pre-populated pipeline
│   │   └── StageNode.tsx         # Custom node component — renders per capabilityState
│   │
│   ├── panel/
│   │   └── InspectorPanel.tsx    # Right panel — stage config / artifact inspector / comparator
│   │
│   └── logs/
│       └── ExecutionPanel.tsx    # Bottom panel — execution log list
│
├── App.tsx                   # Root — composes providers and layout
├── main.tsx                  # Vite entry point
└── index.css                 # All styles — design tokens, layout, state classes
```

---

## Component Dependency Graph

```
App.tsx
├── WorkspaceProvider          (WorkspaceContext.tsx)
│   └── ReactFlowProvider      (@xyflow/react)
│       └── WorkbenchLayout
│           ├── TopStrip           → mockApi.getBootstrap()
│           ├── NodeCatalog        → mockApi.getStageCatalog()
│           │                      → useWorkspace (setSelectedTool)
│           ├── WorkflowCanvas     → mockApi.getStageCatalog()  [pre-populate]
│           │                      → useWorkspace (workspace.nodes, updateWorkspace)
│           │                      → StageNode (per node)
│           ├── InspectorPanel     → useWorkspace (selectedNodeId, selectedTool)
│           │                      → mockApi.getArtifacts()
│           │                      → mockApi.startExecution()
│           │                      → mockApi.compareArtifacts()
│           └── ExecutionPanel     → mockApi.getExecutions()  [polls every 5s]
```

---

## Data Flow

```
mockData.ts
    │
    ▼
MockApiClient (mockClient.ts)
    │   async wrappers with simulated latency (200–500ms)
    │
    ├──▶ TopStrip          getBootstrap()
    ├──▶ NodeCatalog        getStageCatalog()
    ├──▶ WorkflowCanvas     getStageCatalog()  → initialNodes + initialEdges
    ├──▶ InspectorPanel     getArtifacts() / startExecution() / compareArtifacts()
    └──▶ ExecutionPanel     getExecutions()
```

---

## State Flow

```
WorkspaceContext (in-memory + localStorage)
    │
    ├── workspace.nodes          ReactFlow node list (includes stage data)
    ├── workspace.edges          ReactFlow edge list
    ├── workspace.selectedNodeId Set by WorkflowCanvas onSelectionChange
    ├── workspace.selectedArtifactId  (wired in types, not yet driven by UI)
    ├── workspace.selectedExecutionId (wired in types, not yet driven by UI)
    └── selectedTool             'inspector' | 'comparator' | null
                                 Set by NodeCatalog tool buttons
                                 Read by InspectorPanel to switch view
```

---

## Layout Grid

```
┌─────────────────────────────────────────────────────────────┐
│  TopStrip  (40px)   app name · env · version                │
├──────────────┬───────────────────────────┬──────────────────┤
│  NodeCatalog │    WorkflowCanvas         │  InspectorPanel  │
│  260px       │    flex-grow              │  320px           │
│              │    @xyflow/react canvas   │                  │
│  Tools       │    pre-populated pipeline │  Changes on:     │
│  Stages by   │    nodes + edges          │  - stage select  │
│  category    │                           │  - tool select   │
│              │    drag-to-add extra      │                  │
├──────────────┴───────────────────────────┴──────────────────┤
│  ExecutionPanel  (200px)                                     │
│  mock execution log cards                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Pipeline Graph (pre-populated on canvas)

```
Raw Data Source   (runnable)
        │
        ▼
Data Ingestion    (inspectable)
        │
        ├──▶ Content Indexing    (inspectable)
        │
        └──▶ Entity Tagging      (unavailable — no adapter)
                    │
                    ▼
            Semantic Clustering  (pending — waiting for tags)
                    │
                    ▼
            Topic Interpretation (pending — waiting for clusters)
```

---

## Capability → Visual Mapping

| State | Border | Opacity | Meaning |
|---|---|---|---|
| `runnable` | green left border | 100% | Adapter exists, inputs available, can execute |
| `inspectable` | blue left border | 100% | Has produced artifacts, view-only |
| `unavailable` | grey left border | 60% | No adapter registered |
| `pending` | purple left border | 80% | Adapter known, inputs not yet ready |

---

## Artifact State Mapping

| State | Color | Meaning |
|---|---|---|
| `valid` | green | Produced and verified |
| `invalid` | red | Produced but failed validation |
| `missing` | amber | Expected but not yet produced |
| `partial` | purple | Partially produced |
| `stale` | grey | Produced but inputs have since changed |

---

## Persistence Format (localStorage)

Key: `artifact_pipeline_workspace`

```json
{
  "schemaVersion": 1,
  "workspace": {
    "nodes": [...],
    "edges": [...],
    "selectedNodeId": null,
    "selectedArtifactId": null,
    "selectedExecutionId": null
  }
}
```

The `schemaVersion` field is checked on load — mismatched versions are ignored.

---

## Key Design Decisions

- **Components read through `mockApi`** — not directly from `mockData`. This means swapping to a real HTTP client later only requires changing `mockClient.ts`, nothing else.
- **Stage registry is data, not code** — stages are defined in `mockData.ts` as typed objects, not as React components or hardcoded JSX.
- **Canvas pre-populates on mount** — `WorkflowCanvas` calls `getStageCatalog()` and lays out the pipeline automatically on first render if `workspace.nodes` is empty.
- **`panelDefinition` and `configSchema` are stored on each stage** — they're not used to drive dynamic forms yet, but the data is there for a future form renderer.

# Requirements, Decisions & Design Rationale

---

## What This Is

A **frontend-first design prototype** for a modular artifact pipeline workbench. The purpose is to:

1. Define the UX shape and interaction model for working with staged artifact pipelines
2. Establish typed contracts and an API surface before any backend exists
3. Make it possible to inspect, run, compare, and understand the state of pipeline stages and their outputs
4. Be honest with the user about what a stage can and cannot do

This is not a production tool. It is a **design artifact** that doubles as a working prototype.

---

## Core Design Principles

### 1. Honesty about capability
The UI must never present a stage as runnable when it is not. Capability states (`runnable`, `inspectable`, `unavailable`, `pending`) are explicit properties on each stage object. The Run button is disabled and relabelled based on the stage's `capabilityState` — not a soft warning after clicking.

### 2. Registry-driven, not hardcoded
Stages are not baked into JSX or switch statements. They are typed objects in a registry (`mockData.ts`). Adding a new stage means adding an entry to the array. No component logic changes.

### 3. Components talk to the API, not to each other
Components fetch data through `mockApi`. They do not import from `mockData.ts`. They do not call each other directly. This makes the swap from mock to real backend a single-file change.

### 4. Workspace persistence from day one
The workspace (canvas layout, selected state) is persisted to `localStorage` using a versioned JSON schema. This is not bolted on — it is part of the initial architecture.

### 5. Explicit state everywhere
Every domain object has an explicit state:
- Stages have `capabilityState`
- Artifacts have `ArtifactState`
- Executions have `ExecutionState`

These states are typed, not inferred or implied. The UI maps each state to a visual indicator.

---

## Requirements

### Must have (built)
- [x] Workbench layout: top strip, left catalog, center canvas, right panel, bottom logs
- [x] Pipeline displayed as connected stage nodes on a canvas
- [x] Stages grouped by category in the catalog
- [x] Visual state indicators for stage capability
- [x] Inspector panel changes based on what is selected (stage vs. tool)
- [x] Run button disabled for non-runnable stages
- [x] Artifact Inspector tool view
- [x] Run Comparator tool view
- [x] Mock execution log panel
- [x] localStorage workspace persistence with schema versioning
- [x] Typed contracts for Stage, Artifact, Execution
- [x] Mock API client with realistic async latency
- [x] Synthetic mock data — no real credentials, paths, or datasets

### Should have (partially built or mocked)
- [~] Config form — fields render, values not persisted
- [~] `startExecution()` — callable, result not wired to UI
- [~] Artifact preview tables — static mock rows only
- [~] Run Comparator — view exists, no selectors
- [ ] Artifact state badges on canvas nodes
- [ ] Stage-scoped artifact list in inspector
- [ ] Node position persistence on drag

### Could have (not started)
- [ ] Execution state machine (queued → running → succeeded/failed)
- [ ] Lineage graph visualization
- [ ] Edge validation (artifact type matching on connect)
- [ ] Config state persistence per stage
- [ ] Comparator selectors (left/right artifact pickers)
- [ ] Execution cancel button
- [ ] Artifact download / export stub
- [ ] Server-side workspace save/load

---

## Technology Decisions

| Decision | Choice | Reason |
|---|---|---|
| Framework | React + Vite + TypeScript | Standard for this kind of interactive tooling; fast iteration cycle |
| Canvas | @xyflow/react | Purpose-built for node-edge graphs; handles pan/zoom/drag out of the box |
| Icons | lucide-react | Consistent, minimal, tree-shakeable |
| Styling | Custom CSS (no framework) | Full control over tokens, states, and layout without fighting utility class abstractions |
| State | React Context | Simple enough for this scale; no Redux overhead; easily replaceable |
| Persistence | localStorage | Zero dependencies; sufficient for a local workbench prototype |
| Mock API | Class with async wrappers | Same interface as a real HTTP client; swap-ready |

---

## What Was Explicitly Avoided

- **Real data** — no real dataset names, run IDs, credentials, repository names, or machine paths
- **Landing pages / marketing copy** — the app opens directly on the workbench
- **Admin UI templates** — all styling is hand-written to fit the specific domain
- **Fake "enterprise" language** — labels are direct and technical
- **Tailwind CSS** — opted for custom CSS to keep state classes meaningful and explicit
- **Presenting unavailable stages as runnable** — this is a hard requirement

---

## Assumptions Made During Build

1. The pipeline is linear with one branch: `Raw Data → Ingestion → [Indexing branch, Tagging branch]`
2. Stage categories map one-to-one with stages in the current demo (one stage per category)
3. Canvas layout is vertical (top-to-bottom) for the pre-populated pipeline
4. Artifact preview rows are always small (2 rows is enough for the prototype)
5. `configSchema` field types are strings like `'string'` or `'number'` — not JSON Schema objects
6. The inspector right panel is wide enough for single-column forms (320px)

---

## Out of Scope for v1

- Authentication / authorization
- Multi-user collaboration
- Server-side execution
- Real artifact storage or file system access
- Pipeline scheduling or triggers
- Notification system
- Export of pipeline definitions to YAML/JSON

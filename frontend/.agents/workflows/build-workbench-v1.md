---
description: 
---

Create the first frontend-only implementation of a local artifact pipeline workbench.

This is not a dashboard for one fixed pipeline. It is a future-ready workbench for plugging in artifact stages, adapters, inspectors, comparison tools, and execution modules over time.

Use:
- Vite
- React
- TypeScript
- @xyflow/react for the workflow canvas
- lucide-react for icons
- custom CSS

Core idea:
- The UI is driven by a typed node registry.
- Nodes are not hardcoded directly into components.
- Each node has type, label, category, config schema placeholder, adapter key, allowed inputs, allowed outputs, capability state, and UI panel definition.
- New node types should be addable by editing registry/mock contract data, not by rewriting the whole app.

Create generic node categories:
- Source
- Discovery
- Structure
- Enrichment
- Interpretation
- Inspection
- Comparison
- Output

Create example visible nodes:
- Data Source
- File/Format Profiling
- Structure Builder
- Content Enrichment
- Tag/Concept Interpretation
- Artifact Inspector
- Run Comparator
- Export Bundle

Important:
- These are example nodes only.
- The architecture must support adding, removing, renaming, and disabling nodes later.
- Do not bake thesis-specific layer names into component logic.
- Do not include real paths, real run IDs, real datasets, credentials, private repo names, or machine-specific assumptions.
- Use synthetic mock data only.

Build the UI:
- left node catalog grouped by category
- central workflow canvas
- right detail/config/inspection panel
- bottom execution/log panel
- top environment/status strip
- run/artifact browser
- comparison view
- localStorage workspace persistence

Mock states must include:
- one runnable node
- one inspectable-only node
- one unavailable node because no adapter exists
- one invalid artifact/run
- one not-yet-materialized downstream artifact
- one optional projection/view that is unavailable

After building:
- run the app
- open it in browser
- produce screenshots/walkthrough artifacts
- fix obvious layout and state-honesty problems before finishing

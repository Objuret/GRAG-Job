# exjobbet — artefact monorepo

Two self-contained halves, one git repo:

- **[`v2/`](v2/)** — the **active** artefact rebuild. References-not-copies graph
  pipeline (`v2/backend/`, run from there: `python -m v2 ...`), design docs in
  [`v2/docs/`](v2/docs/v2_artefact_rebuild_design.md).
- **[`v1/`](v1/)** — the **frozen** original stack (thesis-era): Python tagging
  pipeline, React/Vite workbench, eval runs, v1 docs. Kept intact and runnable;
  not developed further. Its graph DBs (`herb-eval` canonical) still live in Neo4j.

Session entry for agents: [`CLAUDE.md`](CLAUDE.md).

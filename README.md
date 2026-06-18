# exjobbet — artefact monorepo

Three self-contained builds, one git repo:

- **[`v3/`](v3/)** — **canon**, the active work. A lean HERB evaluation harness:
  three arms (artefact / lucene / vector) scored two ways (HERB + RAGAS).
  Self-contained. Design reference [`v3/README.md`](v3/README.md).
- **[`v2/`](v2/)** — **reference** build: the post-thesis artefact rebuild,
  references-not-copies graph pipeline (`v2/backend/`, run from there:
  `python -m v2 ...`), design docs in [`v2/docs/`](v2/docs/v2_artefact_rebuild_design.md).
  The v3 artefact arm will wrap it.
- **[`v1/`](v1/)** — **reference** build, frozen thesis-era stack: Python tagging
  pipeline, React/Vite workbench, eval runs, v1 docs. Intact and runnable, not
  developed further. Its graph DBs (`herb-eval` canonical) still live in Neo4j.

Each build is its own graphify graph (v3 active; `--v2` / `--v1` on demand).
Session entry for agents: [`CLAUDE.md`](CLAUDE.md).

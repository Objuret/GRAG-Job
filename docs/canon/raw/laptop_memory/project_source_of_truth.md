---
name: Source of truth — djuret/monorepo branch + docs/ tree
description: Where the real, current GRAG-Job implementation and docs live; what is legacy/quarantined
type: project
originSessionId: 75e34ba8-8222-4dbe-aa92-f838e9ccdc20
---
The real, current line of work is the branch **`origin/djuret/monorepo`** (tip historically `fb311f6 frontend pipeline fixing`). `main` lineage is a divergent, stripped/mock state — its frontend (mockData.ts + components/store/api dirs) and its `backend/prompts/extract_chunk.md` + `backend/docs/graph_schema.md` are the OLD generic-tagger frame (5 clusters: theme/object_entity/event_process/time_relevance/information_need).

The HERB system uses **five facets**: topic, entities, activity, temporal, evidence — NOT the old cluster names.

Authoritative current docs (only present on djuret/monorepo, at repo-root `docs/`, not `backend/docs/`):
- `docs/frontend/query_interpretation_layer.md` — the prompt-interpretation method spec.
- `docs/backend/herb_tagging_schema.md`, `herb_tagging_frames.md`, `prompts.md`, `pilot_full_herb_report.md`.
- Real tagging code: `backend/tagging/pipeline.py`.
- `quarantine/DO_NOT_READ_UNLESS_LEGACY.md` marks the old generic-tagger material as legacy.

**Why:** A frontend-only restore left main-lineage backend/docs alongside djuret frontend, and analysis was done from quarantined-legacy files — wasted user time/work.
**How to apply:** For any GRAG-Job design/architecture question, read `docs/frontend|backend/` and `backend/tagging/pipeline.py` on the djuret/monorepo state. Never reason from `backend/prompts/extract_chunk.md`, `backend/docs/graph_schema.md`, or anything under `quarantine/`. Restore/checkout coherent whole branches, not single subtrees.

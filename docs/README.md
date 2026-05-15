# Documentation

Project-wide reference for the thesis system. Start in [`/AGENTS.md`](../AGENTS.md) for the agent brief and hard rules.

**Joint index (HERB-first):** [`system_map.md`](system_map.md) — concepts, entrypoint code, links; legacy paths **`.cursorignore`d** (see [`../quarantine/DO_NOT_READ_UNLESS_LEGACY.md`](../quarantine/DO_NOT_READ_UNLESS_LEGACY.md)).

## Shared

| File | Purpose |
|---|---|
| [`system_map.md`](system_map.md) | **HERB-first** joint index (access → preflight → tagging → UI); legacy indexer quarantined |
| [`graph_schema.md`](graph_schema.md) | The Neo4j artefact contract. Backend writes; frontend reads. |

## Backend — offline Python pipeline

| File | Purpose |
|---|---|
| [`backend/architecture.md`](backend/architecture.md) | Access layer vs indexing, layer map, decision log |
| [`backend/runbook.md`](backend/runbook.md) | First-time setup, commands, recovery |
| [`backend/env_and_config.md`](backend/env_and_config.md) | Every env var, where it's consumed |
| [`backend/codebase_map.md`](backend/codebase_map.md) | Per-file map of `backend/` source (includes legacy rows — skip paths in [`../quarantine/DO_NOT_READ_UNLESS_LEGACY.md`](../quarantine/DO_NOT_READ_UNLESS_LEGACY.md)) |
| [`backend/prompts.md`](backend/prompts.md) | **Legacy** prompt catalogue (path is **`.cursorignore`d`**); HERB prompts live under [`herb_tagging_schema.md`](backend/herb_tagging_schema.md) + `tagging/` |
| [`backend/herb_tagging_schema.md`](backend/herb_tagging_schema.md) | HERB Anthropic tagging method |
| [`backend/herb_tagging_frames.md`](backend/herb_tagging_frames.md) | HERB per-evidence-shape frame routing |
| [`backend/pilot_full_herb_report.md`](backend/pilot_full_herb_report.md) | Current HERB artefact run report |
| [`backend/status.md`](backend/status.md) | Backend built / verified state |

## Frontend — local-only browser workbench

| File | Purpose |
|---|---|
| [`frontend/architecture.md`](frontend/architecture.md) | Canvas, lanes, data flow, browser-direct calls |
| [`frontend/query_interpretation_layer.md`](frontend/query_interpretation_layer.md) | Two-pass prompt interpretation method (runs in browser) |
| [`frontend/plans.md`](frontend/plans.md) | Next implementation steps |
| [`frontend/status.md`](frontend/status.md) | Frontend built / wired state |

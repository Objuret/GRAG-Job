# Documentation

Project-wide reference for the thesis system. Start in [`/AGENTS.md`](../AGENTS.md) for the agent brief and hard rules.

## Shared

| File | Purpose |
|---|---|
| [`graph_schema.md`](graph_schema.md) | The Neo4j artefact contract. Backend writes; frontend reads. |

## Backend — offline Python pipeline

| File | Purpose |
|---|---|
| [`backend/architecture.md`](backend/architecture.md) | Layer model + decision log |
| [`backend/runbook.md`](backend/runbook.md) | First-time setup, commands, recovery |
| [`backend/env_and_config.md`](backend/env_and_config.md) | Every env var, where it's consumed |
| [`backend/codebase_map.md`](backend/codebase_map.md) | Per-file map of `backend/` source |
| [`backend/prompts.md`](backend/prompts.md) | LLM prompt catalogue |
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

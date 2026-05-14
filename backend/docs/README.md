# Docs Index

**TL;DR.** This `docs/` directory is the durable, agent-readable contract for the repository. The project builds a multi-layer index/cluster artefact between heterogeneous datasets and an LLM, with **Neo4j as the only durable store**. For HERB, the current portable archive is `data/tagging_runs/pilot_full_herb_snapshot_20260514T052226Z.zip`; older run folders are build/history. Read these files to learn the architecture, the graph schema, the runbook, the conventions, and the current build state — without needing prior chat context.

**When to read this.** First stop for any new agent or human picking up the codebase. Use this page to choose the right deeper doc.

**Last updated:** 2026-05-14.

> **If you are an AI agent picking up this codebase, start by reading [`agent_brief.md`](agent_brief.md).**

## Touched paths

This index touches: `docs/`, backend `README.md`, backend `AGENTS.md`.

## Project mission (one paragraph)

Many noisy, heterogeneous datasets sit between us and any analytical query. The pipeline ingests the raw payload, deterministically splits each file into chunks, and stores the graph artefact in Neo4j. The legacy indexing path asks one OpenAI-compatible LLM to extract a five-cluster tag set per chunk plus a file-level relevance map. HERB tagging is currently a separate Anthropic path documented in [`herb_tagging_schema.md`](herb_tagging_schema.md), with the completed full-corpus run documented in [`pilot_full_herb_report.md`](pilot_full_herb_report.md). The five clusters/facets (`topic`, `entities`, `activity`, `temporal`, `evidence`) are the retrieval dimensions. The graph (`(:Source)-[:CONTAINS]->(:File)-[:HAS_CHUNK]->(:Chunk)-[:HAS_TAG]->(:Tag)` plus a derived `(:File)-[:TAGGED]->(:Tag)`) is the only durable indexing artefact — there are no parquet/JSON side files, no fallbacks, no mocks.

## Reading order for first-time onboarding

| # | File | Audience | Why |
|---|------|----------|-----|
| 1 | [`agent_brief.md`](agent_brief.md) | **AI agent** (also good for humans) | Minimum context to be productive. Mission, mermaid architecture, hard rules, "where to look" table, end-to-end commands, backlog. |
| 2 | [`architecture.md`](architecture.md) | Human + agent | Layer model, decision log (Path A chunker, tag uniqueness, breaker policy, …), run lifecycle diagram, dispatch modes. |
| 3 | [`graph_schema.md`](graph_schema.md) | Anyone touching Cypher | The Neo4j artefact contract: every node label, every edge type, properties, constraints, indexes, who writes/reads. |
| 4 | [`codebase_map.md`](codebase_map.md) | Anyone navigating the source | One section per top-level dir, every file with a one-line role and key public symbols. |
| 5 | [`runbook.md`](runbook.md) | Operator | First-time setup, bootstrap → preflight → run_index, common failures and fixes, wipe-and-restart. |
| 6 | [`prompts.md`](prompts.md) | Anyone editing `prompts/` | Catalogue of LLM prompts, inputs, output schemas, validation/retry behaviour, editing rules. |
| 7 | [`herb_tagging_schema.md`](herb_tagging_schema.md) | Anyone touching HERB tagging | Exact Anthropic model input/output schema, non-contamination rule, and weight rationale. |
| 8 | [`pilot_full_herb_report.md`](pilot_full_herb_report.md) | Anyone using current HERB output | Current full-corpus HERB artefact, run stats, failure recovery, and archive contents. |
| 9 | [`herb_tagging_frames.md`](herb_tagging_frames.md) | Anyone touching HERB frames | Per-evidence-shape frame routing and why structured HERB chunks must not all be read the same way. |
| 10 | [`query_interpretation_layer.md`](query_interpretation_layer.md) | Anyone wiring frontend retrieval | Planned prompt to query-plan contract, aligned with the real two-pass HERB tagging method. |
| 11 | [`env_and_config.md`](env_and_config.md) | Operator | Every env var, defaults, where consumed, alias precedence (`LLM_*` wins over `AGENT_*`). |
| 12 | [`status.md`](status.md) | Anyone planning the next step | Truthful snapshot: what is verified, what is built but unverified, known gaps, decisions to revisit. |

## How docs cross-link

- Internal links use **relative paths** (e.g. [`../indexing/breaker.py`](../indexing/breaker.py), [`graph_schema.md`](graph_schema.md)).
- Hard rules live in `agent_brief.md`. Decisions and trade-offs live in `architecture.md`. Concrete contracts (Cypher, prompts, env) live in their dedicated files. Don't duplicate.
- When code changes affect a contract (schema, prompt JSON shape, env vars), update the matching doc in the same change.

## Hard rules (mirror of `agent_brief.md` for quick scan)

- **No fallbacks. No mocks.** Fail loud. The agent client never raises; the orchestrator decides. Everywhere else, raise.
- **One model provider per runner.** The legacy indexing path uses OpenAI-compatible HTTP via `LLM_*` env (legacy `AGENT_*` honoured). The HERB tagging pilot uses Anthropic via `ANTHROPIC_*`. No local model fallback.
- **Per-error-class circuit breaker.** Tight thresholds (see [`../indexing/breaker.py`](../indexing/breaker.py)).
- **Working-file job ledger drives agent scheduling.** Do not store scheduler rows in the graph.
- **Neo4j is the only durable store.** No parquet/JSON side artefacts in the indexing path.

# Docs Index

**TL;DR.** This `docs/` directory is the durable, agent-readable contract for the repository. The project builds a multi-layer index/cluster artefact between heterogeneous datasets and an LLM, with **Neo4j as the only durable store**. Read these files to learn the architecture, the graph schema, the runbook, the conventions, and the current build state — without needing prior chat context.

**When to read this.** First stop for any new agent or human picking up the codebase. Use this page to choose the right deeper doc.

**Last updated:** 2026-05-11.

> **If you are an AI agent picking up this codebase, start by reading [`agent_brief.md`](agent_brief.md).**

## Touched paths

This index touches: `docs/`, backend `README.md`, backend `AGENTS.md`.

## Project mission (one paragraph)

Many noisy, heterogeneous datasets sit between us and any analytical query. The pipeline ingests the raw payload, deterministically splits each file into chunks, asks one OpenAI-compatible LLM to extract a five-cluster tag set per chunk plus a file-level relevance map, and rolls those up into a queryable Neo4j graph. The five clusters (`topic`, `entities`, `activity`, `temporal`, `evidence`) are the retrieval dimensions. The graph (`(:Source)-[:CONTAINS]->(:File)-[:HAS_CHUNK]->(:Chunk)-[:HAS_TAG]->(:Tag)` plus a derived `(:File)-[:TAGGED]->(:Tag)`) is the only durable artefact — there are no parquet/JSON side files, no fallbacks, no mocks.

## Reading order for first-time onboarding

| # | File | Audience | Why |
|---|------|----------|-----|
| 1 | [`agent_brief.md`](agent_brief.md) | **AI agent** (also good for humans) | Minimum context to be productive. Mission, mermaid architecture, hard rules, "where to look" table, end-to-end commands, backlog. |
| 2 | [`architecture.md`](architecture.md) | Human + agent | Layer model, decision log (Path A chunker, tag uniqueness, breaker policy, …), run lifecycle diagram, dispatch modes. |
| 3 | [`graph_schema.md`](graph_schema.md) | Anyone touching Cypher | The Neo4j artefact contract: every node label, every edge type, properties, constraints, indexes, who writes/reads. |
| 4 | [`codebase_map.md`](codebase_map.md) | Anyone navigating the source | One section per top-level dir, every file with a one-line role and key public symbols. |
| 5 | [`runbook.md`](runbook.md) | Operator | First-time setup, bootstrap → preflight → run_index, common failures and fixes, wipe-and-restart. |
| 6 | [`prompts.md`](prompts.md) | Anyone editing `prompts/` | Catalogue of LLM prompts, inputs, output schemas, validation/retry behaviour, editing rules. |
| 7 | [`env_and_config.md`](env_and_config.md) | Operator | Every env var, defaults, where consumed, alias precedence (`LLM_*` wins over `AGENT_*`). |
| 8 | [`status.md`](status.md) | Anyone planning the next step | Truthful snapshot: what is verified, what is built but unverified, known gaps, decisions to revisit. |

## How docs cross-link

- Internal links use **relative paths** (e.g. [`../indexing/breaker.py`](../indexing/breaker.py), [`graph_schema.md`](graph_schema.md)).
- Hard rules live in `agent_brief.md`. Decisions and trade-offs live in `architecture.md`. Concrete contracts (Cypher, prompts, env) live in their dedicated files. Don't duplicate.
- When code changes affect a contract (schema, prompt JSON shape, env vars), update the matching doc in the same change.

## Hard rules (mirror of `agent_brief.md` for quick scan)

- **No fallbacks. No mocks.** Fail loud. The agent client never raises; the orchestrator decides. Everywhere else, raise.
- **One LLM endpoint.** OpenAI-compatible HTTP. Configured via `LLM_*` env (legacy `AGENT_*` honoured). No local model fallback.
- **Per-error-class circuit breaker.** Tight thresholds (see [`../indexing/breaker.py`](../indexing/breaker.py)).
- **Working-file job ledger drives agent scheduling.** Do not store scheduler rows in the graph.
- **Neo4j is the only durable store.** No parquet/JSON side artefacts in the indexing path.

# Agents

This backend project is documented in [`docs/`](docs/README.md).

Run backend commands from `backend/`. Paths in backend docs are relative to this directory unless they explicitly say monorepo root.

If you are an AI agent picking up this codebase, start with [`docs/agent_brief.md`](docs/agent_brief.md). The graph schema is the contract; see [`docs/graph_schema.md`](docs/graph_schema.md).

## Hard rules

- No fallbacks. No mocks. Fail loud.
- One OpenAI-compatible LLM endpoint (configured via `LLM_*` env; legacy `AGENT_*` aliases honoured, `LLM_*` wins).
- The agent client never raises — see [`agents/client.py`](agents/client.py); the orchestrator decides what to do with `error_class`.
- Per-error-class circuit breaker — see [`indexing/breaker.py`](indexing/breaker.py).
- Working-file job ledger drives agent scheduling — see [`indexing/worklist.py`](indexing/worklist.py).
- **Neo4j is the only durable store.** No parquet/JSON side artefacts in the indexing path.

Never echo `.env` contents, API keys, or passwords into any file or log.

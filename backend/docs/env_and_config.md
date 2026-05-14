# Environment and Configuration

**TL;DR.** Settings come from `.env` (gitignored) loaded by `pydantic-settings` in [`shared/config.py`](../shared/config.py). The legacy indexing path uses `LLM_*`; legacy `AGENT_*` names work for the same fields and `LLM_*` wins when both are set. The HERB tagging pilot uses `ANTHROPIC_*` directly in `tagging/pipeline.py`. Neo4j is configured via `NEO4J_*`. Embeddings/data root have their own keys. Nothing in this doc echoes secrets.

**When to read this.** Before running anything. Whenever you wonder where a setting is consumed.

**Last updated:** 2026-05-13.

## Touched paths

`shared/config.py`, `.env.example`, `scripts/run_index.py`, `scripts/bootstrap_schema.py`, `scripts/run_preflight.py`, `agents/client.py`, `shared/neo4j_client.py`, `tagging/pipeline.py`.

## Loading mechanism

[`shared/config.Settings`](../shared/config.py) is a `BaseSettings` subclass with:

```python
model_config = SettingsConfigDict(
    env_file=str(REPO_ROOT / ".env"),
    env_file_encoding="utf-8",
    extra="ignore",
)
```

That means:

- Values come from `.env` first, then process env vars (which override).
- Unknown keys are ignored (`extra="ignore"`), so `.env` can contain extras like `HF_TOKEN` without breaking config loading.
- `.env` lives at the backend root (`backend/.env` in the monorepo) and is gitignored.

## Precedence: `LLM_*` vs `AGENT_*`

The agent fields use `pydantic.AliasChoices`:

```python
agent_base_url: str = Field(
    default=_DEFAULT_LLM_BASE_URL,
    validation_alias=AliasChoices("LLM_BASE_URL", "AGENT_BASE_URL"),
)
```

`AliasChoices` resolves **left-to-right**: if both `LLM_BASE_URL` and `AGENT_BASE_URL` are set, `LLM_BASE_URL` wins. Recommended: use the `LLM_*` names; only keep `AGENT_*` around for older `.env` files.

## Variables

### LLM (OpenAI-compatible HTTP API)

| Var | Type | Default | Required | Where consumed |
|---|---|---|---|---|
| `LLM_BASE_URL` (or `AGENT_BASE_URL`) | string | `https://api.openai.com/v1` | No | [`agents/client.AgentClient`](../agents/client.py) — passed to `httpx.AsyncClient(base_url=...)`. Must be the API root that exposes `/chat/completions`. For OpenAI: `…/v1`. For other compatible providers: their root. Blank value falls back to default. |
| `LLM_MODEL` (or `AGENT_MODEL`) | string | `gpt-4o-mini` | No | Sent as `body["model"]` in every chat completion. Stamped on `:Run.agent_model`. Blank value falls back to default. |
| `LLM_API_KEY` (or `AGENT_API_KEY`) | string (secret) | empty | **Yes** for `run_index.py` | Sent as `Authorization: Bearer ...`. [`scripts/run_index.py`](../scripts/run_index.py) exits with code 2 if not set. Bootstrap and preflight don't read it. |
| `LLM_TIMEOUT_SECONDS` (or `AGENT_TIMEOUT_SECONDS`) | float | `30.0` | No | `httpx.AsyncClient(timeout=...)`. Timeouts surface as `error_class="timeout"`. |
| `LLM_MAX_CONCURRENCY` (or `AGENT_MAX_CONCURRENCY`) | int (≥1) | `32` | No | `Orchestrator._semaphore = asyncio.Semaphore(...)`. Stamped on `:Run.agent_max_concurrency`. CLI override: `python scripts/run_index.py --concurrency N`. |

### HERB tagging pilot (Anthropic Messages API)

These are not read by `shared/config.py`. They are loaded from `.env` by
[`tagging/pipeline.py`](../tagging/pipeline.py) for the HERB-specific pilot.

| Var | Type | Default | Required | Where consumed |
|---|---|---|---|---|
| `ANTHROPIC_API_KEY` | string (secret) | none | **Yes** for `python -m tagging extract/describe/score` | Passed to `anthropic.AsyncAnthropic`. Never log or commit it. |
| `ANTHROPIC_MODEL` | string | `claude-haiku-4-5` | No | Anthropic model used by `ClaudeCaller`; aliases `claude-4-5-haiku` and `claude-haiku-4.5` normalize to `claude-haiku-4-5`. |
| `PILOT_NAME` | string | `pilot_format_smoke` | No | Run directory under `data/tagging_runs/`. |
| `TAGGING_SAMPLE_SIZE` | int | `14` | No | Number of selected chunks for `select`. |
| `TAGGING_SELECTION_MODE` | string | `herb_kind_coverage` | No | Selection strategy. Default chooses one representative chunk per HERB evidence shape. |
| `TAGGING_SELECTION_SEED` | int | `0` | No | Deterministic seed for random selection mode. |

### Neo4j

| Var | Type | Default | Required | Where consumed |
|---|---|---|---|---|
| `NEO4J_URI` | string | `neo4j://localhost:7687` | Effectively yes for any DB-touching script | [`shared/neo4j_client.Neo4jClient`](../shared/neo4j_client.py). Use `neo4j://` for routing-aware (recommended); `bolt://` for direct connections. |
| `NEO4J_USER` | string | `neo4j` | Yes | Same. |
| `NEO4J_PASSWORD` | string (secret) | empty | Yes | Same. |
| `NEO4J_DATABASE` | string | `neo4j` | Yes (in practice) | Passed to `driver.session(database=...)`. To run against a fresh DB on Enterprise, create it via [`schema/create_database.cypher`](../schema/create_database.cypher) and set this to its name. |

### Other

| Var | Type | Default | Required | Where consumed |
|---|---|---|---|---|
| `EMBEDDING_MODEL` | string | `intfloat/e5-small-v2` | No | Read into `Settings.embedding_model`. **Not currently consumed by any code path** — embeddings/vector indexes are deferred. Kept so `.env` template stays stable for the reintroduction. |
| `DATA_ROOT` | path | `<backend>/data` | No | Read into `Settings.data_root`. [`indexing/preflight.py`](../indexing/preflight.py) calls `scan_raw_tree(settings.data_root)` to walk `data/raw/`. The `data_access/` CLI tools accept `--data-root` to override per-invocation. |

### Recognised extras (ignored by Settings, used by other tools)

| Var | Where used |
|---|---|
| `HF_TOKEN` | [`data_access/raw/__main__.py`](../data_access/raw/__main__.py) — `--hf-token` default for `python -m data_access.raw sync`. Not loaded by `Settings`. |

## Quick `.env` shape (no secrets here)

See [`.env.example`](../.env.example) for the live template (it carries Swedish + English commentary). Minimum viable shape:

```dotenv
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=...                # required for run_index.py
LLM_MAX_CONCURRENCY=32
LLM_TIMEOUT_SECONDS=30

# Required only for the HERB Anthropic tagging pilot API stages.
ANTHROPIC_API_KEY=sk-ant-replace-with-your-key
ANTHROPIC_MODEL=claude-haiku-4-5

NEO4J_URI=neo4j://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=...
NEO4J_DATABASE=exjobbet_index   # or 'neo4j' if not on Enterprise

EMBEDDING_MODEL=intfloat/e5-small-v2
```

## Validation behaviour

- Blank `LLM_BASE_URL` / `LLM_MODEL` (e.g. `LLM_BASE_URL=`) → falls back to the OpenAI defaults via `field_validator(..., mode="before")` in [`shared/config.py`](../shared/config.py).
- Negative or zero `LLM_MAX_CONCURRENCY` → pydantic raises (the field has `ge=1`).
- Missing `LLM_API_KEY` is **only** validated by `scripts/run_index.py`, which prints a bilingual error and exits with code 2 before opening Neo4j or the agent client. Bootstrap and preflight don't need the key.

## Where settings are stamped onto the graph

- `:Run.agent_model` ← `Settings.agent_model`
- `:Run.agent_max_concurrency` ← `Settings.agent_max_concurrency` (or the `--concurrency` override)
- `:Run.git_commit` ← `git rev-parse HEAD` from [`indexing/runs._git_commit`](../indexing/runs.py)

The API key, base URL, and Neo4j password are **never** persisted to the graph or any log line. Don't add new code that does so.

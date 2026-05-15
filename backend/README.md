# Thesis indexing pipeline

Offline Python pipeline. **HERB (thesis path):** chunk under `data/raw/`, preflight, **`python -m tagging extract`** (Anthropic) → Neo4j. Neo4j is the only durable artefact.

```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate    # Linux/macOS: . .venv/bin/activate
pip install -r requirements-lock.txt
cp .env.example .env                                 # NEO4J_PASSWORD, ANTHROPIC_API_KEY; use NEO4J_DATABASE=herb for HERB

python scripts/bootstrap_schema.py
python scripts/run_preflight.py --dataset-id Salesforce__HERB
python -m tagging extract                            # HERB Anthropic path (current)
python scripts/verify_graph.py                         # read-only counts
```

**Legacy:** `scripts/run_index.py` and the OpenAI-compatible stack under `agents/`, `prompts/`, and orchestrator-related `indexing/` files are **quarantined** from default Cursor indexing — see repo root **`.cursorignore`** and [`../quarantine/DO_NOT_READ_UNLESS_LEGACY.md`](../quarantine/DO_NOT_READ_UNLESS_LEGACY.md). Do not use for HERB unless explicitly forced.

Docs: [`../docs/`](../docs/README.md). Agents: [`../AGENTS.md`](../AGENTS.md). HERB map: [`../docs/system_map.md`](../docs/system_map.md).

## Layout (HERB-relevant first)

- `tagging/` — HERB Anthropic tagging pilot harness.
- `data_access/` — dataset sync, raw-tree scan, classification (access layer inventory).
- `indexing/` — **HERB:** `chunker`, `preflight`, `worklist`, `runs`, `breaker`. **Legacy (quarantined):** orchestrator, extraction/file writers, rollup — see quarantine manifest.
- `schema/` — Cypher constraints/indexes applied at bootstrap.
- `scripts/` — operator entry points (`run_preflight`, `verify_graph`, …).
- `shared/` — config, async Neo4j wrapper, **`error_class`** (breaker types decoupled from `agents/`), small utilities.
- `clustering/` — placeholder for future HERB query views.

# System map

**Purpose.** One entry page for humans and AI agents: **concepts**, **where they live** (backend / frontend / Neo4j), and **which doc** is authoritative.

**Scope (read this first).** This map describes **only the HERB path in actual use**: raw corpus **`Salesforce__HERB`**, Neo4j database **`herb`**, semantic artefact **`pilot_full_herb`**. The generic three-stage indexer (`scripts/run_index.py`, `indexing/orchestrator.py`, OpenAI-compatible `agents/` path, other datasets in `data_access` registry) is **quarantined** — it is not what you run or defend for HERB. See [Quarantine](#quarantine-legacy--non-herb).

**Companion pages.** Rules and commands: [`/AGENTS.md`](../AGENTS.md). Full doc index: [`README.md`](README.md). Graph contract: [`graph_schema.md`](graph_schema.md).

---

## HERB — end-to-end data flow

| Stage | Role | Backend | Frontend |
|---|---|---|---|
| Raw corpus | On-disk HERB tree: `backend/data/raw/Salesforce__HERB/` | — | — |
| Access layer | Join disk → graph-addressable **`:Source` / `:File`** (inventory, hashes, paths, classification, payload rules). | **`backend/data_access/raw/`** (sync/scan/classify for HERB + other registered trees; HERB payload rules in `adapters.py`). **File/source upsert** in **`backend/indexing/preflight.py`**. | Canvas **Access Layer** = same concept ([`frontend/architecture.md`](frontend/architecture.md)). |
| Indexing (HERB) | **`:Chunk`**, **`locator_json`**, worklist seeding for tagging — **no** legacy orchestrator. | **`indexing/chunker.py`**, **`indexing/preflight.py`**, **`indexing/worklist.py`**, **`scripts/run_preflight.py`** (`--dataset-id Salesforce__HERB` when scoping). | Canvas **Index Layer** onward. |
| HERB tagging | Anthropic two-pass → **`HAS_TAG`** with **`facet`**, **`w_chunk`**, **`w_facet`**, **`relevance_to_file`**. | **`backend/tagging/pipeline.py`**, **`python -m tagging …`** | — (consumes graph only). |
| Workbench + interpretation | Read **`herb`** + browser Anthropic two-pass (aligned facets). | — | **`frontend/src/App.jsx`**, `neo4j-driver`, `@anthropic-ai/sdk`; spec [`frontend/query_interpretation_layer.md`](frontend/query_interpretation_layer.md). |

Canonical write-up of access vs indexing for the whole repo (includes legacy): [`backend/architecture.md`](backend/architecture.md).

---

## HERB — concept → authoritative doc

| Concept | Doc |
|---|---|
| Neo4j contract (labels, HERB edge fields) | [`graph_schema.md`](graph_schema.md) |
| Access layer vs indexing (full repo, includes legacy) | [`backend/architecture.md`](backend/architecture.md) |
| Env (`NEO4J_*`, `ANTHROPIC_*`, `DATA_ROOT`, …) | [`backend/env_and_config.md`](backend/env_and_config.md) |
| Commands, bootstrap, preflight, tagging CLI | [`backend/runbook.md`](backend/runbook.md) |
| HERB model I/O and graph writes | [`backend/herb_tagging_schema.md`](backend/herb_tagging_schema.md) |
| HERB evidence shapes → frames | [`backend/herb_tagging_frames.md`](backend/herb_tagging_frames.md) |
| Full-corpus HERB run (method + numbers) | [`backend/pilot_full_herb_report.md`](backend/pilot_full_herb_report.md) |
| Workbench UI + browser-direct | [`frontend/architecture.md`](frontend/architecture.md) |
| Browser prompt interpretation | [`frontend/query_interpretation_layer.md`](frontend/query_interpretation_layer.md) |
| Built state / next steps | [`backend/status.md`](backend/status.md), [`frontend/status.md`](frontend/status.md), [`frontend/plans.md`](frontend/plans.md) |

---

## HERB — concept → code entry

| Concept | Primary path |
|---|---|
| Access layer — inventory (sync, scan, classify, HERB in `PAYLOAD_PATTERNS`) | `backend/data_access/raw/` |
| Access layer — `:Source` / `:File` upsert | `backend/indexing/preflight.py` |
| Chunking + locators (HERB-aware) | `backend/indexing/chunker.py` |
| Preflight entrypoint | `backend/scripts/run_preflight.py` |
| Worklist seed (tagging jobs) | `backend/indexing/worklist.py` |
| HERB tagging pilot | `backend/tagging/pipeline.py`, `backend/tagging/__main__.py` |
| Active workbench | `frontend/src/App.jsx` |
| Pipeline node registry / demo counts | `frontend/src/data/workbenchData.ts` |
| Query-module Cypher helpers | `frontend/src/query/queryModuleSyntax.ts` |
| Shared TS types | `frontend/src/types/index.ts` |

---

## HERB artefact anchor

- **Dataset id:** `Salesforce__HERB`
- **Neo4j database:** `herb`
- **Run id:** `pilot_full_herb`
- **Portable archive:** `backend/data/tagging_runs/pilot_full_herb_snapshot_20260514T052226Z.zip`
- **Report:** [`backend/pilot_full_herb_report.md`](backend/pilot_full_herb_report.md)

---

## Facets (HERB + browser)

`topic`, `entities`, `activity`, `temporal`, `evidence` — on HERB **`HAS_TAG`** edges and in browser interpretation. Literal: `backend/agents/schemas.py` (`Cluster`). Field names: [`/AGENTS.md`](../AGENTS.md) hard rules (`facet`, `w_chunk`, `w_facet`, not legacy `cluster` / `weight_local` on the HERB read path).

---

## Agent navigation (HERB only)

1. **Graph shape / HERB properties** → [`graph_schema.md`](graph_schema.md) + `backend/schema/*.cypher`
2. **Chunks / locators for HERB** → [`backend/architecture.md`](backend/architecture.md) + `chunker.py` + `preflight.py`
3. **Tagging behaviour** → [`backend/herb_tagging_schema.md`](backend/herb_tagging_schema.md) + `tagging/pipeline.py`
4. **Workbench / interpretation** → [`frontend/architecture.md`](frontend/architecture.md) + [`frontend/query_interpretation_layer.md`](frontend/query_interpretation_layer.md) + `App.jsx`

---

## Quarantine (legacy / non-HERB)

**Do not treat this as the thesis delivery path for HERB.** These paths are listed in **`.cursorignore`** at the repo root — **do not** `read_file` or cite them unless the user **explicitly** asks for legacy indexing. Full manifest: [`quarantine/DO_NOT_READ_UNLESS_LEGACY.md`](../quarantine/DO_NOT_READ_UNLESS_LEGACY.md).

| Piece | What it is |
|---|---|
| **`quarantine/legacy_mirror/backend/`** | Full archived legacy Python (orchestrator, writers, `agents/`, run scripts). **`.cursorignore`d.** Loaded at runtime by **small shims** at the old paths — see [`quarantine/DO_NOT_READ_UNLESS_LEGACY.md`](../../quarantine/DO_NOT_READ_UNLESS_LEGACY.md). |
| `python scripts/run_index.py` | Thin shim → `run_index_legacy.py` in the mirror. Legacy generic indexer; **refuses HERB** unless `--allow-legacy-herb-tagging`. |
| `backend/prompts/` | Legacy LLM prompt bodies (`.cursorignore`d). HERB uses `tagging/` + `herb_tagging_schema.md`. |
| Other `HF_DATASETS` / `data/raw/*` dirs | DocVQA, FEVEROUS, HybridQA, etc. — **not** the HERB corpus you ship. |
| `docs/backend/prompts.md` | Legacy prompt catalogue (`.cursorignore`d). |

Per-file backend navigation that still lists everything: [`backend/codebase_map.md`](backend/codebase_map.md) — use the HERB sections above first.

If something HERB-critical is missing from this file, add one row under the right HERB table.

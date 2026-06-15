# Legacy stack — do not read unless explicitly requested

The thesis **HERB** path does not use this stack. Default Cursor indexing excludes **`quarantine/legacy_mirror/`** and **`backend/prompts/`** (see repo **`.cursorignore`**).

## Archived implementations (`quarantine/legacy_mirror/backend/`)

These files are **full copies** of the old generic OpenAI-compatible indexer. They are loaded at runtime by **thin shims** in the main tree:

| Shim (HERB-era, small) | Loads from |
|---|---|
| `backend/indexing/orchestrator.py` | `quarantine/legacy_mirror/backend/indexing/orchestrator_legacy.py` |
| `backend/indexing/extraction_writer.py` | `.../extraction_writer_legacy.py` |
| `backend/indexing/file_writer.py` | `.../file_writer_legacy.py` |
| `backend/indexing/file_rollup.py` | `.../file_rollup_legacy.py` |
| `backend/agents/client.py` | `.../agents/client.py` |
| `backend/agents/schemas.py` | `.../agents/schemas.py` |
| `backend/scripts/run_index.py` | `runpy` → `.../scripts/run_index_legacy.py` |
| `backend/scripts/run_tags_only_pilot.py` | `runpy` → `.../scripts/run_tags_only_pilot_legacy.py` |

Loader helper: `backend/shared/legacy_mirror_boot.py` (`sys.modules` registration for non-agent modules).

**Run legacy CLI from repo root:**

```bash
cd backend
python scripts/run_index.py --help
```

(Shim forwards to `run_index_legacy.py`, which sets `REPO_ROOT` to the real `backend/` package.)

## Prompt files

Legacy prompt bodies remain under **`backend/prompts/`** (`.cursorignore`d). HERB tagging uses `docs/backend/herb_tagging_schema.md` and `tagging/`, not these files.

## Noise directories

| Path | Role |
|---|---|
| `.claude/` | Tool worktrees / local agent state |
| `backend/.plan/` | Scratch planning |
| `frontend/updated/` | Old static prototype |

## What was not split yet

**`backend/indexing/chunker.py`** is still one large module (HERB-aware kinds mixed with other format handlers). A future split can mirror+shim the same way if you want a HERB-only surface file.

## Decision log

[`docs/backend/architecture.md`](../docs/backend/architecture.md) still mixes HERB and legacy history — read the **Thesis scope (HERB) and quarantine** banner first.

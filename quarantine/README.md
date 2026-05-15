# Quarantine

**Default rule:** Do not read **`quarantine/legacy_mirror/`** or **`backend/prompts/`** unless the owner explicitly asks for legacy generic indexing. Cursor honours **`.cursorignore`** at the repo root.

- **Manifest:** [`DO_NOT_READ_UNLESS_LEGACY.md`](DO_NOT_READ_UNLESS_LEGACY.md)
- **HERB work:** [`/AGENTS.md`](../AGENTS.md), [`/docs/system_map.md`](../docs/system_map.md)

**Layout:** Full legacy Python lives under **`legacy_mirror/backend/`**. The repo still contains **small shims** at the original import paths (`backend/indexing/orchestrator.py`, `backend/agents/client.py`, …) that `importlib`/`runpy` into the mirror so `python scripts/run_index.py` keeps working without duplicating logic in the hot path files agents are meant to read.

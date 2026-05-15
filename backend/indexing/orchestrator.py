"""Legacy three-stage orchestrator (OpenAI-compatible).

Implementation is archived under ``quarantine/legacy_mirror/backend/indexing/``.
This shim keeps import paths stable for ``scripts/run_index.py``. HERB uses
``python -m tagging extract`` instead.
"""

from __future__ import annotations

from shared.legacy_mirror_boot import load_module

_m = load_module("indexing", "orchestrator_legacy.py")

CHUNK_BATCH_SIZE = _m.CHUNK_BATCH_SIZE
FILE_BATCH_SIZE = _m.FILE_BATCH_SIZE
PREV_TAIL_CHARS = _m.PREV_TAIL_CHARS
FILE_INVENTORY_DESC_MAX = _m.FILE_INVENTORY_DESC_MAX
Orchestrator = _m.Orchestrator

__all__ = [
    "CHUNK_BATCH_SIZE",
    "FILE_BATCH_SIZE",
    "PREV_TAIL_CHARS",
    "FILE_INVENTORY_DESC_MAX",
    "Orchestrator",
]

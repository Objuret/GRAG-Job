"""Deterministic ``(:File)-[:TAGGED]->(:Tag)`` rollup (legacy orchestrator path).

Implementation: ``quarantine/legacy_mirror/backend/indexing/file_rollup_legacy.py``.
"""

from __future__ import annotations

from shared.legacy_mirror_boot import load_module

_m = load_module("indexing", "file_rollup_legacy.py")
FileRollup = _m.FileRollup

__all__ = ["FileRollup"]

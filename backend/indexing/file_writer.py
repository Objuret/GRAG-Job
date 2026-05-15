"""Writes ``FileOrchestrationOutput`` to Neo4j (legacy orchestrator path).

Implementation: ``quarantine/legacy_mirror/backend/indexing/file_writer_legacy.py``.
"""

from __future__ import annotations

from shared.legacy_mirror_boot import load_module

_m = load_module("indexing", "file_writer_legacy.py")
FileExtractionWriter = _m.FileExtractionWriter

__all__ = ["FileExtractionWriter"]

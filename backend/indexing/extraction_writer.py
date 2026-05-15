"""Writes ``ChunkExtraction`` results to Neo4j (legacy orchestrator path).

Implementation: ``quarantine/legacy_mirror/backend/indexing/extraction_writer_legacy.py``.
"""

from __future__ import annotations

from shared.legacy_mirror_boot import load_module

_m = load_module("indexing", "extraction_writer_legacy.py")
ExtractionWriter = _m.ExtractionWriter

__all__ = ["ExtractionWriter"]

"""Pydantic schemas for legacy chunk/file extraction.

Implementation: ``quarantine/legacy_mirror/backend/agents/schemas.py`` (archived copy).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_LEGACY = (
    Path(__file__).resolve().parents[2]
    / "quarantine"
    / "legacy_mirror"
    / "backend"
    / "agents"
    / "schemas.py"
)
_spec = importlib.util.spec_from_file_location("agents.schemas", _LEGACY)
_module = importlib.util.module_from_spec(_spec)
assert _spec.loader
sys.modules["agents.schemas"] = _module
_spec.loader.exec_module(_module)

Cluster = _module.Cluster
Tag = _module.Tag
ChunkExtraction = _module.ChunkExtraction
FileOrchestrationOutput = _module.FileOrchestrationOutput

__all__ = ["Cluster", "Tag", "ChunkExtraction", "FileOrchestrationOutput"]

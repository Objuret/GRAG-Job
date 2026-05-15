"""OpenAI-compatible agent client (legacy orchestrator path).

Implementation: ``quarantine/legacy_mirror/backend/agents/client.py`` (archived copy).
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
    / "client.py"
)
_spec = importlib.util.spec_from_file_location("agents.client", _LEGACY)
_module = importlib.util.module_from_spec(_spec)
assert _spec.loader
sys.modules["agents.client"] = _module
_spec.loader.exec_module(_module)

AgentClient = _module.AgentClient
AgentConfig = _module.AgentConfig
AgentResult = _module.AgentResult

__all__ = ["AgentClient", "AgentConfig", "AgentResult"]

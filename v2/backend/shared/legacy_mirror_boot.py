"""Load Python modules archived under quarantine/legacy_mirror/backend/."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_module(*relative_parts: str):
    """Load ``quarantine/legacy_mirror/backend/<relative_parts>`` as a one-off module."""
    path = _repo_root() / "quarantine" / "legacy_mirror" / "backend" / Path(*relative_parts)
    mod_name = "legacy_mirror." + "_".join(relative_parts).replace("\\", "/").replace("/", "_").replace(".py", "")
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load legacy mirror module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module

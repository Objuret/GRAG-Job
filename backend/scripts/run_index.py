"""CLI for the legacy generic indexing orchestrator (quarantined implementation).

HERB thesis path: ``python -m tagging extract`` after ``run_preflight``.
Full legacy script: ``quarantine/legacy_mirror/backend/scripts/run_index_legacy.py``.
"""

from __future__ import annotations

import runpy
from pathlib import Path


def main() -> None:
    legacy = (
        Path(__file__).resolve().parents[2]
        / "quarantine"
        / "legacy_mirror"
        / "backend"
        / "scripts"
        / "run_index_legacy.py"
    )
    runpy.run_path(str(legacy), run_name="__main__")


if __name__ == "__main__":
    main()

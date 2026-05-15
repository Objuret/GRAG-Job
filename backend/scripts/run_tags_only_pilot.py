"""Non-mutating tags-only pilot (legacy; quarantined implementation).

Full legacy script: ``quarantine/legacy_mirror/backend/scripts/run_tags_only_pilot_legacy.py``.
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
        / "run_tags_only_pilot_legacy.py"
    )
    runpy.run_path(str(legacy), run_name="__main__")


if __name__ == "__main__":
    main()

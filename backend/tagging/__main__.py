"""CLI for the HERB tagging pilot.

Usage:
    python -m backend.tagging select
    python -m backend.tagging verify-chunks
    python -m backend.tagging extract
    python -m backend.tagging describe
    python -m backend.tagging score
    python -m backend.tagging analyze
"""

from __future__ import annotations

import asyncio
import sys

from . import pipeline

STAGES = {
    "verify-chunks": pipeline.stage_verify_chunks,
    "select": pipeline.stage_select,
    "extract": pipeline.stage_extract,
    "describe": pipeline.stage_describe,
    "score": pipeline.stage_score,
    "analyze": pipeline.stage_analyze,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in STAGES:
        print(__doc__)
        sys.exit(2)
    asyncio.run(STAGES[sys.argv[1]]())


if __name__ == "__main__":
    main()

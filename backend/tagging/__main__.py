"""CLI for the HERB tagging pilot.

Usage:
    python -m tagging select
    python -m tagging verify-chunks
    python -m tagging extract
    python -m tagging describe
    python -m tagging score
    python -m tagging embed-tags
    python -m tagging analyze
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
    "embed-tags": pipeline.stage_embed_tags,
    "analyze": pipeline.stage_analyze,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in STAGES:
        print(__doc__)
        sys.exit(2)
    asyncio.run(STAGES[sys.argv[1]]())


if __name__ == "__main__":
    main()

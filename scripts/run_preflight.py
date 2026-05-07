"""Run pre-flight: scan raw datasets, upsert Source/File nodes, chunk, seed WorkItems.

    python scripts/run_preflight.py

Idempotent. Safe to re-run (skips files that are already chunked).
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from indexing.preflight import run_preflight
from shared.config import Settings
from shared.neo4j_client import Neo4jClient


async def main() -> None:
    settings = Settings()
    client = Neo4jClient(settings)
    try:
        result = await run_preflight(settings, client)
        lines = [
            "Pre-flight complete:",
            f"  files_seen        = {result.files_seen}",
            f"  files_new         = {result.files_new}",
            f"  chunks_created    = {result.chunks_created}",
            f"  work_items_seeded = {result.work_items_seeded}",
            f"  failures          = {len(result.failures)}",
        ]
        print(chr(10).join(lines))
        if result.failures:
            print("")
            print("Per-file failures:")
            print(json.dumps(result.failures, indent=2, ensure_ascii=False))
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())

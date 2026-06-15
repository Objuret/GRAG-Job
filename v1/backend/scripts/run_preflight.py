"""Run pre-flight: scan raw datasets, upsert Source/File nodes, chunk, update working file.

    python scripts/run_preflight.py [--dataset-id DATASET_ID]

Idempotent. Safe to re-run (skips files that are already chunked).
"""

from __future__ import annotations

import asyncio
import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from indexing.preflight import run_preflight
from shared.config import Settings
from shared.neo4j_client import Neo4jClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run pre-flight: scan raw datasets, upsert File nodes, chunk, update working file."
    )
    parser.add_argument(
        "--dataset-id",
        default=None,
        help="Limit preflight to one dataset_id, e.g. Salesforce__HERB.",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    settings = Settings()
    client = Neo4jClient(settings)
    try:
        result = await run_preflight(
            settings,
            client,
            dataset_id_filter=args.dataset_id,
        )
        lines = [
            "Pre-flight complete:",
            f"  files_seen        = {result.files_seen}",
            f"  files_new         = {result.files_new}",
            f"  skipped_no_chunks = {result.files_skipped_no_chunks}",
            f"  chunks_created    = {result.chunks_created}",
            f"  working_items_seeded = {result.working_items_seeded}",
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

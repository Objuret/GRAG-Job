"""Quick sanity check: herb-eval vs herb-eval-backup row counts."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from shared.config import Settings  # noqa: E402
from neo4j import AsyncGraphDatabase  # noqa: E402


async def counts(session) -> dict:
    out: dict[str, int] = {}
    for label in ("Source", "File", "Chunk", "Tag"):
        rec = await session.run(f"MATCH (n:{label}) RETURN count(n) AS n")
        out[f"node:{label}"] = (await rec.single())["n"]
    for rel in ("CONTAINS", "HAS_CHUNK", "HAS_TAG"):
        rec = await session.run(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS n")
        out[f"rel:{rel}"] = (await rec.single())["n"]
    return out


async def main() -> None:
    s = Settings()
    driver = AsyncGraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
    try:
        async with driver.session(database="herb-eval") as session:
            live = await counts(session)
        async with driver.session(database="herb-eval-backup") as session:
            backup = await counts(session)
    finally:
        await driver.close()

    keys = sorted(set(live) | set(backup))
    print(f"{'metric':25s} {'herb-eval':>12s} {'herb-eval-backup':>18s}  match")
    all_match = True
    for k in keys:
        a, b = live.get(k), backup.get(k)
        match = "OK" if a == b else "MISMATCH"
        if a != b:
            all_match = False
        print(f"{k:25s} {a!s:>12s} {b!s:>18s}  {match}")
    print()
    print("ALL MATCH" if all_match else "DIVERGENCE DETECTED")


if __name__ == "__main__":
    asyncio.run(main())

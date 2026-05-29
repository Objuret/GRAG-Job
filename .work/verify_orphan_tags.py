"""What are the 23 tags missing embeddings?"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
os.environ["NEO4J_DATABASE"] = "herb-eval"

from shared.config import Settings  # noqa: E402
from neo4j import AsyncGraphDatabase  # noqa: E402


def fmt(rec: dict) -> str:
    return json.dumps({k: v for k, v in rec.items()}, default=str)


async def run_query(session, q: str, **params):
    res = await session.run(q, **params)
    return [{k: r.get(k) for k in r.keys()} async for r in res]


async def main() -> None:
    s = Settings()
    driver = AsyncGraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
    try:
        async with driver.session(database="herb-eval") as session:
            print("--- all 23 tags missing emb_all (or any embedding) ---")
            for r in await run_query(session, """
                MATCH (t:Tag) WHERE t.emb_all IS NULL
                OPTIONAL MATCH (:Chunk)-[r:HAS_TAG]->(t)
                WITH t, count(r) AS n_edges, collect(DISTINCT r.facet) AS facets,
                     collect(DISTINCT r.run_id) AS runs
                RETURN t.name AS tag,
                       size(t.name) AS name_len,
                       n_edges, facets, runs,
                       t.embedding_model AS model
                ORDER BY n_edges DESC, tag
            """):
                print(fmt(r))

            print("\n--- properties on a sample missing-emb tag (full dump) ---")
            for r in await run_query(session, """
                MATCH (t:Tag) WHERE t.emb_all IS NULL
                RETURN t.name AS name, properties(t) AS props
                LIMIT 3
            """):
                print(fmt(r))

            print("\n--- compare a healthy tag vs a missing one ---")
            for r in await run_query(session, """
                MATCH (t:Tag) WHERE t.emb_all IS NOT NULL
                RETURN t.name AS name, keys(t) AS keys
                LIMIT 1
            """):
                print(fmt(r))
            for r in await run_query(session, """
                MATCH (t:Tag) WHERE t.emb_all IS NULL
                RETURN t.name AS name, keys(t) AS keys
                LIMIT 1
            """):
                print(fmt(r))
    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())

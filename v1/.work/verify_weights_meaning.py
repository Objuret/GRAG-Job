"""Verify w_chunk constancy across facet siblings of one (chunk, tag) pair."""

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
            print("--- is w_chunk constant across facet siblings of one (chunk, tag) ? ---")
            for r in await run_query(session, """
                MATCH (c:Chunk)-[r:HAS_TAG]->(t:Tag)
                WITH c, t, count(DISTINCT r.w_chunk) AS distinct_w_chunk, count(r) AS n_edges
                WHERE n_edges > 1
                RETURN distinct_w_chunk, count(*) AS n_chunk_tag_pairs
                ORDER BY distinct_w_chunk
            """):
                print(fmt(r))

            print("\n--- sample a multi-facet (chunk, tag) and show all sibling edges ---")
            for r in await run_query(session, """
                MATCH (c:Chunk)-[r:HAS_TAG]->(t:Tag {name: 'salesforce'})
                WITH c, t, collect({facet: r.facet, w_facet: r.w_facet, w_chunk: r.w_chunk}) AS edges
                WHERE size(edges) >= 3
                RETURN c.chunk_id AS chunk_id, t.name AS tag, edges
                LIMIT 3
            """):
                print(fmt(r))

            print("\n--- relationship between w_chunk and w_facet on the same edge ---")
            for r in await run_query(session, """
                MATCH ()-[r:HAS_TAG]->()
                WITH r.w_facet AS wf, r.w_chunk AS wc
                WHERE wf IS NOT NULL AND wc IS NOT NULL
                RETURN
                  toInteger(wf*10)/10.0 AS w_facet_bin,
                  count(*) AS n,
                  min(wc) AS min_wc,
                  avg(wc) AS mean_wc,
                  max(wc) AS max_wc
                ORDER BY w_facet_bin
            """):
                print(fmt(r))
    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())

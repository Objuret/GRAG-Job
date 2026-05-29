"""Tag-side verification against herb-eval."""

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
            print("=== TAG side, herb-eval ===\n")

            print("--- tags-per-chunk distribution ---")
            for r in await run_query(session, """
                MATCH (c:Chunk)
                OPTIONAL MATCH (c)-[r:HAS_TAG]->(:Tag)
                WITH c, count(r) AS n_tags
                RETURN count(c) AS chunks,
                       sum(CASE WHEN n_tags = 0 THEN 1 ELSE 0 END) AS orphan_chunks,
                       min(n_tags) AS min, max(n_tags) AS max,
                       avg(n_tags) AS mean,
                       percentileCont(n_tags, 0.1) AS p10,
                       percentileCont(n_tags, 0.5) AS p50,
                       percentileCont(n_tags, 0.9) AS p90
            """):
                print(fmt(r))

            print("\n--- edges-per-tag distribution ---")
            for r in await run_query(session, """
                MATCH (t:Tag)
                OPTIONAL MATCH (:Chunk)-[r:HAS_TAG]->(t)
                WITH t, count(r) AS n_edges
                RETURN count(t) AS tags,
                       sum(CASE WHEN n_edges = 0 THEN 1 ELSE 0 END) AS orphan_tags,
                       sum(CASE WHEN n_edges = 1 THEN 1 ELSE 0 END) AS singleton_tags,
                       min(n_edges) AS min, max(n_edges) AS max,
                       avg(n_edges) AS mean,
                       percentileCont(n_edges, 0.5) AS p50,
                       percentileCont(n_edges, 0.9) AS p90,
                       percentileCont(n_edges, 0.99) AS p99
            """):
                print(fmt(r))

            print("\n--- top 20 most-used tags ---")
            for r in await run_query(session, """
                MATCH (:Chunk)-[r:HAS_TAG]->(t:Tag)
                RETURN t.name AS tag, count(r) AS n_edges,
                       count(DISTINCT r.facet) AS n_facets
                ORDER BY n_edges DESC LIMIT 20
            """):
                print(fmt(r))

            print("\n--- tags by number of facets they appear under ---")
            for r in await run_query(session, """
                MATCH (:Chunk)-[r:HAS_TAG]->(t:Tag)
                WITH t, count(DISTINCT r.facet) AS n_facets
                RETURN n_facets, count(t) AS n_tags
                ORDER BY n_facets
            """):
                print(fmt(r))

            print("\n--- tag embedding population ---")
            for r in await run_query(session, """
                MATCH (t:Tag)
                RETURN count(t) AS tags,
                       sum(CASE WHEN t.emb_all IS NOT NULL THEN 1 ELSE 0 END) AS has_emb_all,
                       sum(CASE WHEN t.emb_topic IS NOT NULL THEN 1 ELSE 0 END) AS has_emb_topic,
                       sum(CASE WHEN t.emb_entities IS NOT NULL THEN 1 ELSE 0 END) AS has_emb_entities,
                       sum(CASE WHEN t.emb_activity IS NOT NULL THEN 1 ELSE 0 END) AS has_emb_activity,
                       sum(CASE WHEN t.emb_temporal IS NOT NULL THEN 1 ELSE 0 END) AS has_emb_temporal,
                       sum(CASE WHEN t.emb_evidence IS NOT NULL THEN 1 ELSE 0 END) AS has_emb_evidence
            """):
                print(fmt(r))

            print("\n--- embedding_model used ---")
            for r in await run_query(session, """
                MATCH (t:Tag) WHERE t.embedding_model IS NOT NULL
                RETURN DISTINCT t.embedding_model AS model, count(*) AS n
            """):
                print(fmt(r))

            print("\n--- tag name shape (sample of long-tail singletons) ---")
            for r in await run_query(session, """
                MATCH (:Chunk)-[r:HAS_TAG]->(t:Tag)
                WITH t, count(r) AS n_edges
                WHERE n_edges = 1
                RETURN t.name AS tag LIMIT 15
            """):
                print(fmt(r))

            print("\n--- distinct tags per facet (vocab size by facet) ---")
            for r in await run_query(session, """
                MATCH (:Chunk)-[r:HAS_TAG]->(t:Tag)
                RETURN r.facet AS facet, count(DISTINCT t) AS distinct_tags, count(r) AS edges
                ORDER BY edges DESC
            """):
                print(fmt(r))

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())

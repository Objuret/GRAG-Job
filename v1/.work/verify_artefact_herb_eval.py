"""
One-off live-graph verification against herb-eval.
"""

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
            print("=== DB target: herb-eval ===\n")

            print("--- node + edge counts ---")
            for r in await run_query(session, """
                MATCH (n) WITH labels(n) AS lbls
                UNWIND lbls AS l
                RETURN l AS label, count(*) AS n
                ORDER BY n DESC
            """):
                print(fmt(r))
            for r in await run_query(session, """
                MATCH ()-[r]->() RETURN type(r) AS rel, count(*) AS n ORDER BY n DESC
            """):
                print(fmt(r))

            print("\n--- chunks per file, by kind ---")
            for r in await run_query(session, """
                MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
                WITH coalesce(c.kind, '(null)') AS kind, f.file_id AS fid, count(c) AS per_file
                RETURN kind, count(*) AS n_files, sum(per_file) AS total_chunks,
                       min(per_file) AS min_pf,
                       percentileCont(per_file, 0.5) AS p50_pf,
                       percentileCont(per_file, 0.9) AS p90_pf,
                       max(per_file) AS max_pf
                ORDER BY total_chunks DESC
            """):
                print(fmt(r))

            print("\n--- chunks per file, by section ---")
            for r in await run_query(session, """
                MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
                WITH coalesce(c.section, '(null)') AS section, f.file_id AS fid, count(c) AS per_file
                RETURN section, count(*) AS n_files, sum(per_file) AS total_chunks,
                       min(per_file) AS min_pf,
                       percentileCont(per_file, 0.5) AS p50_pf,
                       percentileCont(per_file, 0.9) AS p90_pf,
                       max(per_file) AS max_pf
                ORDER BY total_chunks DESC
            """):
                print(fmt(r))

            print("\n--- relevance_to_file population + distribution ---")
            for r in await run_query(session, """
                MATCH (c:Chunk)
                WITH count(c) AS total,
                     sum(CASE WHEN c.relevance_to_file IS NULL THEN 1 ELSE 0 END) AS nulls
                RETURN total, nulls, total - nulls AS populated
            """):
                print(fmt(r))
            for r in await run_query(session, """
                MATCH (c:Chunk) WHERE c.relevance_to_file IS NOT NULL
                RETURN min(c.relevance_to_file) AS min,
                       percentileCont(c.relevance_to_file, 0.1) AS p10,
                       percentileCont(c.relevance_to_file, 0.5) AS p50,
                       percentileCont(c.relevance_to_file, 0.9) AS p90,
                       max(c.relevance_to_file) AS max,
                       avg(c.relevance_to_file) AS mean
            """):
                print(fmt(r))

            print("\n--- relevance_to_file histogram (0.1 bins) ---")
            for r in await run_query(session, """
                MATCH (c:Chunk) WHERE c.relevance_to_file IS NOT NULL
                WITH CASE
                       WHEN c.relevance_to_file >= 1.0 THEN 9
                       ELSE toInteger(c.relevance_to_file * 10)
                     END AS bin
                RETURN bin, count(*) AS n
                ORDER BY bin
            """):
                print(fmt(r))

            print("\n--- w_chunk distribution ---")
            for r in await run_query(session, """
                MATCH ()-[r:HAS_TAG]->()
                WITH r.w_chunk AS v WHERE v IS NOT NULL
                RETURN count(v) AS n, min(v) AS min,
                       percentileCont(v, 0.1) AS p10,
                       percentileCont(v, 0.5) AS p50,
                       percentileCont(v, 0.9) AS p90,
                       max(v) AS max, avg(v) AS mean
            """):
                print(fmt(r))
            for r in await run_query(session, """
                MATCH ()-[r:HAS_TAG]->()
                RETURN count(DISTINCT r.w_chunk) AS distinct_w_chunk
            """):
                print(fmt(r))

            print("\n--- w_facet distribution ---")
            for r in await run_query(session, """
                MATCH ()-[r:HAS_TAG]->()
                WITH r.w_facet AS v WHERE v IS NOT NULL
                RETURN count(v) AS n, min(v) AS min,
                       percentileCont(v, 0.1) AS p10,
                       percentileCont(v, 0.5) AS p50,
                       percentileCont(v, 0.9) AS p90,
                       max(v) AS max, avg(v) AS mean
            """):
                print(fmt(r))
            for r in await run_query(session, """
                MATCH ()-[r:HAS_TAG]->()
                RETURN count(DISTINCT r.w_facet) AS distinct_w_facet
            """):
                print(fmt(r))

            print("\n--- w_facet value histogram (most common) ---")
            for r in await run_query(session, """
                MATCH ()-[r:HAS_TAG]->()
                RETURN r.w_facet AS v, count(*) AS n
                ORDER BY n DESC
                LIMIT 30
            """):
                print(fmt(r))

            print("\n--- HAS_TAG by facet ---")
            for r in await run_query(session, """
                MATCH ()-[r:HAS_TAG]->()
                RETURN coalesce(r.facet, '(null)') AS facet, count(r) AS n
                ORDER BY n DESC
            """):
                print(fmt(r))

            print("\n--- hard-field population by section ---")
            for r in await run_query(session, """
                MATCH (c:Chunk)
                RETURN coalesce(c.section, '(null)') AS section,
                       count(c) AS chunks,
                       sum(CASE WHEN c.product IS NOT NULL THEN 1 ELSE 0 END) AS has_product,
                       sum(CASE WHEN c.channel IS NOT NULL THEN 1 ELSE 0 END) AS has_channel,
                       sum(CASE WHEN c.employee_id IS NOT NULL THEN 1 ELSE 0 END) AS has_employee_id,
                       sum(CASE WHEN c.years IS NOT NULL THEN 1 ELSE 0 END) AS has_years,
                       sum(CASE WHEN c.parent_ref IS NOT NULL THEN 1 ELSE 0 END) AS has_parent_ref,
                       sum(CASE WHEN c.chunk_ref IS NOT NULL THEN 1 ELSE 0 END) AS has_chunk_ref
                ORDER BY chunks DESC
            """):
                print(fmt(r))

            print("\n--- files: dispatch_mode ---")
            for r in await run_query(session, """
                MATCH (f:File) RETURN coalesce(f.dispatch_mode, '(null)') AS dispatch_mode, count(f) AS n ORDER BY n DESC
            """):
                print(fmt(r))

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())

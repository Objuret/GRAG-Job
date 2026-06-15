"""Create a RAG-safe HERB evaluation database from the full HERB graph.

This script never mutates the source database. It copies the existing HERB
artefact into a target database while excluding the corpus surfaces that would
leak evaluation answers or oracle-only product membership:

    answerable_questions
    unanswerable_questions
    product_profile

It preserves existing chunk descriptions, relevance scores, HAS_TAG edges, and
their weights for the allowed evidence chunks. File-level LLM descriptions are
not copied because they were built from all chunk descriptions, including the
excluded surfaces. Tag embeddings are intentionally not copied; run
`NEO4J_DATABASE=<target> python -m tagging embed-tags` after this script so
prompt-tag grounding is rebuilt from only the eval-safe contexts.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable

from neo4j import AsyncGraphDatabase


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


SCHEMA_DIR = REPO_ROOT / "schema"
ENV_PATH = REPO_ROOT / ".env"
DEFAULT_SOURCE_DB = "herb"
DEFAULT_TARGET_DB = "herb-eval"
DEFAULT_EXCLUDED_SECTIONS = (
    "answerable_questions",
    "unanswerable_questions",
    "product_profile",
)
BATCH_SIZE = 1000
_DB_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def load_env_file(path: Path) -> None:
    """Minimal .env loader for Neo4j settings; does not print values."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def quote_db(name: str) -> str:
    if not _DB_NAME_RE.match(name):
        raise SystemExit(f"unsafe database name: {name!r}")
    return f"`{name}`"


def load_cypher_statements(path: Path) -> list[str]:
    if not path.exists():
        return []
    cleaned: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("//") or not stripped:
            continue
        cleaned.append(line)
    body = "\n".join(cleaned)
    return [s.strip() for s in body.split(";") if s.strip()]


def schema_statements() -> list[str]:
    return (
        load_cypher_statements(SCHEMA_DIR / "constraints.cypher")
        + load_cypher_statements(SCHEMA_DIR / "indexes.cypher")
        + load_cypher_statements(SCHEMA_DIR / "vector_indexes.cypher")
    )


async def scalar(session, query: str, **params: Any) -> Any:
    result = await session.run(query, **params)
    record = await result.single()
    return record[0] if record else None


async def ensure_database(driver, target_db: str, replace: bool) -> None:
    qtarget = quote_db(target_db)
    async with driver.session(database="system") as session:
        if replace:
            await session.run(f"DROP DATABASE {qtarget} IF EXISTS WAIT")
            await session.run(f"CREATE DATABASE {qtarget} WAIT")
        else:
            await session.run(f"CREATE DATABASE {qtarget} IF NOT EXISTS WAIT")


async def ensure_empty_target(driver, target_db: str) -> None:
    async with driver.session(database=target_db) as session:
        n = await scalar(session, "MATCH (n) RETURN count(n)")
    if n:
        raise SystemExit(
            f"target database {target_db!r} is not empty ({n} nodes). "
            "Use --replace only if you intentionally want to drop and recreate it."
        )


async def apply_schema(driver, target_db: str) -> None:
    async with driver.session(database=target_db) as session:
        for stmt in schema_statements():
            await session.run(stmt)


async def fetch_page(session, query: str, *, skip: int, limit: int, **params: Any) -> list[dict[str, Any]]:
    result = await session.run(query, skip=skip, limit=limit, **params)
    return [dict(record) async for record in result]


async def copy_node_label(
    driver,
    *,
    source_db: str,
    target_db: str,
    label: str,
    source_query: str,
    source_params: dict[str, Any] | None = None,
) -> int:
    total = 0
    source_params = source_params or {}
    write = f"UNWIND $rows AS row CREATE (n:{label}) SET n += row.props"
    async with driver.session(database=source_db) as src, driver.session(database=target_db) as dst:
        skip = 0
        while True:
            rows = await fetch_page(src, source_query, skip=skip, limit=BATCH_SIZE, **source_params)
            if not rows:
                break
            await dst.run(write, rows=rows)
            total += len(rows)
            skip += len(rows)
    print(f"copied {total:6d} :{label} nodes")
    return total


async def copy_relationships(
    driver,
    *,
    source_db: str,
    target_db: str,
    rel_type: str,
    source_query: str,
    write_query: str,
    source_params: dict[str, Any] | None = None,
) -> int:
    total = 0
    source_params = source_params or {}
    async with driver.session(database=source_db) as src, driver.session(database=target_db) as dst:
        skip = 0
        while True:
            rows = await fetch_page(src, source_query, skip=skip, limit=BATCH_SIZE, **source_params)
            if not rows:
                break
            await dst.run(write_query, rows=rows)
            total += len(rows)
            skip += len(rows)
    print(f"copied {total:6d} :{rel_type} relationships")
    return total


async def source_sanity(driver, source_db: str, excluded_sections: Iterable[str]) -> dict[str, int]:
    async with driver.session(database=source_db) as session:
        total_chunks = await scalar(session, "MATCH (c:Chunk) RETURN count(c)")
        excluded_chunks = await scalar(
            session,
            "MATCH (c:Chunk) WHERE c.section IN $excluded RETURN count(c)",
            excluded=list(excluded_sections),
        )
        safe_chunks = await scalar(
            session,
            "MATCH (c:Chunk) WHERE NOT (coalesce(c.section, '') IN $excluded) RETURN count(c)",
            excluded=list(excluded_sections),
        )
        total_edges = await scalar(session, "MATCH (:Chunk)-[r:HAS_TAG]->(:Tag) RETURN count(r)")
        safe_edges = await scalar(
            session,
            """
            MATCH (c:Chunk)-[r:HAS_TAG]->(:Tag)
            WHERE NOT (coalesce(c.section, '') IN $excluded)
            RETURN count(r)
            """,
            excluded=list(excluded_sections),
        )
    return {
        "total_chunks": int(total_chunks or 0),
        "excluded_chunks": int(excluded_chunks or 0),
        "safe_chunks": int(safe_chunks or 0),
        "total_has_tag": int(total_edges or 0),
        "safe_has_tag": int(safe_edges or 0),
    }


async def validate_target(driver, target_db: str, excluded_sections: Iterable[str]) -> dict[str, int]:
    async with driver.session(database=target_db) as session:
        chunks = await scalar(session, "MATCH (c:Chunk) RETURN count(c)")
        excluded_chunks = await scalar(
            session,
            "MATCH (c:Chunk) WHERE c.section IN $excluded RETURN count(c)",
            excluded=list(excluded_sections),
        )
        has_tag = await scalar(session, "MATCH (:Chunk)-[r:HAS_TAG]->(:Tag) RETURN count(r)")
        orphan_tags = await scalar(
            session,
            "MATCH (t:Tag) WHERE NOT EXISTS { MATCH (:Chunk)-[:HAS_TAG]->(t) } RETURN count(t)",
        )
        embedded_tags = await scalar(
            session,
            """
            MATCH (t:Tag)
            WHERE t.emb_all IS NOT NULL OR t.emb_topic IS NOT NULL
               OR t.emb_entities IS NOT NULL OR t.emb_activity IS NOT NULL
               OR t.emb_temporal IS NOT NULL OR t.emb_evidence IS NOT NULL
            RETURN count(t)
            """,
        )
        file_descriptions = await scalar(
            session,
            "MATCH (f:File) WHERE f.description IS NOT NULL RETURN count(f)",
        )
    return {
        "chunks": int(chunks or 0),
        "excluded_chunks": int(excluded_chunks or 0),
        "has_tag": int(has_tag or 0),
        "orphan_tags": int(orphan_tags or 0),
        "embedded_tags": int(embedded_tags or 0),
        "file_descriptions": int(file_descriptions or 0),
    }


async def create_eval_db(args: argparse.Namespace) -> None:
    load_env_file(ENV_PATH)
    neo4j_uri = os.environ.get("NEO4J_URI", "neo4j://localhost:7687")
    neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
    neo4j_password = os.environ.get("NEO4J_PASSWORD", "")
    if not neo4j_password:
        raise SystemExit("NEO4J_PASSWORD is not set in environment or backend/.env")
    driver = AsyncGraphDatabase.driver(
        neo4j_uri,
        auth=(neo4j_user, neo4j_password),
    )
    excluded = tuple(args.exclude_section)
    try:
        if args.source_db == args.target_db:
            raise SystemExit("source and target databases must be different")

        source_counts = await source_sanity(driver, args.source_db, excluded)
        print(
            "source "
            f"{args.source_db}: chunks={source_counts['total_chunks']} "
            f"excluded={source_counts['excluded_chunks']} "
            f"safe={source_counts['safe_chunks']} "
            f"safe_HAS_TAG={source_counts['safe_has_tag']}"
        )
        if args.dry_run:
            print("dry-run: no target database was created or modified")
            return

        await ensure_database(driver, args.target_db, args.replace)
        if not args.replace:
            await ensure_empty_target(driver, args.target_db)
        await apply_schema(driver, args.target_db)

        await copy_node_label(
            driver,
            source_db=args.source_db,
            target_db=args.target_db,
            label="Source",
            source_query="""
            MATCH (n:Source)
            RETURN properties(n) AS props
            ORDER BY n.source_id SKIP $skip LIMIT $limit
            """,
        )
        await copy_node_label(
            driver,
            source_db=args.source_db,
            target_db=args.target_db,
            label="File",
            source_query="""
            MATCH (n:File)
            RETURN n {
              .file_id, .dataset_id, .format_family, .created_at, .sha256,
              .rel_path, .file_path, .size_bytes, .dispatch_mode
            } AS props
            ORDER BY n.file_id SKIP $skip LIMIT $limit
            """,
        )
        await copy_node_label(
            driver,
            source_db=args.source_db,
            target_db=args.target_db,
            label="Run",
            source_query="""
            MATCH (n:Run)
            RETURN properties(n) AS props
            ORDER BY n.run_id SKIP $skip LIMIT $limit
            """,
        )
        await copy_node_label(
            driver,
            source_db=args.source_db,
            target_db=args.target_db,
            label="Chunk",
            source_query="""
            MATCH (n:Chunk)
            WHERE NOT (coalesce(n.section, '') IN $excluded)
            RETURN properties(n) AS props
            ORDER BY n.chunk_id SKIP $skip LIMIT $limit
            """,
            source_params={"excluded": list(excluded)},
        )
        await copy_node_label(
            driver,
            source_db=args.source_db,
            target_db=args.target_db,
            label="Tag",
            source_query="""
            MATCH (c:Chunk)-[:HAS_TAG]->(n:Tag)
            WHERE NOT (coalesce(c.section, '') IN $excluded)
            WITH DISTINCT n
            RETURN n { .name } AS props
            ORDER BY n.name SKIP $skip LIMIT $limit
            """,
            source_params={"excluded": list(excluded)},
        )

        await copy_relationships(
            driver,
            source_db=args.source_db,
            target_db=args.target_db,
            rel_type="CONTAINS",
            source_query="""
            MATCH (a:Source)-[r:CONTAINS]->(b:File)
            RETURN a.source_id AS start_id, b.file_id AS end_id, properties(r) AS props
            ORDER BY start_id, end_id SKIP $skip LIMIT $limit
            """,
            write_query="""
            UNWIND $rows AS row
            MATCH (a:Source {source_id: row.start_id})
            MATCH (b:File {file_id: row.end_id})
            CREATE (a)-[r:CONTAINS]->(b)
            SET r += row.props
            """,
        )
        await copy_relationships(
            driver,
            source_db=args.source_db,
            target_db=args.target_db,
            rel_type="HAS_CHUNK",
            source_query="""
            MATCH (a:File)-[r:HAS_CHUNK]->(b:Chunk)
            WHERE NOT (coalesce(b.section, '') IN $excluded)
            RETURN a.file_id AS start_id, b.chunk_id AS end_id, properties(r) AS props
            ORDER BY start_id, end_id SKIP $skip LIMIT $limit
            """,
            write_query="""
            UNWIND $rows AS row
            MATCH (a:File {file_id: row.start_id})
            MATCH (b:Chunk {chunk_id: row.end_id})
            CREATE (a)-[r:HAS_CHUNK]->(b)
            SET r += row.props
            """,
            source_params={"excluded": list(excluded)},
        )
        await copy_relationships(
            driver,
            source_db=args.source_db,
            target_db=args.target_db,
            rel_type="HAS_TAG",
            source_query="""
            MATCH (a:Chunk)-[r:HAS_TAG]->(b:Tag)
            WHERE NOT (coalesce(a.section, '') IN $excluded)
            RETURN a.chunk_id AS start_id, b.name AS end_id, properties(r) AS props
            ORDER BY a.chunk_id, b.name, r.facet, r.run_id SKIP $skip LIMIT $limit
            """,
            write_query="""
            UNWIND $rows AS row
            MATCH (a:Chunk {chunk_id: row.start_id})
            MATCH (b:Tag {name: row.end_id})
            CREATE (a)-[r:HAS_TAG]->(b)
            SET r += row.props
            """,
            source_params={"excluded": list(excluded)},
        )

        target_counts = await validate_target(driver, args.target_db, excluded)
        print(
            "target "
            f"{args.target_db}: chunks={target_counts['chunks']} "
            f"excluded={target_counts['excluded_chunks']} "
            f"HAS_TAG={target_counts['has_tag']} "
            f"orphan_tags={target_counts['orphan_tags']} "
            f"embedded_tags={target_counts['embedded_tags']} "
            f"file_descriptions={target_counts['file_descriptions']}"
        )

        if target_counts["excluded_chunks"] != 0:
            raise SystemExit("target validation failed: excluded chunks are present")
        if target_counts["orphan_tags"] != 0:
            raise SystemExit("target validation failed: orphan tags are present")
        if target_counts["embedded_tags"] != 0:
            raise SystemExit("target validation failed: copied tag grounding vectors unexpectedly")
        if target_counts["file_descriptions"] != 0:
            raise SystemExit("target validation failed: copied file descriptions unexpectedly")

        print(
            "\nNext: regenerate safe tag embeddings with:\n"
            f"  set NEO4J_DATABASE={args.target_db} && python -m tagging embed-tags\n"
            "PowerShell:\n"
            f"  $env:NEO4J_DATABASE='{args.target_db}'; python -m tagging embed-tags\n"
        )
    finally:
        await driver.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", default=DEFAULT_SOURCE_DB)
    parser.add_argument("--target-db", default=DEFAULT_TARGET_DB)
    parser.add_argument(
        "--exclude-section",
        action="append",
        default=list(DEFAULT_EXCLUDED_SECTIONS),
        help="Chunk section to exclude from the eval graph. Defaults to the HERB RAG-safety exclusions.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Drop and recreate the target database first. Never affects --source-db.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report source safe/excluded counts; do not create or modify the target database.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    asyncio.run(create_eval_db(parse_args(argv)))


if __name__ == "__main__":
    main()

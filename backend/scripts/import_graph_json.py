"""Import a JSONL graph export into Neo4j."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from contextlib import contextmanager
from io import TextIOWrapper
from pathlib import Path
from typing import Any, Iterator, TextIO
from zipfile import ZipFile

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from shared.config import Settings
from shared.neo4j_client import Neo4jClient
from shared.utils import make_json_safe


DEFAULT_INPUT = BACKEND_ROOT.parent / "graph_export" / "grag_graph_latest.zip"
EXPORT_LABEL = "__GraphExportNode"
DEFAULT_BATCH_SIZE = 1000


def _escape_identifier(value: str) -> str:
    return "`" + value.replace("`", "``") + "`"


def _member_name(zip_file: ZipFile, filename: str) -> str:
    matches = [name for name in zip_file.namelist() if Path(name).name == filename]
    if not matches:
        raise FileNotFoundError(f"{filename} not found in export zip")
    return matches[0]


@contextmanager
def _open_export_file(input_path: Path, filename: str) -> Iterator[TextIO]:
    if input_path.is_dir():
        with (input_path / filename).open("r", encoding="utf-8") as handle:
            yield handle
        return

    with ZipFile(input_path) as zip_file:
        member = _member_name(zip_file, filename)
        with zip_file.open(member) as raw_handle:
            with TextIOWrapper(raw_handle, encoding="utf-8") as text_handle:
                yield text_handle


def _iter_jsonl(input_path: Path, filename: str) -> Iterator[dict[str, Any]]:
    with _open_export_file(input_path, filename) as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                yield json.loads(stripped)


def _read_manifest(input_path: Path) -> dict[str, Any]:
    with _open_export_file(input_path, "manifest.json") as handle:
        return json.load(handle)


async def _run(session: Any, query: str, **params: Any) -> None:
    result = await session.run(query, **params)
    await result.consume()


async def _single_int(session: Any, query: str) -> int:
    result = await session.run(query)
    record = await result.single()
    return int(record[0]) if record else 0


async def _prepare_database(session: Any, wipe: bool) -> None:
    node_count = await _single_int(session, "MATCH (n) RETURN count(n)")
    if node_count and not wipe:
        raise RuntimeError("Neo4j is not empty. Re-run with --wipe to replace it.")

    if wipe:
        await _run(session, "MATCH (n) DETACH DELETE n")

    await _run(
        session,
        f"CREATE INDEX graph_export_node_id IF NOT EXISTS "
        f"FOR (n:{_escape_identifier(EXPORT_LABEL)}) ON (n.__export_element_id)",
    )
    await _run(session, "CALL db.awaitIndexes()")


async def _flush_nodes(session: Any, labels: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    if not rows:
        return

    label_clause = "".join(f":{_escape_identifier(label)}" for label in (*labels, EXPORT_LABEL))
    await _run(
        session,
        f"""
        UNWIND $rows AS row
        CREATE (n{label_clause})
        SET n = row.properties
        SET n.__export_element_id = row.element_id
        """,
        rows=rows,
    )
    rows.clear()


async def _flush_relationships(session: Any, rel_type: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return

    export_label = _escape_identifier(EXPORT_LABEL)
    await _run(
        session,
        f"""
        UNWIND $rows AS row
        MATCH (source:{export_label} {{__export_element_id: row.source_element_id}})
        MATCH (target:{export_label} {{__export_element_id: row.target_element_id}})
        CREATE (source)-[r:{_escape_identifier(rel_type)}]->(target)
        SET r = row.properties
        SET r.__export_element_id = row.element_id
        """,
        rows=rows,
    )
    rows.clear()


async def _import_nodes(session: Any, input_path: Path, batch_size: int) -> int:
    pending: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    count = 0

    for row in _iter_jsonl(input_path, "nodes.jsonl"):
        labels = tuple(row.get("labels", []))
        pending[labels].append(
            {
                "element_id": row["element_id"],
                "properties": make_json_safe(row.get("properties", {})),
            }
        )
        count += 1

        if len(pending[labels]) >= batch_size:
            await _flush_nodes(session, labels, pending[labels])

    for labels, rows in pending.items():
        await _flush_nodes(session, labels, rows)

    return count


async def _import_relationships(session: Any, input_path: Path, batch_size: int) -> int:
    pending: dict[str, list[dict[str, Any]]] = defaultdict(list)
    count = 0

    for row in _iter_jsonl(input_path, "relationships.jsonl"):
        rel_type = row["type"]
        pending[rel_type].append(
            {
                "element_id": row["element_id"],
                "source_element_id": row["source_element_id"],
                "target_element_id": row["target_element_id"],
                "properties": make_json_safe(row.get("properties", {})),
            }
        )
        count += 1

        if len(pending[rel_type]) >= batch_size:
            await _flush_relationships(session, rel_type, pending[rel_type])

    for rel_type, rows in pending.items():
        await _flush_relationships(session, rel_type, rows)

    return count


async def _strip_export_metadata(session: Any) -> None:
    export_label = _escape_identifier(EXPORT_LABEL)
    await _run(session, f"MATCH (n:{export_label}) REMOVE n:{export_label} REMOVE n.__export_element_id")
    await _run(session, "MATCH ()-[r]->() REMOVE r.__export_element_id")


async def import_graph(input_path: Path, wipe: bool, keep_export_metadata: bool, batch_size: int) -> None:
    manifest = _read_manifest(input_path)
    if manifest.get("format") != "grag.graph_export.v1":
        raise RuntimeError(f"Unsupported graph export format: {manifest.get('format')}")

    settings = Settings()
    client = Neo4jClient(settings)
    try:
        async with client.session() as session:
            await _prepare_database(session, wipe=wipe)
            node_count = await _import_nodes(session, input_path, batch_size=batch_size)
            relationship_count = await _import_relationships(session, input_path, batch_size=batch_size)
            if not keep_export_metadata:
                await _strip_export_metadata(session)
    finally:
        await client.close()

    print(f"Imported {node_count} nodes and {relationship_count} relationships from {input_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a graph JSONL export into Neo4j.")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Export directory or zip file. Default: {DEFAULT_INPUT}",
    )
    parser.add_argument("--wipe", action="store_true", help="Delete the current Neo4j graph before importing.")
    parser.add_argument(
        "--keep-export-metadata",
        action="store_true",
        help="Keep temporary export labels and element-id properties after import.",
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    args = parser.parse_args()

    asyncio.run(
        import_graph(
            input_path=args.input,
            wipe=args.wipe,
            keep_export_metadata=args.keep_export_metadata,
            batch_size=args.batch_size,
        )
    )


if __name__ == "__main__":
    main()

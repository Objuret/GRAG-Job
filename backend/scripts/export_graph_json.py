"""Export the current Neo4j graph to portable JSONL files."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from shared.config import REPO_ROOT, Settings
from shared.neo4j_client import Neo4jClient
from shared.utils import ensure_dir, make_json_safe


DEFAULT_OUTPUT_DIR = REPO_ROOT.parent / "graph_export" / "latest"


def _json_default(value: Any) -> str:
    return str(value)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            safe_row = make_json_safe(row)
            handle.write(json.dumps(safe_row, ensure_ascii=False, default=_json_default))
            handle.write("\n")


async def _fetch_rows(client: Neo4jClient) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    async with client.session() as session:
        node_result = await session.run(
            """
            MATCH (n)
            RETURN elementId(n) AS element_id,
                   labels(n) AS labels,
                   properties(n) AS properties
            ORDER BY elementId(n)
            """
        )
        nodes = [dict(record) async for record in node_result]

        rel_result = await session.run(
            """
            MATCH (source)-[r]->(target)
            RETURN elementId(r) AS element_id,
                   type(r) AS type,
                   elementId(source) AS source_element_id,
                   elementId(target) AS target_element_id,
                   properties(r) AS properties
            ORDER BY elementId(r)
            """
        )
        relationships = [dict(record) async for record in rel_result]

    return nodes, relationships


def _manifest(nodes: list[dict[str, Any]], relationships: list[dict[str, Any]]) -> dict[str, Any]:
    label_counts: dict[str, int] = {}
    for node in nodes:
        for label in node["labels"]:
            label_counts[label] = label_counts.get(label, 0) + 1

    relationship_type_counts: dict[str, int] = {}
    for relationship in relationships:
        rel_type = relationship["type"]
        relationship_type_counts[rel_type] = relationship_type_counts.get(rel_type, 0) + 1

    return {
        "format": "grag.graph_export.v1",
        "exported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "node_count": len(nodes),
        "relationship_count": len(relationships),
        "label_counts": dict(sorted(label_counts.items())),
        "relationship_type_counts": dict(sorted(relationship_type_counts.items())),
        "files": {
            "nodes": "nodes.jsonl",
            "relationships": "relationships.jsonl",
        },
    }


async def export_graph(output_dir: Path) -> None:
    settings = Settings()
    client = Neo4jClient(settings)
    try:
        nodes, relationships = await _fetch_rows(client)
    finally:
        await client.close()

    ensure_dir(output_dir)
    _write_jsonl(output_dir / "nodes.jsonl", nodes)
    _write_jsonl(output_dir / "relationships.jsonl", relationships)

    manifest = _manifest(nodes, relationships)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=_json_default) + "\n",
        encoding="utf-8",
    )

    print(
        f"Exported {manifest['node_count']} nodes and "
        f"{manifest['relationship_count']} relationships to {output_dir}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Neo4j graph to JSONL.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory. Default: {DEFAULT_OUTPUT_DIR}",
    )
    args = parser.parse_args()
    asyncio.run(export_graph(args.output_dir))


if __name__ == "__main__":
    main()

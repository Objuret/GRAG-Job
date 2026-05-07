"""Bootstrap the Neo4j schema and seed canonical tags.

Idempotent. Run once per fresh Neo4j install, or any time the schema files or
canonical_seed.yaml change. Existing data is untouched.

    python scripts/bootstrap_schema.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from shared.config import Settings
from shared.neo4j_client import Neo4jClient


SCHEMA_DIR = REPO_ROOT / "schema"
SEED_PATH = REPO_ROOT / "clustering" / "canonical_seed.yaml"


def _load_cypher_statements(path: Path) -> list[str]:
    """Strip line comments and split by ';'."""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    cleaned = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("//") or not stripped:
            continue
        cleaned.append(line)
    body = "\n".join(cleaned)
    return [s.strip() for s in body.split(";") if s.strip()]


async def apply_schema(client: Neo4jClient) -> int:
    statements = (
        _load_cypher_statements(SCHEMA_DIR / "constraints.cypher")
        + _load_cypher_statements(SCHEMA_DIR / "indexes.cypher")
        + _load_cypher_statements(SCHEMA_DIR / "vector_indexes.cypher")
    )
    async with client.session() as s:
        for stmt in statements:
            await s.run(stmt)
    return len(statements)


async def seed_canonical_tags(client: Neo4jClient) -> int:
    if not SEED_PATH.exists():
        return 0
    raw = yaml.safe_load(SEED_PATH.read_text(encoding="utf-8")) or {}
    items: list[dict] = []
    for cluster, tags in raw.items():
        for tag in tags or []:
            if isinstance(tag, str):
                items.append({"label": tag, "cluster": cluster, "gloss": ""})
            elif isinstance(tag, dict):
                label = tag.get("label") or tag.get("name")
                if not label:
                    continue
                items.append({
                    "label": label,
                    "cluster": cluster,
                    "gloss": tag.get("gloss", ""),
                })
    if not items:
        return 0

    async with client.session() as s:
        await s.run(
            """
            UNWIND $items AS item
            MERGE (c:CanonicalTag {label: item.label, cluster: item.cluster})
            ON CREATE SET c.gloss = item.gloss, c.source = 'seed'
            ON MATCH SET c.gloss = item.gloss
            """,
            items=items,
        )
    return len(items)


async def main() -> None:
    settings = Settings()
    client = Neo4jClient(settings)
    try:
        n_schema = await apply_schema(client)
        n_tags = await seed_canonical_tags(client)
        print(f"Applied {n_schema} schema statements; merged {n_tags} canonical tags.")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())

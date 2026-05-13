"""Bootstrap the Neo4j schema.

Idempotent. Run once per fresh Neo4j install, or any time the schema files or
indexes change. Existing data is untouched.

    python scripts/bootstrap_schema.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from shared.config import Settings
from shared.neo4j_client import Neo4jClient


SCHEMA_DIR = REPO_ROOT / "schema"


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


async def main() -> None:
    settings = Settings()
    client = Neo4jClient(settings)
    try:
        n_schema = await apply_schema(client)
        print(f"Applied {n_schema} schema statements.")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())

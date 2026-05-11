"""Rename retired cluster strings in the configured Neo4j database.

This is a data migration for the 2026-05-11 dimension rename:

    theme            -> topic
    object_entity    -> entities
    event_process    -> activity
    time_relevance   -> temporal
    information_need -> evidence

It updates edge properties, canonical-tag node keys, and proposal nodes. Proposal
IDs include the cluster string in their hash input, so those IDs are rewritten
too. The migration is idempotent.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from shared.config import Settings  # noqa: E402
from shared.neo4j_client import Neo4jClient  # noqa: E402
from shared.utils import stable_short_hash  # noqa: E402


CLUSTER_RENAMES: dict[str, str] = {
    "theme": "topic",
    "object_entity": "entities",
    "event_process": "activity",
    "time_relevance": "temporal",
    "information_need": "evidence",
}


async def count_retired(client: Neo4jClient) -> list[dict[str, Any]]:
    old = list(CLUSTER_RENAMES)
    queries = [
        (
            "HAS_TAG",
            "MATCH ()-[r:HAS_TAG]->() WHERE r.cluster IN $old "
            "RETURN r.cluster AS cluster, count(r) AS n",
        ),
        (
            "TAGGED",
            "MATCH ()-[r:TAGGED]->() WHERE r.cluster IN $old "
            "RETURN r.cluster AS cluster, count(r) AS n",
        ),
        (
            "CanonicalTag",
            "MATCH (n:CanonicalTag) WHERE n.cluster IN $old "
            "RETURN n.cluster AS cluster, count(n) AS n",
        ),
        (
            "CanonicalTagProposal",
            "MATCH (n:CanonicalTagProposal) WHERE n.cluster IN $old "
            "RETURN n.cluster AS cluster, count(n) AS n",
        ),
    ]
    rows: list[dict[str, Any]] = []
    async with client.session() as session:
        for place, query in queries:
            result = await session.run(query, old=old)
            async for record in result:
                rows.append({"place": place, "cluster": record["cluster"], "n": record["n"]})
    return sorted(rows, key=lambda row: (row["place"], row["cluster"]))


async def update_relationship_clusters(client: Neo4jClient) -> dict[str, int]:
    mapping = [{"old": old, "new": new} for old, new in CLUSTER_RENAMES.items()]
    counts: dict[str, int] = {}
    async with client.session() as session:
        for rel_type in ("HAS_TAG", "TAGGED"):
            result = await session.run(
                f"""
                UNWIND $mapping AS item
                MATCH ()-[r:{rel_type}]->()
                WHERE r.cluster = item.old
                SET r.cluster = item.new
                RETURN count(r) AS n
                """,
                mapping=mapping,
            )
            record = await result.single()
            counts[rel_type] = int(record["n"] if record else 0)
    return counts


async def migrate_canonical_tags(client: Neo4jClient) -> int:
    old = list(CLUSTER_RENAMES)
    async with client.session() as session:
        result = await session.run(
            """
            MATCH (c:CanonicalTag)
            WHERE c.cluster IN $old
            RETURN elementId(c) AS element_id,
                   c.label AS label,
                   c.cluster AS cluster,
                   c.gloss AS gloss,
                   c.source AS source
            ORDER BY c.cluster, c.label
            """,
            old=old,
        )
        rows = [dict(record) async for record in result]

        for row in rows:
            new_cluster = CLUSTER_RENAMES[row["cluster"]]
            existing = await session.run(
                """
                MATCH (dst:CanonicalTag {label: $label, cluster: $new_cluster})
                RETURN elementId(dst) AS element_id
                """,
                label=row["label"],
                new_cluster=new_cluster,
            )
            dst = await existing.single()
            if dst is None:
                await session.run(
                    """
                    MATCH (old:CanonicalTag)
                    WHERE elementId(old) = $element_id
                    SET old.cluster = $new_cluster
                    """,
                    element_id=row["element_id"],
                    new_cluster=new_cluster,
                )
            else:
                await session.run(
                    """
                    MATCH (old:CanonicalTag)
                    WHERE elementId(old) = $old_element_id
                    MATCH (dst:CanonicalTag)
                    WHERE elementId(dst) = $dst_element_id
                    SET dst.gloss = CASE
                          WHEN coalesce(dst.gloss, '') = '' THEN coalesce(old.gloss, '')
                          ELSE dst.gloss
                        END,
                        dst.source = coalesce(dst.source, old.source)
                    DETACH DELETE old
                    """,
                    old_element_id=row["element_id"],
                    dst_element_id=dst["element_id"],
                )
    return len(rows)


async def migrate_proposals(client: Neo4jClient) -> int:
    old = list(CLUSTER_RENAMES)
    async with client.session() as session:
        result = await session.run(
            """
            MATCH (p:CanonicalTagProposal)
            WHERE p.cluster IN $old
            RETURN elementId(p) AS element_id,
                   p.label AS label,
                   p.cluster AS cluster,
                   p.gloss AS gloss,
                   p.rationale AS rationale,
                   p.observed_count AS observed_count,
                   p.first_seen AS first_seen,
                   p.last_seen AS last_seen,
                   p.run_id AS run_id
            ORDER BY p.cluster, p.label
            """,
            old=old,
        )
        rows = [dict(record) async for record in result]

        for row in rows:
            new_cluster = CLUSTER_RENAMES[row["cluster"]]
            new_proposal_id = stable_short_hash(f"{new_cluster}:{row['label']}", 24)
            existing = await session.run(
                """
                MATCH (dst:CanonicalTagProposal {proposal_id: $proposal_id})
                RETURN elementId(dst) AS element_id
                """,
                proposal_id=new_proposal_id,
            )
            dst = await existing.single()
            if dst is None:
                await session.run(
                    """
                    MATCH (p:CanonicalTagProposal)
                    WHERE elementId(p) = $element_id
                    SET p.cluster = $new_cluster,
                        p.proposal_id = $new_proposal_id
                    """,
                    element_id=row["element_id"],
                    new_cluster=new_cluster,
                    new_proposal_id=new_proposal_id,
                )
            else:
                await session.run(
                    """
                    MATCH (old:CanonicalTagProposal)
                    WHERE elementId(old) = $old_element_id
                    MATCH (dst:CanonicalTagProposal)
                    WHERE elementId(dst) = $dst_element_id
                    OPTIONAL MATCH (old)-[:OBSERVED_IN]->(chunk:Chunk)
                    MERGE (dst)-[:OBSERVED_IN]->(chunk)
                    WITH old, dst
                    SET dst.cluster = $new_cluster,
                        dst.label = coalesce(dst.label, old.label),
                        dst.gloss = CASE
                          WHEN coalesce(dst.gloss, '') = '' THEN old.gloss
                          ELSE dst.gloss
                        END,
                        dst.rationale = CASE
                          WHEN dst.rationale IS NULL THEN old.rationale
                          ELSE dst.rationale
                        END,
                        dst.observed_count = coalesce(dst.observed_count, 0)
                          + coalesce(old.observed_count, 0),
                        dst.first_seen = CASE
                          WHEN dst.first_seen IS NULL THEN old.first_seen
                          WHEN old.first_seen IS NULL THEN dst.first_seen
                          WHEN old.first_seen < dst.first_seen THEN old.first_seen
                          ELSE dst.first_seen
                        END,
                        dst.last_seen = CASE
                          WHEN dst.last_seen IS NULL THEN old.last_seen
                          WHEN old.last_seen IS NULL THEN dst.last_seen
                          WHEN old.last_seen > dst.last_seen THEN old.last_seen
                          ELSE dst.last_seen
                        END,
                        dst.run_id = coalesce(dst.run_id, old.run_id)
                    DETACH DELETE old
                    """,
                    old_element_id=row["element_id"],
                    dst_element_id=dst["element_id"],
                    new_cluster=new_cluster,
                )
    return len(rows)


def print_counts(title: str, rows: list[dict[str, Any]]) -> None:
    print(title)
    if not rows:
        print("  none")
        return
    for row in rows:
        print(f"  {row['place']}: {row['cluster']} = {row['n']}")


async def main() -> None:
    settings = Settings()
    client = Neo4jClient(settings)
    try:
        before = await count_retired(client)
        print_counts("Retired cluster strings before migration:", before)

        rel_counts = await update_relationship_clusters(client)
        canonical_count = await migrate_canonical_tags(client)
        proposal_count = await migrate_proposals(client)

        after = await count_retired(client)
        print("")
        print("Migrated:")
        print(f"  HAS_TAG relationships: {rel_counts['HAS_TAG']}")
        print(f"  TAGGED relationships: {rel_counts['TAGGED']}")
        print(f"  CanonicalTag nodes: {canonical_count}")
        print(f"  CanonicalTagProposal nodes: {proposal_count}")
        print("")
        print_counts("Retired cluster strings after migration:", after)

        if after:
            raise SystemExit("Migration left retired cluster strings behind.")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())

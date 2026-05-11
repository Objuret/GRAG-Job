"""Interactive triage for :CanonicalTagProposal nodes.

    python -m clustering.review

Reviews proposals in observed_count DESC order (most commonly emitted first).
For each proposal the tool shows: label, cluster, gloss, rationale, how many
chunks triggered it, the existing canonical vocab for that cluster (so you can
judge whether it is already covered), and up to 3 chunk content previews.

Actions
-------
  a  Accept  → MERGE (:CanonicalTag) in Neo4j + append to canonical_seed.yaml
               + DETACH DELETE the proposal node.
  r  Reject  → DETACH DELETE the proposal node. The raw tag name stays in the
               graph on any HAS_TAG edges already written; only the proposal
               node is removed.
  s  Skip    → leave the proposal untouched; revisit next run.
  q  Quit    → stop immediately, leaving remaining proposals unchanged.

After the session a summary of accepted / rejected / skipped counts is printed.

Invoke bootstrap_schema.py after an accept session to seed the new canonicals
into the live database (the tool does a targeted MERGE, but bootstrap is the
canonical way to resync the full vocab from the yaml file).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import yaml

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from shared.config import Settings
from shared.neo4j_client import Neo4jClient

_SEED_PATH = Path(__file__).resolve().parent / "canonical_seed.yaml"

# Header written back to canonical_seed.yaml after every accept.
_SEED_HEADER = """\
# Canonical tag vocabulary, organised by retrieval dimension.
#
# Source of truth for the clustering layer. Hybrid seed-and-grow:
# proposals from the indexing run land in (:CanonicalTagProposal) and only
# enter this file via `python -m clustering.review`.
#
# DISCUSS: per-label glosses + synonym lists (currently bare labels only).

"""


# ---------------------------------------------------------------------------
# Neo4j helpers
# ---------------------------------------------------------------------------


async def _fetch_proposals(client: Neo4jClient) -> list[dict[str, Any]]:
    async with client.session() as session:
        result = await session.run(
            """
            MATCH (p:CanonicalTagProposal)
            RETURN p.proposal_id   AS proposal_id,
                   p.label         AS label,
                   p.cluster       AS cluster,
                   p.gloss         AS gloss,
                   p.rationale     AS rationale,
                   p.observed_count AS observed_count,
                   p.first_seen    AS first_seen,
                   p.last_seen     AS last_seen
            ORDER BY p.observed_count DESC, p.cluster, p.label
            """
        )
        return [dict(r) async for r in result]


async def _fetch_example_chunks(
    client: Neo4jClient, proposal_id: str, n: int = 3
) -> list[dict[str, Any]]:
    async with client.session() as session:
        result = await session.run(
            """
            MATCH (p:CanonicalTagProposal {proposal_id: $pid})-[:OBSERVED_IN]->(c:Chunk)
            RETURN c.chunk_id AS chunk_id, c.kind AS kind, c.content AS content
            LIMIT $n
            """,
            pid=proposal_id,
            n=n,
        )
        return [dict(r) async for r in result]


async def _fetch_existing_canonicals(
    client: Neo4jClient, cluster: str
) -> list[str]:
    async with client.session() as session:
        result = await session.run(
            """
            MATCH (ct:CanonicalTag {cluster: $cluster})
            RETURN ct.label AS label
            ORDER BY ct.label
            """,
            cluster=cluster,
        )
        return [r["label"] async for r in result]


async def _promote(client: Neo4jClient, proposal: dict[str, Any]) -> None:
    """Create (:CanonicalTag) and delete the proposal in one session."""
    async with client.session() as session:
        await session.run(
            """
            MERGE (ct:CanonicalTag {label: $label, cluster: $cluster})
            ON CREATE SET ct.gloss = $gloss, ct.source = 'triage'
            ON MATCH  SET ct.gloss = $gloss
            """,
            label=proposal["label"],
            cluster=proposal["cluster"],
            gloss=proposal["gloss"] or "",
        )
        await session.run(
            """
            MATCH (p:CanonicalTagProposal {proposal_id: $pid})
            DETACH DELETE p
            """,
            pid=proposal["proposal_id"],
        )


async def _reject(client: Neo4jClient, proposal_id: str) -> None:
    async with client.session() as session:
        await session.run(
            """
            MATCH (p:CanonicalTagProposal {proposal_id: $pid})
            DETACH DELETE p
            """,
            pid=proposal_id,
        )


# ---------------------------------------------------------------------------
# Seed-file update
# ---------------------------------------------------------------------------


def _update_seed(label: str, cluster: str) -> None:
    raw: dict[str, list[str]] = yaml.safe_load(_SEED_PATH.read_text(encoding="utf-8")) or {}
    tags = raw.setdefault(cluster, [])
    if label not in tags:
        tags.append(label)
        tags.sort()
    body = yaml.dump(raw, allow_unicode=True, sort_keys=True, default_flow_style=False)
    _SEED_PATH.write_text(_SEED_HEADER + body, encoding="utf-8")


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

_SEP = "─" * 60


def _print_proposal(
    proposal: dict[str, Any],
    index: int,
    total: int,
    existing: list[str],
    chunks: list[dict[str, Any]],
) -> None:
    print(f"\n{_SEP}")
    print(
        f"Proposal {index}/{total}  "
        f"(observed {proposal['observed_count']}×  "
        f"first {(proposal['first_seen'] or '')[:10]}  "
        f"last {(proposal['last_seen'] or '')[:10]})"
    )
    print(_SEP)
    print(f"  label   : {proposal['label']}")
    print(f"  cluster : {proposal['cluster']}")
    print(f"  gloss   : {proposal['gloss'] or '(none)'}")
    if proposal.get("rationale"):
        print(f"  why     : {proposal['rationale']}")
    existing_str = ", ".join(existing) if existing else "(none)"
    print(f"\n  existing canonicals in {proposal['cluster']}: {existing_str}")
    if chunks:
        print("\n  example chunks:")
        for i, ch in enumerate(chunks, 1):
            preview = (ch.get("content") or "").replace("\n", " ").strip()
            if len(preview) > 180:
                preview = preview[:177] + "..."
            print(f"    [{i}] ({ch.get('kind', '?')}) {preview}")


def _prompt() -> str:
    while True:
        try:
            raw = input("\n  [a]ccept  [r]eject  [s]kip  [q]uit  → ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return "q"
        if raw in ("a", "r", "s", "q"):
            return raw
        print("  Enter a, r, s, or q.")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


async def _run() -> None:
    settings = Settings()
    client = Neo4jClient(settings)

    try:
        proposals = await _fetch_proposals(client)
    except Exception as exc:
        print(f"Error fetching proposals: {exc}", file=sys.stderr)
        await client.close()
        sys.exit(1)

    if not proposals:
        print("No :CanonicalTagProposal nodes found. Nothing to review.")
        await client.close()
        return

    total = len(proposals)
    print(f"Found {total} proposal(s) to review.")

    accepted = rejected = skipped = 0

    for i, proposal in enumerate(proposals, 1):
        try:
            existing, chunks = await asyncio.gather(
                _fetch_existing_canonicals(client, proposal["cluster"]),
                _fetch_example_chunks(client, proposal["proposal_id"]),
            )
        except Exception as exc:
            print(f"  Warning: could not load context for {proposal['label']}: {exc}")
            existing, chunks = [], []

        _print_proposal(proposal, i, total, existing, chunks)
        action = _prompt()

        if action == "q":
            remaining = total - i
            print(f"  Quit. {remaining} proposal(s) left unreviewed.")
            break

        if action == "a":
            try:
                await _promote(client, proposal)
                _update_seed(proposal["label"], proposal["cluster"])
                print(f"  ✓ Accepted '{proposal['label']}' → {proposal['cluster']}")
                accepted += 1
            except Exception as exc:
                print(f"  Error accepting: {exc}", file=sys.stderr)

        elif action == "r":
            try:
                await _reject(client, proposal["proposal_id"])
                print(f"  ✗ Rejected '{proposal['label']}'")
                rejected += 1
            except Exception as exc:
                print(f"  Error rejecting: {exc}", file=sys.stderr)

        else:
            print(f"  → Skipped '{proposal['label']}'")
            skipped += 1

    print(f"\n{_SEP}")
    print(f"Session done.  accepted={accepted}  rejected={rejected}  skipped={skipped}")
    if accepted:
        print(
            f"\nRun `python scripts/bootstrap_schema.py` to resync the full canonical "
            f"vocab from canonical_seed.yaml into the database."
        )
    print(_SEP)

    await client.close()


if __name__ == "__main__":
    asyncio.run(_run())

"""Graph query API for the clustering layer.

Four async functions wrap the Cypher files in clustering/queries/:

  files_by_canonical  – single-dimension lookup by cluster + canonical_id.
                        Covers the "by_theme" and "by_information_need" views.
  files_recent_active – files tagged recent or active in time_relevance.
  files_multidim      – multi-constraint scoring across any mix of dimensions.
  chunks_for_file     – retrieve ranked chunks for one file (RAGAS contexts).

All functions open their own Neo4j session and return plain dataclasses.
They never write to the graph.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shared.neo4j_client import Neo4jClient


_QUERIES_DIR = Path(__file__).resolve().parent / "queries"


# ---------------------------------------------------------------------------
# Return types
# ---------------------------------------------------------------------------


@dataclass
class TagHit:
    tag_name: str
    cluster: str
    canonical_id: str | None
    weight_global: float


@dataclass
class FileResult:
    file_id: str
    dataset_id: str
    rel_path: str
    description: str | None
    score: float
    dims_matched: int
    matched_tags: list[TagHit] = field(default_factory=list)


@dataclass
class ChunkResult:
    chunk_id: str
    ordinal: int
    kind: str
    content: str
    description: str | None
    relevance_to_file: float | None
    tags: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def files_by_canonical(
    client: Neo4jClient,
    *,
    cluster: str,
    canonical_id: str,
    limit: int = 20,
) -> list[FileResult]:
    """Files ranked by weight_global for one cluster + canonical_id pair.

    Covers the planned 'by_theme' and 'by_information_need' named views —
    pass cluster='theme' or cluster='information_need' respectively.
    """
    cypher = _load("by_canonical.cypher")
    async with client.session() as session:
        result = await session.run(
            cypher,
            cluster=cluster,
            canonical_id=canonical_id,
            limit=limit,
        )
        rows = [dict(r) async for r in result]
    return [_to_file_result(r, dims_matched=1) for r in rows]


async def files_recent_active(
    client: Neo4jClient,
    *,
    limit: int = 20,
) -> list[FileResult]:
    """Files tagged as 'recent' or 'active' in time_relevance, ranked by
    their maximum time_relevance weight_global."""
    cypher = _load("recent_active.cypher")
    async with client.session() as session:
        result = await session.run(cypher, limit=limit)
        rows = [dict(r) async for r in result]
    return [_to_file_result(r, dims_matched=1) for r in rows]


async def files_multidim(
    client: Neo4jClient,
    *,
    constraints: list[tuple[str, str]],
    limit: int = 20,
) -> list[FileResult]:
    """Files scored across multiple (cluster, canonical_id) constraints.

    Each constraint is a (cluster, canonical_id) tuple. Files that match
    more constraints rank higher (dims_matched DESC), then by composite
    score. Files matching zero constraints are excluded.

    Example::

        results = await files_multidim(
            client,
            constraints=[
                ("theme", "advertising"),
                ("time_relevance", "recent"),
            ],
        )
    """
    if not constraints:
        return []
    cypher = _load("multidim.cypher")
    params = [{"cluster": c, "canonical_id": cid} for c, cid in constraints]
    async with client.session() as session:
        result = await session.run(cypher, constraints=params, limit=limit)
        rows = [dict(r) async for r in result]
    return [_to_file_result(r) for r in rows]


async def chunks_for_file(
    client: Neo4jClient,
    file_id: str,
    *,
    limit: int = 10,
) -> list[ChunkResult]:
    """Non-empty chunks for a file, ordered by relevance_to_file DESC.

    Use this after a file-level query to fetch the content that serves as
    retrieval context (e.g. for RAGAS evaluation). Chunks whose file
    orchestrator has not run yet sort after scored chunks (relevance = null
    treated as 0.5, matching the rollup default).
    """
    cypher = _load("chunks_for_file.cypher")
    async with client.session() as session:
        result = await session.run(cypher, file_id=file_id, limit=limit)
        rows = [dict(r) async for r in result]
    return [
        ChunkResult(
            chunk_id=r["chunk_id"],
            ordinal=int(r["ordinal"]),
            kind=r["kind"],
            content=r.get("content") or "",
            description=r.get("description"),
            relevance_to_file=(
                float(r["relevance_to_file"]) if r.get("relevance_to_file") is not None else None
            ),
            tags=r.get("tags") or [],
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load(filename: str) -> str:
    return (_QUERIES_DIR / filename).read_text(encoding="utf-8")


def _to_file_result(r: dict[str, Any], *, dims_matched: int | None = None) -> FileResult:
    matched_tags = [
        TagHit(
            tag_name=t.get("tag_name", ""),
            cluster=t.get("cluster", ""),
            canonical_id=t.get("canonical_id"),
            weight_global=float(t.get("weight_global") or 0.0),
        )
        for t in (r.get("matched_tags") or [])
        if t is not None
    ]
    return FileResult(
        file_id=r["file_id"],
        dataset_id=r["dataset_id"],
        rel_path=r["rel_path"],
        description=r.get("description"),
        score=float(r.get("score") or 0.0),
        dims_matched=int(r.get("dims_matched") or dims_matched or 1),
        matched_tags=matched_tags,
    )


# ---------------------------------------------------------------------------
# CLI  (python -m clustering.query)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import asyncio
    import sys
    from pathlib import Path as _Path

    # Ensure backend/ is importable when invoked as a script from any cwd.
    _backend_root = _Path(__file__).resolve().parent.parent
    if str(_backend_root) not in sys.path:
        sys.path.insert(0, str(_backend_root))

    from shared.config import Settings
    from shared.neo4j_client import Neo4jClient as _Neo4jClient

    # ------------------------------------------------------------------ print helpers

    def _fmt_file(i: int, f: FileResult) -> None:
        path = f"{f.dataset_id}/{f.rel_path}"
        dims = f"  dims={f.dims_matched}" if f.dims_matched > 1 else ""
        print(f"\n #{i}  score={f.score:.3f}{dims}  {path}")
        if f.description:
            first_line = f.description.replace("\n", " ").strip()
            if len(first_line) > 120:
                first_line = first_line[:117] + "..."
            print(f"     {first_line}")
        if f.matched_tags:
            tag_str = "  ".join(
                f"{t.tag_name}({t.cluster},{t.weight_global:.2f})"
                for t in sorted(f.matched_tags, key=lambda t: -t.weight_global)
            )
            print(f"     tags: {tag_str}")

    def _fmt_chunk(c: ChunkResult) -> None:
        rel = f"rel={c.relevance_to_file:.3f}" if c.relevance_to_file is not None else "rel=?"
        print(f"\n  #{c.ordinal}  {c.kind}  {rel}")
        if c.tags:
            tag_str = "  ".join(
                f"{t.get('name', t.get('tag_name',''))}({t.get('cluster','')},{float(t.get('weight_local', 0)):.2f})"
                for t in c.tags[:8]
            )
            print(f"  tags: {tag_str}")
        preview = c.content.replace("\n", " ").strip()
        if len(preview) > 200:
            preview = preview[:197] + "..."
        print(f"  {preview}")

    # ------------------------------------------------------------------ subcommands

    async def _by_canonical(args: argparse.Namespace) -> None:
        client = _Neo4jClient(Settings())
        try:
            results = await files_by_canonical(
                client, cluster=args.cluster, canonical_id=args.canonical_id, limit=args.limit
            )
        finally:
            await client.close()
        print(f"by-canonical  cluster={args.cluster}  canonical_id={args.canonical_id}  "
              f"limit={args.limit}  → {len(results)} file(s)")
        for i, f in enumerate(results, 1):
            _fmt_file(i, f)
        print()

    async def _recent_active(args: argparse.Namespace) -> None:
        client = _Neo4jClient(Settings())
        try:
            results = await files_recent_active(client, limit=args.limit)
        finally:
            await client.close()
        print(f"recent-active  limit={args.limit}  → {len(results)} file(s)")
        for i, f in enumerate(results, 1):
            _fmt_file(i, f)
        print()

    async def _multidim(args: argparse.Namespace) -> None:
        constraints: list[tuple[str, str]] = []
        for token in args.constraints:
            if ":" not in token:
                print(f"Error: constraint '{token}' must be in cluster:canonical_id format",
                      file=sys.stderr)
                sys.exit(1)
            cluster, _, canonical_id = token.partition(":")
            constraints.append((cluster.strip(), canonical_id.strip()))
        client = _Neo4jClient(Settings())
        try:
            results = await files_multidim(client, constraints=constraints, limit=args.limit)
        finally:
            await client.close()
        pairs = "  ".join(f"{c}:{cid}" for c, cid in constraints)
        print(f"multidim  [{pairs}]  limit={args.limit}  → {len(results)} file(s)")
        for i, f in enumerate(results, 1):
            _fmt_file(i, f)
        print()

    async def _chunks_for(args: argparse.Namespace) -> None:
        client = _Neo4jClient(Settings())
        try:
            results = await chunks_for_file(client, args.file_id, limit=args.limit)
        finally:
            await client.close()
        print(f"chunks-for  file_id={args.file_id}  limit={args.limit}  → {len(results)} chunk(s)")
        for c in results:
            _fmt_chunk(c)
        print()

    # ------------------------------------------------------------------ arg parser

    def _make_parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="python -m clustering.query",
            description="Query the Neo4j graph by cluster dimensions.",
        )
        sub = parser.add_subparsers(dest="command", required=True)

        p_bc = sub.add_parser("by-canonical", help="Files by cluster + canonical_id.")
        p_bc.add_argument("cluster", help="e.g. theme, information_need, object_entity")
        p_bc.add_argument("canonical_id", help="e.g. advertising, number, person")
        p_bc.add_argument("--limit", type=int, default=20)

        p_ra = sub.add_parser("recent-active", help="Files tagged recent or active.")
        p_ra.add_argument("--limit", type=int, default=20)

        p_md = sub.add_parser(
            "multidim",
            help="Multi-dimensional scoring. Pass constraints as cluster:canonical_id tokens.",
        )
        p_md.add_argument(
            "constraints",
            nargs="+",
            metavar="cluster:canonical_id",
            help="e.g. theme:advertising time_relevance:recent",
        )
        p_md.add_argument("--limit", type=int, default=20)

        p_cf = sub.add_parser("chunks-for", help="Ranked chunks for a file (RAGAS contexts).")
        p_cf.add_argument("file_id")
        p_cf.add_argument("--limit", type=int, default=10)

        return parser

    # ------------------------------------------------------------------ dispatch

    _HANDLERS = {
        "by-canonical": _by_canonical,
        "recent-active": _recent_active,
        "multidim": _multidim,
        "chunks-for": _chunks_for,
    }

    _args = _make_parser().parse_args()
    asyncio.run(_HANDLERS[_args.command](_args))

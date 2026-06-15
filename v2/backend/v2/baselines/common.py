"""Shared helpers for v2 Neo4j baseline retrievers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase, Session
from shared.config import REPO_ROOT as BACKEND_ROOT, Settings

MONOREPO_ROOT = BACKEND_ROOT.parent

DEFAULT_EXCLUDED_SECTIONS = (
    "answerable_questions",
    "unanswerable_questions",
    "product_profile",
)

CONTENT_FULLTEXT_INDEX = "chunk_content_ft"
CONTENT_VECTOR_INDEX = "chunk_emb_content"


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    file_id: str
    content: str
    description: str | None
    relevance_to_file: float | None
    score: float


def sanitize_lucene(text: str) -> str:
    cleaned = re.sub(r'[+\-&|!(){}[\]^"~*?:\\/]', " ", text or "")
    return " ".join(cleaned.split())


def exclusion_clause(excluded: tuple[str, ...] | list[str]) -> str:
    return (
        'AND NOT (coalesce(c.section, "") IN $excludedSections)'
        if excluded
        else ""
    )


def normalize_limit(limit: int | None) -> int:
    raw = int(limit or 0)
    if raw <= 0:
        return 0
    return max(1, min(100_000, raw))


def neo4j_session(database: str | None = None) -> tuple[Any, Session]:
    settings = Settings()
    db = database or settings.neo4j_database
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    return driver, driver.session(database=db)


def row_to_chunk(rec: dict[str, Any]) -> RetrievedChunk:
    rel = rec.get("relevanceToFile")
    score = rec.get("score")
    return RetrievedChunk(
        chunk_id=str(rec["chunkId"]),
        file_id=str(rec["fileId"]),
        content=str(rec.get("content") or ""),
        description=rec.get("description") if rec.get("description") is None else str(rec["description"]),
        relevance_to_file=float(rel) if rel is not None else None,
        score=float(score) if score is not None else 0.0,
    )


def validate_dataset(session: Session, dataset_id: str | None) -> None:
    if not dataset_id:
        return
    rec = session.run(
        "MATCH (f:File) WHERE f.dataset_id = $datasetId RETURN count(f) AS n",
        datasetId=dataset_id,
    ).single()
    if rec and int(rec["n"]) > 0:
        return
    valid = [
        r["v"]
        for r in session.run(
            """
            MATCH (f:File) WHERE f.dataset_id IS NOT NULL
            RETURN DISTINCT f.dataset_id AS v ORDER BY v LIMIT 60
            """
        )
    ]
    raise RuntimeError(
        f'Dataset "{dataset_id}" matches no files in the graph. '
        f"Valid datasets: {', '.join(valid) if valid else '(none)'}"
    )

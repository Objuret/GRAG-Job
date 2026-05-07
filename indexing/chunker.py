"""Per-format deterministic chunker.

Walks each File and emits ordered (:Chunk) nodes with content, offsets, and
HAS_CHUNK + NEXT edges. No LLM. Every Chunk is independently extractable.

Path A in our chunking design: deterministic boundaries, agent operates on
pre-existing chunks. Re-chunks only when no Chunks exist for the File yet.

chunk_id = stable_short_hash(file_id + ordinal + start_offset, 24).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal

from shared.neo4j_client import Neo4jClient
from shared.utils import iso_utc, stable_short_hash, utc_now


ChunkKind = Literal["record", "object", "section", "paragraph", "table", "image", "raw"]
DispatchMode = Literal["parallel", "sequential"]


def dispatch_mode_for(format_family: str) -> DispatchMode:
    """Records run in parallel, long-form text runs sequentially with continuity."""
    if format_family in {"pdf", "html", "docx", "md", "markdown", "txt", "text"}:
        return "sequential"
    return "parallel"


@dataclass(frozen=True)
class ChunkPolicy:
    target_min_tokens: int = 200
    target_max_tokens: int = 800
    hard_max_tokens: int = 1500


@dataclass
class ChunkRecord:
    chunk_id: str
    file_id: str
    ordinal: int
    kind: ChunkKind
    start_offset: int
    end_offset: int
    content: str
    token_estimate: int
    locator: dict[str, Any] = field(default_factory=dict)


def _est_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class Chunker:
    def __init__(self, client: Neo4jClient, policy: ChunkPolicy | None = None) -> None:
        self._client = client
        self._policy = policy or ChunkPolicy()

    async def chunk_file(self, file_id: str, source_path: Path, format_family: str) -> int:
        """Chunk one file. Returns count of new chunks written.

        Idempotency rule: if any Chunk already exists for this file, skip.
        """
        existing = await self._existing_chunk_count(file_id)
        if existing > 0:
            return 0

        chunks = list(self._produce_chunks(file_id, source_path, format_family))
        if not chunks:
            return 0
        await self._write_chunks(chunks)
        return len(chunks)

    async def _existing_chunk_count(self, file_id: str) -> int:
        async with self._client.session() as s:
            result = await s.run(
                "MATCH (f:File {file_id: $fid})-[:HAS_CHUNK]->(c:Chunk) RETURN count(c) AS n",
                fid=file_id,
            )
            record = await result.single()
            return record["n"] if record else 0

    def _produce_chunks(self, file_id: str, path: Path, format_family: str) -> Iterable[ChunkRecord]:
        if format_family == "jsonl":
            return self._chunk_jsonl(file_id, path)
        if format_family == "json":
            return self._chunk_json(file_id, path)
        if format_family == "parquet":
            return self._chunk_parquet(file_id, path)
        if format_family in {"yaml", "yml"}:
            return self._chunk_text(file_id, path, kind="raw")
        if format_family in {"md", "markdown", "txt", "text"}:
            return self._chunk_text(file_id, path, kind="paragraph")
        if format_family in {"image", "archive", "unknown"}:
            return iter([])
        return self._chunk_text(file_id, path, kind="raw")

    def _make_chunk_id(self, file_id: str, ordinal: int, start_offset: int) -> str:
        return stable_short_hash(f"{file_id}:{ordinal}:{start_offset}", 24)

    def _chunk_jsonl(self, file_id: str, path: Path) -> Iterable[ChunkRecord]:
        offset = 0
        ordinal = 0
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line_len = len(line)
                stripped = line.strip()
                if not stripped:
                    offset += line_len
                    continue
                yield ChunkRecord(
                    chunk_id=self._make_chunk_id(file_id, ordinal, offset),
                    file_id=file_id,
                    ordinal=ordinal,
                    kind="record",
                    start_offset=offset,
                    end_offset=offset + line_len,
                    content=stripped,
                    token_estimate=_est_tokens(stripped),
                    locator={"line": ordinal},
                )
                ordinal += 1
                offset += line_len

    def _chunk_json(self, file_id: str, path: Path) -> Iterable[ChunkRecord]:
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            yield ChunkRecord(
                chunk_id=self._make_chunk_id(file_id, 0, 0),
                file_id=file_id,
                ordinal=0,
                kind="raw",
                start_offset=0,
                end_offset=len(text),
                content=text[: self._policy.hard_max_tokens * 4],
                token_estimate=_est_tokens(text),
                locator={"type": "malformed_json"},
            )
            return

        if isinstance(data, list):
            for ordinal, item in enumerate(data):
                content = json.dumps(item, ensure_ascii=False, indent=2, default=str)
                yield ChunkRecord(
                    chunk_id=self._make_chunk_id(file_id, ordinal, 0),
                    file_id=file_id,
                    ordinal=ordinal,
                    kind="record",
                    start_offset=0,
                    end_offset=len(content),
                    content=content,
                    token_estimate=_est_tokens(content),
                    locator={"index": ordinal},
                )
        elif isinstance(data, dict):
            full = json.dumps(data, ensure_ascii=False, indent=2, default=str)
            if _est_tokens(full) <= self._policy.hard_max_tokens:
                yield ChunkRecord(
                    chunk_id=self._make_chunk_id(file_id, 0, 0),
                    file_id=file_id,
                    ordinal=0,
                    kind="object",
                    start_offset=0,
                    end_offset=len(full),
                    content=full,
                    token_estimate=_est_tokens(full),
                    locator={"type": "object"},
                )
            else:
                for ordinal, (key, value) in enumerate(data.items()):
                    content = json.dumps({key: value}, ensure_ascii=False, indent=2, default=str)
                    yield ChunkRecord(
                        chunk_id=self._make_chunk_id(file_id, ordinal, 0),
                        file_id=file_id,
                        ordinal=ordinal,
                        kind="record",
                        start_offset=0,
                        end_offset=len(content),
                        content=content,
                        token_estimate=_est_tokens(content),
                        locator={"key": key},
                    )
        else:
            yield ChunkRecord(
                chunk_id=self._make_chunk_id(file_id, 0, 0),
                file_id=file_id,
                ordinal=0,
                kind="raw",
                start_offset=0,
                end_offset=len(text),
                content=text,
                token_estimate=_est_tokens(text),
                locator={"type": "primitive"},
            )

    def _chunk_parquet(self, file_id: str, path: Path) -> Iterable[ChunkRecord]:
        """Stream parquet rows in batches so we never materialize the full table.

        Files containing image bytes can exceed RAM if read whole. We use
        ``ParquetFile.iter_batches`` and convert each :class:`pyarrow.RecordBatch`
        to Python dicts one batch at a time. Bytes/bytearray values are replaced
        with a placeholder so chunk content stays small.
        """
        import pyarrow.parquet as pq

        pf = pq.ParquetFile(path)
        ordinal = 0
        for batch in pf.iter_batches(batch_size=512):
            rows = batch.to_pylist()
            for row in rows:
                clean = {
                    k: (
                        f"<{type(v).__name__} {len(v)} bytes>"
                        if isinstance(v, (bytes, bytearray))
                        else v
                    )
                    for k, v in row.items()
                }
                content = json.dumps(clean, ensure_ascii=False, indent=2, default=str)
                yield ChunkRecord(
                    chunk_id=self._make_chunk_id(file_id, ordinal, 0),
                    file_id=file_id,
                    ordinal=ordinal,
                    kind="record",
                    start_offset=0,
                    end_offset=len(content),
                    content=content,
                    token_estimate=_est_tokens(content),
                    locator={"row": ordinal},
                )
                ordinal += 1

    def _chunk_text(self, file_id: str, path: Path, kind: ChunkKind) -> Iterable[ChunkRecord]:
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            return

        max_chars = self._policy.target_max_tokens * 4
        hard_max_chars = self._policy.hard_max_tokens * 4

        paragraphs: list[tuple[int, int, str]] = []
        offset = 0
        for m in re.finditer(r"\n\s*\n", text):
            end = m.start()
            piece = text[offset:end].strip()
            if piece:
                paragraphs.append((offset, end, piece))
            offset = m.end()
        tail = text[offset:].strip()
        if tail:
            paragraphs.append((offset, len(text), tail))

        if not paragraphs:
            paragraphs = [(0, len(text), text.strip())]

        ordinal = 0
        buf_text: list[str] = []
        buf_start: int | None = None
        buf_end: int = 0

        def flush() -> Iterable[ChunkRecord]:
            nonlocal ordinal, buf_text, buf_start, buf_end
            if not buf_text or buf_start is None:
                return
            content = "\n\n".join(buf_text)
            yield ChunkRecord(
                chunk_id=self._make_chunk_id(file_id, ordinal, buf_start),
                file_id=file_id,
                ordinal=ordinal,
                kind=kind,
                start_offset=buf_start,
                end_offset=buf_end,
                content=content,
                token_estimate=_est_tokens(content),
                locator={"char_range": [buf_start, buf_end]},
            )
            ordinal += 1
            buf_text = []
            buf_start = None

        for (p_start, p_end, p_text) in paragraphs:
            if len(p_text) > hard_max_chars:
                yield from flush()
                for i in range(0, len(p_text), hard_max_chars):
                    slice_text = p_text[i : i + hard_max_chars]
                    yield ChunkRecord(
                        chunk_id=self._make_chunk_id(file_id, ordinal, p_start + i),
                        file_id=file_id,
                        ordinal=ordinal,
                        kind=kind,
                        start_offset=p_start + i,
                        end_offset=p_start + i + len(slice_text),
                        content=slice_text,
                        token_estimate=_est_tokens(slice_text),
                        locator={"char_range": [p_start + i, p_start + i + len(slice_text)], "split": True},
                    )
                    ordinal += 1
                continue

            current_len = sum(len(x) for x in buf_text) + max(0, (len(buf_text) - 1) * 2)
            if buf_text and (current_len + 2 + len(p_text)) > max_chars:
                yield from flush()

            if buf_start is None:
                buf_start = p_start
            buf_text.append(p_text)
            buf_end = p_end

        yield from flush()

    _WRITE_BATCH_SIZE: int = 500

    async def _write_chunks(self, chunks: list[ChunkRecord]) -> None:
        """Persist chunks in batches to keep Neo4j transactions bounded.

        For very large files (10k+ rows) a single ``UNWIND`` over all rows can
        blow the transaction. We split into batches of ``_WRITE_BATCH_SIZE`` for
        both the Chunk MERGE pass and the NEXT-edge pass. Schema, properties,
        and edge types are unchanged.
        """
        items = [
            {
                "chunk_id": c.chunk_id,
                "file_id": c.file_id,
                "ordinal": c.ordinal,
                "kind": c.kind,
                "start_offset": c.start_offset,
                "end_offset": c.end_offset,
                "content": c.content,
                "token_estimate": c.token_estimate,
                "locator_json": json.dumps(c.locator, ensure_ascii=False, default=str),
            }
            for c in chunks
        ]
        now = iso_utc(utc_now())
        batch_size = self._WRITE_BATCH_SIZE

        async with self._client.session() as s:
            for start in range(0, len(items), batch_size):
                batch = items[start : start + batch_size]
                await s.run(
                    """
                    UNWIND $items AS item
                    MATCH (f:File {file_id: item.file_id})
                    MERGE (c:Chunk {chunk_id: item.chunk_id})
                    ON CREATE SET
                        c.file_id = item.file_id,
                        c.ordinal = item.ordinal,
                        c.kind = item.kind,
                        c.start_offset = item.start_offset,
                        c.end_offset = item.end_offset,
                        c.content = item.content,
                        c.token_estimate = item.token_estimate,
                        c.locator_json = item.locator_json,
                        c.empty = false,
                        c.created_at = $now
                    MERGE (f)-[:HAS_CHUNK]->(c)
                    """,
                    items=batch,
                    now=now,
                )

        pairs = [
            {"a": chunks[i].chunk_id, "b": chunks[i + 1].chunk_id}
            for i in range(len(chunks) - 1)
        ]
        if not pairs:
            return

        async with self._client.session() as s:
            for start in range(0, len(pairs), batch_size):
                batch = pairs[start : start + batch_size]
                await s.run(
                    """
                    UNWIND $pairs AS p
                    MATCH (a:Chunk {chunk_id: p.a})
                    MATCH (b:Chunk {chunk_id: p.b})
                    MERGE (a)-[:NEXT]->(b)
                    """,
                    pairs=batch,
                )

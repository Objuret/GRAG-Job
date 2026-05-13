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
from typing import Any, Callable, Iterable, Literal

from shared.neo4j_client import Neo4jClient
from shared.utils import iso_utc, stable_short_hash, utc_now


ChunkKind = Literal[
    "record",
    "object",
    "section",
    "paragraph",
    "table",
    "image",
    "raw",
    "product_profile",
    "directory_batch",
    "org_tree",
    "slack_thread_batch",
    "document",
    "document_part",
    "meeting_transcript",
    "meeting_transcript_part",
    "meeting_chat_batch",
    "url_batch",
    "pr_batch",
    "qa_record",
    "qa_record_part",
    "qa_batch",
    "unanswerable_question_batch",
]
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
                "MATCH (c:Chunk {file_id: $fid}) RETURN count(c) AS n",
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

    def _cap_chunk_content(self, content: str) -> str:
        max_chars = self._policy.hard_max_tokens * 4
        if len(content) <= max_chars:
            return content
        return content[:max_chars] + "\n...<chunk content truncated>"

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
                content = self._cap_chunk_content(stripped)
                yield ChunkRecord(
                    chunk_id=self._make_chunk_id(file_id, ordinal, offset),
                    file_id=file_id,
                    ordinal=ordinal,
                    kind="record",
                    start_offset=offset,
                    end_offset=offset + line_len,
                    content=content,
                    token_estimate=_est_tokens(content),
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
                content=self._cap_chunk_content(text),
                token_estimate=_est_tokens(self._cap_chunk_content(text)),
                locator={"type": "malformed_json"},
            )
            return

        if self._is_herb_path(path):
            herb_chunks = list(self._chunk_herb_json(file_id, path, data))
            if herb_chunks:
                yield from herb_chunks
                return

        if isinstance(data, list):
            for ordinal, item in enumerate(data):
                safe = self._make_json_safe_for_chunk(item)
                content = self._cap_chunk_content(
                    json.dumps(safe, ensure_ascii=False, indent=2, default=str)
                )
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
            safe_data = self._make_json_safe_for_chunk(data)
            full = json.dumps(safe_data, ensure_ascii=False, indent=2, default=str)
            if _est_tokens(full) <= self._policy.hard_max_tokens:
                content = self._cap_chunk_content(full)
                yield ChunkRecord(
                    chunk_id=self._make_chunk_id(file_id, 0, 0),
                    file_id=file_id,
                    ordinal=0,
                    kind="object",
                    start_offset=0,
                    end_offset=len(content),
                    content=content,
                    token_estimate=_est_tokens(content),
                    locator={"type": "object"},
                )
            else:
                for ordinal, (key, value) in enumerate(safe_data.items()):
                    content = self._cap_chunk_content(
                        json.dumps({key: value}, ensure_ascii=False, indent=2, default=str)
                    )
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
                content=self._cap_chunk_content(text),
                token_estimate=_est_tokens(self._cap_chunk_content(text)),
                locator={"type": "primitive"},
            )

    def _is_herb_path(self, path: Path) -> bool:
        return any(part == "Salesforce__HERB" for part in path.parts)

    def _chunk_herb_json(
        self,
        file_id: str,
        path: Path,
        data: Any,
    ) -> Iterable[ChunkRecord]:
        ordinal = 0
        for kind, raw_content, locator in self._herb_json_specs(path, data):
            locator = dict(locator)
            parent_ref, chunk_ref = self._herb_refs(path, locator)
            locator["chunk_ref"] = chunk_ref
            if parent_ref is not None:
                locator["parent_ref"] = parent_ref

            content = self._inject_herb_refs(
                raw_content,
                chunk_ref=chunk_ref,
                parent_ref=parent_ref,
            )
            token_estimate = _est_tokens(content)
            if token_estimate > self._policy.hard_max_tokens:
                raise ValueError(
                    "HERB chunk exceeds hard token budget; split strategy missing: "
                    f"kind={kind} tokens={token_estimate} locator={locator}"
                )
            yield ChunkRecord(
                chunk_id=self._make_chunk_id(file_id, ordinal, 0),
                file_id=file_id,
                ordinal=ordinal,
                kind=kind,
                start_offset=0,
                end_offset=len(content),
                content=content,
                token_estimate=token_estimate,
                locator=locator,
            )
            ordinal += 1

    def _herb_json_specs(
        self,
        path: Path,
        data: Any,
    ) -> Iterable[tuple[str, str, dict[str, Any]]]:
        if self._path_has_part(path, "products") and isinstance(data, dict):
            yield from self._herb_product_specs(path, data)
            return

        name = path.name
        if name == "customers_data.json" and isinstance(data, list):
            yield from self._herb_pack_indexed_records(
                title="HERB customer directory chunk",
                kind="directory_batch",
                path=path,
                section="customers_data",
                indexed_rows=list(enumerate(data)),
                locator_base={"herb": True, "metadata": "customers_data"},
                target_tokens=self._policy.target_max_tokens,
            )
            return

        if name == "employee.json" and isinstance(data, dict):
            rows = [
                (index, {**value, "_key": key})
                for index, (key, value) in enumerate(data.items())
                if isinstance(value, dict)
            ]
            yield from self._herb_pack_indexed_records(
                title="HERB employee directory chunk",
                kind="directory_batch",
                path=path,
                section="employee",
                indexed_rows=rows,
                locator_base={"herb": True, "metadata": "employee"},
                target_tokens=self._policy.target_max_tokens,
            )
            return

        if name == "salesforce_team.json" and isinstance(data, list):
            for index, row in enumerate(data):
                if isinstance(row, dict):
                    yield from self._herb_org_tree_specs(path, index, row)
            return

    def _herb_product_specs(
        self,
        path: Path,
        data: dict[str, Any],
    ) -> Iterable[tuple[str, str, dict[str, Any]]]:
        product = path.stem
        yield self._herb_product_profile_spec(path, product, data)

        slack_rows = self._dict_rows(data.get("slack"))
        for channel, indexed_rows in self._group_herb_slack_rows(slack_rows).items():
            yield from self._herb_pack_indexed_records(
                title="HERB Slack conversation chunk",
                kind="slack_thread_batch",
                path=path,
                product=product,
                section="slack",
                indexed_rows=indexed_rows,
                locator_base={
                    "herb": True,
                    "product": product,
                    "section": "slack",
                    "channel": channel,
                },
                context_lines=[f"Channel: {channel}"],
                line_renderer=self._herb_slack_record_line,
                target_tokens=self._policy.target_max_tokens,
            )

        for index, row in self._dict_rows(data.get("documents")):
            yield from self._herb_text_record_specs(
                path=path,
                product=product,
                section="documents",
                index=index,
                row=row,
                text_field="content",
                full_kind="document",
                part_kind="document_part",
                title="HERB document chunk",
            )

        for index, row in self._dict_rows(data.get("meeting_transcripts")):
            yield from self._herb_text_record_specs(
                path=path,
                product=product,
                section="meeting_transcripts",
                index=index,
                row=row,
                text_field="transcript",
                full_kind="meeting_transcript",
                part_kind="meeting_transcript_part",
                title="HERB meeting transcript chunk",
            )

        yield from self._herb_pack_indexed_records(
            title="HERB meeting chat chunk",
            kind="meeting_chat_batch",
            path=path,
            product=product,
            section="meeting_chats",
            indexed_rows=self._dict_rows(data.get("meeting_chats")),
            locator_base={"herb": True, "product": product, "section": "meeting_chats"},
            target_tokens=self._policy.target_max_tokens,
        )

        yield from self._herb_pack_indexed_records(
            title="HERB URL reference chunk",
            kind="url_batch",
            path=path,
            product=product,
            section="urls",
            indexed_rows=self._dict_rows(data.get("urls")),
            locator_base={"herb": True, "product": product, "section": "urls"},
            target_tokens=self._policy.target_max_tokens,
        )

        yield from self._herb_pack_indexed_records(
            title="HERB pull request chunk",
            kind="pr_batch",
            path=path,
            product=product,
            section="prs",
            indexed_rows=self._dict_rows(data.get("prs")),
            locator_base={"herb": True, "product": product, "section": "prs"},
            line_renderer=self._herb_pr_record_line,
            target_tokens=self._policy.target_max_tokens,
        )

        yield from self._herb_question_specs(
            path=path,
            product=product,
            rows=self._dict_rows(data.get("answerable_questions")),
        )

        unanswerable = [
            (index, {"question": value})
            for index, value in enumerate(data.get("unanswerable_questions") or [])
            if isinstance(value, str) and value.strip()
        ]
        yield from self._herb_pack_indexed_records(
            title="HERB unanswerable question chunk",
            kind="unanswerable_question_batch",
            path=path,
            product=product,
            section="unanswerable_questions",
            indexed_rows=unanswerable,
            locator_base={
                "herb": True,
                "product": product,
                "section": "unanswerable_questions",
            },
            target_tokens=self._policy.target_max_tokens,
        )

    def _herb_product_profile_spec(
        self,
        path: Path,
        product: str,
        data: dict[str, Any],
    ) -> tuple[str, str, dict[str, Any]]:
        section_counts = {
            key: len(value)
            for key, value in data.items()
            if isinstance(value, (list, dict))
        }
        profile = {
            "product": product,
            "team_employee_ids": data.get("team") or [],
            "customer_ids": data.get("customers") or [],
            "section_counts": section_counts,
        }
        content = "\n".join(
            [
                "HERB product profile chunk",
                "Chunk type: product_profile",
                f"Source file: {self._display_path(path)}",
                f"Product: {product}",
                "",
                "This chunk summarizes product-level membership and available evidence sections.",
                "",
                self._pretty_json(profile),
            ]
        )
        locator = {
            "herb": True,
            "product": product,
            "section": "product_profile",
        }
        return "product_profile", content, locator

    def _herb_org_tree_specs(
        self,
        path: Path,
        index: int,
        row: dict[str, Any],
    ) -> Iterable[tuple[str, str, dict[str, Any]]]:
        base_locator = {
            "herb": True,
            "metadata": "salesforce_team",
            "index": index,
            "employee_id": row.get("employee_id"),
        }
        full_content = self._herb_single_record_content(
            title="HERB Salesforce org tree chunk",
            kind="org_tree",
            path=path,
            section="salesforce_team",
            index=index,
            row=row,
        )
        if _est_tokens(full_content) <= self._herb_content_budget_tokens():
            yield "org_tree", full_content, base_locator
            return

        vp_fields = {
            key: row.get(key)
            for key in ("employee_id", "name", "role", "location", "org")
            if key in row
        }
        for key, value in row.items():
            if key in vp_fields or not isinstance(value, list) or not value:
                continue
            part = {
                "vp": vp_fields,
                key: value,
            }
            content = self._herb_single_record_content(
                title="HERB Salesforce org tree chunk",
                kind="org_tree",
                path=path,
                section=f"salesforce_team.{key}",
                index=index,
                row=part,
            )
            locator = {**base_locator, "subsection": key}
            yield "org_tree", content, locator

    def _herb_text_record_specs(
        self,
        *,
        path: Path,
        product: str,
        section: str,
        index: int,
        row: dict[str, Any],
        text_field: str,
        full_kind: str,
        part_kind: str,
        title: str,
    ) -> Iterable[tuple[str, str, dict[str, Any]]]:
        text = str(row.get(text_field) or "")
        locator_base = {
            "herb": True,
            "product": product,
            "section": section,
            "index": index,
            "id": row.get("id"),
        }
        full_content = self._herb_text_record_content(
            title=title,
            kind=full_kind,
            path=path,
            product=product,
            section=section,
            index=index,
            row=row,
            text_field=text_field,
            text=text,
        )
        if _est_tokens(full_content) <= self._herb_content_budget_tokens():
            yield full_kind, full_content, locator_base
            return

        metadata = {key: value for key, value in row.items() if key != text_field}
        header = self._herb_record_header(
            title=title,
            kind=part_kind,
            path=path,
            product=product,
            section=section,
            index=index,
            fields=list(row.keys()),
        )
        header.extend(["Metadata:", self._pretty_json(metadata), ""])
        max_chars = max(800, (self._policy.target_max_tokens - _est_tokens("\n".join(header))) * 4)
        for part_index, (start, end, part_text) in enumerate(self._split_text(text, max_chars)):
            content = "\n".join(
                [
                    *header,
                    f"Field: {text_field}",
                    f"Part: {part_index}",
                    "---",
                    part_text,
                    "---",
                ]
            )
            locator = {
                **locator_base,
                "field": text_field,
                "part": part_index,
                "char_range": [start, end],
            }
            yield part_kind, content, locator

    def _herb_question_specs(
        self,
        *,
        path: Path,
        product: str,
        rows: list[tuple[int, dict[str, Any]]],
    ) -> Iterable[tuple[str, str, dict[str, Any]]]:
        pending_batch: list[tuple[int, dict[str, Any]]] = []

        def flush_batch() -> Iterable[tuple[str, str, dict[str, Any]]]:
            nonlocal pending_batch
            if not pending_batch:
                return
            yield from self._herb_pack_indexed_records(
                title="HERB answerable QA chunk",
                kind="qa_batch",
                path=path,
                product=product,
                section="answerable_questions",
                indexed_rows=pending_batch,
                locator_base={
                    "herb": True,
                    "product": product,
                    "section": "answerable_questions",
                },
                target_tokens=self._policy.target_max_tokens,
            )
            pending_batch = []

        for index, row in rows:
            citations = row.get("citations") or []
            rich = _est_tokens(self._compact_json(row)) >= 250 or len(citations) > 5
            if rich:
                yield from flush_batch()
                yield from self._herb_qa_record_specs(
                    path=path,
                    product=product,
                    index=index,
                    row=row,
                )
            else:
                pending_batch.append((index, row))
        yield from flush_batch()

    def _herb_qa_record_specs(
        self,
        *,
        path: Path,
        product: str,
        index: int,
        row: dict[str, Any],
    ) -> Iterable[tuple[str, str, dict[str, Any]]]:
        content = self._herb_single_record_content(
            title="HERB answerable QA chunk",
            kind="qa_record",
            path=path,
            product=product,
            section="answerable_questions",
            index=index,
            row=row,
        )
        locator = {
            "herb": True,
            "product": product,
            "section": "answerable_questions",
            "index": index,
            "question": row.get("question"),
        }
        if _est_tokens(content) <= self._herb_content_budget_tokens():
            yield "qa_record", content, locator
            return

        citations = row.get("citations")
        if not isinstance(citations, list) or not citations:
            yield "qa_record", content, locator
            return

        base = {key: value for key, value in row.items() if key != "citations"}
        batch: list[tuple[int, Any]] = []

        def render(rows: list[tuple[int, Any]]) -> str:
            indices = [i for i, _ in rows]
            lines = self._herb_record_header(
                title="HERB answerable QA citation chunk",
                kind="qa_record_part",
                path=path,
                product=product,
                section="answerable_questions",
                index=index,
                fields=list(row.keys()),
            )
            lines.extend(
                [
                    f"Citation indices: {indices[0]}-{indices[-1]}",
                    f"Citation count: {len(indices)}",
                    "",
                    "Question and answer:",
                    self._pretty_json(base),
                    "",
                    "Citations:",
                    self._pretty_json([citation for _, citation in rows]),
                ]
            )
            return "\n".join(lines)

        def flush() -> Iterable[tuple[str, str, dict[str, Any]]]:
            nonlocal batch
            if not batch:
                return
            indices = [i for i, _ in batch]
            part_locator = {
                **locator,
                "citation_start": indices[0],
                "citation_end": indices[-1],
            }
            yield "qa_record_part", render(batch), part_locator
            batch = []

        for citation_index, citation in enumerate(citations):
            candidate = [*batch, (citation_index, citation)]
            if batch and _est_tokens(render(candidate)) > self._policy.target_max_tokens:
                yield from flush()
            batch.append((citation_index, citation))
        yield from flush()

    def _herb_pack_indexed_records(
        self,
        *,
        title: str,
        kind: str,
        path: Path,
        section: str,
        indexed_rows: list[tuple[int, dict[str, Any]]],
        locator_base: dict[str, Any],
        product: str | None = None,
        context_lines: list[str] | None = None,
        line_renderer: Callable[[dict[str, Any]], str] | None = None,
        target_tokens: int,
    ) -> Iterable[tuple[str, str, dict[str, Any]]]:
        if not indexed_rows:
            return

        fields = self._field_order([row for _, row in indexed_rows])
        batch: list[tuple[int, str]] = []

        def render(rows: list[tuple[int, str]]) -> str:
            indices = [index for index, _ in rows]
            header = self._herb_record_header(
                title=title,
                kind=kind,
                path=path,
                product=product,
                section=section,
                index=None,
                fields=fields,
            )
            if context_lines:
                header.extend(context_lines)
            header.extend(
                [
                    f"Item indices: {indices[0]}-{indices[-1]}",
                    f"Item count: {len(indices)}",
                    "",
                    "Records:",
                ]
            )
            header.extend(line for _, line in rows)
            return "\n".join(header)

        def flush() -> Iterable[tuple[str, str, dict[str, Any]]]:
            nonlocal batch
            if not batch:
                return
            indices = [index for index, _ in batch]
            locator = {
                **locator_base,
                "index_start": indices[0],
                "index_end": indices[-1],
                "indices": indices,
            }
            yield kind, render(batch), locator
            batch = []

        for index, row in indexed_rows:
            line = line_renderer(row) if line_renderer else self._compact_json(row)
            candidate = [*batch, (index, line)]
            if batch and _est_tokens(render(candidate)) > target_tokens:
                yield from flush()
            batch.append((index, line))
        yield from flush()

    def _herb_slack_record_line(self, row: dict[str, Any]) -> str:
        message = row.get("Message")
        if not isinstance(message, dict):
            return self._compact_json(row)
        user = message.get("User")
        if not isinstance(user, dict):
            return self._compact_json(row)

        timestamp = str(user.get("timestamp") or "")
        user_id = str(user.get("userId") or "")
        utterance_id = str(user.get("utterranceID") or row.get("id") or "")
        text = str(user.get("text") or "").replace("\r\n", "\n").replace("\r", "\n")
        text = " ".join(part.strip() for part in text.splitlines() if part.strip())

        parts = [f"{timestamp} {user_id} ({utterance_id}): {text}".strip()]
        reactions = message.get("Reactions")
        if reactions:
            parts.append(f"reactions={self._compact_json(reactions)}")
        replies = row.get("ThreadReplies")
        if replies:
            parts.append(f"thread_replies={self._compact_json(replies)}")
        return " | ".join(parts)

    def _herb_pr_record_line(self, row: dict[str, Any]) -> str:
        user = row.get("user")
        login = user.get("login") if isinstance(user, dict) else None
        reviews = row.get("reviews")
        review_parts: list[str] = []
        if isinstance(reviews, list):
            for review in reviews:
                if not isinstance(review, dict):
                    continue
                reviewer = review.get("user")
                reviewer_login = reviewer.get("login") if isinstance(reviewer, dict) else None
                review_bits = [
                    str(review.get("state") or ""),
                    f"by={reviewer_login}" if reviewer_login else "",
                    f"at={review.get('submitted_at')}" if review.get("submitted_at") else "",
                    str(review.get("comment") or ""),
                ]
                review_parts.append(" ".join(bit for bit in review_bits if bit))

        bits = [
            f"PR #{row.get('number')}",
            str(row.get("title") or ""),
            f"state={row.get('state')}" if row.get("state") else "",
            f"merged={row.get('merged')}" if row.get("merged") is not None else "",
            f"mergeable={row.get('mergeable')}" if row.get("mergeable") is not None else "",
            f"created_at={row.get('created_at')}" if row.get("created_at") else "",
            f"user={login}" if login else "",
            f"summary={row.get('summary')}" if row.get("summary") else "",
            f"reviews={' ; '.join(review_parts)}" if review_parts else "",
            f"link={row.get('link')}" if row.get("link") else "",
            f"id={row.get('id')}" if row.get("id") else "",
        ]
        return " | ".join(bit for bit in bits if bit)

    def _herb_text_record_content(
        self,
        *,
        title: str,
        kind: str,
        path: Path,
        product: str,
        section: str,
        index: int,
        row: dict[str, Any],
        text_field: str,
        text: str,
    ) -> str:
        metadata = {key: value for key, value in row.items() if key != text_field}
        lines = self._herb_record_header(
            title=title,
            kind=kind,
            path=path,
            product=product,
            section=section,
            index=index,
            fields=list(row.keys()),
        )
        lines.extend(
            [
                "Metadata:",
                self._pretty_json(metadata),
                "",
                f"Field: {text_field}",
                "---",
                text,
                "---",
            ]
        )
        return "\n".join(lines)

    def _herb_single_record_content(
        self,
        *,
        title: str,
        kind: str,
        path: Path,
        section: str,
        index: int,
        row: dict[str, Any],
        product: str | None = None,
    ) -> str:
        lines = self._herb_record_header(
            title=title,
            kind=kind,
            path=path,
            product=product,
            section=section,
            index=index,
            fields=list(row.keys()),
        )
        lines.extend(["Record:", self._pretty_json(row)])
        content = "\n".join(lines)
        if _est_tokens(content) <= self._herb_content_budget_tokens():
            return content

        lines[-1] = self._compact_json(row)
        return "\n".join(lines)

    def _herb_content_budget_tokens(self) -> int:
        return max(1, self._policy.hard_max_tokens - 80)

    def _herb_record_header(
        self,
        *,
        title: str,
        kind: str,
        path: Path,
        section: str,
        fields: list[str],
        product: str | None = None,
        index: int | None = None,
    ) -> list[str]:
        lines = [
            title,
            f"Chunk type: {kind}",
            f"Source file: {self._display_path(path)}",
        ]
        if product is not None:
            lines.append(f"Product: {product}")
        lines.append(f"Section: {section}")
        if index is not None:
            lines.append(f"Item index: {index}")
        if fields:
            lines.append("Fields: " + ", ".join(fields))
        lines.append("")
        return lines

    def _herb_refs(
        self,
        path: Path,
        locator: dict[str, Any],
    ) -> tuple[str | None, str]:
        if locator.get("product"):
            parts = ["product", self._ref_part(locator["product"])]
        elif locator.get("metadata"):
            parts = ["metadata", self._ref_part(locator["metadata"])]
        else:
            parts = [self._ref_part(path.stem)]

        section = locator.get("section")
        if section and section not in {"product_profile"}:
            parts.append(self._ref_part(section))
        if locator.get("channel"):
            parts.append(self._ref_part(locator["channel"]))
        if locator.get("subsection"):
            parts.append(self._ref_part(locator["subsection"]))

        if "index" in locator:
            item_ref = [*parts, f"item{int(locator['index']):04d}"]
            if "part" in locator:
                return ".".join(item_ref), ".".join([*item_ref, f"part{int(locator['part']):02d}"])
            if "citation_start" in locator and "citation_end" in locator:
                return (
                    ".".join(item_ref),
                    ".".join(
                        [
                            *item_ref,
                            f"citations{int(locator['citation_start']):04d}-{int(locator['citation_end']):04d}",
                        ]
                    ),
                )
            return ".".join(parts), ".".join(item_ref)

        if "index_start" in locator and "index_end" in locator:
            return (
                ".".join(parts),
                ".".join(
                    [
                        *parts,
                        f"items{int(locator['index_start']):04d}-{int(locator['index_end']):04d}",
                    ]
                ),
            )

        chunk_ref = ".".join(parts)
        return None, chunk_ref

    @staticmethod
    def _ref_part(value: Any) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9-]+", "_", str(value)).strip("_")
        return cleaned or "unknown"

    @staticmethod
    def _inject_herb_refs(
        content: str,
        *,
        chunk_ref: str,
        parent_ref: str | None,
    ) -> str:
        lines = content.splitlines()
        insert_at = 1 if lines else 0
        ref_lines = [f"Chunk reference: {chunk_ref}"]
        if parent_ref and parent_ref != chunk_ref:
            ref_lines.insert(0, f"Parent reference: {parent_ref}")
        return "\n".join([*lines[:insert_at], *ref_lines, *lines[insert_at:]])

    @staticmethod
    def _path_has_part(path: Path, name: str) -> bool:
        return any(part.lower() == name.lower() for part in path.parts)

    @staticmethod
    def _display_path(path: Path) -> str:
        parts = list(path.parts)
        for index, part in enumerate(parts):
            if part == "Salesforce__HERB":
                return "/".join(parts[index:])
        return path.as_posix()

    @staticmethod
    def _dict_rows(value: Any) -> list[tuple[int, dict[str, Any]]]:
        if not isinstance(value, list):
            return []
        return [
            (index, row)
            for index, row in enumerate(value)
            if isinstance(row, dict)
        ]

    @staticmethod
    def _field_order(rows: list[dict[str, Any]]) -> list[str]:
        fields: list[str] = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(str(key))
        return fields

    @staticmethod
    def _group_herb_slack_rows(
        rows: list[tuple[int, dict[str, Any]]],
    ) -> dict[str, list[tuple[int, dict[str, Any]]]]:
        groups: dict[str, list[tuple[int, dict[str, Any]]]] = {}
        for index, row in rows:
            channel = row.get("Channel")
            if isinstance(channel, dict):
                name = str(channel.get("name") or channel.get("channelID") or "unknown")
            else:
                name = "unknown"
            groups.setdefault(name, []).append((index, row))
        return groups

    @staticmethod
    def _split_text(text: str, max_chars: int) -> Iterable[tuple[int, int, str]]:
        if len(text) <= max_chars:
            yield 0, len(text), text
            return

        start = 0
        while start < len(text):
            hard_end = min(len(text), start + max_chars)
            end = hard_end
            if hard_end < len(text):
                paragraph_break = text.rfind("\n\n", start, hard_end)
                line_break = text.rfind("\n", start, hard_end)
                sentence_break = text.rfind(". ", start, hard_end)
                for candidate in (paragraph_break, line_break, sentence_break):
                    if candidate > start + max_chars // 2:
                        end = candidate + (2 if candidate == sentence_break else 0)
                        break
            piece = text[start:end].strip()
            if piece:
                yield start, end, piece
            start = end

    @staticmethod
    def _compact_json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ": "), default=str)

    @staticmethod
    def _pretty_json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)

    def _chunk_parquet(self, file_id: str, path: Path) -> Iterable[ChunkRecord]:
        """Stream parquet rows in batches so we never materialize the full table.

        Files containing image bytes can exceed RAM if read whole. We inspect
        the Arrow schema, omit columns whose type contains binary data, then
        convert the remaining columns one batch at a time.
        """
        import pyarrow as pa
        import pyarrow.parquet as pq

        pf = pq.ParquetFile(path)
        selected_columns: list[str] = []
        omitted_columns: list[str] = []
        for field in pf.schema_arrow:
            if self._arrow_type_contains_binary(field.type, pa):
                omitted_columns.append(field.name)
            else:
                selected_columns.append(field.name)

        if not selected_columns:
            return

        ordinal = 0
        for batch in pf.iter_batches(batch_size=64, columns=selected_columns):
            rows = batch.to_pylist()
            for row in rows:
                clean = self._make_json_safe_for_chunk(row)
                if omitted_columns:
                    clean["_omitted_columns"] = omitted_columns
                    clean["_omitted_reason"] = "binary parquet columns are not embedded in chunk content"
                content = self._cap_chunk_content(
                    json.dumps(clean, ensure_ascii=False, indent=2, default=str)
                )
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

    def _arrow_type_contains_binary(self, dtype: Any, pa: Any) -> bool:
        if pa.types.is_binary(dtype) or pa.types.is_large_binary(dtype) or pa.types.is_fixed_size_binary(dtype):
            return True
        if pa.types.is_list(dtype) or pa.types.is_large_list(dtype) or pa.types.is_fixed_size_list(dtype):
            return self._arrow_type_contains_binary(dtype.value_type, pa)
        if pa.types.is_struct(dtype):
            return any(self._arrow_type_contains_binary(field.type, pa) for field in dtype)
        if pa.types.is_map(dtype):
            return self._arrow_type_contains_binary(dtype.key_type, pa) or self._arrow_type_contains_binary(dtype.item_type, pa)
        return False

    def _make_json_safe_for_chunk(self, value: Any, *, depth: int = 0) -> Any:
        if depth >= 8:
            return "<max depth reached>"
        if isinstance(value, (bytes, bytearray)):
            return f"<{type(value).__name__} {len(value)} bytes>"
        if isinstance(value, str):
            max_chars = self._policy.hard_max_tokens * 4
            if len(value) > max_chars:
                return value[:max_chars] + "...<truncated>"
            return value
        if isinstance(value, dict):
            return {
                str(k): self._make_json_safe_for_chunk(v, depth=depth + 1)
                for k, v in value.items()
            }
        if isinstance(value, (list, tuple)):
            max_items = 50
            out = [
                self._make_json_safe_for_chunk(v, depth=depth + 1)
                for v in value[:max_items]
            ]
            if len(value) > max_items:
                out.append(f"<{len(value) - max_items} items truncated>")
            return out
        return value

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

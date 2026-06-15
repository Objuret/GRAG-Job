"""JSON working-file backed job ledger for indexing.

This is scheduler state, not graph content. The graph stores corpus artefacts;
this file stores which agent calls are unrun/done/failed.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from shared.neo4j_client import Neo4jClient
from shared.utils import iso_utc, utc_now


JobKind = Literal["chunk_extraction", "file_orchestration"]
JobStatus = Literal["unrun", "done", "failed"]


@dataclass(frozen=True)
class JobRecord:
    work_item_id: str
    kind: JobKind
    target_id: str
    file_id: str
    status: JobStatus


def make_work_item_id(kind: JobKind, target_id: str) -> str:
    return f"{kind}:{target_id}"


class WorkList:
    """Persist run scheduling state in ``backend/.work`` instead of Neo4j."""

    _VERSION = 1

    def __init__(self, client: Neo4jClient, path: Path | None = None) -> None:
        self._client = client
        database = getattr(client, "database", getattr(client, "_database", "neo4j"))
        self._path = path or Path(__file__).resolve().parent.parent / ".work" / f"worklist_{database}.json"
        self._lock = asyncio.Lock()

    async def seed_chunk_extraction_items(self, file_id: str) -> int:
        async with self._client.session() as s:
            result = await s.run(
                """
                MATCH (f:File {file_id: $file_id})-[:HAS_CHUNK]->(c:Chunk)
                RETURN c.chunk_id AS cid
                ORDER BY c.ordinal
                """,
                file_id=file_id,
            )
            chunk_ids = [r["cid"] async for r in result]

        if not chunk_ids:
            return 0

        async with self._lock:
            state = self._read_state()
            items = state["items"]
            now = iso_utc(utc_now())
            for cid in chunk_ids:
                work_item_id = make_work_item_id("chunk_extraction", cid)
                items.setdefault(
                    work_item_id,
                    {
                        "work_item_id": work_item_id,
                        "kind": "chunk_extraction",
                        "target_id": cid,
                        "file_id": file_id,
                        "status": "unrun",
                        "created_at": now,
                    },
                )
            self._write_state(state)
        return len(chunk_ids)

    async def seed_file_orchestration_item(self, file_id: str) -> None:
        async with self._lock:
            state = self._read_state()
            work_item_id = make_work_item_id("file_orchestration", file_id)
            state["items"].setdefault(
                work_item_id,
                {
                    "work_item_id": work_item_id,
                    "kind": "file_orchestration",
                    "target_id": file_id,
                    "file_id": file_id,
                    "status": "unrun",
                    "created_at": iso_utc(utc_now()),
                },
            )
            self._write_state(state)

    async def reset_failed_to_unrun(self) -> int:
        async with self._lock:
            state = self._read_state()
            reset_count = 0
            for item in state["items"].values():
                if item.get("status") == "failed":
                    item["status"] = "unrun"
                    item["error_class"] = None
                    item["error_message"] = None
                    item["assigned_at"] = None
                    item["completed_at"] = None
                    reset_count += 1
            if reset_count:
                self._write_state(state)
            return reset_count

    async def pull_unrun_chunk_items(
        self,
        limit: int,
        dataset_id_filter: str | None = None,
        file_id_filter: str | None = None,
    ) -> list[JobRecord]:
        allowed_files = await self._allowed_file_ids(dataset_id_filter, file_id_filter)
        async with self._lock:
            state = self._read_state()
            return self._pull(state, "chunk_extraction", limit, allowed_files)

    async def pull_unrun_file_items_with_chunks_done(
        self,
        limit: int,
        dataset_id_filter: str | None = None,
        file_id_filter: str | None = None,
    ) -> list[JobRecord]:
        allowed_files = await self._allowed_file_ids(dataset_id_filter, file_id_filter)
        async with self._lock:
            state = self._read_state()
            items = state["items"]
            blocked_files = {
                item["file_id"]
                for item in items.values()
                if item.get("kind") == "chunk_extraction"
                and item.get("status") == "unrun"
            }
            records = [
                self._record(item)
                for item in items.values()
                if item.get("kind") == "file_orchestration"
                and item.get("status") == "unrun"
                and item.get("file_id") not in blocked_files
                and (allowed_files is None or item.get("file_id") in allowed_files)
            ]
            records.sort(key=lambda r: r.file_id)
            return records[:limit]

    async def mark_assigned(self, work_item_id: str) -> None:
        await self._update_item(work_item_id, {"assigned_at": iso_utc(utc_now())})

    async def mark_done(
        self,
        work_item_id: str,
        run_id: str,
        in_tokens: int,
        out_tokens: int,
        duration_ms: int,
    ) -> None:
        await self._update_item(
            work_item_id,
            {
                "status": "done",
                "run_id": run_id,
                "completed_at": iso_utc(utc_now()),
                "in_tokens": in_tokens,
                "out_tokens": out_tokens,
                "duration_ms": duration_ms,
                "error_class": None,
                "error_message": None,
            },
        )

    async def mark_failed(
        self,
        work_item_id: str,
        run_id: str,
        error_class: str,
        error_message: str,
        in_tokens: int,
        out_tokens: int,
        duration_ms: int,
    ) -> None:
        await self._update_item(
            work_item_id,
            {
                "status": "failed",
                "run_id": run_id,
                "completed_at": iso_utc(utc_now()),
                "in_tokens": in_tokens,
                "out_tokens": out_tokens,
                "duration_ms": duration_ms,
                "error_class": error_class,
                "error_message": error_message[:5000],
            },
        )

    async def counts_by_status(self) -> dict[str, int]:
        async with self._lock:
            state = self._read_state()
            out: dict[str, int] = {}
            for item in state["items"].values():
                key = f"{item.get('kind')}.{item.get('status')}"
                out[key] = out.get(key, 0) + 1
            return out

    async def _allowed_file_ids(
        self,
        dataset_id_filter: str | None,
        file_id_filter: str | None,
    ) -> set[str] | None:
        if dataset_id_filter is None and file_id_filter is None:
            return None
        async with self._client.session() as s:
            result = await s.run(
                """
                MATCH (f:File)
                WHERE ($file_id IS NULL OR f.file_id = $file_id)
                  AND ($dataset_id IS NULL OR f.dataset_id = $dataset_id)
                RETURN f.file_id AS file_id
                """,
                dataset_id=dataset_id_filter,
                file_id=file_id_filter,
            )
            return {r["file_id"] async for r in result}

    def _pull(
        self,
        state: dict[str, Any],
        kind: JobKind,
        limit: int,
        allowed_files: set[str] | None,
    ) -> list[JobRecord]:
        records = [
            self._record(item)
            for item in state["items"].values()
            if item.get("kind") == kind
            and item.get("status") == "unrun"
            and (allowed_files is None or item.get("file_id") in allowed_files)
        ]
        records.sort(key=lambda r: (r.file_id, r.target_id))
        return records[:limit]

    async def _update_item(self, work_item_id: str, updates: dict[str, Any]) -> None:
        async with self._lock:
            state = self._read_state()
            item = state["items"].get(work_item_id)
            if item is None:
                raise KeyError(f"work item not found in working file: {work_item_id}")
            item.update(updates)
            self._write_state(state)

    @staticmethod
    def _record(item: dict[str, Any]) -> JobRecord:
        return JobRecord(
            work_item_id=str(item["work_item_id"]),
            kind=item["kind"],
            target_id=str(item["target_id"]),
            file_id=str(item["file_id"]),
            status=item["status"],
        )

    def _read_state(self) -> dict[str, Any]:
        if not self._path.exists():
            return {"version": self._VERSION, "items": {}}
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        if raw.get("version") != self._VERSION:
            raise RuntimeError(f"unsupported worklist version in {self._path}")
        raw.setdefault("items", {})
        return raw

    def _write_state(self, state: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        state["version"] = self._VERSION
        # Normalize dataclasses if callers ever pass them through in tests.
        for key, value in list(state["items"].items()):
            if hasattr(value, "__dataclass_fields__"):
                state["items"][key] = asdict(value)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(self._path)

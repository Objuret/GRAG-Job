"""Run repository: start_run / finish_run.

A Run node is created at the start of every invocation. Its run_id stamps every
WorkItem completion that happens during the run. WorkItems persist across runs;
Run nodes do not (but the run_id reference on WorkItems lets you find the most
recent toucher).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from shared.config import REPO_ROOT, Settings
from shared.neo4j_client import Neo4jClient
from shared.utils import iso_utc, stable_short_hash, utc_now


RunStatus = Literal["started", "ok", "aborted"]


@dataclass
class RunSummary:
    chunks_done: int = 0
    chunks_failed: int = 0
    files_done: int = 0
    files_failed: int = 0
    total_in_tokens: int = 0
    total_out_tokens: int = 0
    total_duration_ms: int = 0


def _git_commit() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            cwd=str(REPO_ROOT),
        )
        return out.decode().strip()
    except Exception:
        return ""


def make_run_id(now: datetime | None = None) -> str:
    now = now or utc_now()
    iso = iso_utc(now).replace(":", "-")
    return f"{iso}-{stable_short_hash(iso, 6)}"


class RunRepository:
    def __init__(self, client: Neo4jClient) -> None:
        self._client = client

    async def start_run(self, settings: Settings) -> str:
        run_id = make_run_id()
        async with self._client.session() as s:
            await s.run(
                """
                CREATE (r:Run {
                    run_id: $run_id,
                    status: 'started',
                    started_at: $now,
                    git_commit: $git_commit,
                    agent_model: $agent_model,
                    agent_max_concurrency: $agent_max_concurrency
                })
                """,
                run_id=run_id,
                now=iso_utc(utc_now()),
                git_commit=_git_commit(),
                agent_model=settings.agent_model,
                agent_max_concurrency=settings.agent_max_concurrency,
            )
        return run_id

    async def finish_run(
        self,
        run_id: str,
        status: RunStatus,
        summary: RunSummary,
        abort_reason: str | None = None,
    ) -> None:
        async with self._client.session() as s:
            await s.run(
                """
                MATCH (r:Run {run_id: $run_id})
                SET r.status = $status,
                    r.finished_at = $now,
                    r.abort_reason = $abort_reason,
                    r.chunks_done = $chunks_done,
                    r.chunks_failed = $chunks_failed,
                    r.files_done = $files_done,
                    r.files_failed = $files_failed,
                    r.total_in_tokens = $total_in_tokens,
                    r.total_out_tokens = $total_out_tokens,
                    r.total_duration_ms = $total_duration_ms
                """,
                run_id=run_id,
                status=status,
                now=iso_utc(utc_now()),
                abort_reason=abort_reason or "",
                chunks_done=summary.chunks_done,
                chunks_failed=summary.chunks_failed,
                files_done=summary.files_done,
                files_failed=summary.files_failed,
                total_in_tokens=summary.total_in_tokens,
                total_out_tokens=summary.total_out_tokens,
                total_duration_ms=summary.total_duration_ms,
            )

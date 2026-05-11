"""Non-mutating tags-only model pilot.

Reads chunks from Neo4j, calls the configured OpenAI-compatible LLM endpoint
with the tags-only prompt, validates JSON locally, and writes a Markdown report
under backend/.plan. It does not create WorkItems, Runs, HAS_TAG edges, or
TAGGED edges.

Output shape: 5 cluster keys (``topic``, ``entities``, ``activity``,
``temporal``, ``evidence``) each holding a list of
``{name, weight}`` keywords. The cluster is encoded by the JSON key, not by a
field on the keyword.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from agents.client import AgentClient, AgentConfig, AgentResult  # noqa: E402
from shared.config import Settings  # noqa: E402
from shared.neo4j_client import Neo4jClient  # noqa: E402
from shared.utils import utc_now  # noqa: E402


CLUSTER_ORDER: tuple[str, ...] = (
    "topic",
    "entities",
    "activity",
    "temporal",
    "evidence",
)

DEFAULT_PROMPT = REPO_ROOT / "prompts" / "extract_chunk_tags_only.md"
SNAKE_CASE_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
ID_VALUE_RE = re.compile(r'"(?:eid_[a-fA-F0-9]+|CUST-\d+|[A-Z]{2,}[-_]\d+)"')
ResponseFormat = Literal["json", "structured"]


class Keyword(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    weight: float = Field(ge=0.0, le=1.0)


class TagsOnlyExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_end_offset: int
    empty: bool
    empty_reason: str | None
    topic: list[Keyword]
    entities: list[Keyword]
    activity: list[Keyword]
    temporal: list[Keyword]
    evidence: list[Keyword]


def cluster_items(parsed: TagsOnlyExtraction) -> list[tuple[str, list[Keyword]]]:
    return [(cluster, getattr(parsed, cluster)) for cluster in CLUSTER_ORDER]


def all_keywords(parsed: TagsOnlyExtraction) -> list[tuple[str, Keyword]]:
    return [(cluster, kw) for cluster, kws in cluster_items(parsed) for kw in kws]


def total_keyword_count(parsed: TagsOnlyExtraction) -> int:
    return sum(len(kws) for _, kws in cluster_items(parsed))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a non-mutating tags-only LLM pilot.")
    parser.add_argument("--file-id", default=None, help="Limit sampled chunks to one File.file_id.")
    parser.add_argument("--dataset-id", default=None, help="Limit sampled chunks to one dataset_id.")
    parser.add_argument(
        "--model",
        default=None,
        help="Override LLM_MODEL/AGENT_MODEL for this pilot run.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Number of chunks to sample. Defaults to all chunks for --file-id, "
            "otherwise 50."
        ),
    )
    parser.add_argument("--concurrency", type=int, default=2, help="Concurrent LLM calls.")
    parser.add_argument(
        "--prompt",
        default=str(DEFAULT_PROMPT.relative_to(REPO_ROOT)),
        help="Prompt path, absolute or relative to backend/.",
    )
    parser.add_argument(
        "--response-format",
        choices=("structured", "json"),
        default="structured",
        help="LLM response format. structured uses strict json_schema; json uses JSON mode.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help=(
            "Report path. Defaults to "
            ".plan/tags_only_<response_format>_pilot_<model>_<timestamp>.md."
        ),
    )
    return parser.parse_args()


def resolve_backend_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


async def load_chunks(
    client: Neo4jClient,
    *,
    file_id: str | None,
    dataset_id: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    async with client.session() as session:
        result = await session.run(
            """
            MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
            WHERE ($file_id IS NULL OR f.file_id = $file_id)
              AND ($dataset_id IS NULL OR f.dataset_id = $dataset_id)
              AND coalesce(c.empty, false) = false
            RETURN f.file_id AS file_id,
                   f.dataset_id AS dataset_id,
                   f.rel_path AS rel_path,
                   f.format_family AS format_family,
                   c.chunk_id AS chunk_id,
                   c.kind AS kind,
                   c.ordinal AS ordinal,
                   c.end_offset AS end_offset,
                   c.token_estimate AS token_estimate,
                   size(c.content) AS content_chars,
                   c.content AS content
            ORDER BY f.rel_path, c.ordinal
            LIMIT $limit
            """,
            file_id=file_id,
            dataset_id=dataset_id,
            limit=limit,
        )
        return [dict(record) async for record in result]


def render_user_message(chunk: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"chunk_end_offset: {chunk['end_offset']}",
            "",
            "Chunk content:",
            "```text",
            chunk.get("content") or "",
            "```",
        ]
    )


def render_system_prompt(prompt: str, response_format: ResponseFormat) -> str:
    if response_format == "json":
        return "\n".join(
            [
                prompt.rstrip(),
                "",
                "Return JSON only. Include every schema field, using null where needed.",
            ]
        )
    return prompt


def collect_warnings(
    parsed: TagsOnlyExtraction,
    *,
    chunk_content: str,
) -> list[str]:
    warnings: list[str] = []
    for cluster, kw in all_keywords(parsed):
        if not SNAKE_CASE_RE.fullmatch(kw.name):
            warnings.append(f"{cluster}.{kw.name!r} is not snake_case.")
    if len(ID_VALUE_RE.findall(chunk_content)) >= 3:
        if parsed.empty:
            warnings.append("ID-heavy chunk was marked empty.")
        else:
            has_summary = any(
                kw.name.endswith("_id_list") or kw.name.endswith("_identifier_list")
                for _, kw in all_keywords(parsed)
            )
            if not has_summary:
                warnings.append(
                    "ID-heavy chunk was not summarized with an *_id_list or *_identifier_list keyword."
                )
    descending = []
    for cluster, kws in cluster_items(parsed):
        if any(kws[i].weight < kws[i + 1].weight for i in range(len(kws) - 1)):
            descending.append(cluster)
    if descending:
        warnings.append(
            "Clusters not ordered by descending weight: " + ", ".join(descending) + "."
        )
    return warnings


def offset_error(parsed: TagsOnlyExtraction, *, expected_offset: int) -> str | None:
    if int(parsed.chunk_end_offset) < 0:
        return f"chunk_end_offset is negative: {parsed.chunk_end_offset}"
    if int(parsed.chunk_end_offset) == int(expected_offset):
        return None
    return f"chunk_end_offset mismatch: model={parsed.chunk_end_offset} graph={expected_offset}"


def output_ok(row: dict[str, Any]) -> bool:
    result = row["result"]
    parsed: TagsOnlyExtraction | None = result.parsed
    if result.error_class != "ok" or parsed is None:
        return False
    if row["offset_error"]:
        return False
    if parsed.empty:
        return bool(parsed.empty_reason) and total_keyword_count(parsed) == 0
    return total_keyword_count(parsed) > 0


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    ok = sum(1 for row in rows if row["output_ok"])
    return {
        "ok": ok,
        "failed": len(rows) - ok,
        "provider_errors": sum(
            1 for row in rows if row["result"].error_class not in {"ok", "schema_invalid"}
        ),
        "schema_errors": sum(1 for row in rows if row["result"].error_class == "schema_invalid"),
        "offset_errors": sum(
            1
            for row in rows
            if row["result"].error_class == "ok" and row["offset_error"] is not None
        ),
        "warnings": sum(1 for row in rows if row["warnings"]),
        "empty_outputs": sum(
            1
            for row in rows
            if row["result"].error_class == "ok"
            and row["result"].parsed is not None
            and row["result"].parsed.empty
        ),
        "in_tokens": sum(row["result"].in_tokens for row in rows),
        "out_tokens": sum(row["result"].out_tokens for row in rows),
        "duration_ms": sum(row["result"].duration_ms for row in rows),
    }


async def run_model(
    settings: Settings,
    *,
    prompt: str,
    response_format: ResponseFormat,
    chunks: list[dict[str, Any]],
    concurrency: int,
) -> list[dict[str, Any]]:
    if not settings.agent_api_key.strip():
        raise SystemExit("Missing LLM_API_KEY/AGENT_API_KEY.")

    agent = AgentClient(
        AgentConfig(
            base_url=settings.agent_base_url,
            model=settings.agent_model,
            api_key=settings.agent_api_key,
            timeout_seconds=60,
        )
    )
    sem = asyncio.Semaphore(concurrency)

    async def one(chunk: dict[str, Any]) -> dict[str, Any]:
        async with sem:
            result: AgentResult[TagsOnlyExtraction] = await agent.call(
                system=prompt,
                user=render_user_message(chunk),
                schema=TagsOnlyExtraction,
                response_format=response_format,
                schema_name="tags_only_extraction",
                call_id=chunk["chunk_id"],
            )
            parsed = result.parsed
            offset = (
                offset_error(parsed, expected_offset=int(chunk["end_offset"]))
                if parsed is not None
                else None
            )
            warnings = (
                collect_warnings(parsed, chunk_content=chunk.get("content") or "")
                if parsed is not None
                else []
            )
            row = {
                "chunk": chunk,
                "result": result,
                "offset_error": offset,
                "warnings": warnings,
            }
            row["output_ok"] = output_ok(row)
            return row

    try:
        return await asyncio.gather(*(one(chunk) for chunk in chunks))
    finally:
        await agent.aclose()


def _md(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "_", text.strip())
    return slug.strip("_") or "model"


def normalize_tag_name(name: str) -> str:
    normalized = name.strip().strip("`'\"").lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "tag"


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def render_report(
    *,
    settings: Settings,
    prompt_path: Path,
    response_format: ResponseFormat,
    chunks: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> str:
    now = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    lines: list[str] = [
        f"# Tags-Only Model Pilot - {now}",
        "",
        "Non-mutating pilot. No graph writes, no WorkItem changes, no Run node.",
        "",
        "## Model",
        "",
        f"- Model: `{settings.agent_model}`",
        f"- Prompt: `{_md(_display_path(prompt_path))}`",
        f"- Response format: `{response_format}`",
        "",
        "For model comparison: run this script once per model with the same `--file-id` and prompt.",
    ]

    lines.extend(
        [
            "",
            "## Sample",
            "",
            f"- Chunks: {len(chunks)}",
            "",
            "| Ord | Chunk | File | Tokens | Chars |",
            "|---:|---|---|---:|---:|",
        ]
    )
    for ch in chunks:
        lines.append(
            f"| {ch['ordinal']} | `{ch['chunk_id']}` | `{_md(ch['rel_path'])}` | "
            f"{ch['token_estimate']} | {ch['content_chars']} |"
        )

    lines.extend(["", "## Summary", ""])
    summary = summarize_rows(rows)
    lines.extend(
        [
            f"- OK: {summary['ok']}",
            f"- Failed: {summary['failed']}",
            f"- Provider errors: {summary['provider_errors']}",
            f"- Schema errors: {summary['schema_errors']}",
            f"- Offset errors: {summary['offset_errors']}",
            f"- Warnings: {summary['warnings']}",
            f"- Empty outputs: {summary['empty_outputs']}",
            f"- Tokens in/out: {summary['in_tokens']}/{summary['out_tokens']}",
            f"- Duration ms: {summary['duration_ms']}",
            "",
            "## Results",
            "",
        ]
    )

    for row in rows:
        ch = row["chunk"]
        result = row["result"]
        lines.extend(
            [
                f"### Ord {ch['ordinal']} / `{ch['chunk_id']}`",
                "",
                f"- File: `{ch['rel_path']}`",
                f"- Status: `{result.error_class}`",
                f"- Tokens in/out: {result.in_tokens}/{result.out_tokens}",
                f"- Duration ms: {result.duration_ms}",
            ]
        )
        if result.error_class == "ok" and result.parsed is not None:
            parsed: TagsOnlyExtraction = result.parsed
            lines.append(f"- OK: {row['output_ok']}")
            lines.append(f"- Empty: {parsed.empty}")
            lines.append(f"- Total keywords: {total_keyword_count(parsed)}")
            if row["offset_error"]:
                lines.append(f"- Offset error: {_md(row['offset_error'])}")
            if parsed.empty_reason:
                lines.append(f"- Empty reason: {_md(parsed.empty_reason)}")
            if row["warnings"]:
                lines.append("- Warnings: " + "; ".join(_md(e) for e in row["warnings"]))
            for cluster, kws in cluster_items(parsed):
                if not kws:
                    continue
                lines.append("")
                lines.append(f"**{cluster}**")
                lines.append("")
                lines.append("| Keyword | Weight |")
                lines.append("|---|---:|")
                for kw in kws:
                    lines.append(f"| `{_md(kw.name)}` | {kw.weight:.2f} |")
        else:
            lines.append("")
            lines.append("```text")
            lines.append(result.error_message or "")
            lines.append("```")
            if result.raw_text:
                lines.append("")
                lines.append("Raw model output:")
                lines.append("")
                lines.append("```text")
                lines.append(result.raw_text)
                lines.append("```")
        lines.append("")

    return "\n".join(lines)


async def async_main() -> None:
    args = parse_args()
    settings = Settings()
    if args.model:
        settings.agent_model = args.model
    limit = args.limit
    if limit is None:
        limit = 1_000_000 if args.file_id else 50

    prompt_path = resolve_backend_path(args.prompt)
    response_format: ResponseFormat = args.response_format
    prompt = render_system_prompt(
        prompt_path.read_text(encoding="utf-8"),
        response_format,
    )
    client = Neo4jClient(settings)
    try:
        chunks = await load_chunks(
            client,
            file_id=args.file_id,
            dataset_id=args.dataset_id,
            limit=limit,
        )
    finally:
        await client.close()

    if not chunks:
        raise SystemExit("No chunks matched the sample filter.")

    print(f"[pilot] running {settings.agent_model} on {len(chunks)} chunks")
    rows = await run_model(
        settings,
        prompt=prompt,
        response_format=response_format,
        chunks=chunks,
        concurrency=args.concurrency,
    )

    if args.out:
        out_path = Path(args.out)
    else:
        stamp = utc_now().strftime("%Y%m%d_%H%M%S")
        model_slug = _slug(settings.agent_model)
        out_path = (
            REPO_ROOT
            / ".plan"
            / f"tags_only_{response_format}_pilot_{model_slug}_{stamp}.md"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        render_report(
            settings=settings,
            prompt_path=prompt_path,
            response_format=response_format,
            chunks=chunks,
            rows=rows,
        ),
        encoding="utf-8",
    )
    print(f"[pilot] wrote {out_path}")


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()

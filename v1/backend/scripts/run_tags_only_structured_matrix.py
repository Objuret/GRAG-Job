"""Run the controlled structured tags-only model matrix.

This repeats the ActionGenie tags-only pilot matrix with the same file, chunks,
and model list as the 20260508_152333 review, but uses the current lean prompt
and strict structured output mode. It is non-mutating: no graph writes,
working-file changes, or Run nodes.
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.run_tags_only_pilot import (  # noqa: E402
    DEFAULT_PROMPT,
    TagsOnlyExtraction,
    _md,
    cluster_items,
    load_chunks,
    normalize_tag_name,
    render_report,
    render_system_prompt,
    run_model,
    summarize_rows,
    total_keyword_count,
)
from shared.config import Settings  # noqa: E402
from shared.neo4j_client import Neo4jClient  # noqa: E402
from shared.utils import utc_now  # noqa: E402


FILE_ID = "960f223de786daa74a7d0f70"
REFERENCE_MATRIX = REPO_ROOT / ".plan" / "tags_only_model_matrix_20260508_152333.md"
RESPONSE_FORMAT = "structured"

MODEL_MATRIX: tuple[tuple[str, str], ...] = (
    ("gpt_5_4_nano", "gpt-5.4-nano"),
    ("gpt_5_4_mini", "gpt-5.4-mini"),
    ("gpt_5_mini", "gpt-5-mini"),
    ("gpt_5_4", "gpt-5.4"),
)


def parse_reference_chunk_ids(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    ids: list[str] = []
    in_sample = False
    for line in text.splitlines():
        if line.strip() == "## Sample":
            in_sample = True
            continue
        if in_sample and line.startswith("## ") and line.strip() != "## Sample":
            break
        if not in_sample or not line.startswith("|"):
            continue
        cells = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(cells) < 2 or not cells[0].isdigit():
            continue
        match = re.search(r"`([^`]+)`", cells[1])
        if match:
            ids.append(match.group(1))
    if not ids:
        raise SystemExit(f"No sample chunk ids found in {path}")
    return ids


def render_matrix_report(
    *,
    stamp: str,
    out_dir: Path,
    rows_by_label: dict[str, list[dict[str, Any]]],
    report_paths: dict[str, Path],
) -> str:
    lines: list[str] = [
        f"# Structured Tags-Only Model Matrix - {stamp}",
        "",
        f"Same file_id: `{FILE_ID}`",
        f"Same prompt: `backend/prompts/{DEFAULT_PROMPT.name}`",
        f"Same response format: `{RESPONSE_FORMAT}`",
        f"Per-model output dir: `backend/.plan/{out_dir.name}`",
        "",
        "## Matrix Summary",
        "| Label | Model | Status | OK | Failed | Provider errors | Schema errors | Offset errors | Warnings | Tokens In/Out | Duration ms | Report |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for label, model in MODEL_MATRIX:
        rows = rows_by_label[label]
        summary = summarize_rows(rows)
        status = "ok" if summary["failed"] == 0 else "needs_review"
        report = report_paths[label]
        lines.append(
            f"| `{label}` | `{model}` | {status} | {summary['ok']} | {summary['failed']} | "
            f"{summary['provider_errors']} | {summary['schema_errors']} | "
            f"{summary['offset_errors']} | {summary['warnings']} | "
            f"{summary['in_tokens']}/{summary['out_tokens']} | {summary['duration_ms']} | "
            f"`backend\\.plan\\{out_dir.name}\\{report.name}` |"
        )
    return "\n".join(lines) + "\n"


def render_model_output(row: dict[str, Any]) -> list[str]:
    result = row["result"]
    lines: list[str] = []
    if result.error_class == "ok" and result.parsed is not None:
        parsed: TagsOnlyExtraction = result.parsed
        if total_keyword_count(parsed) == 0:
            if parsed.empty:
                lines.append(f"_No keywords: {_md(parsed.empty_reason)}_")
            else:
                lines.append("_No keywords parsed._")
            return lines
        lines.extend(
            [
                "| Keyword | Cluster | Weight |",
                "|---|---|---:|",
            ]
        )
        seen: set[tuple[str, str]] = set()
        for cluster, kws in cluster_items(parsed):
            for kw in kws:
                normalized = normalize_tag_name(kw.name)
                key = (normalized, cluster)
                if key in seen:
                    continue
                seen.add(key)
                lines.append(f"| `{_md(normalized)}` | `{cluster}` | {kw.weight:.2f} |")
    else:
        lines.append(f"_No keywords parsed: {result.error_class}._")
    return lines


def render_review_report(
    *,
    stamp: str,
    chunks: list[dict[str, Any]],
    rows_by_label: dict[str, list[dict[str, Any]]],
    report_paths: dict[str, Path],
) -> str:
    lines: list[str] = [
        f"# Structured Tags-Only Review - ActionGenie - {stamp}",
    ]
    for index, chunk in enumerate(chunks):
        lines.extend(
            [
                "",
                f"## Chunk {chunk['ordinal']}",
                "",
                "```text",
                chunk.get("content") or "",
                "```",
            ]
        )
        for label, model in MODEL_MATRIX:
            lines.extend(["", f"#### {label} / `{model}`", ""])
            lines.extend(render_model_output(rows_by_label[label][index]))
    return "\n".join(lines) + "\n"


async def async_main() -> None:
    settings = Settings()
    if not settings.agent_api_key.strip():
        raise SystemExit("Missing LLM_API_KEY/AGENT_API_KEY.")

    expected_ids = parse_reference_chunk_ids(REFERENCE_MATRIX)
    prompt_path = DEFAULT_PROMPT
    prompt = render_system_prompt(prompt_path.read_text(encoding="utf-8"), RESPONSE_FORMAT)

    client = Neo4jClient(settings)
    try:
        chunks = await load_chunks(client, file_id=FILE_ID, dataset_id=None, limit=len(expected_ids))
    finally:
        await client.close()

    got_ids = [chunk["chunk_id"] for chunk in chunks]
    if got_ids != expected_ids:
        raise SystemExit(f"Loaded chunk ids do not match reference sample.\nexpected={expected_ids}\ngot={got_ids}")

    stamp = utc_now().strftime("%Y%m%d_%H%M%S")
    out_dir = REPO_ROOT / ".plan" / f"matrix_structured_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)

    rows_by_label: dict[str, list[dict[str, Any]]] = {}
    report_paths: dict[str, Path] = {}
    for label, model in MODEL_MATRIX:
        model_settings = Settings()
        model_settings.agent_model = model
        print(f"[matrix] running {label} / {model} on {len(chunks)} chunks")
        rows = await run_model(
            model_settings,
            prompt=prompt,
            response_format=RESPONSE_FORMAT,
            chunks=chunks,
            concurrency=2,
        )
        rows_by_label[label] = rows
        report_path = out_dir / f"{label}.md"
        report_path.write_text(
            render_report(
                settings=model_settings,
                prompt_path=prompt_path,
                response_format=RESPONSE_FORMAT,
                chunks=chunks,
                rows=rows,
            ),
            encoding="utf-8",
        )
        report_paths[label] = report_path
        print(f"[matrix] wrote {report_path}")

    matrix_path = REPO_ROOT / ".plan" / f"tags_only_structured_model_matrix_{stamp}.md"
    matrix_path.write_text(
        render_matrix_report(
            stamp=stamp,
            out_dir=out_dir,
            rows_by_label=rows_by_label,
            report_paths=report_paths,
        ),
        encoding="utf-8",
    )
    print(f"[matrix] wrote {matrix_path}")

    review_path = REPO_ROOT / ".plan" / f"tags_only_structured_review_ActionGenie_{stamp}.md"
    review_path.write_text(
        render_review_report(
            stamp=stamp,
            chunks=chunks,
            rows_by_label=rows_by_label,
            report_paths=report_paths,
        ),
        encoding="utf-8",
    )
    print(f"[matrix] wrote {review_path}")


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()

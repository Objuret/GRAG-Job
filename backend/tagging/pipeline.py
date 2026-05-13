"""HERB semantic tagging pilot — single-file pipeline.

Stages: select | extract | describe | score | analyze
Run via: python -m backend.tagging <stage>
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import re
import statistics
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from anthropic import AsyncAnthropic
from neo4j import AsyncGraphDatabase
from pydantic import BaseModel, Field, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
load_dotenv(BACKEND_ROOT / ".env", override=True)

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")
# Map common aliases to canonical Anthropic model IDs.
_MODEL_ALIASES = {
    "claude-4-5-haiku": "claude-haiku-4-5",
    "claude-haiku-4.5": "claude-haiku-4-5",
}
ANTHROPIC_MODEL = _MODEL_ALIASES.get(ANTHROPIC_MODEL, ANTHROPIC_MODEL)
PROVIDER_NAME = "anthropic"
NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USER = os.environ["NEO4J_USER"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]
NEO4J_DATABASE = "herb"
DATASET_ID = "Salesforce__HERB"

PILOT_NAME = os.environ.get("PILOT_NAME", "pilot_format_smoke")
RUN_DIR = BACKEND_ROOT / "data" / "tagging_runs" / PILOT_NAME
RUN_DIR.mkdir(parents=True, exist_ok=True)

CONCURRENCY = 4
SAMPLE_SIZE = int(os.environ.get("TAGGING_SAMPLE_SIZE", "14"))
SELECTION_MODE = os.environ.get("TAGGING_SELECTION_MODE", "herb_kind_coverage")
SELECTION_SEED = int(os.environ.get("TAGGING_SELECTION_SEED", "0"))
FACETS = ("topic", "entities", "activity", "temporal", "evidence")
FILLER = {"data", "information", "content", "record", "text", "chunk", "item"}
HERB_KIND_PRIORITY = (
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
    "unanswerable_question_batch",
)

# ---------- Prompts ----------

EXTRACT_PROMPT = """## Description

Describe the chunk's content in 1–3 sentences.

## Five facets

| Facet    | Captures                                                                                    |
|----------|---------------------------------------------------------------------------------------------|
| topic    | Subject matter                                                                              |
| entities | Named people, organisations, products, systems, places                                      |
| activity | Actions, processes, events                                                                  |
| temporal | Dates and time expressions present verbatim in the text                                     |
| evidence | Kind of information: definition, example, metric, argument, procedure, case_study, raw_data |

## Tags

For each sentence or clause, identify concept labels. Keep proper names whole.

## Weights

- **w_chunk** — contextual relevance of this tag to the chunk as a whole (1.00 = the chunk is entirely this concept, 0.01 = marginal)
- **w_facet** — fit of this tag to its facet (1.00 = unambiguous, 0.01 = forced)

A facet may have zero tags. No filler: `data`, `information`, `content`, `record`.
"""

DESCRIBE_PROMPT = (
    "Describe the file's central concerns in 2–3 sentences, "
    "based on the chunk descriptions provided."
)

SCORE_PROMPT = (
    "Score how representative this chunk is of the file "
    "(1.0 = core example, 0.0 = off-topic). "
    "Return w_chunk_file as a float in [0, 1] with 2 decimals."
)

# ---------- JSON schemas (sent as Anthropic forced tool input_schema) ----------

TAG_DEF = {
    "type": "object",
    "required": ["t", "w_chunk", "w_facet"],
    "additionalProperties": False,
    "properties": {
        "t": {"type": "string", "minLength": 1},
        "w_chunk": {"type": "number", "minimum": 0.01, "maximum": 1.0},
        "w_facet": {"type": "number", "minimum": 0.01, "maximum": 1.0},
    },
}

EXTRACT_SCHEMA = {
    "type": "object",
    "required": ["description", "tags"],
    "additionalProperties": False,
    "properties": {
        "description": {"type": "string", "minLength": 1},
        "tags": {
            "type": "object",
            "required": list(FACETS),
            "additionalProperties": False,
            "properties": {f: {"type": "array", "items": TAG_DEF} for f in FACETS},
        },
    },
}

DESCRIBE_SCHEMA = {
    "type": "object",
    "required": ["file_summary"],
    "additionalProperties": False,
    "properties": {"file_summary": {"type": "string", "minLength": 1}},
}

SCORE_SCHEMA = {
    "type": "object",
    "required": ["w_chunk_file"],
    "additionalProperties": False,
    "properties": {"w_chunk_file": {"type": "number", "minimum": 0, "maximum": 1}},
}


# ---------- Pydantic models (post-validation) ----------

class TagOut(BaseModel):
    t: str
    w_chunk: float = Field(ge=0, le=1)
    w_facet: float = Field(ge=0, le=1)


class FacetsOut(BaseModel):
    topic: list[TagOut] = []
    entities: list[TagOut] = []
    activity: list[TagOut] = []
    temporal: list[TagOut] = []
    evidence: list[TagOut] = []


class ExtractOut(BaseModel):
    description: str
    tags: FacetsOut


class DescribeOut(BaseModel):
    file_summary: str


class ScoreOut(BaseModel):
    w_chunk_file: float = Field(ge=0, le=1)


# ---------- Utilities ----------

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_jsonl(path: Path, obj: dict) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


def read_run_json() -> dict:
    p = RUN_DIR / "run.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def write_run_json(data: dict) -> None:
    (RUN_DIR / "run.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def clean_tag_name(raw: str) -> str:
    s = raw.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    return s


def parse_locator_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return obj if isinstance(obj, dict) else {}


def enrich_chunk_row(row: dict[str, Any]) -> dict[str, Any]:
    loc = parse_locator_json(row.get("locator_json"))
    out = dict(row)
    out["locator"] = loc
    out["chunk_ref"] = loc.get("chunk_ref") or row.get("chunk_id")
    out["parent_ref"] = loc.get("parent_ref") or ""
    return out


def _header_value(content: str, name: str) -> str:
    prefix = f"{name}: "
    for line in content.splitlines()[:30]:
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return ""


def _after_marker(content: str, marker: str) -> str:
    before, sep, after = content.partition(marker)
    if not sep:
        return ""
    return after.strip()


def _record_payload(content: str) -> str:
    for marker in ("Records:\n", "Record:\n"):
        body = _after_marker(content, marker)
        if body:
            return body
    return content.strip()


def _clean_fields(fields: str) -> str:
    return ", ".join(
        field.strip()
        for field in fields.split(",")
        if field.strip() and field.strip() != "_key"
    )


def _clean_json_line_records(text: str, *, drop_keys: set[str] | None = None) -> str:
    drop_keys = drop_keys or set()
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            lines.append(stripped)
            continue
        if isinstance(parsed, dict):
            for key in drop_keys:
                parsed.pop(key, None)
            lines.append(json.dumps(parsed, ensure_ascii=False, separators=(",", ": ")))
        else:
            lines.append(stripped)
    return "\n".join(lines)


def _product_profile_payload(content: str) -> str:
    start = content.find("{")
    if start < 0:
        return content.strip()
    raw = content[start:].strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    profile = {
        "product": parsed.get("product"),
        "team_employee_count": len(parsed.get("team_employee_ids") or []),
        "customer_count": len(parsed.get("customer_ids") or []),
        "section_counts": parsed.get("section_counts") or {},
    }
    return json.dumps(profile, ensure_ascii=False, indent=2)


def _text_payload(content: str) -> tuple[str, str, str]:
    metadata = _after_marker(content, "Metadata:\n")
    if "\n\nField:" in metadata:
        metadata = metadata.split("\n\nField:", 1)[0].strip()
    field = _header_value(content, "Field")
    if "---" not in content:
        return metadata, field, content.strip()
    parts = content.split("---")
    text = parts[1].strip() if len(parts) >= 3 else parts[-1].strip()
    return metadata, field, text


def _source_label(row: dict[str, Any]) -> str:
    loc = row.get("locator") or {}
    product = loc.get("product")
    metadata = loc.get("metadata")
    if product:
        return str(product)
    if metadata:
        return str(metadata)
    return "HERB source"


def render_chunk_user_message(row: dict[str, Any]) -> str:
    kind = str(row.get("kind") or "")
    content = row.get("content") or ""
    fields = _header_value(content, "Fields")
    source = _source_label(row)

    if kind == "directory_batch":
        table = _clean_json_line_records(_record_payload(content), drop_keys={"_key"})
        label = "personnel directory table" if "employee" in source else "customer directory table"
        return "\n".join([
            f"Source: {label}",
            f"Headers: {_clean_fields(fields)}",
            "",
            "Rows:",
            table,
        ])

    if kind == "org_tree":
        return "\n".join([
            "Source: organization hierarchy record",
            f"Headers: {fields}",
            "",
            "Hierarchy data:",
            _record_payload(content),
        ])

    if kind == "product_profile":
        product = (row.get("locator") or {}).get("product") or _header_value(content, "Product")
        return "\n".join([
            f"Source: product profile for {product}",
            "Use the product name, membership counts, and available section counts.",
            "",
            "Profile data:",
            _product_profile_payload(content),
        ])

    if kind in {"document", "document_part"}:
        metadata, field, text = _text_payload(content)
        source_name = "product document excerpt" if kind.endswith("_part") else "product document"
        return "\n".join([
            f"Source: {source_name} from {source}",
            "Metadata:",
            metadata,
            "",
            f"Text field: {field or 'content'}",
            "---",
            text,
            "---",
        ])

    if kind in {"meeting_transcript", "meeting_transcript_part"}:
        metadata, field, text = _text_payload(content)
        source_name = "meeting transcript excerpt" if kind.endswith("_part") else "meeting transcript"
        return "\n".join([
            f"Source: {source_name} for {source}",
            "Metadata:",
            metadata,
            "",
            f"Transcript field: {field or 'transcript'}",
            "---",
            text,
            "---",
        ])

    if kind in {"slack_thread_batch", "meeting_chat_batch"}:
        return "\n".join([
            f"Source: conversation messages from {source}",
            "Use message text, participants, timestamps, links, decisions, and requests.",
            "",
            "Messages:",
            _record_payload(content),
        ])

    if kind == "url_batch":
        return "\n".join([
            f"Source: URL/reference list from {source}",
            f"Headers: {fields}",
            "",
            "References:",
            _record_payload(content),
        ])

    if kind == "pr_batch":
        return "\n".join([
            f"Source: pull request records from {source}",
            "Use titles, summaries, status, review comments, authors, dates, and links.",
            "",
            "Pull requests:",
            _record_payload(content),
        ])

    if kind == "qa_record":
        return "\n".join([
            f"Source: answerable question record from {source}",
            "Use the question as the retrieval intent and the answer/citations as evidence.",
            "",
            "Question record:",
            _record_payload(content),
        ])

    if kind == "qa_record_part":
        question_answer = _after_marker(content, "Question and answer:\n")
        citations = ""
        if "\n\nCitations:\n" in question_answer:
            question_answer, citations = question_answer.split("\n\nCitations:\n", 1)
        return "\n".join([
            f"Source: citation evidence for an answerable question from {source}",
            "Use the question/answer as context and the citations as supporting evidence.",
            "",
            "Question and answer:",
            question_answer.strip(),
            "",
            "Citations:",
            citations.strip(),
        ])

    if kind == "unanswerable_question_batch":
        return "\n".join([
            f"Source: unanswerable question batch from {source}",
            "Use the questions as missing-information intents. Do not infer answers.",
            "",
            "Questions:",
            _record_payload(content),
        ])

    return "\n".join([
        f"Source: {_source_label(row)}",
        "",
        "Evidence:",
        content.strip(),
    ])


def _kind_order(kind: str) -> tuple[int, str]:
    try:
        return (HERB_KIND_PRIORITY.index(kind), kind)
    except ValueError:
        return (len(HERB_KIND_PRIORITY), kind)


def choose_chunks(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if SELECTION_MODE == "all":
        return sorted(rows, key=lambda r: (r["rel_path"], r["ordinal"], r["chunk_id"]))

    if SELECTION_MODE == "random":
        # Kept only as an explicit escape hatch. The default is coverage of the
        # HERB chunk kinds so pilot runs test the new chunk format.
        ordered = sorted(rows, key=lambda r: r["chunk_id"])
        random.Random(SELECTION_SEED).shuffle(ordered)
        return ordered[:limit]

    by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_kind[str(row.get("kind") or "")].append(row)

    picks: list[dict[str, Any]] = []
    picked_ids: set[str] = set()
    for kind in sorted(by_kind, key=_kind_order):
        candidates = by_kind[kind]
        med = statistics.median([int(r.get("token_estimate") or 0) for r in candidates])
        chosen = sorted(
            candidates,
            key=lambda r: (
                abs(int(r.get("token_estimate") or 0) - med),
                r["rel_path"],
                int(r["ordinal"]),
                r["chunk_id"],
            ),
        )[0]
        picks.append(chosen)
        picked_ids.add(chosen["chunk_id"])
        if len(picks) >= limit:
            return picks

    if len(picks) < limit:
        remaining = [
            r for r in rows
            if r["chunk_id"] not in picked_ids
        ]
        remaining.sort(key=lambda r: (r["rel_path"], int(r["ordinal"]), r["chunk_id"]))
        picks.extend(remaining[: limit - len(picks)])
    return picks


# ---------- Anthropic client ----------

class ClaudeCaller:
    """Anthropic Messages API wrapper using forced tool_use for structured output."""

    def __init__(self) -> None:
        self.client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        self.sem = asyncio.Semaphore(CONCURRENCY)

    async def _raw_call(self, *, system: str, user: str, schema: dict, schema_name: str) -> Any:
        return await self.client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
            tools=[{
                "name": schema_name,
                "description": "Return the structured result for this task.",
                "input_schema": schema,
            }],
            tool_choice={"type": "tool", "name": schema_name},
            temperature=0.3,
        )

    async def call(
        self,
        *,
        system: str,
        user: str,
        schema: dict,
        schema_name: str,
        stage: str,
        target_id: str,
        io_path: Path,
        err_path: Path,
    ) -> tuple[dict | None, dict]:
        """Returns (parsed_json_or_None, record_for_jsonl)."""
        async with self.sem:
            t0 = time.perf_counter()
            last_err: str | None = None
            for attempt in (1, 2):
                try:
                    resp = await self._raw_call(
                        system=system, user=user, schema=schema, schema_name=schema_name,
                    )
                    ms = int((time.perf_counter() - t0) * 1000)
                    parsed: dict | None = None
                    reasoning: str | None = None
                    text_parts: list[str] = []
                    for block in resp.content:
                        bt = getattr(block, "type", None)
                        if bt == "tool_use" and getattr(block, "name", None) == schema_name:
                            parsed = dict(block.input)
                        elif bt == "thinking":
                            reasoning = getattr(block, "thinking", None)
                        elif bt == "text":
                            text_parts.append(getattr(block, "text", ""))
                    usage = {
                        "prompt_tokens": resp.usage.input_tokens,
                        "completion_tokens": resp.usage.output_tokens,
                        "total_tokens": resp.usage.input_tokens + resp.usage.output_tokens,
                    }
                    record = {
                        "ts": now_iso(),
                        "stage": stage,
                        "target_id": target_id,
                        "attempt": attempt,
                        "provider": PROVIDER_NAME,
                        "model": ANTHROPIC_MODEL,
                        "request": {"system": system, "user": user},
                        "response_tool_input": parsed,
                        "response_text": "\n".join(text_parts) if text_parts else None,
                        "response_reasoning": reasoning,
                        "stop_reason": getattr(resp, "stop_reason", None),
                        "usage": usage,
                        "duration_ms": ms,
                    }
                    append_jsonl(io_path, record)
                    if parsed is None:
                        last_err = f"no tool_use block named {schema_name}"
                        if attempt == 1:
                            await asyncio.sleep(2)
                            continue
                        append_jsonl(err_path, {"stage": stage, "target_id": target_id, "error": last_err})
                        return None, record
                    return parsed, record
                except Exception as e:
                    last_err = f"{type(e).__name__}: {e}"
                    if attempt == 1:
                        await asyncio.sleep(2)
                        continue
                    ms = int((time.perf_counter() - t0) * 1000)
                    record = {
                        "ts": now_iso(),
                        "stage": stage,
                        "target_id": target_id,
                        "attempt": attempt,
                        "provider": PROVIDER_NAME,
                        "model": ANTHROPIC_MODEL,
                        "request": {"system": system, "user": user},
                        "error": last_err,
                        "duration_ms": ms,
                    }
                    append_jsonl(io_path, record)
                    append_jsonl(err_path, {"stage": stage, "target_id": target_id, "error": last_err})
                    return None, record
            return None, {}


# ---------- Neo4j helpers ----------

def neo4j_driver():
    return AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


async def ensure_tag_uniqueness(driver) -> None:
    async with driver.session(database=NEO4J_DATABASE) as s:
        await s.run("CREATE CONSTRAINT tag_name_unique IF NOT EXISTS FOR (t:Tag) REQUIRE t.name IS UNIQUE")


# ---------- Stage: verify_chunks ----------

async def stage_verify_chunks() -> None:
    """No-API check that the current HERB graph exposes the new chunk format."""
    driver = neo4j_driver()
    try:
        async with driver.session(database=NEO4J_DATABASE) as s:
            result = await s.run(
                """
                MATCH (f:File {dataset_id: $dataset_id})-[:HAS_CHUNK]->(c:Chunk)
                RETURN c.chunk_id AS chunk_id, c.kind AS kind,
                       c.ordinal AS ordinal, c.token_estimate AS token_estimate,
                       c.locator_json AS locator_json, c.content AS content,
                       f.rel_path AS rel_path
                ORDER BY c.kind, f.rel_path, c.ordinal
                """,
                dataset_id=DATASET_ID,
            )
            rows = [enrich_chunk_row(dict(r)) async for r in result]
    finally:
        await driver.close()

    by_kind = Counter(row["kind"] for row in rows)
    missing_ref = [row for row in rows if not row.get("chunk_ref")]
    missing_kind = [row for row in rows if not row.get("kind")]
    missing_ref_in_content = [
        row for row in rows
        if row.get("chunk_ref") and row["chunk_ref"] not in (row.get("content") or "")
    ]
    missing_kind_in_content = [
        row for row in rows
        if row.get("kind") and f"Chunk type: {row['kind']}" not in (row.get("content") or "")
    ]

    print(f"database={NEO4J_DATABASE} dataset={DATASET_ID}")
    print(f"chunks={len(rows)} kinds={len(by_kind)}")
    for kind, count in sorted(by_kind.items(), key=lambda kv: _kind_order(kv[0])):
        print(f"  {kind}: {count}")
    print(f"missing_kind={len(missing_kind)}")
    print(f"missing_chunk_ref={len(missing_ref)}")
    print(f"chunk_ref_not_in_content={len(missing_ref_in_content)}")
    print(f"chunk_type_not_in_content={len(missing_kind_in_content)}")

    offenders = (
        missing_kind[:3]
        + missing_ref[:3]
        + missing_ref_in_content[:3]
        + missing_kind_in_content[:3]
    )
    for row in offenders[:8]:
        print(
            "  offender "
            f"chunk_id={row['chunk_id']} kind={row.get('kind')} ref={row.get('chunk_ref')} "
            f"file={row.get('rel_path')} ordinal={row.get('ordinal')}"
        )

    if missing_kind or missing_ref or missing_ref_in_content or missing_kind_in_content:
        raise RuntimeError("HERB chunk format verification failed.")


# ---------- Stage: select ----------

async def stage_select() -> None:
    driver = neo4j_driver()
    try:
        async with driver.session(database=NEO4J_DATABASE) as s:
            result = await s.run(
                """
                MATCH (f:File {dataset_id: $dataset_id})-[:HAS_CHUNK]->(c:Chunk)
                WHERE c.content IS NOT NULL
                RETURN c.chunk_id AS chunk_id, c.file_id AS file_id,
                       c.ordinal AS ordinal, c.kind AS kind,
                       c.token_estimate AS token_estimate,
                       c.locator_json AS locator_json,
                       f.rel_path AS rel_path
                ORDER BY f.rel_path, c.ordinal
                """,
                dataset_id=DATASET_ID,
            )
            rows = [enrich_chunk_row(dict(r)) async for r in result]
    finally:
        await driver.close()

    picks = choose_chunks(rows, SAMPLE_SIZE)

    run_state = {
        "pilot_name": PILOT_NAME,
        "created_at": now_iso(),
        "model": ANTHROPIC_MODEL,
        "database": NEO4J_DATABASE,
        "dataset_id": DATASET_ID,
        "sample_size": SAMPLE_SIZE,
        "selection_mode": SELECTION_MODE,
        "selection_seed": SELECTION_SEED,
        "concurrency": CONCURRENCY,
        "facets": list(FACETS),
        "chunk_ids": picks,
        "stages_done": [],
    }
    write_run_json(run_state)
    print(
        f"Selected {len(picks)} chunks across {len({p['file_id'] for p in picks})} files "
        f"and {len({p['kind'] for p in picks})} chunk kinds."
    )
    for p in picks:
        print(
            f"  - {p['chunk_id']}  kind={p['kind']:<28} "
            f"ord={p['ordinal']:>4}  ref={p['chunk_ref']}"
        )


# ---------- Stage: extract ----------

async def stage_extract() -> None:
    state = read_run_json()
    if not state.get("chunk_ids"):
        raise RuntimeError("Run `select` first.")
    chunk_ids = [c["chunk_id"] for c in state["chunk_ids"]]

    driver = neo4j_driver()
    try:
        await ensure_tag_uniqueness(driver)
        async with driver.session(database=NEO4J_DATABASE) as s:
            res = await s.run(
                """
                MATCH (c:Chunk) WHERE c.chunk_id IN $ids
                MATCH (f:File {file_id: c.file_id})
                RETURN c.chunk_id AS chunk_id, c.content AS content,
                       c.kind AS kind, c.ordinal AS ordinal,
                       c.token_estimate AS token_estimate,
                       c.locator_json AS locator_json,
                       f.rel_path AS rel_path
                """,
                ids=chunk_ids,
            )
            chunks = {r["chunk_id"]: enrich_chunk_row(dict(r)) async for r in res}

        caller = ClaudeCaller()
        io_path = RUN_DIR / "io.jsonl"
        err_path = RUN_DIR / "errors.jsonl"
        results: dict[str, dict] = {}

        async def one(chunk_id: str, row: dict[str, Any]) -> None:
            parsed, _rec = await caller.call(
                system=EXTRACT_PROMPT, user=render_chunk_user_message(row),
                schema=EXTRACT_SCHEMA, schema_name="chunk_extraction",
                stage="extract", target_id=chunk_id,
                io_path=io_path, err_path=err_path,
            )
            if parsed is None:
                results[chunk_id] = {"ok": False}
                return
            try:
                model = ExtractOut.model_validate(parsed)
            except ValidationError as e:
                append_jsonl(err_path, {"stage": "extract", "target_id": chunk_id, "error": f"pydantic: {e}"})
                results[chunk_id] = {"ok": False}
                return
            results[chunk_id] = {"ok": True, "raw": parsed, "model": model}

        await asyncio.gather(*(one(cid, row) for cid, row in chunks.items()))

        # Clean + write to Neo4j
        async with driver.session(database=NEO4J_DATABASE) as s:
            # Wipe prior HAS_TAG edges for these chunks (re-run safety)
            await s.run(
                "MATCH (c:Chunk)-[r:HAS_TAG]->() WHERE c.chunk_id IN $ids DELETE r",
                ids=chunk_ids,
            )
            for chunk_id, out in results.items():
                if not out.get("ok"):
                    continue
                model: ExtractOut = out["model"]
                # Cleaned tag tuples per facet
                cleaned_edges: list[dict] = []
                for facet in FACETS:
                    facet_tags = getattr(model.tags, facet)
                    # dedupe by cleaned name, keep max w_chunk
                    by_name: dict[str, TagOut] = {}
                    for tg in facet_tags:
                        name = clean_tag_name(tg.t)
                        if not name or name in FILLER:
                            continue
                        prev = by_name.get(name)
                        if prev is None or tg.w_chunk > prev.w_chunk:
                            by_name[name] = TagOut(
                                t=name,
                                w_chunk=round(tg.w_chunk, 2),
                                w_facet=round(tg.w_facet, 2),
                            )
                    for tg in by_name.values():
                        cleaned_edges.append({
                            "name": tg.t,
                            "facet": facet,
                            "w_chunk": tg.w_chunk,
                            "w_facet": tg.w_facet,
                        })

                await s.run(
                    """
                    MATCH (c:Chunk {chunk_id: $chunk_id})
                    SET c.description = $description
                    """,
                    chunk_id=chunk_id, description=model.description,
                )
                if cleaned_edges:
                    await s.run(
                        """
                        MATCH (c:Chunk {chunk_id: $chunk_id})
                        UNWIND $edges AS e
                          MERGE (t:Tag {name: e.name})
                          CREATE (c)-[:HAS_TAG {
                            facet: e.facet,
                            w_chunk: e.w_chunk,
                            w_facet: e.w_facet,
                            run_id: $run_id
                          }]->(t)
                        """,
                        chunk_id=chunk_id, edges=cleaned_edges, run_id=PILOT_NAME,
                    )

        ok = sum(1 for v in results.values() if v.get("ok"))
        print(f"extract: {ok}/{len(chunks)} chunks succeeded")
        state.setdefault("stages_done", [])
        if "extract" not in state["stages_done"]:
            state["stages_done"].append("extract")
        write_run_json(state)
    finally:
        await driver.close()


# ---------- Stage: describe ----------

async def stage_describe() -> None:
    state = read_run_json()
    if "extract" not in state.get("stages_done", []):
        raise RuntimeError("Run `extract` first.")
    chunk_ids = [c["chunk_id"] for c in state["chunk_ids"]]

    driver = neo4j_driver()
    try:
        async with driver.session(database=NEO4J_DATABASE) as s:
            # Group chunk descriptions by file (only chunks we have descriptions for)
            res = await s.run(
                """
                MATCH (c:Chunk) WHERE c.chunk_id IN $ids AND c.description IS NOT NULL
                MATCH (f:File {file_id: c.file_id})
                RETURN f.file_id AS file_id, f.rel_path AS rel_path,
                       c.ordinal AS ordinal, c.kind AS kind,
                       c.locator_json AS locator_json,
                       c.description AS description
                ORDER BY f.file_id, c.ordinal
                """,
                ids=chunk_ids,
            )
            by_file: dict[str, dict] = {}
            async for r in res:
                fid = r["file_id"]
                row = enrich_chunk_row(dict(r))
                by_file.setdefault(fid, {"rel_path": r["rel_path"], "items": []})
                by_file[fid]["items"].append(row)

        caller = ClaudeCaller()
        io_path = RUN_DIR / "io.jsonl"
        err_path = RUN_DIR / "errors.jsonl"
        summaries: dict[str, str] = {}

        async def one(file_id: str, info: dict) -> None:
            items = sorted(info["items"], key=lambda r: int(r["ordinal"]))
            lines = "\n".join(
                f"{i+1}. [{row['kind']} | {row['chunk_ref']}] {row['description']}"
                for i, row in enumerate(items)
            )
            user_msg = f"File: {info['rel_path']}\n\nChunk descriptions (in file order):\n{lines}"
            parsed, _rec = await caller.call(
                system=DESCRIBE_PROMPT, user=user_msg,
                schema=DESCRIBE_SCHEMA, schema_name="file_description",
                stage="describe", target_id=file_id,
                io_path=io_path, err_path=err_path,
            )
            if parsed is None:
                return
            try:
                m = DescribeOut.model_validate(parsed)
                summaries[file_id] = m.file_summary
            except ValidationError as e:
                append_jsonl(err_path, {"stage": "describe", "target_id": file_id, "error": f"pydantic: {e}"})

        await asyncio.gather(*(one(fid, info) for fid, info in by_file.items()))

        async with driver.session(database=NEO4J_DATABASE) as s:
            for fid, summary in summaries.items():
                await s.run(
                    "MATCH (f:File {file_id: $fid}) SET f.description = $d",
                    fid=fid, d=summary,
                )
        print(f"describe: wrote descriptions for {len(summaries)}/{len(by_file)} files")
        if "describe" not in state["stages_done"]:
            state["stages_done"].append("describe")
        write_run_json(state)
    finally:
        await driver.close()


# ---------- Stage: score ----------

async def stage_score() -> None:
    state = read_run_json()
    if "describe" not in state.get("stages_done", []):
        raise RuntimeError("Run `describe` first.")
    chunk_ids = [c["chunk_id"] for c in state["chunk_ids"]]

    driver = neo4j_driver()
    try:
        async with driver.session(database=NEO4J_DATABASE) as s:
            res = await s.run(
                """
                MATCH (c:Chunk) WHERE c.chunk_id IN $ids
                  AND c.description IS NOT NULL
                MATCH (f:File {file_id: c.file_id})
                WHERE f.description IS NOT NULL
                RETURN c.chunk_id AS chunk_id, c.description AS chunk_desc,
                       c.kind AS kind, c.ordinal AS ordinal,
                       c.locator_json AS locator_json,
                       f.rel_path AS rel_path,
                       f.description AS file_summary
                """,
                ids=chunk_ids,
            )
            pairs = [enrich_chunk_row(dict(r)) async for r in res]

        caller = ClaudeCaller()
        io_path = RUN_DIR / "io.jsonl"
        err_path = RUN_DIR / "errors.jsonl"
        scores: dict[str, float] = {}

        async def one(row: dict) -> None:
            user_msg = (
                f"File summary:\n{row['file_summary']}\n\n"
                f"Chunk kind: {row['kind']}\n"
                f"Chunk reference: {row['chunk_ref']}\n"
                f"Parent reference: {row['parent_ref'] or '(none)'}\n\n"
                f"Chunk description:\n{row['chunk_desc']}"
            )
            parsed, _rec = await caller.call(
                system=SCORE_PROMPT, user=user_msg,
                schema=SCORE_SCHEMA, schema_name="chunk_file_score",
                stage="score", target_id=row["chunk_id"],
                io_path=io_path, err_path=err_path,
            )
            if parsed is None:
                return
            try:
                m = ScoreOut.model_validate(parsed)
                scores[row["chunk_id"]] = round(m.w_chunk_file, 2)
            except ValidationError as e:
                append_jsonl(err_path, {"stage": "score", "target_id": row["chunk_id"], "error": f"pydantic: {e}"})

        await asyncio.gather(*(one(p) for p in pairs))

        async with driver.session(database=NEO4J_DATABASE) as s:
            for cid, sc in scores.items():
                await s.run(
                    "MATCH (c:Chunk {chunk_id: $cid}) SET c.relevance_to_file = $s",
                    cid=cid, s=sc,
                )

        print(f"score: wrote w_chunk_file for {len(scores)}/{len(pairs)} chunks")
        if "score" not in state["stages_done"]:
            state["stages_done"].append("score")
        write_run_json(state)
    finally:
        await driver.close()


# ---------- Stage: analyze ----------

def _hist(values: list[float], bins: int = 11) -> list[tuple[str, int]]:
    edges = [i / (bins - 1) for i in range(bins)]
    counts = [0] * (bins - 1)
    for v in values:
        for i in range(bins - 1):
            lo, hi = edges[i], edges[i + 1]
            if (i == bins - 2 and lo <= v <= hi) or (lo <= v < hi):
                counts[i] += 1
                break
    return [
        (f"[{edges[i]:.1f}, {edges[i+1]:.1f}{']' if i == bins-2 else ')'}", counts[i])
        for i in range(bins - 1)
    ]


async def stage_analyze() -> None:
    state = read_run_json()
    if "score" not in state.get("stages_done", []):
        raise RuntimeError("Run `score` first.")
    chunk_ids = [c["chunk_id"] for c in state["chunk_ids"]]

    driver = neo4j_driver()
    try:
        async with driver.session(database=NEO4J_DATABASE) as s:
            res = await s.run(
                """
                MATCH (c:Chunk) WHERE c.chunk_id IN $ids
                OPTIONAL MATCH (f:File {file_id: c.file_id})
                OPTIONAL MATCH (c)-[r:HAS_TAG]->(t:Tag)
                WITH c, f, collect({name: t.name, facet: r.facet, w_chunk: r.w_chunk, w_facet: r.w_facet}) AS edges
                RETURN c.chunk_id AS chunk_id, c.file_id AS file_id, c.ordinal AS ordinal,
                       c.kind AS kind, c.token_estimate AS token_estimate,
                       c.locator_json AS locator_json,
                       c.content AS content, c.description AS description,
                       c.relevance_to_file AS w_chunk_file,
                       f.rel_path AS rel_path, f.description AS file_summary,
                       edges
                ORDER BY c.file_id, c.ordinal
                """,
                ids=chunk_ids,
            )
            rows = [enrich_chunk_row(dict(r)) async for r in res]
    finally:
        await driver.close()

    # Aggregate
    all_w_chunk: list[float] = []
    all_w_facet: list[float] = []
    all_w_chunk_file: list[float] = []
    facet_counts: Counter = Counter()
    facet_chunks_with_tags: dict[str, int] = defaultdict(int)
    tag_freq: Counter = Counter()
    rounded_anchors_w_chunk = Counter()
    rounded_anchors_w_facet = Counter()
    rounded_anchors_w_chunk_file = Counter()

    for row in rows:
        if row["w_chunk_file"] is not None:
            v = row["w_chunk_file"]
            all_w_chunk_file.append(v)
            rounded_anchors_w_chunk_file[round(v, 1)] += 1
        for e in row["edges"] or []:
            if e.get("name") is None:
                continue
            facet_counts[e["facet"]] += 1
            tag_freq[(e["facet"], e["name"])] += 1
            all_w_chunk.append(e["w_chunk"])
            all_w_facet.append(e["w_facet"])
            rounded_anchors_w_chunk[round(e["w_chunk"], 1)] += 1
            rounded_anchors_w_facet[round(e["w_facet"], 1)] += 1
        for facet in FACETS:
            if any(e and e.get("facet") == facet and e.get("name") for e in (row["edges"] or [])):
                facet_chunks_with_tags[facet] += 1

    n_chunks = len(rows)

    def stats_block(name: str, vals: list[float]) -> str:
        if not vals:
            return f"### {name}\n(no values)\n"
        out = [
            f"### {name}",
            f"- n = {len(vals)}",
            f"- min/median/max = {min(vals):.2f} / {statistics.median(vals):.2f} / {max(vals):.2f}",
            f"- mean = {statistics.fmean(vals):.3f}",
            f"- stdev = {statistics.pstdev(vals):.3f}" if len(vals) > 1 else "- stdev = n/a",
            f"- distinct values = {len(set(round(v, 2) for v in vals))}",
            "- histogram (0.1 bins):",
        ]
        for label, c in _hist(vals):
            bar = "#" * c
            out.append(f"    {label:>12} {c:>3} {bar}")
        return "\n".join(out) + "\n"

    md: list[str] = []
    md.append(f"# HERB Tagging Pilot — `{PILOT_NAME}`\n")
    md.append(f"- Generated: {now_iso()}")
    md.append(f"- Model: `{ANTHROPIC_MODEL}`")
    md.append(f"- Database: `{NEO4J_DATABASE}`")
    md.append(f"- Dataset: `{DATASET_ID}`")
    md.append(f"- Selection mode: `{SELECTION_MODE}`")
    md.append(f"- Selection seed: `{SELECTION_SEED}`")
    md.append(f"- Provider: `{PROVIDER_NAME}` (structured output via forced tool_use)")
    md.append(
        f"- Sample: {n_chunks} chunks across {len({r['file_id'] for r in rows})} files "
        f"and {len({r['kind'] for r in rows})} chunk kinds\n"
    )

    md.append("## Caveat")
    md.append("This pilot samples HERB chunks from the current chunk graph. ")
    md.append("File descriptions were generated only from the sampled chunks of each file, ")
    md.append("not from every chunk in the file. The w_chunk_file scores are therefore relative ")
    md.append("to a partial picture of each file. Comparable cross-file scoring requires a full run.\n")

    md.append("## Chunk-format coverage\n")
    kind_counter = Counter(row["kind"] for row in rows)
    for kind, count in sorted(kind_counter.items(), key=lambda kv: _kind_order(kv[0])):
        md.append(f"- `{kind}`: {count}")
    md.append("")

    md.append("## Per-chunk dump\n")
    for row in rows:
        md.append(f"### `{row['chunk_id']}`  (ordinal {row['ordinal']})")
        md.append(f"- file: `{row['rel_path']}`")
        md.append(f"- kind: `{row['kind']}`")
        md.append(f"- chunk_ref: `{row['chunk_ref']}`")
        md.append(f"- parent_ref: `{row['parent_ref'] or ''}`")
        md.append(f"- token_estimate: `{row['token_estimate']}`")
        md.append(f"- w_chunk_file: `{row['w_chunk_file']}`")
        content_preview = (row["content"] or "")[:400].replace("\n", " ")
        md.append(f"- content (first 400 chars): `{content_preview}`")
        md.append(f"- description: {row['description']}")
        edges = [e for e in (row["edges"] or []) if e.get("name")]
        if edges:
            by_facet: dict[str, list[dict]] = defaultdict(list)
            for e in edges:
                by_facet[e["facet"]].append(e)
            md.append("- tags:")
            for facet in FACETS:
                ts = by_facet.get(facet, [])
                if not ts:
                    md.append(f"    - **{facet}**: (none)")
                    continue
                ts_sorted = sorted(ts, key=lambda x: -x["w_chunk"])
                items = ", ".join(f"`{t['name']}` (w_c={t['w_chunk']}, w_f={t['w_facet']})" for t in ts_sorted)
                md.append(f"    - **{facet}**: {items}")
        else:
            md.append("- tags: (none)")
        md.append("")

    md.append("## Per-file dump\n")
    files_seen: dict[str, dict] = {}
    for row in rows:
        if row["file_id"] not in files_seen:
            files_seen[row["file_id"]] = {
                "rel_path": row["rel_path"],
                "file_summary": row["file_summary"],
                "chunks": [],
            }
        files_seen[row["file_id"]]["chunks"].append(row)
    for fid, info in files_seen.items():
        md.append(f"### `{fid}`")
        md.append(f"- rel_path: `{info['rel_path']}`")
        md.append(f"- chunks sampled: {len(info['chunks'])}")
        refs = ", ".join(f"`{row['kind']}:{row['chunk_ref']}`" for row in info["chunks"])
        md.append(f"- sampled refs: {refs}")
        md.append(f"- file description: {info['file_summary']}")
        md.append("")

    md.append("## Tag stats\n")
    md.append(f"- total tag-edges: {sum(facet_counts.values())}")
    md.append(f"- unique tag names (across facets): {len({n for _, n in tag_freq.keys()})}")
    md.append("- edges per facet:")
    for facet in FACETS:
        md.append(f"    - {facet}: {facet_counts.get(facet, 0)} edges, "
                  f"{facet_chunks_with_tags.get(facet, 0)}/{n_chunks} chunks have ≥1 tag")
    md.append("")
    top = tag_freq.most_common(20)
    if top:
        md.append("- top tag occurrences (facet/name → count):")
        for (facet, name), cnt in top:
            md.append(f"    - {facet}/`{name}`: {cnt}")
    md.append("")

    md.append("## Weight distributions\n")
    md.append(stats_block("w_chunk (per-tag centrality)", all_w_chunk))
    md.append(stats_block("w_facet (per-tag facet-fit)", all_w_facet))
    md.append(stats_block("w_chunk_file (per-chunk file representativeness)", all_w_chunk_file))

    md.append("## Round-number anchoring check\n")
    md.append("If the model anchors to round values, you'll see most mass at multiples of 0.1.\n")

    def anchor_table(name: str, counter: Counter, total: int) -> str:
        if total == 0:
            return f"### {name}\n(no data)\n"
        lines = [f"### {name}"]
        for v in sorted(counter):
            cnt = counter[v]
            pct = cnt / total * 100
            bar = "#" * int(pct / 2)
            lines.append(f"- {v:.1f}: {cnt:>3}  ({pct:5.1f}%)  {bar}")
        return "\n".join(lines) + "\n"

    md.append(anchor_table("w_chunk → nearest 0.1", rounded_anchors_w_chunk, sum(rounded_anchors_w_chunk.values())))
    md.append(anchor_table("w_facet → nearest 0.1", rounded_anchors_w_facet, sum(rounded_anchors_w_facet.values())))
    md.append(anchor_table("w_chunk_file → nearest 0.1", rounded_anchors_w_chunk_file, sum(rounded_anchors_w_chunk_file.values())))

    # Cost/perf
    io_path = RUN_DIR / "io.jsonl"
    total_prompt = total_completion = total_ms = 0
    n_calls = 0
    by_stage: Counter = Counter()
    if io_path.exists():
        for line in io_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("usage"):
                total_prompt += rec["usage"].get("prompt_tokens", 0)
                total_completion += rec["usage"].get("completion_tokens", 0)
            total_ms += rec.get("duration_ms", 0) or 0
            n_calls += 1
            by_stage[rec.get("stage", "?")] += 1
    md.append("## Cost / perf\n")
    md.append(f"- total API calls (incl retries): {n_calls}")
    md.append(f"- calls per stage: {dict(by_stage)}")
    md.append(f"- total prompt tokens: {total_prompt}")
    md.append(f"- total completion tokens: {total_completion}")
    md.append(f"- summed duration: {total_ms} ms ({total_ms/1000:.1f} s)")
    md.append("")

    out = "\n".join(md)
    (RUN_DIR / "analysis.md").write_text(out, encoding="utf-8")

    state["analysis"] = {
        "n_chunks": n_chunks,
        "n_files": len(files_seen),
        "chunk_kinds_sampled": dict(kind_counter),
        "tag_edges_total": sum(facet_counts.values()),
        "tag_edges_per_facet": dict(facet_counts),
        "unique_tag_names": len({n for _, n in tag_freq.keys()}),
        "w_chunk_stats": _basic_stats(all_w_chunk),
        "w_facet_stats": _basic_stats(all_w_facet),
        "w_chunk_file_stats": _basic_stats(all_w_chunk_file),
        "round_anchor_pct_w_chunk": _anchor_pct(all_w_chunk),
        "round_anchor_pct_w_facet": _anchor_pct(all_w_facet),
        "round_anchor_pct_w_chunk_file": _anchor_pct(all_w_chunk_file),
    }
    if "analyze" not in state["stages_done"]:
        state["stages_done"].append("analyze")
    write_run_json(state)
    print(f"analyze: wrote {RUN_DIR / 'analysis.md'}")


def _basic_stats(vals: list[float]) -> dict:
    if not vals:
        return {}
    return {
        "n": len(vals),
        "min": min(vals),
        "max": max(vals),
        "mean": statistics.fmean(vals),
        "median": statistics.median(vals),
        "stdev": statistics.pstdev(vals) if len(vals) > 1 else None,
        "distinct_at_2dp": len(set(round(v, 2) for v in vals)),
    }


def _anchor_pct(vals: list[float]) -> float | None:
    """Fraction of values within 0.005 of a multiple of 0.1."""
    if not vals:
        return None
    on_anchor = sum(1 for v in vals if abs(v * 10 - round(v * 10)) < 0.05)
    return on_anchor / len(vals)

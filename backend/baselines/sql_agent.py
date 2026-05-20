"""
Realistic production-style baseline for the graph-RAG thesis: an LLM that
queries the HERB corpus via a SQL tool, the same pattern companies actually
use (e.g. an LLM agent over BigQuery). This is INDEPENDENT of the graph
artefact — no Neo4j, no :Chunk nodes, no tag embeddings — so it's a defensible
thesis comparison point rather than an ablation of the same system.

Flow per question:
  1. Load HERB product JSONs into a local SQLite DB with a relational schema
     (one-time; subsequent runs reuse the .db file).
  2. Hand the LLM the schema + an `execute_sql(query)` tool. The LLM writes
     SQL, sees rows, optionally writes more SQL, then writes a final answer.
  3. The rows the LLM saw become the RAGAS `contexts`/`retrieved_contexts`
     field, so the output JSONL is the same shape your graph runs emit and
     `python -m evaluation.ragas_eval` consumes it unchanged.

Comparison contract (thesis ceiling runs):
  Graph and SQL-agent exports both default to 0 = no limit on retrieval count
  caps (graph: maxChunks/groundingK; SQL: max-tool-calls/rows/cell-chars).
  RAGAS `retrieved_contexts` carries the full evidence each arm returned —
  no hidden post-hoc slice or field truncation unless you set a cap explicitly.
  Tool-call budget 0 still has a hard 200-iteration sanity ceiling in Python.

RAG-safe rule (matches backend/eval/README.md): `answerable_questions`,
`unanswerable_questions`, `team`, and `customers` are NOT loaded into the
SQLite DB — they are the eval/oracle surfaces and must never be retrieved.

Usage:
  pip install openai   # not in requirements.txt; one-off install for this script
  $env:DEEPSEEK_API_KEY = 'sk-...'
  python -m backend.baselines.sql_agent \
      --gold-set frontend/scripts/ragas-questions.herb-gold100.jsonl \
      --out backend/evaluation/sql_agent.jsonl \
      --model deepseek-chat

  # then score:
  python -m evaluation.ragas_eval --input backend/evaluation/sql_agent.jsonl \
      --metrics faithfulness,context_recall,context_precision \
      --report backend/evaluation/sql_agent.report.json
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
HERB_PRODUCTS_DIR = REPO_ROOT / "backend" / "data" / "raw" / "Salesforce__HERB" / "products"
DEFAULT_DB_PATH = REPO_ROOT / "backend" / "data" / "baselines" / "herb.db"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_BASE_URL = "https://api.deepseek.com/v1"

# Defaults: 0 = no limit on that knob (SQL tool-call budget 0 → hard ceiling 200).
MAX_TOOL_CALLS = 0
MAX_ROWS_PER_QUERY = 0
MAX_CELL_CHARS = 0

# RAG-safe surfaces: these are the gold / oracle surfaces and must NOT be
# loaded into the SQLite store, mirroring the graph's exclusion rule.
EXCLUDED_SURFACES = {"answerable_questions", "unanswerable_questions", "team", "customers"}

# ─── SQLite loader ──────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS products (
    name TEXT PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY, product TEXT, type TEXT, author TEXT,
    date TEXT, document_link TEXT, content TEXT
);
CREATE TABLE IF NOT EXISTS meeting_transcripts (
    id TEXT PRIMARY KEY, product TEXT, document_type TEXT, date TEXT,
    participants TEXT,  -- JSON array of employee ids (eids)
    transcript TEXT
);
CREATE TABLE IF NOT EXISTS meeting_chats (
    id TEXT PRIMARY KEY, product TEXT, text TEXT
);
CREATE TABLE IF NOT EXISTS slack_messages (
    id TEXT PRIMARY KEY, product TEXT, channel TEXT, channel_id TEXT,
    user_id TEXT, timestamp TEXT, text TEXT
);
CREATE TABLE IF NOT EXISTS slack_thread_replies (
    message_id TEXT, product TEXT, user_id TEXT, timestamp TEXT, text TEXT
);
CREATE TABLE IF NOT EXISTS prs (
    product TEXT, number TEXT, title TEXT, summary TEXT, link TEXT,
    state TEXT, merged TEXT, mergeable TEXT, user_login TEXT, created_at TEXT,
    PRIMARY KEY (product, number)
);
CREATE TABLE IF NOT EXISTS pr_reviews (
    product TEXT, pr_number TEXT, state TEXT, user_login TEXT,
    comment TEXT, submitted_at TEXT
);
CREATE TABLE IF NOT EXISTS urls (
    id TEXT PRIMARY KEY, product TEXT, link TEXT, description TEXT
);
"""


def _str(v: Any) -> str | None:
    if v is None:
        return None
    return str(v)


def _load_product(con: sqlite3.Connection, product_name: str, data: dict) -> None:
    con.execute("INSERT OR REPLACE INTO products (name) VALUES (?)", (product_name,))
    for doc in data.get("documents") or []:
        con.execute(
            "INSERT OR REPLACE INTO documents VALUES (?,?,?,?,?,?,?)",
            (doc.get("id"), product_name, doc.get("type"), doc.get("author"),
             doc.get("date"), doc.get("document_link"), doc.get("content")),
        )
    for m in data.get("meeting_transcripts") or []:
        con.execute(
            "INSERT OR REPLACE INTO meeting_transcripts VALUES (?,?,?,?,?,?)",
            (m.get("id"), product_name, m.get("document_type"), m.get("date"),
             json.dumps(m.get("participants") or []), m.get("transcript")),
        )
    for c in data.get("meeting_chats") or []:
        con.execute(
            "INSERT OR REPLACE INTO meeting_chats VALUES (?,?,?)",
            (c.get("id"), product_name, c.get("text")),
        )
    for s in data.get("slack") or []:
        msg = s.get("Message") or {}
        user = msg.get("User") or {}
        ch = s.get("Channel") or {}
        con.execute(
            "INSERT OR REPLACE INTO slack_messages VALUES (?,?,?,?,?,?,?)",
            (s.get("id"), product_name, ch.get("name"), ch.get("channelID"),
             user.get("userId"), user.get("timestamp"), user.get("text")),
        )
        for reply in s.get("ThreadReplies") or []:
            ruser = (reply.get("User") or {})
            con.execute(
                "INSERT INTO slack_thread_replies VALUES (?,?,?,?,?)",
                (s.get("id"), product_name, ruser.get("userId"),
                 ruser.get("timestamp"), ruser.get("text")),
            )
    for p in data.get("prs") or []:
        user_login = (p.get("user") or {}).get("login") if isinstance(p.get("user"), dict) else _str(p.get("user"))
        con.execute(
            "INSERT OR REPLACE INTO prs VALUES (?,?,?,?,?,?,?,?,?,?)",
            (product_name, _str(p.get("number")), p.get("title"), p.get("summary"),
             p.get("link"), p.get("state"), _str(p.get("merged")),
             _str(p.get("mergeable")), user_login, p.get("created_at")),
        )
        for rv in p.get("reviews") or []:
            ru = (rv.get("user") or {}).get("login") if isinstance(rv.get("user"), dict) else _str(rv.get("user"))
            con.execute(
                "INSERT INTO pr_reviews VALUES (?,?,?,?,?,?)",
                (product_name, _str(p.get("number")), rv.get("state"), ru,
                 rv.get("comment"), rv.get("submitted_at")),
            )
    for u in data.get("urls") or []:
        con.execute(
            "INSERT OR REPLACE INTO urls VALUES (?,?,?,?)",
            (u.get("id"), product_name, u.get("link"), u.get("description")),
        )


def build_sqlite(db_path: Path, raw_dir: Path = HERB_PRODUCTS_DIR, force: bool = False) -> Path:
    """Build (or rebuild) the HERB SQLite store. Returns the DB path."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists() and not force:
        return db_path
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    try:
        con.executescript(SCHEMA_SQL)
        # Clear tables with no unique key before re-populating.
        con.execute("DELETE FROM slack_thread_replies")
        con.execute("DELETE FROM pr_reviews")
        for p in sorted(raw_dir.glob("*.json")):
            data = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            # Strip excluded surfaces defensively — never load these into SQL.
            for key in EXCLUDED_SURFACES:
                data.pop(key, None)
            _load_product(con, p.stem, data)
        con.commit()
    finally:
        con.close()
    return db_path


# ─── SQL execution tool ─────────────────────────────────────────────────────

def _truncate(s: Any, n: int = MAX_CELL_CHARS) -> str:
    text = "" if s is None else str(s)
    return text if len(text) <= n else text[: n - 3] + "..."


def _format_rows(cursor: sqlite3.Cursor, rows: list[tuple]) -> str:
    if not rows:
        return "(0 rows)"
    cols = [c[0] for c in cursor.description]
    lines = ["\t".join(cols)]
    for r in rows:
        lines.append("\t".join(_truncate(v) for v in r))
    return "\n".join(lines)


@dataclass
class ToolResult:
    text: str        # what the LLM sees
    rows: list[dict] # what we collect as "contexts" for RAGAS


def execute_sql(con: sqlite3.Connection, query: str,
                max_rows: int = MAX_ROWS_PER_QUERY,
                max_cell_chars: int = MAX_CELL_CHARS) -> ToolResult:
    """Run a SELECT-only query against the HERB SQLite store. Other statements
    are refused with a loud error so the agent cannot mutate data.

    Conventions:
      max_rows == 0       → return all rows (no cap).
      max_cell_chars == 0 → no truncation of cell text.
    """
    q = query.strip().rstrip(";").strip()
    head = q.split(None, 1)[0].lower() if q else ""
    if head not in ("select", "with"):
        return ToolResult(
            text=f"ERROR: only SELECT/WITH queries are allowed (got `{head}`).",
            rows=[],
        )
    try:
        cur = con.execute(q)
        if max_rows <= 0:
            rows = cur.fetchall()
            more = False
        else:
            rows = cur.fetchmany(max_rows)
            more = cur.fetchone() is not None
        cols = [c[0] for c in cur.description] if cur.description else []
        row_dicts = [dict(zip(cols, r)) for r in rows]
        def fmt(v: Any) -> str:
            t = "" if v is None else str(v)
            if max_cell_chars <= 0 or len(t) <= max_cell_chars:
                return t
            return t[: max_cell_chars - 3] + "..."
        if rows:
            lines = ["\t".join(cols)]
            for r in rows:
                lines.append("\t".join(fmt(v) for v in r))
            text = "\n".join(lines)
        else:
            text = "(0 rows)"
        if more:
            text += f"\n... (truncated at {max_rows} rows; tighten the query)"
        return ToolResult(text=text, rows=row_dicts)
    except sqlite3.Error as e:
        return ToolResult(text=f"SQL ERROR: {e}", rows=[])


def schema_description(con: sqlite3.Connection) -> str:
    """Introspect the live SQLite schema and return it as a human-readable
    block for the system prompt — that way the prompt cannot lie about the
    schema if it drifts."""
    lines = []
    for (name,) in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ):
        cols = list(con.execute(f"PRAGMA table_info({name})"))
        col_descs = ", ".join(f"{c[1]} {c[2]}" for c in cols)
        (n,) = con.execute(f"SELECT count(*) FROM {name}").fetchone()
        lines.append(f"  {name}({col_descs})  -- {n} rows")
    return "\n".join(lines)


# ─── LLM agent loop ─────────────────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """You are a data analyst answering questions about the HERB corpus.
HERB is a multi-source business dataset with 30 products. Each product has documents,
meeting transcripts/chats, Slack channels, GitHub PRs, and reference URLs.

You have one tool: execute_sql(query) — runs a SELECT query against the HERB SQLite
store and returns {max_rows_hint}. Only SELECT/WITH queries are allowed.

Schema:
{schema}

Notes:
  - `products.name` is the product id (e.g. "ActionGenie"). Every other table has a
    `product` column joining back to it.
  - Employee ids look like "eid_xxxxxxxx". They appear in `documents.author`,
    `slack_messages.user_id`, `slack_thread_replies.user_id`, `prs.user`, and inside
    `meeting_transcripts.participants` (which is a JSON array — use json_each() to
    expand it, e.g. `SELECT j.value FROM meeting_transcripts m, json_each(m.participants) j`).
  - `documents.type` and `meeting_transcripts.document_type` enumerate document classes
    like 'Market Research Report', 'Product Vision Document', etc.
  - Text fields (`documents.content`, `meeting_transcripts.transcript`, `slack_messages.text`)
    are long-form natural language; use LIKE for keyword matching.

Strategy:
  1. Issue 1–{max_calls} SQL queries to find evidence. Start broad, then narrow.
  2. After gathering enough rows, write the final answer. Cite specific values found.
  3. If the evidence does not support a confident answer, say so explicitly.
  4. Never speculate beyond what the rows contain.
"""

TOOLS_SPEC = [{
    "type": "function",
    "function": {
        "name": "execute_sql",
        "description": "Run a SELECT/WITH SQL query against the HERB SQLite database.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "A single SELECT or WITH SQL statement."}
            },
            "required": ["query"],
        },
    },
}]


def tools_spec(max_rows: int) -> list[dict]:
    """OpenAI tool list with a row-cap hint that matches the run configuration."""
    row_hint = "all matching rows (no limit)" if max_rows <= 0 else f"up to {max_rows} rows"
    spec = json.loads(json.dumps(TOOLS_SPEC))  # deep copy
    spec[0]["function"]["description"] = (
        f"Run a SELECT/WITH SQL query against the HERB SQLite database and return {row_hint}."
    )
    return spec


def _chat(base_url: str, api_key: str, model: str, messages: list[dict],
          tools: list[dict] | None = None, temperature: float = 0.0) -> dict:
    """Raw OpenAI-compatible chat completion POST. Returns the parsed response."""
    import httpx
    payload: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"LLM HTTP {resp.status_code}: {resp.text[:500]}")
        return resp.json()


@dataclass
class AgentRun:
    answer: str
    sql_queries: list[str]
    rows_seen: list[dict]
    tokens_in: int
    tokens_out: int
    iterations: int
    elapsed_ms: int
    error: str | None = None


def run_question(
    question: str,
    con: sqlite3.Connection,
    model: str,
    api_key: str,
    base_url: str = DEFAULT_BASE_URL,
    max_calls: int = MAX_TOOL_CALLS,
    max_rows: int = MAX_ROWS_PER_QUERY,
    max_cell_chars: int = MAX_CELL_CHARS,
    temperature: float = 0.0,
) -> AgentRun:
    """One question → one tool-use loop → final answer + collected evidence."""
    t0 = time.time()
    # Absolute sanity ceiling on iterations when caller passes 0 (= no cap).
    # Without it a misbehaving model could loop indefinitely.
    HARD_ITER_CEILING = 200
    effective_max_calls = HARD_ITER_CEILING if max_calls <= 0 else max_calls
    max_rows_hint = "all matching rows (no limit)" if max_rows <= 0 else f"up to {max_rows} rows"
    system = SYSTEM_PROMPT_TEMPLATE.format(
        schema=schema_description(con),
        max_calls=("no limit" if max_calls <= 0 else str(max_calls)),
        max_rows_hint=max_rows_hint,
    )
    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]
    sql_queries: list[str] = []
    rows_seen: list[dict] = []
    tokens_in = tokens_out = 0

    tools = tools_spec(max_rows)

    for it in range(1, effective_max_calls + 1):
        resp = _chat(base_url, api_key, model, messages, tools=tools, temperature=temperature)
        usage = resp.get("usage") or {}
        tokens_in += int(usage.get("prompt_tokens") or 0)
        tokens_out += int(usage.get("completion_tokens") or 0)
        choice = resp["choices"][0]
        msg = choice["message"]
        finish = choice.get("finish_reason")
        tool_calls = msg.get("tool_calls") or []
        # Always append the assistant turn before any tool turns.
        messages.append({k: v for k, v in msg.items() if k in ("role", "content", "tool_calls")})

        if not tool_calls:
            return AgentRun(
                answer=msg.get("content") or "",
                sql_queries=sql_queries,
                rows_seen=rows_seen,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                iterations=it,
                elapsed_ms=int((time.time() - t0) * 1000),
            )

        for tc in tool_calls:
            fn = tc.get("function") or {}
            name = fn.get("name")
            args_raw = fn.get("arguments") or "{}"
            try:
                args = json.loads(args_raw)
            except json.JSONDecodeError:
                args = {}
            if name != "execute_sql":
                tool_text = f"ERROR: unknown tool `{name}`. Only `execute_sql` is available."
            else:
                query = args.get("query") or ""
                sql_queries.append(query)
                result = execute_sql(con, query, max_rows=max_rows, max_cell_chars=max_cell_chars)
                tool_text = result.text
                rows_seen.extend(result.rows)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id"),
                "name": name,
                "content": tool_text,
            })

        if finish == "stop":
            break

    return AgentRun(
        answer="(no answer — tool-call budget exhausted)",
        sql_queries=sql_queries,
        rows_seen=rows_seen,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        iterations=effective_max_calls,
        elapsed_ms=int((time.time() - t0) * 1000),
        error=f"exhausted {effective_max_calls} tool calls without a final answer",
    )


# ─── RAGAS JSONL output ─────────────────────────────────────────────────────

def _row_to_context(row: dict, max_cell_chars: int = 0) -> str:
    """Flatten a row dict to a single context string for RAGAS."""
    def fmt(v: Any) -> str:
        t = "" if v is None else str(v)
        if max_cell_chars <= 0 or len(t) <= max_cell_chars:
            return t
        return t[: max_cell_chars - 3] + "..."
    parts = [f"{k}={fmt(v)}" for k, v in row.items() if v not in (None, "")]
    return " | ".join(parts)


def _question_records(gold_path: Path) -> Iterable[dict]:
    with gold_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            yield json.loads(line)


def run_gold_set(
    gold_path: Path, out_path: Path, model: str, api_key: str,
    base_url: str = DEFAULT_BASE_URL, db_path: Path = DEFAULT_DB_PATH,
    limit: int | None = None, temperature: float = 0.0,
    max_calls: int = MAX_TOOL_CALLS,
    max_rows: int = MAX_ROWS_PER_QUERY,
    max_cell_chars: int = MAX_CELL_CHARS,
) -> None:
    build_sqlite(db_path)  # idempotent — only rebuilds if missing
    out_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    n_ok = n_err = 0
    with out_path.open("w", encoding="utf-8") as out:
        for i, rec in enumerate(_question_records(gold_path)):
            if limit is not None and i >= limit:
                break
            qid = rec.get("id") or f"q_{i}"
            question = rec.get("question") or ""
            reference = rec.get("reference")
            try:
                run = run_question(question, con, model, api_key, base_url,
                                   max_calls=max_calls, max_rows=max_rows,
                                   max_cell_chars=max_cell_chars, temperature=temperature)
            except Exception as e:
                run = AgentRun(answer="", sql_queries=[], rows_seen=[], tokens_in=0,
                               tokens_out=0, iterations=0, elapsed_ms=0, error=str(e))
            contexts = [_row_to_context(r, max_cell_chars) for r in run.rows_seen]
            row = {
                "id": qid,
                "question": question,
                "user_input": question,
                "answer": run.answer,
                "response": run.answer,
                "contexts": contexts,
                "retrieved_contexts": contexts,
                "reference": reference,
                "meta": {
                    "baseline": "sql_agent",
                    "model": model,
                    "max_tool_calls": max_calls,
                    "max_rows_per_query": max_rows,
                    "max_cell_chars": max_cell_chars,
                    "sql_queries": run.sql_queries,
                    "n_rows_seen": len(run.rows_seen),
                    "iterations": run.iterations,
                    "tokens": {"in": run.tokens_in, "out": run.tokens_out},
                    "elapsed_ms": run.elapsed_ms,
                    "error": run.error,
                },
            }
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            if run.error:
                n_err += 1
                print(f"  [{i}] {qid}: ERROR {run.error}", file=sys.stderr)
            else:
                n_ok += 1
                print(f"  [{i}] {qid}: {run.iterations} iters, {len(run.rows_seen)} rows, "
                      f"{run.tokens_in}/{run.tokens_out} tok, {run.elapsed_ms}ms",
                      file=sys.stderr)
    con.close()
    print(f"\nDone: {n_ok} ok, {n_err} errors → {out_path}", file=sys.stderr)


# ─── CLI ────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--gold-set", type=Path, required=True,
                   help="Path to the gold-set JSONL (id/question/reference).")
    p.add_argument("--out", type=Path, required=True,
                   help="Path to write the RAGAS-shaped JSONL.")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"Model id for the OpenAI-compatible API (default: {DEFAULT_MODEL}).")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL,
                   help=f"OpenAI-compatible API base (default: {DEFAULT_BASE_URL}).")
    p.add_argument("--api-key-env", default="DEEPSEEK_API_KEY",
                   help="Env var holding the API key (default: DEEPSEEK_API_KEY).")
    p.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH,
                   help=f"SQLite store path (default: {DEFAULT_DB_PATH}).")
    p.add_argument("--rebuild-db", action="store_true",
                   help="Force re-loading HERB JSONs into SQLite even if the .db exists.")
    p.add_argument("--limit", type=int, default=None,
                   help="Run only the first N gold questions (debugging).")
    p.add_argument("--temperature", type=float, default=0.0,
                   help="LLM sampling temperature (default: 0.0 = deterministic, thesis-reproducible).")
    p.add_argument("--max-tool-calls", type=int, default=MAX_TOOL_CALLS,
                   help=f"Max SQL calls per question (default: {MAX_TOOL_CALLS}; 0 = no cap, hard ceiling 200).")
    p.add_argument("--max-rows-per-query", type=int, default=MAX_ROWS_PER_QUERY,
                   help=f"Max rows returned per SQL call (default: {MAX_ROWS_PER_QUERY}; 0 = fetch all).")
    p.add_argument("--max-cell-chars", type=int, default=MAX_CELL_CHARS,
                   help=f"Max chars per cell before truncation (default: {MAX_CELL_CHARS}; 0 = no truncation).")
    args = p.parse_args(argv)

    if args.rebuild_db:
        build_sqlite(args.db_path, force=True)
        print(f"Rebuilt SQLite store at {args.db_path}", file=sys.stderr)

    api_key = os.environ.get(args.api_key_env, "").strip()
    if not api_key:
        print(f"ERROR: env var {args.api_key_env} is not set.", file=sys.stderr)
        return 2
    if not args.gold_set.exists():
        print(f"ERROR: gold-set not found: {args.gold_set}", file=sys.stderr)
        return 2
    if not HERB_PRODUCTS_DIR.exists():
        print(f"ERROR: HERB raw not found: {HERB_PRODUCTS_DIR}", file=sys.stderr)
        return 2

    run_gold_set(args.gold_set, args.out, args.model, api_key,
                 base_url=args.base_url, db_path=args.db_path, limit=args.limit,
                 temperature=args.temperature, max_calls=args.max_tool_calls,
                 max_rows=args.max_rows_per_query, max_cell_chars=args.max_cell_chars)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Shared RAGAS export I/O — cohort, run_frame, question rows.

Contract: `ragas-export/v1` (mirrors frontend/src/rag/exportContract.ts).
Line 0 of every export JSONL is a `run_frame`; following lines are `kind=question`.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

RAGAS_EXPORT_SCHEMA = "ragas-export/v1"
PERMANENT_SKIP_IDS = ("gold_personalizeforce_34",)
_GOLD_ID = re.compile(r"^gold_([^_]+)_(.+)_(\d+)$")


def parse_gold_id(rid: str) -> dict[str, Any]:
    m = _GOLD_ID.match(rid)
    if not m:
        return {}
    return {"qtype": m.group(1), "product": m.group(2), "item_index": int(m.group(3))}


def is_run_frame(row: dict[str, Any]) -> bool:
    return row.get("kind") == "run_frame"


def is_question_row(row: dict[str, Any]) -> bool:
    return row.get("kind") == "question" or (
        row.get("kind") is None and row.get("id") and row.get("user_input") is not None
    )


def load_gold_questions(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Questions file not found: {path}")
    items: list[dict[str, Any]] = []
    n = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        n += 1
        if line.startswith("{"):
            rec = json.loads(line)
            qid = str(rec.get("id") or f"q{n}")
            question = str(rec.get("question") or rec.get("user_input") or "")
            ref = rec.get("reference") or rec.get("ground_truth")
            row: dict[str, Any] = {"id": qid, "question": question}
            if ref is not None:
                row["reference"] = str(ref)
            items.append(row)
        else:
            items.append({"id": f"q{n}", "question": line})
    return items


def builder_manifest_path(questions_path: Path) -> Path:
    s = str(questions_path)
    if s.endswith(".jsonl"):
        return Path(s[:-6] + ".manifest.json")
    return questions_path.with_suffix(questions_path.suffix + ".manifest.json")


def build_cohort_manifest(source: str | Path, items: list[dict[str, Any]]) -> dict[str, Any]:
    src = str(source)
    sidecar = builder_manifest_path(Path(src))
    return {
        "source": src,
        "count": len(items),
        "builder_manifest": str(sidecar) if sidecar.exists() else None,
        "items": [
            {
                "index": i + 1,
                "id": str(q["id"]),
                "has_reference": bool(str(q.get("reference") or "").strip()),
                **parse_gold_id(str(q["id"])),
            }
            for i, q in enumerate(items)
        ],
    }


def write_run_frame(out_path: Path, frame: dict[str, Any], *, fresh: bool) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(frame, ensure_ascii=False) + "\n"
    if fresh or not out_path.exists():
        out_path.write_text(line, encoding="utf-8")
        return
    first = next((ln for ln in out_path.read_text(encoding="utf-8").splitlines() if ln.strip()), "")
    if first:
        try:
            if is_run_frame(json.loads(first)):
                return
        except json.JSONDecodeError:
            pass
    body = out_path.read_text(encoding="utf-8")
    out_path.write_text(line + body, encoding="utf-8")


def append_question_row(out_path: Path, row: dict[str, Any]) -> None:
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def question_row_shell(
    qid: str,
    question: str,
    reference: str | None,
) -> dict[str, Any]:
    return {
        "kind": "question",
        "id": qid,
        "question": question,
        "user_input": question,
        "reference": reference,
        "answer": "",
        "response": "",
        "contexts": [],
        "retrieved_contexts": [],
        "meta": {},
    }


def iter_export_rows(path: Path) -> Iterable[dict[str, Any]]:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        yield json.loads(line)


def load_question_rows(path: Path) -> list[dict[str, Any]]:
    return [r for r in iter_export_rows(path) if not is_run_frame(r)]

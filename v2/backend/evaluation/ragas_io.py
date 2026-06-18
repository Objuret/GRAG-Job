"""Eval-export JSONL I/O — the shared output contract for all v2 eval arms.

This is an export FORMAT, not a commitment to a scoring method. The field names
happen to be RAGAS-compatible, but which metric reads them (HERB's own per-type
extraction-F1 / LLM-Likert, IR metrics against citations, RAGAS judges, or a mix)
is an open, separate decision — NOT defined here.

One run = one JSONL file:
  line 1            a `run_frame` (kind="run_frame") — full provenance of the run
  lines 2..N        one `question_row` (kind="question_row") per gold question

Both line kinds carry `schema="ragas-export/v1"` so the file is self-describing
and a scorer can separate frame from rows without out-of-band knowledge. The
question rows hold the common q/a/contexts fields (`question`, `reference`,
`answer`/`response`, `contexts`/`retrieved_contexts`) plus a free-form per-arm
`meta` block.

Every arm produces this exact shape; the metrics/scoring step is a separate,
arm-agnostic pass that reads these files — it is NOT defined here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA = "ragas-export/v1"

# Questions excluded from every v2 run, by id. v2 takes no hard filters and
# reads the raw directories, so the v1 abort class (a gold item that died on a
# hard gate) does not recur — there is nothing to permanently skip. Kept as an
# explicit, empty contract so arms and the manifest can reference it uniformly.
PERMANENT_SKIP_IDS: frozenset[str] = frozenset()


def load_gold_questions(gold_path: Path) -> list[dict[str, Any]]:
    """Load a gold-set JSONL into a list of records.

    Blank lines and `#` comment lines are ignored. A malformed JSON line is a
    loud failure (json.JSONDecodeError) — never silently dropped.
    """
    items: list[dict[str, Any]] = []
    with Path(gold_path).open(encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{gold_path}:{n}: malformed gold JSONL line: {e}") from e
    return items


def question_row_shell(qid: str, question: str, reference: Any) -> dict[str, Any]:
    """A well-formed, empty question row. The arm fills answer/response,
    contexts/retrieved_contexts, and meta before it is appended."""
    return {
        "kind": "question_row",
        "schema": SCHEMA,
        "id": qid,
        "question": question,
        "reference": reference,
        "answer": "",
        "response": "",
        "contexts": [],
        "retrieved_contexts": [],
        "meta": {},
    }


def build_cohort_manifest(gold_path: Path, cohort_slice: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe exactly which questions a run covers — its reproducible cohort."""
    return {
        "source": str(gold_path),
        "n_questions": len(cohort_slice),
        "question_ids": [rec.get("id") for rec in cohort_slice],
        "permanent_skip_ids": sorted(PERMANENT_SKIP_IDS),
    }


def write_run_frame(out_path: Path, frame: dict[str, Any], *, fresh: bool = True) -> None:
    """Write the run frame as the first line of the output file. `fresh=True`
    truncates any existing file (one run = one file); `fresh=False` appends,
    for the headless exporter that writes the frame ahead of the rows."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w" if fresh else "a", encoding="utf-8") as f:
        f.write(json.dumps(frame, ensure_ascii=False) + "\n")


def append_question_row(out_path: Path, row: dict[str, Any]) -> None:
    """Append one question row to the run's JSONL file."""
    with Path(out_path).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

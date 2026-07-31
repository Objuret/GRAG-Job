"""questions.py — load the HERB question set from data/questions.jsonl.

Each record: id, question, type, ground_truth, citations. The file is built once
from raw by build_questions.py (HERB ships no question ids).
"""
import json
from pathlib import Path

from contract import QuestionWithTruth

QUESTIONS = Path(__file__).parent / "data" / "questions.jsonl"


def load_questions(path=QUESTIONS):
    """The HERB question set as QuestionWithTruth records."""
    with Path(path).open(encoding="utf-8") as fh:
        return [QuestionWithTruth(**json.loads(line)) for line in fh if line.strip()]

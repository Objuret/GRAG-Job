import json
from pathlib import Path

from harness.contract import QuestionWithTruth

QUESTIONS = Path(__file__).parent.parent.parent / "data" / "questions.jsonl"


def load_questions(path=QUESTIONS):
    with Path(path).open(encoding="utf-8") as fh:
        return [QuestionWithTruth(**json.loads(line)) for line in fh if line.strip()]

"""smoke.py — a tiny wiring check: run a couple of questions through one pipeline
+ evaluator into output/smoke/, to confirm the contract flows end to end before
a real run.

Why it's here and separate: throwaway test runs must not mix with real results.
Not for reported numbers. No logic.
"""


def pick_few_question_ids(n):
    # grab a small fixed subset of ids for a fast check.
    # linked to: orchestrator.load_chosen_questions
    ...


def run_smoke(pipeline, evaluator, n):
    # run orchestrator.run over n questions, writing to output/smoke/.
    # linked to: orchestrator.run (same path, tiny subset + smoke output dir)
    ...

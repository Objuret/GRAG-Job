"""ragas.py — multidimensional answer/evidence quality (the primary lens, and
what transfers to a no-gold set later).

Why it's here: scores faithfulness + answer relevance via a judge, and context
precision/recall DETERMINISTICALLY against the gold citations (no judge). Emits
raw per-question contract.EvalResult (tidy long), nothing pre-aggregated.
No logic.
"""


def score_outputs(outputs, questions):
    # ENTRY: per output compute the metrics -> list[contract.EvalResult].
    # linked to: orchestrator.run_one_evaluator (calls this)
    ...


def faithfulness(answer, contexts):
    # judge: are the answer's claims grounded in the retrieved contexts?
    # reads ArmOutput.contexts. linked to: build_eval_result
    ...


def answer_relevancy(question, answer):
    # judge + embeddings: does the answer address the question? (content only)
    # linked to: build_eval_result
    ...


def context_precision(context_ids, citations):
    # DETERMINISTIC: |retrieved & gold| / |retrieved| (no judge).
    # reads ArmOutput.context_ids + QuestionWithTruth.citations.
    # linked to: build_eval_result
    ...


def context_recall(context_ids, citations):
    # DETERMINISTIC: |retrieved & gold| / |gold| (no judge).
    # reads ArmOutput.context_ids + QuestionWithTruth.citations.
    # linked to: build_eval_result
    ...


def calibrate_judge_vs_human(human_labeled_subset):
    # judge<->human agreement (kappa / corr) on a subset — validates the judged
    # metrics. fills EvalResult.human_label for the calibration items.
    ...


def build_eval_result(question, arm, metric, value, components):
    # assemble one contract.EvalResult. linked to: contract.EvalResult
    ...

"""ragas.py — multidimensional answer/evidence quality (the primary lens, and
what transfers to a no-gold set later).

Why it's here: scores faithfulness + answer relevance via a judge, and context
precision/recall DETERMINISTICALLY against the gold citations (no judge).
Implements contract.EvaluatorInterface. No logic.
"""


def score_outputs(outputs, questions):
    # ENTRY: per output compute the metrics -> Report.
    # linked to: orchestrator.run_one_evaluator; returns contract.Report
    ...


def faithfulness(answer, retrieved_contexts):
    # judge: are the answer's claims grounded in the retrieved contexts?
    # linked to: build_metric_score
    ...


def answer_relevancy(question, answer):
    # judge + embeddings: does the answer address the question? (content only)
    # linked to: build_metric_score
    ...


def context_precision(retrieved_ids, citations):
    # DETERMINISTIC: |retrieved & gold| / |retrieved| (no judge).
    # linked to: PipelineOutput.retrieved_ids + QuestionWithTruth.citations
    ...


def context_recall(retrieved_ids, citations):
    # DETERMINISTIC: |retrieved & gold| / |gold| (no judge).
    # linked to: PipelineOutput.retrieved_ids + QuestionWithTruth.citations
    ...


def calibrate_judge_vs_human(human_labeled_subset):
    # judge<->human agreement (kappa / corr) on a subset — validates the judged
    # metrics. fills MetricScore.human_label for the calibration items.
    ...


def build_metric_score(question, arm, metric, value, components):
    # assemble one contract.MetricScore. linked to: contract.MetricScore
    ...

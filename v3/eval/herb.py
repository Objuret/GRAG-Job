"""herb.py — HERB's own scorer: exact answer correctness, the anchor metric
(leaderboard-comparable).

Why it's here: the authoritative correctness measure for this dataset. Routes by
question type, reads truth from QuestionWithTruth (hydrated from raw).
Implements contract.EvaluatorInterface. No logic.
"""


def score_outputs(outputs, questions):
    # ENTRY: for each output, route by type, produce MetricScore(s) -> Report.
    # linked to: orchestrator.run_one_evaluator (calls this);
    #            returns contract.Report
    ...


def extract_answer_items(answer, qtype):
    # pull eids / urls / prs / companies from the answer text
    #   (regex for eids+urls; a small judge for fuzzy pr/company).
    # linked to: f1_over_sets (feeds it the predicted set)
    ...


def f1_over_sets(predicted, gold):
    # set precision/recall/F1 -> value + components (tp/fp/fn, the two sets).
    # linked to: extract_answer_items (input); build_metric_score (output)
    ...


def judge_content_likert(question, answer):
    # content type: LLM judge 0-100 (HERB's content scoring).
    # linked to: build_metric_score
    ...


def judge_unanswerable_abstention(question, answer):
    # unanswerable: did the answer correctly abstain? (0/1)
    # linked to: build_metric_score
    ...


def build_metric_score(question, arm, metric, value, components):
    # assemble one contract.MetricScore (raw, per question).
    # linked to: contract.MetricScore; called by score_outputs
    ...

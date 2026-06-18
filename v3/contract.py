"""contract.py — the shared shapes + the two interfaces both sides import.

Why it's here: pipelines and evaluators must agree on exactly what a pipeline
emits and what an evaluator returns. This is the single file both depend on.
No logic — just the shapes and the interfaces.
"""
from dataclasses import dataclass
from typing import Protocol


@dataclass
class PromptForPipeline:
    # truth-free view handed to a pipeline: id + question text ONLY.
    # the oracle (answer + citations) is withheld here — this IS the quarantine.
    ...


@dataclass
class QuestionWithTruth:
    # full view handed to an evaluator: id, text, type, answerable,
    # ground_truth, citations — hydrated from raw by the orchestrator.
    ...


@dataclass
class PipelineOutput:
    # what every arm emits per question:
    #   question_id, answer, retrieved_contexts, retrieved_ids, meta
    # answer -> used by HERB + RAGAS; retrieved_contexts/ids -> used by RAGAS.
    ...


@dataclass
class MetricScore:
    # one raw record per (question x metric x arm) — tidy long format:
    #   question_id, type, arm, metric, value, status, components, human_label
    # kept raw so analysis can do paired tests / CIs / per-type splits.
    ...


@dataclass
class RunManifest:
    # provenance for one run: arm, evaluator, generator_model, judge_model,
    # top_k, seed, git_sha, timestamp — for reproducibility.
    ...


@dataclass
class Report:
    # what an evaluator returns: manifest + list[MetricScore]
    # (+ an aggregate that is recomputable from the records).
    ...


class PipelineInterface(Protocol):
    # implemented by every arm in pipelines/; driven by the orchestrator.
    def prepare_over_corpus(self, corpus):
        # build/connect the arm's retrieval once over the corpus
        ...

    def answer_one_question(self, prompt, prepared, generate):
        # -> PipelineOutput. `generate` is the SHARED generator injected by the
        # orchestrator so generation is identical across arms (fairness control).
        ...


class EvaluatorInterface(Protocol):
    # implemented by eval/herb.py and eval/ragas.py; driven by the orchestrator.
    def score_outputs(self, outputs, questions):
        # -> Report (a MetricScore per question/metric)
        ...

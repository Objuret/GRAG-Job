"""contract.py — the shared shapes both sides import."""
from dataclasses import dataclass


@dataclass
class QuestionWithTruth:
    id: str
    question: str
    type: str
    answerable: bool
    ground_truth: list[str]
    citations: list[str]


@dataclass
class ArmOutput:
    answer: str
    contexts: list[str]
    context_ids: list[str]
    search_time_s: float
    model_calls: int
    model_tokens: int
    model_time_s: float


@dataclass
class BuildStats:
    build_time_s: float
    model_calls: int
    model_tokens: int
    model_time_s: float
    models: list[str]


@dataclass
class EvalResult:
    question_id: str
    type: str
    arm: str
    metric: str
    value: float
    status: str
    components: dict
    human_label: str | None


@dataclass
class RunConfig:
    arm: str
    evaluator: str
    generator_model: str
    judge_model: str | None
    top_k: int
    seed: int
    timestamp: str

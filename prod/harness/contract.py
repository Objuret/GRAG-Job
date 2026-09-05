import json
from dataclasses import dataclass, field


GENERATOR_SYSTEM = "Answer the question using only the provided documents. Be concise."


@dataclass
class QuestionWithTruth:
    id: str
    question: str
    type: str
    ground_truth: list[str]
    citations: list[str]


@dataclass
class ModelUsage:
    calls: int = 0
    tokens_in: int = 0
    cached_input_tokens: int = 0
    tokens_out: int = 0
    reasoning_tokens: int = 0
    time_s: float = 0.0
    attempts: int = 0
    request_s: float = 0.0
    wait_s: float = 0.0
    retry_s: float = 0.0

    @property
    def tokens(self) -> int:
        return self.tokens_in + self.tokens_out


def generator_user_content(question: str, contexts: list[str]) -> str:
    ctx = "\n\n".join(contexts)
    return f"Documents:\n{ctx}\n\nQuestion: {question}"


def generator_messages(question: str, contexts: list[str]) -> list[dict]:
    return [
        {"role": "system", "content": GENERATOR_SYSTEM},
        {"role": "user", "content": generator_user_content(question, contexts)},
    ]


def generator_output_text(answer: str) -> str:
    return json.dumps({"answer": answer}, ensure_ascii=False)


def generator_usage_from_nim(usage: dict | None) -> tuple[int, int]:
    u = usage or {}
    tin = int(u.get("prompt_tokens", 0) or 0)
    tout = int(u.get("completion_tokens", 0) or 0)
    if tin or tout:
        return tin, tout
    tot = int(u.get("total_tokens", 0) or 0)
    return tot, 0


def _transport_parts(d: dict) -> dict:
    return {
        "attempts": int(d.get("attempts", 0) or 0),
        "request_s": float(d.get("request_s", 0.0) or 0.0),
        "wait_s": float(d.get("wait_s", 0.0) or 0.0),
        "retry_s": float(d.get("retry_s", 0.0) or 0.0),
    }


def model_usage_from_dict(d: dict) -> ModelUsage:
    if "tokens_in" in d or "tokens_out" in d:
        return ModelUsage(
            calls=int(d.get("calls", 0) or 0),
            tokens_in=int(d.get("tokens_in", 0) or 0),
            cached_input_tokens=int(d.get("cached_input_tokens", 0) or 0),
            tokens_out=int(d.get("tokens_out", 0) or 0),
            reasoning_tokens=int(d.get("reasoning_tokens", 0) or 0),
            time_s=float(d.get("time_s", 0.0) or 0.0),
            **_transport_parts(d),
        )
    tot = int(d.get("tokens", 0) or 0)
    return ModelUsage(
        calls=int(d.get("calls", 0) or 0),
        tokens_in=tot,
        cached_input_tokens=int(d.get("cached_input_tokens", 0) or 0),
        tokens_out=0,
        reasoning_tokens=int(d.get("reasoning_tokens", 0) or 0),
        time_s=float(d.get("time_s", 0.0) or 0.0),
        **_transport_parts(d),
    )


def model_usage_from_telemetry(tel: dict, time_s: float = 0.0) -> ModelUsage:
    if "tokens_in" in tel or "tokens_out" in tel:
        return ModelUsage(
            calls=int(tel.get("calls", 1)),
            tokens_in=int(tel.get("tokens_in", 0) or 0),
            cached_input_tokens=int(tel.get("cached_input_tokens", 0) or 0),
            tokens_out=int(tel.get("tokens_out", 0) or 0),
            reasoning_tokens=int(tel.get("reasoning_tokens", 0) or 0),
            time_s=float(tel.get("time", time_s)),
            **_transport_parts(tel),
        )
    tok = int(tel.get("tokens", 0) or 0)
    return ModelUsage(
        calls=int(tel.get("calls", 1)),
        tokens_in=tok,
        cached_input_tokens=int(tel.get("cached_input_tokens", 0) or 0),
        tokens_out=0,
        reasoning_tokens=int(tel.get("reasoning_tokens", 0) or 0),
        time_s=float(tel.get("time", time_s)),
        **_transport_parts(tel),
    )


def unpack_generation(result, elapsed_s: float) -> tuple[str, ModelUsage]:
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], dict):
        return result[0], model_usage_from_telemetry(result[1], elapsed_s)
    if hasattr(result, "answer"):
        tel = {
            "calls": getattr(result, "calls", 1),
            "tokens_in": getattr(result, "tokens_in", None),
            "tokens_out": getattr(result, "tokens_out", None),
            "tokens": getattr(result, "tokens", 0),
            "time": getattr(result, "time", elapsed_s),
        }
        if tel["tokens_in"] is None and tel["tokens_out"] is None:
            tel.pop("tokens_in", None)
            tel.pop("tokens_out", None)
        else:
            tel["tokens_in"] = int(tel["tokens_in"] or 0)
            tel["tokens_out"] = int(tel["tokens_out"] or 0)
            tel.pop("tokens", None)
        return result.answer, model_usage_from_telemetry(tel, elapsed_s)
    return str(result), ModelUsage(calls=1, time_s=elapsed_s)


def backfill_generator_usage(rec: dict, *, force: bool = False) -> dict:
    gen = dict(rec.get("generator") or {})
    if gen.get("tokens") or gen.get("tokens_in") or gen.get("tokens_out"):
        if not force:
            return gen
        if gen.get("tokens"):
            return gen
    from harness.prompt_tokens import compute_generator_usage

    tin, tout = compute_generator_usage(
        rec.get("question", ""), rec.get("contexts") or [], rec.get("answer", ""))
    gen["tokens_in"] = tin
    gen["tokens_out"] = tout
    return gen


@dataclass
class ArmOutput:
    answer: str
    contexts: list[str]
    context_ids: list[str]
    search_time_s: float
    generator: ModelUsage = field(default_factory=ModelUsage)
    retrieval: ModelUsage = field(default_factory=ModelUsage)
    meta: dict | None = None


@dataclass
class BuildStats:
    build_time_s: float
    model: ModelUsage
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
class RunManifest:
    arm: str
    generator_model: str | None
    interpreter_model: str | None
    top_k: int
    questions_file: str
    n_questions: int
    n_ran: int
    n_failed: int
    timestamp: str
    build_stats: BuildStats
    retrieval_flags: dict | None = None
    char_budget: int | None = None
    code_version: dict | None = None
    environment: dict | None = None
    inputs: dict | None = None
    graph: dict | None = None
    n_exhausted: int | None = None


@dataclass
class EvalManifest:
    scorer: str
    judge_model: str | None
    source_run: str
    arm: str
    timestamp: str
    judge_backend: str | None = None
    judge_effort: str | None = None
    judge_usage: ModelUsage | None = None
    judge_elapsed_s: float | None = None
    judge_legs: list | None = None

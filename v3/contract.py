"""contract.py — the shared shapes every arm and evaluator imports."""
import json
from dataclasses import dataclass, field


GENERATOR_SYSTEM = "Answer the question using only the provided documents. Be concise."


@dataclass
class QuestionWithTruth:
    id: str
    question: str
    type: str  # HERB answer-category (person/content/company/pr/url); "" = unanswerable. a/u also in the id.
    ground_truth: list[str]
    citations: list[str]


@dataclass
class ModelUsage:
    """One model's cost — calls / tokens_in / tokens_out / wall-time. Reused wherever a
    model is touched: the shared generator, an arm's own retrieval model, a build."""
    calls: int = 0
    tokens_in: int = 0
    cached_input_tokens: int = 0
    tokens_out: int = 0
    reasoning_tokens: int = 0
    time_s: float = 0.0

    @property
    def tokens(self) -> int:
        return self.tokens_in + self.tokens_out


def generator_user_content(question: str, contexts: list[str]) -> str:
    ctx = "\n\n".join(contexts)
    return f"Documents:\n{ctx}\n\nQuestion: {question}"


def generator_messages(question: str, contexts: list[str]) -> list[dict]:
    """The exact system + user messages the shared generator sends to NIM."""
    return [
        {"role": "system", "content": GENERATOR_SYSTEM},
        {"role": "user", "content": generator_user_content(question, contexts)},
    ]


def generator_output_text(answer: str) -> str:
    """The structured JSON body the generator returns."""
    return json.dumps({"answer": answer}, ensure_ascii=False)


def generator_usage_from_nim(usage: dict | None) -> tuple[int, int]:
    """tokens_in/tokens_out from a NIM /chat/completions usage block."""
    u = usage or {}
    tin = int(u.get("prompt_tokens", 0) or 0)
    tout = int(u.get("completion_tokens", 0) or 0)
    if tin or tout:
        return tin, tout
    tot = int(u.get("total_tokens", 0) or 0)
    return tot, 0


def model_usage_from_dict(d: dict) -> ModelUsage:
    """Rehydrate ModelUsage from a persisted dict (arm_outputs / run_manifest)."""
    if "tokens_in" in d or "tokens_out" in d:
        return ModelUsage(
            calls=int(d.get("calls", 0) or 0),
            tokens_in=int(d.get("tokens_in", 0) or 0),
            cached_input_tokens=int(d.get("cached_input_tokens", 0) or 0),
            tokens_out=int(d.get("tokens_out", 0) or 0),
            reasoning_tokens=int(d.get("reasoning_tokens", 0) or 0),
            time_s=float(d.get("time_s", 0.0) or 0.0),
        )
    tot = int(d.get("tokens", 0) or 0)
    return ModelUsage(
        calls=int(d.get("calls", 0) or 0),
        tokens_in=tot,
        cached_input_tokens=int(d.get("cached_input_tokens", 0) or 0),
        tokens_out=0,
        reasoning_tokens=int(d.get("reasoning_tokens", 0) or 0),
        time_s=float(d.get("time_s", 0.0) or 0.0),
    )


def model_usage_from_telemetry(tel: dict, time_s: float = 0.0) -> ModelUsage:
    """Build ModelUsage from a generator telemetry dict."""
    if "tokens_in" in tel or "tokens_out" in tel:
        return ModelUsage(
            calls=int(tel.get("calls", 1)),
            tokens_in=int(tel.get("tokens_in", 0) or 0),
            cached_input_tokens=int(tel.get("cached_input_tokens", 0) or 0),
            tokens_out=int(tel.get("tokens_out", 0) or 0),
            reasoning_tokens=int(tel.get("reasoning_tokens", 0) or 0),
            time_s=float(tel.get("time", time_s)),
        )
    tok = int(tel.get("tokens", 0) or 0)
    return ModelUsage(
        calls=int(tel.get("calls", 1)),
        tokens_in=tok,
        cached_input_tokens=int(tel.get("cached_input_tokens", 0) or 0),
        tokens_out=0,
        reasoning_tokens=int(tel.get("reasoning_tokens", 0) or 0),
        time_s=float(tel.get("time", time_s)),
    )


def unpack_generation(result, elapsed_s: float) -> tuple[str, ModelUsage]:
    """Normalise a generator return into (answer, ModelUsage)."""
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
    """Add tokens_in/tokens_out only when generator has no token fields at all.

    Never overwrites or removes an existing `tokens` total — that is the NIM bill
    from the live run and must stay intact."""
    gen = dict(rec.get("generator") or {})
    if gen.get("tokens") or gen.get("tokens_in") or gen.get("tokens_out"):
        if not force:
            return gen
        if gen.get("tokens"):
            return gen  # real NIM total — do not replace with estimates
    from prompt_tokens import compute_generator_usage

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
    search_time_s: float                  # total retrieval wall-time
    generator: ModelUsage = field(default_factory=ModelUsage)  # the shared answer-writer (same role every arm)
    retrieval: ModelUsage = field(default_factory=ModelUsage)  # the arm's OWN model use in retrieval (0 for lucene)
    meta: dict | None = None              # arm-specific retrieval forensics (plan, spheres, ranking depths)


@dataclass
class BuildStats:
    build_time_s: float
    model: ModelUsage                     # the build's model work (e.g. embedding the corpus)
    models: list[str]                     # which model ids the build used


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
    """Provenance for a `questions` run — answers generated by ONE arm."""
    arm: str
    generator_model: str | None  # None on a retrieval-only run (no generation)
    interpreter_model: str | None  # retrieval interpreter, when the arm has one
    top_k: int
    questions_file: str
    n_questions: int                      # chosen for this run
    n_ran: int                            # produced an answer -> arm_outputs.jsonl
    n_failed: int                         # chosen minus answered (n_ran + n_failed == n_questions)
    timestamp: str
    build_stats: BuildStats
    retrieval_flags: dict | None = None   # the arm's env-driven regime switches


@dataclass
class EvalManifest:
    """Provenance for an `evals` run — ONE scorer over one run file."""
    scorer: str
    judge_model: str | None
    source_run: str
    arm: str
    timestamp: str
    judge_backend: str | None = None
    judge_effort: str | None = None
    judge_usage: ModelUsage | None = None
    judge_elapsed_s: float | None = None

"""ragas.py — multidimensional answer/evidence quality via the RAGAS library.

Scores each (arm output, question) on the metrics ragas_catalog.metrics_to_run()
selects: the deterministic backbone (id-based context precision/recall, n-gram and
string scores) plus the judged metrics (faithfulness, answer relevance, the LLM/NV
context metrics, factual correctness, ...). The judge defaults to haiku
(`claude-haiku-4-5`) through the headless Claude CLI; `--judge` (RAGAS_JUDGE_MODEL)
swaps in another Claude (`claude-*`), Codex GPT (`gpt-*`), or Gemini (`gemini-*`);
embedder = llama-nemotron-embed on NIM — the judge and embedder both drive through
their backend-specific wrappers. Emits raw per-question contract.EvalResult (tidy
long), one row per (question, metric); nothing pre-aggregated.

Built on RAGAS's legacy metric classes (ragas.metrics). The newer
ragas.metrics.collections API is an architectural rewrite still missing the id-based
and non-LLM context metrics — the exact, judge-free retrieval scores the gold
citations make possible, which are the headline retrieval signal. Pin ragas==0.4.3
so the legacy implementation is frozen and reproducible.

References (the evaluation library + its metric definitions — the canonical RAGAS
sources; consult these for any RAGAS question, not blogs):
  - Es, S., James, J., Espinosa-Anke, L. & Schockaert, S. (2024). RAGAs: Automated
    Evaluation of Retrieval Augmented Generation. Proc. EACL 2024: System
    Demonstrations, 150-158. doi:10.18653/v1/2024.eacl-demo.16 ; arXiv:2309.15217 —
    the framework and its reference-free faithfulness / answer-relevance /
    context-relevance metrics.
  - Official docs (metric definitions; matches the pinned ragas==0.4.3 behaviour):
    https://docs.ragas.io
      Context Precision — mean of Precision@k over the retrieved list (no separate
      @k cutoff parameter; the list length IS K, so cut the list to score at depth):
      https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/
      Context Recall:
      https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_recall/
  - NVIDIA metrics (AnswerAccuracy / ContextRelevance / ResponseGroundedness), the
    ragas._nv_metrics used here:
      https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/nvidia_metrics/
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import threading
import tempfile
import time
import warnings
from collections import Counter, defaultdict
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

import abort
import nim
from progress import progress
from contract import EvalResult, ModelUsage
from eval.ragas_catalog import CATALOG, metrics_to_run

# The decided eval model stack: haiku through the headless Claude CLI is the default
# judge, llama-nemotron-embed on NIM is the dense embedder. RAGAS_JUDGE_MODEL swaps
# the judge for a run (judge shoot-outs, fast iteration); scores are only comparable
# within one judge.
JUDGE_MODEL = os.environ.get("RAGAS_JUDGE_MODEL", "claude-haiku-4-5")
EMBED_MODEL = "nvidia/llama-nemotron-embed-1b-v2"
_JUDGE_MODEL_LC = JUDGE_MODEL.lower()
JUDGE_BACKEND = "gemini-cli" if "gemini" in _JUDGE_MODEL_LC else (
    "codex-cli" if "gpt-" in _JUDGE_MODEL_LC else (
        "claude-cli" if "claude" in _JUDGE_MODEL_LC else "nim"))
JUDGE_REASONING_EFFORT = (
    os.environ.get("RAGAS_JUDGE_REASONING_EFFORT", "high").strip().lower()
    if JUDGE_BACKEND == "codex-cli" else None)
if JUDGE_BACKEND == "codex-cli" and JUDGE_REASONING_EFFORT not in {"low", "medium", "high", "xhigh"}:
    raise ValueError(
        "RAGAS_JUDGE_REASONING_EFFORT must be one of low, medium, high, xhigh")


def _judge_profile(model: str) -> dict:
    """How to drive this judge — each model family carries its own settings.
    `inflight` is the global concurrent-call cap (the shared pool size: RAGAS fans
    metrics out per item, and every concurrent call occupies one pool thread);
    `timeout_s`/`tries` shape one call. Claude and GPT judges have no queue to
    respect and run wide open (RAM/network are the physical limits — one call per
    verdict). Hosted NIM giants queue for minutes, so a try must outlast the queue
    and bursts must stay shy (the backend 429s them). Small NIM models answer in
    seconds — short fuse, fail fast."""
    model = model.lower()
    if "claude" in model:
        return {"inflight": 64, "timeout_s": 120.0, "tries": 2}
    if "gpt-" in model:
        return {"inflight": 64, "timeout_s": 180.0, "tries": 2}
    if "gemini" in model:
        # Match the other subscription CLI judges: queue every RAGAS cell, with
        # up to 64 real CLI calls in flight. Set RAGAS_JUDGE_INFLIGHT explicitly
        # only when an account's quota returns a rate-limit error.
        return {"inflight": 64, "timeout_s": 180.0, "tries": 2}
    if any(x in model for x in ("397b", "-675b", "340b", "ultra")):
        return {"inflight": 8, "timeout_s": 480.0, "tries": 3}
    return {"inflight": 8, "timeout_s": 90.0, "tries": 3}


_PROFILE = _judge_profile(JUDGE_MODEL)
JUDGE_TIMEOUT_S = max(30.0, float(os.environ.get("RAGAS_JUDGE_TIMEOUT_S", _PROFILE["timeout_s"])))
JUDGE_MAX_TRIES = max(1, int(os.environ.get("RAGAS_JUDGE_MAX_TRIES", _PROFILE["tries"])))
JUDGE_INFLIGHT = max(1, int(os.environ.get("RAGAS_JUDGE_INFLIGHT", _PROFILE["inflight"])))
_CALL_POOL = ThreadPoolExecutor(max_workers=JUDGE_INFLIGHT, thread_name_prefix="judge-call")
EMBED_TIMEOUT_S = float(os.environ.get("RAGAS_EMBED_TIMEOUT_S", "45"))
EMBED_MAX_TRIES = int(os.environ.get("RAGAS_EMBED_MAX_TRIES", "1"))
MAX_JUDGE_CONTEXT_CHARS = int(os.environ.get("RAGAS_MAX_JUDGE_CONTEXT_CHARS", "60000"))
_JUDGE_USAGE_LOCK = threading.Lock()
LAST_JUDGE_USAGE = ModelUsage()
LAST_JUDGE_BACKEND = JUDGE_BACKEND
# The judge model an actual scoring cell invoked. None until a judge cell fires, so a
# retrieval-only or judge-free pass reports no judge model.
LAST_JUDGE_MODEL = None
LAST_JUDGE_REASONING_EFFORT = JUDGE_REASONING_EFFORT
LAST_JUDGE_WALL_TIME_S = 0.0

# Eval circuit breaker: N consecutive questions with most NIM-pass cells errored means
# the judge backend is down — stop loud rather than grind the rest into NaNs; whatever an
# outage touches re-scores on resume. High enough that a short outage passes under it and
# only a sustained one trips. (A judge-side or full outage trips it; an embedder-only
# outage errors just 2 of the 5 cells, so it won't — those NaNs re-score on resume.)
MAX_CONSECUTIVE_FAILED_QUESTIONS = 10

# RAGAS's specific metric classes sit behind a deprecation shim (its public future is
# ragas.metrics.collections, which lacks the id-based retrieval metrics). Silence the
# shim warning; the version is pinned so the legacy path is stable.
warnings.filterwarnings(
    "ignore", message=r"Importing .* from 'ragas\.metrics' is deprecated",
    category=DeprecationWarning)

from langchain_core.outputs import Generation, LLMResult  # noqa: E402
from ragas.dataset_schema import SingleTurnSample  # noqa: E402
from ragas.embeddings.base import BaseRagasEmbeddings  # noqa: E402
from ragas.llms.base import BaseRagasLLM  # noqa: E402
from ragas.run_config import RunConfig  # noqa: E402
from ragas.metrics import (  # noqa: E402
    AnswerCorrectness,
    BleuScore,
    ChrfScore,
    ContextEntityRecall,
    ExactMatch,
    Faithfulness,
    FactualCorrectness,
    IDBasedContextPrecision,
    IDBasedContextRecall,
    LLMContextPrecisionWithoutReference,
    LLMContextPrecisionWithReference,
    LLMContextRecall,
    NonLLMContextPrecisionWithReference,
    NonLLMContextRecall,
    NonLLMStringSimilarity,
    NoiseSensitivity,
    ResponseRelevancy,
    RougeScore,
    SemanticSimilarity,
    StringPresence,
)
from ragas.metrics._nv_metrics import (  # noqa: E402
    AnswerAccuracy,
    ContextRelevance,
    ResponseGroundedness,
)


# --- judge + embedder (RAGAS drivers over backend-specific model calls) -------

_CODEX_EXE = shutil.which("codex")
# npm installs Windows command shims under %APPDATA%\\npm. PowerShell resolves
# that directory through its own command search, while Python's shutil.which can
# miss it when the npm directory is absent from PATH; keep the explicit .cmd
# fallback so `python run.py` invokes the same CLI the user just tested.
_GEMINI_NPM_SHIM = Path(os.environ.get("APPDATA", "")) / "npm" / "gemini.cmd"
_GEMINI_EXE = shutil.which("gemini") or (
    str(_GEMINI_NPM_SHIM) if _GEMINI_NPM_SHIM.is_file() else None)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


@lru_cache(maxsize=16)
def _encoding_for(model: str):
    try:
        import tiktoken
    except Exception:
        return None
    try:
        return tiktoken.encoding_for_model(model)
    except Exception:
        return tiktoken.get_encoding("o200k_base")


def _estimate_tokens(model: str, text: str) -> int:
    enc = _encoding_for(model)
    if enc is None:
        return 0
    return len(enc.encode(text or ""))


def _record_judge_usage(tokens_in: int, tokens_out: int, reasoning_tokens: int,
                        elapsed_s: float, cached_input_tokens: int = 0) -> None:
    with _JUDGE_USAGE_LOCK:
        LAST_JUDGE_USAGE.calls += 1
        LAST_JUDGE_USAGE.tokens_in += int(tokens_in or 0)
        LAST_JUDGE_USAGE.cached_input_tokens += int(cached_input_tokens or 0)
        LAST_JUDGE_USAGE.tokens_out += int(tokens_out or 0)
        LAST_JUDGE_USAGE.reasoning_tokens += int(reasoning_tokens or 0)
        LAST_JUDGE_USAGE.time_s += float(elapsed_s or 0.0)


def _claude_verdict(text: str, model: str, timeout_s: float) -> str:
    """One judge verdict on the shared claude lane (nim._claude_chat — the same
    transport the generator and interpreter ride). max_tries=1: the judge driver
    owns retries. The lane already strips fences; CLI usage counters fill the
    judge accounting, token estimates cover an envelope without them."""
    started = time.perf_counter()
    resp = nim.post("/chat/completions",
                    {"model": model, "messages": [{"role": "user", "content": text}]},
                    timeout=timeout_s, max_tries=1)
    clean = ((resp.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    usage = resp.get("usage") or {}
    _record_judge_usage(
        int(usage.get("prompt_tokens") or 0) or _estimate_tokens(model, text),
        int(usage.get("completion_tokens") or 0) or _estimate_tokens(model, clean),
        0, time.perf_counter() - started)
    return clean


def _codex_usage(jsonl: str) -> dict:
    """The final `turn.completed` event carries Codex CLI's authoritative usage."""
    usage = {}
    for line in jsonl.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "turn.completed":
            usage = event.get("usage") or {}
    return usage


def _codex_verdict(text: str, model: str, timeout_s: float) -> str:
    """Run a subscription-authenticated, isolated `codex exec` verdict.

    Codex emits machine-readable JSONL on stdout; its final event includes real
    token accounting. `--output-last-message` avoids guessing which streamed
    message is the verdict, while `--ephemeral` keeps hundreds of judge calls
    from filling the user's Codex session history.
    """
    if not _CODEX_EXE:
        raise RuntimeError("gpt-* judges need the signed-in `codex` CLI on PATH")
    started = time.perf_counter()
    fd, output_file = tempfile.mkstemp(prefix="ragas-codex-", suffix=".json")
    os.close(fd)
    output_path = Path(output_file)
    command = [
        _CODEX_EXE, "exec", "--ephemeral", "--skip-git-repo-check",
        "--ignore-user-config", "--ignore-rules", "--sandbox", "read-only",
        "--ask-for-approval", "never", "--color", "never", "--json",
        "--output-last-message", str(output_path), "--model", model,
        "--config", f'model_reasoning_effort="{JUDGE_REASONING_EFFORT}"', "-",
    ]
    try:
        run = subprocess.run(
            command, input=text, capture_output=True, text=True,
            timeout=timeout_s, encoding="utf-8", cwd=tempfile.gettempdir())
        if run.returncode != 0:
            raise RuntimeError(
                f"codex judge exit {run.returncode}: {(run.stderr or run.stdout)[:300]}")
        result = output_path.read_text(encoding="utf-8").strip()
        if not result:
            raise RuntimeError("codex judge completed without a final message")
        clean = _FENCE.sub("", result)
        usage = _codex_usage(run.stdout)
        _record_judge_usage(
            int(usage.get("input_tokens", _estimate_tokens(model, text)) or 0),
            int(usage.get("output_tokens", _estimate_tokens(model, clean)) or 0),
            int(usage.get("reasoning_output_tokens", 0) or 0),
            time.perf_counter() - started,
            int(usage.get("cached_input_tokens", 0) or 0),
        )
        return clean
    finally:
        output_path.unlink(missing_ok=True)


def _gemini_usage(stats: object) -> tuple[int, int, int, int]:
    """Extract Gemini CLI's provider token counters from headless JSON stats.

    `--output-format json` returns the CLI's complete session metrics. A
    headless judge call is one fresh session, but sum all model entries so a
    future CLI model alias/route change cannot silently drop usage.
    """
    if not isinstance(stats, dict):
        return 0, 0, 0, 0
    models = stats.get("models")
    if not isinstance(models, dict):
        return 0, 0, 0, 0
    prompt = cached = candidates = thoughts = 0
    for model_stats in models.values():
        if not isinstance(model_stats, dict):
            continue
        tokens = model_stats.get("tokens")
        if not isinstance(tokens, dict):
            continue
        prompt += int(tokens.get("prompt", 0) or 0)
        cached += int(tokens.get("cached", 0) or 0)
        candidates += int(tokens.get("candidates", 0) or 0)
        thoughts += int(tokens.get("thoughts", 0) or 0)
    return prompt, cached, candidates, thoughts


def _run_gemini_cli(command: list[str], text: str, timeout_s: float,
                    env: dict[str, str]) -> subprocess.CompletedProcess:
    """Run one Gemini CLI session and reap its whole process tree on timeout.

    Gemini's Windows launcher can re-exec Node. Killing only Popen's immediate
    process leaves the child holding stdout/stderr open, making `communicate()`
    wait forever after its timeout. A tree kill makes the timeout real.
    """
    kwargs = {
        "stdin": subprocess.PIPE,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "encoding": "utf-8",
        "cwd": tempfile.gettempdir(),
        "env": env,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    process = subprocess.Popen(command, **kwargs)
    try:
        stdout, stderr = process.communicate(input=text, timeout=timeout_s)
    except subprocess.TimeoutExpired as exc:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True, text=True, check=False,
            )
        else:
            process.kill()
        stdout, stderr = process.communicate()
        raise subprocess.TimeoutExpired(
            command, timeout_s, output=stdout, stderr=stderr) from exc
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _gemini_terminal_quota_error(error: Exception) -> bool:
    """A terminal Gemini quota/entitlement rejection cannot improve with a retry."""
    text = str(error).lower()
    return "terminalquotaerror" in text or "daily quota" in text


def _gemini_quota_error_row(row: "EvalResult") -> bool:
    """Whether a cell has Gemini CLI's terminal quota/entitlement rejection."""
    return (
        JUDGE_BACKEND == "gemini-cli"
        and row.status == "error"
        and _gemini_terminal_quota_error(
            RuntimeError(str((row.components or {}).get("error", "")))
        )
    )


def _gemini_verdict(text: str, model: str, timeout_s: float) -> str:
    """One subscription-authenticated Gemini CLI verdict with real CLI usage.

    RAGAS supplies the entire judging prompt on stdin. Gemini CLI appends that
    input to the short headless instruction, so the RAGAS prompt itself remains
    the source of truth for the structured verdict. Each call starts a fresh,
    isolated CLI session; it cannot read or edit the repository.
    """
    if not _GEMINI_EXE:
        raise RuntimeError("gemini-* judges need the signed-in `gemini` CLI on PATH")
    started = time.perf_counter()
    last_error = None
    attempts = 0
    for attempt in range(JUDGE_MAX_TRIES):
        attempts = attempt + 1
        try:
            # Do not map this project's historical GEMINI_API setting into the
            # subprocess. This judge deliberately uses the account signed into
            # Gemini CLI, matching the Claude CLI transport rather than billed
            # direct API-key inference.
            child_env = os.environ.copy()
            child_env.pop("GEMINI_API_KEY", None)
            child_env.pop("GOOGLE_API_KEY", None)
            run = _run_gemini_cli(
                [_GEMINI_EXE, "-p",
                 "Follow the instructions in the supplied input exactly. Return only the requested output.",
                 "--model", model, "--output-format", "json",
                 "--approval-mode", "plan", "--skip-trust"],
                text, timeout_s, child_env,
            )
            if run.returncode != 0:
                raise RuntimeError(
                    f"gemini judge exit {run.returncode}: {(run.stderr or run.stdout)[:300]}")
            payload = json.loads(run.stdout)
            if payload.get("error"):
                error = payload["error"]
                raise RuntimeError(
                    f"gemini judge error: {error.get('message', error) if isinstance(error, dict) else error}")
            clean = _FENCE.sub("", str(payload.get("response") or "").strip())
            if not clean:
                raise RuntimeError("Gemini CLI completed without a final response")
            tokens_in, cached, tokens_out, reasoning = _gemini_usage(payload.get("stats"))
            _record_judge_usage(
                tokens_in or _estimate_tokens(model, text),
                tokens_out or _estimate_tokens(model, clean),
                reasoning,
                time.perf_counter() - started,
                cached,
            )
            return clean
        except Exception as exc:
            last_error = exc
            if _gemini_terminal_quota_error(exc):
                break
            if attempt + 1 < JUDGE_MAX_TRIES:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Gemini judge failed after {attempts} attempt(s): {last_error}")


@dataclass
class _JudgeLLM(BaseRagasLLM):
    """RAGAS LLM driven by nim.post or a headless subscription CLI.
    The backend follows the judge model slug: Claude for `claude-*` (the default,
    haiku), subscription-authenticated Codex for `gpt-*`, Gemini CLI for `gemini-*`,
    and NIM otherwise (e.g. Qwen). Implements the three BaseRagasLLM hooks;
    structured-output parsing is RAGAS's own (it appends format instructions to
    the prompt)."""

    model: str = JUDGE_MODEL

    def _post(self, text, temperature, stop):
        global LAST_JUDGE_BACKEND, LAST_JUDGE_MODEL
        LAST_JUDGE_MODEL = self.model
        model = self.model.lower()
        if "claude" in model:
            LAST_JUDGE_BACKEND = "claude-cli"
            return {}, _claude_verdict(text, self.model, JUDGE_TIMEOUT_S), "stop"
        if "gemini" in model:
            LAST_JUDGE_BACKEND = "gemini-cli"
            return {}, _gemini_verdict(text, self.model, JUDGE_TIMEOUT_S), "stop"
        if "gpt-" in model:
            LAST_JUDGE_BACKEND = "codex-cli"
            return {}, _codex_verdict(text, self.model, JUDGE_TIMEOUT_S), "stop"
        LAST_JUDGE_BACKEND = "nim"
        resp = nim.post("/chat/completions", {
            "model": self.model,
            "temperature": float(temperature),
            # enable_thinking is NIM's authoritative thinking switch (it overrides the
            # /no_think prompt token); off keeps the verdict a direct structured 0/1.
            "chat_template_kwargs": {"enable_thinking": False},
            # Output budget for the verdict JSON; NIM's low default truncates it and the
            # RAGAS parser then fails the cell. The 262k context has room.
            "max_tokens": 4096,
            # Force >=1 generated token; this model otherwise emits end-of-turn as token 1
            # for some prompts, yielding an empty verdict.
            "min_tokens": 1,
            "messages": [{"role": "user", "content": text}],
            **({"stop": stop} if stop else {}),
        }, timeout=JUDGE_TIMEOUT_S, max_tries=JUDGE_MAX_TRIES,
            give_up_after_s=JUDGE_TIMEOUT_S * JUDGE_MAX_TRIES)
        choices = resp.get("choices") or []
        content = (choices[0].get("message") or {}).get("content") if choices else None
        finish = choices[0].get("finish_reason") if choices else "no choices"
        return resp, content, finish

    def _verdict(self, text, temperature, stop):
        # Retry on empty content: the model occasionally leaks into thinking mode even
        # with enable_thinking=False, emitting reasoning_content but zero content tokens.
        # min_tokens=1 doesn't prevent it (NIM counts reasoning tokens toward the
        # minimum); a fresh call usually escapes the leak.
        for _ in range(3):
            resp, content, finish = self._post(text, float(temperature or 0), stop)
            if content and content.strip():
                return content
        usage = resp.get("usage") or {}
        message = (resp.get("choices") or [{}])[0].get("message") or {}
        raise RuntimeError(
            f"NIM judge returned empty content (finish_reason={finish}, "
            f"completion_tokens={usage.get('completion_tokens')}, message_keys={sorted(message)})")

    def _complete(self, text, n, temperature, stop):
        return LLMResult(generations=[[
            Generation(text=self._verdict(text, temperature, stop)) for _ in range(max(1, n))]])

    def generate_text(self, prompt, n=1, temperature=1e-8, stop=None, callbacks=None):
        return self._complete(prompt.to_string(), n, temperature, stop)

    async def agenerate_text(self, prompt, n=1, temperature=1e-8, stop=None, callbacks=None):
        # Await the blocking call in the shared judge pool, so a metric's per-item
        # fan-out (RAGAS gathers these) genuinely overlaps. The pool size is the
        # global in-flight cap; the nim pacer still bounds NIM call rate per lane.
        return await asyncio.get_running_loop().run_in_executor(
            _CALL_POOL, lambda: self._complete(prompt.to_string(), n, temperature, stop))

    def is_finished(self, response) -> bool:
        return True


class _NimEmbedder(BaseRagasEmbeddings):
    """RAGAS embeddings driven by nim.post — llama-nemotron-embed, asymmetric: questions embed
    as "query", contexts as "passage" (the side matters for retrieval-QA)."""

    def __init__(self, model: str = EMBED_MODEL, run_config: RunConfig = None):
        super().__init__()
        self.model = model
        self.run_config = run_config or RunConfig()

    def _embed(self, texts, input_type):
        resp = nim.post("/embeddings", {
            "model": self.model,
            "input": [t or " " for t in texts],
            "input_type": input_type,
            "truncate": "NONE",
        }, timeout=EMBED_TIMEOUT_S, max_tries=EMBED_MAX_TRIES,
            give_up_after_s=EMBED_TIMEOUT_S * EMBED_MAX_TRIES)
        data = resp.get("data")
        if not data:
            raise RuntimeError(f"NIM /embeddings returned no data (keys={list(resp)})")
        return [d["embedding"] for d in sorted(data, key=lambda d: d.get("index", 0))]

    def embed_query(self, text):
        return self._embed([text], "query")[0]

    def embed_documents(self, texts):
        return self._embed(texts, "passage")

    async def aembed_query(self, text):
        return await asyncio.get_running_loop().run_in_executor(
            _CALL_POOL, self.embed_query, text)

    async def aembed_documents(self, texts):
        return await asyncio.get_running_loop().run_in_executor(
            _CALL_POOL, self.embed_documents, texts)


# --- catalog name -> RAGAS class + what it needs ------------------------------

_LLM, _EMB = "llm", "emb"

_REGISTRY = {
    "context_precision_id":      (IDBasedContextPrecision, ()),
    "context_recall_id":         (IDBasedContextRecall, ()),
    "context_precision_nonllm":  (NonLLMContextPrecisionWithReference, ()),
    "context_recall_nonllm":     (NonLLMContextRecall, ()),
    "context_precision_llm":     (LLMContextPrecisionWithoutReference, (_LLM,)),
    "context_precision_llm_ref": (LLMContextPrecisionWithReference, (_LLM,)),
    "context_recall_llm":        (LLMContextRecall, (_LLM,)),
    "context_entity_recall":     (ContextEntityRecall, (_LLM,)),
    "context_relevance_nv":      (ContextRelevance, (_LLM,)),
    "noise_sensitivity":         (NoiseSensitivity, (_LLM,)),
    "faithfulness":              (Faithfulness, (_LLM,)),
    "answer_relevancy":          (ResponseRelevancy, (_LLM, _EMB)),
    "response_groundedness_nv":  (ResponseGroundedness, (_LLM,)),
    "answer_accuracy_nv":        (AnswerAccuracy, (_LLM,)),
    "factual_correctness":       (FactualCorrectness, (_LLM,)),
    "answer_correctness":        (AnswerCorrectness, (_LLM, _EMB)),
    "semantic_similarity":       (SemanticSimilarity, (_EMB,)),
    "string_similarity":         (NonLLMStringSimilarity, ()),
    "bleu":                      (BleuScore, ()),
    "rouge":                     (RougeScore, ()),
    "chrf":                      (ChrfScore, ()),
    "exact_match":               (ExactMatch, ()),
    "string_presence":           (StringPresence, ()),
}

# These LLM metrics judge each retrieved context independently — ~one model call per
# context (so ~k calls/question). They get their own pass, run last, so they never hold
# up the cheap metrics.
_PER_CONTEXT = {"context_precision_llm", "context_precision_llm_ref"}
_CONTEXT_HEAVY_LLM = {
    "context_precision_llm",
    "context_precision_llm_ref",
    "context_recall_llm",
    "context_relevance_nv",
    "faithfulness",
    "response_groundedness_nv",
}


def _build_metrics(names, judge, embedder, run_config):
    """Instantiate each selected metric with the wrappers it needs, then init() it —
    RAGAS's lifecycle step (run by evaluate(), which we bypass by calling
    single_turn_ascore directly). init() wires sub-components RAGAS builds lazily there,
    e.g. AnswerCorrectness's AnswerSimilarity from the embedder, and stamps the run
    config; without it those stay unset and the metric asserts. A name with no builder is
    a hard failure (ragas_catalog drifted from this registry)."""
    built = {}
    for name in names:
        if name not in _REGISTRY:
            raise KeyError(
                f"no RAGAS builder for metric {name!r} — ragas_catalog.metrics_to_run "
                "lists a metric ragas.py doesn't map")
        cls, needs = _REGISTRY[name]
        kw = {}
        if _LLM in needs:
            kw["llm"] = judge
        if _EMB in needs:
            kw["embeddings"] = embedder
        metric = cls(**kw)
        metric.init(run_config)
        built[name] = metric
    return built


# --- sample construction ------------------------------------------------------

_ARTIFACT_TYPES = ("slack", "documents", "meeting_transcripts", "meeting_chats", "urls", "prs")


def _string_leaves(value) -> str:
    """Every string leaf of an artifact record, joined — a faithful text rendering of
    the artifact for the gold-context-text metrics. Arm-agnostic on purpose (the
    string-sim metrics only need comparable gold text, not an arm's exact rendering)."""
    parts: list = []

    def walk(v):
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, dict):
            for w in v.values():
                walk(w)
        elif isinstance(v, list):
            for w in v:
                walk(w)

    walk(value)
    return " ".join(parts).strip()


def corpus_gold_text(corpus_root) -> dict:
    """artifact id -> its text. The non-LLM context metrics score retrieved text
    against gold *context text*, so the gold citation ids must dereference to text.
    The evaluator may read the corpus for this — it is scoring against truth, not
    retrieving. First occurrence of an id wins (ids are globally unique in HERB).
    linked to: _to_sample (fills reference_contexts)"""
    root = Path(corpus_root)
    out: dict = {}
    for pf in sorted((root / "products").glob("*.json")):
        data = json.loads(pf.read_text(encoding="utf-8"))
        for kind in _ARTIFACT_TYPES:
            for rec in data.get(kind, []) or []:
                aid = rec.get("id")
                if aid is None or aid in out:
                    continue
                out[aid] = _string_leaves(rec)
    return out


def _to_sample(out, q, gold_text) -> SingleTurnSample:
    """One contract pair -> a RAGAS SingleTurnSample. reference = the gold answer
    (joined); reference_context_ids = gold citations; reference_contexts = those
    citations' text (when the corpus was supplied)."""
    gold = [str(g) for g in (q.ground_truth or [])]
    cites = [str(c) for c in (q.citations or [])]
    ref_ctx = [gold_text[c] for c in cites if c in gold_text]
    return SingleTurnSample(
        user_input=q.question,
        response=out.answer or "",
        retrieved_contexts=list(out.contexts or []),
        retrieved_context_ids=[str(c) for c in (out.context_ids or [])],
        reference=" ".join(gold),
        reference_context_ids=cites,
        reference_contexts=ref_ctx or None,
    )


# --- scoring ------------------------------------------------------------------

def score_outputs(outputs, questions, arm="", corpus=None, results_path=None, workers=1,
                  retrieval_only=False):
    """ENTRY: per (output, question) score every metric in metrics_to_run() ->
    list[contract.EvalResult] (one row per question per metric). judge = the model
    named by RAGAS_JUDGE_MODEL (haiku via the Claude CLI by default, another Claude,
    Codex GPT, or Gemini when requested), embedder = llama-nemotron-embed on NIM.
    `corpus` (root path) lets the gold-context-text metrics dereference citations to
    text; the orchestrator supplies it.

    `retrieval_only` keeps only the judge-free, embed-free metrics (the id/nonllm
    retrieval scores): with no generator the answers are empty, so the judge and embed
    metrics have nothing real to score and their NIM pass never runs.

    `workers` scores that many questions concurrently (the same knob generation uses);
    every call still funnels through nim.py's one shared rate cap, so concurrency only
    overlaps the model latency, it never bursts past the limit.

    If `results_path` is given, each question's full set of cells is appended there and
    flushed the moment that question finishes — so a crash or q-abort keeps every
    finished question, and a re-run over the same path skips the questions already
    scored (the eval resumes, like generation does). The return is this leg's rows.
    linked to: orchestrator.run_one_evaluator; ragas_catalog.metrics_to_run"""
    # nim.post owns retry + the global rate-limit backoff; cap RAGAS's own retry at a
    # single attempt so it never stacks its default 10x on top of each judge/embed call.
    # That nesting turned one 429 into minutes of dead retries and, under concurrency,
    # starved the shared pacer so parallel ran slower than serial.
    run_config = RunConfig(max_retries=1)
    global LAST_JUDGE_USAGE, LAST_JUDGE_BACKEND, LAST_JUDGE_MODEL
    global LAST_JUDGE_REASONING_EFFORT, LAST_JUDGE_WALL_TIME_S
    LAST_JUDGE_USAGE = ModelUsage()
    LAST_JUDGE_BACKEND = JUDGE_BACKEND
    LAST_JUDGE_MODEL = None
    LAST_JUDGE_REASONING_EFFORT = JUDGE_REASONING_EFFORT
    LAST_JUDGE_WALL_TIME_S = 0.0
    if JUDGE_BACKEND == "codex-cli" and not _CODEX_EXE:
        raise RuntimeError("RAGAS_JUDGE_MODEL starts with gpt- but `codex` is not on PATH")
    if JUDGE_BACKEND == "gemini-cli" and not _GEMINI_EXE:
        raise RuntimeError("RAGAS_JUDGE_MODEL starts with gemini- but `gemini` is not on PATH")

    started = time.perf_counter()
    judge, embedder = _JudgeLLM(run_config=run_config), _NimEmbedder(run_config=run_config)
    selected = metrics_to_run()
    if retrieval_only:
        selected = [n for n in selected if not CATALOG[n].judge and not CATALOG[n].embed]
    metrics = _build_metrics(selected, judge, embedder, run_config)
    if not retrieval_only:  # no judge runs on empty answers, so don't announce one
        effort = f" effort={JUDGE_REASONING_EFFORT}" if JUDGE_REASONING_EFFORT else ""
        print(f"ragas judge: {JUDGE_MODEL} backend={JUDGE_BACKEND}{effort} "
              f"timeout={JUDGE_TIMEOUT_S:g}s tries={JUDGE_MAX_TRIES}")
    gold_text = corpus_gold_text(corpus) if corpus else {}
    results = _score_all(outputs, questions, arm, metrics, gold_text,
                         results_path, workers)
    LAST_JUDGE_WALL_TIME_S = time.perf_counter() - started
    _print_status_summary(results)
    if LAST_JUDGE_USAGE.calls:
        print(
            f"ragas judge usage: {LAST_JUDGE_USAGE.calls} call(s), "
            f"in={LAST_JUDGE_USAGE.tokens_in} cached={LAST_JUDGE_USAGE.cached_input_tokens} "
            f"out={LAST_JUDGE_USAGE.tokens_out} reasoning={LAST_JUDGE_USAGE.reasoning_tokens} "
            f"tokens, request-time={LAST_JUDGE_USAGE.time_s:.1f}s "
            f"wall={LAST_JUDGE_WALL_TIME_S:.1f}s")
    return results


def _load_rows(results_path) -> list:
    """Parsed rows already in results_path. A torn trailing line from a killed write
    is dropped (that question re-scores on resume); a non-trailing parse error is real
    corruption and raises loud."""
    p = Path(results_path) if results_path else None
    if not p or not p.is_file():
        return []
    lines = [x for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    rows = []
    for i, x in enumerate(lines):
        try:
            rows.append(json.loads(x))
        except json.JSONDecodeError:
            if i == len(lines) - 1:
                break  # torn last line from a killed write — drop it, re-score that q
            raise
    return rows


def _check_judge_context_budget(outputs, questions, metrics) -> None:
    """Context-heavy judged metrics concatenate all retrieved contexts into one prompt."""
    heavy = sorted(set(metrics) & _CONTEXT_HEAVY_LLM)
    if not heavy or MAX_JUDGE_CONTEXT_CHARS <= 0:
        return

    sizes = [
        (getattr(q, "id", "?"),
         sum(len(c or "") for c in (getattr(out, "contexts", None) or [])),
         len(getattr(out, "contexts", None) or []))
        for out, q in zip(outputs, questions)
    ]
    over = [row for row in sizes if row[1] > MAX_JUDGE_CONTEXT_CHARS]
    if not over:
        return

    over.sort(key=lambda row: row[1], reverse=True)
    worst = "\n".join(
        f"  {qid}: {n_ctx} contexts, {chars:,} chars"
        for qid, chars, n_ctx in over[:8]
    )
    print(
        "ragas warning: context-heavy judged metrics will create huge k50 judge prompts.\n"
        f"metrics: {', '.join(heavy)}\n"
        f"warning threshold: {MAX_JUDGE_CONTEXT_CHARS:,} retrieved-context chars per question\n"
        f"over-threshold questions: {len(over)}/{len(sizes)}\n"
        f"{worst}\n"
        "continuing the run; this is expected to be slow."
    )


def _score_all(outputs, questions, arm, metrics, gold_text, results_path=None,
               workers=1) -> list:
    """Score every (question, metric) cell -> list[EvalResult], in ordered passes: the
    deterministic metrics first (no model call — instant, the id-based retrieval scores are
    the headline signal), then the cheap NIM judge/embed metrics, then the per-context
    metrics last (~1 call per retrieved context — the slow tail), so every cheap score
    lands before the slow pass grinds alone. An abort or throttle still leaves every
    finished pass on disk, and a pass only touches the metrics it owns.
    Each pass scores up to `workers` CELLS (question × metric) at once, one per thread —
    each in its OWN event loop (asyncio.run), because RAGAS bridges sync<->async with
    nest_asyncio and sharing one running loop deadlocks it. Inside a cell, a metric's
    per-item fan-out overlaps through the shared judge pool (JUDGE_INFLIGHT is the
    global in-flight cap); the nim.py pacer still bounds NIM call rate per lane. The
    main thread collects and writes each cell as it lands, so the bar tracks real work.

    Resume (results_path): tracked per CELL. A (question, metric) is done only if it has an
    ok row on disk; errored or missing cells re-score, and ONLY those — never an already-ok
    cell, even when a pass-mate of it failed. The compaction below keeps every ok cell and
    drops the rest. Each errored cell is also appended live to eval_failures.jsonl (truncated
    fresh each leg) so failures can be watched mid-run, like generation's."""
    passes = [(lbl, m) for lbl, m in (
        ("scoring - offline (free)",
         {n: m for n, m in metrics.items() if _REGISTRY[n][1] == ()}),
        ("scoring - judge + embed (NIM)",
         {n: m for n, m in metrics.items() if _REGISTRY[n][1] != () and n not in _PER_CONTEXT}),
        ("scoring - context precision (1 call/context, slow)",
         {n: m for n, m in metrics.items() if n in _PER_CONTEXT}),
    ) if m]
    prior = _load_rows(results_path)
    selected = set(metrics)
    # Resume is per CELL: a (question, metric) is done only if it has an ok row for a
    # still-selected metric. Build the ok-cell set per question and, in the same pass, the
    # rows to keep (each selected ok cell, once). Errored, missing, duplicate, and
    # now-deselected cells all fall away — re-scored if still selected, else just dropped.
    done_ok = defaultdict(set)
    kept = []
    for r in prior:
        if (r["status"] != "ok" or r["metric"] not in selected
                or r["metric"] in done_ok[r["question_id"]]):
            continue
        done_ok[r["question_id"]].add(r["metric"])
        kept.append(r)

    if results_path and len(kept) != len(prior):
        # keep every selected ok cell; drop the rest. Atomic temp+rename so a crash
        # mid-rewrite can't lose kept rows.
        dst = Path(results_path)
        tmp = dst.with_name(dst.name + ".tmp")
        tmp.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept), encoding="utf-8")
        os.replace(tmp, dst)

    sample_of = {q.id: (q, _to_sample(out, q, gold_text))
                 for out, q in zip(outputs, questions)
                 if selected - done_ok[q.id]}

    fh = open(results_path, "a", encoding="utf-8") if results_path else None
    ffh = (open(Path(results_path).parent / "eval_failures.jsonl", "w", encoding="utf-8")
           if results_path else None)
    results = []

    def _score_cell(q, sample, name, metric, on_cell):
        """Score ONE (question, metric) cell in this worker thread's OWN event loop
        (asyncio.run — RAGAS bridges sync<->async with nest_asyncio, and sharing a
        running loop across cells deadlocks it). Cells are the parallel unit: a
        question's metrics land independently, and a metric's per-item fan-out
        overlaps through the shared judge pool."""
        async def _go():
            value, status, comp = await _score_one(metric, sample)
            return EvalResult(q.id, q.type, arm, name, value, status, comp, None)
        row = asyncio.run(_go())
        on_cell()
        return row

    def _run_pass(pass_metrics, pass_samples, label) -> str:
        """Score this pass's cells, up to `workers` at a time in a thread pool, writing
        each cell's row the moment it lands. The cheap passes tick the bar per cell;
        the per-context pass tracks NIM calls (one cell is ~k calls, so even per-cell
        would crawl). Either way the bar moves within seconds. Rows are
        self-identifying by question_id, so the file is free to follow completion
        order. -> 'ok' | 'user_abort' | 'backend_down'."""
        if not pass_metrics or not pass_samples:
            return "ok"
        # The per-context metrics make ~one judge call per retrieved context, so a single
        # question is ~k calls before its one cell lands — a per-cell bar would sit at 0%
        # for minutes. For that pass, size and drive the bar by NIM calls instead, so it
        # climbs every couple seconds; other passes stay per-cell with a call-count postfix.
        per_context = bool(set(pass_metrics) & _PER_CONTEXT)
        if per_context:
            expected_calls = sum(len(s.retrieved_contexts or []) * len(todo) for _, s, todo in pass_samples)
            bar = progress(total=max(1, expected_calls), desc=label, unit="call")
        else:
            bar = progress(total=sum(len(todo) for _, _, todo in pass_samples), desc=label, unit="cell")
        bar_lock = threading.Lock()

        def _tick_cell():  # per-context: the heartbeat drives the bar by NIM calls instead
            if not per_context:
                with bar_lock:
                    bar.update(1)

        start_calls, stop = nim.completed_calls(), threading.Event()

        def _heartbeat():
            while not stop.wait(1.0):
                with bar_lock:
                    done = nim.completed_calls() - start_calls
                    if per_context:
                        bar.n = min(bar.total, done)
                        bar.refresh()
                    else:
                        bar.set_postfix_str(f"{done} nim calls", refresh=True)

        threading.Thread(target=_heartbeat, daemon=True).start()
        consecutive_failed, outcome = 0, None
        cells = [(q, sample, name, metric)
                 for q, sample, todo in pass_samples for name, metric in todo.items()]
        cells_total = Counter(q.id for q, _, _, _ in cells)
        cells_left, cells_errored, cells_quota_errored = dict(cells_total), Counter(), Counter()
        try:
            with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
                futs = {ex.submit(_score_cell, q, sample, name, metric, _tick_cell): q
                        for q, sample, name, metric in cells}
                for fut in as_completed(futs):
                    if abort.aborted():
                        for f in futs:
                            f.cancel()
                        outcome = "user_abort"
                        bar.write("[q] eval aborted - every finished cell is saved")
                        break
                    try:
                        row = fut.result()  # an unexpected raise (e.g. disk full) propagates loud
                    except abort.Aborted:  # q pressed mid-fan-out — stop; this cell writes nothing
                        for f in futs:
                            f.cancel()
                        outcome = "user_abort"
                        bar.write("[q] eval aborted - every finished cell is saved")
                        break
                    if ffh and row.status == "error":
                        ffh.write(json.dumps(
                            {"question_id": row.question_id, "metric": row.metric,
                             "error": (row.components or {}).get("error", "")},
                            ensure_ascii=False) + "\n")
                        ffh.flush()  # live — errored cells show up the moment they land
                    if fh:
                        fh.write(json.dumps(asdict(row), ensure_ascii=False) + "\n")
                        fh.flush()  # per cell — durable + resumable at cell grain
                    results.append(row)
                    # circuit breaker: when a question's LAST cell lands, mostly-errored
                    # counts as failed; that many in a row means the backend is down.
                    qid = row.question_id
                    cells_errored[qid] += row.status == "error"
                    cells_quota_errored[qid] += _gemini_quota_error_row(row)
                    cells_left[qid] -= 1
                    if cells_left[qid] == 0:
                        failed = cells_errored[qid] * 2 >= cells_total[qid]
                        consecutive_failed = consecutive_failed + 1 if failed else 0
                        if consecutive_failed >= MAX_CONSECUTIVE_FAILED_QUESTIONS:
                            for f in futs:
                                f.cancel()
                            quota_exhausted = (
                                JUDGE_BACKEND == "gemini-cli"
                                and cells_quota_errored[qid] == cells_errored[qid]
                                and cells_quota_errored[qid] > 0
                            )
                            outcome = "gemini_quota_exhausted" if quota_exhausted else "backend_down"
                            if quota_exhausted:
                                bar.write("[abort] Gemini CLI rejected the model with a terminal quota/entitlement error")
                            else:
                                bar.write(f"[abort] {consecutive_failed} questions in a row mostly errored "
                                          "- judge/embed backend likely down")
                            break
        finally:
            stop.set()
            if per_context and outcome is None:  # finished clean — show the full bar
                with bar_lock:
                    bar.n = bar.total
                    bar.refresh()
            bar.close()
        return outcome or "ok"

    try:
        status = "ok"
        for label, pass_metrics in passes:
            pass_samples = []
            for q in questions:
                if q.id not in sample_of:
                    continue
                todo = {n: m for n, m in pass_metrics.items() if n not in done_ok[q.id]}
                if todo:
                    pass_samples.append((q, sample_of[q.id][1], todo))
            status = _run_pass(pass_metrics, pass_samples, label)
            if status != "ok":
                break
    finally:
        if fh:
            fh.close()
        if ffh:
            ffh.close()
    # fail loud like the generation leg — finished questions are on disk, resume continues.
    if status == "user_abort":
        raise RuntimeError("eval aborted (pressed q) - finished questions saved; resume to continue")
    if status == "gemini_quota_exhausted":
        raise RuntimeError(
            "eval stopped: Gemini CLI returned TerminalQuotaError for this model "
            "(quota or entitlement; this can happen at 0% used) - finished questions saved")
    if status == "backend_down":
        raise RuntimeError(
            f"eval stopped: {MAX_CONSECUTIVE_FAILED_QUESTIONS} questions in a row mostly errored "
            "(judge/embed backend likely down) - finished questions saved, resume when it recovers")
    return results


def _print_status_summary(results):
    """One line per metric that produced any non-ok cell, so failures are visible at
    a glance instead of buried in the jsonl."""
    bad = Counter((r.metric, r.status) for r in results if r.status != "ok")
    if not bad:
        print(f"ragas: all {len(results)} cells ok")
        return
    print("ragas non-ok cells:")
    for (metric, status), n in sorted(bad.items()):
        print(f"  {metric:<26} {status:<6} x{n}")


async def _score_one(metric, sample) -> tuple:
    """Score one metric on one sample. A per-cell failure is recorded LOUD (status +
    message in the row), not swallowed — one metric erroring on one item must not sink
    the other 22 x N. The caller surfaces the error tally."""
    try:
        value = float(await metric.single_turn_ascore(sample))
    except abort.Aborted:
        raise  # control flow, not a scored failure — unwinds the pass, writes no cell
    except Exception as e:
        return float("nan"), "error", {"error": f"{type(e).__name__}: {e}"}
    if value != value:  # NaN: the metric ran but produced no number for this item
        return value, "nan", {}
    return value, "ok", {}

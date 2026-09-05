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

from harness import abort
from harness import jsonl
from harness import nim
from harness.progress import progress
from harness.contract import EvalResult, ModelUsage
from eval.ragas_catalog import CATALOG, metrics_to_run
from harness.embed import EMBED_BATCH, _embed_request

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
    model = model.lower()
    if "claude" in model:
        return {"inflight": 64, "timeout_s": 120.0, "tries": 2}
    if "gpt-" in model:
        return {"inflight": 64, "timeout_s": 180.0, "tries": 2}
    if "gemini" in model:
        return {"inflight": 64, "timeout_s": 180.0, "tries": 2}
    if any(x in model for x in ("397b", "-675b", "340b", "ultra")):
        return {"inflight": 8, "timeout_s": 480.0, "tries": 3}
    return {"inflight": 8, "timeout_s": 90.0, "tries": 3}


_PROFILE = _judge_profile(JUDGE_MODEL)
JUDGE_TIMEOUT_S = max(30.0, float(os.environ.get("RAGAS_JUDGE_TIMEOUT_S", _PROFILE["timeout_s"])))
JUDGE_MAX_TRIES = max(1, int(os.environ.get("RAGAS_JUDGE_MAX_TRIES", _PROFILE["tries"])))
JUDGE_INFLIGHT = max(1, int(os.environ.get("RAGAS_JUDGE_INFLIGHT", _PROFILE["inflight"])))
_CALL_POOL = ThreadPoolExecutor(max_workers=JUDGE_INFLIGHT, thread_name_prefix="judge-call")
MAX_JUDGE_CONTEXT_CHARS = int(os.environ.get("RAGAS_MAX_JUDGE_CONTEXT_CHARS", "60000"))
_JUDGE_USAGE_LOCK = threading.Lock()
LAST_JUDGE_USAGE = ModelUsage()
LAST_JUDGE_BACKEND = JUDGE_BACKEND
LAST_JUDGE_MODEL = None
LAST_JUDGE_REASONING_EFFORT = JUDGE_REASONING_EFFORT
LAST_JUDGE_WALL_TIME_S = 0.0

MAX_CONSECUTIVE_FAILED_QUESTIONS = 10

warnings.filterwarnings(
    "ignore", message=r"Importing .* from 'ragas\.metrics' is deprecated",
    category=DeprecationWarning)

from langchain_core.outputs import Generation, LLMResult
from ragas.dataset_schema import SingleTurnSample
from ragas.embeddings.base import BaseRagasEmbeddings
from ragas.llms.base import BaseRagasLLM
from ragas.run_config import RunConfig
from ragas.metrics import (
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
from ragas.metrics._nv_metrics import (
    AnswerAccuracy,
    ContextRelevance,
    ResponseGroundedness,
)


_CODEX_EXE = shutil.which("codex")
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
                        elapsed_s: float, cached_input_tokens: int = 0,
                        transport: dict | None = None) -> None:
    if transport is None:
        transport = {"attempts": 1, "request_s": float(elapsed_s or 0.0),
                     "wait_s": 0.0, "retry_s": 0.0}
    with _JUDGE_USAGE_LOCK:
        LAST_JUDGE_USAGE.calls += 1
        LAST_JUDGE_USAGE.tokens_in += int(tokens_in or 0)
        LAST_JUDGE_USAGE.cached_input_tokens += int(cached_input_tokens or 0)
        LAST_JUDGE_USAGE.tokens_out += int(tokens_out or 0)
        LAST_JUDGE_USAGE.reasoning_tokens += int(reasoning_tokens or 0)
        LAST_JUDGE_USAGE.time_s += float(elapsed_s or 0.0)
        LAST_JUDGE_USAGE.attempts += transport["attempts"]
        LAST_JUDGE_USAGE.request_s += transport["request_s"]
        LAST_JUDGE_USAGE.wait_s += transport["wait_s"]
        LAST_JUDGE_USAGE.retry_s += transport["retry_s"]


def _claude_verdict(text: str, model: str, timeout_s: float) -> str:
    started = time.perf_counter()
    nim.reset_timing()
    resp = nim.post("/chat/completions",
                    {"model": model, "messages": [{"role": "user", "content": text}]},
                    timeout=timeout_s, max_tries=1)
    transport = nim.take_timing()
    clean = ((resp.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    usage = resp.get("usage") or {}
    _record_judge_usage(
        int(usage.get("prompt_tokens") or 0) or _estimate_tokens(model, text),
        int(usage.get("completion_tokens") or 0) or _estimate_tokens(model, clean),
        0, time.perf_counter() - started,
        int(usage.get("cached_input_tokens") or 0),
        transport)
    return clean


def _codex_usage(jsonl: str) -> dict:
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
    text = str(error).lower()
    return "terminalquotaerror" in text or "daily quota" in text


def _gemini_quota_error_row(row: "EvalResult") -> bool:
    return (
        JUDGE_BACKEND == "gemini-cli"
        and row.status == "error"
        and _gemini_terminal_quota_error(
            RuntimeError(str((row.components or {}).get("error", "")))
        )
    )


def _gemini_verdict(text: str, model: str, timeout_s: float) -> str:
    if not _GEMINI_EXE:
        raise RuntimeError("gemini-* judges need the signed-in `gemini` CLI on PATH")
    started = time.perf_counter()
    last_error = None
    attempts = 0
    for attempt in range(JUDGE_MAX_TRIES):
        attempts = attempt + 1
        try:
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
            "chat_template_kwargs": {"enable_thinking": False},
            "max_tokens": 4096,
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
        return await asyncio.get_running_loop().run_in_executor(
            _CALL_POOL, lambda: self._complete(prompt.to_string(), n, temperature, stop))

    def is_finished(self, response) -> bool:
        return True


class _SharedEmbedder(BaseRagasEmbeddings):

    def __init__(self, model: str = EMBED_MODEL, run_config: RunConfig = None):
        super().__init__()
        self.model = model
        self.run_config = run_config or RunConfig()
        self._vectors = {}
        self._vectors_lock = threading.Lock()

    def _request(self, texts, input_type):
        return _embed_request(texts, input_type)[0]

    def _uncached(self, texts, input_type):
        with self._vectors_lock:
            return [t for t in dict.fromkeys(texts) if (input_type, t) not in self._vectors]

    def _store(self, texts, input_type, vectors) -> None:
        with self._vectors_lock:
            self._vectors.update(((input_type, t), v) for t, v in zip(texts, vectors))

    def prime(self, texts, input_type) -> int:
        missing = self._uncached(texts, input_type)
        calls = 0
        for i in progress(range(0, len(missing), EMBED_BATCH),
                          desc="ragas embed", unit="batch"):
            chunk = missing[i:i + EMBED_BATCH]
            vectors, made, _tok_in, _tok_out, _secs = _embed_request(chunk, input_type)
            self._store(chunk, input_type, vectors)
            calls += made
        return calls

    def _embed(self, texts, input_type):
        missing = self._uncached(texts, input_type)
        if missing:
            self._store(missing, input_type, self._request(missing, input_type))
        with self._vectors_lock:
            return [self._vectors[(input_type, t)] for t in texts]

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


_ARTIFACT_TYPES = ("slack", "documents", "meeting_transcripts", "meeting_chats", "urls", "prs")


def _string_leaves(value) -> str:
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


def score_outputs(outputs, questions, arm="", corpus=None, results_path=None, workers=1,
                  retrieval_only=False):
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
    judge, embedder = _JudgeLLM(run_config=run_config), _SharedEmbedder(run_config=run_config)
    selected = metrics_to_run()
    if retrieval_only:
        selected = [n for n in selected if not CATALOG[n].judge and not CATALOG[n].embed]
    metrics = _build_metrics(selected, judge, embedder, run_config)
    if not retrieval_only:
        effort = f" effort={JUDGE_REASONING_EFFORT}" if JUDGE_REASONING_EFFORT else ""
        print(f"ragas judge: {JUDGE_MODEL} backend={JUDGE_BACKEND}{effort} "
              f"timeout={JUDGE_TIMEOUT_S:g}s tries={JUDGE_MAX_TRIES}")
    gold_text = corpus_gold_text(corpus) if corpus else {}
    results = _score_all(outputs, questions, arm, metrics, gold_text,
                         results_path, workers, embedder)
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
    return jsonl.load(results_path) if results_path else []


def _check_judge_context_budget(outputs, questions, metrics) -> None:
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


def _prime_embed_cache(embedder, metrics, samples) -> None:
    if not any(_EMB in _REGISTRY[n][1] for n in metrics):
        return
    texts = [t for _q, s in samples for t in (s.reference or "", s.response or "")]
    distinct = len(dict.fromkeys(texts))
    print(f"ragas embed: priming {distinct} text(s) in "
          f"{-(-distinct // EMBED_BATCH)} batch(es) of up to {EMBED_BATCH}", flush=True)
    calls = embedder.prime(texts, "passage")
    print(f"ragas embed: primed in {calls} forward pass(es)", flush=True)


def _score_all(outputs, questions, arm, metrics, gold_text, results_path=None,
               workers=1, embedder=None) -> list:
    passes = [(lbl, m) for lbl, m in (
        ("scoring - offline (free)",
         {n: m for n, m in metrics.items() if _REGISTRY[n][1] == ()}),
        ("scoring - judge + embed",
         {n: m for n, m in metrics.items() if _REGISTRY[n][1] != () and n not in _PER_CONTEXT}),
        ("scoring - context precision (1 call/context, slow)",
         {n: m for n, m in metrics.items() if n in _PER_CONTEXT}),
    ) if m]
    prior = _load_rows(results_path)
    selected = set(metrics)
    done_ok = defaultdict(set)
    kept = []
    for r in prior:
        if (r["status"] != "ok" or r["metric"] not in selected
                or r["metric"] in done_ok[r["question_id"]]):
            continue
        done_ok[r["question_id"]].add(r["metric"])
        kept.append(r)

    if results_path and len(kept) != len(prior):
        dst = Path(results_path)
        tmp = dst.with_name(dst.name + ".tmp")
        tmp.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept), encoding="utf-8")
        os.replace(tmp, dst)

    sample_of = {q.id: (q, _to_sample(out, q, gold_text))
                 for out, q in zip(outputs, questions)
                 if selected - done_ok[q.id]}

    if embedder is not None and sample_of:
        _prime_embed_cache(embedder, metrics, sample_of.values())

    if results_path:
        jsonl.heal(results_path)
    fh = open(results_path, "a", encoding="utf-8") if results_path else None
    ffh = (open(Path(results_path).parent / "eval_failures.jsonl", "w", encoding="utf-8")
           if results_path else None)
    results = []

    def _score_cell(q, sample, name, metric, on_cell):
        async def _go():
            value, status, comp = await _score_one(metric, sample)
            return EvalResult(q.id, q.type, arm, name, value, status, comp, None)
        row = asyncio.run(_go())
        on_cell()
        return row

    def _run_pass(pass_metrics, pass_samples, label) -> str:
        if not pass_metrics or not pass_samples:
            return "ok"
        per_context = bool(set(pass_metrics) & _PER_CONTEXT)
        if per_context:
            expected_calls = sum(len(s.retrieved_contexts or []) * len(todo) for _, s, todo in pass_samples)
            bar = progress(total=max(1, expected_calls), desc=label, unit="call")
        else:
            bar = progress(total=sum(len(todo) for _, _, todo in pass_samples), desc=label, unit="cell")
        bar_lock = threading.Lock()

        def _tick_cell():
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
                        row = fut.result()
                    except abort.Aborted:
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
                        ffh.flush()
                    if fh:
                        fh.write(json.dumps(asdict(row), ensure_ascii=False) + "\n")
                        fh.flush()
                        os.fsync(fh.fileno())
                    results.append(row)
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
            if per_context and outcome is None:
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
    bad = Counter((r.metric, r.status) for r in results if r.status != "ok")
    if not bad:
        print(f"ragas: all {len(results)} cells ok")
        return
    print("ragas non-ok cells:")
    for (metric, status), n in sorted(bad.items()):
        print(f"  {metric:<26} {status:<6} x{n}")


async def _score_one(metric, sample) -> tuple:
    try:
        value = float(await metric.single_turn_ascore(sample))
    except abort.Aborted:
        raise
    except Exception as e:
        return float("nan"), "error", {"error": f"{type(e).__name__}: {e}"}
    if value != value:
        return value, "nan", {}
    return value, "ok", {}

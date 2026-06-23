"""vector.py — dense baseline (embeddings + cosine), i.e. naive RAG.

Why it's here: the dense-retrieval control arm — the standard vector RAG the
artefact's structured retrieval is claimed to beat. It reads the corpus and
builds its own embedding index over it.

In -> out: question -> embed -> cosine top-k artifacts -> shared generator -> answer.

Provenance (the method's lineage, not an eval target): dense passage retrieval in
the Sentence-BERT (Reimers & Gurevych 2019) / DPR (Karpukhin et al. 2020) line,
benchmarked on BEIR (Thakur et al. 2021). The search mirrors BEIR's reference
`evaluate_sbert.py` — `DenseRetrievalExactSearch` with `cos_sim`: exact cosine of
the query against every corpus vector, which is exactly the brute-force matrix-dot
below. These citations are the PROVENANCE of the method only — BEIR is NOT an
evaluation target; every arm (artifact / lucene / vector) is scored solely by the
two project scorers, HERB and RAGAS.

Two things moved on from the textbook default. The embedder is
nvidia/llama-3.2-nv-embedqa-1b-v2 on NVIDIA NIM — a multilingual, English-strong
QA-retrieval embedder — NOT the English-only, 256-token all-MiniLM-L6-v2 via
Sentence-Transformers (rejected: it would truncate HERB's long documents and
meeting transcripts and could not serve the deferred Swedish Bonnier set). And
artifacts embed WHOLE: nv-embedqa's 8192-token context covers every HERB artifact
(the longest document is ~1.5k tokens), so no truncation and no chunking — this
arm's own unit choice. ONE shared embedder across datasets — HERB now, Bonnier
later, no swap.

nv-embedqa is asymmetric: corpus artifacts embed as `input_type="passage"`,
questions as `input_type="query"` — passing the wrong side silently degrades
retrieval, so the side is explicit at both call sites.

Search: exact (brute-force) cosine over the corpus embedding matrix. The HERB
corpus is small (~38.6k artifacts), so an ANN index would only add approximation
error for no real speed gain — "index" here means embed-all + cosine, not an ANN
structure. Vectors are L2-normalised at build, so cosine is one matrix-vector dot.

Retrieval unit = one whole HERB artifact, kept under its native `id`, so
`context_ids` are in the same id space as the gold citations (which the
citation-based context metrics compare against).

Contract fit: prepare returns a Prepared index carrying a contract.BuildStats
(model = ModelUsage capturing the embedder's build-time calls / tokens / time);
answer_one_question returns a contract.ArmOutput. The question is read for its
`id` + `question` ONLY — ground_truth / citations are never touched. (contract.py
is the one module every arm imports: the shared harness shapes, not a retrieval
component.)
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np

import nim
from contract import ArmOutput, BuildStats, ModelUsage

EMBED_MODEL = "nvidia/llama-3.2-nv-embedqa-1b-v2"
# ponytail: fixed batch + nim.post's own retry/backoff instead of a rate limiter.
# Drop EMBED_BATCH if NIM rejects large batches; add a limiter only if a real
# build actually trips the rate cap.
EMBED_BATCH = 64
DEFAULT_TOP_K = 10

# The six artifact arrays in each HERB product file. Metadata (employee /
# customer / team directories) is deliberately NOT embedded: no gold citation
# points at it, so it could only be a never-relevant distractor in the index.
ARTIFACT_TYPES = (
    "slack",
    "documents",
    "meeting_transcripts",
    "meeting_chats",
    "urls",
    "prs",
)

# The shared generator the orchestrator injects (fairness control). It takes the
# question text + retrieved contexts and returns the answer (optionally with a
# telemetry pair/object); _unpack_generation handles the three return shapes.
Generator = Callable[[str, list], object]


@dataclass
class Prepared:
    """Handle returned by prepare(); fed back into answer_one_question. Holds the
    L2-normalised embedding matrix (so cosine == dot) + ids/texts + the BuildStats
    for run provenance. The query embeds via nim.post with the same EMBED_MODEL."""

    matrix: "np.ndarray"
    ids: list = field(default_factory=list)
    texts: list = field(default_factory=list)
    build_stats: Optional[BuildStats] = None


# --- corpus ------------------------------------------------------------------

def _artifact_text(kind: str, rec: dict) -> str:
    """The text the dense arm embeds for one artifact. Each artifact type stores
    its body in different fields; this pulls the human-readable content into one
    string (empty -> nothing worth embedding)."""
    if kind == "slack":
        msg = (rec.get("Message") or {}).get("User") or {}
        channel = (rec.get("Channel") or {}).get("name", "")
        return f"Slack #{channel} {msg.get('userId', '')}: {msg.get('text', '')}".strip()
    if kind == "documents":
        return "\n".join(
            s for s in (rec.get("type", ""), rec.get("content", ""), rec.get("feedback", ""))
            if s
        ).strip()
    if kind == "meeting_transcripts":
        return f"{rec.get('document_type', '')}\n{rec.get('transcript', '')}".strip()
    if kind == "meeting_chats":
        return rec.get("text", "")
    if kind == "urls":
        return f"{rec.get('description', '')} {rec.get('link', '')}".strip()
    if kind == "prs":
        reviews = " ".join(
            (r.get("comment") or "")
            for r in (rec.get("reviews") or [])
            if isinstance(r, dict)
        )
        return f"{rec.get('title', '')}\n{rec.get('summary', '')} {reviews}".strip()
    return ""


def _read_corpus(corpus_root) -> list:
    """Read the corpus into one whole artifact per document: {id, text}.

    Walks the product files only (the sole data this arm sees), keyed by each
    artifact's native id. Where an id repeats (in practice only within `urls`,
    whose id is the URL itself), the first occurrence wins, keeping the
    id->vector map 1:1.
    linked to: build_dense_index (embeds these docs)
    """
    root = Path(corpus_root)
    docs, seen = [], set()
    for pf in sorted((root / "products").glob("*.json")):
        data = json.loads(pf.read_text(encoding="utf-8"))
        for kind in ARTIFACT_TYPES:
            for rec in data.get(kind, []) or []:
                aid = rec.get("id")
                if aid is None or aid in seen:
                    continue
                seen.add(aid)
                docs.append({"id": aid, "text": _artifact_text(kind, rec)})
    return docs


# --- embed -------------------------------------------------------------------

def _embed(texts: list, input_type: str, batch: int = EMBED_BATCH) -> tuple:
    """Embed texts via nv-embedqa -> (matrix [n, d] float32 L2-normalised, calls,
    tokens, seconds).

    `input_type` is the model's asymmetric flag: "passage" for corpus docs,
    "query" for questions. `truncate="NONE"` so an over-long input errors loudly
    rather than being silently clipped — the design asserts 8192 ctx covers every
    artifact whole, and a violation should surface, not pass. Results are reordered
    by the API's `index` field so batch order can't scramble row->id alignment.
    """
    vecs, calls, tokens, secs = [], 0, 0, 0.0
    for i in range(0, len(texts), batch):
        chunk = [t or " " for t in texts[i:i + batch]]  # NIM rejects empty input
        t0 = time.perf_counter()
        resp = nim.post("/embeddings", {
            "model": EMBED_MODEL,
            "input": chunk,
            "input_type": input_type,
            "truncate": "NONE",
        })
        secs += time.perf_counter() - t0
        calls += 1
        tokens += int((resp.get("usage") or {}).get("total_tokens", 0) or 0)
        data = resp.get("data")
        if not data:
            raise RuntimeError(f"NIM /embeddings returned no data (keys={list(resp)})")
        # tolerant sort key so a malformed row surfaces as the loud RuntimeError below,
        # not a bare KeyError from the sort. (idx, not i — i is the batch offset above.)
        for d in sorted(data, key=lambda d: d.get("index", 0)):
            idx, emb = d.get("index"), d.get("embedding")
            if idx is None or not emb:
                raise RuntimeError(
                    f"NIM /embeddings row malformed (index={idx}, has_emb={bool(emb)})")
            vecs.append(emb)
    # dtype=float32 over ragged rows raises ValueError, so mismatched dims fail loud.
    mat = np.asarray(vecs, dtype=np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    mat /= norms
    return mat, calls, tokens, secs


# --- index -------------------------------------------------------------------

def build_dense_index(corpus, batch: int = EMBED_BATCH) -> Prepared:
    """prepare(): embed every corpus artifact (as "passage") and hold the
    normalised matrix. Runs once.

    `corpus` is either a path to the corpus root (read by this arm's own
    _read_corpus) or an already-read list of {id, text} dicts. Records a
    contract.BuildStats capturing the embedder's build-time calls / tokens / time.
    linked to: orchestrator.run_one_pipeline (called once); _read_corpus
    """
    t0 = time.perf_counter()
    docs = corpus if isinstance(corpus, list) else _read_corpus(corpus)
    ids = [d["id"] for d in docs]
    texts = [d["text"] for d in docs]

    nim.require_key()  # fail loud before embedding — no silent offline mode
    matrix, calls, tokens, model_s = _embed(texts, "passage", batch)

    build_stats = BuildStats(
        build_time_s=time.perf_counter() - t0,
        model=ModelUsage(calls, tokens, model_s),
        models=[EMBED_MODEL],
    )
    return Prepared(matrix=matrix, ids=ids, texts=texts, build_stats=build_stats)


def prepare_over_corpus(corpus) -> Prepared:
    """Uniform prepare entry the orchestrator drives. Thin alias over
    build_dense_index; the returned Prepared carries .build_stats."""
    return build_dense_index(corpus)


# --- retrieve ----------------------------------------------------------------

def _qid_text(question) -> tuple:
    """(id, question_text) from a QuestionWithTruth, dict, (id, text) tuple, or a
    bare string. Reads ONLY id + question — truth fields are never touched."""
    if hasattr(question, "question") and hasattr(question, "id"):
        return question.id, question.question
    if isinstance(question, dict):
        return question.get("id", ""), question.get("question", "")
    if isinstance(question, (tuple, list)) and len(question) == 2:
        return question[0], question[1]
    return "", str(question)


def retrieve_top_k_units(question, prepared: Prepared, k: int = DEFAULT_TOP_K) -> tuple:
    """Embed the question (as "query"), exact brute-force cosine top-k over the
    corpus matrix -> (unit dicts {id, text, score, rank} best first, ModelUsage for
    the query embed — this arm's own retrieval-time model cost).
    linked to: unit_to_artifact_id + gather_unit_text (consume the hits)
    """
    _, text = _qid_text(question)
    if k <= 0 or not prepared.ids or not text.strip():
        return [], ModelUsage()
    k = min(k, len(prepared.ids))
    qmat, calls, tokens, secs = _embed([text], "query", batch=1)
    scores = prepared.matrix @ qmat[0]  # cosine — both sides L2-normalised
    top = np.argsort(-scores)[:k]
    units = [
        {
            "id": prepared.ids[i],
            "text": prepared.texts[i],
            "score": float(scores[i]),
            "rank": rank,
        }
        for rank, i in enumerate(int(j) for j in top)
    ]
    return units, ModelUsage(calls, tokens, secs)


def unit_to_artifact_id(unit: dict) -> str:
    """Native artifact id off the unit. Fills ArmOutput.context_ids (same id space
    the artefact resolves to and the gold citations use)."""
    return unit["id"]


def gather_unit_text(units: list) -> list:
    """Collect the units' text. Fills ArmOutput.contexts + feeds the generator."""
    return [u["text"] for u in units]


# --- answer ------------------------------------------------------------------

def _unpack_generation(result, elapsed_s: float) -> tuple:
    """Normalise a generator's return into (answer, calls, tokens, time_s).

    Accepts: a bare answer string; a (answer, telemetry_dict) pair; or an object
    exposing .answer plus optional .calls/.tokens/.time. Missing telemetry falls
    back to calls=1, tokens=0, time=the measured wall time of the call."""
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], dict):
        answer, tel = result
        return (
            answer,
            int(tel.get("calls", 1)),
            int(tel.get("tokens", 0)),
            float(tel.get("time", elapsed_s)),
        )
    if hasattr(result, "answer"):
        return (
            result.answer,
            int(getattr(result, "calls", 1)),
            int(getattr(result, "tokens", 0)),
            float(getattr(result, "time", elapsed_s)),
        )
    return str(result), 1, 0, elapsed_s


def answer_one_question(
    question, prepared: Prepared, generate: Optional[Generator], k: int = DEFAULT_TOP_K
) -> ArmOutput:
    """ENTRY: retrieve_top_k -> ids + text -> generate -> ArmOutput.

    `generate` is the SHARED generator injected by the orchestrator so generation
    is identical across arms. If None (retrieval-only smoke), the answer is left
    empty and model telemetry is zero.
    linked to: orchestrator; shared `generate`; returns contract.ArmOutput
    """
    _, text = _qid_text(question)

    t0 = time.perf_counter()
    units, retrieval_usage = retrieve_top_k_units(question, prepared, k)
    search_time_s = time.perf_counter() - t0

    context_ids = [unit_to_artifact_id(u) for u in units]
    contexts = gather_unit_text(units)

    if generate is None:
        answer, model_calls, model_tokens, model_time_s = "", 0, 0, 0.0
    else:
        g0 = time.perf_counter()
        result = generate(text, contexts)
        answer, model_calls, model_tokens, model_time_s = _unpack_generation(
            result, time.perf_counter() - g0
        )

    return ArmOutput(
        answer=answer,
        contexts=contexts,
        context_ids=context_ids,
        search_time_s=search_time_s,
        generator=ModelUsage(model_calls, model_tokens, model_time_s),
        retrieval=retrieval_usage,  # the query-embed cost
    )

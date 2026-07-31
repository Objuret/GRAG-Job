"""vector.py — dense baseline (embeddings + cosine), i.e. naive RAG.

Why it's here: the dense-retrieval control arm — the standard vector RAG the
artefact's structured retrieval is claimed to beat. It reads the corpus and
builds its own embedding index over it.

In -> out: question -> precomputed query vector (by id) -> cosine top-k artifacts
-> shared generator -> answer. Questions are embedded offline by embed_questions.py.

Provenance (the method's lineage, not an eval target): dense passage retrieval in
the Sentence-BERT (Reimers & Gurevych 2019) / DPR (Karpukhin et al. 2020) line,
benchmarked on BEIR (Thakur et al. 2021). The search mirrors BEIR's reference
`evaluate_sbert.py` — `DenseRetrievalExactSearch` with `cos_sim`: exact cosine of
the query against every corpus vector, which is exactly the brute-force matrix-dot
below. These citations are the PROVENANCE of the method only — BEIR is NOT an
evaluation target; every arm (artifact / lucene / vector) is scored solely by RAGAS.

Two things moved on from the textbook default. The embedder is
nvidia/llama-nemotron-embed-1b-v2 on NVIDIA NIM — a multilingual (26 languages
incl. Swedish), English-strong, 8192-token QA-retrieval embedder — NOT the
English-only, 256-token all-MiniLM-L6-v2 via
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

References (provenance of the method; none is an evaluation target — every arm is
scored solely by RAGAS):
  - Reimers, N. & Gurevych, I. (2019). Sentence-BERT: Sentence Embeddings using
    Siamese BERT-Networks. EMNLP 2019. arXiv:1908.10084 — the dense bi-encoder
    sentence-embedding line this arm's encoder descends from.
  - Karpukhin, V. et al. (2020). Dense Passage Retrieval for Open-Domain Question
    Answering. EMNLP 2020. arXiv:2004.04906 — foundational dense passage retrieval.
  - Thakur, N., Reimers, N., Rücklé, A., Srivastava, A. & Gurevych, I. (2021).
    BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of IR Models.
    arXiv:2104.08663 — the benchmark whose reference evaluate_sbert.py this arm's
    brute-force cos_sim DenseRetrievalExactSearch mirrors.
  - Embedder: nvidia/llama-nemotron-embed-1b-v2 (NVIDIA NIM) — an 8192-token,
    multilingual (26 languages incl. Swedish) QA-retrieval bi-encoder. Model card:
    https://build.nvidia.com/nvidia/llama-nemotron-embed-1b-v2/modelcard ;
    https://huggingface.co/nvidia/llama-nemotron-embed-1b-v2
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import httpx
import numpy as np
from tqdm import tqdm

import nim
from contract import ArmOutput, BuildStats, ModelUsage, generator_usage_from_nim, unpack_generation

EMBED_MODEL = "nvidia/llama-nemotron-embed-1b-v2"
# NIM hosted /embeddings caps: 2048 inputs AND 300k tokens per request. Batch to
# the input cap — at ~73 tokens/artifact that lands near 150k tokens, well under
# the token cap. _embed_request splits on a too-large rejection, so a batch that
# does trip the token cap (or a single over-8192-token artifact) self-resolves and
# fails loud only at size 1. One rate-limited request embeds up to 2048 artifacts.
EMBED_BATCH = 2048
DEFAULT_TOP_K = 10

# Content-addressed embedding cache. Building the index embeds the whole corpus
# (~600 rate-limited requests at the old batch, ~19 here); caching the matrix
# keyed by (model, ids, texts) makes every re-run over an unchanged corpus instant.
CACHE_DIR = Path(__file__).resolve().parent.parent / "output" / "embed_cache"

# Question (query) vectors, precomputed once by embed_questions.py and looked up
# here by question id. ids[i] <-> matrix row i; the arm never embeds a question at
# retrieval time. A new embedder (different EMBED_MODEL) means re-running that script.
QUERY_VECS_PATH = Path(__file__).resolve().parent.parent / "data" / "question_query_vecs.npz"

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
    L2-normalised corpus matrix (so cosine == dot) + ids/texts + the BuildStats for
    run provenance + query_vecs (precomputed question vectors, looked up by id)."""

    matrix: "np.ndarray"
    ids: list = field(default_factory=list)
    texts: list = field(default_factory=list)
    build_stats: Optional[BuildStats] = None
    query_vecs: dict = field(default_factory=dict)  # question id -> precomputed query vector


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

def _embed_request(texts: list, input_type: str) -> tuple:
    """Embed one batch in a single NIM call -> (embeddings in input order, calls,
    tokens_in, tokens_out, seconds).

    `truncate="NONE"` so an over-long input errors loudly rather than being
    silently clipped. On a too-large rejection (NIM 4xx — the batch over the
    300k-token cap, or a single artifact over 8192 tokens) the batch is split in
    half and each half retried; a size-1 batch that still fails re-raises, so an
    over-long artifact surfaces loud instead of being dropped. Rows are reordered
    by the API's `index` field so batch order can't scramble row->id alignment.
    """
    try:
        t0 = time.perf_counter()
        resp = nim.post("/embeddings", {
            "model": EMBED_MODEL,
            "input": [t or " " for t in texts],  # NIM rejects empty input
            "input_type": input_type,
            "truncate": "NONE",
        })
        secs = time.perf_counter() - t0
    except httpx.HTTPStatusError as e:
        # A size rejection is 400/413/422 — split and retry, bottoming out at a
        # single artifact that re-raises loud. 401/403/404 are auth / permission /
        # endpoint errors that no split can fix; raise at once, else the recursion
        # fans the same error across a whole binary tree of rate-capped calls.
        if e.response.status_code in (401, 403, 404) or len(texts) == 1:
            raise
        mid = len(texts) // 2
        lo, ro = _embed_request(texts[:mid], input_type), _embed_request(texts[mid:], input_type)
        return lo[0] + ro[0], lo[1] + ro[1], lo[2] + ro[2], lo[3] + ro[3], lo[4] + ro[4]

    tokens_in, tokens_out = generator_usage_from_nim(resp.get("usage"))
    data = resp.get("data")
    if not data:
        raise RuntimeError(f"NIM /embeddings returned no data (keys={list(resp)})")
    # tolerant sort key so a malformed row surfaces as the loud RuntimeError below,
    # not a bare KeyError from the sort.
    embs = []
    for d in sorted(data, key=lambda d: d.get("index", 0)):
        idx, emb = d.get("index"), d.get("embedding")
        if idx is None or not emb:
            raise RuntimeError(
                f"NIM /embeddings row malformed (index={idx}, has_emb={bool(emb)})")
        embs.append(emb)
    return embs, 1, tokens_in, tokens_out, secs


def _embed(texts: list, input_type: str, batch: int = EMBED_BATCH) -> tuple:
    """Embed texts via nv-embedqa -> (matrix [n, d] float32 L2-normalised, calls,
    tokens_in, tokens_out, seconds).

    `input_type` is the model's asymmetric flag: "passage" for corpus docs,
    "query" for questions. Batches up to `batch` inputs per request (the NIM input
    cap); _embed_request handles the token cap and over-long inputs by splitting.
    calls/tokens_in/tokens_out/seconds count SUCCESSFUL embedding requests only — a batch
    rejected for size is a sizing probe that embeds nothing, so it is not counted.
    """
    vecs, calls, tokens_in, tokens_out, secs = [], 0, 0, 0, 0.0
    starts = range(0, len(texts), batch)
    # A live bar for the multi-batch corpus build; disabled for a single-text query.
    for i in tqdm(starts, desc="embedding", unit="batch", disable=len(texts) <= batch):
        e, c, ti, to, s = _embed_request(texts[i:i + batch], input_type)
        vecs.extend(e)
        calls += c
        tokens_in += ti
        tokens_out += to
        secs += s
    # dtype=float32 over ragged rows raises ValueError, so mismatched dims fail loud.
    mat = np.asarray(vecs, dtype=np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    mat /= norms
    return mat, calls, tokens_in, tokens_out, secs


# --- index -------------------------------------------------------------------

def _cache_path(ids: list, texts: list) -> Path:
    """Content-addressed cache file for this index: any change to the model, the
    ids, or the texts yields a new key and forces a re-embed. Each field is
    length-prefixed so no id/text byte sequence can forge a field boundary and
    alias a different corpus onto the same key."""
    h = hashlib.sha256(EMBED_MODEL.encode())
    h.update(len(ids).to_bytes(8, "big"))
    for i, t in zip(ids, texts):
        for b in (f"{type(i).__name__}:{i!r}".encode(), t.encode()):
            h.update(len(b).to_bytes(8, "big"))
            h.update(b)
    return CACHE_DIR / f"{EMBED_MODEL.split('/')[-1]}_{h.hexdigest()[:16]}.npz"


def build_dense_index(corpus, batch: int = EMBED_BATCH) -> Prepared:
    """prepare(): embed every corpus artifact (as "passage") and hold the
    normalised matrix. Runs once; the matrix is cached to disk keyed by corpus
    content, so a re-run over an unchanged corpus loads instead of re-embedding.

    `corpus` is either a path to the corpus root (read by this arm's own
    _read_corpus) or an already-read list of {id, text} dicts. Records a
    contract.BuildStats capturing the embedder's build-time calls / tokens / time;
    the cached copy preserves that first-build provenance across loads.
    linked to: orchestrator.run_one_pipeline (called once); _read_corpus
    """
    t0 = time.perf_counter()
    docs = corpus if isinstance(corpus, list) else _read_corpus(corpus)
    ids = [d["id"] for d in docs]
    texts = [d["text"] for d in docs]
    if not texts:
        raise RuntimeError(f"dense index: corpus is empty (corpus={corpus!r})")

    cache = _cache_path(ids, texts)
    if cache.is_file():
        z = np.load(cache, allow_pickle=True)
        stats = z["build_stats"]
        bt = float(stats[0])
        calls = int(stats[1])
        if len(stats) == 4:
            tokens_in, tokens_out, model_s = int(stats[2]), 0, float(stats[3])
        else:
            tokens_in, tokens_out, model_s = int(stats[2]), int(stats[3]), float(stats[4])
        return Prepared(
            matrix=z["matrix"], ids=list(z["ids"]), texts=list(z["texts"]),
            build_stats=BuildStats(
                build_time_s=bt,
                model=ModelUsage(calls=calls, tokens_in=tokens_in, tokens_out=tokens_out,
                                 time_s=model_s),
                models=[EMBED_MODEL]),
        )

    nim.require_key()  # fail loud before embedding — no silent offline mode
    matrix, calls, tokens_in, tokens_out, model_s = _embed(texts, "passage", batch)

    build_stats = BuildStats(
        build_time_s=time.perf_counter() - t0,
        model=ModelUsage(calls=calls, tokens_in=tokens_in, tokens_out=tokens_out,
                         time_s=model_s),
        models=[EMBED_MODEL],
    )
    # Atomic publish: write a temp file then rename, so a concurrent reader gating
    # on cache.is_file() never loads a half-written .npz. os.replace is atomic on
    # one filesystem; the temp lives in CACHE_DIR, so it always is. Passing the
    # open handle to np.savez avoids its ".npz" suffix rewriting of the path.
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=CACHE_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            np.savez(
                f, matrix=matrix,
                ids=np.array(ids, dtype=object), texts=np.array(texts, dtype=object),
                build_stats=np.array([build_stats.build_time_s, calls, tokens_in, tokens_out,
                                      model_s], dtype=object),
            )
        os.replace(tmp, cache)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    # The construction cost, saved once beside the embeddings as readable JSON.
    (CACHE_DIR / f"{cache.stem}.cost.json").write_text(
        json.dumps({"model": EMBED_MODEL, "calls": calls,
                    "tokens_in": tokens_in, "tokens_out": tokens_out,
                    "build_time_s": build_stats.build_time_s}, indent=2),
        encoding="utf-8")
    return Prepared(matrix=matrix, ids=ids, texts=texts, build_stats=build_stats)


def prepare_over_corpus(corpus) -> Prepared:
    """Uniform prepare entry the orchestrator drives: build the corpus index and
    attach the precomputed question vectors (loaded once here, before the answer
    threads spawn). The returned Prepared carries .build_stats + .query_vecs."""
    prepared = build_dense_index(corpus)
    prepared.query_vecs = load_query_vecs()
    return prepared


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


def load_query_vecs() -> dict:
    """Load the precomputed question vectors -> {id: vector [d] float32 L2-normalised}.
    Raises if the file is absent (run embed_questions.py first — no silent fallback).
    linked to: embed_questions.main (writes the file); prepare_over_corpus (loads it)
    """
    if not QUERY_VECS_PATH.is_file():
        raise FileNotFoundError(
            f"no precomputed question vectors at {QUERY_VECS_PATH}; "
            f"run `python embed_questions.py` (from v3/) before the vector arm")
    z = np.load(QUERY_VECS_PATH, allow_pickle=True)
    return {qid: vec for qid, vec in zip(z["ids"], z["matrix"])}


def retrieve_top_k_units(question, prepared: Prepared, k: int = DEFAULT_TOP_K) -> tuple:
    """Look up the question's precomputed query vector by id, exact brute-force cosine
    top-k over the corpus matrix -> (unit dicts {id, text, score, rank} best first,
    ModelUsage — zero, since the query embed happens offline in embed_questions.py).
    An id with no precomputed vector raises (the set was embedded under a different
    question set or embedder — re-run embed_questions.py).
    linked to: unit_to_artifact_id + gather_unit_text (consume the hits)
    """
    qid, text = _qid_text(question)
    if k <= 0 or not prepared.ids or not text.strip():
        return [], ModelUsage()
    k = min(k, len(prepared.ids))
    qvec = prepared.query_vecs.get(qid)
    if qvec is None:
        raise KeyError(
            f"no precomputed query vector for question id {qid!r}; "
            f"re-run embed_questions.py over the current question set")
    scores = prepared.matrix @ qvec  # cosine — both sides L2-normalised
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
    return units, ModelUsage()  # query embed is offline; no retrieval-time call


def unit_to_artifact_id(unit: dict) -> str:
    """Native artifact id off the unit. Fills ArmOutput.context_ids (same id space
    the artefact resolves to and the gold citations use)."""
    return unit["id"]


def gather_unit_text(units: list) -> list:
    """Collect the units' text. Fills ArmOutput.contexts + feeds the generator."""
    return [u["text"] for u in units]


# --- answer ------------------------------------------------------------------

def _unpack_generation(result, elapsed_s: float) -> tuple:
    """Normalise a generator's return into (answer, ModelUsage)."""
    return unpack_generation(result, elapsed_s)


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
    # search_time_s = the cosine/rank only. The query-embed wall (network + rate-cap
    # wait) lives in `retrieval`, so subtracting it keeps this comparable to lucene's
    # pure in-process search time instead of being dominated by the model call.
    search_time_s = (time.perf_counter() - t0) - retrieval_usage.time_s

    context_ids = [unit_to_artifact_id(u) for u in units]
    contexts = gather_unit_text(units)

    if generate is None:
        answer, gen_usage = "", ModelUsage()
    else:
        g0 = time.perf_counter()
        result = generate(text, contexts)
        answer, gen_usage = _unpack_generation(result, time.perf_counter() - g0)

    return ArmOutput(
        answer=answer,
        contexts=contexts,
        context_ids=context_ids,
        search_time_s=search_time_s,
        generator=gen_usage,
        retrieval=retrieval_usage,  # the query-embed cost
    )

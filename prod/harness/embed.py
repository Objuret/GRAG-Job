from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np

from harness import capture
from harness.progress import progress, say

EMBED_MODEL = "nvidia/llama-nemotron-embed-1b-v2"

EMBED_REVISION = "113abe4acafa848e77ead9c0623205e511932348"

EMBED_DEVICE = "cpu"

EMBED_DTYPE = "float32"

EMBED_PREFIX = {"query": "query: ", "passage": "passage: "}

EMBED_BATCH = 1

QUERY_VECS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "question_query_vecs.npz"

_model = None

_model_lock = threading.Lock()

_encode_lock = threading.Lock()

LOAD_S = None

_totals = {"requests": 0, "texts": 0, "tokens_in": 0, "lock_wait_s": 0.0, "encode_s": 0.0}
_totals_lock = threading.Lock()


def take_totals() -> dict:
    """Every embed request since the last take, summed; an evaluation reads it per leg."""
    with _totals_lock:
        out = dict(_totals)
        for k in _totals:
            _totals[k] = 0 if isinstance(_totals[k], int) else 0.0
    return out


def _embedder():
    global _model, LOAD_S
    with _model_lock:
        if _model is None:
            say(f"embedder: loading {EMBED_MODEL} @ {EMBED_REVISION[:12]} on "
                f"{EMBED_DEVICE} ({EMBED_DTYPE}) — first use")
            t0 = time.perf_counter()
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(
                EMBED_MODEL, revision=EMBED_REVISION, device=EMBED_DEVICE,
                trust_remote_code=True, model_kwargs={"dtype": EMBED_DTYPE})
            LOAD_S = time.perf_counter() - t0
            say(f"embedder: ready in {LOAD_S:.0f}s "
                f"({_model.get_embedding_dimension()} dim, "
                f"{_model.max_seq_length}-token context)")
    return _model

def _embed_request(texts: list, input_type: str) -> tuple:
    if input_type not in EMBED_PREFIX:
        raise ValueError(f"input_type must be one of {sorted(EMBED_PREFIX)}, "
                         f"got {input_type!r}")
    model = _embedder()
    prefixed = [EMBED_PREFIX[input_type] + (t or " ") for t in texts]
    started_at = capture.now()
    t0 = time.perf_counter()
    with _encode_lock:
        t1 = time.perf_counter()
        lengths = [len(ids) for ids in model.tokenizer(
            prefixed, add_special_tokens=True, truncation=False)["input_ids"]]
        over = [(i, n) for i, n in enumerate(lengths) if n > model.max_seq_length]
        if over:
            raise RuntimeError(
                f"{len(over)} of {len(texts)} inputs are past the embedder's "
                f"{model.max_seq_length}-token context (first: index {over[0][0]} at "
                f"{over[0][1]} tokens)")
        embs = model.encode(prefixed, batch_size=EMBED_BATCH, convert_to_numpy=True,
                            show_progress_bar=False)
        t2 = time.perf_counter()
    with _totals_lock:
        _totals["requests"] += 1
        _totals["texts"] += len(prefixed)
        _totals["tokens_in"] += sum(lengths)
        _totals["lock_wait_s"] += t1 - t0
        _totals["encode_s"] += t2 - t1
    # kept with the question or evaluation cell that asked: what was embedded, how, how long
    capture.record({"kind": "embed", "model": EMBED_MODEL, "revision": EMBED_REVISION,
                    "device": EMBED_DEVICE, "dtype": EMBED_DTYPE, "input_type": input_type,
                    "prefix": EMBED_PREFIX[input_type], "batch": EMBED_BATCH,
                    "n_texts": len(prefixed), "texts": list(texts), "tokens": lengths,
                    "tokens_in": sum(lengths), "started_at": started_at,
                    "finished_at": capture.now(), "lock_wait_s": t1 - t0, "encode_s": t2 - t1})
    return (embs.tolist(), -(-len(prefixed) // EMBED_BATCH), sum(lengths), 0,
            time.perf_counter() - t0)

def _embed(texts: list, input_type: str, batch: int = EMBED_BATCH,
           bar: bool = True) -> tuple:
    vecs, calls, tokens_in, tokens_out, secs = [], 0, 0, 0, 0.0
    starts = range(0, len(texts), batch)
    for i in (progress(starts, desc="embedding", unit="batch")
              if bar and len(texts) > batch else starts):
        e, c, ti, to, s = _embed_request(texts[i:i + batch], input_type)
        vecs.extend(e)
        calls += c
        tokens_in += ti
        tokens_out += to
        secs += s
    mat = np.asarray(vecs, dtype=np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    mat /= norms
    return mat, calls, tokens_in, tokens_out, secs

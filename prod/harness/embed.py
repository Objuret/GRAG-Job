from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import numpy as np

from harness import capture
from harness.progress import progress, say

EMBED_MODEL = "nvidia/llama-nemotron-embed-1b-v2"

EMBED_REVISION = "113abe4acafa848e77ead9c0623205e511932348"

# HERB_EMBED_DEVICE=cuda puts the embedder on the graphics card (the desktop's GTX 1080 Ti); a
# run whose arm or scoring asks the embedder refuses to start without it (`require_cuda`)
EMBED_DEVICE = os.environ.get("HERB_EMBED_DEVICE", "cpu")

EMBED_DTYPE = "float32"

EMBED_PREFIX = {"query": "query: ", "passage": "passage: "}

EMBED_BATCH = 1

QUERY_VECS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "question_query_vecs.npz"

# requests made once, not timed, before requests are timed alone: the number the measurements of
# corrections embed-gpu-time and judge-embed-gpu-time warmed up with (tools/measure_gpu_*.py)
WARM_REQUESTS = 20

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


def require_cuda(what: str) -> None:
    """Stops a start in which `what` asks the embedder unless the embedder is on a graphics card:
    every embedding time of a run is the card's (corrections embed-gpu-time and
    judge-embed-gpu-time put them there after the run)."""
    if not EMBED_DEVICE.startswith("cuda"):
        raise RuntimeError(f"{what} asks the embedder and HERB_EMBED_DEVICE is {EMBED_DEVICE!r}: "
                           "a run embeds on a graphics card only (HERB_EMBED_DEVICE=cuda)")
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError(f"{what} asks the embedder and HERB_EMBED_DEVICE is {EMBED_DEVICE!r}, "
                           "but torch sees no graphics card")


def time_alone(records: list) -> list:
    """Each embed record's request made again with the same texts in the same input type, one
    after the other in this process with nothing else under way, after the first WARM_REQUESTS of
    them made once and not timed, as the measurements of corrections embed-gpu-time and
    judge-embed-gpu-time made them. Returns, per record, the record of the request made again;
    a request whose texts now give other tokens stops it. The requests are not added to what
    `take_totals` reads."""
    with _totals_lock:
        before = dict(_totals)
    try:
        for r in records[:WARM_REQUESTS]:
            _embed_request(r["texts"], r["input_type"])
        out = []
        for r in records:
            cap, token = capture.start()
            try:
                _embed_request(r["texts"], r["input_type"])
            finally:
                capture.stop(token)
            again = cap.close()["calls"][-1]
            if again["tokens_in"] != r.get("tokens_in"):
                raise RuntimeError(f"an embed request made again gives {again['tokens_in']} tokens, "
                                   f"its record {r.get('tokens_in')}")
            out.append(again)
    finally:
        with _totals_lock:
            _totals.update(before)
    return out


def retimed(record: dict, again: dict) -> dict:
    """The record with the device, encode_s and lock_wait_s of its request made alone
    (`time_alone`); those it was made with while the start ran are kept under in_run."""
    return {**record, "device": again["device"], "encode_s": again["encode_s"],
            "lock_wait_s": again["lock_wait_s"],
            "in_run": {k: record.get(k) for k in ("device", "encode_s", "lock_wait_s")}}

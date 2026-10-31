from __future__ import annotations

import hashlib
import json
import os
import socket
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from harness import char_budget
from harness.char_budget import cut_at_budget
from harness.contract import ArmOutput, BuildStats, ModelUsage, unpack_generation
from harness.fields import sub, whole
from harness.progress import progress, say
from harness.embed import (EMBED_MODEL, EMBED_REVISION, EMBED_DEVICE, EMBED_DTYPE,
                           EMBED_PREFIX, EMBED_BATCH, QUERY_VECS_PATH, _embedder,
                           _embed_request, _embed)
from harness.provenance import file_digest
from harness.record_text import ARTIFACT_TYPES, FORM, metadata_records, record_text, units_digest

DEFAULT_TOP_K = 10

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "embed_cache"

# the arm has no switches of its own
RETRIEVAL_FLAGS: dict = {}

Generator = Callable[[str, list], object]

# a delivered text is one record: contexts and context_ids go one to one, but for the text
# cut at the budget
UNIT_IS_ONE_RECORD = True

# what was left out of the data this arm rests on, and on whose word (harness.fields, FIELDS.md)
LEFT_OUT = [
    "The metadata file salesforce_team.json: it is not embedded; the index holds the records of "
    "the product files and the employees and customers of employee.json and customers_data.json. "
    "His words: \"yeah, so, dont fucking talk about or use it then, if its not a current file, why "
    "are you talking about it?\" (2026-10-31).",
]

# the words for what only this arm writes into a run folder (harness.fields, FIELDS.md)
FIELDS = {
    "meta": sub("What the arm recorded about this question's ranking.", {
        "char_budget": char_budget.FIELDS,
        "ranking": sub("The ranking the delivered texts were taken from.", {
            "n_units": "How many units the index holds.",
            "n_ranked": "How many of them were ranked: all of them.",
            "scores": "The cosine between the question's vector and each delivered text's "
                      "vector, in delivered order.",
            "next_score": "The cosine of the first unit that was not delivered; empty when none "
                          "was left.",
        }),
    }),
    "index": sub("What the arm's index is.", {
        "units": "How many units the index holds. A unit is one record of the corpus: a record "
                 "of a product file, or an employee or a customer of the metadata files.",
        "text_chars": "The characters of all unit texts together.",
        "unit_text": "The form a record is written in to make its unit's text, and where that "
                     "form is from.",
        "units_sha256": "One sha256 over all units in index order: per unit the id and then the "
                        "text, each as UTF-8 behind its byte length written as 8 bytes, big end "
                        "first. Two runs with the same value ran on the same units.",
        "matrix_shape": "The vectors: how many, and how many numbers each has.",
        "matrix_dtype": "The number type of the vectors.",
        "matrix_bytes": "Their size in memory.",
        "cache_file": "The stored file the vectors were read from, as a path on the machine "
                      "that ran it.",
        "cache_file_bytes": "Its size.",
        "cache_file_sha256": "Its sha256, which identifies the vectors.",
        "cache_cost_note": whole("What making those vectors cost and on which machine, as noted "
                                 "beside the stored file when it was made: calls (requests to the "
                                 "embedder), batch (texts in a request), tokens, build_time_s and "
                                 "how it was read (build_time_note), max_seq_length (the most "
                                 "tokens a text may have) and how many units were longer, the "
                                 "device, the machine and the software. When the vectors are a "
                                 "stored file's vectors, kept as they are, with the vectors of "
                                 "the units after them appended, the calls, tokens and "
                                 "build_time_s are those of the two together; extends names the "
                                 "stored file (its sha256, how many units it holds and its own "
                                 "note) and appended gives the appended units' own count, calls, "
                                 "tokens, seconds, device, machine and software."),
        "embedder_warm_s": "Seconds the embedder took for one empty request before the first "
                           "question, so that no question pays for its loading.",
        "question_embedding": "When and how a question is embedded.",
    }),
    "retrieval_flags": sub("The arm's own switches. The arm has none, so this is empty.", {}),
}


@dataclass
class Prepared:

    matrix: "np.ndarray"
    ids: list = field(default_factory=list)
    texts: list = field(default_factory=list)
    build_stats: Optional[BuildStats] = None
    cache_file: Optional[str] = None
    warm_s: Optional[float] = None


def _read_corpus(corpus_root) -> list:
    """One unit per record, as lucene's: the records of the product files, then the employees and
    customers of the metadata files (`metadata_records`), each with its own id and its
    record_text."""
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
                docs.append({"id": aid, "text": record_text(kind, rec)})

    products = len(docs)
    for kind, rid, rec in metadata_records(root):
        if rid in seen:
            raise RuntimeError(f"the {kind} record {rid!r} has the id of another unit: two units "
                               "would share one id")
        seen.add(rid)
        docs.append({"id": rid, "text": record_text(kind, rec)})
    print(f"vector: {products} product records + {len(docs) - products} employees and customers",
          flush=True)
    return docs


def _cache_path(ids: list, texts: list) -> Path:
    h = hashlib.sha256(EMBED_MODEL.encode())
    h.update(len(ids).to_bytes(8, "big"))
    for i, t in zip(ids, texts):
        for b in (f"{type(i).__name__}:{i!r}".encode(), t.encode()):
            h.update(len(b).to_bytes(8, "big"))
            h.update(b)
    return CACHE_DIR / f"{EMBED_MODEL.split('/')[-1]}_{h.hexdigest()[:16]}.npz"


def _build_entry(calls, tokens_in, tokens_out, seconds, device, not_recorded=None) -> dict:
    """The embedder's one entry in build_stats. Its requests run one after the other, so their
    seconds added are the start to end of its work. `not_recorded` carries how the stored file's
    own note says its seconds were read, where no timer covered all of it."""
    return {"kind": "embed", "model": EMBED_MODEL,
            "what": "every unit of the corpus embedded in passage mode, for the stored vectors",
            "calls": calls, "tokens_in": tokens_in, "tokens_out": tokens_out,
            "seconds_summed_per_call": None, "seconds_elapsed": seconds, "device": device,
            "not_recorded": not_recorded}


def _seconds_note(note: dict) -> str | None:
    """What the stored file's cost note says of how its seconds were read, when no one timer
    covered the whole making of it."""
    said = note.get("build_time_note")
    return None if not said else f"no one timer covered all of it; the cost note says: {said}"


def _stats(z) -> tuple:
    """A stored file's build_stats: build time, calls, tokens in, tokens out and the embedder's
    seconds. An older file holds no tokens out."""
    stats = z["build_stats"]
    if len(stats) == 4:
        return float(stats[0]), int(stats[1]), int(stats[2]), 0, float(stats[3])
    return float(stats[0]), int(stats[1]), int(stats[2]), int(stats[3]), float(stats[4])


def _device_name() -> str:
    """The device the embedder runs on: a graphics card by its own name, else EMBED_DEVICE."""
    if EMBED_DEVICE.startswith("cuda"):
        import torch
        return torch.cuda.get_device_name(torch.device(EMBED_DEVICE))
    return EMBED_DEVICE


def _made_with(batch: int) -> dict:
    """The settings vectors are made with in passage mode: what a stored file's cost note must
    record the same for its vectors to be extended."""
    return {"model": EMBED_MODEL, "revision": EMBED_REVISION, "mode": "passage",
            "prefix": EMBED_PREFIX["passage"], "dtype": EMBED_DTYPE, "batch": batch}


def _machine() -> dict:
    """When, on which machine and with which software vectors were made, for a cost note."""
    from importlib.metadata import PackageNotFoundError, version
    out = {"made_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "host": socket.gethostname(), "python": sys.version.split()[0]}
    for name in ("torch", "sentence_transformers", "transformers"):
        try:
            out[name] = version(name)
        except PackageNotFoundError:
            out[name] = None
    return out


def _save(cache: Path, matrix, ids: list, texts: list, stats: list, note: dict) -> None:
    """The vectors with their units and build_stats written to `cache` through a file beside it,
    and the cost note beside them."""
    cache.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=cache.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            np.savez(
                f, matrix=matrix,
                ids=np.array(ids, dtype=object), texts=np.array(texts, dtype=object),
                build_stats=np.array(stats, dtype=object),
            )
        os.replace(tmp, cache)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    (cache.parent / f"{cache.stem}.cost.json").write_text(json.dumps(note, indent=2),
                                                          encoding="utf-8")


def _stored_start(ids: list, texts: list):
    """The stored file to extend: of the files in CACHE_DIR, the one whose units, ids and texts in
    order, are exactly the first n units of `ids` and `texts`, the most of them, n below all.
    (path, n), or None when no file holds such a start."""
    best = None
    for path in sorted(CACHE_DIR.glob("*.npz")):
        with np.load(path, allow_pickle=True) as z:
            if not {"matrix", "ids", "texts", "build_stats"} <= set(z.files):
                continue
            held = z["ids"]
            n = len(held)
            if n <= (best[1] if best else 0) or n >= len(ids) or list(held) != ids[:n]:
                continue
            if list(z["texts"]) != texts[:n]:
                continue
        best = (path, n)
    return best


def _extend(stored: Path, n: int, ids: list, texts: list, batch: int, cache: Path,
            t0: float) -> Prepared:
    """The vectors of all units: the stored file's rows for the first n units, kept bit for bit,
    and the rest embedded in passage mode with the settings the stored file's cost note records,
    appended after them. Refuses when the note is missing or records any other model, revision,
    mode, prefix, dtype or batch than the rest would be made with. The new file's build_stats and
    cost note hold the two parts together, and the note gives the appended part's own."""
    note_path = stored.parent / f"{stored.stem}.cost.json"
    if not note_path.is_file():
        raise RuntimeError(f"{stored.name} holds the first {n} of the {len(ids)} units but has no "
                           "cost note beside it, so the settings of its vectors are not known: "
                           "nothing is appended")
    note = json.loads(note_path.read_text(encoding="utf-8"))
    differ = {k: {"stored": note.get(k), "now": v} for k, v in _made_with(batch).items()
              if note.get(k) != v}
    if differ:
        raise RuntimeError(f"{stored.name} holds the first {n} of the {len(ids)} units, but the "
                           f"rest would be embedded with other settings than its vectors were: "
                           f"{differ}; nothing is appended")
    with np.load(stored, allow_pickle=True) as z:
        held = z["matrix"]
        bt0, calls0, tokens_in0, tokens_out0, model_s0 = _stats(z)
    if held.shape[0] != n:
        raise RuntimeError(f"{stored.name} holds {n} units but {held.shape[0]} vectors")
    say(f"vector: {stored.name} holds the vectors of the first {n} of the {len(ids)} units; "
        f"embedding the other {len(ids) - n}")

    rest, calls, tokens_in, tokens_out, model_s = _embed(texts[n:], "passage", batch)
    if rest.dtype != held.dtype or rest.shape[1:] != held.shape[1:]:
        raise RuntimeError(f"the appended vectors are {rest.dtype} {rest.shape[1:]}, the stored "
                           f"ones {held.dtype} {held.shape[1:]}: nothing is appended")
    matrix = np.concatenate([held, rest])
    part_s = time.perf_counter() - t0

    device = _device_name()
    both = (device if note.get("device") == device
            else f"{note.get('device')} (units 1-{n}), {device} (units {n + 1}-{len(ids)})")
    said = note.get("build_time_note")
    total = [bt0 + part_s, calls0 + calls, tokens_in0 + tokens_in, tokens_out0 + tokens_out,
             model_s0 + model_s]
    new_note = {
        **_made_with(batch), "calls": total[1], "tokens_in": total[2], "tokens_out": total[3],
        "build_time_s": total[0],
        "build_time_note": (f"two builds: units 1-{n} are the vectors of {stored.name}, made in "
                            f"{bt0:.1f} s" + (f" (its note: {said})" if said else "")
                            + f"; units {n + 1}-{len(ids)} were embedded and appended to them in "
                            f"{part_s:.1f} s, one timer from the start of that build to its "
                            "vectors"),
        "device": both, "unit_text": FORM, "units": len(ids),
        "units_sha256": units_digest(ids, texts),
        "extends": {"cache_file": stored.name, "cache_file_sha256": file_digest(stored),
                    "units": n, "cost_note": note},
        "appended": {"units": len(ids) - n, "first_unit": n + 1, "calls": calls,
                     "tokens_in": tokens_in, "tokens_out": tokens_out, "seconds_elapsed": model_s,
                     "build_time_s": part_s, "device": device, **_machine()},
    }
    _save(cache, matrix, ids, texts, total, new_note)
    return Prepared(
        matrix=matrix, ids=ids, texts=texts,
        build_stats=BuildStats(
            build_time_s=total[0],
            models=[_build_entry(total[1], total[2], total[3], total[4], both,
                                 _seconds_note(new_note))]),
        cache_file=str(cache))


def build_dense_index(corpus, batch: int = EMBED_BATCH) -> Prepared:
    """The vectors of every unit: read from the stored file of exactly these units when there is
    one; else a stored file's vectors of the first units, with the rest embedded and appended
    (`_extend`); else every unit embedded. A file made here is stored with its cost note."""
    t0 = time.perf_counter()
    docs = corpus if isinstance(corpus, list) else _read_corpus(corpus)
    ids = [d["id"] for d in docs]
    texts = [d["text"] for d in docs]
    if not texts:
        raise RuntimeError(f"dense index: corpus is empty (corpus={corpus!r})")

    cache = _cache_path(ids, texts)
    if cache.is_file():
        z = np.load(cache, allow_pickle=True)
        bt, calls, tokens_in, tokens_out, model_s = _stats(z)
        try:
            note = json.loads((CACHE_DIR / f"{cache.stem}.cost.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            note = {}
        return Prepared(
            matrix=z["matrix"], ids=list(z["ids"]), texts=list(z["texts"]),
            build_stats=BuildStats(
                build_time_s=bt,
                models=[_build_entry(calls, tokens_in, tokens_out, model_s,
                                     note.get("device"), _seconds_note(note))]),
            cache_file=str(cache),
        )

    stored = _stored_start(ids, texts)
    if stored is not None:
        return _extend(*stored, ids, texts, batch, cache, t0)

    matrix, calls, tokens_in, tokens_out, model_s = _embed(texts, "passage", batch)
    build_time_s = time.perf_counter() - t0

    device = _device_name()
    build_stats = BuildStats(
        build_time_s=build_time_s,
        models=[_build_entry(calls, tokens_in, tokens_out, model_s, device)],
    )
    _save(cache, matrix, ids, texts,
          [build_stats.build_time_s, calls, tokens_in, tokens_out, model_s],
          {**_made_with(batch), "calls": calls, "tokens_in": tokens_in, "tokens_out": tokens_out,
           "build_time_s": build_stats.build_time_s, "device": device, "unit_text": FORM,
           "units": len(ids), "units_sha256": units_digest(ids, texts), **_machine()})
    return Prepared(matrix=matrix, ids=ids, texts=texts, build_stats=build_stats,
                    cache_file=str(cache))


def prepare_over_corpus(corpus) -> Prepared:
    prepared = build_dense_index(corpus)
    # the question is embedded when it is asked, so the embedder is loaded and run once here:
    # the first question then pays for its own embedding only
    t0 = time.perf_counter()
    _embed([" "], "query", bar=False)
    prepared.warm_s = time.perf_counter() - t0
    return prepared


def index_info(prepared: Prepared) -> dict:
    """What the dense index is, for the run manifest."""
    cache = Path(prepared.cache_file) if prepared.cache_file else None
    cost = cache.with_suffix(".cost.json") if cache else None
    digest = None
    if cache and cache.is_file():
        h = hashlib.sha256()
        with cache.open("rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                h.update(block)
        digest = h.hexdigest()
    try:
        cost_note = json.loads(cost.read_text(encoding="utf-8")) if cost and cost.is_file() else None
    except (OSError, ValueError):
        cost_note = None
    return {"units": len(prepared.ids), "text_chars": sum(len(t) for t in prepared.texts),
            "unit_text": FORM, "units_sha256": units_digest(prepared.ids, prepared.texts),
            "matrix_shape": list(prepared.matrix.shape), "matrix_dtype": str(prepared.matrix.dtype),
            "matrix_bytes": int(prepared.matrix.nbytes),
            "cache_file": None if cache is None else str(cache),
            "cache_file_bytes": cache.stat().st_size if cache and cache.is_file() else None,
            "cache_file_sha256": digest, "cache_cost_note": cost_note,
            "embedder_warm_s": prepared.warm_s,
            "question_embedding": "at query time, local embedder, query mode"}


def _qid_text(question) -> tuple:
    if hasattr(question, "question") and hasattr(question, "id"):
        return question.id, question.question
    if isinstance(question, dict):
        return question.get("id", ""), question.get("question", "")
    if isinstance(question, (tuple, list)) and len(question) == 2:
        return question[0], question[1]
    return "", str(question)


def retrieve_top_k_units(question, prepared: Prepared, k: int = DEFAULT_TOP_K) -> tuple:
    qid, text = _qid_text(question)
    if k <= 0 or not prepared.ids or not text.strip():
        return [], ModelUsage()
    k = min(k, len(prepared.ids))
    # the question's vector is made here, timed and counted: it is part of what this run costs
    # (2026-10-08, "times, tokens, runtime, build cost ... ALL FUCKING DATAMETRICS")
    mat, calls, tokens_in, tokens_out, secs = _embed([text], "query", bar=False)
    usage = ModelUsage(calls=calls, tokens_in=tokens_in, tokens_out=tokens_out, time_s=secs,
                       attempts=calls, request_s=secs)
    qvec = mat[0]
    scores = prepared.matrix @ qvec
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
    return units, usage


def gather_unit_text(units: list) -> list:
    return [u["text"] for u in units]


def _unpack_generation(result, elapsed_s: float) -> tuple:
    return unpack_generation(result, elapsed_s)


def answer_one_question(
    question, prepared: Prepared, generate: Optional[Generator], k: int = DEFAULT_TOP_K,
    char_budget: Optional[int] = None,
) -> ArmOutput:
    _, text = _qid_text(question)

    t0 = time.perf_counter()
    depth = len(prepared.ids) if char_budget is not None else k
    units, retrieval_usage = retrieve_top_k_units(question, prepared, depth)
    search_time_s = (time.perf_counter() - t0) - retrieval_usage.time_s

    meta = None
    if char_budget is None:
        context_ids = [u["id"] for u in units]
        contexts = gather_unit_text(units)
    else:
        cut = cut_at_budget(((u["id"], u["text"]) for u in units), char_budget)
        contexts = cut.contexts
        context_ids = [u["id"] for u in units[:cut.kept]]
        meta = {"char_budget": {"budget": char_budget, "chars": cut.chars,
                                "kept": cut.kept, "boundary": cut.boundary,
                                "exhausted": cut.exhausted},
                # the cosine of every delivered context, in delivered order, and of the first
                # unit left out; every unit of the index is ranked
                "ranking": {"n_units": len(prepared.ids), "n_ranked": len(units),
                            "scores": [u["score"] for u in units[:len(contexts)]],
                            "next_score": (units[len(contexts)]["score"]
                                           if len(units) > len(contexts) else None)}}

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
        retrieval=retrieval_usage,
        meta=meta,
    )

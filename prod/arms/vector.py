from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from harness.char_budget import cut_at_budget
from harness.contract import ArmOutput, BuildStats, ModelUsage, unpack_generation
from harness.progress import progress, say
from harness.embed import (EMBED_MODEL, EMBED_REVISION, EMBED_DEVICE, EMBED_DTYPE,
                           EMBED_PREFIX, EMBED_BATCH, QUERY_VECS_PATH, _embedder,
                           _embed_request, _embed)
from harness.record_text import ARTIFACT_TYPES, FORM, record_text, units_digest

DEFAULT_TOP_K = 10

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "embed_cache"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    value = raw.strip()
    if value not in ("0", "1"):
        raise ValueError(f"{name} must be '0' or '1', got {raw!r}")
    return value == "1"


METADATA_ON = _env_bool("HERB_BASELINE_METADATA", False)

EMPLOYEE_JSON = "metadata/employee.json"
CUSTOMERS_JSON = "metadata/customers_data.json"
TEAM_JSON = "metadata/salesforce_team.json"

DIRECTORY_ID_PREFIX = "metadata::"

RETRIEVAL_FLAGS = {"HERB_BASELINE_METADATA": METADATA_ON}

Generator = Callable[[str, list], object]


@dataclass
class Prepared:

    matrix: "np.ndarray"
    ids: list = field(default_factory=list)
    texts: list = field(default_factory=list)
    build_stats: Optional[BuildStats] = None
    cache_file: Optional[str] = None
    warm_s: Optional[float] = None


def _team_leaders(nodes: list) -> list:
    out: list = []
    for node in nodes:
        rosters = [v for v in node.values() if isinstance(v, list)]
        if rosters:
            out.append(node)
        for roster in rosters:
            out.extend(_team_leaders(roster))
    return out


def _directory_records(root: Path) -> list:
    employees = json.loads((root / EMPLOYEE_JSON).read_text(encoding="utf-8"))
    customers = json.loads((root / CUSTOMERS_JSON).read_text(encoding="utf-8"))
    team = json.loads((root / TEAM_JSON).read_text(encoding="utf-8"))
    return (
        [("employee", rec["employee_id"], rec) for rec in employees.values()]
        + [("customers_data", rec["id"], rec) for rec in customers]
        + [("salesforce_team", rec["employee_id"], rec) for rec in _team_leaders(team)]
    )


def _directory_text(section: str, rec: dict) -> str:
    lines = [f"{section} directory"]
    for key, value in rec.items():
        if isinstance(value, list):
            value = ", ".join(f'{m["name"]} ({m["employee_id"]})' for m in value)
        lines.append(f"{key}: {value}")
    return "\n".join(lines)


def _read_corpus(corpus_root) -> list:
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

    artifacts = len(docs)
    if METADATA_ON:
        clash = sorted(i for i in seen if str(i).startswith(DIRECTORY_ID_PREFIX))
        if clash:
            raise RuntimeError(
                f"{len(clash)} artifact ids sit in the directory namespace "
                f"{DIRECTORY_ID_PREFIX!r} (e.g. {clash[:3]}) — a directory record "
                f"would be indistinguishable from an artifact")
        for section, native, rec in _directory_records(root):
            uid = f"{DIRECTORY_ID_PREFIX}{section}::{native}"
            if uid in seen:
                raise RuntimeError(f"duplicate directory unit id {uid!r}")
            seen.add(uid)
            docs.append({"id": uid, "text": _directory_text(section, rec)})
    print(f"vector: {artifacts} artifacts + {len(docs) - artifacts} directory records",
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


def build_dense_index(corpus, batch: int = EMBED_BATCH) -> Prepared:
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
            cache_file=str(cache),
        )

    matrix, calls, tokens_in, tokens_out, model_s = _embed(texts, "passage", batch)

    build_stats = BuildStats(
        build_time_s=time.perf_counter() - t0,
        model=ModelUsage(calls=calls, tokens_in=tokens_in, tokens_out=tokens_out,
                         time_s=model_s, attempts=calls, request_s=model_s),
        models=[EMBED_MODEL],
    )
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
    (CACHE_DIR / f"{cache.stem}.cost.json").write_text(
        json.dumps({"model": EMBED_MODEL, "calls": calls,
                    "tokens_in": tokens_in, "tokens_out": tokens_out,
                    "build_time_s": build_stats.build_time_s}, indent=2),
        encoding="utf-8")
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


def unit_to_artifact_id(unit: dict) -> Optional[str]:
    uid = unit["id"]
    return None if str(uid).startswith(DIRECTORY_ID_PREFIX) else uid


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
        per_unit = [unit_to_artifact_id(u) for u in units]
        context_ids = [aid for aid in per_unit if aid is not None]
        contexts = gather_unit_text(units)
        if METADATA_ON:
            meta = {"chunk_ids": [[aid] if aid is not None else [] for aid in per_unit]}
    else:
        cut = cut_at_budget(((u["id"], u["text"]) for u in units), char_budget)
        contexts = cut.contexts
        context_ids = [aid for aid in (unit_to_artifact_id(u) for u in units[:cut.kept])
                       if aid is not None]
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

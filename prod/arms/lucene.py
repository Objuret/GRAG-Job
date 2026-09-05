from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Union

import bm25s
import Stemmer

from harness.char_budget import cut_at_budget
from harness.contract import ArmOutput, BuildStats, ModelUsage, unpack_generation

K1 = 0.9
B = 0.4
DEFAULT_TOP_K = 10

ARTIFACT_TYPES = (
    "slack",
    "documents",
    "meeting_transcripts",
    "meeting_chats",
    "urls",
    "prs",
)


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

    retriever: "bm25s.BM25"
    stemmer: object
    ids: list = field(default_factory=list)
    titles: list = field(default_factory=list)
    texts: list = field(default_factory=list)
    build_stats: Optional[BuildStats] = None


def _flatten_one(kind: str, rec: dict) -> Optional[tuple]:
    aid = rec.get("id")
    if aid is None:
        return None

    if kind == "slack":
        channel = (rec.get("Channel") or {}).get("name", "")
        user_blob = (rec.get("Message") or {}).get("User") or {}
        user = user_blob.get("userId", "")
        text = user_blob.get("text", "")
        title = f"Slack #{channel} — {user}".strip(" —")
        contents = text
    elif kind == "documents":
        title = rec.get("type", "Document")
        contents = "\n".join(
            s for s in (rec.get("content", ""), rec.get("feedback", "")) if s
        )
    elif kind == "meeting_transcripts":
        title = rec.get("document_type", "Meeting transcript")
        contents = rec.get("transcript", "")
    elif kind == "meeting_chats":
        title = "Meeting chat"
        contents = rec.get("text", "")
    elif kind == "urls":
        desc = rec.get("description", "")
        link = rec.get("link", "")
        title = desc or link
        contents = f"{desc} {link}".strip()
    elif kind == "prs":
        title = rec.get("title", "")
        summary = rec.get("summary", "")
        reviews = rec.get("reviews") or []
        review_text = " ".join(
            (r.get("comment") or "") for r in reviews if isinstance(r, dict)
        )
        contents = f"{summary} {review_text}".strip()
    else:
        return None

    return aid, title, contents


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


def _flatten_directory(section: str, rec: dict) -> tuple:
    lines = []
    for key, value in rec.items():
        if isinstance(value, list):
            value = ", ".join(f'{m["name"]} ({m["employee_id"]})' for m in value)
        lines.append(f"{key}: {value}")
    return f"{section} directory", "\n".join(lines)


def ingest_corpus(corpus_root: Union[str, Path]) -> list:
    root = Path(corpus_root)
    product_files = sorted((root / "products").glob("*.json"))
    docs: list = []
    seen: set = set()
    for pf in product_files:
        data = json.loads(pf.read_text(encoding="utf-8"))
        for kind in ARTIFACT_TYPES:
            for rec in data.get(kind, []) or []:
                flat = _flatten_one(kind, rec)
                if flat is None:
                    continue
                aid, title, contents = flat
                if aid in seen:
                    continue
                seen.add(aid)
                docs.append(
                    {"id": aid, "title": title, "contents": contents, "kind": kind}
                )

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
            title, contents = _flatten_directory(section, rec)
            docs.append({"id": uid, "title": title, "contents": contents,
                         "kind": section})
    print(f"lucene: {artifacts} artifacts + {len(docs) - artifacts} directory records",
          flush=True)
    return docs


def build_sparse_index(
    corpus: Union[str, Path, list], k1: float = K1, b: float = B
) -> Prepared:
    t0 = time.perf_counter()
    docs = corpus if isinstance(corpus, list) else ingest_corpus(corpus)
    ids = [d["id"] for d in docs]
    titles = [d["title"] for d in docs]
    texts = [f'{d["title"]}\n{d["contents"]}'.strip() for d in docs]
    if not texts:
        raise RuntimeError(f"sparse index: corpus is empty (corpus={corpus!r})")

    stemmer = Stemmer.Stemmer("english")
    corpus_tokens = bm25s.tokenize(
        texts, stopwords="en", stemmer=stemmer, show_progress=False
    )
    retriever = bm25s.BM25(k1=k1, b=b, method="lucene")
    retriever.index(corpus_tokens, show_progress=False)

    build_stats = BuildStats(
        build_time_s=time.perf_counter() - t0,
        model=ModelUsage(),
        models=[],
    )
    return Prepared(
        retriever=retriever,
        stemmer=stemmer,
        ids=ids,
        titles=titles,
        texts=texts,
        build_stats=build_stats,
    )


def prepare_over_corpus(corpus: Union[str, Path, list]) -> Prepared:
    return build_sparse_index(corpus)


def _qid_text(question) -> tuple:
    if hasattr(question, "question") and hasattr(question, "id"):
        return question.id, question.question
    if isinstance(question, dict):
        return question.get("id", ""), question.get("question", "")
    if isinstance(question, (tuple, list)) and len(question) == 2:
        return question[0], question[1]
    return "", str(question)


def retrieve_top_k_units(question, prepared: Prepared, k: int = DEFAULT_TOP_K) -> list:
    _, text = _qid_text(question)
    if k <= 0 or not prepared.ids:
        return []
    k = min(k, len(prepared.ids))
    query_tokens = bm25s.tokenize(
        [text], stopwords="en", stemmer=prepared.stemmer, show_progress=False
    )
    try:
        if len(query_tokens.ids[0]) == 0:
            return []
    except (AttributeError, IndexError, TypeError):
        pass
    indices, scores = prepared.retriever.retrieve(query_tokens, k=k, show_progress=False)
    units = []
    for rank, idx in enumerate(indices[0]):
        idx = int(idx)
        units.append(
            {
                "id": prepared.ids[idx],
                "text": prepared.texts[idx],
                "score": float(scores[0][rank]),
                "rank": rank,
            }
        )
    return units


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
    units = retrieve_top_k_units(question, prepared, depth)
    search_time_s = time.perf_counter() - t0

    meta = None
    if char_budget is None:
        per_unit = [unit_to_artifact_id(u) for u in units]
        context_ids = [aid for aid in per_unit if aid is not None]
        contexts = gather_unit_text(units)
        if METADATA_ON:
            meta = {"chunk_ids": [[aid] if aid is not None else [] for aid in per_unit]}
    else:
        ranked = [u for u in units if u["score"] > 0.0]
        cut = cut_at_budget(((u["id"], u["text"]) for u in ranked), char_budget)
        contexts = cut.contexts
        context_ids = [aid for aid in (unit_to_artifact_id(u) for u in ranked[:cut.kept])
                       if aid is not None]
        meta = {"char_budget": {"budget": char_budget, "chars": cut.chars,
                                "kept": cut.kept, "boundary": cut.boundary,
                                "exhausted": cut.exhausted}}

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
        retrieval=ModelUsage(),
        meta=meta,
    )

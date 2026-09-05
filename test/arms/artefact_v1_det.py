from __future__ import annotations

import os
import re
import time
from typing import Optional

import numpy as np

from harness.contract import ArmOutput, ModelUsage
import arms.artefact_v1 as v1
from harness.embed import _embed

Prepared = v1.Prepared
prepare_over_corpus = v1.prepare_over_corpus
DATABASE = v1.DATABASE

INTERPRET_MODEL = "deterministic"

_EID = re.compile(r"\beid_[0-9a-f]+\b")
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")

_PRODUCTS: dict = {}

_FACET_MODE = os.environ.get("HERB_DET_FACETS", "")
FACETS_ON = _FACET_MODE in ("1", "support", "all")
ROUTING_ON = _FACET_MODE in ("routing", "all")
EDGES_ON = _FACET_MODE in ("edges", "all")

RETRIEVAL_FLAGS = {**v1.RETRIEVAL_FLAGS, "HERB_DET_FACETS": _FACET_MODE or None}

_ANCHOR_TEXTS = {
    "topic":    "the subject matter and conceptual theme being discussed",
    "entities": "named people, organizations, products, and systems involved",
    "activity": "events, processes, decisions, and actions taking place",
    "temporal": "the time relationship: retrospective, ongoing, planned, deadlines",
    "evidence": "the kind of answer material: facts, figures, links, artifacts",
}
_FACET_WORDS = {
    "entities": ("who", "whom", "whose", "employee", "employees", "author",
                 "authors", "reviewer", "reviewers", "people", "team", "teams",
                 "customer", "customers", "company", "companies"),
    "temporal": ("when", "year", "years", "date", "dates", "recent", "latest",
                 "timeline", "timelines"),
    "activity": ("happened", "did", "decision", "decisions", "decided",
                 "process", "processes", "how", "change", "changes", "changed",
                 "review", "reviews", "discussed"),
    "evidence": ("document", "documents", "report", "reports", "pr", "prs",
                 "pull", "pulls", "link", "links", "url", "urls", "file",
                 "files", "evidence"),
}

_ANCHORS: Optional[np.ndarray] = None


def _anchors() -> tuple:
    global _ANCHORS
    if _ANCHORS is None:
        qmat, calls, tok_in, tok_out, secs = _embed(
            list(_ANCHOR_TEXTS.values()), "query", bar=False)
        A = np.asarray(qmat, dtype=np.float64)
        _ANCHORS = A / np.linalg.norm(A, axis=1, keepdims=True)
        return _ANCHORS, ModelUsage(calls=calls, tokens_in=tok_in,
                                    tokens_out=tok_out, time_s=secs)
    return _ANCHORS, ModelUsage()


def _facet_triggers(text: str) -> dict:
    low = set(re.findall(r"[a-z]+", text.lower()))
    d = {f: 0.2 for f in v1.ALL_FACETS}
    triggered = False
    for facet, words in _FACET_WORDS.items():
        if low & set(words):
            d[facet] = 1.0
            triggered = True
    if not triggered:
        d["topic"] = 1.0
    return d


def _facet_direction(text: str) -> np.ndarray:
    d = _facet_triggers(text)
    vec = np.array([d[f] for f in _ANCHOR_TEXTS], dtype=np.float64)
    return vec / vec.sum()


def _facet_shaper(text: str):
    qdir = _facet_direction(text)
    A, _ = _anchors()

    def shape(names, embs, support):
        G = np.clip(embs @ A.T, 0.0, None)
        G = G / np.maximum(G.sum(axis=1, keepdims=True), 1e-9)
        return support * (G @ qdir)
    return shape


def _facet_router(text: str):
    qdir = _facet_direction(text)
    A, _ = _anchors()

    def shape_distances(embs, D):
        G = np.clip(embs @ A.T, 0.0, None)
        G = G / np.maximum(G.sum(axis=1, keepdims=True), 1e-9)
        gap = np.abs(G[:, None, :] - G[None, :, :])
        disagreement = np.clip((gap * qdir).sum(axis=2), 0.0, 1.0)
        return D * (1.0 + disagreement)
    return shape_distances


def _products(session) -> list:
    if v1.DATABASE not in _PRODUCTS:
        _PRODUCTS[v1.DATABASE] = [r["p"] for r in session.run(
            "MATCH (c:Chunk) WHERE c.product IS NOT NULL "
            "RETURN DISTINCT c.product AS p ORDER BY p")]
    return _PRODUCTS[v1.DATABASE]


def _phrase_at(phrase: str, low: str) -> int:
    m = re.search(rf"\b{re.escape(phrase)}\b", low)
    return m.start() if m else -1


def _det_plan(text: str, session) -> dict:
    low = text.lower()
    words = set(re.findall(r"[a-z_]+", low))
    product, best = None, None
    for p in _products(session):
        pos = _phrase_at(p.lower(), low)
        if pos >= 0 and (best is None or (pos, -len(p)) < best):
            best = (pos, -len(p))
            product = p
    section = next((s for s in v1.OFFERED_SECTIONS
                    if s in words or _phrase_at(v1._readable(s), low) >= 0), None)
    eid = _EID.search(low)
    years = [int(y) for y in dict.fromkeys(_YEAR.findall(text))]
    neutral = {f: 0.2 for f in v1.ALL_FACETS}
    return {
        "description": text,
        "parts": [{"t": text, "facets": neutral}],
        "gate": {"product": product, "section": section, "channel": None,
                 "employee_id": eid.group(0) if eid else None, "years": years},
    }


def answer_one_question(question, prepared: Prepared, generate, k: int = 50,
                        char_budget: Optional[int] = None) -> ArmOutput:
    _, text = v1._qid_text(question)

    anchor_usage = ModelUsage()
    if FACETS_ON or ROUTING_ON:
        _, anchor_usage = _anchors()
    t0 = time.perf_counter()
    persons = (v1.resolve_persons(text, prepared.directory)
               if v1.PERSON_ON else None)
    with prepared.driver.session(database=v1.DATABASE) as session:
        plan = _det_plan(text, session)
        if EDGES_ON:
            d = _facet_triggers(text)
            for part in plan["parts"]:
                part["facets"] = dict(d)
        if FACETS_ON:
            plan["_support_shaper"] = _facet_shaper(text)
        if ROUTING_ON:
            plan["_distance_shaper"] = _facet_router(text)
        rows, ground_usage, meta = v1._retrieve(session, plan, k,
                                                keep_all=char_budget is not None,
                                                persons=persons)
    meta["interpreter"] = {"model": INTERPRET_MODEL, "backend": "none"}
    meta["facet_channel"] = _FACET_MODE or None
    retrieve_wall = time.perf_counter() - t0

    doc_cache: dict = {}
    if char_budget is not None:
        contexts, chunk_id_lists, context_ids, meta["char_budget"] = v1._budget_contexts(
            rows, char_budget, doc_cache)
    else:
        contexts: list[str] = []
        context_ids: list[str] = []
        chunk_id_lists: list[list[str]] = []
        seen: set[str] = set()
        for row in rows:
            chunk_text, ids = v1._resolve_chunk(row, doc_cache)
            contexts.append(chunk_text)
            chunk_id_lists.append(ids)
            for aid in ids:
                if aid not in seen:
                    seen.add(aid)
                    context_ids.append(aid)
    meta["chunk_ids"] = chunk_id_lists
    meta["returned"] = len(contexts)

    search_time_s = max(0.0, retrieve_wall - ground_usage.time_s)
    retrieval_usage = ModelUsage(
        calls=anchor_usage.calls + ground_usage.calls,
        tokens_in=anchor_usage.tokens_in + ground_usage.tokens_in,
        tokens_out=anchor_usage.tokens_out + ground_usage.tokens_out,
        time_s=anchor_usage.time_s + ground_usage.time_s)

    if generate is None:
        answer, gen = "", ModelUsage()
    else:
        g0 = time.perf_counter()
        result = generate(text, contexts)
        answer, gen = v1.unpack_generation(result, time.perf_counter() - g0)

    return ArmOutput(
        answer=answer,
        contexts=contexts,
        context_ids=context_ids,
        search_time_s=search_time_s,
        generator=gen,
        retrieval=retrieval_usage,
        meta=meta,
    )

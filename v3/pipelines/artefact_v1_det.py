"""artefact_v1_det.py — the deterministic leg of the ARTEFACT-V1 arm: the same
graph mechanism with zero interpreter calls.

The question text is the single prompt part, embedded with underscores read as
spaces; the need vector is the question verbatim. Stated scope comes from
literal matches only: product names read from the graph's own chunk vocabulary,
section names from the offered enum as literal words or their readable phrases,
`eid_…` employee ids and 4-digit years by pattern. A person the question names
is read the same literal way, through artefact_v1's directory resolver, and
weighs its chunks through the person support path.
Facets are direction-neutral. The walk, the value system, and the hard k are
artefact_v1's, unchanged; there is no sufficiency review. The only model
calls are embeddings — the query, plus a once-per-process embed of the five
facet anchors when a facet channel is on, both counted in the question's
retrieval usage — so a run is repeatable end to end: identical inputs give
identical evidence.
"""
from __future__ import annotations

import os
import re
import time
from typing import Optional

import numpy as np

from contract import ArmOutput, ModelUsage
import pipelines.artefact_v1 as v1
from pipelines.vector import _embed

Prepared = v1.Prepared
prepare_over_corpus = v1.prepare_over_corpus
DATABASE = v1.DATABASE

INTERPRET_MODEL = "deterministic"

_EID = re.compile(r"\beid_[0-9a-f]+\b")
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")

# product vocabulary per database name
_PRODUCTS: dict = {}

# --- optional facet channel (HERB_DET_FACETS) ---------------------------------
# Two-sided facet direction at query time, zero graph writes: the question's
# direction from a literal lexicon, each pool tag's direction from geometry
# (its embedding against the five facet-meaning anchors).
#   HERB_DET_FACETS=support  their dot reshapes support before the anchor
#   HERB_DET_FACETS=routing  facet disagreement (in the question's channels)
#                            stretches the mutual distances the clusters are
#                            built from — the areas themselves form
#                            query-relatively; agreeing pairs keep their true
#                            distance, and the stretch is capped by the sum of
#                            the question direction's two largest facet weights
#   HERB_DET_FACETS=edges    the question's direction feeds the parts' facet
#                            channels, so the per-edge stored facet weights
#                            enter facetTerm; HERB_STR_FACET sets how much of
#                            it reaches the score
#   HERB_DET_FACETS=all      all three placements together
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
    """The five facet-anchor embeddings (unit rows) -> (anchors, the embed's
    ModelUsage). The embed runs once per process; a cached hit returns zero
    usage. Timed callers warm the cache before their window opens and count
    the returned usage."""
    global _ANCHORS
    if _ANCHORS is None:
        qmat, calls, tok_in, tok_out, secs = _embed(list(_ANCHOR_TEXTS.values()), "query")
        A = np.asarray(qmat, dtype=np.float64)
        _ANCHORS = A / np.linalg.norm(A, axis=1, keepdims=True)
        return _ANCHORS, ModelUsage(calls=calls, tokens_in=tok_in,
                                    tokens_out=tok_out, time_s=secs)
    return _ANCHORS, ModelUsage()


def _facet_triggers(text: str) -> dict:
    """The question's facet triggers from its literal form: triggered facets
    at full weight, the rest at the neutral floor. A question whose form
    declares nothing is a topic question — topic leads only then."""
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
    """The trigger weights as a unit-sum direction vector over the anchor
    order."""
    d = _facet_triggers(text)
    vec = np.array([d[f] for f in _ANCHOR_TEXTS], dtype=np.float64)
    return vec / vec.sum()


def _facet_shaper(text: str):
    """support ← support × (question direction · tag geometry direction), on the
    raw shared scale the combine step normalizes. Both sides vary, so the
    product can discriminate which tag anchors the part."""
    qdir = _facet_direction(text)
    A, _ = _anchors()

    def shape(names, embs, support):
        G = np.clip(embs @ A.T, 0.0, None)
        G = G / np.maximum(G.sum(axis=1, keepdims=True), 1e-9)
        return support * (G @ qdir)
    return shape


def _facet_router(text: str):
    """d′(i,j) = d(i,j) × (1 + facet disagreement in the question's channels):
    the clusters — the routing — form query-relatively. Disagreement is the
    question-direction-weighted L1 gap between the tags' geometric facet
    directions, in [0, 1]: agreeing pairs keep their true distance, and the
    stretch is capped by the sum of the question direction's two largest facet
    weights."""
    qdir = _facet_direction(text)
    A, _ = _anchors()

    def shape_distances(embs, D):
        G = np.clip(embs @ A.T, 0.0, None)
        G = G / np.maximum(G.sum(axis=1, keepdims=True), 1e-9)
        gap = np.abs(G[:, None, :] - G[None, :, :])          # pairwise |ΔG| per facet
        disagreement = np.clip((gap * qdir).sum(axis=2), 0.0, 1.0)
        return D * (1.0 + disagreement)
    return shape_distances


def _products(session) -> list:
    """Product vocabulary read once per database from the graph's own chunk
    fields, in a fixed order."""
    if v1.DATABASE not in _PRODUCTS:
        _PRODUCTS[v1.DATABASE] = [r["p"] for r in session.run(
            "MATCH (c:Chunk) WHERE c.product IS NOT NULL "
            "RETURN DISTINCT c.product AS p ORDER BY p")]
    return _PRODUCTS[v1.DATABASE]


def _phrase_at(phrase: str, low: str) -> int:
    """Position of `phrase` as whole words in the lowercased question; -1
    when absent."""
    m = re.search(rf"\b{re.escape(phrase)}\b", low)
    return m.start() if m else -1


def _det_plan(text: str, session) -> dict:
    """The plan without a model: the question is the single part; stated scope
    is what the question literally contains. The stated product is the
    earliest whole-word product mention, longest name on a tie; a section
    matches as its enum token or its readable phrase."""
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

    # the facet channels read the anchor embeddings: warm them before the
    # timed window opens and count the embed in the question's usage
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
        # Fill-to-budget: the ranking is consumed by characters, and the budget
        # sets the returned depth.
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

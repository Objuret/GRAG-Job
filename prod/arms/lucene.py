from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Union

import bm25s
import Stemmer

from harness import char_budget
from harness.char_budget import cut_at_budget
from harness.contract import ArmOutput, BuildStats, ModelUsage, unpack_generation
from harness.fields import sub
from harness.record_text import ARTIFACT_TYPES, FORM, metadata_records, record_text, units_digest

# Anserini's defaults (Lucene's own are 1.2 / 0.75, bm25s's 1.5 / 0.75)
K1 = 0.9
B = 0.4
DEFAULT_TOP_K = 10

# the arm has no switches of its own
RETRIEVAL_FLAGS: dict = {}

Generator = Callable[[str, list], object]

# a delivered text is one record: contexts and context_ids go one to one, but for the text
# cut at the budget
UNIT_IS_ONE_RECORD = True

# what was left out of the data this arm rests on, and on whose word (harness.fields, FIELDS.md)
LEFT_OUT = [
    "The metadata file salesforce_team.json: it is not indexed; the index holds the records of the "
    "product files and the employees and customers of employee.json and customers_data.json. His "
    "words: \"yeah, so, dont fucking talk about or use it then, if its not a current file, why are "
    "you talking about it?\" (2026-10-31).",
]

# the words for what only this arm writes into a run folder (harness.fields, FIELDS.md)
FIELDS = {
    "meta": sub("What the arm recorded about this question's ranking.", {
        "char_budget": char_budget.FIELDS,
        "ranking": sub("The ranking the delivered texts were taken from.", {
            "n_units": "How many units the index holds.",
            "n_ranked": "How many of them scored above zero for this question. Only those are "
                        "ranked; a unit that shares no word with the question is never delivered.",
            "scores": "The BM25 score of each delivered text, in delivered order. A BM25 score has "
                      "no upper bound; a higher score is a closer match to the question's words.",
            "next_score": "The BM25 score of the first unit that was not delivered, on the same "
                          "scale; empty when none was left.",
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
        "method": "The BM25 variant.",
        "k1": "BM25's k1.",
        "b": "BM25's b.",
        "bm25_parameters": "Where k1 and b are from.",
        "stopwords": "The stop word list.",
        "stemmer": "The stemmer.",
        "bm25s": "The version of the BM25 library.",
        "PyStemmer": "The version of the stemmer.",
        "kept": "Where the index lives.",
    }),
    "retrieval_flags": sub("The arm's own switches. The arm has none, so this is empty.", {}),
}


@dataclass
class Prepared:

    retriever: "bm25s.BM25"
    stemmer: object
    ids: list = field(default_factory=list)
    texts: list = field(default_factory=list)
    build_stats: Optional[BuildStats] = None


def ingest_corpus(corpus_root: Union[str, Path]) -> list:
    """One unit per record: the records of the product files, then the employees and customers of
    the metadata files (`metadata_records`), each with its own id and its record_text."""
    root = Path(corpus_root)
    product_files = sorted((root / "products").glob("*.json"))
    docs: list = []
    seen: set = set()
    for pf in product_files:
        data = json.loads(pf.read_text(encoding="utf-8"))
        for kind in ARTIFACT_TYPES:
            for rec in data.get(kind, []) or []:
                aid = rec.get("id")
                if aid is None or aid in seen:
                    continue
                seen.add(aid)
                docs.append({"id": aid, "text": record_text(kind, rec), "kind": kind})

    products = len(docs)
    for kind, rid, rec in metadata_records(root):
        if rid in seen:
            raise RuntimeError(f"the {kind} record {rid!r} has the id of another unit: two units "
                               "would share one id")
        seen.add(rid)
        docs.append({"id": rid, "text": record_text(kind, rec), "kind": kind})
    print(f"lucene: {products} product records + {len(docs) - products} employees and customers",
          flush=True)
    return docs


def build_sparse_index(
    corpus: Union[str, Path, list], k1: float = K1, b: float = B
) -> Prepared:
    t0 = time.perf_counter()
    docs = corpus if isinstance(corpus, list) else ingest_corpus(corpus)
    ids = [d["id"] for d in docs]
    texts = [d["text"] for d in docs]
    if not texts:
        raise RuntimeError(f"sparse index: corpus is empty (corpus={corpus!r})")

    stemmer = Stemmer.Stemmer("english")
    corpus_tokens = bm25s.tokenize(
        texts, stopwords="en", stemmer=stemmer, show_progress=False
    )
    retriever = bm25s.BM25(k1=k1, b=b, method="lucene")
    retriever.index(corpus_tokens, show_progress=False)

    # BM25 is built without a model: no entry
    build_stats = BuildStats(build_time_s=time.perf_counter() - t0, models=[])
    return Prepared(
        retriever=retriever,
        stemmer=stemmer,
        ids=ids,
        texts=texts,
        build_stats=build_stats,
    )


def prepare_over_corpus(corpus: Union[str, Path, list]) -> Prepared:
    return build_sparse_index(corpus)


def index_info(prepared: Prepared) -> dict:
    """What the sparse index is, for the run manifest."""
    from importlib.metadata import version
    return {"units": len(prepared.ids), "text_chars": sum(len(t) for t in prepared.texts),
            "unit_text": FORM, "units_sha256": units_digest(prepared.ids, prepared.texts),
            "method": "lucene", "k1": K1, "b": B, "bm25_parameters": "Anserini's defaults",
            "stopwords": "en", "stemmer": "english",
            "bm25s": version("bm25s"), "PyStemmer": version("PyStemmer"),
            "kept": "in memory, built at the start of every leg"}


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
        context_ids = [u["id"] for u in units]
        contexts = gather_unit_text(units)
    else:
        ranked = [u for u in units if u["score"] > 0.0]
        cut = cut_at_budget(((u["id"], u["text"]) for u in ranked), char_budget)
        contexts = cut.contexts
        context_ids = [u["id"] for u in ranked[:cut.kept]]
        meta = {"char_budget": {"budget": char_budget, "chars": cut.chars,
                                "kept": cut.kept, "boundary": cut.boundary,
                                "exhausted": cut.exhausted},
                # the BM25 score of every delivered context, in delivered order, and of the
                # first unit left out; how many units there are and how many scored above zero
                "ranking": {"n_units": len(prepared.ids), "n_ranked": len(ranked),
                            "scores": [u["score"] for u in ranked[:len(contexts)]],
                            "next_score": (ranked[len(contexts)]["score"]
                                           if len(ranked) > len(contexts) else None)}}

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

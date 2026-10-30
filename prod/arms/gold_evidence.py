"""The gold-evidence arm: hands the answer model HERB's own oracle context for the question, the
context the benchmark's code/oracle_eval.py (build_context) builds, and nothing else.

It answers how well the answer model does when the evidence is exactly what the benchmark gives
its oracle: the same answer model, the same answer prompt and the same 72,000-character cut as the
other arms, with no retrieval in front of it. It is the one arm that reads a question's citations;
the question it is called with is its id and its text, as for every arm, and the citations are
read by id from the questions file at prepare.

The context, in oracle_eval.py's order: the team structure of the question's product (each role
with its people as "eid (name)"), then its customers (each customer id with its company), both
written as oracle_eval.py writes them, from the product file's `team` and `customers` fields, which
HERB's dataset card keeps for oracle settings; then the cited records in the order the question's
citations list them, a record listed twice once, at its first place. A record is written by
harness.record_text as lucene and vector write it. A citation that names no record stops the
question.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Union

from harness import char_budget
from harness.char_budget import cut_at_budget
from harness.contract import ArmOutput, BuildStats, ModelUsage, unpack_generation
from harness.fields import sub
from harness.questions import QUESTIONS, load_questions
from harness.record_text import ARTIFACT_TYPES, FORM, record_text, units_digest

DEFAULT_TOP_K = 10

# the product files as HERB ships them: the corpus the other arms read has `team` and `customers`
# taken out, and the oracle context is built from them
RAW_PRODUCTS = Path(__file__).resolve().parents[2] / "data" / "raw" / "Salesforce__HERB" / "products"

ORACLE_FORM = ("SalesforceAIResearch/HERB db3bf9b3: code/oracle_eval.py build_context, the team "
               "structure and the customers blocks; the cited records as harness.record_text "
               "writes them")

ORDER = ("the team structure block, then the customers block, then the cited records in the order "
         "the question's citations list them, a record listed twice once, at its first place")

TEAM_ID = "oracle::team"
CUSTOMERS_ID = "oracle::customers"

RETRIEVAL_FLAGS: dict = {}

Generator = Callable[[str, list], object]

# the team and customers blocks are delivered texts that are no record, so contexts and
# context_ids do not go one to one
UNIT_IS_ONE_RECORD = False

# what was left out of the data this arm rests on, and on whose word (harness.fields, FIELDS.md)
LEFT_OUT = [
    "Every record the question's citations do not name: the arm hands over HERB's oracle context "
    "only, the experiment the reviewer suggested (\"a small experiment using only HERB's gold "
    "evidence with the same answer model\") and he started (\"first 2, then 1\", 2026-10-30; "
    "\"ah, yes, the evidence path is smart\", 2026-10-30, on the team and customers blocks).",
]

# the words for what only this arm writes into a run folder (harness.fields, FIELDS.md)
FIELDS = {
    "meta": sub("What the arm recorded about this question's evidence.", {
        "char_budget": char_budget.FIELDS,
        "evidence": sub("HERB's oracle context for this question, before the cut.", {
            "product": "The product the question belongs to, read off its id.",
            "team_chars": "The characters of the team structure block; 0 when the product has "
                          "no team.",
            "customers_chars": "The characters of the customers block; 0 when the product has "
                               "no customers.",
            "cited": "How many record ids the question's citations list.",
            "records": "How many distinct records they name.",
            "chars": "The characters of the blocks and the records together.",
        }),
        "chunk_ids": "The record ids behind each delivered text, in delivered order: one id for "
                     "a record, none for the team structure or customers block.",
    }),
    "index": sub("What the arm reads the evidence from.", {
        "units": "How many records the arm can hand over. A unit is one record of the corpus.",
        "text_chars": "The characters of all unit texts together.",
        "unit_text": "The form a record is written in to make its unit's text, and where that "
                     "form is from.",
        "units_sha256": "One sha256 over all units in record order: per unit the id and then the "
                        "text, each as UTF-8 behind its byte length written as 8 bytes, big end "
                        "first. Two runs with the same value read the same units.",
        "evidence": "Where each question's citations are read.",
        "evidence_sha256": "The sha256 of that file's bytes.",
        "oracle_blocks": "The form of the team structure and customers blocks, and where it is "
                         "from.",
        "order": "The order the oracle context is handed over in.",
        "kept": "Where the records are held.",
    }),
}


@dataclass
class Prepared:

    texts: dict = field(default_factory=dict)
    citations: dict = field(default_factory=dict)
    blocks: dict = field(default_factory=dict)
    questions_path: str = ""
    build_stats: Optional[BuildStats] = None


def _oracle_blocks(corpus_root: Path) -> dict:
    """Per product: its team structure block and its customers block, each "" when the product
    has none, written as oracle_eval.py's build_context writes them."""
    employees = json.loads((corpus_root / "metadata" / "employee.json").read_text(encoding="utf-8"))
    companies = {c["id"]: c["company"] for c in json.loads(
        (corpus_root / "metadata" / "customers_data.json").read_text(encoding="utf-8"))}
    blocks = {}
    for pf in sorted(RAW_PRODUCTS.glob("*.json")):
        data = json.loads(pf.read_text(encoding="utf-8"))
        team = ""
        if data.get("team"):
            by_role: dict = {}
            for eid in data["team"]:
                emp = employees[eid]
                by_role.setdefault(emp["role"], []).append(f"{eid} ({emp['name']})")
            team = "TEAM STRUCTURE:\n" + "".join(
                f"{role}: {', '.join(people)}\n" for role, people in by_role.items())
        customers = ""
        if data.get("customers"):
            customers = "CUSTOMERS:\n" + "".join(
                f"{cid}: {companies[cid]}\n" for cid in data["customers"])
        blocks[pf.stem] = (team, customers)
    if not blocks:
        raise FileNotFoundError(f"no product files under {RAW_PRODUCTS}")
    return blocks


def _record_texts(root: Path) -> dict:
    texts: dict = {}
    for pf in sorted((root / "products").glob("*.json")):
        data = json.loads(pf.read_text(encoding="utf-8"))
        for kind in ARTIFACT_TYPES:
            for rec in data.get(kind, []) or []:
                aid = rec.get("id")
                if aid is None or aid in texts:
                    continue
                texts[aid] = record_text(kind, rec)
    return texts


def prepare_over_corpus(corpus: Union[str, Path]) -> Prepared:
    t0 = time.perf_counter()
    texts = _record_texts(Path(corpus))
    blocks = _oracle_blocks(Path(corpus))
    citations = {q.id: list(q.citations) for q in load_questions(QUESTIONS)}
    print(f"gold_evidence: {len(texts)} records, oracle blocks of {len(blocks)} products, "
          f"citations of {len(citations)} questions", flush=True)
    # nothing is built with a model: no entry
    return Prepared(texts=texts, citations=citations, blocks=blocks,
                    questions_path=str(QUESTIONS),
                    build_stats=BuildStats(build_time_s=time.perf_counter() - t0, models=[]))


def index_info(prepared: Prepared) -> dict:
    """Where the evidence is read from, for the run manifest."""
    ids = list(prepared.texts)
    path = Path(prepared.questions_path)
    return {"units": len(ids), "text_chars": sum(len(t) for t in prepared.texts.values()),
            "unit_text": FORM, "units_sha256": units_digest(ids, [prepared.texts[i] for i in ids]),
            "evidence": f"citations of {path.parent.name}/{path.name}",
            "evidence_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "oracle_blocks": ORACLE_FORM,
            "order": ORDER, "kept": "in memory, read at the start of every leg"}


def _qid_text(question) -> tuple:
    if hasattr(question, "question") and hasattr(question, "id"):
        return question.id, question.question
    if isinstance(question, dict):
        return question.get("id", ""), question.get("question", "")
    if isinstance(question, (tuple, list)) and len(question) == 2:
        return question[0], question[1]
    return "", str(question)


def oracle_units(qid: str, prepared: Prepared) -> tuple:
    """The question's oracle context as (id, text) units: the team structure and customers blocks
    of its product, each left out when empty, then its cited records in citation order, each once.
    Also what the context holds, for the row's meta."""
    if qid not in prepared.citations:
        raise KeyError(f"question {qid!r} is not in {prepared.questions_path}")
    product = qid.split("::")[0]
    if product not in prepared.blocks:
        raise KeyError(f"question {qid!r}: no product file {product!r} under {RAW_PRODUCTS}")
    team, customers = prepared.blocks[product]
    listed = prepared.citations[qid]
    missing = [c for c in listed if c not in prepared.texts]
    if missing:
        raise KeyError(f"{len(missing)} citations of {qid!r} name no record, e.g. {missing[:3]}")
    units = [(uid, t) for uid, t in ((TEAM_ID, team), (CUSTOMERS_ID, customers)) if t]
    seen = set()
    for cid in listed:
        if cid not in seen:
            seen.add(cid)
            units.append((cid, prepared.texts[cid]))
    evidence = {"product": product, "team_chars": len(team), "customers_chars": len(customers),
                "cited": len(listed), "records": len(seen),
                "chars": sum(len(t) for _, t in units)}
    return units, evidence


def _record_ids(units) -> list:
    return [uid for uid, _ in units if uid not in (TEAM_ID, CUSTOMERS_ID)]


def answer_one_question(
    question, prepared: Prepared, generate: Optional[Generator], k: int = DEFAULT_TOP_K,
    char_budget: Optional[int] = None,
) -> ArmOutput:
    qid, text = _qid_text(question)

    t0 = time.perf_counter()
    units, evidence = oracle_units(qid, prepared)
    search_time_s = time.perf_counter() - t0

    if char_budget is None:
        units = units[:k]
        contexts = [t for _, t in units]
        context_ids = _record_ids(units)
        meta = {"evidence": evidence}
    else:
        cut = cut_at_budget(units, char_budget)
        contexts = cut.contexts
        context_ids = _record_ids(units[:cut.kept])
        meta = {"char_budget": {"budget": char_budget, "chars": cut.chars, "kept": cut.kept,
                                "boundary": cut.boundary, "exhausted": cut.exhausted},
                "evidence": evidence,
                "chunk_ids": [_record_ids([u]) for u in units[:len(contexts)]]}

    if generate is None:
        answer, gen_usage = "", ModelUsage()
    else:
        g0 = time.perf_counter()
        result = generate(text, contexts)
        answer, gen_usage = unpack_generation(result, time.perf_counter() - g0)

    return ArmOutput(
        answer=answer,
        contexts=contexts,
        context_ids=context_ids,
        search_time_s=search_time_s,
        generator=gen_usage,
        retrieval=ModelUsage(),
        meta=meta,
    )

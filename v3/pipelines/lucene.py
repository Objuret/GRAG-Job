"""lucene.py — sparse baseline (BM25, Lucene-variant ranking).

Why it's here: the sparse-retrieval control arm.
Why this one is relevant: classic keyword retrieval — the floor any dense or
structured method must beat. Builds its OWN index over the corpus and shares
NOTHING with the artefact.

In -> out: question -> BM25 top-k artifacts -> shared generator -> answer.

Engine: bm25s (pure-Python) with `method="lucene"`. BM25 is a family, not one
formula — bm25s ships several standard variants (robertson / atire / bm25l /
bm25+ / lucene) that differ only in IDF and length-normalisation detail.
`"lucene"` is the variant Apache Lucene / Elasticsearch / Anserini use and is
bm25s's default, so this baseline IS the de-facto-standard BM25 the literature
benchmarks against; it reproduces Lucene's *scoring* exactly. The text analysis,
though, is bm25s's own — its tokenizer + English stopwords + a Snowball/Porter2
stemmer: Lucene-LIKE, not Lucene's Java EnglishAnalyzer (which stems with the
original Porter). So we approximate Lucene's analyzer, we don't reproduce it.

Params k1=0.9, b=0.4 are the reference defaults from "Resources for Brewing BEIR"
(Kamalloo et al. 2023), established on the BEIR benchmark (Thakur et al. 2021);
algorithm origin Robertson & Zaragoza (2009). These citations are the PROVENANCE
of the configuration only — BEIR is not an evaluation target here. Every arm
(artifact / lucene / vector) is scored solely by RAGAS.

Retrieval unit = one HERB artifact (slack message / document / meeting
transcript / meeting chat / url / pr). The artifact's native `id` is preserved
verbatim, so context_ids land in the SAME id space the gold citations use
(verified: 100% of gold citations resolve to an artifact id), which is what the
citation-based context precision/recall compares against.

Corpus scope. HERB's dataset card marks the `team` and `customers` FIELDS inside
a product file as oracle-only and says those facts "should be inferred from
either other artifacts (e.g. Slack messages) or from `metadata/*`"
(`data/raw/Salesforce__HERB/README.md`:54) — `derive_corpus.RAG_UNSAFE_KEYS`
strips the two fields, and the three `metadata/` directory files are a sanctioned
RAG source. With `HERB_BASELINE_METADATA=1` this index carries them too. The
document is one directory ENTRY, not one file: `employee.json` is 89,394 chars
and `salesforce_team.json` 112,053 against a 293-char median artifact, so BM25's
length normalisation (b=0.4) buries a whole-file document, and one entry is the
granularity the id->name join lives at — a query naming a person or a company
matches exactly one short record. Of `salesforce_team.json`'s 530 nodes only the
65 carrying report rosters are emitted: the other 465 are byte-identical to their
`employee.json` records, so emitting them would put 465 exact duplicates in the
index competing for the same rank slots, and the reporting structure is the only
thing that file adds. A directory record carries no artifact `id`, so it
contributes NO context_ids — the same thing the artefact arm does with a
directory chunk (`artefact_v1._resolve_chunk` returns an empty id list for a
`metadata` locator). Its text reaches the generator and its rank slot is spent;
the citation id space stays exactly the artifact id space.

Contract fit: prepare returns a Prepared index carrying a contract.BuildStats;
answer_one_question returns a contract.ArmOutput. The question is read for its
`id` + `question` ONLY — `ground_truth` / `citations` are never touched, so the
truth quarantine holds by convention.

References (provenance of the method + its configuration; none is an evaluation
target — every arm is scored solely by RAGAS):
  - Robertson, S. & Zaragoza, H. (2009). The Probabilistic Relevance Framework:
    BM25 and Beyond. Foundations and Trends in IR 3(4):333-389.
    doi:10.1561/1500000019 — the BM25 ranking function itself.
  - Kamphuis, C., de Vries, A.P., Boytsov, L. & Lin, J. (2020). Which BM25 Do You
    Mean? A Large-Scale Reproducibility Study of Scoring Variants. ECIR 2020.
    doi:10.1007/978-3-030-45442-5_4 — the variant taxonomy; "lucene" is the
    Lucene/Robertson length-normalisation this arm selects.
  - Lù, X.H. (2024). BM25S: Orders of Magnitude Faster Lexical Search via Eager
    Sparse Scoring. arXiv:2407.03618 — the bm25s engine used here, which
    reproduces those variants' exact scoring.
  - Kamalloo, E., Thakur, N. et al. (2023). Resources for Brewing BEIR:
    Reproducible Reference Models and an Official Leaderboard. arXiv:2306.07471 —
    source of the k1=0.9, b=0.4 reference defaults.
  - Thakur, N., Reimers, N., Rücklé, A., Srivastava, A. & Gurevych, I. (2021).
    BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of IR Models.
    arXiv:2104.08663 — the benchmark those defaults were established on.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Union

import bm25s
import Stemmer

from char_budget import cut_at_budget
from contract import ArmOutput, BuildStats, ModelUsage, unpack_generation

# BM25 reference parameters (Kamalloo et al. 2023 / BEIR).
K1 = 0.9
B = 0.4
DEFAULT_TOP_K = 10

# The six artifact arrays a corpus-view HERB product file carries — its ten raw
# top-level keys less the four `derive_corpus.STRIP_KEYS` removes.
ARTIFACT_TYPES = (
    "slack",
    "documents",
    "meeting_transcripts",
    "meeting_chats",
    "urls",
    "prs",
)


def _env_bool(name: str, default: bool) -> bool:
    """A run switch read from the environment, `default` when unset or blank.
    Only "0" and "1" are values; anything else fails loud rather than silently
    reverting, so a typo can never select the other corpus."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    value = raw.strip()
    if value not in ("0", "1"):
        raise ValueError(f"{name} must be '0' or '1', got {raw!r}")
    return value == "1"


# Corpus scope: with HERB_BASELINE_METADATA=1 the index carries HERB's three
# `metadata/` directory files beside the product artifacts, one document per
# directory entry. Read once at import so a run documents its own corpus.
METADATA_ON = _env_bool("HERB_BASELINE_METADATA", False)

# HERB's directory files, under the corpus root, keyed by the section name each
# one is read under.
EMPLOYEE_JSON = "metadata/employee.json"
CUSTOMERS_JSON = "metadata/customers_data.json"
TEAM_JSON = "metadata/salesforce_team.json"

# A directory unit id is namespaced, because one person is both an `employee`
# entry and a `salesforce_team` entry under the same native id, and because a
# directory record must never be mistaken for an artifact. `ingest_corpus`
# checks the artifact ids against this prefix rather than assuming the split.
DIRECTORY_ID_PREFIX = "metadata::"

# Manifest provenance: the corpus scope, recorded by the runner in run_manifest.json.
RETRIEVAL_FLAGS = {"HERB_BASELINE_METADATA": METADATA_ON}

# The shared generator the orchestrator injects into every arm (fairness
# control). It takes the question text + retrieved contexts and returns the
# answer. To fill ArmOutput's model telemetry it MAY return, instead of a bare
# string, a (answer, telemetry) pair or an object exposing
# .answer/.calls/.tokens/.time — see _unpack_generation. If it returns a plain
# string, we record calls=1, tokens=0 and time the call ourselves.
Generator = Callable[[str, list], object]


@dataclass
class Prepared:
    """Handle returned by prepare(); fed back into answer_one_question.
    Carries the BuildStats so the orchestrator can record build provenance."""

    retriever: "bm25s.BM25"
    stemmer: object
    ids: list = field(default_factory=list)
    titles: list = field(default_factory=list)
    texts: list = field(default_factory=list)
    build_stats: Optional[BuildStats] = None


# --- ingest -----------------------------------------------------------------

def _flatten_one(kind: str, rec: dict) -> Optional[tuple]:
    """One artifact -> (id, title, contents). None if the record carries no id."""
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
    """The `salesforce_team.json` nodes that carry a roster of direct reports,
    depth first. A node with no list-valued field is a leaf, and a leaf repeats
    its `employee.json` record field for field, so only the leaders are read."""
    out: list = []
    for node in nodes:
        rosters = [v for v in node.values() if isinstance(v, list)]
        if rosters:
            out.append(node)
        for roster in rosters:
            out.extend(_team_leaders(roster))
    return out


def _directory_records(root: Path) -> list:
    """HERB's directory files as (section, native id, record) triples. A record
    with no id fails loud rather than entering the index unaddressable."""
    employees = json.loads((root / EMPLOYEE_JSON).read_text(encoding="utf-8"))
    customers = json.loads((root / CUSTOMERS_JSON).read_text(encoding="utf-8"))
    team = json.loads((root / TEAM_JSON).read_text(encoding="utf-8"))
    return (
        [("employee", rec["employee_id"], rec) for rec in employees.values()]
        + [("customers_data", rec["id"], rec) for rec in customers]
        + [("salesforce_team", rec["employee_id"], rec) for rec in _team_leaders(team)]
    )


def _flatten_directory(section: str, rec: dict) -> tuple:
    """One directory record -> (title, contents). Fields render as `name: value`
    in the record's own key order; a roster renders as its members' names with
    their ids, so a leader's reports are one searchable line."""
    lines = []
    for key, value in rec.items():
        if isinstance(value, list):
            value = ", ".join(f'{m["name"]} ({m["employee_id"]})' for m in value)
        lines.append(f"{key}: {value}")
    return f"{section} directory", "\n".join(lines)


def ingest_corpus(corpus_root: Union[str, Path]) -> list:
    """Flatten HERB into one document per artifact: {id, title, contents, kind}.

    Reads product files, and under METADATA_ON HERB's three directory files as
    one document per entry, namespaced by DIRECTORY_ID_PREFIX. Artifact ids are
    globally unique in HERB; on the rare duplicate the first occurrence wins so
    the id->record map stays 1:1.
    linked to: build_sparse_index (consumes these docs)
    """
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


# --- index -------------------------------------------------------------------

def build_sparse_index(
    corpus: Union[str, Path, list], k1: float = K1, b: float = B
) -> Prepared:
    """prepare(): build an own BM25 index over the corpus artifacts. Runs once.

    `corpus` is either a path to the corpus root (it gets ingested) or an
    already-ingested list of doc dicts. Independent of the artefact — own units,
    own index. Records a contract.BuildStats on the returned Prepared (no model
    is used at build time, so model = ModelUsage() and models = []).
    linked to: orchestrator.run_one_pipeline (called once); ingest_corpus
    """
    t0 = time.perf_counter()
    docs = corpus if isinstance(corpus, list) else ingest_corpus(corpus)
    ids = [d["id"] for d in docs]
    titles = [d["title"] for d in docs]
    # Title + body is the indexed text (the standard BEIR concatenation).
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
        model=ModelUsage(),  # sparse BM25 touches no model at build
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
    """Uniform prepare entry the orchestrator drives. Thin alias over
    build_sparse_index; the returned Prepared carries .build_stats."""
    return build_sparse_index(corpus)


# --- retrieve ----------------------------------------------------------------

def _qid_text(question) -> tuple:
    """(id, question_text) from a QuestionWithTruth, dict, (id, text) tuple, or
    a bare string. Reads ONLY id + question — truth fields are never touched."""
    if hasattr(question, "question") and hasattr(question, "id"):
        return question.id, question.question
    if isinstance(question, dict):
        return question.get("id", ""), question.get("question", "")
    if isinstance(question, (tuple, list)) and len(question) == 2:
        return question[0], question[1]
    return "", str(question)


def retrieve_top_k_units(question, prepared: Prepared, k: int = DEFAULT_TOP_K) -> list:
    """Sparse top-k retrieval for the question text -> list of unit dicts
    {id, text, score, rank}, best first.
    linked to: unit_to_artifact_id + gather_unit_text (consume the hits)
    """
    _, text = _qid_text(question)
    if k <= 0 or not prepared.ids:
        return []
    k = min(k, len(prepared.ids))
    # Tokenize as a 1-doc batch so the return shape is the documented 2-D form.
    query_tokens = bm25s.tokenize(
        [text], stopwords="en", stemmer=prepared.stemmer, show_progress=False
    )
    # A question that tokenizes to nothing (all stopwords) has no lexical signal;
    # return no hits rather than letting bm25s emit sentinel (-1) indices.
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
    """The native artifact id off the unit, None for a directory record — a HERB
    directory entry has no artifact id, so it enters no citation-space list.
    Fills ArmOutput.context_ids (same id space the artefact resolves to and the
    gold citations use)."""
    uid = unit["id"]
    return None if str(uid).startswith(DIRECTORY_ID_PREFIX) else uid


def gather_unit_text(units: list) -> list:
    """Collect the units' text. Fills ArmOutput.contexts + feeds the generator."""
    return [u["text"] for u in units]


# --- answer ------------------------------------------------------------------

def _unpack_generation(result, elapsed_s: float) -> tuple:
    """Normalise a generator's return into (answer, ModelUsage)."""
    return unpack_generation(result, elapsed_s)


def answer_one_question(
    question, prepared: Prepared, generate: Optional[Generator], k: int = DEFAULT_TOP_K,
    char_budget: Optional[int] = None,
) -> ArmOutput:
    """ENTRY: retrieve_top_k -> ids + text -> generate -> ArmOutput.

    `generate` is the SHARED generator injected by the orchestrator so generation
    is identical across arms. If None (retrieval-only smoke), the answer is left
    empty and model telemetry is zero.

    With `char_budget` the ranking runs over the whole corpus, ends where the
    BM25 scores stop being positive (a zero score expresses no preference), and
    is consumed to exactly that many context characters
    (char_budget.cut_at_budget): whole artifacts in rank order, the crossing
    artifact cut mid-text as the final context. `context_ids` carries the whole
    artifacts only; the cut is recorded in meta["char_budget"].

    Under METADATA_ON a retrieved directory record occupies a context and
    contributes no id, so `context_ids` is shorter than `contexts` and the
    per-context id lists ride in meta["chunk_ids"] — what `truncate_k` rebuilds
    a shallower depth's ids from.
    linked to: orchestrator; shared `generate`; returns contract.ArmOutput
    """
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
        # A zero BM25 score expresses no preference, so the consumable
        # ranking ends there; a budget the scored ranking cannot fill is an
        # exhaustion, recorded at its true total.
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
        retrieval=ModelUsage(),  # sparse retrieval uses no model
        meta=meta,
    )

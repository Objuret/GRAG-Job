"""artefact_v1_five_questions.py — the ARTEFACT-V1 arm resolved by five-questions
matching: one flat combined score over the whole chunk population, ranking by
content agreement between what the prompt asks and what each chunk answers.

The five questions are the user's original tagging design — every chunk was read
by asking five questions of it, and the facet names the graph carries are his
renames of them: topic (what is this about), entities (what specific things are
named), activity (what occurrence or process is described), temporal (when is
this relevant), evidence (what kind of evidence does this supply). This arm asks
the same five questions of both sides and matches answers to answers.

BUILD TIME — everything query-independent is premade, cached under
`output/five_questions_cache/<entry>/` (entry named by the derived-layer key,
the role configuration, and a digest of the content the answers derive from;
`manifest.json` written last as the completeness marker):

  roles     which question each tag answers, recovered as the argmax of the
            tag's five-slot fit. The fit is the tag's marginal over the derived
            facet layer — the mean over its edges of (φ − ½), an unevidenced
            cell contributing exactly nothing — read from the layer's cache
            entry (`HERB_FQ_ROLE_SOURCE=derived`), or the mean of the baked
            per-facet `w_facets` cells on the live edges (`baked`). The fit is
            taken raw or z-scored by the corpus spread of the marginals
            (`HERB_FQ_ROLE_FIT`).
  answers   per chunk: its entity-role and activity-role tags (indices into the
            tag-embedding matrix), its median record day (locators resolved
            against the oracle-stripped corpus by the derived build's own
            reader), and its 15-feature register profile (the derived build's
            evidence machinery), from which each evidence kind's text-shape
            score is read.

QUERY TIME — a deterministic read of the prompt text, words and spans only, no
model call and no model-emitted number:

  named things    the corpus's own product names, eid handles, CamelCase
                  compounds, acronyms, and capitalized runs;
  action phrases  verb-lexicon hits with a short trailing window;
  time reference  an ISO day, a quarter, a month, a year span, or one of his
                  five posture words (recent / historical / future / active /
                  completed);
  evidence kind   from the question's form (how much/how many → number, why →
                  cause, decided/approved → status, compare → comparison,
                  what happened/summarize → summary, said → quote);
  query embedding the whole prompt, for topic.

Extracted spans embed through the arm's shared per-text embed cache.

Each asked question j scores every chunk with a match m_j in [0, 1]:

  entities  the best half-cosine between a query-named thing and a chunk's
            entity-role tags (max over the pairs; `HERB_FQ_ENTITY_AGG=mean`
            averages the per-name bests instead);
  activity  the same form over action phrases and activity-role tags;
  topic     (1 + cos(query, desc)) / 2 — the existing description channel,
            unchanged;
  temporal  exp(−distance-to-reference / s) over the chunk's median record day,
            s the dated chunks' own spread (`HERB_FQ_TIME_SCALE` overrides); a
            posture word maps onto recency rank;
  evidence  agreement between the asked kind and the chunk's register-profile
            kind label (`HERB_FQ_EVIDENCE=graded` uses the rank-calibrated kind
            score instead).

THE SILENCE RULE: a question the prompt does not ask enters the combine for no
chunk — under every combine form that is a per-chunk constant, so an unasked
question can reorder nothing. Chunk-side silence on an asked question (no
entity-role tags, no date) contributes the scale's floor, or the neutral
midpoint under `HERB_FQ_SILENT=neutral` — it never excludes the chunk. Every
match is a weight and every chunk stays scored, with one form-specific
property: under the multiplicative combine a binary or floored match is
tier-dominant at k — the chunks it favors outrank every other whenever they
fill the depth — while the additive and noisy-OR forms blend across the
questions. The oracle sections sit outside the population.

The combined score is one score over the whole chunk population — the
description channel and the question matches together, top-k out. Which math
combines the weights is canonically undecided, so the combine is carried as
configuration (`HERB_FQ_COMBINE`: additive weighted sum, the default;
multiplicative, each term floored at MULT_FLOOR so a zero match weights and
never annihilates the product; noisy-OR) with one weight per question, all
recorded in the run manifest.

The graph stores references, never content: a retrieved chunk is a pointer —
`locator_json` on the chunk plus `rel_path` + `sha256` on its file — resolved
from raw under `v3/data/raw` at answer time and hash-verified by artefact_v1's
own resolver. `context_ids` are HERB artifact ids from the raw records. The
whole layer loads at prepare, so answering a question opens no graph session.

Contract: `prepare_over_corpus(corpus) -> Prepared`; `answer_one_question(...)
-> ArmOutput`. The question is read for id + text ONLY.
"""
from __future__ import annotations

print("artefact_v1_five_questions: five-questions matching over the whole "
      "chunk population — loading numpy + scipy …", flush=True)

import hashlib
import inspect
import json
import os
import re
import time
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from graph.build_facet_layer import (
    DERIVED_CACHE_DIR, FACET_PRIOR, REGISTER, _derived_key, fetch_matrix,
    midrank_cdf, read_chunks, register_profiles,
)
from harness.contract import ArmOutput, BuildStats, ModelUsage, unpack_generation
from arms.artefact_v1 import (
    ALL_FACETS, DATABASE, DATASET_ID, EXCLUDED_SECTIONS, RUN_ID, _driver,
    _embed_cached, _env_float, _qid_text, _resolve_chunk, _unit,
)
from harness.embed import EMBED_MODEL
from harness.progress import progress

# --- constants ---------------------------------------------------------------

INTERPRET_MODEL = "deterministic"

# The premade answers: one cache entry per (derived-layer key, role
# configuration, content digest), holding the per-tag roles and the per-chunk
# answer facts, with the manifest written last as the completeness marker.
FIVE_QUESTIONS_CACHE_DIR = (Path(__file__).resolve().parent.parent.parent / "output" /
                            "five_questions_cache")

# The calibrated scale's neutral point: the mid-rank CDF sends every facet
# column's median to 1/2, so a cell at the median says nothing and centres to
# exactly zero in the tag's marginal.
PHI_NEUTRAL = 0.5

# Divide-by-zero guard on the corpus spreads the z-scored role fit divides by.
DIVIDE_FLOOR = 1e-6

# Which layer the per-tag roles are recovered from: the derived facet layer's
# marginals, or the baked `w_facets` cells on the live edges.
ROLE_SOURCE = os.environ.get("HERB_FQ_ROLE_SOURCE", "derived")
if ROLE_SOURCE not in ("derived", "baked"):
    raise ValueError(
        f"HERB_FQ_ROLE_SOURCE must be 'derived' or 'baked', got {ROLE_SOURCE!r}")

# How the five-slot fit is read before the argmax: raw, or z-scored by the
# corpus spread of the marginals so the five facets speak on one scale.
ROLE_FIT = os.environ.get("HERB_FQ_ROLE_FIT", "raw")
if ROLE_FIT not in ("raw", "zscored"):
    raise ValueError(
        f"HERB_FQ_ROLE_FIT must be 'raw' or 'zscored', got {ROLE_FIT!r}")

# How a multi-name question folds its per-name matches: the best pair, or the
# mean of the per-name bests so breadth is required.
ENTITY_AGG = os.environ.get("HERB_FQ_ENTITY_AGG", "max")
ACTIVITY_AGG = os.environ.get("HERB_FQ_ACTIVITY_AGG", "max")
for _name, _value in (("HERB_FQ_ENTITY_AGG", ENTITY_AGG),
                      ("HERB_FQ_ACTIVITY_AGG", ACTIVITY_AGG)):
    if _value not in ("max", "mean"):
        raise ValueError(f"{_name} must be 'max' or 'mean', got {_value!r}")

# The evidence match: agreement with the chunk's register-profile kind label,
# or the rank-calibrated kind score.
EVIDENCE_MATCH = os.environ.get("HERB_FQ_EVIDENCE", "label")
if EVIDENCE_MATCH not in ("label", "graded"):
    raise ValueError(
        f"HERB_FQ_EVIDENCE must be 'label' or 'graded', got {EVIDENCE_MATCH!r}")

# What chunk-side silence on an ASKED question contributes: the match scale's
# floor, or its neutral midpoint. It is a weight either way — silence never
# excludes the chunk.
SILENT = os.environ.get("HERB_FQ_SILENT", "floor")
if SILENT not in ("floor", "neutral"):
    raise ValueError(f"HERB_FQ_SILENT must be 'floor' or 'neutral', got {SILENT!r}")
SILENT_FLOOR = 0.0
SILENT_NEUTRAL = 0.5

# The combine over the asked questions' matches — carried as configuration
# because which math combines the weights is canonically undecided.
COMBINE = os.environ.get("HERB_FQ_COMBINE", "additive")

# The factor floor under the multiplicative combine: a zero-valued match
# multiplies by this instead of annihilating the product, so the worst match
# is a heavy weight and never a gate — chunks it touches keep the order their
# other matches give them.
MULT_FLOOR = 1e-6

# One weight per question, in the combine's own sense: additive scales the
# term, multiplicative is the exponent, noisy-OR scales the term inside [0, 1].
W_TOPIC = _env_float("HERB_FQ_W_TOPIC", 1.0)
W_ENTITIES = _env_float("HERB_FQ_W_ENTITIES", 1.0)
W_ACTIVITY = _env_float("HERB_FQ_W_ACTIVITY", 1.0)
W_TEMPORAL = _env_float("HERB_FQ_W_TEMPORAL", 1.0)
W_EVIDENCE = _env_float("HERB_FQ_W_EVIDENCE", 1.0)
_QWEIGHTS = {"topic": W_TOPIC, "entities": W_ENTITIES, "activity": W_ACTIVITY,
             "temporal": W_TEMPORAL, "evidence": W_EVIDENCE}


def _validate_combine(combine: str, weights: dict) -> None:
    """The combine family and its weights, checked loud at import: a question
    weight is non-negative under every form, and noisy-OR additionally needs
    every weighted term inside [0, 1]."""
    if combine not in ("additive", "multiplicative", "noisy_or"):
        raise ValueError(f"HERB_FQ_COMBINE must be 'additive', 'multiplicative' "
                         f"or 'noisy_or', got {combine!r}")
    negative = {q: w for q, w in weights.items() if w < 0.0}
    if negative:
        raise ValueError(
            f"question weights must be >= 0 under every combine, got {negative}")
    if combine == "noisy_or":
        bad = {q: w for q, w in weights.items() if w > 1.0}
        if bad:
            raise ValueError(
                f"noisy_or needs every question weight in [0, 1], got {bad}")


_validate_combine(COMBINE, _QWEIGHTS)

# The temporal closeness scale in days; 0 reads the dated chunks' own standard
# deviation at prepare. The floor keeps a degenerate spread out of the divisor.
TIME_SCALE = _env_float("HERB_FQ_TIME_SCALE", 0.0)
DAY_SCALE_FLOOR = 1.0

# Manifest provenance: the regime switches and combine weights the runner
# copies into run_manifest.json, plus the facet prior naming the derived entry
# the roles are read under — two runs differing only in it stay tellable
# apart.
RETRIEVAL_FLAGS = {
    "HERB_FQ_ROLE_SOURCE": ROLE_SOURCE, "HERB_FQ_ROLE_FIT": ROLE_FIT,
    "HERB_FQ_ENTITY_AGG": ENTITY_AGG, "HERB_FQ_ACTIVITY_AGG": ACTIVITY_AGG,
    "HERB_FQ_EVIDENCE": EVIDENCE_MATCH, "HERB_FQ_SILENT": SILENT,
    "HERB_FQ_COMBINE": COMBINE, "HERB_FQ_W_TOPIC": W_TOPIC,
    "HERB_FQ_W_ENTITIES": W_ENTITIES, "HERB_FQ_W_ACTIVITY": W_ACTIVITY,
    "HERB_FQ_W_TEMPORAL": W_TEMPORAL, "HERB_FQ_W_EVIDENCE": W_EVIDENCE,
    "HERB_FQ_TIME_SCALE": TIME_SCALE, "HERB_FACET_PRIOR": FACET_PRIOR,
}

Generator = Callable[[str, list], object]

_FACET_AT = {f: i for i, f in enumerate(ALL_FACETS)}

# --- the query-side read: words and spans only --------------------------------

# What the query names: eid handles, tokens carrying two or more capitals
# (CamelCase compounds and acronyms alike), and capitalized runs; the product
# lexicon comes from the corpus's own file names.
_EID = re.compile(r"\beid_[0-9a-f]+\b")
_MIXED_CAPS = re.compile(r"\b\w*[A-Z]\w*[A-Z]\w*\b")
_CAP_RUN = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b")

# Question-leading words trimmed off the front of a capitalized run; a run they
# exhaust names nothing.
_NAME_STOP = {
    "what", "which", "who", "whom", "whose", "when", "where", "why", "how",
    "did", "does", "do", "was", "were", "is", "are", "the", "a", "an",
    "list", "name", "find", "show", "give",
}

# The action lexicon: 60 verb stems, matched as word-initial stems on the
# lowercased forms; a capitalized hit names something rather than doing it and
# is skipped.
_VERB_STEMS = (
    "adopt", "agree", "analys", "analyz", "announc", "approv", "assign",
    "audit", "automat", "benchmark", "build", "cancel", "chang", "complet",
    "configur", "creat", "debug", "decid", "delay", "deliver", "deploy",
    "design", "develop", "discuss", "escalat", "estimat", "evaluat", "fix",
    "forecast", "hir", "implement", "improv", "integrat", "investigat",
    "launch", "measur", "merg", "migrat", "monitor", "onboard", "optimi",
    "patch", "plan", "postpon", "present", "prioriti", "propos", "publish",
    "reduc", "refactor", "reject", "releas", "report", "resolv", "review",
    "schedul", "track", "updat", "upgrad", "valid",
)
_VERB = re.compile(r"\b(?:" + "|".join(_VERB_STEMS) + r")\w*\b", re.I)

# How many words an action phrase carries from its verb, clause-bounded.
ACTION_WINDOW = 6

# Time references, most specific first: an ISO day, a quarter, a month, the
# stated year(s), or one of the user's five posture words.
_DAY_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_QUARTER_RE = re.compile(
    r"\b(?:q([1-4])|(first|second|third|fourth)\s+quarter)\s*(?:of\s+)?"
    r"((?:19|20)\d{2})\b", re.I)
_ORDINAL_QUARTER = {"first": 1, "second": 2, "third": 3, "fourth": 4}
_MONTHS = ("january", "february", "march", "april", "may", "june", "july",
           "august", "september", "october", "november", "december")
_MONTH_RE = re.compile(
    r"\b(" + "|".join(_MONTHS) + r")\s+((?:19|20)\d{2})\b", re.I)
_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")
# The five posture words are the user's own time_relevance enum; each maps
# monotonically onto recency rank, late side first.
_POSTURE_LATE = {"recent": True, "future": True, "active": True,
                 "historical": False, "completed": False}
_POSTURE_RE = re.compile(r"\b(" + "|".join(_POSTURE_LATE) + r")\b", re.I)

# The question forms that state an evidence kind, first match wins.
_KIND_FORMS = (
    ("number", r"\bhow\s+(?:much|many|often|long)\b"),
    ("cause", r"\bwhy\b"),
    ("status", r"\b(?:decided?|decision|approved?|approval|status|"
               r"confirmed?|agreed?|resolved?)\b"),
    ("comparison", r"\b(?:compare[ds]?|comparison|versus|vs\.?|"
                   r"difference\s+between)\b"),
    ("summary", r"\b(?:what\s+happened|summar\w+|overview)\b"),
    ("quote", r"\b(?:say|says|said|stated?|mention(?:ed|s)?|quote[ds]?)\b"),
)
_KIND_RES = tuple((kind, re.compile(form, re.I)) for kind, form in _KIND_FORMS)

# Each evidence kind's register signature: the countable text-shape features
# whose density says a chunk supplies that kind. A kind with no countable mark
# (comparison) scores every chunk the same, so asking it reorders nothing.
EVIDENCE_KIND_FEATURES = {
    "number": ("numeral", "percent", "money", "unit"),
    "quote": ("first_person", "second_person"),
    "cause": ("causal",),
    "summary": ("definition", "example"),
    "comparison": (),
    "status": ("modal", "procedure"),
}
_KINDS = tuple(EVIDENCE_KIND_FEATURES)
_UNKNOWN_FEATURES = {f for marks in EVIDENCE_KIND_FEATURES.values()
                     for f in marks} - set(REGISTER)
if _UNKNOWN_FEATURES:
    raise ValueError(
        f"EVIDENCE_KIND_FEATURES names features outside REGISTER: "
        f"{sorted(_UNKNOWN_FEATURES)}")


def _named_things(text: str, products: list) -> list:
    """What the query names, in first-mention order: the corpus's own product
    names as whole words, eid handles, multi-capital tokens, and capitalized
    runs with their leading question words trimmed."""
    found = []
    for p in products:
        m = re.search(rf"\b{re.escape(p)}\b", text, re.I)
        if m:
            found.append((m.start(), p))
    for pattern in (_EID, _MIXED_CAPS):
        for m in pattern.finditer(text):
            found.append((m.start(), m.group(0)))
    for m in _CAP_RUN.finditer(text):
        words = m.group(0).split()
        while words and words[0].lower() in _NAME_STOP:
            words.pop(0)
        if len(words) >= 2:
            found.append((m.start(), " ".join(words)))
    out, seen = [], set()
    for _, name in sorted(found, key=lambda x: (x[0], -len(x[1]))):
        key = name.casefold()
        if key not in seen:
            seen.add(key)
            out.append(name)
    return out


def _action_phrases(text: str) -> list:
    """What the query asks about doing: each verb-lexicon hit with up to
    ACTION_WINDOW words of its own clause. A capitalized hit names something
    rather than doing it and is skipped."""
    out, seen = [], set()
    for m in _VERB.finditer(text):
        if text[m.start()].isupper():
            continue
        clause = re.split(r"[.,;:?!\n]", text[m.start():], maxsplit=1)[0]
        phrase = " ".join(clause.split()[:ACTION_WINDOW])
        key = phrase.casefold()
        if phrase and key not in seen:
            seen.add(key)
            out.append(phrase)
    return out


def _time_reference(text: str) -> Optional[dict]:
    """The query's time reference, most specific reading first: an ISO day, a
    quarter, a month, the span of the stated year(s), or a posture word. None
    when the query points at no time. A date-shaped token that is no calendar
    day reads as no day and the read continues."""
    for m in _DAY_RE.finditer(text):
        try:
            at = date(int(m.group(1)), int(m.group(2)), int(m.group(3))).toordinal()
        except ValueError:
            continue
        return {"form": "day", "lo": at, "hi": at, "text": m.group(0)}
    m = _QUARTER_RE.search(text)
    if m:
        q = int(m.group(1)) if m.group(1) else _ORDINAL_QUARTER[m.group(2).lower()]
        y = int(m.group(3))
        lo = date(y, 3 * q - 2, 1).toordinal()
        hi = (date(y + 1, 1, 1) if q == 4 else date(y, 3 * q + 1, 1)).toordinal() - 1
        return {"form": "range", "lo": lo, "hi": hi, "text": m.group(0)}
    m = _MONTH_RE.search(text)
    if m:
        mo = _MONTHS.index(m.group(1).lower()) + 1
        y = int(m.group(2))
        lo = date(y, mo, 1).toordinal()
        hi = (date(y + 1, 1, 1) if mo == 12 else date(y, mo + 1, 1)).toordinal() - 1
        return {"form": "range", "lo": lo, "hi": hi, "text": m.group(0)}
    years = [int(y) for y in dict.fromkeys(_YEAR_RE.findall(text))]
    if years:
        return {"form": "range", "lo": date(min(years), 1, 1).toordinal(),
                "hi": date(max(years), 12, 31).toordinal(),
                "text": " ".join(str(y) for y in years)}
    m = _POSTURE_RE.search(text)
    if m:
        word = m.group(1).lower()
        return {"form": "posture", "word": word, "late": _POSTURE_LATE[word],
                "text": word}
    return None


def _evidence_kind(text: str) -> Optional[str]:
    """The evidence kind the question's form implies; None when no form
    matches."""
    for kind, pattern in _KIND_RES:
        if pattern.search(text):
            return kind
    return None


def _extract(text: str, products: list) -> dict:
    """The whole deterministic query read: words and spans only."""
    return {"names": _named_things(text, products),
            "actions": _action_phrases(text),
            "time": _time_reference(text),
            "kind": _evidence_kind(text)}


# --- Cypher ------------------------------------------------------------------

# The chunk population: every chunk of the dataset with its pointer, the guard
# fields deciding whether it is retrievable, and the fields the corpus reader
# resolves records by.
_CHUNKS_CYPHER = """
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
WHERE ($datasetId IS NULL OR f.dataset_id = $datasetId)
RETURN c.chunk_id AS chunkId, c.locator_json AS locator, f.rel_path AS relpath,
       f.sha256 AS sha256, coalesce(c.empty, false) AS empty,
       coalesce(c.section, "") AS section, c.kind AS kind, c.channel AS channel
ORDER BY chunkId
"""

_TAG_EMB_CYPHER = """
UNWIND $keys AS key
MATCH (t:Tag {name: key})
RETURN t.name AS key, t.emb AS emb
"""

_CHUNK_EMB_CYPHER = """
UNWIND $keys AS key
MATCH (c:Chunk {chunk_id: key})
RETURN c.chunk_id AS key, c.desc_emb AS emb
"""

# Retrievability is a graph property, verified at prepare: a chunk carrying an
# excluded section would take a score while never being returnable, so the
# graph must hold none.
_ORACLE_COUNT_CYPHER = """
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
WHERE ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND coalesce(c.section, "") IN $excludedSections
RETURN count(c) AS n
"""

# The baked facet layer, read only under HERB_FQ_ROLE_SOURCE=baked: each
# edge's aligned facet names and weights.
_BAKED_CYPHER = """
MATCH (c:Chunk)-[r:HAS_TAG]->(t:Tag)
WHERE r.run_id = $runId
RETURN t.name AS tag, r.facets AS facets, r.w_facets AS weights
"""


# --- roles: which question a tag answers --------------------------------------

def _read_edges() -> tuple:
    """The derived facet layer's edge list -> (per-edge weights, per-cell
    evidence mask, edge tag names, edge chunk ids). A missing entry fails loud
    naming the build step."""
    entry = DERIVED_CACHE_DIR / _derived_key()
    if not (entry / "manifest.json").is_file():
        raise RuntimeError(
            f"derived facet layer missing at {entry} — "
            f"run `python build_facet_layer.py` once.")
    with np.load(entry / "facets.npz", allow_pickle=False) as z:
        phi = z["phi"].astype(np.float64)
        evidenced = z["evidenced"].astype(bool)
        edge_tag = [str(t) for t in z["tag"]]
        edge_chunk = [str(c) for c in z["chunk_id"]]
    print(f"  layer {entry.name}: {len(phi)} edges, "
          f"{len(set(edge_tag))} tags", flush=True)
    return phi, evidenced, edge_tag, edge_chunk


def _role_fit_derived(phi: np.ndarray, evidenced: np.ndarray, edge_tag: list,
                      tags: list) -> tuple:
    """Each tag's five-slot fit from the derived layer -> (fit, present): the
    mean over the tag's edges of the centred weight, an unevidenced cell
    contributing exactly nothing."""
    at = {t: i for i, t in enumerate(tags)}
    rows = np.array([at[t] for t in edge_tag])
    centred = np.where(evidenced, phi - PHI_NEUTRAL, 0.0)
    total = np.zeros((len(tags), len(ALL_FACETS)))
    count = np.zeros(len(tags))
    np.add.at(total, rows, centred)
    np.add.at(count, rows, 1.0)
    return total / np.maximum(count, 1.0)[:, None], count > 0


def _role_fit_baked(session, tags: list) -> tuple:
    """Each tag's five-slot fit from the live edges' baked facet cells ->
    (fit, present): per facet, the mean of `w_facets` over the edges that carry
    it; a facet no edge carries fits 0. An edge facet outside the five fails
    loud."""
    at = {t: i for i, t in enumerate(tags)}
    total = np.zeros((len(tags), len(ALL_FACETS)))
    count = np.zeros((len(tags), len(ALL_FACETS)))
    bar = progress(desc="baked facets", unit="edge")
    for rec in session.run(_BAKED_CYPHER, runId=RUN_ID):
        i = at.get(rec["tag"])
        if i is None:
            raise RuntimeError(
                f"edge tag {rec['tag']!r} is outside the derived layer's "
                f"vocabulary — rebuild the layer.")
        for facet, weight in zip(rec["facets"] or [], rec["weights"] or []):
            fi = _FACET_AT.get(facet)
            if fi is None:
                raise RuntimeError(f"edge facet {facet!r} is outside {ALL_FACETS}")
            if weight is not None:
                total[i, fi] += float(weight)
                count[i, fi] += 1.0
        bar.update(1)
    bar.close()
    return total / np.maximum(count, 1.0), count.sum(axis=1) > 0


def _roles(fit: np.ndarray, present: np.ndarray) -> np.ndarray:
    """role(τ) = argmax over the tag's five-slot fit — hard, mirroring the
    user's one-question-per-tag original. `zscored` reads the fit in each
    facet's own corpus spread first."""
    if ROLE_FIT == "zscored":
        mean = fit[present].mean(axis=0)
        sd = np.maximum(fit[present].std(axis=0), DIVIDE_FLOOR)
        fit = (fit - mean) / sd
    return np.argmax(fit, axis=1)


# --- the premade answers cache -------------------------------------------------

def _content_digest(phi: np.ndarray, evidenced: np.ndarray, edge_tag: list,
                    edge_chunk: list, chunk_rows: list,
                    baked_fit: Optional[tuple]) -> str:
    """What the premade answers derive from, as one content address: the
    derived layer's edges and weights, the chunk pointers the days and
    register profiles resolve through, the reader module's own source, this
    arm's own shaping of them — the derived fit, the role argmax and its
    constants, the answer build — and, under the baked role source, the baked
    fit itself. Changed content digests differently and lands in a sibling
    entry, so an entry can never be served stale under an unchanged name."""
    parts = [
        "\n".join(edge_tag).encode("utf-8"),
        "\n".join(edge_chunk).encode("utf-8"),
        np.ascontiguousarray(phi).tobytes(),
        np.ascontiguousarray(evidenced).tobytes(),
        json.dumps(chunk_rows, sort_keys=True).encode("utf-8"),
        inspect.getsource(inspect.getmodule(read_chunks)).encode("utf-8"),
        str(PHI_NEUTRAL).encode("utf-8"),
        str(DIVIDE_FLOOR).encode("utf-8"),
        inspect.getsource(_role_fit_derived).encode("utf-8"),
        inspect.getsource(_roles).encode("utf-8"),
        inspect.getsource(_build_answers).encode("utf-8"),
    ]
    if baked_fit is not None:
        fit, present = baked_fit
        parts.append(np.ascontiguousarray(fit).tobytes())
        parts.append(np.ascontiguousarray(present).tobytes())
    h = hashlib.sha256()
    for part in parts:
        h.update(len(part).to_bytes(8, "big"))
        h.update(part)
    return h.hexdigest()


def _answers_key(digest: str) -> str:
    """The cache entry name for one build: the role source's own key — the
    derived layer's entry name, or the database and run for the baked read —
    plus the fit reading and the content digest."""
    source = (_derived_key() if ROLE_SOURCE == "derived"
              else f"{DATABASE}__{RUN_ID}__baked")
    return f"{source}__fit{ROLE_FIT}__{digest[:16]}"


def _store_answers(entry: Path, roles: np.ndarray, days: np.ndarray,
                   zprofile: np.ndarray, tags: list, chunk_ids: list,
                   stats: dict) -> None:
    """One complete cache entry: the arrays first, the manifest last as the
    completeness marker."""
    entry.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(entry / "answers.npz", roles=roles.astype(np.int8),
                        days=days, zprofile=zprofile,
                        tag=np.array(tags), chunk_id=np.array(chunk_ids))
    (entry / "manifest.json").write_text(json.dumps({
        "database": DATABASE, "run_id": RUN_ID,
        "role_source": ROLE_SOURCE, "role_fit": ROLE_FIT,
        "features": list(REGISTER), "n_tags": len(tags),
        "n_chunks": len(chunk_ids), **stats,
    }, indent=1), encoding="utf-8")


def _load_answers(entry: Path) -> Optional[dict]:
    """A complete entry's arrays and manifest; None when the manifest is
    absent — a partial entry is rebuilt rather than trusted. A corrupt or
    half-written file reads as a miss too — never wrong answers."""
    if not (entry / "manifest.json").is_file():
        return None
    try:
        manifest = json.loads((entry / "manifest.json").read_text(encoding="utf-8"))
        with np.load(entry / "answers.npz", allow_pickle=False) as z:
            return {"roles": z["roles"].astype(np.int64), "days": z["days"],
                    "zprofile": z["zprofile"],
                    "tag": [str(t) for t in z["tag"]],
                    "chunk_id": [str(c) for c in z["chunk_id"]],
                    "features": manifest["features"]}
    except (ValueError, OSError, KeyError, zipfile.BadZipFile):
        return None


def _verify_answers(answers: dict, tags: list, chunk_ids: list,
                    entry: Path) -> None:
    """A cache entry is served only for the vocabulary, population and register
    features it was built over; anything else fails loud rather than resolving
    the wrong answers."""
    if (answers["tag"] != tags or answers["chunk_id"] != chunk_ids
            or answers["features"] != list(REGISTER)):
        raise RuntimeError(
            f"cache entry {entry.name} was built over a different vocabulary, "
            f"chunk population or register feature set — delete "
            f"{entry} and re-run.")


def _build_answers(entry: Path, chunk_rows: list, tags: list, fit: np.ndarray,
                   present: np.ndarray) -> dict:
    """Everything query-independent, computed once and cached: the per-tag
    roles, each chunk's median record day (locators resolved against the
    oracle-stripped corpus), and each chunk's register profile."""
    t0 = time.perf_counter()
    roles = _roles(fit, present)
    facts = read_chunks(chunk_rows)
    days = np.full(len(facts), np.nan)
    for i, fact in enumerate(facts):
        if fact["days"]:
            days[i] = float(np.median(fact["days"]))
    zprofile = register_profiles([f["text"] for f in facts])
    chunk_ids = [r["chunkId"] for r in chunk_rows]
    stats = {
        "n_dated": int((~np.isnan(days)).sum()),
        "roles": {f: int((roles == i).sum()) for i, f in enumerate(ALL_FACETS)},
        "build_time_s": time.perf_counter() - t0,
    }
    _store_answers(entry, roles, days, zprofile, tags, chunk_ids, stats)
    print("  roles " + " ".join(f"{f}={n}" for f, n in stats["roles"].items()) +
          f"  ({stats['n_dated']} dated chunks, "
          f"{stats['build_time_s']:.0f}s)", flush=True)
    return {"roles": roles, "days": days, "zprofile": zprofile, "tag": tags,
            "chunk_id": chunk_ids, "features": list(REGISTER)}


# --- prepare -----------------------------------------------------------------

@dataclass
class Layer:
    """Everything one prompt is resolved against, loaded once per process."""
    tags: list                    # the tag vocabulary, in index order
    tag_emb: np.ndarray           # (T, dim) unit rows
    roles: np.ndarray             # (T,) which question each tag answers
    chunk_ids: list               # the chunk population, in index order
    desc_emb: np.ndarray          # (C, dim) unit rows
    ent_rows: np.ndarray          # entity-role edges: tag index per edge
    ent_cols: np.ndarray          # entity-role edges: chunk index per edge
    act_rows: np.ndarray          # activity-role edges, same shape
    act_cols: np.ndarray
    days: np.ndarray              # (C,) median record day; NaN undated
    day_scale: float              # the temporal closeness scale, in days
    recency: np.ndarray           # (C,) mid-rank of day over the dated chunks
    kind_score: np.ndarray        # (C, kinds) mean register z per kind
    kind_label: np.ndarray        # (C,) argmax kind among those with marks
    kind_graded: np.ndarray       # (C, kinds) rank-calibrated kind scores
    retrievable: np.ndarray       # (C,) bool — oracle sections sit outside it
    pointers: list                # (C,) resolve rows: chunkId/locator/relpath/sha256
    products: list                # the corpus's own product names


@dataclass
class Prepared:
    layer: Layer
    build_stats: Optional[BuildStats] = None


def _build_layer(chunk_rows: list, products: list, tags: list,
                 tag_emb: np.ndarray, desc_emb: np.ndarray, edge_tag: list,
                 edge_chunk: list, answers: dict) -> Layer:
    """The graph rows, the premade answers and the tag geometry as the one
    structure a prompt is resolved against. A chunk the layer was built on that
    the graph does not carry fails loud rather than resolving to the wrong
    pointer."""
    tag_at = {t: i for i, t in enumerate(tags)}
    chunk_at = {r["chunkId"]: i for i, r in enumerate(chunk_rows)}
    absent = sorted({c for c in edge_chunk if c not in chunk_at})
    if absent:
        raise RuntimeError(
            f"{len(absent)} chunk(s) the facet layer was built on are not in "
            f"{DATABASE!r} (e.g. {absent[:3]}) — rebuild the layer.")
    rows = np.array([tag_at[t] for t in edge_tag])
    cols = np.array([chunk_at[c] for c in edge_chunk])
    roles = answers["roles"]
    ent = roles[rows] == _FACET_AT["entities"]
    act = roles[rows] == _FACET_AT["activity"]

    days = answers["days"]
    dated = ~np.isnan(days)
    if TIME_SCALE > 0.0:
        day_scale = TIME_SCALE
    elif dated.any():
        day_scale = max(float(np.std(days[dated])), DAY_SCALE_FLOOR)
    else:
        day_scale = DAY_SCALE_FLOOR
    recency = midrank_cdf(np.where(dated, days, 0.0), dated)

    features = list(REGISTER)
    kind_score = np.zeros((len(chunk_rows), len(_KINDS)))
    for ki, kind in enumerate(_KINDS):
        marks = [features.index(f) for f in EVIDENCE_KIND_FEATURES[kind]]
        if marks:
            kind_score[:, ki] = answers["zprofile"][:, marks].mean(axis=1)
    labelable = [ki for ki, kind in enumerate(_KINDS)
                 if EVIDENCE_KIND_FEATURES[kind]]
    kind_label = np.array(labelable)[np.argmax(kind_score[:, labelable], axis=1)]
    retrievable = np.array([not r["empty"] and r["section"] not in EXCLUDED_SECTIONS
                            for r in chunk_rows])
    kind_graded = np.column_stack([midrank_cdf(kind_score[:, ki], retrievable)
                                   for ki in range(len(_KINDS))])

    return Layer(
        tags=tags, tag_emb=tag_emb, roles=roles,
        chunk_ids=[r["chunkId"] for r in chunk_rows], desc_emb=desc_emb,
        ent_rows=rows[ent], ent_cols=cols[ent],
        act_rows=rows[act], act_cols=cols[act],
        days=days, day_scale=day_scale, recency=recency,
        kind_score=kind_score, kind_label=kind_label, kind_graded=kind_graded,
        retrievable=retrievable,
        pointers=[{k: r[k] for k in ("chunkId", "locator", "relpath", "sha256")}
                  for r in chunk_rows],
        products=products)


def prepare_over_corpus(corpus) -> Prepared:
    """Load the derived layer's edges, the tag and chunk-description
    embeddings, the chunk pointers, and the premade answers — building and
    caching the answers when no complete entry exists. Read-only: the graph is
    never written, and the session closes before the first question."""
    t0 = time.perf_counter()
    phi, evidenced, edge_tag, edge_chunk = _read_edges()
    tags = sorted(set(edge_tag))
    products = sorted(p.stem for p in (Path(corpus) / "products").glob("*.json"))
    drv = _driver()
    try:
        with drv.session(database=DATABASE) as s:
            multi = s.run(
                "MATCH (c:Chunk) WITH c, count { (:File)-[:HAS_CHUNK]->(c) } AS n "
                "WHERE n <> 1 RETURN count(*) AS bad").single()["bad"]
            if multi:
                raise RuntimeError(
                    f"{multi} chunk(s) in {DATABASE!r} without exactly one File — "
                    f"pointer resolution would be ambiguous")
            oracle = s.run(_ORACLE_COUNT_CYPHER, datasetId=DATASET_ID,
                           excludedSections=list(EXCLUDED_SECTIONS)).single()["n"]
            if oracle:
                raise RuntimeError(
                    f"{oracle} chunk(s) in {DATABASE!r} carry an excluded "
                    f"section — scoreable but never returnable")
            print(f"artefact_v1_five_questions: reading {DATABASE!r} "
                  f"(about a minute) …", flush=True)
            chunk_rows = [dict(r) for r in s.run(_CHUNKS_CYPHER, datasetId=DATASET_ID)]
            print(f"  {len(chunk_rows)} chunks, {len(products)} products", flush=True)
            tag_emb = fetch_matrix(s, _TAG_EMB_CYPHER, tags, "tag")
            desc_emb = fetch_matrix(s, _CHUNK_EMB_CYPHER,
                                    [r["chunkId"] for r in chunk_rows], "chunk")
            baked = (_role_fit_baked(s, tags) if ROLE_SOURCE == "baked"
                     else None)
    finally:
        drv.close()

    digest = _content_digest(phi, evidenced, edge_tag, edge_chunk, chunk_rows,
                             baked)
    entry = FIVE_QUESTIONS_CACHE_DIR / _answers_key(digest)
    answers = _load_answers(entry)
    if answers is None:
        fit, present = (baked if baked is not None
                        else _role_fit_derived(phi, evidenced, edge_tag, tags))
        answers = _build_answers(entry, chunk_rows, tags, fit, present)
    else:
        print(f"  answers {entry.name}: reused", flush=True)
    _verify_answers(answers, tags, [r["chunkId"] for r in chunk_rows], entry)

    layer = _build_layer(chunk_rows, products, tags, tag_emb, desc_emb,
                         edge_tag, edge_chunk, answers)
    elapsed = time.perf_counter() - t0
    print(f"  day scale {layer.day_scale:.1f} days, "
          f"{int((~np.isnan(layer.days)).sum())} dated chunks  "
          f"({elapsed:.0f}s)", flush=True)
    return Prepared(
        layer=layer,
        build_stats=BuildStats(build_time_s=elapsed, model=ModelUsage(),
                               models=[EMBED_MODEL]),
    )


# --- the per-question matches --------------------------------------------------

def _silent_value() -> float:
    return SILENT_FLOOR if SILENT == "floor" else SILENT_NEUTRAL


def _pair_match(vecs: np.ndarray, tag_emb: np.ndarray, rows: np.ndarray,
                cols: np.ndarray, n_chunks: int, agg: str) -> np.ndarray:
    """Content agreement between the query's extracted spans and a chunk's
    answer-set tags, on the half-cosine scale: per chunk, the best pair (max),
    or the mean over the spans of each span's best tag (mean). A chunk whose
    answer set is empty carries the silent value — a weight, never a cut."""
    silent = _silent_value()
    if not len(vecs) or not len(rows):
        return np.full(n_chunks, silent)
    sims = (vecs @ tag_emb.T + 1.0) / 2.0
    if agg == "max":
        best = sims.max(axis=0)
        m = np.full(n_chunks, -np.inf)
        np.maximum.at(m, cols, best[rows])
    else:
        m = np.zeros(n_chunks)
        touched = np.zeros(n_chunks, dtype=bool)
        touched[cols] = True
        for row in sims:
            per = np.full(n_chunks, -np.inf)
            np.maximum.at(per, cols, row[rows])
            m += np.where(touched, per, 0.0)
        m = np.where(touched, m / len(sims), -np.inf)
    silentmask = ~np.isfinite(m)
    m[silentmask] = silent
    return m


def _match_temporal(layer: Layer, ref: dict) -> np.ndarray:
    """Graded closeness of each chunk's median record day to the query's time
    reference: exp(−distance-to-interval / s) for a day or range, recency rank
    for a posture word. An undated chunk carries the silent value."""
    m = np.full(len(layer.chunk_ids), _silent_value())
    dated = ~np.isnan(layer.days)
    if ref["form"] == "posture":
        r = layer.recency[dated]
        m[dated] = r if ref["late"] else 1.0 - r
    else:
        d = layer.days[dated]
        dist = np.maximum(np.maximum(ref["lo"] - d, d - ref["hi"]), 0.0)
        m[dated] = np.exp(-dist / layer.day_scale)
    return m


def _match_evidence(layer: Layer, kind: str) -> np.ndarray:
    """Agreement between the asked evidence kind and what the chunk's text
    shape supplies: label agreement, or the rank-calibrated kind score."""
    ki = _KINDS.index(kind)
    if EVIDENCE_MATCH == "label":
        return (layer.kind_label == ki).astype(np.float64)
    return layer.kind_graded[:, ki]


def _match_topic(layer: Layer, qvec: np.ndarray) -> np.ndarray:
    """The existing description channel, unchanged: the whole prompt against
    each chunk's description embedding, on the half-cosine scale."""
    return (layer.desc_emb @ qvec + 1.0) / 2.0


def _combine(matches: dict) -> np.ndarray:
    """One combined score over the asked questions' matches, in ALL_FACETS
    order so the float fold is deterministic. Only asked questions enter, which
    is the silence rule: under every form here an absent question is a
    per-chunk constant, so it reorders nothing."""
    asked = [q for q in ALL_FACETS if q in matches]
    if COMBINE == "additive":
        total = np.zeros(len(next(iter(matches.values()))))
        for q in asked:
            total = total + _QWEIGHTS[q] * matches[q]
        return total
    if COMBINE == "multiplicative":
        total = np.ones(len(next(iter(matches.values()))))
        for q in asked:
            total = total * np.maximum(matches[q], MULT_FLOOR) ** _QWEIGHTS[q]
        return total
    total = np.ones(len(next(iter(matches.values()))))
    for q in asked:
        total = total * (1.0 - _QWEIGHTS[q] * matches[q])
    return 1.0 - total


# --- retrieve ----------------------------------------------------------------

def _retrieve(layer: Layer, qvec: np.ndarray, name_vecs: np.ndarray,
              act_vecs: np.ndarray, extracted: dict, k: int) -> tuple:
    """One prompt against the whole chunk population -> (selected pointer rows,
    meta). Topic is always asked; each other question enters only when the
    query read found something to ask it with."""
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    matches = {"topic": _match_topic(layer, qvec)}
    if len(name_vecs):
        matches["entities"] = _pair_match(name_vecs, layer.tag_emb,
                                          layer.ent_rows, layer.ent_cols,
                                          len(layer.chunk_ids), ENTITY_AGG)
    if len(act_vecs):
        matches["activity"] = _pair_match(act_vecs, layer.tag_emb,
                                          layer.act_rows, layer.act_cols,
                                          len(layer.chunk_ids), ACTIVITY_AGG)
    if extracted["time"] is not None:
        matches["temporal"] = _match_temporal(layer, extracted["time"])
    if extracted["kind"] is not None:
        matches["evidence"] = _match_evidence(layer, extracted["kind"])
    score = _combine(matches)

    population = np.flatnonzero(layer.retrievable)
    kept = min(len(population), k)
    ranked = sorted(population.tolist(),
                    key=lambda i: (-score[i], layer.chunk_ids[i]))[:kept]
    selected = [{**layer.pointers[i], "score": float(score[i])} for i in ranked]

    asked = [q for q in ALL_FACETS if q in matches]
    time_ref = extracted["time"]
    meta = {
        "extracted": {
            "names": extracted["names"], "actions": extracted["actions"],
            "time": ({"form": time_ref["form"], "text": time_ref["text"]}
                     if time_ref else None),
            "evidence_kind": extracted["kind"],
        },
        "asked": asked,
        "combine": {"form": COMBINE,
                    "weights": {q: _QWEIGHTS[q] for q in asked}},
        "population": int(layer.retrievable.sum()),
        "K": kept,
        "retrieved": len(selected),
    }
    return selected, meta


# --- answer ------------------------------------------------------------------

def answer_one_question(question, prepared: Prepared, generate: Optional[Generator],
                        k: int = 50) -> ArmOutput:
    _, text = _qid_text(question)

    t0 = time.perf_counter()
    layer = prepared.layer
    extracted = _extract(text, layer.products)
    spans = [text] + extracted["names"] + extracted["actions"]
    mat, calls, tok_in, tok_out, secs = _embed_cached(spans, "query")
    vecs = _unit(np.asarray(mat, dtype=np.float32))
    qvec = vecs[0]
    name_vecs = vecs[1:1 + len(extracted["names"])]
    act_vecs = vecs[1 + len(extracted["names"]):]
    rows, meta = _retrieve(layer, qvec, name_vecs, act_vecs, extracted, k)
    meta["interpreter"] = {"model": INTERPRET_MODEL, "backend": "none"}
    retrieve_wall = time.perf_counter() - t0

    doc_cache: dict = {}
    contexts: list[str] = []
    context_ids: list[str] = []
    chunk_id_lists: list[list[str]] = []
    seen: set[str] = set()
    for row in rows:
        chunk_text, ids = _resolve_chunk(row, doc_cache)
        contexts.append(chunk_text)
        chunk_id_lists.append(ids)
        for aid in ids:
            if aid not in seen:
                seen.add(aid)
                context_ids.append(aid)
    meta["chunk_ids"] = chunk_id_lists
    meta["returned"] = len(contexts)

    search_time_s = max(0.0, retrieve_wall - secs)
    retrieval_usage = ModelUsage(calls=calls, tokens_in=tok_in,
                                 tokens_out=tok_out, time_s=secs)

    if generate is None:
        answer, gen = "", ModelUsage()
    else:
        g0 = time.perf_counter()
        result = generate(text, contexts)
        answer, gen = unpack_generation(result, time.perf_counter() - g0)

    return ArmOutput(
        answer=answer,
        contexts=contexts,
        context_ids=context_ids,
        search_time_s=search_time_s,
        generator=gen,
        retrieval=retrieval_usage,
        meta=meta,
    )

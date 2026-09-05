from __future__ import annotations

import hashlib
import inspect
import json
import math
import os
import re
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform

from harness import abort
from harness import nim
from harness.char_budget import cut_at_budget
from harness.contract import (
    ArmOutput, BuildStats, ModelUsage, generator_usage_from_nim, unpack_generation,
)
from harness.embed import EMBED_MODEL, _embed
from harness.progress import progress


DATABASE = os.environ.get("NEO4J_DATABASE", "herb-eval-volmax")
DATASET_ID = os.environ.get("HERB_DATASET_ID", "Salesforce__HERB")
RUN_ID = os.environ.get("HERB_TAG_RUN_ID", "pilot_full_herb")

INTERPRET_MODEL = "claude-haiku-4-5"

ALL_FACETS = ("topic", "entities", "activity", "temporal", "evidence")

NEUTRAL_FACETS = {f: 0.2 for f in ALL_FACETS}

GROUND_INDEX = "tag_emb"
DESC_INDEX = "chunk_desc_emb"

K_LEVELS = (8, 16, 32, 64)

KNN_OVERFETCH = 4

CURVE_WALK = os.environ.get("HERB_CURVE_WALK") == "1"

DOOR_TRACE = os.environ.get("HERB_DOOR_TRACE") == "1"

FRESH_INTERP = os.environ.get("HERB_FRESH_INTERP") == "1"

NO_REVIEW = os.environ.get("HERB_NO_REVIEW") == "1"


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    value = raw.strip()
    if value not in ("0", "1"):
        raise ValueError(f"{name} must be '0' or '1', got {raw!r}")
    return value == "1"


W_TAG = _env_float("HERB_W_TAG", 1.0)
W_DESC = _env_float("HERB_W_DESC", 1.0)
W_SCOPE = _env_float("HERB_W_SCOPE", 1.0)

STR_FACET = _env_float("HERB_STR_FACET", 1.0)
STR_WCHUNK = _env_float("HERB_STR_WCHUNK", 1.0)
STR_DESC_HINT = _env_float("HERB_STR_DESC_HINT", 1.0)
STR_SCOPE_MATCH = _env_float("HERB_STR_SCOPE_MATCH", 1.0)

DESC_HINT_M = _env_float("HERB_DESC_HINT_M", 2.0)

DESC_CUT = _env_bool("HERB_DESC_CUT", True)

RAW_QUESTION = _env_bool("HERB_RAW_QUESTION", True)

STR_CONCENTRATION = _env_float("HERB_STR_CONCENTRATION", 1.0)
if STR_CONCENTRATION < 0.0:
    raise ValueError(
        f"HERB_STR_CONCENTRATION must be >= 0.0, got {STR_CONCENTRATION!r} — a "
        f"negative strength would push down the chunks the query's own pool "
        f"concentrated on, and 0 is where the modifier switches off")
CONCENTRATION_ON = STR_CONCENTRATION > 0.0

PARTITIONS = ("product", "channel", "kind")

STR_AGREEMENT = _env_float("HERB_STR_AGREEMENT", 1.0)
if STR_AGREEMENT < 0.0:
    raise ValueError(
        f"HERB_STR_AGREEMENT must be >= 0.0, got {STR_AGREEMENT!r} — a negative "
        f"strength would push down the chunks several paths agree on, and 0 is "
        f"where the modifier switches off")
AGREEMENT_ON = STR_AGREEMENT > 0.0

PERSON_AMBIGUOUS = os.environ.get("HERB_PERSON_AMBIGUOUS", "all")
if PERSON_AMBIGUOUS not in ("all", "none"):
    raise ValueError(
        f"HERB_PERSON_AMBIGUOUS must be 'all' or 'none', got {PERSON_AMBIGUOUS!r}")

PERSON_NEAR = _env_bool("HERB_PERSON_NEAR", True)

EMPLOYEE_JSON = "metadata/employee.json"
CUSTOMERS_JSON = "metadata/customers_data.json"

_EID_LITERAL = re.compile(r"\beid_[0-9a-f]{8}\b")
_EMP_LITERAL = re.compile(r"\bEMP_\d{6,12}\b")
_CUST_LITERAL = re.compile(r"\bCUST-\d+\b")

_ID_SHAPE = re.compile(r"\b(?:eid_[0-9a-f]{8}|emp_\d{6,12}|cust-\d+)\b", re.I)

_NAME_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)

_INITIAL_STOP = ("a", "i")

STR_GUIDE = _env_float("HERB_STR_GUIDE", 0.0)
GUIDE_TAU = _env_float("HERB_GUIDE_TAU", 0.01)
GUIDE_C = _env_int("HERB_GUIDE_C", 128)
GUIDE_M = _env_float("HERB_GUIDE_M", 1.5)
GUIDE_LAMBDA = _env_float("HERB_GUIDE_LAMBDA", 0.05)
GUIDE_SEED = _env_int("HERB_GUIDE_SEED", 20260731)
if STR_GUIDE < 0.0:
    raise ValueError(f"HERB_STR_GUIDE must be >= 0.0, got {STR_GUIDE!r}")
if GUIDE_M <= 1.0:
    raise ValueError(
        f"HERB_GUIDE_M (the fuzzifier) must be > 1.0, got {GUIDE_M!r} — "
        f"membership exponents divide by m - 1, and m < 1 flips them toward "
        f"the farthest prototype")

if STR_GUIDE > 0:
    print(f"artefact_v2: cluster guide on (HERB_STR_GUIDE={STR_GUIDE}, "
          f"tau={GUIDE_TAU}, C={GUIDE_C}, m={GUIDE_M})", flush=True)

if CONCENTRATION_ON:
    print(f"artefact_v2: concentration modifier on "
          f"(HERB_STR_CONCENTRATION={STR_CONCENTRATION})", flush=True)

if AGREEMENT_ON:
    print(f"artefact_v2: agreement modifier on "
          f"(HERB_STR_AGREEMENT={STR_AGREEMENT})", flush=True)

if RAW_QUESTION:
    print("artefact_v2: the raw question probes beside the interpreted plan "
          "(HERB_RAW_QUESTION=1)", flush=True)

AGG = os.environ.get("HERB_AGG", "sum")
NORM = os.environ.get("HERB_NORM", "relative")
NORM_SCOPE = os.environ.get("HERB_NORM_SCOPE", "per_path")
if AGG not in ("sum", "max"):
    raise ValueError(f"HERB_AGG must be 'sum' or 'max', got {AGG!r}")
if NORM not in ("relative", "absolute", "none"):
    raise ValueError(f"HERB_NORM must be 'relative', 'absolute' or 'none', got {NORM!r}")
if NORM_SCOPE not in ("per_path", "global"):
    raise ValueError(f"HERB_NORM_SCOPE must be 'per_path' or 'global', got {NORM_SCOPE!r}")

ABS_REF_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "abs_ref_cache"

_NN_BLOCK_CELLS = 1 << 24

RETRIEVAL_FLAGS = {
    "HERB_CURVE_WALK": CURVE_WALK, "HERB_DOOR_TRACE": DOOR_TRACE,
    "HERB_DESC_CUT": DESC_CUT, "HERB_RAW_QUESTION": RAW_QUESTION,
    "HERB_FRESH_INTERP": FRESH_INTERP,
    "HERB_NO_REVIEW": NO_REVIEW,
    "HERB_AGG": AGG, "HERB_NORM": NORM, "HERB_NORM_SCOPE": NORM_SCOPE,
    "abs_ref_dist": None,
    "HERB_W_TAG": W_TAG, "HERB_W_DESC": W_DESC, "HERB_W_SCOPE": W_SCOPE,
    "HERB_STR_FACET": STR_FACET, "HERB_STR_WCHUNK": STR_WCHUNK,
    "HERB_STR_DESC_HINT": STR_DESC_HINT,
    "HERB_STR_SCOPE_MATCH": STR_SCOPE_MATCH, "HERB_DESC_HINT_M": DESC_HINT_M,
    "HERB_STR_CONCENTRATION": STR_CONCENTRATION,
    "HERB_STR_AGREEMENT": STR_AGREEMENT,
    "HERB_STR_GUIDE": STR_GUIDE, "HERB_GUIDE_TAU": GUIDE_TAU,
    "HERB_GUIDE_C": GUIDE_C, "HERB_GUIDE_M": GUIDE_M,
    "HERB_GUIDE_LAMBDA": GUIDE_LAMBDA, "HERB_GUIDE_SEED": GUIDE_SEED,
    "HERB_PERSON_AMBIGUOUS": PERSON_AMBIGUOUS, "HERB_PERSON_NEAR": PERSON_NEAR,
}

EMBED_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "query_embed_cache"
INTERP_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "interp_cache"

GUIDE_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "tag_cluster_cache"

GATE_SECTIONS = (
    "slack", "documents", "meeting_transcripts", "meeting_chats", "prs",
    "urls", "answerable_questions", "unanswerable_questions", "product_profile",
)

EXCLUDED_SECTIONS = ("answerable_questions", "unanswerable_questions", "product_profile")
_EXCLUDED_PARAM = list(EXCLUDED_SECTIONS)
OFFERED_SECTIONS = tuple(s for s in GATE_SECTIONS if s not in EXCLUDED_SECTIONS)

FILLER = {"data", "information", "content", "record", "text", "chunk", "item", "find"}

RAW_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "raw"

Generator = Callable[[str, list], object]


_GROUND_CYPHER = """
CALL db.index.vector.queryNodes($idx, $fetch, $vec) YIELD node, score
WHERE EXISTS { MATCH (node)<-[r:HAS_TAG]-(:Chunk) WHERE r.run_id = $runId }
RETURN node.name AS name, score AS sim, node.emb AS emb
ORDER BY sim DESC, name
LIMIT $k
"""

_AREA_CHUNKS_CYPHER = """
UNWIND $tags AS qt
MATCH (t:Tag {name: qt.name})<-[r:HAS_TAG]-(c:Chunk)<-[:HAS_CHUNK]-(f:File)
WHERE coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND r.run_id = $runId
  AND NOT (coalesce(c.section, "") IN $excludedSections)
WITH c, f, qt, r,
     reduce(dot = 0.0, fi IN range(0, size(coalesce(r.facets, [])) - 1) |
       dot + (CASE r.facets[fi]
                WHEN 'topic'    THEN qt.topic
                WHEN 'entities' THEN qt.entities
                WHEN 'activity' THEN qt.activity
                WHEN 'temporal' THEN qt.temporal
                WHEN 'evidence' THEN qt.evidence
                ELSE 0.0
              END) * coalesce(r.w_facets[fi], 0.0)) AS facetTerm
WITH c, f, qt.name AS name, qt.weight AS support,
     CASE WHEN $neutral THEN 1.0 ELSE coalesce(facetTerm, 0.0) END AS facetTerm,
     coalesce(r.w_chunk, 0.0) AS w_chunk
WITH c, f, name, support, w_chunk,
     support
       * CASE WHEN 1.0 + $strFacet * (facetTerm - 1.0) > 0.0
              THEN 1.0 + $strFacet * (facetTerm - 1.0) ELSE 0.0 END
       * CASE WHEN 1.0 + $strWchunk * (w_chunk - 1.0) > 0.0
              THEN 1.0 + $strWchunk * (w_chunk - 1.0) ELSE 0.0 END AS graded
ORDER BY graded DESC, support DESC, w_chunk DESC, name
WITH c, f, collect(graded)[0] AS graded
RETURN c.chunk_id AS chunkId, c.locator_json AS locator,
       f.rel_path AS relpath, f.sha256 AS sha256, graded
"""

_DESC_KNN_TEMPLATE = """
CALL db.index.vector.queryNodes($idx, $fetch, $vec) YIELD node AS c, score AS sim
MATCH (f:File)-[:HAS_CHUNK]->(c)
WHERE coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND NOT (coalesce(c.section, "") IN $excludedSections)
RETURN c.chunk_id AS chunkId, c.locator_json AS locator,
       f.rel_path AS relpath, f.sha256 AS sha256, sim,{emb}
       [(c)-[:product]->(p:Product) | p.name][0] AS product,
       c.section AS section,
       [(c)-[:channel]->(ch:Channel) | ch.id] AS channels,
       [(pe:Employee)-[:slack]->(:Channel)<-[:channel]-(c) | pe.eid]
         + [(pe:Employee)-[pl:meeting_transcripts|documents]->(:Product)
            <-[:product]-(c)-[:kind]->(pk:Kind)
            WHERE pk.name = type(pl) | pe.eid] AS eids,
       c.years AS years
ORDER BY sim DESC, chunkId
LIMIT $k
"""
_DESC_KNN_CYPHER = _DESC_KNN_TEMPLATE.format(emb="")
_DESC_KNN_EMB_CYPHER = _DESC_KNN_TEMPLATE.format(
    emb="\n       c.desc_emb AS desc_emb,")

_CHUNK_REGIONS_CYPHER = """
UNWIND $chunkIds AS cid
MATCH (c:Chunk {chunk_id: cid})
RETURN c.chunk_id AS chunkId,
       [(c)-[:product]->(p) | elementId(p)] AS product,
       [(c)-[:channel]->(ch) | elementId(ch)] AS channel,
       [(c)-[:kind]->(kd) | elementId(kd)] AS kind
"""

_REGION_SIZES_CYPHER = """
MATCH (c:Chunk)-[e:product|channel|kind]->(n)
WHERE coalesce(c.empty, false) = false
WITH type(e) AS partition, elementId(n) AS regionId, count(DISTINCT c) AS size
RETURN partition, regionId, size
"""

_PARTITION_POPULATION_CYPHER = """
MATCH (c:Chunk)-[e:product|channel|kind]->()
WHERE coalesce(c.empty, false) = false
WITH type(e) AS partition, count(DISTINCT c) AS population
RETURN partition, population
"""


def _hint_terms(gate: dict) -> tuple:
    terms, params = [], {}
    if gate.get("product"):
        terms.append("exists { (c)-[:product]->(p:Product) WHERE p.name = $g_product }")
        params["g_product"] = gate["product"]
    if gate.get("section"):
        terms.append("c.section = $g_section")
        params["g_section"] = gate["section"]
    if gate.get("channel"):
        terms.append("exists { (c)-[:channel]->(ch:Channel) WHERE ch.id IN $g_channel }")
        params["g_channel"] = list(gate.get("channel_ids") or ())
    for i, pids in enumerate(gate.get("persons") or ()):
        param = f"g_person_{i}"
        terms.append(
            "(exists { (pe:Employee)-[:slack]->(:Channel)<-[:channel]-(c) "
            "WHERE pe.eid IN $" + param + " } OR "
            "exists { (pe:Employee)-[pl:meeting_transcripts|documents]->(:Product)"
            "<-[:product]-(c)-[:kind]->(pk:Kind) "
            "WHERE pk.name = type(pl) AND pe.eid IN $" + param + " })")
        params[param] = list(pids)
    if gate.get("years"):
        terms.append("any(y IN $g_years WHERE y IN coalesce(c.years, []))")
        params["g_years"] = list(gate["years"])
    return terms, params


def _tag_affinity(session, names: list, gate: dict) -> dict:
    terms, params = _hint_terms(gate)
    if not terms:
        return {}
    cypher = f"""
UNWIND $names AS name
MATCH (t:Tag {{name: name}})<-[r:HAS_TAG]-(c:Chunk)<-[:HAS_CHUNK]-(f:File)
WHERE r.run_id = $runId
  AND coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND NOT (coalesce(c.section, "") IN $excludedSections)
RETURN name, count(c) AS total,
       sum(CASE WHEN {" OR ".join(terms)} THEN 1 ELSE 0 END) AS hits
"""
    res = session.run(cypher, names=names, runId=RUN_ID, datasetId=DATASET_ID,
                      excludedSections=_EXCLUDED_PARAM, **params)
    return {rec["name"]: (float(rec["hits"]) / float(rec["total"]))
            for rec in res if rec["total"]}


def _hint_match(row: dict, gate: dict) -> bool:
    for f in ("product", "section"):
        if gate.get(f) and row.get(f) == gate[f]:
            return True
    if gate.get("channel") and set(gate.get("channel_ids") or ()) & set(row.get("channels") or []):
        return True
    if gate.get("years") and set(gate["years"]) & set(row.get("years") or []):
        return True
    eids = set(row.get("eids") or [])
    return any(eids & set(pids) for pids in gate.get("persons") or ())


def _corpus_path(root: Path, relpath: str) -> Path:
    path = (root / relpath).resolve()
    if not path.is_relative_to(root.resolve()):
        raise RuntimeError(
            f"relpath {relpath!r} resolves outside the corpus root — refusing to read it")
    return path


def _pointer_value(doc, pointer: str):
    node = doc
    for token in pointer.split("/")[1:]:
        token = token.replace("~1", "/").replace("~0", "~")
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


def _channel_names(session, root: Path) -> dict:
    files = {r["fid"]: r["rel"] for r in
             session.run("MATCH (f:File) RETURN f.file_id AS fid, f.rel_path AS rel")}
    channels = [dict(r) for r in session.run(
        "MATCH (ch:Channel) RETURN ch.id AS id, ch.file_id AS fid, ch.pointer AS ptr "
        "ORDER BY ch.id")]
    by_file: dict = {}
    for ch in channels:
        by_file.setdefault(ch["fid"], []).append(ch)
    names: dict = {}
    for fid in progress(sorted(by_file), desc="channel names", unit="file"):
        doc = json.loads(_corpus_path(root, files[fid]).read_text(encoding="utf-8"))
        for ch in by_file[fid]:
            names.setdefault(_pointer_value(doc, ch["ptr"])["name"], []).append(ch["id"])
    if not names:
        raise RuntimeError(
            f"no channel in {DATABASE!r} resolves to a name through its pointer — "
            f"a stated channel could never be matched")
    return {name: tuple(ids) for name, ids in names.items()}


def _name_key(name: str) -> tuple:
    return tuple(m.group(0).lower() for m in _NAME_TOKEN.finditer(name))


def _load_person_directory(corpus_root) -> dict:
    root = Path(corpus_root)
    employee_path = root / EMPLOYEE_JSON
    customers_path = root / CUSTOMERS_JSON
    for path in (employee_path, customers_path):
        if not path.is_file():
            raise RuntimeError(
                f"person directory missing at {path} — the stated-scope gate "
                f"resolves query names against the corpus view's own "
                f"directories.")
    employees = json.loads(employee_path.read_text(encoding="utf-8"))
    customers = json.loads(customers_path.read_text(encoding="utf-8"))
    entries = [((rec.get("name") or "").strip(), pid)
               for pid, rec in employees.items()]
    entries += [((rec.get("name") or "").strip(), rec.get("id"))
                for rec in customers]

    ids: dict = {}
    surface: dict = {}
    token_sets: dict = {}
    initials: dict = {}

    def add(index: dict, key, pid: str) -> None:
        holders = index.setdefault(key, [])
        if pid not in holders:
            holders.append(pid)

    for name, pid in entries:
        key = _name_key(name)
        if not key or not pid:
            continue
        add(ids, key, pid)
        surface.setdefault(key, name)
        if len(set(key)) == len(key):
            add(token_sets, frozenset(key), pid)
        add(initials, (key[0][0], key[-1]), pid)
    all_ids = frozenset(pid for _, pid in entries if pid)
    return {
        "ids": {k: tuple(sorted(v)) for k, v in ids.items()},
        "surface": surface,
        "token_sets": {k: tuple(sorted(v)) for k, v in token_sets.items()},
        "initials": {k: tuple(sorted(v)) for k, v in initials.items()},
        "lengths": tuple(sorted({len(k) for k in ids}, reverse=True)),
        "all_ids": all_ids,
        "counts": {"employees": len(employees), "customers": len(customers),
                   "names": len(ids),
                   "ids": len(all_ids)},
    }


def _is_initial(text: str, token: tuple) -> bool:
    word, start, end = token
    if len(word) != 1 or not text[start].isupper():
        return False
    return text[end:end + 1] == "." or word not in _INITIAL_STOP


def resolve_persons(text: str, directory: dict) -> list:
    if directory is None:
        raise RuntimeError(
            "no person directory is loaded — `prepare_over_corpus` fills "
            "Prepared.directory, and resolution needs it.")
    tokens = [(m.group(0).lower(), m.start(), m.end())
              for m in _NAME_TOKEN.finditer(text)]
    claimed: set = set()
    found = []

    def span_tokens(start: int, end: int) -> list:
        return [i for i, (_, s, e) in enumerate(tokens) if s >= start and e <= end]

    for pattern in (_EID_LITERAL, _EMP_LITERAL, _CUST_LITERAL):
        for m in pattern.finditer(text):
            at = span_tokens(m.start(), m.end())
            if not at or claimed & set(at):
                continue
            claimed.update(at)
            found.append((at[0], m.group(0), "id_literal", (m.group(0),)))

    for m in _ID_SHAPE.finditer(text):
        at = span_tokens(m.start(), m.end())
        if not at or claimed & set(at):
            continue
        claimed.update(at)
        found.append((at[0], m.group(0), "unresolved", ()))

    for width in directory["lengths"]:
        for i in range(len(tokens) - width + 1):
            span_at = range(i, i + width)
            if claimed & set(span_at):
                continue
            key = tuple(t for t, _, _ in tokens[i:i + width])
            hit = directory["ids"].get(key)
            if hit is None:
                continue
            claimed.update(span_at)
            written = text[tokens[i][1]:tokens[i + width - 1][2]]
            found.append((i, written,
                          "exact" if written == directory["surface"][key] else "normalized",
                          hit))

    if PERSON_NEAR:
        for i in range(len(tokens) - 1):
            if i in claimed or i + 1 in claimed:
                continue
            pair = (tokens[i][0], tokens[i + 1][0])
            hit, rule = None, ""
            if len(set(pair)) == 2:
                hit, rule = directory["token_sets"].get(frozenset(pair)), "reordered"
            if hit is None and _is_initial(text, tokens[i]):
                hit, rule = directory["initials"].get(pair), "initial"
            if hit is None:
                continue
            claimed.update((i, i + 1))
            found.append((i, text[tokens[i][1]:tokens[i + 1][2]], rule, hit))

    for i in range(len(tokens) - 1):
        if i in claimed or i + 1 in claimed:
            continue
        if text[tokens[i][1]].isupper() and text[tokens[i + 1][1]].isupper():
            claimed.update((i, i + 1))
            found.append((i, text[tokens[i][1]:tokens[i + 1][2]], "unresolved", ()))

    mentions, seen = [], set()
    for _, written, rule, hit in sorted(found, key=lambda f: f[0]):
        ids = tuple(hit)
        if len(ids) > 1 and PERSON_AMBIGUOUS == "none":
            mentions.append({"name": written, "rule": "ambiguous", "ids": []})
            continue
        if ids:
            if ids in seen:
                continue
            seen.add(ids)
        mentions.append({"name": written, "rule": rule, "ids": list(ids)})
    return mentions


def _gate_persons(gate: dict, persons: Optional[list],
                  directory: Optional[dict]) -> tuple:
    stated = [tuple(m["ids"]) for m in (persons or []) if m["ids"]]
    eid = gate.get("employee_id")
    unresolved = None
    if eid:
        if directory is None:
            raise RuntimeError(
                "no person directory is loaded — `prepare_over_corpus` fills "
                "Prepared.directory, and the gate employee_id is held to it.")
        if _EID_LITERAL.fullmatch(eid) and eid in directory["all_ids"]:
            if not any(eid in ids for ids in stated):
                stated.append((eid,))
        elif not any(eid == m["name"] or eid in m["ids"]
                     for m in (persons or [])):
            unresolved = {"name": eid, "rule": "unresolved", "ids": []}
    return tuple(stated), unresolved


def _embed_key(text: str, input_type: str) -> str:
    h = hashlib.sha256()
    for field in (EMBED_MODEL, input_type, text):
        b = field.encode("utf-8")
        h.update(len(b).to_bytes(8, "big"))
        h.update(b)
    return h.hexdigest()


def _load_cached_vec(key: str):
    path = EMBED_CACHE_DIR / f"{key}.npy"
    if not path.is_file():
        return None
    try:
        return np.load(path)
    except (ValueError, OSError):
        return None


def _store_cached_vec(key: str, vec: np.ndarray) -> None:
    EMBED_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=EMBED_CACHE_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            np.save(f, np.asarray(vec, dtype=np.float32))
        os.replace(tmp, EMBED_CACHE_DIR / f"{key}.npy")
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _embed_cached(texts: list, input_type: str) -> tuple:
    keys = [_embed_key(t, input_type) for t in texts]
    rows: dict = {}
    misses, miss_at = [], []
    for i, (t, key) in enumerate(zip(texts, keys)):
        vec = _load_cached_vec(key)
        if vec is None:
            misses.append(t)
            miss_at.append(i)
        else:
            rows[i] = vec
    calls = tok_in = tok_out = 0
    secs = 0.0
    if misses:
        mat, calls, tok_in, tok_out, secs = _embed(misses, input_type, bar=False)
        for j, i in enumerate(miss_at):
            vec = np.asarray(mat[j], dtype=np.float32)
            rows[i] = vec
            _store_cached_vec(keys[i], vec)
    return (np.asarray([rows[i] for i in range(len(texts))], dtype=np.float32),
            calls, tok_in, tok_out, secs)


_TAG_POOL_MATCH = """
MATCH (t:Tag)
WHERE t.emb IS NOT NULL
  AND EXISTS { MATCH (t)<-[r:HAS_TAG]-(:Chunk) WHERE r.run_id = $runId }
"""

_DESC_POOL_MATCH = """
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
WHERE coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND NOT (coalesce(c.section, "") IN $excludedSections)
  AND c.desc_emb IS NOT NULL
"""


def _median_nn_dist(embs: np.ndarray, label: str) -> float:
    n = len(embs)
    if n < 2:
        raise RuntimeError(
            f"{label} holds {n} embedding(s) — no nearest neighbor exists to "
            f"derive a reference distance from")
    step = max(1, _NN_BLOCK_CELLS // n)
    nn = np.empty(n)
    for start in progress(range(0, n, step), desc=f"nn dist {label}", unit="block"):
        stop = min(start + step, n)
        sims = embs[start:stop] @ embs.T
        sims[np.arange(stop - start), np.arange(start, stop)] = -1.0
        nn[start:stop] = 1.0 - np.clip(sims.max(axis=1), -1.0, 1.0)
    return float(np.median(nn))


def _median_cross_nn_dist(queries: np.ndarray, targets: np.ndarray,
                          label: str) -> float:
    if not len(queries) or not len(targets):
        raise RuntimeError(
            f"{label} pairs {len(queries)} query embedding(s) against "
            f"{len(targets)} target(s) — no nearest neighbor exists to derive "
            f"a reference distance from")
    step = max(1, _NN_BLOCK_CELLS // len(targets))
    nn = np.empty(len(queries))
    for start in progress(range(0, len(queries), step),
                          desc=f"nn dist {label}", unit="block"):
        stop = min(start + step, len(queries))
        sims = queries[start:stop] @ targets.T
        nn[start:stop] = 1.0 - np.clip(sims.max(axis=1), -1.0, 1.0)
    return float(np.median(nn))


def _abs_ref_key() -> str:
    h = hashlib.sha256()
    for field in (DATABASE, RUN_ID, DATASET_ID):
        b = field.encode("utf-8")
        h.update(len(b).to_bytes(8, "big"))
        h.update(b)
    return h.hexdigest()


def _abs_ref_dists(session) -> dict:
    pools = {
        GROUND_INDEX: (_TAG_POOL_MATCH, "t.emb", {"runId": RUN_ID}),
        DESC_INDEX: (_DESC_POOL_MATCH, "c.desc_emb",
                     {"datasetId": DATASET_ID,
                      "excludedSections": _EXCLUDED_PARAM}),
    }
    counts = {space: session.run(match + "RETURN count(*) AS n",
                                 **params).single()["n"]
              for space, (match, _, params) in pools.items()}
    path = ABS_REF_CACHE_DIR / f"{_abs_ref_key()}.json"
    if path.is_file():
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            entry = None
        if isinstance(entry, dict) and all(
                isinstance(entry.get(space), dict)
                and entry[space].get("n") == counts[space]
                and isinstance(entry[space].get("median_nn_dist_retrieval"), float)
                for space in pools):
            return {space: entry[space]["median_nn_dist_retrieval"]
                    for space in pools}
    print("artefact_v2: measuring the absolute-normalization references — one "
          "nearest-neighbor pass per path, cached per graph …", flush=True)
    embs = {}
    for space, (match, column, params) in pools.items():
        embs[space] = _unit(np.asarray(
            [r["emb"] for r in session.run(match + f"RETURN {column} AS emb",
                                           **params)],
            dtype=np.float64))
        if len(embs[space]) != counts[space]:
            raise RuntimeError(
                f"{space} returned {len(embs[space])} embeddings against a "
                f"count of {counts[space]} — the graph changed under the "
                f"measurement")
    dists = {
        GROUND_INDEX: _median_cross_nn_dist(
            embs[DESC_INDEX], embs[GROUND_INDEX], "desc->tag") / 2.0,
        DESC_INDEX: _median_nn_dist(embs[DESC_INDEX], DESC_INDEX) / 2.0,
    }
    entry = {space: {"n": counts[space],
                     "median_nn_dist_retrieval": dists[space]}
             for space in pools}
    ABS_REF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=ABS_REF_CACHE_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return dists


@dataclass
class Prepared:
    driver: object
    channels: dict
    build_stats: Optional[BuildStats] = None
    directory: Optional[dict] = None
    region_size: Optional[dict] = None
    population: Optional[dict] = None
    abs_ref_dist: Optional[dict] = None


def _driver():
    from neo4j import GraphDatabase
    nim._load_dotenv()
    pw = os.environ.get("NEO4J_PASSWORD")
    if not pw:
        raise RuntimeError("NEO4J_PASSWORD is not set — add it to .env at the repo root (like NVIDIA_API_KEY).")
    uri = os.environ.get("NEO4J_URI", "neo4j://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    return GraphDatabase.driver(uri, auth=(user, pw),
                                notifications_min_severity="OFF")


def prepare_over_corpus(corpus) -> Prepared:
    t0 = time.perf_counter()
    corpus_root = Path(corpus)
    print(f"artefact_v2: opening {DATABASE} …", flush=True)
    directory = _load_person_directory(corpus_root)
    drv = _driver()
    try:
        with drv.session(database=DATABASE) as s:
            s.run("RETURN 1").consume()
            present = s.run(
                "SHOW INDEXES YIELD name WHERE name IN [$t, $d] "
                "RETURN collect(name) AS names",
                t=GROUND_INDEX, d=DESC_INDEX).single()["names"]
            no_desc = s.run(
                "MATCH (c:Chunk) WHERE coalesce(c.empty, false) = false "
                "AND c.desc_emb IS NULL RETURN count(c) AS n").single()["n"]
            multi = s.run(
                "MATCH (c:Chunk) WITH c, count { (:File)-[:HAS_CHUNK]->(c) } AS n "
                "WHERE n <> 1 RETURN count(*) AS bad").single()["bad"]
            employee_nodes = s.run(
                "MATCH (e:Employee) RETURN count(e) AS n").single()["n"]
            channels = _channel_names(s, corpus_root.parent)
            region_size = population = None
            if CONCENTRATION_ON:
                print("artefact_v2: reading the partition census …", flush=True)
                region_size = {(r["partition"], r["regionId"]): r["size"]
                               for r in s.run(_REGION_SIZES_CYPHER)}
                population = {r["partition"]: r["population"]
                              for r in s.run(_PARTITION_POPULATION_CYPHER)}
            abs_ref_dist = None
            if NORM == "absolute":
                abs_ref_dist = _abs_ref_dists(s)
        if multi:
            raise RuntimeError(
                f"{multi} chunk(s) in {DATABASE!r} without exactly one File — "
                f"pointer resolution would be ambiguous")
        missing = sorted({GROUND_INDEX, DESC_INDEX} - set(present))
        if missing or no_desc:
            raise RuntimeError(
                f"semantic layer incomplete in {DATABASE!r} (missing indexes: {missing or 'none'}, "
                f"non-empty chunks without desc_emb: {no_desc}) — the tag pools, the "
                f"description path and the stated-scope path all read that layer.")
        if not employee_nodes:
            raise RuntimeError(
                f"{DATABASE!r} carries no Employee nodes — a named person's "
                f"stated-scope term walks `Employee -[:slack]-> Channel` and "
                f"`Employee -[:meeting_transcripts|documents]-> Product` to reach "
                f"a chunk. Point NEO4J_DATABASE at a database that carries them.")
        print(f"artefact_v2: {len(channels)} channel names", flush=True)
        counts = directory["counts"]
        print(f"artefact_v2: person directory {counts['employees']} employees + "
              f"{counts['customers']} customers -> {counts['names']} distinct names "
              f"over {counts['ids']} ids; {DATABASE} carries {employee_nodes} Employee nodes",
              flush=True)
        if CONCENTRATION_ON:
            absent = sorted(set(PARTITIONS) - set(population))
            if absent:
                raise RuntimeError(
                    f"no chunk in {DATABASE!r} carries the {absent} partition(s) — "
                    f"a region's lift there would be measured against an empty spread.")
            census = " | ".join(
                f"{p} {sum(1 for key in region_size if key[0] == p)} regions over "
                f"{population[p]} chunks" for p in PARTITIONS)
            print(f"artefact_v2: partition census: {census}", flush=True)
        if NORM == "absolute":
            print(f"artefact_v2: absolute references (retrieval units) — "
                  f"desc->tag median NN {abs_ref_dist[GROUND_INDEX]:.4f} "
                  f"({GROUND_INDEX}), desc median NN "
                  f"{abs_ref_dist[DESC_INDEX]:.4f} ({DESC_INDEX})", flush=True)
            RETRIEVAL_FLAGS["abs_ref_dist"] = dict(abs_ref_dist)
    except Exception:
        drv.close()
        raise
    return Prepared(
        driver=drv,
        channels=channels,
        build_stats=BuildStats(
            build_time_s=time.perf_counter() - t0,
            model=ModelUsage(),
            models=[EMBED_MODEL],
        ),
        directory=directory,
        region_size=region_size,
        population=population,
        abs_ref_dist=abs_ref_dist,
    )


def _qid_text(question) -> tuple:
    if hasattr(question, "question") and hasattr(question, "id"):
        return question.id, question.question
    if isinstance(question, dict):
        return question.get("id", ""), question.get("question", "")
    if isinstance(question, (tuple, list)) and len(question) == 2:
        return question[0], question[1]
    return "", str(question)


def _extract_json(text: str) -> dict:
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    body = fence.group(1).strip() if fence else text
    start = body.find("{")
    if start == -1:
        raise ValueError(f"no JSON object in model output: {text[:200]!r}")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(body)):
        ch = body[i]
        if esc:
            esc = False
            continue
        if ch == "\\" and in_str:
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(body[start:i + 1])
    raise ValueError(f"unterminated JSON object in model output: {text[:200]!r}")


_PASS1_SYSTEM = (
    "You interpret a user query for graph retrieval. Work in three steps. "
    'STEP 1: write "description" — a concise, self-contained 1-3 sentence statement of the '
    "underlying information need (what the user actually wants to find, including implied "
    "entities/scope), in plain declarative prose, not a restatement of the question. "
    'STEP 2: derive "tags" FROM that description — the query\'s distinct parts as specific '
    "noun phrases, named entities, systems, or actions. No generic filler words. "
    'STEP 3: extract "gate" — structured scope hints ONLY when the query explicitly names them, '
    'else null/[]. Fields: product (a "*Force"/"*Genie"-style product name if named), '
    f"section (one of: {', '.join(OFFERED_SECTIONS)} — map synonyms, e.g. \"pull requests\"->prs, \"chat\"->slack), "
    'channel (a Slack channel name if given), employee_id (an "eid_..." id if given), '
    "years (array of 4-digit years explicitly mentioned). Do NOT guess values not in the query. "
    'Return ONLY valid JSON: {"description":"...","tags":["tag1"],'
    '"gate":{"product":null,"section":null,"channel":null,"employee_id":null,"years":[]}}.'
)

_PASS2_SYSTEM = (
    "Score retrieval tags against five facets (each 0.0-1.0). "
    "topic: subject matter. entities: named people/orgs/products/systems. "
    "activity: events/processes/actions. temporal: time relevance. evidence: answer material type. "
    'Return ONLY valid JSON: {"scores":[{"t":"tag","facets":{"topic":0.0,"entities":0.0,"activity":0.0,"temporal":0.0,"evidence":0.0}}]}'
)

_REVIEW_SYSTEM = (
    "You are driving evidence retrieval for a question. You see the evidence "
    "collected so far, best-first. Decide whether it is sufficient to answer "
    "the question. Say sufficient ONLY when the answer is actually contained "
    "in the evidence shown — more evidence arrives if you say it is not. "
    'Return ONLY valid JSON: {"sufficient": true} or {"sufficient": false}.'
)


class InterpreterError(RuntimeError):

    def __init__(self, message: str, calls: int = 0, tokens_in: int = 0,
                 tokens_out: int = 0, time_s: float = 0.0):
        super().__init__(message)
        self.calls = calls
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.time_s = time_s


def _chat_json(model: str, system: str, user: str, max_tokens: int,
               validate: Optional[Callable[[dict], None]] = None) -> tuple:
    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    calls = tok_in = tok_out = 0
    elapsed = 0.0

    def fail(message: str) -> InterpreterError:
        return InterpreterError(message, calls=calls, tokens_in=tok_in,
                                tokens_out=tok_out, time_s=elapsed)

    for attempt in (1, 2):
        t0 = time.perf_counter()
        resp = nim.post("/chat/completions", payload, timeout=480.0)
        elapsed += time.perf_counter() - t0
        calls += 1
        ti, to = generator_usage_from_nim(resp.get("usage"))
        tok_in += ti
        tok_out += to
        choices = resp.get("choices") or []
        finish = choices[0].get("finish_reason") if choices else "no choices"
        content = (choices[0].get("message") or {}).get("content") if choices else None
        if not content:
            raise fail(f"interpreter returned empty content (finish_reason={finish})")
        if finish == "length":
            raise fail(
                f"interpreter truncated at max_tokens={max_tokens} (finish_reason=length) — raise the budget")
        try:
            parsed = _extract_json(content)
            if validate is not None:
                validate(parsed)
            return parsed, tok_in, tok_out, elapsed
        except ValueError as e:
            if attempt == 2:
                raise fail(f"interpreter emitted a malformed payload twice: {e}") from e


def _clean_tag(raw: str) -> str:
    """A tag as the vocabulary writes it — collapsed whitespace, nothing else.
    Case and punctuation carry meaning in the tag names the corpus holds."""
    return re.sub(r"\s+", " ", raw).strip()


def _readable(name: str) -> str:
    return name.strip()


def _parse_gate(raw) -> dict:
    """Normalise the model's loose gate into strict scope hints: string-or-null
    fields, a section restricted to the offered set, 4-digit years."""
    g = raw if isinstance(raw, dict) else {}

    def s(v):
        return v.strip() if isinstance(v, str) and v.strip() else None

    section = s(g.get("section"))
    years, seen = [], set()
    for y in (g.get("years") or []):
        try:
            yi = int(y)
        except (TypeError, ValueError):
            continue
        if 1000 <= yi <= 9999 and yi not in seen:
            seen.add(yi)
            years.append(yi)
    return {
        "product": s(g.get("product")),
        "section": section if section in OFFERED_SECTIONS else None,
        "channel": s(g.get("channel")),
        "employee_id": s(g.get("employee_id")),
        "years": years,
    }


def _validate_scores(parsed: dict) -> None:
    """Pass-2 payload shape: `scores` is a list of rows, each {t: str,
    facets: {facet: number}}. A violation raises ValueError, which
    `_chat_json` retries like any malformed emission."""
    scores = parsed.get("scores")
    if not isinstance(scores, list):
        raise ValueError(f"scores is not a list: {type(scores).__name__}")
    for row in scores:
        if not isinstance(row, dict) or not isinstance(row.get("t"), str):
            raise ValueError(f"score row malformed: {row!r}")
        facets = row.get("facets")
        if not isinstance(facets, dict):
            raise ValueError(f"facets missing for tag {row['t']!r}")
        for f, v in facets.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError(f"facet {f!r} of tag {row['t']!r} is not a number: {v!r}")


def _interpret(text: str, model: str) -> tuple:
    """interpret a question -> (plan, calls, tokens_in, tokens_out, time_s).
    plan = {description, parts:[{t, facets}], gate}. Pass 2 is skipped when
    pass 1 yields no usable parts; the description then stands in as the
    single part. Tags pass 2 leaves unscored keep the neutral default and are
    listed in plan["unscored"]."""
    p1, in1, out1, t1 = _chat_json(model, _PASS1_SYSTEM, f"User query: {text}", 512)
    description = p1.get("description") or text
    gate = _parse_gate(p1.get("gate"))
    raw_parts, seen = [], set()
    for raw in (p1.get("tags") or []):
        t = _clean_tag(str(raw))
        key = t.casefold()
        if len(t) > 1 and key not in FILLER and key not in seen:
            seen.add(key)
            raw_parts.append(t)

    if not raw_parts:
        neutral = {f: 0.2 for f in ALL_FACETS}
        return ({"description": description,
                 "parts": [{"t": description, "facets": neutral}],
                 "gate": gate},
                1, in1, out1, t1)

    p2, in2, out2, t2 = _chat_json(
        model, _PASS2_SYSTEM,
        f"Original query: {text}\n\nScore these tags:\n{json.dumps(raw_parts)}", 1024,
        validate=_validate_scores)
    # echoed tags match on the same cleaned form the parts carry, so case or
    # spacing drift in the echo cannot detach a score row
    score_map = {_clean_tag(row["t"]).casefold(): (row.get("facets") or {})
                 for row in (p2.get("scores") or [])}
    default = {f: 0.2 for f in ALL_FACETS}
    unscored = [t for t in raw_parts if t.casefold() not in score_map]
    parts = []
    for t in raw_parts:
        scored = score_map.get(t.casefold(), default)
        facets = {f: min(1.0, max(0.0, float(scored.get(f, 0.2))))
                  for f in ALL_FACETS}
        parts.append({"t": t, "facets": facets})
    plan = {"description": description, "parts": parts, "gate": gate}
    if unscored:
        plan["unscored"] = unscored
    return plan, 2, in1 + in2, out1 + out2, t1 + t2


_INTERP_SIG = hashlib.sha256("\x00".join([
    _PASS1_SYSTEM, _PASS2_SYSTEM, repr(sorted(FILLER)), repr(ALL_FACETS),
    inspect.getsource(_interpret), inspect.getsource(_clean_tag),
    inspect.getsource(_parse_gate), inspect.getsource(_validate_scores),
    inspect.getsource(_extract_json),
]).encode("utf-8")).hexdigest()


def _interp_key(text: str, model: str) -> str:
    h = hashlib.sha256()
    for field in (model, _INTERP_SIG, text):
        b = field.encode("utf-8")
        h.update(len(b).to_bytes(8, "big"))
        h.update(b)
    return h.hexdigest()


def _store_interp(key: str, plan: dict) -> None:
    INTERP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=INTERP_CACHE_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False)
        os.replace(tmp, INTERP_CACHE_DIR / f"{key}.json")
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _interpret_cached(text: str, model: str) -> tuple:
    key = _interp_key(text, model)
    path = INTERP_CACHE_DIR / f"{key}.json"
    if not FRESH_INTERP and path.is_file():
        try:
            plan = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            plan = None
        if isinstance(plan, dict) and isinstance(plan.get("parts"), list):
            return plan, 0, 0, 0, 0.0
    plan, calls, tok_in, tok_out, secs = _interpret(text, model)
    _store_interp(key, plan)
    return plan, calls, tok_in, tok_out, secs


def _unit(a: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(a, axis=-1, keepdims=True)
    norms[norms == 0] = 1.0
    return a / norms


def _gap_break(gaps: list, gap: float) -> bool:
    if len(gaps) < 3 or gap <= 1e-9:
        return False
    return gap > float(np.mean(gaps)) + 2.0 * float(np.std(gaps)) + 1e-9


def _multi_k_support(dists: np.ndarray, extend: bool = False,
                     normalize: bool = True) -> np.ndarray:
    levels = list(K_LEVELS)
    if extend:
        while levels[-1] < len(dists):
            levels.append(levels[-1] * 2)
    support = np.zeros(len(dists))
    for k in levels:
        kk = min(k, len(dists))
        support[:kk] += 1.0 / np.maximum(dists[:kk], 1e-6) ** 2
    if not normalize:
        return support
    total = support.sum()
    return support / total if total > 0 else support


def _norm_pool(base: dict, lo: float, hi: float) -> dict:
    if not base:
        return {}
    if hi <= lo:
        return {cid: 1.0 for cid in base}
    span = hi - lo
    return {cid: (v - lo) / span for cid, v in base.items()}


def _minmax(raw: dict) -> dict:
    if not raw:
        return {}
    return _norm_pool(raw, min(raw.values()), max(raw.values()))


def _absolute(base: float, ref: float) -> float:
    return base / (base + ref)


def _n_levels(n: int) -> int:
    levels = list(K_LEVELS)
    while levels[-1] < n:
        levels.append(levels[-1] * 2)
    return len(levels)


def _agg(slots: list) -> dict:
    base: dict = {}
    for slot in slots:
        for cid, sup in slot.items():
            if cid not in base:
                base[cid] = sup
            elif AGG == "max":
                base[cid] = max(base[cid], sup)
            else:
                base[cid] = base[cid] + sup
    return base


def _normalize(tag_base: dict, desc_base: dict, scope_base: dict,
               scope_levels: int, ref_dist: Optional[dict]) -> tuple:
    if NORM == "none":
        return tag_base, desc_base, scope_base
    if NORM == "absolute":
        if ref_dist is None:
            raise RuntimeError(
                "HERB_NORM=absolute and no reference distances are loaded — "
                "`prepare_over_corpus` fills Prepared.abs_ref_dist from the "
                "graph's own geometry.")
        tag_ref = len(K_LEVELS) / ref_dist[GROUND_INDEX] ** 2
        desc_ref = len(K_LEVELS) / ref_dist[DESC_INDEX] ** 2
        scope_ref = scope_levels / ref_dist[DESC_INDEX] ** 2
        return ({cid: _absolute(v, tag_ref) for cid, v in tag_base.items()},
                {cid: _absolute(v, desc_ref) for cid, v in desc_base.items()},
                {cid: _absolute(v, scope_ref) for cid, v in scope_base.items()})
    if NORM_SCOPE == "global":
        allvals = [*tag_base.values(), *desc_base.values(), *scope_base.values()]
        lo = min(allvals) if allvals else 0.0
        hi = max(allvals) if allvals else 0.0
        return (_norm_pool(tag_base, lo, hi), _norm_pool(desc_base, lo, hi),
                _norm_pool(scope_base, lo, hi))
    return _minmax(tag_base), _minmax(desc_base), _minmax(scope_base)


def _mod(m: float, strength: float) -> float:
    return max(0.0, 1.0 + strength * (m - 1.0))


def _level_chain(embs: np.ndarray, anchor: int, dist_shaper=None) -> list:
    n = len(embs)
    if n == 1:
        return [(0.0, [0])]
    D = 1.0 - np.clip(embs @ embs.T, -1.0, 1.0)
    np.fill_diagonal(D, 0.0)
    if dist_shaper is not None:
        D = dist_shaper(embs, D)
        np.fill_diagonal(D, 0.0)
    Z = linkage(squareform(D, checks=False), method="average")

    members = {i: [i] for i in range(n)}
    for i, (a, b, _, _) in enumerate(Z):
        members[n + i] = members[int(a)] + members[int(b)]

    levels = [(0.0, [anchor])]
    node = anchor
    for i, (a, b, height, _) in enumerate(Z):
        a, b = int(a), int(b)
        if node in (a, b):
            sibling = b if node == a else a
            levels.append((float(height), list(members[sibling])))
            node = n + i
    return levels


_GUIDE: Optional[dict] = None


def _guide_key() -> str:
    return (f"{DATABASE}__{RUN_ID}__C{GUIDE_C}__m{GUIDE_M}"
            f"__lam{GUIDE_LAMBDA}__seed{GUIDE_SEED}")


def _guide_tables() -> dict:
    global _GUIDE
    if _GUIDE is None:
        entry = GUIDE_CACHE_DIR / _guide_key()
        if not (entry / "manifest.json").is_file():
            raise RuntimeError(
                f"tag-cluster cache missing at {entry} — run `python build_tag_clusters.py` once.")
        with np.load(entry / "memberships.npz") as z:
            U = np.stack([z[f] for f in ALL_FACETS])
        names = json.loads((entry / "tags.json").read_text(encoding="utf-8"))
        _GUIDE = {"U": U, "row": {n: i for i, n in enumerate(names)}}
    return _GUIDE


def _guidance(names: list, facets: dict, stats: Optional[dict] = None) -> np.ndarray:
    tables = _guide_tables()
    U, row = tables["U"], tables["row"]
    phi = np.array([float(facets.get(f, 0.0)) for f in ALL_FACETS])
    total = phi.sum()
    phi = phi / total if total > 0 else np.full(len(ALL_FACETS), 1.0 / len(ALL_FACETS))
    g = np.zeros(len(names))
    hit = [(i, row[n]) for i, n in enumerate(names) if n in row]
    if hit:
        at, rows = zip(*hit)
        cells = phi[:, None, None] * U[:, list(rows), :]
        g[list(at)] = np.where(cells >= GUIDE_TAU, cells, 0.0).sum(axis=(0, 2))
    if stats is not None:
        stats["matched"] += len(hit)
        stats["unmatched"] += len(names) - len(hit)
        stats["g_sum"] += float(g.sum())
        stats["g_n"] += len(names)
    return g


def _part_levels(session, part: dict, vec: np.ndarray, gate: dict,
                 shaper=None, dist_shaper=None, guide_stats=None) -> list:
    recs = list(session.run(
        _GROUND_CYPHER, idx=GROUND_INDEX, k=K_LEVELS[-1],
        fetch=KNN_OVERFETCH * K_LEVELS[-1], runId=RUN_ID,
        vec=[float(x) for x in vec]))
    rows = [(r["name"], r["sim"], r["emb"]) for r in recs
            if r["name"] and r["sim"] is not None and r["emb"] is not None]
    if not rows:
        return []
    names = [n for n, _, _ in rows]
    embs = _unit(np.asarray([e for _, _, e in rows], dtype=np.float64))
    dists = np.array([1.0 - float(s) for _, s, _ in rows])

    support = _multi_k_support(dists, normalize=False)
    affinity = _tag_affinity(session, names, gate)
    if affinity:
        support = support * np.array([1.0 + affinity.get(n, 0.0) for n in names])
    if STR_GUIDE > 0:
        support = support * (1.0 + STR_GUIDE * _guidance(names, part["facets"], guide_stats))
    if shaper is not None:
        support = shaper(names, embs, support)
    anchor = int(np.argmax(support))
    return [{"height": h,
             "tags": [(names[i], float(support[i])) for i in added]}
            for h, added in _level_chain(embs, anchor, dist_shaper)]


def _open_area(session, area: dict, facets: dict) -> list:
    cols = {f: float(facets.get(f, 0.0)) for f in ALL_FACETS}
    res = session.run(
        _AREA_CHUNKS_CYPHER,
        tags=[{"name": n, "weight": s, **cols} for n, s in area["tags"]],
        datasetId=DATASET_ID,
        runId=RUN_ID,
        excludedSections=_EXCLUDED_PARAM,
        neutral=facets == NEUTRAL_FACETS,
        strFacet=STR_FACET,
        strWchunk=STR_WCHUNK,
    )
    return [dict(rec) for rec in res]


def _desc_area(session, vec) -> tuple:
    recs = list(session.run(
        _DESC_KNN_EMB_CYPHER, idx=DESC_INDEX, k=K_LEVELS[-1],
        fetch=KNN_OVERFETCH * K_LEVELS[-1],
        vec=[float(x) for x in vec],
        datasetId=DATASET_ID, excludedSections=_EXCLUDED_PARAM))
    rows = [dict(r) for r in recs
            if r["sim"] is not None and r["desc_emb"] is not None]
    if not rows:
        return [], [], []
    dists = np.array([1.0 - float(r["sim"]) for r in rows])
    vals = _multi_k_support(dists, normalize=False)
    embs = _unit(np.asarray([r["desc_emb"] for r in rows], dtype=np.float64))
    return rows, vals, _level_chain(embs, int(np.argmax(vals)))


def _anchor_cluster(chain: list) -> list:
    members: list = []
    for _, added in chain:
        members.extend(added)
        if len(members) > 1:
            break
    return members


def _chunk_regions(session, chunk_ids: list) -> dict:
    res = session.run(_CHUNK_REGIONS_CYPHER, chunkIds=list(chunk_ids))
    return {rec["chunkId"]: {p: tuple(rec[p]) for p in PARTITIONS} for rec in res}


def _lift_distance(lifts: np.ndarray, _: np.ndarray) -> np.ndarray:
    return np.abs(lifts - lifts.T)


def _concentration(pool: list, region_size: dict, population: dict) -> tuple:
    promoted: dict = {}
    report: dict = {}
    for partition in PARTITIONS:
        members = [regions[partition] for regions in pool if regions[partition]]
        placed = len(members)
        chunks = population[partition]
        counts = Counter(rid for regions in members for rid in regions)
        lifts = {}
        for rid, hits in counts.items():
            size = region_size[(partition, rid)]
            lift = (hits / placed) / (size / chunks)
            if lift > 1.0:
                lifts[rid] = lift
        considered = sorted(lifts, key=lambda rid: (-lifts[rid], rid))
        admitted = []
        if considered:
            column = np.array([lifts[rid] for rid in considered]).reshape(-1, 1)
            admitted = [considered[i] for i in
                        _anchor_cluster(_level_chain(column, 0, _lift_distance))]
        rows = []
        for rid in admitted:
            size = region_size[(partition, rid)]
            promoted[(partition, rid)] = 1.0
            rows.append({"region_id": rid, "hits": counts[rid], "size": size,
                         "lift": round(lifts[rid], 3),
                         "promotion": promoted[(partition, rid)]})
        report[partition] = {
            "placed": placed, "regions": len(counts),
            "considered": len(considered), "above": len(admitted),
            "boundary": round(min(lifts[rid] for rid in admitted), 3)
                        if admitted else None,
            "concentrated": rows}
    return promoted, report


def _promoted_share(regions: dict, promoted: dict) -> float:
    positions = [p for p in PARTITIONS if regions[p]]
    if not positions:
        return 0.0
    reached = sum(1 for p in positions
                  if any((p, rid) in promoted for rid in regions[p]))
    return reached / len(positions)


def _concentration_modifier(session, semantic_bases: list, bases: list,
                            region_size: Optional[dict],
                            population: Optional[dict]) -> tuple:
    if not CONCENTRATION_ON:
        return {}, None
    if region_size is None or population is None:
        raise RuntimeError(
            "the concentration modifier is on and no partition census is loaded "
            "— `prepare_over_corpus` fills Prepared.region_size and "
            "Prepared.population when HERB_STR_CONCENTRATION > 0.")
    pooled = sorted({cid for weight, base in bases if weight > 0.0 for cid in base})
    measured = sorted({cid for weight, base in semantic_bases if weight > 0.0
                       for cid in base})
    regions = _chunk_regions(session, pooled)
    promoted, report = _concentration([regions[cid] for cid in measured],
                                      region_size, population)
    factors = {cid: _mod(1.0 + _promoted_share(regions[cid], promoted),
                         STR_CONCENTRATION)
               for cid in pooled}
    lifted = sorted(f for f in factors.values() if f != 1.0)
    meta = {"str": STR_CONCENTRATION, "measured": len(measured),
            "pool": len(pooled),
            "regions": sum(block["above"] for block in report.values()),
            "lifted": len(lifted),
            "factor": {"min": round(lifted[0], 4),
                       "median": round(lifted[len(lifted) // 2], 4),
                       "max": round(lifted[-1], 4)} if lifted else None,
            "partitions": report}
    spread = (f", factor {lifted[0]:.3f}-{lifted[-1]:.3f}" if lifted else "")
    print(f"artefact_v2: concentration: {meta['regions']} region(s) above the cut "
          f"over {len(measured)} ranked chunk(s), "
          f"{len(lifted)}/{len(pooled)} chunks lifted{spread}", flush=True)
    return factors, meta


def _agreement_modifier(semantic_bases: list) -> tuple:
    if not AGREEMENT_ON:
        return {}, None
    live = [base for weight, base in semantic_bases if weight > 0.0 and base]
    reach: dict = {}
    for base in live:
        for cid in base:
            reach[cid] = reach.get(cid, 0) + 1
    factors = {cid: _mod(paths / len(live), STR_AGREEMENT)
               for cid, paths in reach.items()}
    values = sorted(factors.values())
    counts = Counter(reach.values())
    meta = {"str": STR_AGREEMENT, "live": len(live), "pool": len(factors),
            "paths": {str(n): counts[n] for n in sorted(counts)},
            "factor": {"min": round(values[0], 4),
                       "median": round(values[len(values) // 2], 4),
                       "max": round(values[-1], 4)} if values else None}
    spread = (f", factor {values[0]:.3f}-{values[-1]:.3f}" if values else "")
    print(f"artefact_v2: agreement: {len(live)} live ranked path(s), "
          f"chunks by paths reached {meta['paths']}{spread}", flush=True)
    return factors, meta


def _retrieve(session, plan: dict, k: int, channels: dict, question: str,
              keep_all: bool = False, persons: Optional[list] = None,
              directory: Optional[dict] = None,
              region_size: Optional[dict] = None,
              population: Optional[dict] = None,
              abs_ref_dist: Optional[dict] = None) -> tuple:
    if k <= 0:
        raise ValueError("k must be positive")
    if RAW_QUESTION and not question.strip():
        raise ValueError(
            "HERB_RAW_QUESTION is on and the question text is empty — the raw "
            "probe has nothing to embed")
    if keep_all and CURVE_WALK:
        raise ValueError(
            "keep_all does not combine with HERB_CURVE_WALK — the curve walk's "
            "stop rule sets its own kept depth")

    parts = list(plan["parts"])
    probes = [_readable(p["t"]) for p in parts]
    raw_at = None
    if RAW_QUESTION:
        raw_at = len(parts)
        parts.append({"t": question, "facets": dict(NEUTRAL_FACETS)})
        probes.append(question)
    qmat, calls, tok_in, tok_out, secs = _embed_cached(
        [plan["description"]] + probes, "query")
    usage = ModelUsage(calls=calls, tokens_in=tok_in, tokens_out=tok_out, time_s=secs)
    need_vec = _unit(np.asarray([float(x) for x in qmat[0]], dtype=np.float64))

    gate = dict(plan.get("gate") or {})
    gate["channel_ids"] = channels.get(gate.get("channel") or "", ())
    gate["persons"], gate_unresolved = _gate_persons(gate, persons, directory)
    shaper = plan.get("_support_shaper")
    dist_shaper = plan.get("_distance_shaper")
    guide_stats = ({"matched": 0, "unmatched": 0, "g_sum": 0.0, "g_n": 0}
                   if STR_GUIDE > 0 else None)
    anchors = []
    widening = []
    part_vecs = []
    level_log = []
    for i, part in enumerate(parts):
        vec = _unit(np.asarray([float(x) for x in qmat[i + 1]], dtype=np.float64))
        part_vecs.append(vec)
        levels = _part_levels(session, part, vec, gate, shaper, dist_shaper,
                              guide_stats)
        level_log.append({
            "part": part["t"],
            "pool": sum(len(lv["tags"]) for lv in levels),
            "levels": [{"height": round(lv["height"], 4),
                        "size": len(lv["tags"]),
                        "tags": [n for n, _ in lv["tags"][:6]]}
                       for lv in levels],
        })
        for li, lv in enumerate(levels):
            if li == 0:
                anchors.append((i, lv))
            else:
                widening.append((lv["height"], i, lv))
    if not anchors:
        raise RuntimeError("no tag pool for any prompt part — is tag_emb empty?")
    widening.sort(key=lambda x: x[0])

    pool: set = set()
    semantic: set = set()
    tag_reached: set = set()
    payload: dict = {}
    walk = []

    tag_slots = [dict() for _ in parts]
    desc_sources: list = []
    raw_desc: list = []
    desc_hint: dict = {}
    scope_base: dict = {}
    scope_match: dict = {}
    scope_n = 0

    def _pointer(row):
        return {f: row[f] for f in ("chunkId", "locator", "relpath", "sha256")}

    def open_level(height, pi, level):
        rows = _open_area(session, level, parts[pi]["facets"])
        fresh = 0
        for row in rows:
            cid = row["chunkId"]
            graded = float(row["graded"])
            if cid not in pool:
                fresh += 1
                pool.add(cid)
            semantic.add(cid)
            tag_reached.add(cid)
            if cid not in tag_slots[pi] or graded > tag_slots[pi][cid]:
                tag_slots[pi][cid] = graded
            payload.setdefault(cid, _pointer(row))
        walk.append({"part": parts[pi]["t"], "path": "tag", "height": round(height, 4),
                     "tags": len(level["tags"]), "chunks": len(rows), "new": fresh})

    def _record_desc(slot, rows, vals):
        hinted = bool(_hint_terms(gate)[0])
        fresh = 0
        for row, val in zip(rows, vals):
            cid = row["chunkId"]
            if cid not in pool:
                fresh += 1
                pool.add(cid)
            semantic.add(cid)
            v = float(val)
            if v > slot.get(cid, 0.0):
                slot[cid] = v
            if hinted and _hint_match(row, gate):
                desc_hint[cid] = DESC_HINT_M
            payload.setdefault(cid, _pointer(row))
        return fresh

    def open_desc(vec, label, sink):
        if DESC_CUT:
            rows, vals, chain = _desc_area(session, vec)
            if not rows:
                return
            admitted = _anchor_cluster(chain)
        else:
            recs = list(session.run(
                _DESC_KNN_CYPHER, idx=DESC_INDEX, k=K_LEVELS[-1],
                fetch=KNN_OVERFETCH * K_LEVELS[-1],
                vec=[float(x) for x in vec],
                datasetId=DATASET_ID, excludedSections=_EXCLUDED_PARAM))
            rows = [dict(r) for r in recs if r["sim"] is not None]
            if not rows:
                return
            dists = np.array([1.0 - float(r["sim"]) for r in rows])
            vals = _multi_k_support(dists, normalize=False)
            admitted = list(range(len(rows)))
        slot: dict = {}
        sink.append(slot)
        fresh = _record_desc(slot, [rows[j] for j in admitted],
                             [vals[j] for j in admitted])
        walk.append({"part": label, "path": "desc", "chunks": len(admitted),
                     "new": fresh})

    def open_desc_area(vec, label, sink):
        rows, vals, chain = _desc_area(session, vec)
        if not rows:
            return []
        slot: dict = {}
        sink.append(slot)

        def open_members(height, added):
            fresh = _record_desc(slot, [rows[j] for j in added],
                                 [vals[j] for j in added])
            walk.append({"part": label, "path": "desc", "height": round(height, 4),
                         "chunks": len(added), "new": fresh})

        open_members(*chain[0])
        return [(h, (lambda h=h, added=added: open_members(h, added)))
                for h, added in chain[1:]]

    def open_stated_scope():
        terms, params = _hint_terms(gate)
        if not terms:
            return
        matched_expr = " + ".join(f"(CASE WHEN {t} THEN 1 ELSE 0 END)" for t in terms)
        cypher = f"""
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
WHERE coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND NOT (coalesce(c.section, "") IN $excludedSections)
  AND ({" OR ".join(terms)})
WITH c, f, ({matched_expr}) AS matched,
     vector.similarity.cosine(c.desc_emb, $descVec) AS sim
RETURN c.chunk_id AS chunkId, c.locator_json AS locator,
       f.rel_path AS relpath, f.sha256 AS sha256, matched, sim
ORDER BY sim DESC, chunkId
"""
        recs = list(session.run(cypher, descVec=[float(x) for x in need_vec],
                                datasetId=DATASET_ID,
                                excludedSections=_EXCLUDED_PARAM, **params))
        rows = [dict(r) for r in recs if r["sim"] is not None]
        if not rows:
            return
        nonlocal scope_n
        scope_n = len(rows)
        dists = np.array([1.0 - float(r["sim"]) for r in rows])
        vals = _multi_k_support(dists, extend=True, normalize=False)
        fresh = 0
        for row, val in zip(rows, vals):
            cid = row["chunkId"]
            if cid not in pool:
                fresh += 1
                pool.add(cid)
            sup = float(val)
            if sup > scope_base.get(cid, 0.0):
                scope_base[cid] = sup
                scope_match[cid] = float(row["matched"]) / len(terms)
            payload.setdefault(cid, _pointer(row))
        walk.append({"part": "stated-scope", "path": "scope",
                     "chunks": len(rows), "new": fresh})

    for pi, lv in anchors:
        open_level(0.0, pi, lv)

    stopped = False
    opened = 0
    if CURVE_WALK:
        seq = iter(range(1 << 30))
        frontier = [(h, next(seq), (lambda h=h, pi=pi, lv=lv: open_level(h, pi, lv)))
                    for h, pi, lv in widening]
        for pi in range(len(parts)):
            frontier += [(h, next(seq), fn) for h, fn in
                         open_desc_area(part_vecs[pi], parts[pi]["t"],
                                        raw_desc if pi == raw_at else desc_sources)]
        if plan["description"] not in (
                {p["t"] for p in parts} | {_readable(p["t"]) for p in parts}):
            frontier += [(h, next(seq), fn) for h, fn in
                         open_desc_area(need_vec, "description", desc_sources)]
        open_stated_scope()
        frontier.sort(key=lambda e: e[:2])
        gaps, last_h = [], 0.0
        for height, _, open_fn in frontier:
            gap = height - last_h
            if _gap_break(gaps, gap):
                stopped = True
                break
            open_fn()
            gaps.append(gap)
            last_h = height
        opened = len(gaps)
    else:
        for pi in range(len(parts)):
            open_desc(part_vecs[pi], parts[pi]["t"],
                      raw_desc if pi == raw_at else desc_sources)
        open_stated_scope()
        for height, pi, lv in widening:
            if len(tag_reached) >= k:
                break
            open_level(height, pi, lv)
    if not pool:
        raise RuntimeError("opened areas produced no evidence chunks")
    if CURVE_WALK and not semantic:
        raise RuntimeError(
            "semantic areas vouch for no chunks — the tag and description paths "
            "found nothing, and stated scope filled the pool alone")

    tag_base = _agg(tag_slots)
    desc_base = _agg(desc_sources)
    raw_base = _agg(raw_desc)
    raw_wins = 0
    for cid, sup in raw_base.items():
        if sup > desc_base.get(cid, 0.0):
            desc_base[cid] = sup
            raw_wins += 1
    tag_norm, desc_norm, scope_norm = _normalize(
        tag_base, desc_base, scope_base, _n_levels(scope_n), abs_ref_dist)
    semantic_bases = [(W_TAG, tag_norm), (W_DESC, desc_norm)]
    bases = semantic_bases + [(W_SCOPE, scope_norm)]
    concentration, conc_meta = _concentration_modifier(
        session, semantic_bases, bases, region_size, population)
    agreement, agree_meta = _agreement_modifier(semantic_bases)
    tag_score, desc_score, scope_score = {}, {}, {}
    for cid, nb in tag_norm.items():
        tag_score[cid] = (nb * concentration.get(cid, 1.0)
                          * agreement.get(cid, 1.0))
    for cid, nb in desc_norm.items():
        desc_score[cid] = (nb * _mod(desc_hint.get(cid, 1.0), STR_DESC_HINT)
                           * concentration.get(cid, 1.0) * agreement.get(cid, 1.0))
    for cid, nb in scope_norm.items():
        scope_score[cid] = (nb * _mod(scope_match.get(cid, 1.0), STR_SCOPE_MATCH)
                            * concentration.get(cid, 1.0) * agreement.get(cid, 1.0))

    totals: dict = {}
    for cid, s in tag_score.items():
        totals[cid] = totals.get(cid, 0.0) + W_TAG * s
    for cid, s in desc_score.items():
        totals[cid] = totals.get(cid, 0.0) + W_DESC * s
    for cid, s in scope_score.items():
        totals[cid] = totals.get(cid, 0.0) + W_SCOPE * s

    ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    kept_k = min(len(semantic), k) if CURVE_WALK else k
    if not keep_all:
        ranked = ranked[:kept_k]
    selected = [{**payload[cid], "score": round(sc, 4)} for cid, sc in ranked]

    meta = {
        "plan": {key: val for key, val in plan.items() if not key.startswith("_")},
        "knn_levels": list(K_LEVELS),
        "parts": level_log,
        "walk": walk,
        "retrieved": len(selected),
    }
    if NORM == "absolute":
        meta["abs_ref_dist"] = dict(abs_ref_dist)
    if CURVE_WALK:
        meta["curve_walk"] = {"pool": len(totals), "semantic": len(semantic),
                              "kept": kept_k, "stopped": stopped,
                              "opened": opened}
    if RAW_QUESTION:
        meta["raw_question"] = {"part": raw_at, "desc_chunks": len(raw_base),
                                "desc_wins": raw_wins}
    if STR_GUIDE > 0:
        meta["guide"] = {
            "str": STR_GUIDE, "tau": GUIDE_TAU, "C": GUIDE_C, "m": GUIDE_M,
            "matched": guide_stats["matched"],
            "unmatched": guide_stats["unmatched"],
            "mean_g": round(guide_stats["g_sum"] / guide_stats["g_n"], 4)
                      if guide_stats["g_n"] else 0.0}
    if conc_meta is not None:
        meta["concentration"] = conc_meta
    if agree_meta is not None:
        meta["agreement"] = agree_meta
    if persons or gate_unresolved:
        listed = [{"name": m["name"], "rule": m["rule"], "ids": list(m["ids"])}
                  for m in (persons or [])]
        if gate_unresolved:
            listed.append(gate_unresolved)
        meta["scope"] = {"persons": listed}
    if DOOR_TRACE:
        meta["door_trace"] = [
            {**payload[cid],
             "tag": round(W_TAG * tag_score.get(cid, 0.0), 6),
             "desc": round(W_DESC * desc_score.get(cid, 0.0), 6),
             "scope": round(W_SCOPE * scope_score.get(cid, 0.0), 6),
             "total": round(totals[cid], 6)}
            for cid in sorted(totals, key=lambda c: (-totals[c], c))]
    return selected, usage, meta


def _load_verified_doc(relpath: str, sha256: str, cache: dict):
    key = (relpath, sha256)
    doc = cache.get(key)
    if doc is not None:
        return doc
    path = (RAW_ROOT / relpath).resolve()
    if not path.is_relative_to(RAW_ROOT):
        raise RuntimeError(
            f"locator relpath {relpath!r} resolves outside the raw root — refusing to read it")
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != sha256:
        raise RuntimeError(
            f"HASH MISMATCH for {relpath}: graph built against {sha256[:12]}…, "
            f"on-disk is {actual[:12]}…. Refusing to serve drifted content.")
    doc = json.loads(data.decode("utf-8"))
    cache[key] = doc
    return doc


def _nth_entry(root, i: int):
    if isinstance(root, list):
        return root[i]
    k, v = list(root.items())[i]
    return {k: v}


def _resolve_chunk(row: dict, cache: dict) -> tuple:
    loc = json.loads(row["locator"])
    doc = _load_verified_doc(row["relpath"], row["sha256"], cache)

    if "metadata" in loc:
        if "indices" in loc:
            recs = [_nth_entry(doc, i) for i in loc["indices"]]
        else:
            rec = _nth_entry(doc, loc["index"])
            if loc.get("subsection"):
                rec = rec[loc["subsection"]]
            recs = [rec]
        return "\n".join(json.dumps(r, ensure_ascii=False) for r in recs), []

    arr = doc[loc["section"]]
    if "char_range" in loc:
        rec = arr[loc["index"]]
        start, end = loc["char_range"]
        text = rec[loc["field"]][start:end]
        aid = rec.get("id")
        return text, [str(aid)] if aid is not None else []

    recs = [arr[i] for i in (loc["indices"] if "indices" in loc else [loc["index"]])]
    ids, seen = [], set()
    for rec in recs:
        aid = rec.get("id")
        if aid is not None and aid not in seen:
            seen.add(aid)
            ids.append(str(aid))
    return "\n".join(json.dumps(r, ensure_ascii=False) for r in recs), ids


def _budget_contexts(rows: list, budget: int, doc_cache: dict) -> tuple:
    id_lists: list[list[str]] = []

    def stream():
        for row in rows:
            chunk_text, ids = _resolve_chunk(row, doc_cache)
            id_lists.append(ids)
            yield row["chunkId"], chunk_text

    cut = cut_at_budget(stream(), budget)
    context_ids: list[str] = []
    seen: set[str] = set()
    for ids in id_lists[:cut.kept]:
        for aid in ids:
            if aid not in seen:
                seen.add(aid)
                context_ids.append(aid)
    block = {"budget": budget, "chars": cut.chars, "kept": cut.kept,
             "boundary": cut.boundary, "exhausted": cut.exhausted}
    return cut.contexts, id_lists, context_ids, block


def _sufficient_cut(text: str, contexts: list) -> tuple:
    kept = len(contexts)
    log = []
    calls = tok_in = tok_out = 0
    time_s = 0.0
    for lv in [l for l in K_LEVELS if l < len(contexts)]:
        digest = "\n\n".join(f"[{i + 1}] {contexts[i][:240]}" for i in range(lv))
        try:
            verdict, ti, to, el = _chat_json(
                INTERPRET_MODEL, _REVIEW_SYSTEM,
                f"Question: {text}\n\nEvidence so far (top {lv}):\n{digest}", 128)
        except abort.Aborted:
            raise
        except Exception as e:
            calls += getattr(e, "calls", 0)
            tok_in += getattr(e, "tokens_in", 0)
            tok_out += getattr(e, "tokens_out", 0)
            time_s += getattr(e, "time_s", 0.0)
            log.append({"at": lv, "decision": "fallback",
                        "error": f"{type(e).__name__}: {e}"})
            break
        calls += 1
        tok_in += ti
        tok_out += to
        time_s += el
        sufficient = bool(verdict.get("sufficient"))
        log.append({"at": lv, "sufficient": sufficient})
        if sufficient:
            kept = lv
            break
    return kept, log, calls, tok_in, tok_out, time_s


def answer_one_question(question, prepared: Prepared, generate: Optional[Generator],
                        k: int = 50, char_budget: Optional[int] = None) -> ArmOutput:
    _, text = _qid_text(question)

    nim.reset_timing()
    t0 = time.perf_counter()
    plan, interp_calls, interp_in, interp_out, interp_time = _interpret_cached(text, INTERPRET_MODEL)
    persons = resolve_persons(text, prepared.directory)
    with prepared.driver.session(database=DATABASE) as session:
        rows, ground_usage, meta = _retrieve(session, plan, k, prepared.channels,
                                             text,
                                             keep_all=char_budget is not None,
                                             persons=persons,
                                             directory=prepared.directory,
                                             region_size=prepared.region_size,
                                             population=prepared.population,
                                             abs_ref_dist=prepared.abs_ref_dist)
    meta["interpreter"] = {"model": INTERPRET_MODEL, "backend": "claude-cli"}
    retrieve_wall = time.perf_counter() - t0

    doc_cache: dict = {}
    rev_calls = rev_in = rev_out = 0
    rev_time = 0.0
    if char_budget is not None:
        contexts, chunk_id_lists, context_ids, meta["char_budget"] = _budget_contexts(
            rows, char_budget, doc_cache)
    else:
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
        if NO_REVIEW:
            kept, review_log = len(contexts), []
        else:
            kept, review_log, rev_calls, rev_in, rev_out, rev_time = _sufficient_cut(text, contexts)
        contexts = contexts[:kept]
        chunk_id_lists = chunk_id_lists[:kept]
        seen = set()
        context_ids = []
        for ids in chunk_id_lists:
            for aid in ids:
                if aid not in seen:
                    seen.add(aid)
                    context_ids.append(aid)
        meta["review"] = {"kept": kept, "rounds": review_log}
    meta["returned"] = len(contexts)
    meta["chunk_ids"] = chunk_id_lists

    search_time_s = max(0.0, retrieve_wall - interp_time - ground_usage.time_s)
    retrieval_usage = ModelUsage(
        calls=interp_calls + ground_usage.calls + rev_calls,
        tokens_in=interp_in + ground_usage.tokens_in + rev_in,
        tokens_out=interp_out + ground_usage.tokens_out + rev_out,
        time_s=interp_time + ground_usage.time_s + rev_time,
        **nim.take_timing())

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

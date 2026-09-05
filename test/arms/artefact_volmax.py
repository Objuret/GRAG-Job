from __future__ import annotations

if __name__ == "__main__":
    print("artefact_volmax self-check — loading numpy, scipy, the embedder and neo4j …",
          flush=True)

import hashlib
import inspect
import json
import os
import re
import tempfile
import time
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
W_PERSON = _env_float("HERB_W_PERSON", 1.0)
if W_PERSON < 0.0:
    raise ValueError(
        f"HERB_W_PERSON must be >= 0.0, got {W_PERSON!r} — a path weights a "
        f"chunk up or leaves it alone; a negative weight would push a chunk "
        f"down for carrying evidence")
PERSON_ON = W_PERSON > 0.0

STR_FACET = _env_float("HERB_STR_FACET", 0.0)
STR_WCHUNK = _env_float("HERB_STR_WCHUNK", 1.0)
STR_RELEVANCE = _env_float("HERB_STR_RELEVANCE", 1.0)
STR_DESC_HINT = _env_float("HERB_STR_DESC_HINT", 1.0)
STR_SCOPE_MATCH = _env_float("HERB_STR_SCOPE_MATCH", 1.0)
STR_PERSON_MATCH = _env_float("HERB_STR_PERSON_MATCH", 1.0)

DESC_HINT_M = _env_float("HERB_DESC_HINT_M", 2.0)

DESC_CUT = _env_bool("HERB_DESC_CUT", True)

W_ROLE_SLACK = _env_float("HERB_W_ROLE_SLACK", 1.0)
W_ROLE_MEETING_TRANSCRIPTS = _env_float("HERB_W_ROLE_MEETING_TRANSCRIPTS", 1.0)
W_ROLE_DOCUMENTS = _env_float("HERB_W_ROLE_DOCUMENTS", 1.0)
PERSON_ROLE_W = {
    "slack": W_ROLE_SLACK,
    "meeting_transcripts": W_ROLE_MEETING_TRANSCRIPTS,
    "documents": W_ROLE_DOCUMENTS,
}
_NEGATIVE_ROLES = sorted(f"HERB_W_ROLE_{role.upper()}"
                         for role, w in PERSON_ROLE_W.items() if w < 0.0)
if _NEGATIVE_ROLES:
    raise ValueError(
        f"{', '.join(_NEGATIVE_ROLES)} must be >= 0.0 — a role weight grades a "
        f"link up or down to nothing; a negative weight would score a chunk for "
        f"carrying the wrong kind of evidence")

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
    print(f"artefact_volmax: cluster guide on (HERB_STR_GUIDE={STR_GUIDE}, "
          f"tau={GUIDE_TAU}, C={GUIDE_C}, m={GUIDE_M})", flush=True)

if PERSON_ON:
    print(f"artefact_volmax: person support path on (HERB_W_PERSON={W_PERSON}, "
          f"ambiguous={PERSON_AMBIGUOUS}, near={'on' if PERSON_NEAR else 'off'}, "
          f"roles={PERSON_ROLE_W})", flush=True)

AGG = os.environ.get("HERB_AGG", "sum")
NORM = os.environ.get("HERB_NORM", "relative")
NORM_SCOPE = os.environ.get("HERB_NORM_SCOPE", "per_path")
if AGG not in ("sum", "max"):
    raise ValueError(f"HERB_AGG must be 'sum' or 'max', got {AGG!r}")
if NORM not in ("relative", "absolute", "none"):
    raise ValueError(f"HERB_NORM must be 'relative', 'absolute' or 'none', got {NORM!r}")
if NORM_SCOPE not in ("per_path", "global"):
    raise ValueError(f"HERB_NORM_SCOPE must be 'per_path' or 'global', got {NORM_SCOPE!r}")

_ABS_REF_DIST = 0.5
_ABS_UNIT = 1.0 / _ABS_REF_DIST ** 2
_ABS_REF = len(K_LEVELS) * _ABS_UNIT

RETRIEVAL_FLAGS = {
    "HERB_CURVE_WALK": CURVE_WALK, "HERB_DOOR_TRACE": DOOR_TRACE,
    "HERB_DESC_CUT": DESC_CUT, "HERB_FRESH_INTERP": FRESH_INTERP,
    "HERB_NO_REVIEW": NO_REVIEW,
    "HERB_AGG": AGG, "HERB_NORM": NORM, "HERB_NORM_SCOPE": NORM_SCOPE,
    "HERB_W_TAG": W_TAG, "HERB_W_DESC": W_DESC, "HERB_W_SCOPE": W_SCOPE,
    "HERB_STR_FACET": STR_FACET, "HERB_STR_WCHUNK": STR_WCHUNK,
    "HERB_STR_RELEVANCE": STR_RELEVANCE, "HERB_STR_DESC_HINT": STR_DESC_HINT,
    "HERB_STR_SCOPE_MATCH": STR_SCOPE_MATCH, "HERB_DESC_HINT_M": DESC_HINT_M,
    "HERB_STR_GUIDE": STR_GUIDE, "HERB_GUIDE_TAU": GUIDE_TAU,
    "HERB_GUIDE_C": GUIDE_C, "HERB_GUIDE_M": GUIDE_M,
    "HERB_GUIDE_LAMBDA": GUIDE_LAMBDA, "HERB_GUIDE_SEED": GUIDE_SEED,
    "HERB_W_PERSON": W_PERSON, "HERB_STR_PERSON_MATCH": STR_PERSON_MATCH,
    "HERB_PERSON_AMBIGUOUS": PERSON_AMBIGUOUS, "HERB_PERSON_NEAR": PERSON_NEAR,
    "HERB_W_ROLE_SLACK": W_ROLE_SLACK,
    "HERB_W_ROLE_MEETING_TRANSCRIPTS": W_ROLE_MEETING_TRANSCRIPTS,
    "HERB_W_ROLE_DOCUMENTS": W_ROLE_DOCUMENTS,
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

REQUIRED_LABELS = ("File", "Chunk", "Tag", "Product", "Channel")
REQUIRED_TYPES = ("HAS_CHUNK", "HAS_TAG", "product", "channel")
PERSON_LABELS = ("Employee", "Kind")
PERSON_TYPES = ("slack", "meeting_transcripts", "documents", "kind")

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
WITH c, f, qt.weight AS support, coalesce(facetTerm, 0.0) AS facetTerm,
     coalesce(r.w_chunk, 0.0) AS w_chunk,
     coalesce(c.relevance_to_file, 1.0) AS relevance
ORDER BY support DESC, w_chunk DESC
WITH c, f, collect({support: support, facetTerm: facetTerm,
                    w_chunk: w_chunk, relevance: relevance})[0] AS best
RETURN c.chunk_id AS chunkId, c.locator_json AS locator,
       f.rel_path AS relpath,
       best.support AS support, best.facetTerm AS facetTerm,
       best.w_chunk AS w_chunk, best.relevance AS relevance
"""

_DESC_KNN_TEMPLATE = """
CALL db.index.vector.queryNodes($idx, $fetch, $vec) YIELD node AS c, score AS sim
MATCH (f:File)-[:HAS_CHUNK]->(c)
WHERE coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND NOT (coalesce(c.section, "") IN $excludedSections)
RETURN c.chunk_id AS chunkId, c.locator_json AS locator,
       f.rel_path AS relpath, sim,{emb}
       [(c)-[:product]->(p:Product) | p.name][0] AS product,
       c.section AS section,
       [(c)-[:channel]->(ch:Channel) | ch.id] AS channels,
       c.employee_id AS employee_id, c.years AS years
ORDER BY sim DESC, chunkId
LIMIT $k
"""
_DESC_KNN_CYPHER = _DESC_KNN_TEMPLATE.format(emb="")
_DESC_KNN_EMB_CYPHER = _DESC_KNN_TEMPLATE.format(
    emb="\n       c.desc_emb AS desc_emb,")

_PERSON_CHUNKS_CYPHER = """
MATCH (e:Employee)-[:slack]->(:Channel)<-[:channel]-(c:Chunk)<-[:HAS_CHUNK]-(f:File)
WHERE e.eid IN $pids
  AND coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND NOT (coalesce(c.section, "") IN $excludedSections)
RETURN c.chunk_id AS chunkId, c.locator_json AS locator, f.rel_path AS relpath,
       "slack" AS role, vector.similarity.cosine(c.desc_emb, $descVec) AS sim
UNION
MATCH (e:Employee)-[r:meeting_transcripts|documents]->(:Product)<-[:product]-(c:Chunk)<-[:HAS_CHUNK]-(f:File)
MATCH (c)-[:kind]->(k:Kind)
WHERE e.eid IN $pids
  AND k.name = type(r)
  AND coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND NOT (coalesce(c.section, "") IN $excludedSections)
RETURN c.chunk_id AS chunkId, c.locator_json AS locator, f.rel_path AS relpath,
       type(r) AS role, vector.similarity.cosine(c.desc_emb, $descVec) AS sim
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
    if gate.get("employee_id"):
        terms.append("c.employee_id = $g_employee_id")
        params["g_employee_id"] = gate["employee_id"]
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
    for f in ("product", "section", "employee_id"):
        if gate.get(f) and row.get(f) == gate[f]:
            return True
    if gate.get("channel") and set(gate.get("channel_ids") or ()) & set(row.get("channels") or []):
        return True
    if gate.get("years") and set(gate["years"]) & set(row.get("years") or []):
        return True
    return False


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
                f"person directory missing at {path} — the person support path "
                f"(HERB_W_PERSON={W_PERSON}) resolves query names against the "
                f"corpus view's own directories.")
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
    return {
        "ids": {k: tuple(sorted(v)) for k, v in ids.items()},
        "surface": surface,
        "token_sets": {k: tuple(sorted(v)) for k, v in token_sets.items()},
        "initials": {k: tuple(sorted(v)) for k, v in initials.items()},
        "lengths": tuple(sorted({len(k) for k in ids}, reverse=True)),
        "counts": {"employees": len(employees), "customers": len(customers),
                   "names": len(ids),
                   "ids": len({pid for _, pid in entries if pid})},
    }


def _is_initial(text: str, token: tuple) -> bool:
    word, start, end = token
    if len(word) != 1 or not text[start].isupper():
        return False
    return text[end:end + 1] == "." or word not in _INITIAL_STOP


def resolve_persons(text: str, directory: dict) -> list:
    if directory is None:
        raise RuntimeError(
            "the person support path is on and no person directory is loaded — "
            "`prepare_over_corpus` fills Prepared.directory when HERB_W_PERSON "
            "> 0, and resolution needs it.")
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


def _role_weight(roles: list) -> float:
    best = 0.0
    for role in roles:
        if role not in PERSON_ROLE_W:
            raise RuntimeError(
                f"person edge role {role!r} in {DATABASE!r} has no weight — "
                f"the roles this arm grades are {sorted(PERSON_ROLE_W)}")
        best = max(best, PERSON_ROLE_W[role])
    return best


def _person_rows(session, pids: list, need_vec) -> list:
    folded: dict = {}
    for rec in session.run(_PERSON_CHUNKS_CYPHER, pids=list(pids),
                           descVec=[float(x) for x in need_vec],
                           datasetId=DATASET_ID, excludedSections=_EXCLUDED_PARAM):
        if rec["sim"] is None:
            continue
        row = folded.get(rec["chunkId"])
        if row is None:
            row = {"chunkId": rec["chunkId"], "locator": rec["locator"],
                   "relpath": rec["relpath"], "sim": float(rec["sim"]), "roles": []}
            folded[rec["chunkId"]] = row
        if rec["role"] not in row["roles"]:
            row["roles"].append(rec["role"])
    return sorted(folded.values(), key=lambda r: (-r["sim"], r["chunkId"]))


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


@dataclass
class Prepared:
    driver: object
    corpus_root: Path
    channels: dict
    build_stats: Optional[BuildStats] = None
    directory: Optional[dict] = None


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
    print(f"artefact_volmax: opening {DATABASE} …", flush=True)
    directory = _load_person_directory(corpus_root) if PERSON_ON else None
    drv = _driver()
    try:
        with drv.session(database=DATABASE) as s:
            labels = set(s.run("CALL db.labels() YIELD label RETURN collect(label) AS v")
                         .single()["v"])
            types = set(s.run("CALL db.relationshipTypes() YIELD relationshipType AS t "
                              "RETURN collect(t) AS v").single()["v"])
            indexes = set(s.run("SHOW INDEXES YIELD name RETURN collect(name) AS v")
                          .single()["v"])
            want_labels = set(REQUIRED_LABELS) | (set(PERSON_LABELS) if PERSON_ON else set())
            want_types = set(REQUIRED_TYPES) | (set(PERSON_TYPES) if PERSON_ON else set())
            missing = (sorted(want_labels - labels) + sorted(want_types - types)
                       + sorted({GROUND_INDEX, DESC_INDEX} - indexes))
            if missing:
                raise RuntimeError(
                    f"{DATABASE!r} is not the graph this arm walks — missing {missing}. "
                    f"Every one of them is traversed by a query in this arm, and a "
                    f"pattern over a type the graph does not carry answers with zero "
                    f"rows instead of failing.")
            no_desc = s.run(
                "MATCH (c:Chunk) WHERE coalesce(c.empty, false) = false "
                "AND c.desc_emb IS NULL RETURN count(c) AS n").single()["n"]
            if no_desc:
                raise RuntimeError(
                    f"{no_desc} non-empty chunk(s) in {DATABASE!r} carry no desc_emb — "
                    f"the description path, the stated-scope path and the person path "
                    f"would all be blind to them.")
            multi = s.run(
                "MATCH (c:Chunk) WITH c, count { (:File)-[:HAS_CHUNK]->(c) } AS n "
                "WHERE n <> 1 RETURN count(*) AS bad").single()["bad"]
            if multi:
                raise RuntimeError(
                    f"{multi} chunk(s) in {DATABASE!r} without exactly one File — "
                    f"pointer resolution would be ambiguous")
            chunks = s.run("MATCH (c:Chunk) RETURN count(c) AS n").single()["n"]
            channels = _channel_names(s, corpus_root.parent)
    except Exception:
        drv.close()
        raise
    print(f"artefact_volmax: {chunks} chunks | {len(channels)} channel names", flush=True)
    if PERSON_ON:
        counts = directory["counts"]
        print(f"artefact_volmax: person directory {counts['employees']} employees + "
              f"{counts['customers']} customers -> {counts['names']} distinct names "
              f"over {counts['ids']} ids", flush=True)
    return Prepared(
        driver=drv,
        corpus_root=corpus_root.parent,
        channels=channels,
        build_stats=BuildStats(
            build_time_s=time.perf_counter() - t0,
            model=ModelUsage(),
            models=[EMBED_MODEL],
        ),
        directory=directory,
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
    return re.sub(r"^_+|_+$", "", re.sub(r"[^a-z0-9]+", "_", raw.lower()))


def _readable(name: str) -> str:
    return name.replace("_", " ").strip()


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
        if len(t) > 1 and t not in FILLER and t not in seen:
            seen.add(t)
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
    score_map = {_clean_tag(row["t"]): (row.get("facets") or {})
                 for row in (p2.get("scores") or [])}
    default = {f: 0.2 for f in ALL_FACETS}
    unscored = [t for t in raw_parts if t not in score_map]
    parts = []
    for t in raw_parts:
        facets = {f: min(1.0, max(0.0, float(score_map.get(t, default).get(f, 0.2))))
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
               person_base: dict, scope_levels: int, person_levels: int) -> tuple:
    if NORM == "none":
        return tag_base, desc_base, scope_base, person_base
    if NORM == "absolute":
        scope_ref = scope_levels * _ABS_UNIT
        person_ref = person_levels * _ABS_UNIT
        return ({cid: _absolute(v, _ABS_REF) for cid, v in tag_base.items()},
                {cid: _absolute(v, _ABS_REF) for cid, v in desc_base.items()},
                {cid: _absolute(v, scope_ref) for cid, v in scope_base.items()},
                {cid: _absolute(v, person_ref) for cid, v in person_base.items()})
    if NORM_SCOPE == "global":
        allvals = [*tag_base.values(), *desc_base.values(), *scope_base.values(),
                   *person_base.values()]
        lo = min(allvals) if allvals else 0.0
        hi = max(allvals) if allvals else 0.0
        return (_norm_pool(tag_base, lo, hi), _norm_pool(desc_base, lo, hi),
                _norm_pool(scope_base, lo, hi), _norm_pool(person_base, lo, hi))
    return (_minmax(tag_base), _minmax(desc_base), _minmax(scope_base),
            _minmax(person_base))


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


def _retrieve(session, plan: dict, k: int, channels: dict, keep_all: bool = False,
              persons: Optional[list] = None) -> tuple:
    if k <= 0:
        raise ValueError("k must be positive")
    if keep_all and CURVE_WALK:
        raise ValueError(
            "keep_all does not combine with HERB_CURVE_WALK — the curve walk's "
            "stop rule sets its own kept depth")

    parts = plan["parts"]
    qmat, calls, tok_in, tok_out, secs = _embed_cached(
        [plan["description"]] + [_readable(p["t"]) for p in parts], "query")
    usage = ModelUsage(calls=calls, tokens_in=tok_in, tokens_out=tok_out, time_s=secs)
    need_vec = _unit(np.asarray([float(x) for x in qmat[0]], dtype=np.float64))

    gate = dict(plan.get("gate") or {})
    gate["channel_ids"] = channels.get(gate.get("channel") or "", ())
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
    tag_supp: dict = {}
    tag_mods: dict = {}
    desc_sources: list = []
    desc_hint: dict = {}
    scope_base: dict = {}
    scope_match: dict = {}
    scope_n = 0
    person_slots: list = []
    person_role: dict = {}
    person_hits: dict = {}
    person_log: list = []

    def _pointer(row):
        return {f: row[f] for f in ("chunkId", "locator", "relpath")}

    def open_level(height, pi, level):
        rows = _open_area(session, level, parts[pi]["facets"])
        fresh = 0
        for row in rows:
            cid = row["chunkId"]
            sup = float(row["support"])
            if cid not in pool:
                fresh += 1
                pool.add(cid)
            semantic.add(cid)
            tag_reached.add(cid)
            if cid not in tag_slots[pi] or sup > tag_slots[pi][cid]:
                tag_slots[pi][cid] = sup
            if cid not in tag_supp or sup > tag_supp[cid]:
                tag_supp[cid] = sup
                tag_mods[cid] = (float(row["facetTerm"]), float(row["w_chunk"]),
                                 float(row["relevance"]))
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

    def open_desc(vec, label):
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
        desc_sources.append(slot)
        fresh = _record_desc(slot, [rows[j] for j in admitted],
                             [vals[j] for j in admitted])
        walk.append({"part": label, "path": "desc", "chunks": len(admitted),
                     "new": fresh})

    def open_desc_area(vec, label):
        rows, vals, chain = _desc_area(session, vec)
        if not rows:
            return []
        slot: dict = {}
        desc_sources.append(slot)

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
       f.rel_path AS relpath, matched, sim
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

    def open_person_areas():
        for mention in persons or []:
            entry = {"name": mention["name"], "rule": mention["rule"],
                     "ids": list(mention["ids"]), "chunks": 0, "new": 0}
            person_log.append(entry)
            if not mention["ids"]:
                continue
            rows = _person_rows(session, mention["ids"], need_vec)
            if not rows:
                continue
            dists = np.array([1.0 - float(r["sim"]) for r in rows])
            vals = _multi_k_support(dists, extend=True, normalize=False)
            slot: dict = {}
            person_slots.append(slot)
            fresh = 0
            for row, val in zip(rows, vals):
                cid = row["chunkId"]
                if cid not in pool:
                    fresh += 1
                    pool.add(cid)
                sup = float(val)
                if cid not in slot or sup > slot[cid]:
                    slot[cid] = sup
                weight = _role_weight(row["roles"])
                if cid not in person_role or weight > person_role[cid]:
                    person_role[cid] = weight
                person_hits[cid] = person_hits.get(cid, 0) + 1
                payload.setdefault(cid, _pointer(row))
            entry["chunks"] = len(rows)
            entry["new"] = fresh
            walk.append({"part": mention["name"], "path": "person",
                         "ids": len(mention["ids"]), "chunks": len(rows),
                         "new": fresh})

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
                         open_desc_area(part_vecs[pi], parts[pi]["t"])]
        if plan["description"] not in (
                {p["t"] for p in parts} | {_readable(p["t"]) for p in parts}):
            frontier += [(h, next(seq), fn) for h, fn in
                         open_desc_area(need_vec, "description")]
        open_stated_scope()
        if PERSON_ON:
            open_person_areas()
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
            open_desc(part_vecs[pi], parts[pi]["t"])
        open_stated_scope()
        if PERSON_ON:
            open_person_areas()
        for height, pi, lv in widening:
            if len(tag_reached) >= k:
                break
            open_level(height, pi, lv)
    if not pool:
        raise RuntimeError("opened areas produced no evidence chunks")
    if CURVE_WALK and not semantic:
        raise RuntimeError(
            "semantic areas vouch for no chunks — the tag and description paths "
            "found nothing, and stated scope or a named person filled the pool alone")

    tag_base = _agg(tag_slots)
    desc_base = _agg(desc_sources)
    person_base = _agg(person_slots)
    tag_norm, desc_norm, scope_norm, person_norm = _normalize(
        tag_base, desc_base, scope_base, person_base,
        _n_levels(scope_n), _n_levels(len(person_base)))
    named = sum(1 for m in (persons or []) if m["ids"]) if PERSON_ON else 0
    tag_score, desc_score, scope_score, person_score = {}, {}, {}, {}
    for cid, nb in tag_norm.items():
        ft, wc, rel = tag_mods[cid]
        tag_score[cid] = nb * _mod(ft, STR_FACET) * _mod(wc, STR_WCHUNK) * _mod(rel, STR_RELEVANCE)
    for cid, nb in desc_norm.items():
        desc_score[cid] = nb * _mod(desc_hint.get(cid, 1.0), STR_DESC_HINT)
    for cid, nb in scope_norm.items():
        scope_score[cid] = nb * _mod(scope_match.get(cid, 1.0), STR_SCOPE_MATCH)
    for cid, nb in person_norm.items():
        person_score[cid] = (nb * person_role[cid]
                             * _mod(person_hits[cid] / named, STR_PERSON_MATCH))

    totals: dict = {}
    for cid, s in tag_score.items():
        totals[cid] = totals.get(cid, 0.0) + W_TAG * s
    for cid, s in desc_score.items():
        totals[cid] = totals.get(cid, 0.0) + W_DESC * s
    for cid, s in scope_score.items():
        totals[cid] = totals.get(cid, 0.0) + W_SCOPE * s
    for cid, s in person_score.items():
        totals[cid] = totals.get(cid, 0.0) + W_PERSON * s

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
    if CURVE_WALK:
        meta["curve_walk"] = {"pool": len(totals), "semantic": len(semantic),
                              "kept": kept_k, "stopped": stopped,
                              "opened": opened}
    if STR_GUIDE > 0:
        meta["guide"] = {
            "str": STR_GUIDE, "tau": GUIDE_TAU, "C": GUIDE_C, "m": GUIDE_M,
            "matched": guide_stats["matched"],
            "unmatched": guide_stats["unmatched"],
            "mean_g": round(guide_stats["g_sum"] / guide_stats["g_n"], 4)
                      if guide_stats["g_n"] else 0.0}
    if PERSON_ON:
        meta["person"] = {"w": W_PERSON, "named": named,
                          "mentions": person_log, "chunks": len(person_base)}
    if DOOR_TRACE:
        meta["door_trace"] = [
            {**payload[cid],
             "tag": round(W_TAG * tag_score.get(cid, 0.0), 6),
             "desc": round(W_DESC * desc_score.get(cid, 0.0), 6),
             "scope": round(W_SCOPE * scope_score.get(cid, 0.0), 6),
             **({"person": round(W_PERSON * person_score.get(cid, 0.0), 6)}
                if PERSON_ON else {}),
             "total": round(totals[cid], 6)}
            for cid in sorted(totals, key=lambda c: (-totals[c], c))]
    return selected, usage, meta


def _load_doc(root: Path, relpath: str, cache: dict):
    doc = cache.get(relpath)
    if doc is not None:
        return doc
    doc = json.loads(_corpus_path(root, relpath).read_text(encoding="utf-8"))
    cache[relpath] = doc
    return doc


def _nth_entry(root, i: int):
    if isinstance(root, list):
        return root[i]
    k, v = list(root.items())[i]
    return {k: v}


def _addressed(arr: list, loc: dict, index: int):
    rec = arr[index]
    wanted = loc.get("id")
    if wanted is not None and rec.get("id") != wanted:
        raise RuntimeError(
            f"locator {loc['chunk_ref']!r} names id {wanted!r} at "
            f"{loc['section']}[{index}] and the corpus carries {rec.get('id')!r} "
            f"— the graph and the corpus address different records")
    return rec


def locator_records(loc: dict, doc) -> list:
    if "metadata" in loc:
        if "indices" in loc:
            return [_nth_entry(doc, i) for i in loc["indices"]]
        rec = _nth_entry(doc, loc["index"])
        if loc.get("subsection"):
            rec = rec[loc["subsection"]]
        return [rec]
    arr = doc[loc["section"]]
    if "indices" in loc:
        return [arr[i] for i in loc["indices"]]
    return [_addressed(arr, loc, loc["index"])]


def _resolve_chunk(row: dict, root: Path, cache: dict) -> tuple:
    loc = json.loads(row["locator"])
    doc = _load_doc(root, row["relpath"], cache)
    records = locator_records(loc, doc)
    if "metadata" in loc:
        return "\n".join(json.dumps(r, ensure_ascii=False) for r in records), []
    if "char_range" in loc:
        start, end = loc["char_range"]
        text = records[0][loc["field"]][start:end]
    else:
        text = "\n".join(json.dumps(r, ensure_ascii=False) for r in records)
    ids, seen = [], set()
    for rec in records:
        aid = rec.get("id")
        if aid is not None and aid not in seen:
            seen.add(aid)
            ids.append(str(aid))
    return text, ids


def _budget_contexts(rows: list, budget: int, root: Path, doc_cache: dict) -> tuple:
    id_lists: list[list[str]] = []

    def stream():
        for row in rows:
            chunk_text, ids = _resolve_chunk(row, root, doc_cache)
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
    persons = resolve_persons(text, prepared.directory) if PERSON_ON else None
    with prepared.driver.session(database=DATABASE) as session:
        rows, ground_usage, meta = _retrieve(session, plan, k, prepared.channels,
                                             keep_all=char_budget is not None,
                                             persons=persons)
    meta["interpreter"] = {"model": INTERPRET_MODEL, "backend": "claude-cli"}
    retrieve_wall = time.perf_counter() - t0

    doc_cache: dict = {}
    rev_calls = rev_in = rev_out = 0
    rev_time = 0.0
    if char_budget is not None:
        contexts, chunk_id_lists, context_ids, meta["char_budget"] = _budget_contexts(
            rows, char_budget, prepared.corpus_root, doc_cache)
    else:
        contexts: list[str] = []
        context_ids: list[str] = []
        chunk_id_lists: list[list[str]] = []
        seen: set[str] = set()
        for row in rows:
            chunk_text, ids = _resolve_chunk(row, prepared.corpus_root, doc_cache)
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


_PROBE_TEMPLATES = (
    "What did the team decide about {product}?",
    "What did {person} say in the {channel} slack channel?",
    "What is the roadmap?",
)


def _selfcheck() -> None:
    corpus = Path(__file__).resolve().parent.parent.parent / "data" / "corpus" / DATASET_ID
    prepared = prepare_over_corpus(corpus)
    try:
        with prepared.driver.session(database=DATABASE) as s:
            product = s.run("MATCH (p:Product) RETURN p.name AS n ORDER BY n "
                            "LIMIT 1").single()["n"]
        channel = sorted(prepared.channels)[0]
        person = prepared.directory["surface"][
            sorted(prepared.directory["surface"])[0]] if PERSON_ON else "the team"
        probes = [t.format(product=product, person=person, channel=channel)
                  for t in _PROBE_TEMPLATES]
        print(f"artefact_volmax: {len(probes)} probes on {INTERPRET_MODEL}, up to "
              f"{4 * len(probes)} interpreter calls (none for a probe the plan "
              f"cache already holds) + up to {2 * len(probes)} sufficiency-review "
              f"calls, which no cache serves", flush=True)
        for probe in progress(probes, desc="probing", unit="q"):
            out = answer_one_question(("selfcheck", probe), prepared, None, k=10)
            meta = out.meta
            print(f"\n  {probe}", flush=True)
            print(f"    parts={[p['part'] for p in meta['parts']]} "
                  f"gate={meta['plan'].get('gate')}", flush=True)
            print(f"    walk={[(w['part'], w['path'], w['new']) for w in meta['walk']]}",
                  flush=True)
            print(f"    retrieved={meta['retrieved']} returned={meta['returned']} "
                  f"context_ids={len(out.context_ids)} "
                  f"chars={sum(len(c) for c in out.contexts)}", flush=True)
            assert len(meta["chunk_ids"]) == len(out.contexts)
            assert out.contexts, "a probe returned no context"
        print("\nartefact_volmax self-check OK", flush=True)
    finally:
        prepared.driver.close()


if __name__ == "__main__":
    _selfcheck()

from __future__ import annotations

if __name__ == "__main__":
    print("artefact_graph self-check — loading numpy, the embedder and neo4j …",
          flush=True)

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

INTERPRET_MODEL = "claude-sonnet-5"

GROUND_INDEX = "tag_emb"
DESC_INDEX = "chunk_desc_emb"

DEFAULT_TOP_K = 50


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


TAG_KNN = _env_int("HERB_GRAPH_TAG_KNN", 64)
DESC_KNN = _env_int("HERB_GRAPH_DESC_KNN", 200)

KNN_OVERFETCH = 4

W_TAG = _env_float("HERB_GRAPH_W_TAG", 1.0)
W_DESC = _env_float("HERB_GRAPH_W_DESC", 1.0)

FACET_TERM = _env_int("HERB_GRAPH_FACET_TERM", 1)

FACET_STRENGTH = _env_float("HERB_GRAPH_FACET_STRENGTH", 1.0)

FACET_PROFILE = {"topic": 1.0, "entities": 1.0, "activity": 1.0,
                 "temporal": 1.0, "evidence": 1.0}

W_CHUNK_TERM = _env_int("HERB_GRAPH_W_CHUNK_TERM", 1)

W_CHUNK_STRENGTH = _env_float("HERB_GRAPH_W_CHUNK_STRENGTH", 1.0)

CONCENTRATION_POOL = _env_int("HERB_GRAPH_CONCENTRATION_POOL", 100)

CONCENTRATION_MIN_HITS = _env_int("HERB_GRAPH_MIN_HITS", 2)
CONCENTRATION_LIFT = _env_float("HERB_GRAPH_LIFT", 3.0)

PROMOTION = _env_float("HERB_GRAPH_PROMOTION", 0.25)

COMPLETION_SHARE = _env_float("HERB_GRAPH_COMPLETION_SHARE", 0.25)

SCOPE_LIMIT = _env_int("HERB_GRAPH_SCOPE_LIMIT", 0)

LEXICAL_LIMIT = _env_int("HERB_GRAPH_LEXICAL_LIMIT", 0)

LEXICAL_SHARE = _env_float("HERB_GRAPH_LEXICAL_SHARE", 0.5)

LEXICAL_WINDOW = _env_int("HERB_GRAPH_LEXICAL_WINDOW", 1)

LEXICAL_FLOOR = _env_int("HERB_GRAPH_LEXICAL_FLOOR", 1)

LEXICAL_PROBE_CHUNKS = 300

ATTRIBUTE_MATCH = _env_int("HERB_GRAPH_ATTRIBUTE_MATCH", 0)

ATTRIBUTE_PROMOTION = _env_float("HERB_GRAPH_ATTRIBUTE_PROMOTION", 0.25)

ATTRIBUTE_STEM_MIN = 3

ATTRIBUTE_PROBE_CHUNKS = 300

PARTITIONS = ("product", "channel", "kind")

EXCLUDED_SECTIONS = ("answerable_questions", "unanswerable_questions", "product_profile")

REQUIRED_LABELS = ("File", "Chunk", "Tag", "Product", "Channel", "Kind")
REQUIRED_TYPES = ("HAS_CHUNK", "HAS_TAG", "product", "channel", "kind")

RETRIEVAL_FLAGS = {
    "HERB_DATASET_ID": DATASET_ID, "HERB_TAG_RUN_ID": RUN_ID,
    "HERB_GRAPH_TAG_KNN": TAG_KNN, "HERB_GRAPH_DESC_KNN": DESC_KNN,
    "HERB_GRAPH_W_TAG": W_TAG, "HERB_GRAPH_W_DESC": W_DESC,
    "HERB_GRAPH_FACET_TERM": FACET_TERM,
    "HERB_GRAPH_FACET_STRENGTH": FACET_STRENGTH,
    "HERB_GRAPH_W_CHUNK_TERM": W_CHUNK_TERM,
    "HERB_GRAPH_W_CHUNK_STRENGTH": W_CHUNK_STRENGTH,
    "HERB_GRAPH_CONCENTRATION_POOL": CONCENTRATION_POOL,
    "HERB_GRAPH_MIN_HITS": CONCENTRATION_MIN_HITS,
    "HERB_GRAPH_LIFT": CONCENTRATION_LIFT,
    "HERB_GRAPH_PROMOTION": PROMOTION,
    "HERB_GRAPH_COMPLETION_SHARE": COMPLETION_SHARE,
    "HERB_GRAPH_SCOPE_LIMIT": SCOPE_LIMIT,
    "HERB_GRAPH_LEXICAL_LIMIT": LEXICAL_LIMIT,
    "HERB_GRAPH_LEXICAL_SHARE": LEXICAL_SHARE,
    "HERB_GRAPH_LEXICAL_WINDOW": LEXICAL_WINDOW,
    "HERB_GRAPH_LEXICAL_FLOOR": LEXICAL_FLOOR,
    "HERB_GRAPH_ATTRIBUTE_MATCH": ATTRIBUTE_MATCH,
    "HERB_GRAPH_ATTRIBUTE_PROMOTION": ATTRIBUTE_PROMOTION,
}

if FACET_TERM:
    print(f"artefact_graph: the edge's facet weights grade the tag path, strength "
          f"{FACET_STRENGTH} (HERB_GRAPH_FACET_TERM={FACET_TERM})", flush=True)

if W_CHUNK_TERM:
    print(f"artefact_graph: the edge's magnitude grades the tag path, strength "
          f"{W_CHUNK_STRENGTH} (HERB_GRAPH_W_CHUNK_TERM={W_CHUNK_TERM})", flush=True)

if SCOPE_LIMIT:
    print(f"artefact_graph: the matching scope limits the chunk "
          f"(HERB_GRAPH_SCOPE_LIMIT={SCOPE_LIMIT})", flush=True)

if LEXICAL_LIMIT:
    print(f"artefact_graph: the query limits the chunk, share {LEXICAL_SHARE} "
          f"window {LEXICAL_WINDOW} floor {LEXICAL_FLOOR} "
          f"(HERB_GRAPH_LEXICAL_LIMIT={LEXICAL_LIMIT})", flush=True)

if ATTRIBUTE_MATCH:
    print(f"artefact_graph: the values the question names promote the chunks whose "
          f"records state them, strength {ATTRIBUTE_PROMOTION} "
          f"(HERB_GRAPH_ATTRIBUTE_MATCH={ATTRIBUTE_MATCH})", flush=True)

print(f"artefact_graph: the interpreter restates the query in both shapes on "
      f"{INTERPRET_MODEL}", flush=True)

EMBED_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "query_embed_cache"

Generator = Callable[[str, list], object]


_TAG_HITS_CYPHER = """
CALL db.index.vector.queryNodes($idx, $fetch, $vec) YIELD node AS t, score AS sim
WHERE EXISTS { MATCH (t)<-[r:HAS_TAG]-(:Chunk) WHERE r.run_id = $runId }
WITH t, sim ORDER BY sim DESC, elementId(t) LIMIT $tags
MATCH (t)<-[r:HAS_TAG]-(c:Chunk)<-[:HAS_CHUNK]-(f:File)
WHERE r.run_id = $runId
  AND coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND NOT (coalesce(c.section, "") IN $excludedSections)
WITH c, f, sim, coalesce(r.w_chunk, 0.0) AS magnitude,
     reduce(dot = 0.0, fi IN range(0, size(coalesce(r.facets, [])) - 1) |
       dot + coalesce($profile[r.facets[fi]], 0.0)
             * coalesce(r.w_facets[fi], 0.0)) AS facet
ORDER BY sim DESC, magnitude DESC, facet DESC
WITH c, f, collect({support: sim, facet: facet, magnitude: magnitude})[0] AS best
RETURN c.chunk_id AS chunkId, c.locator_json AS locator, f.rel_path AS relpath,
       c.ordinal AS ordinal, best.support AS support, best.facet AS facet,
       best.magnitude AS magnitude,
       [(c)-[:product]->(p) | elementId(p)] AS product,
       [(c)-[:channel]->(ch) | elementId(ch)] AS channel,
       [(c)-[:kind]->(kd) | elementId(kd)] AS kind
"""

_DESC_HITS_CYPHER = """
CALL db.index.vector.queryNodes($idx, $fetch, $vec) YIELD node AS c, score AS sim
MATCH (f:File)-[:HAS_CHUNK]->(c)
WHERE coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND NOT (coalesce(c.section, "") IN $excludedSections)
RETURN c.chunk_id AS chunkId, c.locator_json AS locator, f.rel_path AS relpath,
       c.ordinal AS ordinal, sim AS support,
       [(c)-[:product]->(p) | elementId(p)] AS product,
       [(c)-[:channel]->(ch) | elementId(ch)] AS channel,
       [(c)-[:kind]->(kd) | elementId(kd)] AS kind
ORDER BY support DESC, chunkId
LIMIT $k
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

_ITEM_REGIONS_CYPHER = """
MATCH (c:Chunk)-[e:product|channel|kind]->(n)
WHERE n.pointer IS NOT NULL AND n.pointer <> "" AND n.id IS NOT NULL
RETURN DISTINCT type(e) AS partition, elementId(n) AS regionId, n.id AS regionKey,
       n.pointer AS pointer
"""

_COMPLETION_CYPHER = """
MATCH (c:Chunk)-[:product|channel|kind]->(n)
WHERE elementId(n) IN $regionIds
MATCH (f:File)-[:HAS_CHUNK]->(c)
WHERE coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND NOT (coalesce(c.section, "") IN $excludedSections)
WITH DISTINCT c, f
RETURN c.chunk_id AS chunkId, c.locator_json AS locator, f.rel_path AS relpath,
       c.ordinal AS ordinal,
       [(c)-[:product]->(p) | elementId(p)] AS product,
       [(c)-[:channel]->(ch) | elementId(ch)] AS channel,
       [(c)-[:kind]->(kd) | elementId(kd)] AS kind
ORDER BY chunkId
"""

_SPLIT_CHUNKS_CYPHER = """
MATCH (c:Chunk)-[e:product|channel|kind]->(n)
WHERE n.pointer IS NOT NULL AND n.pointer <> "" AND n.id IS NOT NULL
WITH c, type(e) AS partition, collect(elementId(n)) AS regions
WHERE size(regions) > 1
MATCH (f:File)-[:HAS_CHUNK]->(c)
RETURN c.chunk_id AS chunkId, c.locator_json AS locator, f.rel_path AS relpath,
       partition, regions
ORDER BY chunkId
"""

_INDEXED_CHUNKS_CYPHER = """
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
WHERE c.locator_json CONTAINS '"indices"'
  AND coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
RETURN c.chunk_id AS chunkId, c.locator_json AS locator, f.rel_path AS relpath
ORDER BY chunkId
"""

_DECLARED_VALUES_CYPHER = """
MATCH (n) WHERE n.value IS NOT NULL AND n.pointer IS NULL
RETURN labels(n)[0] AS kind, n.value AS value
ORDER BY kind, value
"""

_RECORD_NODES_CYPHER = """
MATCH (n) WHERE n.pointer IS NOT NULL AND n.file_id IS NOT NULL
RETURN properties(n) AS props
ORDER BY n.file_id, n.pointer
"""

_FILES_CYPHER = """
MATCH (f:File) RETURN f.file_id AS fileId, f.rel_path AS relpath ORDER BY fileId
"""

_ALL_CHUNKS_CYPHER = """
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
WHERE coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND NOT (coalesce(c.section, "") IN $excludedSections)
RETURN c.chunk_id AS chunkId, c.locator_json AS locator, f.rel_path AS relpath
ORDER BY chunkId
"""


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


def _embed_query(text: str) -> tuple:
    key = _embed_key(text, "query")
    vec = _load_cached_vec(key)
    if vec is not None:
        return [float(x) for x in vec], ModelUsage()
    mat, calls, tok_in, tok_out, secs = _embed([text], "query")
    vec = np.asarray(mat[0], dtype=np.float32)
    _store_cached_vec(key, vec)
    return ([float(x) for x in vec],
            ModelUsage(calls=calls, tokens_in=tok_in, tokens_out=tok_out, time_s=secs))


_INTERPRET_SYSTEM = (
    "You describe the passage that would answer a question, in the two shapes a "
    "retrieval index is written in. You never answer the question yourself. "
    'STEP 1: "description" — 1 to 3 sentences of plain declarative prose describing '
    "what a passage carrying the answer contains, written the way a summary of that "
    "passage would be written, not as a restatement of the question. State the "
    "information need it settles, including the entities and scope the question "
    "implies. "
    'STEP 2: "phrases" — derive FROM that description the distinct things such a '
    "passage would be labelled with: specific noun phrases, named entities, systems, "
    "products, roles, artefacts and actions. Keep every specific the question names. "
    "No generic filler. "
    "Do not invent identifiers, dates or names the question does not give you, and do "
    "not emit field names or database keys. "
    'Return ONLY valid JSON: {"description":"...","phrases":["a phrase"]}.'
)


def _extract_json(text: str) -> dict:
    """The JSON object in one emission, from its first brace to its last — the
    model may frame it in prose or a fence and the payload still reads."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise ValueError(f"no JSON object in model output: {text[:200]!r}")
    return json.loads(text[start:end + 1])


def _shape(parsed: dict) -> dict:
    """One emission as the two shapes -> {"phrases": [...], "description": "..."}.
    A missing or empty side would embed nothing and blind that space, so it
    raises ValueError, which `_interpret` retries like any malformed emission."""
    phrases = [p.strip() for p in (parsed.get("phrases") or [])
               if isinstance(p, str) and p.strip()]
    description = parsed.get("description")
    if not phrases:
        raise ValueError(f"no phrases in the payload: {parsed!r}")
    if not isinstance(description, str) or not description.strip():
        raise ValueError(f"no description in the payload: {parsed!r}")
    return {"phrases": phrases, "description": description.strip()}


def _interpret(text: str) -> tuple:
    """The question restated in both shapes -> (the shapes, ModelUsage). One
    turn on INTERPRET_MODEL; a malformed emission gets one retry and a second
    failure stops the run, naming what it emitted."""
    payload = {
        "model": INTERPRET_MODEL,
        "temperature": 0,
        "max_tokens": 512,
        "messages": [
            {"role": "system", "content": _INTERPRET_SYSTEM},
            {"role": "user", "content": f"Question: {text}"},
        ],
    }
    calls = tok_in = tok_out = 0
    elapsed = 0.0
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
            raise RuntimeError(
                f"the interpreter returned empty content (finish_reason={finish})")
        try:
            shape = _shape(_extract_json(content))
        except ValueError as e:
            if attempt == 2:
                raise RuntimeError(
                    f"the interpreter emitted a malformed payload twice: {e}") from e
        else:
            return shape, ModelUsage(calls=calls, tokens_in=tok_in,
                                     tokens_out=tok_out, time_s=elapsed)


_INTERPRET_SIG = hashlib.sha256("\x00".join([
    _INTERPRET_SYSTEM, inspect.getsource(_interpret), inspect.getsource(_shape),
    inspect.getsource(_extract_json),
]).encode("utf-8")).hexdigest()


def _interpret_key(text: str) -> str:
    h = hashlib.sha256()
    for field in (INTERPRET_MODEL, _INTERPRET_SIG, text):
        b = field.encode("utf-8")
        h.update(len(b).to_bytes(8, "big"))
        h.update(b)
    return h.hexdigest()


def _store_shape(key: str, shape: dict) -> None:
    EMBED_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=EMBED_CACHE_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(shape, f, ensure_ascii=False)
        os.replace(tmp, EMBED_CACHE_DIR / f"{key}.json")
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _interpret_cached(text: str, qid: str) -> tuple:
    key = _interpret_key(text)
    path = EMBED_CACHE_DIR / f"{key}.json"
    if path.is_file():
        try:
            shape = _shape(json.loads(path.read_text(encoding="utf-8")))
        except (ValueError, OSError):
            shape = None
        if shape is not None:
            print(f"artefact_graph: {qid} restated from cache", flush=True)
            return shape, ModelUsage()
    print(f"artefact_graph: restating {qid} on {INTERPRET_MODEL} …", flush=True)
    shape, usage = _interpret(text)
    _store_shape(key, shape)
    print(f"artefact_graph: {qid} restated into {len(shape['phrases'])} phrase(s) "
          f"and {len(shape['description'])} chars of prose in {usage.time_s:.1f}s",
          flush=True)
    return shape, usage


@dataclass
class Prepared:
    driver: object
    corpus_root: Path
    region_size: dict
    population: dict
    item_regions: dict
    declared: dict
    directory: dict
    build_stats: Optional[BuildStats] = None


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


def _pointer_path(pointer: str) -> tuple:
    tokens = [t.replace("~1", "/").replace("~0", "~")
              for t in pointer.split("/")[1:]]
    if len(tokens) < 3 or not tokens[1].isdigit():
        raise RuntimeError(
            f"region pointer {pointer!r} does not address a place inside one "
            f"record of a section — an item's own membership cannot be read from it")
    return tuple(tokens[2:])


def _item_region_index(rows: list) -> dict:
    index: dict = {}
    for row in rows:
        entry = index.setdefault(row["partition"], {"paths": set(), "keys": {}})
        entry["paths"].add(_pointer_path(row["pointer"]))
        clash = entry["keys"].setdefault(row["regionKey"], row["regionId"])
        if clash != row["regionId"]:
            raise RuntimeError(
                f"two {row['partition']} regions answer to id {row['regionKey']!r} — "
                f"an item stating it sits in neither one nor the other")
    return index


def _pointer_value(doc, pointer: str):
    node = doc
    for token in pointer.split("/")[1:]:
        token = token.replace("~1", "/").replace("~0", "~")
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


def _declared_values(session) -> tuple:
    declared, census = {}, Counter()
    for row in session.run(_DECLARED_VALUES_CYPHER):
        declared[row["value"]] = _match_tokens(row["value"])
        census[row["kind"]] += 1
    return declared, census


def _record_directory(session, root: Path, declared: dict) -> tuple:
    files = {row["fileId"]: row["relpath"] for row in session.run(_FILES_CYPHER)}
    nodes = [row["props"] for row in session.run(_RECORD_NODES_CYPHER)]
    docs = {}
    for fid in progress(sorted(files), desc="verifying pointers", unit="file"):
        raw = _corpus_path(root, files[fid]).read_bytes()
        if hashlib.sha256(raw).hexdigest()[:24] == fid:
            docs[fid] = json.loads(raw.decode("utf-8"))
    directory, resolved = {}, 0
    for props in nodes:
        doc = docs.get(props["file_id"])
        if doc is None:
            continue
        record = _pointer_value(doc, props["pointer"])
        stated = record.values() if isinstance(record, dict) else ()
        values = frozenset(v for v in stated if isinstance(v, str) and v in declared)
        resolved += 1
        for key, value in props.items():
            if key in ("file_id", "pointer") or not isinstance(value, str):
                continue
            clash = directory.setdefault(value, values)
            if clash != values:
                raise RuntimeError(
                    f"two records answer to identifier {value!r} and state "
                    f"different values — an item naming it reaches neither")
    return directory, len(docs), len(files), resolved


def prepare_over_corpus(corpus) -> Prepared:
    t0 = time.perf_counter()
    corpus_root = Path(corpus)
    print(f"artefact_graph: opening {DATABASE} …", flush=True)
    drv = _driver()
    try:
        with drv.session(database=DATABASE) as s:
            labels = set(s.run("CALL db.labels() YIELD label RETURN collect(label) AS v")
                         .single()["v"])
            types = set(s.run("CALL db.relationshipTypes() YIELD relationshipType AS t "
                              "RETURN collect(t) AS v").single()["v"])
            indexes = set(s.run("SHOW INDEXES YIELD name RETURN collect(name) AS v")
                          .single()["v"])
            missing = (sorted(set(REQUIRED_LABELS) - labels)
                       + sorted(set(REQUIRED_TYPES) - types)
                       + sorted({GROUND_INDEX, DESC_INDEX} - indexes))
            if missing:
                raise RuntimeError(
                    f"{DATABASE!r} is not the graph this arm walks — missing {missing}. "
                    f"Every one of them is traversed by a query in this arm, and a "
                    f"pattern over a type the graph does not carry answers with zero "
                    f"rows instead of failing.")
            tagged = s.run("MATCH ()-[r:HAS_TAG]->() WHERE r.run_id = $runId "
                           "RETURN count(r) AS n", runId=RUN_ID).single()["n"]
            if not tagged:
                raise RuntimeError(
                    f"no HAS_TAG edge in {DATABASE!r} carries run_id {RUN_ID!r} — "
                    f"the tag path filters on it, so it would answer every query "
                    f"with zero rows instead of failing.")
            if FACET_TERM or W_CHUNK_TERM:
                bare = s.run(
                    "MATCH ()-[r:HAS_TAG]->() WHERE r.run_id = $runId AND ("
                    "r.facets IS NULL OR r.w_facets IS NULL OR r.w_chunk IS NULL "
                    "OR size(r.facets) <> size(r.w_facets)) "
                    "RETURN count(r) AS n", runId=RUN_ID).single()["n"]
                if bare:
                    raise RuntimeError(
                        f"{bare} of {tagged} HAS_TAG edge(s) in {DATABASE!r} state no "
                        f"facets, no magnitude, or facet weights their names do not "
                        f"line up with — the tag path's modifiers would read a missing "
                        f"one as zero and cancel that chunk's tag value instead of "
                        f"failing.")
            files = s.run("MATCH (f:File) WHERE f.dataset_id = $datasetId "
                          "RETURN count(f) AS n", datasetId=DATASET_ID).single()["n"]
            if not files:
                raise RuntimeError(
                    f"no File in {DATABASE!r} carries dataset_id {DATASET_ID!r} — "
                    f"every retrieval query filters on it, so all three would "
                    f"answer with zero rows instead of failing.")
            print(f"artefact_graph: {tagged} tag edges under {RUN_ID!r} over "
                  f"{files} files of {DATASET_ID!r}", flush=True)
            no_desc = s.run(
                "MATCH (c:Chunk) WHERE coalesce(c.empty, false) = false "
                "AND c.desc_emb IS NULL RETURN count(c) AS n").single()["n"]
            if no_desc:
                raise RuntimeError(
                    f"{no_desc} non-empty chunk(s) in {DATABASE!r} carry no desc_emb — "
                    f"the description path would be blind to them.")
            multi = s.run(
                "MATCH (c:Chunk) WITH c, count { (:File)-[:HAS_CHUNK]->(c) } AS n "
                "WHERE n <> 1 RETURN count(*) AS bad").single()["bad"]
            if multi:
                raise RuntimeError(
                    f"{multi} chunk(s) in {DATABASE!r} without exactly one File — "
                    f"pointer resolution would be ambiguous")
            print("artefact_graph: reading the partition census …", flush=True)
            region_size = {(r["partition"], r["regionId"]): r["size"]
                           for r in s.run(_REGION_SIZES_CYPHER)}
            population = {r["partition"]: r["population"]
                          for r in s.run(_PARTITION_POPULATION_CYPHER)}
            item_regions = _item_region_index([dict(r) for r
                                               in s.run(_ITEM_REGIONS_CYPHER)])
            declared, kinds = _declared_values(s)
            vocabulary = " | ".join(f"{kind} {n}" for kind, n
                                    in sorted(kinds.items())) or "none"
            print(f"artefact_graph: declared values: {vocabulary}", flush=True)
            directory: dict = {}
            if ATTRIBUTE_MATCH:
                if not declared:
                    raise RuntimeError(
                        f"no node in {DATABASE!r} declares a value of its own — a "
                        f"question could name nothing the corpus declares")
                directory, verified, seen, resolved = _record_directory(
                    s, corpus_root.parent, declared)
                if not directory:
                    raise RuntimeError(
                        f"no node in {DATABASE!r} resolves to a record through a "
                        f"pointer the corpus verifies — no chunk could reach a "
                        f"declared value")
                print(f"artefact_graph: {resolved} record(s) resolve through "
                      f"{verified} of {seen} file(s) the corpus verifies, "
                      f"{len(directory)} identifier(s) an item can name", flush=True)
            chunks = s.run("MATCH (c:Chunk) RETURN count(c) AS n").single()["n"]
    except Exception:
        drv.close()
        raise
    absent = sorted(set(PARTITIONS) - set(population))
    if absent:
        drv.close()
        raise RuntimeError(
            f"no chunk in {DATABASE!r} carries the {absent} partition(s) — "
            f"concentration over them would be measured against an empty null")
    census = " | ".join(
        f"{p} {sum(1 for key in region_size if key[0] == p)} regions over "
        f"{population[p]} chunks" for p in PARTITIONS)
    print(f"artefact_graph: {chunks} chunks | {census}", flush=True)
    stated = " | ".join(
        f"{partition} at {sorted('/'.join(path) for path in entry['paths'])} "
        f"over {len(entry['keys'])} regions"
        for partition, entry in sorted(item_regions.items())) or "none"
    print(f"artefact_graph: regions stated inside a record: {stated}", flush=True)
    return Prepared(
        driver=drv,
        corpus_root=corpus_root.parent,
        region_size=region_size,
        population=population,
        item_regions=item_regions,
        declared=declared,
        directory=directory,
        build_stats=BuildStats(
            build_time_s=time.perf_counter() - t0,
            model=ModelUsage(),
            models=[EMBED_MODEL, INTERPRET_MODEL],
        ),
    )


def _qid_text(question) -> tuple:
    if hasattr(question, "question") and hasattr(question, "id"):
        return question.id, question.question
    if isinstance(question, dict):
        return question.get("id", ""), question.get("question", "")
    if isinstance(question, (tuple, list)) and len(question) == 2:
        return question[0], question[1]
    return "", str(question)


def _mod(m: float, strength: float) -> float:
    return max(0.0, 1.0 + strength * (m - 1.0))


def _spread(values: list) -> dict:
    if not values:
        return {"min": 0.0, "median": 0.0, "max": 0.0, "mean": 0.0}
    v = sorted(values)
    return {"min": round(v[0], 4), "median": round(v[len(v) // 2], 4),
            "max": round(v[-1], 4), "mean": round(sum(v) / len(v), 4)}


def _hit(row) -> dict:
    return {"chunkId": row["chunkId"], "locator": row["locator"],
            "relpath": row["relpath"], "ordinal": row["ordinal"],
            "tag": 0.0, "desc": 0.0, "facet": 0.0, "magnitude": 0.0,
            "regions": {p: tuple(row[p]) for p in PARTITIONS}}


def _embed_queries(texts: list) -> tuple:
    vecs, total = [], ModelUsage()
    for text in texts:
        vec, usage = _embed_query(text)
        vecs.append(vec)
        for field in ("calls", "tokens_in", "cached_input_tokens", "tokens_out",
                      "reasoning_tokens", "time_s", "attempts", "request_s",
                      "wait_s", "retry_s"):
            setattr(total, field, getattr(total, field) + getattr(usage, field))
    return vecs, total


def _semantic_hits(session, tag_vecs: list, desc_vec: list) -> dict:
    hits: dict = {}
    params = {"runId": RUN_ID, "datasetId": DATASET_ID,
              "excludedSections": list(EXCLUDED_SECTIONS)}
    for vec in tag_vecs:
        for row in session.run(_TAG_HITS_CYPHER, idx=GROUND_INDEX, vec=vec,
                               fetch=TAG_KNN * KNN_OVERFETCH, tags=TAG_KNN,
                               profile=FACET_PROFILE, **params):
            hit = hits.setdefault(row["chunkId"], _hit(row))
            support = float(row["support"])
            if support >= hit["tag"]:
                hit["tag"] = support
                hit["facet"] = float(row["facet"])
                hit["magnitude"] = float(row["magnitude"])
    for row in session.run(_DESC_HITS_CYPHER, idx=DESC_INDEX, vec=desc_vec,
                           fetch=DESC_KNN * KNN_OVERFETCH, k=DESC_KNN, **params):
        hits.setdefault(row["chunkId"], _hit(row))["desc"] = float(row["support"])
    for hit in hits.values():
        hit["grade"] = ((_mod(hit["facet"], FACET_STRENGTH) if FACET_TERM else 1.0)
                        * (_mod(hit["magnitude"], W_CHUNK_STRENGTH)
                           if W_CHUNK_TERM else 1.0))
        hit["base"] = W_TAG * hit["tag"] * hit["grade"] + W_DESC * hit["desc"]
    return hits


def _concentration(pool: list, region_size: dict, population: dict) -> tuple:
    promoted: dict = {}
    report: dict = {}
    for partition in PARTITIONS:
        members = [h for h in pool if h["regions"][partition]]
        placed = len(members)
        chunks = population[partition]
        counts = Counter(rid for h in members for rid in h["regions"][partition])
        rows = []
        for rid, hits in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            size = region_size[(partition, rid)]
            lift = (hits / placed) / (size / chunks)
            if hits >= CONCENTRATION_MIN_HITS and lift >= CONCENTRATION_LIFT:
                promoted[(partition, rid)] = lift
                rows.append({"region_id": rid, "hits": hits, "size": size,
                             "lift": round(lift, 3)})
        report[partition] = {"placed": placed, "regions": len(counts),
                             "promoted": rows}
    return promoted, report


def _promoted_share(regions: dict, promoted: dict) -> float:
    positions = [p for p in PARTITIONS if regions[p]]
    if not positions:
        return 0.0
    reached = sum(1 for p in positions
                  if any((p, rid) in promoted for rid in regions[p]))
    return reached / len(positions)


def _hit_ordinals(pool: list, promoted: dict) -> dict:
    where: dict = {}
    for hit in pool:
        for partition in PARTITIONS:
            for rid in hit["regions"][partition]:
                key = (partition, rid)
                if key in promoted:
                    (where.setdefault(key, {}).setdefault(hit["relpath"], [])
                     .append(hit["ordinal"]))
    return where


def _completions(session, promoted: dict, hits: dict, pool: list) -> list:
    if not promoted:
        return []
    where = _hit_ordinals(pool, promoted)
    rows = []
    for row in session.run(_COMPLETION_CYPHER,
                           regionIds=[rid for _, rid in promoted],
                           datasetId=DATASET_ID,
                           excludedSections=list(EXCLUDED_SECTIONS)):
        if row["chunkId"] in hits:
            continue
        regions = {p: tuple(row[p]) for p in PARTITIONS}
        keys = [(p, rid) for p in PARTITIONS for rid in regions[p]
                if (p, rid) in promoted]
        tightest = min(keys, key=lambda key: (-promoted[key], key[1]))
        near = [abs(row["ordinal"] - o)
                for o in where.get(tightest, {}).get(row["relpath"], ())]
        rows.append({
            "chunkId": row["chunkId"], "locator": row["locator"],
            "relpath": row["relpath"], "ordinal": row["ordinal"],
            "regions": regions,
            "share": _promoted_share(regions, promoted),
            "lift": promoted[tightest],
            "gap": min(near) if near else None,
        })
    rows.sort(key=lambda r: (-r["share"], -r["lift"],
                             float("inf") if r["gap"] is None else r["gap"],
                             r["chunkId"]))
    return rows


def _corpus_path(root: Path, relpath: str) -> Path:
    path = (root / relpath).resolve()
    if not path.is_relative_to(root.resolve()):
        raise RuntimeError(
            f"relpath {relpath!r} resolves outside the corpus root — refusing to read it")
    return path


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


def _render(records: list) -> str:
    return "\n".join(json.dumps(r, ensure_ascii=False) for r in records)


def _stated_regions(record, entry: dict) -> set:
    found = set()
    for path in entry["paths"]:
        node = record
        for token in path:
            node = node.get(token) if isinstance(node, dict) else None
        if isinstance(node, dict):
            found.update(entry["keys"][v] for v in node.values()
                         if isinstance(v, str) and v in entry["keys"])
    return found


_TERM = re.compile(r"[^\W_]+", re.UNICODE)


def _terms(text: str) -> frozenset:
    return frozenset(m.group(0).lower() for m in _TERM.finditer(text))


def _lexical_keep(records: list, terms: frozenset) -> tuple:
    n = len(records)
    carried = [_terms(json.dumps(rec, ensure_ascii=False)) & terms for rec in records]
    df = Counter(term for ts in carried for term in ts)
    scores = [sum(math.log(n / df[term]) for term in ts) for ts in carried]
    bar = LEXICAL_SHARE * max(scores, default=0.0)
    seeds = [i for i, score in enumerate(scores) if score > 0 and score >= bar]
    scored = len(seeds)
    if len(seeds) < LEXICAL_FLOOR:
        seeds = sorted(sorted(range(n),
                              key=lambda i: (-scores[i], i))[:LEXICAL_FLOOR])
    kept = sorted({j for i in seeds
                   for j in range(max(0, i - LEXICAL_WINDOW),
                                  min(n, i + LEXICAL_WINDOW + 1))})
    return kept, scored


def _scope_limit(promoted: dict, item_regions: dict) -> dict:
    scope = {}
    for partition, entry in item_regions.items():
        reached = {rid for p, rid in promoted if p == partition}
        if reached:
            scope[partition] = dict(entry, promoted=reached)
    return scope


def _on_scope(records: list, regions: dict, scope: dict, chunk_id: str) -> list:
    limiting = [(partition, entry) for partition, entry in scope.items()
                if set(regions[partition]) & entry["promoted"]]
    if not limiting:
        return records
    kept = []
    for record in records:
        on = True
        for partition, entry in limiting:
            stated = _stated_regions(record, entry)
            if not stated:
                raise RuntimeError(
                    f"chunk {chunk_id} sits in a concentrated {partition} region "
                    f"and one of its records states no {partition} of its own — "
                    f"the graph and the corpus place its items differently")
            if not stated & entry["promoted"]:
                on = False
                break
        if on:
            kept.append(record)
    return kept


def _resolve_chunk(row: dict, root: Path, cache: dict,
                   scope: Optional[dict] = None,
                   terms: Optional[frozenset] = None) -> tuple:
    loc = json.loads(row["locator"])
    doc = _load_doc(root, row["relpath"], cache)
    records = locator_records(loc, doc)
    if "metadata" in loc:
        return _render(records), [], None
    limited = None
    if "char_range" in loc:
        start, end = loc["char_range"]
        text = records[0][loc["field"]][start:end]
    else:
        text = _render(records)
        if (scope or terms is not None) and "indices" in loc:
            limited = {"items": len(records), "on_scope": len(records),
                       "rendered": len(records), "chars": len(text),
                       "chars_rendered": len(text)}
            if scope:
                records = _on_scope(records, row["regions"], scope, row["chunkId"])
                limited["on_scope"] = limited["rendered"] = len(records)
            if terms is not None:
                kept, limited["scored"] = _lexical_keep(records, terms)
                records = [records[i] for i in kept]
                limited["rendered"] = len(records)
            if limited["rendered"] != limited["items"]:
                text = _render(records)
                limited["chars_rendered"] = len(text)
    ids, seen = [], set()
    for rec in records:
        aid = rec.get("id")
        if aid is not None and aid not in seen:
            seen.add(aid)
            ids.append(str(aid))
    return text, ids, limited


def _match_tokens(text: str) -> tuple:
    return tuple(token[:-1] if token.endswith("s") and len(token) > ATTRIBUTE_STEM_MIN
                 else token
                 for token in (m.group(0).lower() for m in _TERM.finditer(text)))


def _named_values(text: str, declared: dict) -> frozenset:
    tokens = _match_tokens(text)
    return frozenset(value for value, key in declared.items()
                     if key and any(tokens[i:i + len(key)] == key
                                    for i in range(len(tokens) - len(key) + 1)))


def _derived_attributes(records: list, directory: dict) -> frozenset:
    values = set()
    stack = list(records)
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
        elif isinstance(node, str):
            values.update(directory.get(node, ()))
    return frozenset(values)


def _pool_attributes(rows: list, root: Path, cache: dict, directory: dict) -> dict:
    return {row["chunkId"]: _derived_attributes(
        locator_records(json.loads(row["locator"]),
                        _load_doc(root, row["relpath"], cache)), directory)
        for row in rows}


def _named_share(attributes: frozenset, named: frozenset) -> float:
    return len(attributes & named) / len(named) if named else 0.0


def _context_ids(id_lists: list) -> list:
    out, seen = [], set()
    for ids in id_lists:
        for aid in ids:
            if aid not in seen:
                seen.add(aid)
                out.append(aid)
    return out


def _budget_contexts(ranked: list, completions: list, budget: int, root: Path,
                     cache: dict, scope: Optional[dict],
                     terms: Optional[frozenset]) -> tuple:
    reserve = int(budget * COMPLETION_SHARE) if completions else 0
    limit = budget - reserve
    id_lists: list = []
    completed: list = []
    scope_rows: list = []

    def emit(row, text, ids, limited, origin):
        id_lists.append(ids)
        scope_rows.append(limited)
        completed.append(origin)
        return row["chunkId"], text

    def stream():
        rest = iter(ranked)
        held = None
        chars = 0
        for row in rest:
            text, ids, limited = _resolve_chunk(row, root, cache, scope, terms)
            if id_lists and chars + len(text) > limit:
                held = (row, text, ids, limited)
                break
            chars += len(text)
            yield emit(row, text, ids, limited, False)
        taken = 0
        for row in completions:
            text, ids, limited = _resolve_chunk(row, root, cache, scope, terms)
            if taken + len(text) > reserve:
                break
            taken += len(text)
            yield emit(row, text, ids, limited, True)
        if held is not None:
            yield emit(*held, False)
        for row in rest:
            text, ids, limited = _resolve_chunk(row, root, cache, scope, terms)
            yield emit(row, text, ids, limited, False)

    cut = cut_at_budget(stream(), budget)
    block = {"budget": budget, "chars": cut.chars, "kept": cut.kept,
             "boundary": cut.boundary, "exhausted": cut.exhausted,
             "completion_reserve": reserve}
    return (cut.contexts, id_lists, _context_ids(id_lists[:cut.kept]),
            sum(completed), scope_rows, block)


def _depth_contexts(ranked: list, completions: list, k: int, root: Path,
                    cache: dict, scope: Optional[dict],
                    terms: Optional[frozenset]) -> tuple:
    reserve = int(round(k * COMPLETION_SHARE)) if completions else 0
    lead = max(1, k - reserve)
    taken = min(lead, len(ranked))
    filled = completions[:max(0, k - taken)]
    rows = (ranked[:lead] + filled + ranked[lead:])[:k]
    contexts, id_lists, scope_rows = [], [], []
    for row in rows:
        text, ids, limited = _resolve_chunk(row, root, cache, scope, terms)
        contexts.append(text)
        id_lists.append(ids)
        scope_rows.append(limited)
    return contexts, id_lists, _context_ids(id_lists), len(filled), scope_rows


def answer_one_question(question, prepared: Prepared, generate: Optional[Generator],
                        k: int = DEFAULT_TOP_K,
                        char_budget: Optional[int] = None) -> ArmOutput:
    qid, text = _qid_text(question)

    nim.reset_timing()
    t0 = time.perf_counter()
    shape, interp_usage = _interpret_cached(text, qid)
    tag_texts = [text] if os.environ.get("HERB_GRAPH_RAW_TAG") == "1" else shape["phrases"]
    desc_text = text if os.environ.get("HERB_GRAPH_RAW_DESC") == "1" else shape["description"]
    tag_vecs, tag_usage = _embed_queries(tag_texts)
    desc_vec, desc_usage = _embed_query(desc_text)
    model_time_s = interp_usage.time_s + tag_usage.time_s + desc_usage.time_s
    with prepared.driver.session(database=DATABASE) as session:
        hits = _semantic_hits(session, tag_vecs, desc_vec)
        pool = sorted(hits.values(), key=lambda h: (-h["base"], h["chunkId"]))
        promoted, report = _concentration(pool[:CONCENTRATION_POOL],
                                          prepared.region_size, prepared.population)
        for hit in pool:
            hit["score"] = hit["base"] + PROMOTION * _promoted_share(hit["regions"],
                                                                    promoted)
        ranked = sorted(pool, key=lambda h: (-h["score"], h["chunkId"]))
        completions = _completions(session, promoted, hits, pool[:CONCENTRATION_POOL])
    search_time_s = (time.perf_counter() - t0) - model_time_s
    scope = _scope_limit(promoted, prepared.item_regions) if SCOPE_LIMIT else None
    terms = _terms(text) if LEXICAL_LIMIT else None

    doc_cache: dict = {}
    named = _named_values(text, prepared.declared) if ATTRIBUTE_MATCH else None
    if named is not None:
        attributes = _pool_attributes(ranked, prepared.corpus_root, doc_cache,
                                      prepared.directory)
        for hit in ranked:
            hit["score"] += ATTRIBUTE_PROMOTION * _named_share(
                attributes[hit["chunkId"]], named)
        ranked = sorted(ranked, key=lambda h: (-h["score"], h["chunkId"]))
    meta = {"interpreter": {"model": INTERPRET_MODEL, "backend": "claude-cli",
                            "phrases": len(shape["phrases"]),
                            "description_chars": len(shape["description"])},
            "hits": {"tag": sum(1 for h in hits.values() if h["tag"]),
                     "desc": sum(1 for h in hits.values() if h["desc"]),
                     "pool": len(hits)},
            "concentration": report,
            "completion": {"candidates": len(completions)}}
    if FACET_TERM or W_CHUNK_TERM:
        reached = [h for h in hits.values() if h["tag"]]
        meta["tag_grade"] = _spread([h["grade"] for h in reached])
    if FACET_TERM:
        meta["facets"] = {
            "candidates": len(hits),
            "graded": sum(1 for h in reached if h["facet"] > 0.0),
            "term": _spread([h["facet"] for h in reached]),
            "factor": _spread([_mod(h["facet"], FACET_STRENGTH) for h in reached]),
        }
    if W_CHUNK_TERM:
        meta["w_chunk"] = {
            "candidates": len(hits),
            "graded": sum(1 for h in reached if h["magnitude"] > 0.0),
            "term": _spread([h["magnitude"] for h in reached]),
            "factor": _spread([_mod(h["magnitude"], W_CHUNK_STRENGTH)
                               for h in reached]),
        }
    if char_budget is not None:
        (contexts, chunk_id_lists, context_ids, completed, scope_rows,
         meta["char_budget"]) = _budget_contexts(
            ranked, completions, char_budget, prepared.corpus_root, doc_cache,
            scope, terms)
    else:
        (contexts, chunk_id_lists, context_ids, completed,
         scope_rows) = _depth_contexts(
            ranked, completions, k, prepared.corpus_root, doc_cache, scope, terms)
    meta["completion"]["returned"] = completed
    meta["returned"] = len(contexts)
    if SCOPE_LIMIT or LEXICAL_LIMIT:
        eligible = [row for row in scope_rows if row]
        block = {
            "chunks": scope_rows,
            "eligible": len(eligible),
            "limited": sum(1 for row in eligible if row["rendered"] < row["items"]),
            "items": sum(row["items"] for row in eligible),
            "on_scope": sum(row["on_scope"] for row in eligible),
            "rendered": sum(row["rendered"] for row in eligible),
            "chars": sum(row["chars"] for row in eligible),
            "chars_rendered": sum(row["chars_rendered"] for row in eligible),
        }
        if LEXICAL_LIMIT:
            block["scored"] = sum(row["scored"] for row in eligible)
        meta["scope_limit"] = block
    if named is not None:
        meta["attributes"] = {
            "declared": len(prepared.declared),
            "named": sorted(named),
            "candidates": len(ranked),
            "with_attributes": sum(1 for v in attributes.values() if v),
            "matching": sum(1 for v in attributes.values() if v & named),
        }
    meta["chunk_ids"] = chunk_id_lists

    spent = (interp_usage, tag_usage, desc_usage)
    retrieval_usage = ModelUsage(
        calls=sum(u.calls for u in spent),
        tokens_in=sum(u.tokens_in for u in spent),
        tokens_out=sum(u.tokens_out for u in spent), time_s=model_time_s,
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


_PROBES = (
    "What did the team decide about the release timeline in the planning channel?",
    "Which pull request changed the authentication flow, and who reviewed it?",
    "What is the roadmap?",
)


def _delivered(text: str) -> tuple:
    items = [json.loads(line) for line in text.split("\n")]
    return items, list(dict.fromkeys(str(item["id"]) for item in items))


def _scope_probe(prepared: Prepared) -> None:
    with prepared.driver.session(database=DATABASE) as session:
        splits = [dict(r) for r in session.run(_SPLIT_CHUNKS_CYPHER)]
    print(f"artefact_graph: {len(splits)} chunk(s) sit in more than one stated "
          f"region — driving the scope limit over each", flush=True)
    terms = _terms(_PROBES[0])
    cache: dict = {}
    for split in progress(splits, desc="scope probe", unit="chunk"):
        partition = split["partition"]
        row = dict(split, regions={p: tuple(split["regions"]) if p == partition
                                   else () for p in PARTITIONS})
        whole, whole_ids, _ = _resolve_chunk(row, prepared.corpus_root, cache)
        rendered = 0
        for region in split["regions"]:
            scope = _scope_limit({(partition, region): 1.0}, prepared.item_regions)
            text, ids, limited = _resolve_chunk(row, prepared.corpus_root, cache, scope)
            items, read_back = _delivered(text)
            assert ids == read_back, (
                f"{split['chunkId']}: the ids do not follow the rendered text")
            assert limited["rendered"] == len(items) < limited["items"]
            assert limited["chars_rendered"] == len(text) < limited["chars"]
            assert set(ids) <= set(whole_ids)
            rendered += len(items)
            narrowed, narrow_ids, cut = _resolve_chunk(
                row, prepared.corpus_root, cache, scope, terms)
            narrow_items, narrow_read_back = _delivered(narrowed)
            assert narrow_ids == narrow_read_back, (
                f"{split['chunkId']}: the ids do not follow the narrowed text")
            assert cut["on_scope"] == limited["rendered"]
            assert 0 < cut["rendered"] == len(narrow_items) <= cut["on_scope"]
            assert cut["chars_rendered"] == len(narrowed)
            assert set(narrow_ids) <= set(ids)
        assert rendered == limited["items"], (
            f"{split['chunkId']}: its items do not divide over its {partition} regions")
        assert len(whole) == limited["chars"]


def _lexical_probe(prepared: Prepared) -> None:
    with prepared.driver.session(database=DATABASE) as session:
        rows = [dict(r) for r in session.run(_INDEXED_CHUNKS_CYPHER,
                                             datasetId=DATASET_ID)]
    stride = max(1, len(rows) // LEXICAL_PROBE_CHUNKS)
    sample = rows[::stride]
    print(f"artefact_graph: {len(rows)} chunk(s) list their items — driving the "
          f"lexical limit over {len(sample)} of them, {len(_PROBES)} queries each",
          flush=True)
    cache: dict = {}
    items_seen = rendered_seen = chars_seen = chars_rendered = 0
    for row in progress(sample, desc="lexical probe", unit="chunk"):
        whole, whole_ids, _ = _resolve_chunk(row, prepared.corpus_root, cache)
        whole_lines = whole.split("\n")
        for probe in _PROBES:
            terms = _terms(probe)
            text, ids, cut = _resolve_chunk(row, prepared.corpus_root, cache,
                                            None, terms)
            if cut is None:
                continue
            items, read_back = _delivered(text)
            assert ids == read_back, (
                f"{row['chunkId']}: the ids do not follow the rendered text")
            assert cut["items"] == cut["on_scope"] == len(whole_lines)
            assert min(LEXICAL_FLOOR, cut["items"]) <= cut["rendered"] == len(items)
            assert cut["rendered"] <= cut["items"]
            assert cut["scored"] <= cut["items"]
            assert cut["chars_rendered"] == len(text) <= cut["chars"] == len(whole)
            rest = iter(whole_lines)
            assert all(any(line == other for other in rest)
                       for line in text.split("\n")), (
                f"{row['chunkId']}: the delivery is not the chunk's own items in "
                f"its own order")
            assert set(ids) <= set(whole_ids)
            items_seen += cut["items"]
            rendered_seen += cut["rendered"]
            chars_seen += cut["chars"]
            chars_rendered += cut["chars_rendered"]
    print(f"artefact_graph: the lexical limit delivered {rendered_seen} of "
          f"{items_seen} items and {chars_rendered} of {chars_seen} chars over "
          f"the probe", flush=True)


def _attribute_probe(prepared: Prepared) -> None:
    with prepared.driver.session(database=DATABASE) as session:
        rows = [dict(r) for r in session.run(
            _ALL_CHUNKS_CYPHER, datasetId=DATASET_ID,
            excludedSections=list(EXCLUDED_SECTIONS))]
        directory = prepared.directory or _record_directory(
            session, prepared.corpus_root, prepared.declared)[0]
    stride = max(1, len(rows) // ATTRIBUTE_PROBE_CHUNKS)
    sample = rows[::stride]
    print(f"artefact_graph: {len(rows)} retrievable chunk(s) — deriving attributes "
          f"over {len(sample)} of them against {len(directory)} identifier(s)",
          flush=True)
    values = frozenset(prepared.declared)
    named = {probe: _named_values(probe, prepared.declared) for probe in _PROBES}
    for probe, found in named.items():
        assert found <= values, f"{probe!r} named a value the corpus does not declare"
    cache: dict = {}
    carrying = 0
    for row in progress(sample, desc="attribute probe", unit="chunk"):
        attributes = _derived_attributes(
            locator_records(json.loads(row["locator"]),
                            _load_doc(prepared.corpus_root, row["relpath"], cache)),
            directory)
        assert attributes <= values, (
            f"{row['chunkId']}: reached a value the corpus does not declare")
        carrying += bool(attributes)
        for found in named.values():
            assert 0.0 <= _named_share(attributes, found) <= 1.0
    print(f"artefact_graph: {carrying} of {len(sample)} sampled chunk(s) reach a "
          f"record the graph points at, and the probes name "
          f"{[len(found) for found in named.values()]} declared value(s)", flush=True)


def _selfcheck() -> None:
    corpus = Path(__file__).resolve().parent.parent.parent / "data" / "corpus" / DATASET_ID
    prepared = prepare_over_corpus(corpus)
    try:
        print(f"artefact_graph: {len(_PROBES)} probes, up to {len(_PROBES)} "
              f"reformulation calls on {INTERPRET_MODEL} and "
              f"{2 * len(_PROBES)} embedding calls on {EMBED_MODEL}", flush=True)
        for probe in progress(_PROBES, desc="probing", unit="q"):
            out = answer_one_question(("selfcheck", probe), prepared, None,
                                      char_budget=72000)
            meta = out.meta
            print(f"\n  {probe}", flush=True)
            print(f"    hits: tag={meta['hits']['tag']} desc={meta['hits']['desc']} "
                  f"pool={meta['hits']['pool']}", flush=True)
            for name in ("facets", "w_chunk"):
                block = meta.get(name)
                if block is None:
                    continue
                print(f"    {name}: {block['graded']} of {block['candidates']} "
                      f"candidate(s) graded, term {block['term']['min']} to "
                      f"{block['term']['max']} median {block['term']['median']}, "
                      f"factor median {block['factor']['median']}", flush=True)
                assert block["graded"] <= block["candidates"]
            if "tag_grade" in meta:
                print(f"    tag grade: {meta['tag_grade']['min']} to "
                      f"{meta['tag_grade']['max']} median "
                      f"{meta['tag_grade']['median']}", flush=True)
            for partition, block in meta["concentration"].items():
                print(f"    {partition}: {len(block['promoted'])} of "
                      f"{block['regions']} regions promoted, lifts="
                      f"{[r['lift'] for r in block['promoted'][:5]]}", flush=True)
            print(f"    completion: {meta['completion']['returned']} of "
                  f"{meta['completion']['candidates']} candidates returned, "
                  f"contexts={meta['returned']} context_ids={len(out.context_ids)} "
                  f"chars={sum(len(c) for c in out.contexts)}", flush=True)
            block = meta.get("scope_limit")
            if block is not None:
                print(f"    scope: {block['limited']} of {block['eligible']} "
                      f"eligible chunk(s) cut, {block['rendered']}/{block['items']} "
                      f"items, {block['chars_rendered']}/{block['chars']} chars",
                      flush=True)
                assert len(block["chunks"]) == len(out.contexts)
                assert block["rendered"] <= block["items"]
            block = meta.get("attributes")
            if block is not None:
                print(f"    attributes: {len(block['named'])} declared value(s) "
                      f"named, {block['matching']} of {block['with_attributes']} "
                      f"chunk(s) with attributes match, over "
                      f"{block['candidates']} candidates", flush=True)
                assert block["matching"] <= block["with_attributes"] <= block["candidates"]
            assert len(meta["chunk_ids"]) == len(out.contexts)
            assert out.contexts, "a probe returned no context"
        _scope_probe(prepared)
        _lexical_probe(prepared)
        _attribute_probe(prepared)
        print("\nartefact_graph self-check OK", flush=True)
    finally:
        prepared.driver.close()


if __name__ == "__main__":
    _selfcheck()

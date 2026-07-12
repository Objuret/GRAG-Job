"""artefact_v1.py — the ARTEFACT-V1 arm: facet-grounded tag retrieval over the
Neo4j `herb-eval` graph (the v1 artefact build), scored head-to-head with the
lucene and vector arms under the same shared generator and the same RAGAS eval.

The graph under test is `Source -[:CONTAINS]-> File -[:HAS_CHUNK]-> Chunk
-[:HAS_TAG]-> Tag`, holding no content — structure, weights, and embeddings
only. Each `HAS_TAG` edge carries `w_chunk`, `w_facet`, `facet`, and `run_id`.
The semantic layer is two nemotron vector families written by
`reembed_herb_eval.py` (run once before this arm): the tag IS its embedding —
each `:Tag` name embedded bare as `t.emb` under the `tag_emb` cosine index —
and each chunk's description IS an embedding, `c.desc_emb` (the description
text itself lives nowhere in this graph). The whole arm runs on the v3 model
stack (NIM throughout, no local model):

  1. interpret — two NIM passes on the shared v3 model (qwen). Pass 1 emits a
     self-contained statement of the information need + structured tags + a hard
     gate (product / section / channel / employee_id / years, only when the query
     names them). Pass 2 scores each tag across five facets (topic, entities,
     activity, temporal, evidence); `w_query` is derived from the facet vector
     (strength × coverage).
  2. ground — one embed call (query side) for the pass-1 description + the
     prompt tag names, bare. Each prompt tag kNNs the `tag_emb` index for its
     nearest corpus tags; each grounded tag carries the grounding cosine as
     `sim` plus the prompt tag's full facet vector (facet agreement is scored
     numerically against the edge's facet arrays, facets are never embedded).
  3. score — the weighted-overlap Cypher: each prompt tag contributes its best
     matching `HAS_TAG` edge on a chunk (max over that tag's grounded links),
     summed across prompt tags, then multiplied by the chunk's
     description-similarity — cosine of the prompt-description vector against
     `c.desc_emb`, one more weight in the chain — then top-k. When the tag
     channel has no grip on the (gated) candidates — attribute/aggregate
     questions whose tags name the question's form, not any chunk's content —
     the description channel carries retrieval alone: the same gated candidates
     ranked by description agreement × chunk-to-file weight (logged, never
     silent). The oracle sections (answerable / unanswerable questions, product
     profiles) are excluded so the arm cannot read the gold answer; a question
     fails loud only when its gate matches no chunks at all.

The graph stores references, never content: a retrieved chunk is a pointer —
`locator_json` (HERB section/index/indices/field/char_range) on the chunk plus
`rel_path` + `sha256` on its file — and the arm resolves the text from the raw
files under `v3/data/raw` at answer time, hash-verified, failing loud on any
drifted file or dangling pointer. `context_ids` are the HERB artifact `id`s of
the records a chunk covers (read from the raw records themselves), the same id
space the gold citations use, so the id-based context metrics compare
like-for-like with lucene/vector. Metadata chunks (directories, org tree) have
no artifact ids and contribute none.

The shared v3 generator writes the answer from the resolved chunk text, so the
only thing that differs from lucene/vector is retrieval. Contract mirrors the
other arms: `prepare_over_corpus(corpus) -> Prepared` opens the Neo4j driver and
checks the grounding indexes; `answer_one_question(question, prepared, generate,
k) -> ArmOutput` runs interpret → ground → score → resolve → generate per
question. The question is read for id + text ONLY; truth fields are never
touched.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import nim
from contract import ArmOutput, BuildStats, ModelUsage
from pipelines.vector import EMBED_MODEL, _embed

log = logging.getLogger("pipelines.artefact_v1")

# --- graph + retrieval constants (the live herb-eval contract) ----------------

DATABASE = os.environ.get("NEO4J_DATABASE", "herb-eval")
DATASET_ID = os.environ.get("HERB_DATASET_ID", "Salesforce__HERB")
# HAS_TAG edges are stamped with the tagging run that wrote them; retrieval reads
# exactly that run. Override if the graph was tagged under a different run id.
RUN_ID = os.environ.get("HERB_TAG_RUN_ID", "pilot_full_herb")

INTERPRET_MODEL = "qwen/qwen3.5-397b-a17b"

# The five facets. Facet agreement is numeric — the prompt tag's facet values
# against the edge's facet arrays; facets are never embedded.
ALL_FACETS = ("topic", "entities", "activity", "temporal", "evidence")
GROUND_INDEX = "tag_emb"          # :Tag(emb) — the tag IS its embedding
DESC_INDEX = "chunk_desc_emb"     # :Chunk(desc_emb) — the description IS an embedding

# Eval-safety: the gold-answer records and oracle product profiles never enter
# retrieval, so the arm cannot read its own evaluation.
EXCLUDED_SECTIONS = ("answerable_questions", "unanswerable_questions", "product_profile")
GATE_SECTIONS = (
    "slack", "documents", "meeting_transcripts", "meeting_chats", "prs",
    "urls", "answerable_questions", "unanswerable_questions", "product_profile",
)

# Grounding: kNN the tag index for GROUNDING_K nearest corpus tags per prompt tag,
# above an optional cosine floor (0.0 = top-K is the only filter).
GROUNDING_K = int(os.environ.get("HERB_GROUNDING_K", "10"))
MIN_SIM = float(os.environ.get("HERB_MIN_SIM", "0.0"))
MIN_W_CHUNK = 0.0
MIN_RELEVANCE_TO_FILE = 0.0

FILLER = {"data", "information", "content", "record", "text", "chunk", "item", "find"}
COVERAGE_ALPHA = 0.25

# The raw files the graph's pointers resolve against (File.rel_path is relative
# to this root; File.sha256 is verified on every read).
RAW_ROOT = Path(__file__).resolve().parent.parent / "data" / "raw"

Generator = Callable[[str, list], object]


# --- Cypher (the weighted-overlap retrieval over the graph contract) ----------

_GROUND_CYPHER = (
    "CALL db.index.vector.queryNodes($idx, $k, $vec) YIELD node, score "
    "RETURN node.name AS name, score AS sim"
)


def _gate_clause(gate: dict) -> tuple[str, dict]:
    """The hard-gate WHERE fragment + params from the plan's structured gate,
    ANDed onto the chunk before any tag scoring. Empty when nothing is set."""
    parts, params = [], {}
    for f in ("product", "section", "channel", "employee_id"):
        v = gate.get(f)
        if v:
            parts.append(f"AND c.{f} = $g_{f}")
            params[f"g_{f}"] = v
    years = gate.get("years") or []
    if years:
        params["g_years"] = list(years)
        parts.append("AND any(y IN $g_years WHERE y IN c.years)")
    return "\n  ".join(parts), params


# One HAS_TAG edge per (chunk, tag), carrying the full facet vector as aligned
# arrays (`facets` / `w_facets`) plus `w_chunk`. Facet agreement = the dot
# product of the prompt tag's facet values with the edge's facet weights (a
# facet absent from the edge contributes 0).
_SCORE_CYPHER = """
UNWIND $queryTags AS qt
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
MATCH (c)-[r:HAS_TAG]->(t:Tag {{name: qt.name}})
WHERE coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND r.run_id = $runId
  AND coalesce(r.w_chunk, 0.0) >= $minWChunk
  AND coalesce(c.relevance_to_file, 1.0) >= $minRelevanceToFile
  {gate}
  AND NOT (coalesce(c.section, "") IN $excludedSections)
WITH c, qt, r,
     reduce(dot = 0.0, fi IN range(0, size(r.facets) - 1) |
       dot + (CASE r.facets[fi]
                WHEN 'topic'    THEN qt.topic
                WHEN 'entities' THEN qt.entities
                WHEN 'activity' THEN qt.activity
                WHEN 'temporal' THEN qt.temporal
                WHEN 'evidence' THEN qt.evidence
                ELSE 0.0
              END) * coalesce(r.w_facets[fi], 0.0)) AS facetTerm
WITH c, qt.promptIndex AS promptIdx,
     (qt.w_query * facetTerm * r.w_chunk
       * coalesce(c.relevance_to_file, 1.0) * qt.sim) AS contrib
WITH c, promptIdx, max(contrib) AS bestPromptContrib
WITH c, sum(bestPromptContrib) AS tagScore
WHERE tagScore > 0
WITH c, tagScore * vector.similarity.cosine(c.desc_emb, $descVec) AS score
MATCH (f:File)-[:HAS_CHUNK]->(c)
RETURN c.chunk_id AS chunkId, c.locator_json AS locator,
       f.rel_path AS relpath, f.sha256 AS sha256, round(score, 4) AS score
ORDER BY score DESC
LIMIT $limit
"""

# The description channel alone: when the tag channel has no grip on the (gated)
# candidates, chunks rank by prompt-description ↔ chunk-description agreement ×
# chunk-to-file weight. Same graph, same embeddings — no text search involved.
_DESC_CYPHER = """
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
WHERE coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND coalesce(c.relevance_to_file, 1.0) >= $minRelevanceToFile
  {gate}
  AND NOT (coalesce(c.section, "") IN $excludedSections)
WITH c, f, vector.similarity.cosine(c.desc_emb, $descVec)
       * coalesce(c.relevance_to_file, 1.0) AS score
RETURN c.chunk_id AS chunkId, c.locator_json AS locator,
       f.rel_path AS relpath, f.sha256 AS sha256, round(score, 4) AS score
ORDER BY score DESC
LIMIT $limit
"""



# --- prepare ------------------------------------------------------------------

@dataclass
class Prepared:
    """Handle returned by prepare(): the live Neo4j driver + BuildStats. The tag
    grounding vectors live in the graph (the six `tag_emb_<facet>` indexes), so
    there is nothing to load here beyond the connection."""

    driver: object
    build_stats: Optional[BuildStats] = None


def _driver():
    """Neo4j driver from the usual v3/.env (loaded by nim, same as every other
    secret) — fail loud, no silent default. NEO4J_URI / NEO4J_USER default to the
    local install; NEO4J_PASSWORD is required (set it in v3/.env)."""
    from neo4j import GraphDatabase
    nim._load_dotenv()
    pw = os.environ.get("NEO4J_PASSWORD")
    if not pw:
        raise RuntimeError("NEO4J_PASSWORD is not set — add it to v3/.env (like NVIDIA_API_KEY).")
    uri = os.environ.get("NEO4J_URI", "neo4j://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    return GraphDatabase.driver(uri, auth=(user, pw))


def _readable(name: str) -> str:
    return name.replace("_", " ").strip()


def prepare_over_corpus(corpus) -> Prepared:
    """Open the Neo4j driver and confirm the per-facet grounding indexes are
    present. `corpus` is accepted for contract parity but unused — this arm reads
    the graph, not the on-disk corpus. Fails loud if `herb-eval` is unreachable or
    any `tag_emb_<facet>` index is missing (run `reembed_herb_eval.py` first)."""
    t0 = time.perf_counter()
    drv = _driver()
    with drv.session(database=DATABASE) as s:
        s.run("RETURN 1").consume()  # loud now if the DB is down or misnamed
        present = s.run(
            "SHOW INDEXES YIELD name WHERE name IN [$t, $d] "
            "RETURN collect(name) AS names", t=GROUND_INDEX, d=DESC_INDEX).single()["names"]
        # Every chunk must carry a description vector — the score chain multiplies
        # by it, and a null would silently drop the chunk from every result.
        no_desc = s.run(
            "MATCH (c:Chunk) WHERE c.desc_emb IS NULL RETURN count(c) AS n").single()["n"]
        # Pointer resolution assumes exactly one File per Chunk — the score Cypher
        # re-MATCHes the file after aggregation, so a violation would duplicate
        # output rows. Assert the invariant once here, not per query.
        multi = s.run(
            "MATCH (c:Chunk) WITH c, count { (:File)-[:HAS_CHUNK]->(c) } AS n "
            "WHERE n <> 1 RETURN count(*) AS bad").single()["bad"]
    if multi:
        raise RuntimeError(
            f"{multi} chunk(s) in {DATABASE!r} without exactly one File — "
            f"pointer resolution would be ambiguous")
    missing = sorted({GROUND_INDEX, DESC_INDEX} - set(present))
    if missing or no_desc:
        raise RuntimeError(
            f"semantic layer incomplete in {DATABASE!r} (missing indexes: {missing or 'none'}, "
            f"chunks without desc_emb: {no_desc}) — run `python reembed_herb_eval.py` once.")
    build_stats = BuildStats(
        build_time_s=time.perf_counter() - t0,
        model=ModelUsage(),            # no model call at prepare; tags are pre-embedded in the graph
        models=[EMBED_MODEL],
    )
    return Prepared(driver=drv, build_stats=build_stats)


# --- interpret (two NIM passes on the shared v3 model) ------------------------

def _qid_text(question) -> tuple:
    """(id, question_text) from a QuestionWithTruth, dict, (id, text) tuple, or a
    bare string. Reads ONLY id + question — truth fields are never touched."""
    if hasattr(question, "question") and hasattr(question, "id"):
        return question.id, question.question
    if isinstance(question, dict):
        return question.get("id", ""), question.get("question", "")
    if isinstance(question, (tuple, list)) and len(question) == 2:
        return question[0], question[1]
    return "", str(question)


def _extract_json(text: str) -> dict:
    """First balanced {...} object in the model output, tolerant of code fences
    and surrounding prose. Braces inside strings are ignored."""
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
    "You interpret a user query for graph retrieval. Work in two steps. "
    'STEP 1: write "description" — a concise, self-contained 1-3 sentence statement of the '
    "underlying information need (what the user actually wants to find, including implied entities/scope), "
    "in plain declarative prose, not a restatement of the question. "
    'STEP 2: derive "tags" FROM that description — specific noun phrases, named entities, systems, or actions. '
    "No generic filler words. "
    'STEP 3: extract "gate" — hard structured constraints ONLY when the query explicitly names them, else null/[]. '
    'Fields: product (a "*Force"/"*Genie"-style product name if named), '
    f"section (one of: {', '.join(GATE_SECTIONS)} — map synonyms, e.g. \"pull requests\"->prs, \"chat\"->slack), "
    'channel (a Slack channel name if given), employee_id (an "eid_..." id if given), '
    "years (array of 4-digit years explicitly mentioned). "
    "Do NOT guess values that are not in the query. "
    'Return ONLY valid JSON: {"description":"...","tags":["tag1"],'
    '"gate":{"product":null,"section":null,"channel":null,"employee_id":null,"years":[]}}.'
)

_PASS2_SYSTEM = (
    "Score retrieval tags against five facets (each 0.0-1.0). "
    "topic: subject matter. entities: named people/orgs/products/systems. "
    "activity: events/processes/actions. temporal: time relevance. evidence: answer material type. "
    'Return ONLY valid JSON: {"scores":[{"t":"tag","facets":{"topic":0.0,"entities":0.0,"activity":0.0,"temporal":0.0,"evidence":0.0}}]}'
)


def _chat_json(model: str, system: str, user: str, max_tokens: int) -> tuple:
    """One JSON turn on the shared model -> (parsed_json, tokens, time_s).
    Deterministic, non-thinking, min_tokens=1 (Qwen otherwise emits end-of-turn
    first and returns empty content). The prompt pins the shape and the content is
    parsed tolerantly (`_extract_json`) — the same prompt-and-parse approach the
    RAGAS judge uses, not guided structured output. Fails loud and legibly on an
    empty or length-truncated response rather than as an opaque parse error."""
    t0 = time.perf_counter()
    resp = nim.post("/chat/completions", {
        "model": model,
        "temperature": 0,
        "chat_template_kwargs": {"enable_thinking": False},
        "max_tokens": max_tokens,
        "min_tokens": 1,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    })
    elapsed = time.perf_counter() - t0
    tokens = int((resp.get("usage") or {}).get("total_tokens", 0) or 0)
    choices = resp.get("choices") or []
    finish = choices[0].get("finish_reason") if choices else "no choices"
    content = (choices[0].get("message") or {}).get("content") if choices else None
    if not content:
        raise RuntimeError(f"interpreter returned empty content (finish_reason={finish})")
    if finish == "length":
        raise RuntimeError(
            f"interpreter truncated at max_tokens={max_tokens} (finish_reason=length) — raise the budget")
    return _extract_json(content), tokens, elapsed


def _clean_tag(raw: str) -> str:
    return re.sub(r"^_+|_+$", "", re.sub(r"[^a-z0-9]+", "_", raw.lower()))


def _compute_w_query(facets: dict) -> float:
    """Tag weight from its facet vector: RMS strength scaled by a coverage bonus
    (a tag spread across facets weighs more than a one-facet spike of equal RMS)."""
    vals = [float(facets.get(f, 0.0)) for f in ALL_FACETS]
    n = len(vals)
    s = sum(vals)
    s2 = sum(v * v for v in vals)
    if s2 == 0:
        return 0.0
    strength = (s2 / n) ** 0.5
    coverage = ((s * s) / (n * s2)) ** COVERAGE_ALPHA
    return round(strength * coverage, 2)


def _parse_gate(raw) -> dict:
    """Normalise the model's loose gate into the strict shape retrieval gates on:
    string-or-null fields, a section restricted to the known set, 4-digit years."""
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
        "section": section if section in GATE_SECTIONS else None,
        "channel": s(g.get("channel")),
        "employee_id": s(g.get("employee_id")),
        "years": years,
    }


def _interpret(text: str, model: str) -> tuple:
    """interpret a question -> (plan, calls, tokens, time_s). plan = {description,
    tags:[{t, facets, w_query}], gate}. Two passes; pass 2 is skipped when pass 1
    yields no usable tags (retrieval then fails loud for that question)."""
    p1, tok1, t1 = _chat_json(model, _PASS1_SYSTEM, f"User query: {text}", 512)
    gate = _parse_gate(p1.get("gate"))
    description = p1.get("description") or text
    raw_tags, seen = [], set()
    for raw in (p1.get("tags") or []):
        t = _clean_tag(str(raw))
        if len(t) > 1 and t not in FILLER and t not in seen:
            seen.add(t)
            raw_tags.append(t)

    if not raw_tags:
        return ({"description": description, "tags": [], "gate": gate}, 1, tok1, t1)

    p2, tok2, t2 = _chat_json(
        model, _PASS2_SYSTEM,
        f"Original query: {text}\n\nScore these tags:\n{json.dumps(raw_tags)}", 1024)
    score_map = {row.get("t"): (row.get("facets") or {})
                 for row in (p2.get("scores") or [])}
    default = {f: 0.2 for f in ALL_FACETS}
    tags = []
    for t in raw_tags:
        facets = {f: float(score_map.get(t, default).get(f, 0.2)) for f in ALL_FACETS}
        tags.append({"t": t, "facets": facets, "w_query": _compute_w_query(facets)})
    return ({"description": description, "tags": tags, "gate": gate},
            2, tok1 + tok2, t1 + t2)


# --- ground (embed description + bare tag names, kNN the tag index) -----------

def _facet_cols(facets: dict) -> dict:
    return {f: float(facets.get(f, 0.0)) for f in ALL_FACETS}


def _ground(session, plan: dict) -> tuple:
    """One embed call (query side) for the pass-1 description + the prompt tag
    names, bare. Each prompt tag kNNs the `tag_emb` index for its GROUNDING_K
    nearest corpus tags (above MIN_SIM). Returns (queryTags param list the score
    Cypher unwinds, the description vector for the desc_emb channel, embed
    ModelUsage). One param per grounded corpus tag: the grounding cosine as
    `sim` plus the prompt tag's full facet vector + w_query — the score Cypher
    matches the vectors against the edge's facet arrays; facets are never
    embedded and never fanned out."""
    tags = plan["tags"]
    qmat, calls, tokens, secs = _embed(
        [plan["description"]] + [_readable(qt["t"]) for qt in tags], "query")
    desc_vec = [float(x) for x in qmat[0]]

    params = []
    for i, qt in enumerate(tags):
        cols = _facet_cols(qt["facets"])
        res = session.run(_GROUND_CYPHER, idx=GROUND_INDEX, k=GROUNDING_K,
                          vec=[float(x) for x in qmat[i + 1]])
        for rec in res:
            name, sim = rec["name"], rec["sim"]
            if not name or sim is None or sim < MIN_SIM:
                continue
            params.append({"name": name, "sim": float(sim), "promptIndex": i,
                           "w_query": qt["w_query"], **cols})
    return params, desc_vec, ModelUsage(calls, tokens, secs)


# --- score (weighted overlap over the grounded tags) --------------------------

def _run_desc_channel(session, desc_vec: list, gate_clause: str, gate_params: dict,
                      k: int) -> list:
    cypher = _DESC_CYPHER.format(gate=gate_clause)
    res = session.run(cypher, descVec=desc_vec, datasetId=DATASET_ID,
                      minRelevanceToFile=MIN_RELEVANCE_TO_FILE,
                      excludedSections=list(EXCLUDED_SECTIONS), limit=k, **gate_params)
    return [dict(rec) for rec in res]


def _retrieve(session, plan: dict, k: int) -> tuple:
    """interpret-plan -> (pointer rows best-first, ground embed ModelUsage). Each
    row carries {chunkId, locator, relpath, sha256, score} — references only; the
    caller resolves text from raw.

    The two semantic channels in order: tag scoring (× description agreement)
    when the prompt's tags grip the candidates; the description channel alone
    when they don't — attribute/aggregate questions whose tags name the question's
    form rather than any chunk's content still rank the gated candidates by
    description agreement (logged, never silent). Fails loud only when the gate
    itself matches nothing."""
    gate_clause, gate_params = _gate_clause(plan["gate"])

    if not plan["tags"]:
        raise RuntimeError("interpreter produced no usable tags — no tag path for this question")

    params, desc_vec, ground_usage = _ground(session, plan)
    if params:
        cypher = _SCORE_CYPHER.format(gate=gate_clause)
        res = session.run(cypher, queryTags=params, descVec=desc_vec,
                          datasetId=DATASET_ID, runId=RUN_ID, minWChunk=MIN_W_CHUNK,
                          minRelevanceToFile=MIN_RELEVANCE_TO_FILE,
                          excludedSections=list(EXCLUDED_SECTIONS), limit=k, **gate_params)
        rows = [dict(rec) for rec in res]
        if rows:
            return rows, ground_usage
        log.warning("tag channel scored no chunks (gate=%s) — description channel carries",
                    plan["gate"])
    else:
        log.warning("prompt tags grounded onto nothing — description channel carries")

    rows = _run_desc_channel(session, desc_vec, gate_clause, gate_params, k)
    if not rows:
        raise RuntimeError(
            f"no chunks match the gate at all (gate={plan['gate']}) — nothing to retrieve")
    return rows, ground_usage


# --- resolve (pointers -> raw text + artifact ids) -----------------------------

def _load_verified_doc(relpath: str, sha256: str, cache: dict):
    """Read + hash-verify + parse one raw file, memoized in `cache` so k chunks
    into the same file cost one read per question. A drifted file is refused,
    never served — the graph's pointers are only valid against the bytes they
    were built from."""
    key = (relpath, sha256)
    doc = cache.get(key)
    if doc is not None:
        return doc
    data = (RAW_ROOT / relpath).read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != sha256:
        raise RuntimeError(
            f"HASH MISMATCH for {relpath}: graph built against {sha256[:12]}…, "
            f"on-disk is {actual[:12]}…. Refusing to serve drifted content.")
    doc = json.loads(data.decode("utf-8"))
    cache[key] = doc
    return doc


def _nth_entry(root, i: int):
    """Record i of a metadata file: a list root indexes directly; a dict root
    (the employee directory, keyed by eid) takes the i-th entry in file order,
    kept as {key: value} so the id stays visible in the rendered text."""
    if isinstance(root, list):
        return root[i]
    k, v = list(root.items())[i]
    return {k: v}


def _resolve_chunk(row: dict, cache: dict) -> tuple:
    """One retrieved pointer row -> (chunk text, [artifact ids]). The locator is
    self-describing: `metadata` rows resolve into the metadata file (directories /
    org tree — no artifact ids there); product rows resolve `doc[section]` by
    index/indices, or slice one field by char_range for part chunks. Records
    render as compact JSON; ids come off the raw records, deduped in rank order.
    Any dangling pointer (bad index, missing field) raises — never a silent skip."""
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
    if "char_range" in loc:  # a part chunk: one slice of one field of one record
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


# --- answer -------------------------------------------------------------------

def _unpack_generation(result, elapsed_s: float) -> tuple:
    """Normalise the shared generator's return into (answer, calls, tokens,
    time_s) — mirrors the other arms so the one generator unpacks identically."""
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], dict):
        answer, tel = result
        return (answer, int(tel.get("calls", 1)), int(tel.get("tokens", 0)),
                float(tel.get("time", elapsed_s)))
    if hasattr(result, "answer"):
        return (result.answer, int(getattr(result, "calls", 1)),
                int(getattr(result, "tokens", 0)), float(getattr(result, "time", elapsed_s)))
    return str(result), 1, 0, elapsed_s


def answer_one_question(question, prepared: Prepared, generate: Optional[Generator],
                        k: int = 50) -> ArmOutput:
    """ENTRY: interpret -> ground -> score -> top-k chunk text -> generate ->
    ArmOutput. `generate` is the SHARED generator injected by the orchestrator so
    generation is identical across arms; None (retrieval-only smoke) leaves the
    answer empty."""
    _, text = _qid_text(question)

    t0 = time.perf_counter()
    plan, interp_calls, interp_tokens, interp_time = _interpret(text, INTERPRET_MODEL)
    with prepared.driver.session(database=DATABASE) as session:
        rows, ground_usage = _retrieve(session, plan, k)
    retrieve_wall = time.perf_counter() - t0

    # Resolve each pointer row from raw (hash-verified, one read per file per
    # question). context_ids land in the gold-citation id space, rank-ordered.
    doc_cache: dict = {}
    contexts: list[str] = []
    context_ids: list[str] = []
    seen: set[str] = set()
    for row in rows:
        chunk_text, ids = _resolve_chunk(row, doc_cache)
        contexts.append(chunk_text)
        for aid in ids:
            if aid not in seen:
                seen.add(aid)
                context_ids.append(aid)

    # search_time_s = the in-process Neo4j combinator only. The interpreter and the
    # grounding embed are NIM walls, carried in `retrieval`, so subtracting both
    # keeps this comparable to the other arms' search time.
    search_time_s = max(0.0, retrieve_wall - interp_time - ground_usage.time_s)
    retrieval_usage = ModelUsage(
        calls=interp_calls + ground_usage.calls,
        tokens=interp_tokens + ground_usage.tokens,
        time_s=interp_time + ground_usage.time_s)

    if generate is None:
        answer, gen = "", ModelUsage()
    else:
        g0 = time.perf_counter()
        result = generate(text, contexts)
        answer, gc, gt, gs = _unpack_generation(result, time.perf_counter() - g0)
        gen = ModelUsage(gc, gt, gs)

    return ArmOutput(
        answer=answer,
        contexts=contexts,
        context_ids=context_ids,
        search_time_s=search_time_s,
        generator=gen,
        retrieval=retrieval_usage,
    )

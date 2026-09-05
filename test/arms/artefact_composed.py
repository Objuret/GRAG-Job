from __future__ import annotations

print("artefact_composed: one score per chunk — base x (1 + tag weight), each "
      "part choosing its own tags; loading numpy, scipy and the shared graph "
      "plumbing …", flush=True)

import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from harness import nim
from harness.contract import ArmOutput, BuildStats, ModelUsage, unpack_generation
from arms.artefact_v2 import (
    ABS_REF_CACHE_DIR, ALL_FACETS, DATABASE, DATASET_ID, DESC_INDEX,
    FRESH_INTERP, GROUND_INDEX, INTERPRET_MODEL, K_LEVELS, KNN_OVERFETCH,
    NEUTRAL_FACETS, NO_REVIEW, RAW_QUESTION, RUN_ID, _DESC_POOL_MATCH,
    _EXCLUDED_PARAM, _GROUND_CYPHER, _TAG_POOL_MATCH, _absolute,
    _budget_contexts, _driver, _embed_cached, _env_float, _interpret_cached,
    _level_chain, _median_nn_dist, _mod, _qid_text, _readable, _resolve_chunk,
    _sufficient_cut, _unit,
)
from harness.embed import EMBED_MODEL
from harness.progress import progress


STR_MODIFIER = _env_float("HERB_STR_MODIFIER", 1.0)
if STR_MODIFIER < 0.0:
    raise ValueError(
        f"HERB_STR_MODIFIER must be >= 0.0, got {STR_MODIFIER!r} — a negative "
        f"strength would push down the chunks the query's own tags reached, and "
        f"0 is where the modifier switches off")

DIVIDE_FLOOR = 1e-6

RANK_SCORE_DP = 12

RETRIEVAL_FLAGS = {
    "HERB_STR_MODIFIER": STR_MODIFIER,
    "HERB_RAW_QUESTION": RAW_QUESTION,
    "HERB_FRESH_INTERP": FRESH_INTERP,
    "HERB_NO_REVIEW": NO_REVIEW,
    "ref_dist": None,
}


_TAG_CHUNKS_CYPHER = """
UNWIND $tags AS qt
MATCH (t:Tag {name: qt.name})<-[r:HAS_TAG]-(c:Chunk)<-[:HAS_CHUNK]-(f:File)
WHERE coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND r.run_id = $runId
  AND NOT (coalesce(c.section, "") IN $excludedSections)
WITH c, f, qt.name AS name, qt.part AS part, qt.weight AS weight,
     reduce(dot = 0.0, fi IN range(0, size(r.facets) - 1) |
       dot + (CASE r.facets[fi]
                WHEN 'topic'    THEN qt.topic
                WHEN 'entities' THEN qt.entities
                WHEN 'activity' THEN qt.activity
                WHEN 'temporal' THEN qt.temporal
                WHEN 'evidence' THEN qt.evidence
              END) * r.w_facets[fi]) AS relevance
WITH c, f, name, part, relevance, weight * relevance AS value
ORDER BY value DESC, relevance DESC, name, part
WITH c, f, collect({tag: name, part: part, relevance: relevance,
                    value: value})[0] AS best
RETURN c.chunk_id AS chunkId, c.locator_json AS locator,
       f.rel_path AS relpath, f.sha256 AS sha256,
       best.tag AS tag, best.part AS part, best.relevance AS relevance,
       best.value AS weight
"""

_DESC_CANDIDATES_CYPHER = """
CALL db.index.vector.queryNodes($idx, $fetch, $vec) YIELD node AS c, score AS sim
MATCH (f:File)-[:HAS_CHUNK]->(c)
WHERE coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND NOT (coalesce(c.section, "") IN $excludedSections)
RETURN c.chunk_id AS chunkId, c.locator_json AS locator,
       f.rel_path AS relpath, f.sha256 AS sha256, sim
ORDER BY sim DESC, chunkId
LIMIT $k
"""

_TAG_RELEVANCE_CYPHER = """
UNWIND $names AS qn
MATCH (t:Tag {name: qn})<-[r:HAS_TAG]-(c:Chunk)<-[:HAS_CHUNK]-(f:File)
WHERE coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND r.run_id = $runId
  AND NOT (coalesce(c.section, "") IN $excludedSections)
WITH qn, reduce(dot = 0.0, fi IN range(0, size(r.facets) - 1) |
       dot + (CASE r.facets[fi]
                WHEN 'topic'    THEN $topic
                WHEN 'entities' THEN $entities
                WHEN 'activity' THEN $activity
                WHEN 'temporal' THEN $temporal
                WHEN 'evidence' THEN $evidence
              END) * r.w_facets[fi]) AS relevance
RETURN qn AS name, max(relevance) AS relevance
"""

_BASE_SIM_CYPHER = """
UNWIND $chunkIds AS cid
MATCH (c:Chunk {chunk_id: cid})
RETURN cid AS chunkId, vector.similarity.cosine(c.desc_emb, $vec) AS sim
"""


def _ref_key() -> str:
    h = hashlib.sha256()
    for field in (DATABASE, RUN_ID, DATASET_ID, "within-space"):
        b = field.encode("utf-8")
        h.update(len(b).to_bytes(8, "big"))
        h.update(b)
    return h.hexdigest()


def _within_space_refs(session) -> dict:
    pools = {
        GROUND_INDEX: (_TAG_POOL_MATCH, "t.emb", {"runId": RUN_ID}),
        DESC_INDEX: (_DESC_POOL_MATCH, "c.desc_emb",
                     {"datasetId": DATASET_ID,
                      "excludedSections": _EXCLUDED_PARAM}),
    }
    counts = {space: session.run(match + "RETURN count(*) AS n",
                                 **params).single()["n"]
              for space, (match, _, params) in pools.items()}
    path = ABS_REF_CACHE_DIR / f"{_ref_key()}.json"
    if path.is_file():
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            entry = None
        if isinstance(entry, dict) and all(
                isinstance(entry.get(space), dict)
                and entry[space].get("n") == counts[space]
                and isinstance(entry[space].get("median_nn_dist_within_retrieval"),
                               float)
                for space in pools):
            return {space: entry[space]["median_nn_dist_within_retrieval"]
                    for space in pools}
    print("artefact_composed: measuring the within-space references — one "
          "nearest-neighbor pass per space, cached per graph …", flush=True)
    dists = {}
    for space, (match, column, params) in pools.items():
        embs = _unit(np.asarray(
            [r["emb"] for r in session.run(match + f"RETURN {column} AS emb",
                                           **params)],
            dtype=np.float64))
        if len(embs) != counts[space]:
            raise RuntimeError(
                f"{space} returned {len(embs)} embeddings against a count of "
                f"{counts[space]} — the graph changed under the measurement")
        dists[space] = _median_nn_dist(embs, space) / 2.0
    entry = {space: {"n": counts[space],
                     "median_nn_dist_within_retrieval": dists[space]}
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


def _parts(plan: dict, question: str) -> list:
    parts = [{"source": "description", "text": plan["description"],
              "facets": dict(NEUTRAL_FACETS)}]
    for part in plan["parts"]:
        parts.append({"source": "part", "text": _readable(part["t"]),
                      "facets": _part_facets(part)})
    if RAW_QUESTION:
        parts.append({"source": "question", "text": question,
                      "facets": dict(NEUTRAL_FACETS)})
    return parts


def _part_facets(part: dict) -> dict:
    facets = part.get("facets")
    if isinstance(facets, dict):
        profile = {f: float(facets.get(f, 0.0)) for f in ALL_FACETS}
        if sum(profile.values()) > 0.0:
            return profile
    return dict(NEUTRAL_FACETS)


def _tag_pool(session, vec) -> tuple:
    found: dict = {}
    for rec in session.run(_GROUND_CYPHER, idx=GROUND_INDEX, k=K_LEVELS[-1],
                           fetch=KNN_OVERFETCH * K_LEVELS[-1], runId=RUN_ID,
                           vec=[float(x) for x in vec]):
        if not rec["name"] or rec["sim"] is None or rec["emb"] is None:
            continue
        found[rec["name"]] = (1.0 - float(rec["sim"]), rec["emb"])
    if not found:
        raise RuntimeError(
            f"a part reached no tag in {DATABASE!r} — is {GROUND_INDEX} empty?")
    names = sorted(found)
    embs = _unit(np.asarray([found[n][1] for n in names], dtype=np.float64))
    return names, embs, np.array([found[n][0] for n in names])


def _tag_relevance(session, names: list, phi: np.ndarray) -> np.ndarray:
    at = {n: i for i, n in enumerate(names)}
    relevance = np.zeros(len(names))
    for rec in session.run(_TAG_RELEVANCE_CYPHER, names=names, runId=RUN_ID,
                           datasetId=DATASET_ID,
                           excludedSections=_EXCLUDED_PARAM,
                           **{f: float(phi[j])
                              for j, f in enumerate(ALL_FACETS)}):
        relevance[at[rec["name"]]] = float(rec["relevance"])
    return relevance


def _profile(facets: dict) -> np.ndarray:
    phi = np.array([float(facets.get(f, 0.0)) for f in ALL_FACETS])
    total = phi.sum()
    if total <= 0.0:
        return np.full(len(ALL_FACETS), 1.0 / len(ALL_FACETS))
    return phi / total


def _spread(values) -> dict:
    ordered = sorted(float(v) for v in values)
    if not ordered:
        return {"n": 0}
    return {"n": len(ordered), "min": round(ordered[0], 4),
            "median": round(ordered[len(ordered) // 2], 4),
            "max": round(ordered[-1], 4)}


def tag_weights(names: list, embs: np.ndarray, dists: np.ndarray,
                ref_dist: float, relevance: np.ndarray) -> tuple:
    support = 1.0 / np.maximum(dists, DIVIDE_FLOOR) ** 2
    tag_ref = 1.0 / ref_dist ** 2
    weighted_support = support * relevance
    if not weighted_support.any():
        raise RuntimeError(
            f"every tag in the part's pool of {len(names)} is worth zero to it "
            f"— the part's facet weights meet nothing on any of the pool's "
            f"edges, and there is nothing to anchor on")
    anchor = int(np.argmax(weighted_support))
    heights = np.empty(len(names))
    for height, added in _level_chain(embs, anchor):
        heights[added] = height / 2.0
    centrality = np.array(
        [_absolute(1.0 / max(h, DIVIDE_FLOOR) ** 2, tag_ref) for h in heights])
    weights = centrality * relevance
    meta = {"pool": len(names), "anchor": names[anchor],
            "relevance": _spread(relevance),
            "height": _spread(heights),
            "centrality": _spread(centrality),
            "weight": _spread(weights)}
    return weights, meta


def _divergence(blocks: list) -> dict:
    weight_of: dict = {}
    for block in blocks:
        for name, weight in zip(block["tags"], block["weights"]):
            weight_of.setdefault(name, []).append(weight)
    shared = [w for w in weight_of.values() if len(w) > 1]
    profiles = [np.array([b["profile"][f] for f in ALL_FACETS]) for b in blocks]
    gap = max((float(np.abs(a - b).sum())
               for i, a in enumerate(profiles) for b in profiles[i + 1:]),
              default=0.0)
    return {"parts": len(blocks),
            "anchors": len({b["anchor"] for b in blocks}),
            "tags": {"distinct": len(weight_of),
                     "reached": sum(len(b["tags"]) for b in blocks),
                     "shared": len(shared)},
            "shared_weight": _spread(max(w) - min(w) for w in shared),
            "profile_gap": round(gap, 4)}


def _base(dist: float, ref_dist: float) -> float:
    return _absolute(1.0 / max(dist, DIVIDE_FLOOR) ** 2, 1.0 / ref_dist ** 2)


def _modifier(weight: float) -> float:
    return _mod(1.0 + weight, STR_MODIFIER)


def _pointer(row: dict) -> dict:
    return {f: row[f] for f in ("chunkId", "locator", "relpath", "sha256")}


def _retrieve(session, plan: dict, k: int, question: str,
              keep_all: bool = False,
              ref_dist: Optional[dict] = None) -> tuple:
    if k <= 0:
        raise ValueError("k must be positive")
    if ref_dist is None:
        raise RuntimeError(
            "no reference distances are loaded — `prepare_over_corpus` fills "
            "Prepared.ref_dist from the graph's own geometry, and both the base "
            "and the tag weights saturate against it.")
    if RAW_QUESTION and not question.strip():
        raise ValueError(
            "HERB_RAW_QUESTION is on and the question text is empty — the raw "
            "probe has nothing to embed")

    parts = _parts(plan, question)
    qmat, calls, tok_in, tok_out, secs = _embed_cached(
        [p["text"] for p in parts], "query")
    usage = ModelUsage(calls=calls, tokens_in=tok_in, tokens_out=tok_out,
                       time_s=secs)
    vecs = [_unit(np.asarray([float(x) for x in row], dtype=np.float64))
            for row in qmat]
    need_vec = vecs[0]

    tag_rows: list = []
    blocks: list = []
    for index, (part, vec) in enumerate(zip(parts, vecs)):
        names, embs, dists = _tag_pool(session, vec)
        phi = _profile(part["facets"])
        weights, block = tag_weights(names, embs, dists, ref_dist[GROUND_INDEX],
                                     _tag_relevance(session, names, phi))
        facets = {f: float(phi[j]) for j, f in enumerate(ALL_FACETS)}
        tag_rows.extend({"name": name, "weight": float(weight), "part": index,
                         **facets}
                        for name, weight in zip(names, weights))
        selected = sorted(zip(names, (float(w) for w in weights)),
                          key=lambda nw: (-nw[1], nw[0]))
        block["source"] = part["source"]
        block["profile"] = {f: round(v, 4) for f, v in facets.items()}
        block["tags"] = [name for name, _ in selected]
        block["weights"] = [round(weight, 4) for _, weight in selected]
        blocks.append(block)

    payload: dict = {}
    tag_weight: dict = {}
    best_edge: dict = {}
    for rec in session.run(_TAG_CHUNKS_CYPHER, tags=tag_rows,
                           datasetId=DATASET_ID, runId=RUN_ID,
                           excludedSections=_EXCLUDED_PARAM):
        row = dict(rec)
        payload.setdefault(row["chunkId"], _pointer(row))
        tag_weight[row["chunkId"]] = float(row["weight"])
        best_edge[row["chunkId"]] = (row["tag"], int(row["part"]),
                                     float(row["relevance"]))
    tag_reached = len(payload)

    for vec in vecs:
        for rec in session.run(_DESC_CANDIDATES_CYPHER, idx=DESC_INDEX,
                               k=K_LEVELS[-1],
                               fetch=KNN_OVERFETCH * K_LEVELS[-1],
                               vec=[float(x) for x in vec],
                               datasetId=DATASET_ID,
                               excludedSections=_EXCLUDED_PARAM):
            row = dict(rec)
            payload.setdefault(row["chunkId"], _pointer(row))
    if not payload:
        raise RuntimeError("neither reach produced a candidate chunk")

    candidates = sorted(payload)
    ref = ref_dist[DESC_INDEX]
    totals: dict = {}
    bases: dict = {}
    for rec in session.run(_BASE_SIM_CYPHER, chunkIds=candidates,
                           vec=[float(x) for x in need_vec]):
        if rec["sim"] is None:
            raise RuntimeError(
                f"chunk {rec['chunkId']!r} carries no description embedding — "
                f"the base is its distance to the need and there is none")
        base = _base(1.0 - float(rec["sim"]), ref)
        bases[rec["chunkId"]] = base
        totals[rec["chunkId"]] = base * _modifier(
            tag_weight.get(rec["chunkId"], 0.0))
    if len(totals) != len(candidates):
        raise RuntimeError(
            f"{len(candidates)} candidate(s) went in and {len(totals)} came back "
            f"scored — the graph changed under the query")

    ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    ranking = {"chunk_ids": [cid for cid, _ in ranked],
               "scores": [round(sc, RANK_SCORE_DP) for _, sc in ranked]}
    if not keep_all:
        ranked = ranked[:k]
    rows = [{**payload[cid], "score": round(sc, 4)} for cid, sc in ranked]

    spread = sorted(bases.values())
    factors = sorted(_modifier(tag_weight.get(cid, 0.0)) for cid in candidates)
    per_tag: dict = {}
    won = [0] * len(parts)
    for tag, index, edge_relevance in best_edge.values():
        per_tag.setdefault(tag, []).append(edge_relevance)
        won[index] += 1
    shared = [v for v in per_tag.values() if len(v) > 1]
    meta = {
        "plan": {key: val for key, val in plan.items() if not key.startswith("_")},
        "parts": blocks,
        "divergence": _divergence(blocks),
        "candidates": {"tag": tag_reached, "pool": len(candidates),
                       "modified": len(tag_weight)},
        "ref_dist": dict(ref_dist),
        "base": {"min": round(spread[0], 4),
                 "median": round(spread[len(spread) // 2], 4),
                 "max": round(spread[-1], 4)},
        "per_edge": {
            "relevance": _spread(rel for _, _, rel in best_edge.values()),
            "by_part": won,
            "shared_tag": {"tags": len(shared),
                           "chunks": sum(len(v) for v in shared),
                           "spread": _spread(max(v) - min(v) for v in shared)},
        },
        "modifier": {"str": STR_MODIFIER,
                     "min": round(factors[0], 4),
                     "median": round(factors[len(factors) // 2], 4),
                     "max": round(factors[-1], 4)},
        "ranking": ranking,
        "retrieved": len(rows),
    }
    return rows, usage, meta


@dataclass
class Prepared:
    driver: object
    build_stats: Optional[BuildStats] = None
    ref_dist: Optional[dict] = None


def prepare_over_corpus(corpus) -> Prepared:
    t0 = time.perf_counter()
    print(f"artefact_composed: opening {DATABASE} …", flush=True)
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
            missing = sorted({GROUND_INDEX, DESC_INDEX} - set(present))
            if missing or no_desc:
                raise RuntimeError(
                    f"semantic layer incomplete in {DATABASE!r} (missing indexes: "
                    f"{missing or 'none'}, non-empty chunks without desc_emb: "
                    f"{no_desc}) — the tag pool, the description reach and the "
                    f"base all read that layer.")
            if multi:
                raise RuntimeError(
                    f"{multi} chunk(s) in {DATABASE!r} without exactly one File — "
                    f"pointer resolution would be ambiguous")
            shape = s.run(
                "MATCH (:Chunk)-[r:HAS_TAG]->(:Tag) WHERE r.run_id = $runId "
                "RETURN count(r) AS edges, sum(CASE WHEN size(r.facets) = "
                "size(r.w_facets) THEN 0 ELSE 1 END) AS unpaired, "
                "sum(CASE WHEN size([f IN $facets WHERE f IN r.facets]) = "
                "size($facets) AND size(r.facets) = size($facets) THEN 0 ELSE 1 "
                "END) AS partial, min(size(r.facets)) AS narrowest, "
                "max(size(r.facets)) AS widest",
                runId=RUN_ID, facets=list(ALL_FACETS)).single()
            axes = s.run(
                "MATCH (:Chunk)-[r:HAS_TAG]->(:Tag) WHERE r.run_id = $runId "
                "UNWIND r.facets AS facet RETURN collect(DISTINCT facet) AS axes",
                runId=RUN_ID).single()["axes"]
            unknown = sorted(set(axes) - set(ALL_FACETS))
            if shape["unpaired"] or unknown:
                raise RuntimeError(
                    f"the facet layer of run {RUN_ID!r} in {DATABASE!r} does not "
                    f"read per edge: {shape['unpaired']} of {shape['edges']} "
                    f"HAS_TAG edge(s) carry a `w_facets` array that does not pair "
                    f"with the `facets` array beside it, and the edges name "
                    f"{unknown or 'no'} axis/axes outside ALL_FACETS "
                    f"{list(ALL_FACETS)} — a part's facet weights multiply "
                    f"those values at the positions those names give.")
            if shape["partial"]:
                raise RuntimeError(
                    f"the facet layer of run {RUN_ID!r} in {DATABASE!r} names "
                    f"fewer than the {len(ALL_FACETS)} axes of ALL_FACETS "
                    f"{list(ALL_FACETS)} on {shape['partial']} of "
                    f"{shape['edges']} HAS_TAG edge(s), the run's edges naming "
                    f"{shape['narrowest']} to {shape['widest']} axes each — the "
                    f"arm values an edge by a part's profile against all "
                    f"five and cannot read a layer that names fewer: a dot over "
                    f"the axes one edge happens to carry scales with how many "
                    f"the tagger wrote instead of with what the tag is worth to "
                    f"that chunk.")
            ref_dist = _within_space_refs(s)
    except Exception:
        drv.close()
        raise
    print(f"artefact_composed: within-space references (retrieval units) — tag "
          f"median NN {ref_dist[GROUND_INDEX]:.4f} ({GROUND_INDEX}), chunk "
          f"description median NN {ref_dist[DESC_INDEX]:.4f} ({DESC_INDEX})",
          flush=True)
    RETRIEVAL_FLAGS["ref_dist"] = dict(ref_dist)
    return Prepared(
        driver=drv,
        build_stats=BuildStats(
            build_time_s=time.perf_counter() - t0,
            model=ModelUsage(),
            models=[EMBED_MODEL],
        ),
        ref_dist=ref_dist,
    )


def answer_one_question(question, prepared: Prepared, generate=None,
                        k: int = 50, char_budget: Optional[int] = None) -> ArmOutput:
    _, text = _qid_text(question)

    nim.reset_timing()
    t0 = time.perf_counter()
    plan, interp_calls, interp_in, interp_out, interp_time = _interpret_cached(
        text, INTERPRET_MODEL)
    with prepared.driver.session(database=DATABASE) as session:
        rows, ground_usage, meta = _retrieve(
            session, plan, k, text, keep_all=char_budget is not None,
            ref_dist=prepared.ref_dist)
    meta["interpreter"] = {"model": INTERPRET_MODEL, "backend": "claude-cli"}
    retrieve_wall = time.perf_counter() - t0

    doc_cache: dict = {}
    rev_calls = rev_in = rev_out = 0
    rev_time = 0.0
    if char_budget is not None:
        contexts, chunk_id_lists, context_ids, meta["char_budget"] = _budget_contexts(
            rows, char_budget, doc_cache)
        ids_through = meta["char_budget"]["kept"]
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
            kept, review_log, rev_calls, rev_in, rev_out, rev_time = _sufficient_cut(
                text, contexts)
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
        ids_through = len(contexts)
    meta["returned"] = len(contexts)
    meta["ranking"]["ids_through"] = ids_through
    meta["ranking"]["contexts_through"] = len(contexts)
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


_PROBES = (
    "What did the team decide about the release timeline in the planning channel?",
    "Which pull request changed the authentication flow, and who reviewed it?",
    "What is the roadmap?",
)


def _model_selfcheck() -> None:
    ref = 0.25
    assert abs(_base(ref, ref) - 0.5) < 1e-12
    assert _base(ref / 2, ref) > 0.5 > _base(ref * 2, ref)
    assert 0.0 < _base(1.0, ref) < _base(0.5, ref) < 1.0
    print(f"  base: d=ref -> {_base(ref, ref):.4f}, d=ref/2 -> "
          f"{_base(ref / 2, ref):.4f}, d=2*ref -> {_base(ref * 2, ref):.4f}",
          flush=True)

    assert _modifier(0.0) == 1.0
    assert abs(_modifier(1.0) - (1.0 + STR_MODIFIER)) < 1e-12
    print(f"  modifier: weight 0 -> {_modifier(0.0):.4f}, weight 1 -> "
          f"{_modifier(1.0):.4f} at HERB_STR_MODIFIER={STR_MODIFIER}", flush=True)

    tagged = _base(ref, ref) * _modifier(0.8)
    untagged = _base(ref, ref) * _modifier(0.0)
    assert tagged > untagged
    print(f"  one chunk at the reference distance: tagged {tagged:.4f} vs "
          f"untagged {untagged:.4f}", flush=True)

    assert abs(_profile(NEUTRAL_FACETS).sum() - 1.0) < 1e-12
    assert (_profile({f: 0.0 for f in ALL_FACETS}) == 0.2).all()
    one = _profile({f: (3.0 if f == "temporal" else 0.0) for f in ALL_FACETS})
    assert one[ALL_FACETS.index("temporal")] == 1.0
    assert _part_facets({"t": "x"}) == NEUTRAL_FACETS
    assert _part_facets({"t": "x", "facets": {f: 0.0 for f in ALL_FACETS}}) \
        == NEUTRAL_FACETS
    sharp = {f: (0.9 if f == "entities" else 0.1) for f in ALL_FACETS}
    assert _part_facets({"t": "x", "facets": sharp}) == sharp
    print(f"  part profile: a no-claim part -> {_profile(NEUTRAL_FACETS)[0]:.4f} "
          f"per axis, a single-axis part -> {one[ALL_FACETS.index('temporal')]:.4f} "
          f"on temporal", flush=True)

    rng = np.random.default_rng(20260827)
    embs = _unit(rng.normal(size=(24, 16)))
    names = [f"t{i}" for i in range(24)]
    dists = np.full(24, 0.2)
    dists[7] = 0.15
    flat = np.full(24, 0.5)
    weights, block = tag_weights(names, embs, dists, ref, flat)
    assert weights.shape == (24,)
    assert weights.min() >= 0.0 and weights.max() <= 1.0
    assert block["anchor"] == "t7"
    assert abs(weights[7] - 0.5) < 1e-9
    print(f"  flat relevance: pool {block['pool']}, anchor {block['anchor']!r} — "
          f"the nearest tag, no tag worth more to the part than another; "
          f"centrality {block['centrality']['min']}-{block['centrality']['max']}, "
          f"weight {block['weight']['min']}-{block['weight']['max']}", flush=True)

    raised = flat.copy()
    raised[19] = 1.0
    only, only_block = tag_weights(names, embs, dists, ref, raised)
    assert only_block["anchor"] == "t19"
    assert abs(only[19] - 1.0) < 1e-9
    assert only[7] < 1.0
    print(f"  one tag twice as relevant: anchor moves {block['anchor']!r} -> "
          f"{only_block['anchor']!r} over a pool whose distances did not change; "
          f"t19 {weights[19]:.4f} -> {only[19]:.4f}, t7 {weights[7]:.4f} -> "
          f"{only[7]:.4f}", flush=True)

    damped = flat.copy()
    damped[3] = 0.1
    few, few_block = tag_weights(names, embs, dists, ref, damped)
    assert few_block["anchor"] == "t7"
    assert abs(few[3] - weights[3] * 0.2) < 1e-12
    assert all(abs(few[i] - weights[i]) < 1e-12 for i in range(24) if i != 3)
    print(f"  one tag a fifth as relevant: t3 {weights[3]:.4f} -> {few[3]:.4f} "
          f"with the anchor and every other weight unmoved", flush=True)

    tight, tight_block = tag_weights(names, embs, dists, ref / 8, flat)
    assert abs(tight.max() - weights.max()) < 1e-6
    assert (tight <= weights + 1e-12).all()
    print(f"  reference scale: ref {ref} -> median weight "
          f"{block['weight']['median']}, modifier "
          f"{_modifier(float(np.median(weights))):.4f}; ref {ref / 8} -> median "
          f"weight {tight_block['weight']['median']}, modifier "
          f"{_modifier(float(np.median(tight))):.4f}", flush=True)

    apart = _divergence([
        {"anchor": "a", "tags": ["x", "y"], "weights": [0.8, 0.2],
         "profile": {f: (1.0 if f == "entities" else 0.0) for f in ALL_FACETS}},
        {"anchor": "b", "tags": ["y", "z"], "weights": [0.9, 0.4],
         "profile": {f: (1.0 if f == "temporal" else 0.0) for f in ALL_FACETS}},
    ])
    assert apart["anchors"] == 2 and apart["tags"] == {"distinct": 3,
                                                       "reached": 4, "shared": 1}
    assert abs(apart["profile_gap"] - 2.0) < 1e-9
    assert abs(apart["shared_weight"]["max"] - 0.7) < 1e-9
    print(f"  divergence over two parts asking for disjoint axes: "
          f"{apart['anchors']} anchor(s), tags {apart['tags']}, profile gap "
          f"{apart['profile_gap']}, shared-tag weight spread "
          f"{apart['shared_weight']['max']}", flush=True)
    print("artefact_composed model self-check OK", flush=True)


def _selfcheck() -> None:
    _model_selfcheck()
    corpus = Path(__file__).resolve().parent.parent.parent / "data" / "corpus" / DATASET_ID
    prepared = prepare_over_corpus(corpus)
    try:
        for probe in progress(_PROBES, desc="probing", unit="q"):
            out = answer_one_question(("selfcheck", probe), prepared, None,
                                      char_budget=72000)
            meta = out.meta
            edge = meta["per_edge"]
            apart = meta["divergence"]
            print(f"\n  {probe}", flush=True)
            for index, block in enumerate(meta["parts"]):
                print(f"    part {index} {block['source']:<11s} anchor "
                      f"{block['anchor']!r} — pool {block['pool']}, relevance "
                      f"{block['relevance']['min']} to "
                      f"{block['relevance']['max']}, weight "
                      f"{block['weight']['min']} to {block['weight']['max']}, "
                      f"{edge['by_part'][index]} winning edge(s)", flush=True)
                print("                  profile " + "  ".join(
                    f"{f} {block['profile'][f]:.3f}" for f in ALL_FACETS),
                    flush=True)
            print(f"    divergence: {apart['parts']} part(s), {apart['anchors']} "
                  f"distinct anchor(s), tags {apart['tags']}, profile gap "
                  f"{apart['profile_gap']}, shared-tag weight spread "
                  f"{apart['shared_weight']}", flush=True)
            print(f"    winning-edge relevance: {edge['relevance']}", flush=True)
            print(f"    shared-tag separation: {edge['shared_tag']['tags']} tag(s) "
                  f"hold the winning edge for {edge['shared_tag']['chunks']} "
                  f"candidate(s), spread {edge['shared_tag']['spread']}",
                  flush=True)
            cand = meta["candidates"]
            print(f"    candidates: {cand['tag']} tag-reached, {cand['pool']} "
                  f"in the union, {cand['modified']} carrying a selected tag; "
                  f"base {meta['base']['min']} to {meta['base']['max']}, modifier "
                  f"{meta['modifier']['min']} to {meta['modifier']['max']}",
                  flush=True)
            print(f"    returned {meta['returned']} context(s), "
                  f"{len(out.context_ids)} artifact id(s), "
                  f"{sum(len(c) for c in out.contexts)} chars", flush=True)
            rank = meta["ranking"]
            budget = meta["char_budget"]
            print(f"    ranking: {len(rank['chunk_ids'])} rank(s) recorded, "
                  f"artifact ids through {rank['ids_through']}, context text "
                  f"through {rank['contexts_through']}, "
                  f"{len(json.dumps(rank, ensure_ascii=False))} chars of the "
                  f"record", flush=True)
            assert len(rank["chunk_ids"]) == len(rank["scores"]) == cand["pool"]
            assert len(set(rank["chunk_ids"])) == len(rank["chunk_ids"])
            assert all(a >= b for a, b in zip(rank["scores"], rank["scores"][1:]))
            assert rank["contexts_through"] == len(meta["chunk_ids"])
            assert rank["ids_through"] == budget["kept"]
            if budget["boundary"] is not None:
                assert rank["contexts_through"] == budget["kept"] + 1
                assert rank["chunk_ids"][budget["kept"]] == budget["boundary"]["id"]
            resorted = sorted(zip(rank["chunk_ids"], rank["scores"]),
                              key=lambda kv: (-kv[1], kv[0]))
            assert [cid for cid, _ in resorted] == rank["chunk_ids"]
            assert apart["parts"] == len(meta["parts"]) == len(edge["by_part"])
            assert sum(edge["by_part"]) == cand["modified"]
            for block in meta["parts"]:
                assert len(block["tags"]) == len(block["weights"]) == block["pool"]
                assert all(a >= b for a, b in zip(block["weights"],
                                                  block["weights"][1:]))
                assert 0.0 <= block["weight"]["min"] <= block["weight"]["max"] <= 1.0
                assert abs(sum(block["profile"].values()) - 1.0) < 1e-3
            if edge["relevance"]["n"]:
                assert (0.0 <= edge["relevance"]["min"]
                        <= edge["relevance"]["max"] <= 1.0)
            assert (1.0 <= meta["modifier"]["min"]
                    <= meta["modifier"]["max"] <= 1.0 + STR_MODIFIER)
            assert len(out.context_ids) == len(set(out.context_ids))
            assert len(meta["chunk_ids"]) == len(out.contexts)
            assert out.contexts, "a probe returned no context"
        print("\nartefact_composed self-check OK", flush=True)
    finally:
        prepared.driver.close()


if __name__ == "__main__":
    _selfcheck()

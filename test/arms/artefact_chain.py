from __future__ import annotations

print("artefact_chain: one score per chunk — the description's evidence and the "
      "evidence of every tag aiming at the chunk, each tag by its enrichment "
      "against the query's own distance null and each edge by the reaching "
      "part's facet weights; loading numpy, scipy and the shared graph "
      "plumbing …", flush=True)

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.special import logsumexp
from scipy.stats import t as student_t

from harness import nim
from harness.contract import ArmOutput, BuildStats, ModelUsage, unpack_generation
from arms.artefact_composed import (
    RANK_SCORE_DP, _PROBES, _parts, _pointer, _profile, _spread,
)
from arms.artefact_v2 import (
    ALL_FACETS, DATABASE, DATASET_ID, FRESH_INTERP, INTERPRET_MODEL,
    NEUTRAL_FACETS, RAW_QUESTION, RUN_ID, _DESC_POOL_MATCH, _EXCLUDED_PARAM,
    _TAG_POOL_MATCH, _budget_contexts, _driver, _embed_cached,
    _interpret_cached, _qid_text, _resolve_chunk, _unit,
)
from harness.embed import EMBED_MODEL
from harness.progress import progress


CHAIN_VARIANT = os.environ.get("HERB_CHAIN", "evidence")
if CHAIN_VARIANT not in ("evidence", "probability"):
    raise ValueError(
        f"HERB_CHAIN must be 'evidence' or 'probability', got {CHAIN_VARIANT!r}")

MADK = 1.4826

RETRIEVAL_FLAGS = {
    "HERB_CHAIN": CHAIN_VARIANT,
    "HERB_RAW_QUESTION": RAW_QUESTION,
    "HERB_FRESH_INTERP": FRESH_INTERP,
}


_TAGS_RETURN = "RETURN t.name AS name, t.emb AS emb"

_CHUNKS_RETURN = """
RETURN c.chunk_id AS chunkId, c.locator_json AS locator,
       f.rel_path AS relpath, f.sha256 AS sha256, c.desc_emb AS emb
"""

_NO_DESC_MATCH = """
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
WHERE coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND NOT (coalesce(c.section, "") IN $excludedSections)
  AND c.desc_emb IS NULL
"""

_EDGES_MATCH = _DESC_POOL_MATCH + """
MATCH (c)-[r:HAS_TAG]->(t:Tag)
WHERE r.run_id = $runId AND t.emb IS NOT NULL
"""
_EDGES_RETURN = """
RETURN c.chunk_id AS chunkId, t.name AS name, r.facets AS facets, r.w_facets AS w
"""


@dataclass
class Prepared:
    tag_names: list
    tag_emb: np.ndarray
    chunk_ids: list
    pointers: list
    desc_emb: np.ndarray
    edge_chunk: np.ndarray
    edge_tag: np.ndarray
    edge_w: np.ndarray
    chunk_degree: np.ndarray
    build_stats: Optional[BuildStats] = None


def _pull(session, match: str, returning: str, params: dict, desc: str,
          unit: str) -> list:
    total = session.run(match + "RETURN count(*) AS n", **params).single()["n"]
    rows = [dict(rec) for rec in progress(session.run(match + returning, **params),
                                          desc=desc, unit=unit, total=total)]
    if len(rows) != total:
        raise RuntimeError(
            f"{desc} returned {len(rows)} row(s) against a count of {total} — "
            f"the graph changed under the pull")
    return rows


def prepare_over_corpus(corpus) -> Prepared:
    t0 = time.perf_counter()
    print(f"artefact_chain: opening {DATABASE} …", flush=True)
    drv = _driver()
    try:
        with drv.session(database=DATABASE) as s:
            s.run("RETURN 1").consume()
            population = {"datasetId": DATASET_ID, "excludedSections": _EXCLUDED_PARAM}
            no_desc = s.run(_NO_DESC_MATCH + "RETURN count(*) AS n",
                            **population).single()["n"]
            if no_desc:
                raise RuntimeError(
                    f"{no_desc} non-empty chunk(s) of {DATASET_ID!r} outside the "
                    f"excluded sections carry no desc_emb in {DATABASE!r} — the "
                    f"chain scores every retrievable chunk on its description")
            tags = _pull(s, _TAG_POOL_MATCH, _TAGS_RETURN, {"runId": RUN_ID},
                         "tag layer", "tag")
            chunks = _pull(s, _DESC_POOL_MATCH, _CHUNKS_RETURN, population,
                           "chunk layer", "chunk")
            edges = _pull(s, _EDGES_MATCH, _EDGES_RETURN,
                          {**population, "runId": RUN_ID}, "facet layer", "edge")
    finally:
        drv.close()

    emb_of = {row["name"]: row["emb"] for row in tags}
    if len(emb_of) != len(tags):
        raise RuntimeError(
            f"{len(tags) - len(emb_of)} tag name(s) in {DATABASE!r} are not unique "
            f"— the chain addresses a tag by its name")
    tag_names = sorted(emb_of)
    tag_emb = _unit(np.asarray([emb_of[n] for n in tag_names], dtype=np.float32))

    pointer_of = {row["chunkId"]: row for row in chunks}
    if len(pointer_of) != len(chunks):
        raise RuntimeError(
            f"{len(chunks) - len(pointer_of)} chunk id(s) in {DATABASE!r} are not "
            f"unique — pointer resolution would be ambiguous")
    chunk_ids = sorted(pointer_of)
    pointers = [_pointer(pointer_of[cid]) for cid in chunk_ids]
    desc_emb = _unit(np.asarray([pointer_of[cid]["emb"] for cid in chunk_ids],
                                dtype=np.float32))

    tag_at = {n: i for i, n in enumerate(tag_names)}
    chunk_at = {cid: i for i, cid in enumerate(chunk_ids)}
    facet_at = {f: j for j, f in enumerate(ALL_FACETS)}
    edge_chunk = np.empty(len(edges), dtype=np.int64)
    edge_tag = np.empty(len(edges), dtype=np.int64)
    edge_w = np.empty((len(edges), len(ALL_FACETS)))
    for i, row in enumerate(progress(edges, desc="facet order", unit="edge")):
        if (sorted(row["facets"]) != sorted(ALL_FACETS)
                or len(row["w"]) != len(row["facets"])):
            raise RuntimeError(
                f"the HAS_TAG edge {row['chunkId']!r} -> {row['name']!r} of run "
                f"{RUN_ID!r} names {row['facets']} over {len(row['w'])} value(s) — "
                f"the chain reads all five of {list(ALL_FACETS)} on every edge")
        edge_chunk[i] = chunk_at[row["chunkId"]]
        edge_tag[i] = tag_at[row["name"]]
        for f, w in zip(row["facets"], row["w"]):
            edge_w[i, facet_at[f]] = float(w)
    order = np.lexsort((edge_tag, edge_chunk))
    edge_chunk, edge_tag, edge_w = edge_chunk[order], edge_tag[order], edge_w[order]
    pairs = edge_chunk * len(tag_names) + edge_tag
    if len(np.unique(pairs)) != len(pairs):
        raise RuntimeError(
            f"{len(pairs) - len(np.unique(pairs))} (chunk, tag) pair(s) carry more "
            f"than one HAS_TAG edge of run {RUN_ID!r} — the sum over a chunk's "
            f"edges would count a tag twice")
    chunk_degree = np.bincount(edge_chunk, minlength=len(chunk_ids))
    if not chunk_degree.all():
        raise RuntimeError(
            f"{int((chunk_degree == 0).sum())} retrievable chunk(s) in {DATABASE!r} "
            f"carry no HAS_TAG edge of run {RUN_ID!r} — every chunk's tag evidence "
            f"is a sum over its edges and would be zero")

    print(f"artefact_chain: {len(tag_names)} tags, {len(chunk_ids)} chunks, "
          f"{len(edge_chunk)} edges in memory; HERB_CHAIN={CHAIN_VARIANT}",
          flush=True)
    return Prepared(
        tag_names=tag_names, tag_emb=tag_emb,
        chunk_ids=chunk_ids, pointers=pointers, desc_emb=desc_emb,
        edge_chunk=edge_chunk, edge_tag=edge_tag, edge_w=edge_w,
        chunk_degree=chunk_degree,
        build_stats=BuildStats(
            build_time_s=time.perf_counter() - t0,
            model=ModelUsage(),
            models=[EMBED_MODEL],
        ),
    )


def _null(d: np.ndarray) -> tuple:
    mu = np.median(d)
    up = d[d > mu] - mu
    s = MADK * np.median(up) if up.size else 0.0
    if not s > 0.0:
        raise RuntimeError(
            "degenerate distance population: no spread above the median")
    return mu, s, up / s


def _enrichment(dmin: np.ndarray, nulls: list, nu: float, c: float) -> np.ndarray:
    n = len(dmin)
    order = np.argsort(dmin, kind="stable")
    rank = np.searchsorted(dmin[order], dmin, side="right")
    log_f0 = logsumexp(np.stack([student_t.logcdf((dmin - mu) / (c * s), nu)
                                 for mu, s in nulls]), axis=0)
    raw = (np.log(rank) - np.log(n) - log_f0)[order]
    ell = np.empty(n)
    ell[order] = np.maximum.accumulate(raw[::-1])[::-1]
    return np.maximum(ell, 0.0)


def _score(probes: np.ndarray, phi: np.ndarray, tag_emb: np.ndarray,
           desc_emb: np.ndarray, edge_chunk: np.ndarray, edge_tag: np.ndarray,
           edge_w: np.ndarray, variant: str) -> dict:
    dp = (1.0 - (probes @ tag_emb.T).astype(np.float64)) / 2.0
    nearest_part = dp.argmin(axis=0)
    d_star = dp.min(axis=0)
    nulls, standardised = [], []
    for p in range(dp.shape[0]):
        mu, s, u = _null(dp[p])
        nulls.append((mu, s))
        standardised.append(u)
    sym = np.concatenate(standardised)
    nu, _, c = student_t.fit(np.concatenate([sym, -sym]), floc=0.0)
    ell = _enrichment(d_star, nulls, nu, c)
    r_edge = (phi[nearest_part[edge_tag]] * edge_w).sum(axis=1)
    d_c = (1.0 - (desc_emb @ probes[0]).astype(np.float64)) / 2.0
    mu_c, s_c, u_c = _null(d_c)
    nu_c, _, c_c = student_t.fit(np.concatenate([u_c, -u_c]), floc=0.0)
    ell_c = _enrichment(d_c, [(mu_c, s_c)], nu_c, c_c)
    if variant == "evidence":
        tag_ev = np.bincount(edge_chunk, weights=r_edge * ell[edge_tag],
                             minlength=len(desc_emb))
        score = ell_c + tag_ev
    elif variant == "probability":
        w = -np.expm1(-ell)
        tag_ev = np.bincount(edge_chunk, weights=r_edge * w[edge_tag],
                             minlength=len(desc_emb))
        score = np.exp(ell_c) * tag_ev
    else:
        raise ValueError(f"unknown chain variant {variant!r}")
    return {"score": score, "base": ell_c, "tag_score": tag_ev, "ell": ell,
            "d_star": d_star, "d_c": d_c, "r_edge": r_edge,
            "nearest_part": nearest_part, "nu": float(nu), "nu_desc": float(nu_c)}


def _retrieve(prepared: Prepared, plan: dict, k: int, question: str,
              keep_all: bool = False) -> tuple:
    if k <= 0:
        raise ValueError("k must be positive")
    if RAW_QUESTION and not question.strip():
        raise ValueError(
            "HERB_RAW_QUESTION is on and the question text is empty — the raw "
            "probe has nothing to embed")

    parts = _parts(plan, question)
    qmat, calls, tok_in, tok_out, secs = _embed_cached(
        [p["text"] for p in parts], "query")
    usage = ModelUsage(calls=calls, tokens_in=tok_in, tokens_out=tok_out,
                       time_s=secs)
    probes = _unit(np.asarray(qmat, dtype=np.float32))
    phi = np.array([_profile(p["facets"]) for p in parts])

    chain = _score(probes, phi, prepared.tag_emb, prepared.desc_emb,
                   prepared.edge_chunk, prepared.edge_tag, prepared.edge_w,
                   CHAIN_VARIANT)
    ell, ell_c, tag_ev = chain["ell"], chain["base"], chain["tag_score"]
    if not (tag_ev > 0.0).any() and not (ell_c > 0.0).any():
        raise RuntimeError(
            "no chunk carries tag evidence and no chunk carries description "
            "evidence — every distance sits in the null's bulk and there is "
            "nothing to rank on")

    score = np.round(chain["score"], RANK_SCORE_DP)
    desc_dist = np.round(chain["d_c"], RANK_SCORE_DP)
    order = np.lexsort((np.arange(len(score)), desc_dist, -score))
    ranking = {"chunk_ids": [prepared.chunk_ids[i] for i in order],
               "scores": [float(score[i]) for i in order],
               "desc_dist": [float(desc_dist[i]) for i in order]}
    kept = order if keep_all else order[:k]
    rows = [prepared.pointers[i] for i in kept]

    meta = {
        "parts": [{"index": i, "source": p["source"],
                   "profile": {f: float(phi[i, j]) for j, f in enumerate(ALL_FACETS)}}
                  for i, p in enumerate(parts)],
        "n_parts": len(parts),
        "tag_evidence": {**_spread(ell),
                         "positive": int((ell > 0.0).sum()),
                         "over_3": int((ell > 3.0).sum())},
        "nu": chain["nu"],
        "nu_desc": chain["nu_desc"],
        "nearest_part": np.bincount(chain["nearest_part"],
                                    minlength=len(parts)).tolist(),
        "edge_relevance": _spread(chain["r_edge"]),
        "description_evidence": {**_spread(ell_c),
                                 "positive": int((ell_c > 0.0).sum())},
        "chunk_evidence": {
            **_spread(tag_ev),
            "zero": int((tag_ev == 0.0).sum()),
            "top_k": {"k": k, "tags_per_chunk_median":
                      float(np.median(prepared.chunk_degree[order[:k]]))}},
        "ranking": ranking,
        "retrieved": len(rows),
    }
    return rows, usage, meta


def answer_one_question(question, prepared: Prepared, generate=None,
                        k: int = 50, char_budget: Optional[int] = None) -> ArmOutput:
    _, text = _qid_text(question)

    nim.reset_timing()
    t0 = time.perf_counter()
    plan, interp_calls, interp_in, interp_out, interp_time = _interpret_cached(
        text, INTERPRET_MODEL)
    rows, embed_usage, meta = _retrieve(prepared, plan, k, text,
                                        keep_all=char_budget is not None)
    meta["interpreter"] = {"model": INTERPRET_MODEL, "backend": "claude-cli"}
    retrieve_wall = time.perf_counter() - t0

    doc_cache: dict = {}
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
        ids_through = len(contexts)
    meta["returned"] = len(contexts)
    meta["ranking"]["ids_through"] = ids_through
    meta["ranking"]["contexts_through"] = len(contexts)
    meta["chunk_ids"] = chunk_id_lists

    search_time_s = max(0.0, retrieve_wall - interp_time - embed_usage.time_s)
    retrieval_usage = ModelUsage(
        calls=interp_calls + embed_usage.calls,
        tokens_in=interp_in + embed_usage.tokens_in,
        tokens_out=interp_out + embed_usage.tokens_out,
        time_s=interp_time + embed_usage.time_s,
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


def _model_selfcheck() -> None:
    rng = np.random.default_rng(20260903)
    bulk = 0.5 + 0.1 * rng.standard_normal(20000)
    mu, s, u = _null(bulk)
    assert mu == np.median(bulk)
    assert abs(s - 0.1) < 0.01
    assert (u > 0.0).all() and abs(np.median(u) - 1.0 / MADK) < 1e-12
    try:
        _null(np.full(16, 0.3))
    except RuntimeError:
        pass
    else:
        raise AssertionError("a population with no spread yielded a null")
    print(f"  null on a Gaussian bulk of scale 0.1: median {mu:.4f}, scale "
          f"{s:.4f}; a flat population stops", flush=True)

    assert abs(_profile(NEUTRAL_FACETS).sum() - 1.0) < 1e-12
    assert (_profile({f: 0.0 for f in ALL_FACETS}) == 0.2).all()
    one = _profile({f: (3.0 if f == "temporal" else 0.0) for f in ALL_FACETS})
    assert one[ALL_FACETS.index("temporal")] == 1.0
    print(f"  part profile: a no-claim part -> {_profile(NEUTRAL_FACETS)[0]:.4f} "
          f"per axis, a single-axis part -> {one[ALL_FACETS.index('temporal')]:.4f} "
          f"on temporal", flush=True)

    dim, n_tags, n_chunks = 32, 600, 120
    probes = _unit(rng.standard_normal((2, dim)).astype(np.float32))
    tag_emb = rng.standard_normal((n_tags, dim))
    tag_emb[:12] = 8.0 * probes[0] + rng.standard_normal((12, dim))
    tag_emb[12:18] = 8.0 * probes[1] + rng.standard_normal((6, dim))
    tag_emb = _unit(tag_emb.astype(np.float32))
    desc_emb = rng.standard_normal((n_chunks, dim))
    desc_emb[:5] = 8.0 * probes[0] + rng.standard_normal((5, dim))
    desc_emb = _unit(desc_emb.astype(np.float32))
    topic, evidence = ALL_FACETS.index("topic"), ALL_FACETS.index("evidence")
    phi = np.zeros((2, len(ALL_FACETS)))
    phi[0, topic] = 1.0
    phi[1, evidence] = 1.0
    pairs = {(0, 0), (0, 1), (1, 0), (2, 12)}
    for chunk in range(3, n_chunks):
        for tag in rng.choice(np.arange(18, n_tags), 3, replace=False):
            pairs.add((chunk, int(tag)))
    pairs = sorted(pairs)
    edge_chunk = np.array([c for c, _ in pairs])
    edge_tag = np.array([t for _, t in pairs])
    edge_w = rng.random((len(pairs), len(ALL_FACETS)))
    edge_w[:4] = 0.0
    edge_w[:3, topic] = 1.0
    edge_w[3, evidence] = 1.0

    chain = _score(probes, phi, tag_emb, desc_emb, edge_chunk, edge_tag, edge_w,
                   "evidence")
    dp = (1.0 - (probes @ tag_emb.T).astype(np.float64)) / 2.0
    assert (chain["nearest_part"] == dp.argmin(axis=0)).all()
    assert np.allclose(chain["d_star"], dp.min(axis=0))
    assert chain["nearest_part"][:12].tolist() == [0] * 12
    assert chain["nearest_part"][12:18].tolist() == [1] * 6
    ell = chain["ell"]
    assert (ell >= 0.0).all() and (ell[:18] > 0.0).all()
    assert (ell == 0.0).mean() > 0.5
    by_distance = ell[np.argsort(chain["d_star"], kind="stable")]
    assert (np.diff(by_distance) <= 1e-12).all()
    assert np.allclose(chain["r_edge"],
                       (phi[chain["nearest_part"][edge_tag]] * edge_w).sum(axis=1))
    assert np.allclose(chain["r_edge"][:4], 1.0)
    tag_ev = chain["tag_score"]
    assert np.allclose(tag_ev, np.bincount(edge_chunk, weights=chain["r_edge"] * ell[edge_tag],
                                           minlength=n_chunks))
    assert abs(tag_ev[0] - (ell[0] + ell[1])) < 1e-9
    assert abs(tag_ev[1] - ell[0]) < 1e-9
    assert tag_ev[0] > tag_ev[1] > 0.0
    ell_c = chain["base"]
    assert (ell_c >= 0.0).all()
    assert ell_c[:5].min() > ell_c[5:].max()
    assert np.median(ell_c[5:]) < 1.0
    by_distance = ell_c[np.argsort(chain["d_c"], kind="stable")]
    assert (np.diff(by_distance) <= 1e-12).all()
    assert np.allclose(chain["score"], ell_c + tag_ev)
    assert chain["nu"] > 0.0 and chain["nu_desc"] > 0.0
    print(f"  evidence: {int((ell > 0).sum())} of {n_tags} tags above 0 (18 "
          f"planted), planted tag evidence {ell[:18].min():.2f}-{ell[:18].max():.2f} "
          f"nats, monotone in the distance; t shape nu {chain['nu']:.2f} (tags), "
          f"{chain['nu_desc']:.2f} (descriptions); planted descriptions "
          f"{ell_c[:5].min():.2f}-{ell_c[:5].max():.2f} nats over a bulk median "
          f"of {np.median(ell_c[5:]):.4f}", flush=True)
    print(f"  chunk 0 tag evidence: two edges {tag_ev[0]:.4f} = {ell[0]:.4f} + "
          f"{ell[1]:.4f}; chunk 1 one edge {tag_ev[1]:.4f}; score = description "
          f"evidence + tag evidence", flush=True)

    prob = _score(probes, phi, tag_emb, desc_emb, edge_chunk, edge_tag, edge_w,
                  "probability")
    assert np.allclose(prob["ell"], ell) and np.allclose(prob["base"], ell_c)
    assert (prob["nearest_part"] == chain["nearest_part"]).all()
    assert np.allclose(prob["r_edge"], chain["r_edge"])
    share = -np.expm1(-ell)
    assert (share >= 0.0).all() and (share < 1.0).all()
    assert np.allclose(prob["tag_score"], np.bincount(
        edge_chunk, weights=chain["r_edge"] * share[edge_tag], minlength=n_chunks))
    assert np.allclose(prob["score"], np.exp(ell_c) * prob["tag_score"])
    print(f"  probability: chunk 0 tag share {prob['tag_score'][0]:.4f} = "
          f"{share[0]:.4f} + {share[1]:.4f}; score = exp(description evidence) "
          f"x tag share, same evidence, same parts, same edges", flush=True)

    other = _score(probes, phi[::-1].copy(), tag_emb, desc_emb, edge_chunk,
                   edge_tag, edge_w, "evidence")
    assert np.allclose(other["ell"], ell)
    assert np.allclose(other["r_edge"][:4], 0.0)
    assert np.allclose(other["tag_score"][:3], 0.0)
    print(f"  parts' profiles swapped: the four planted edges' relevance "
          f"{np.round(other['r_edge'][:4], 4).tolist()} over unchanged tag "
          f"evidence", flush=True)
    print("artefact_chain model self-check OK", flush=True)


def _selfcheck() -> None:
    _model_selfcheck()
    corpus = Path(__file__).resolve().parent.parent.parent / "data" / "corpus" / DATASET_ID
    prepared = prepare_over_corpus(corpus)
    n_tags, n_chunks = len(prepared.tag_names), len(prepared.chunk_ids)
    walls, searches, shapes, positives = [], [], [], []
    for probe in progress(_PROBES, desc="probing", unit="q"):
        t0 = time.perf_counter()
        out = answer_one_question(("selfcheck", probe), prepared, None,
                                  char_budget=72000)
        walls.append(time.perf_counter() - t0)
        searches.append(out.search_time_s)
        meta = out.meta
        rank = meta["ranking"]
        budget = meta["char_budget"]
        shapes.append((meta["nu"], meta["nu_desc"]))
        positives.append(meta["tag_evidence"]["positive"])
        print(f"\n  {probe}", flush=True)
        for block, share in zip(meta["parts"], meta["nearest_part"]):
            print(f"    part {block['index']} {block['source']:<11s} nearest to "
                  f"{share} tag(s); profile " + "  ".join(
                      f"{f} {block['profile'][f]:.3f}" for f in ALL_FACETS),
                  flush=True)
        print(f"    tag evidence: {meta['tag_evidence']}; t shape nu "
              f"{meta['nu']:.2f} (tags), {meta['nu_desc']:.2f} (descriptions)",
              flush=True)
        print(f"    edge relevance: {meta['edge_relevance']}", flush=True)
        print(f"    description evidence: {meta['description_evidence']}", flush=True)
        print(f"    chunk evidence: {meta['chunk_evidence']}", flush=True)
        print(f"    returned {meta['returned']} context(s), "
              f"{len(out.context_ids)} artifact id(s), "
              f"{sum(len(c) for c in out.contexts)} chars; retrieval model "
              f"calls {out.retrieval.calls}, search {out.search_time_s:.3f}s, "
              f"wall {walls[-1]:.3f}s", flush=True)
        print(f"    ranking: {len(rank['chunk_ids'])} rank(s) recorded, "
              f"artifact ids through {rank['ids_through']}, context text "
              f"through {rank['contexts_through']}, "
              f"{len(json.dumps(rank, ensure_ascii=False))} chars of the "
              f"record", flush=True)
        assert (len(rank["chunk_ids"]) == len(rank["scores"])
                == len(rank["desc_dist"]) == n_chunks)
        assert len(set(rank["chunk_ids"])) == n_chunks
        assert all(a >= b for a, b in zip(rank["scores"], rank["scores"][1:]))
        assert meta["retrieved"] == n_chunks
        assert rank["contexts_through"] == len(meta["chunk_ids"])
        assert rank["ids_through"] == budget["kept"]
        if budget["boundary"] is not None:
            assert rank["contexts_through"] == budget["kept"] + 1
            assert rank["chunk_ids"][budget["kept"]] == budget["boundary"]["id"]
        resorted = sorted(zip(rank["chunk_ids"], rank["scores"], rank["desc_dist"]),
                          key=lambda row: (-row[1], row[2], row[0]))
        assert [cid for cid, _, _ in resorted] == rank["chunk_ids"]
        assert meta["n_parts"] == len(meta["parts"]) == len(meta["nearest_part"])
        assert sum(meta["nearest_part"]) == meta["tag_evidence"]["n"] == n_tags
        assert 0.0 <= meta["tag_evidence"]["min"] <= meta["tag_evidence"]["max"]
        assert (0 <= meta["tag_evidence"]["over_3"]
                <= meta["tag_evidence"]["positive"] <= n_tags)
        assert meta["nu"] > 0.0 and meta["nu_desc"] > 0.0
        assert meta["edge_relevance"]["n"] == len(prepared.edge_tag)
        assert 0.0 <= meta["edge_relevance"]["min"] <= meta["edge_relevance"]["max"] <= 1.0
        assert meta["chunk_evidence"]["n"] == meta["description_evidence"]["n"] == n_chunks
        assert 0.0 <= meta["chunk_evidence"]["min"] <= meta["chunk_evidence"]["max"]
        assert 0 <= meta["chunk_evidence"]["zero"] <= n_chunks
        assert (0.0 <= meta["description_evidence"]["min"]
                <= meta["description_evidence"]["max"])
        assert 0 <= meta["description_evidence"]["positive"] <= n_chunks
        for block in meta["parts"]:
            assert abs(sum(block["profile"].values()) - 1.0) < 1e-9
        assert len(out.context_ids) == len(set(out.context_ids))
        assert len(meta["chunk_ids"]) == len(out.contexts)
        assert out.contexts, "a probe returned no context"
    print(f"\nartefact_chain: prepare {prepared.build_stats.build_time_s:.1f}s — "
          f"{n_tags} tags, {n_chunks} chunks, {len(prepared.edge_tag)} edges in "
          f"memory; HERB_CHAIN={CHAIN_VARIANT}", flush=True)
    print(f"  t shapes over the probes: tags nu "
          f"{min(s for s, _ in shapes):.2f}-{max(s for s, _ in shapes):.2f}, "
          f"descriptions nu {min(s for _, s in shapes):.2f}-"
          f"{max(s for _, s in shapes):.2f}; {min(positives)}-{max(positives)} of "
          f"{n_tags} tags above 0", flush=True)
    print(f"  {len(_PROBES)} probe(s): search {min(searches):.3f}-{max(searches):.3f}s, "
          f"wall with resolution {min(walls):.3f}-{max(walls):.3f}s per question",
          flush=True)
    print(f"  every chunk scored on every probe; the record re-sorts to the arm's "
          f"order at {RANK_SCORE_DP} dp", flush=True)
    print("artefact_chain self-check OK", flush=True)


if __name__ == "__main__":
    _selfcheck()

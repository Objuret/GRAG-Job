from __future__ import annotations

print("artefact_cluster: the hits seed a cluster over the tag distances on the "
      "levels-of-k's ladder, the facets weight the seeds, every edge brings its "
      "tag's membership to the chunk at the edge's relevance, the description's "
      "own evidence joins the sum; loading numpy, scipy and the shared graph "
      "plumbing …", flush=True)

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Optional

import numpy as np
from scipy.special import logsumexp, ndtri
from scipy.stats import t as student_t

from harness import nim
from harness.contract import ArmOutput, BuildStats, ModelUsage, unpack_generation
from arms.artefact_composed import (
    RANK_SCORE_DP, _PROBES, _parts, _pointer, _profile, _spread,
)
from arms.artefact_v2 import (
    ALL_FACETS, DATABASE, DATASET_ID, FRESH_INTERP, INTERPRET_MODEL,
    NEUTRAL_FACETS, RAW_QUESTION, RUN_ID, _DESC_POOL_MATCH, _EXCLUDED_PARAM,
    _TAG_POOL_MATCH, _budget_contexts, _driver, _embed_cached, _env_int,
    _interpret_cached, _qid_text, _resolve_chunk, _unit,
)
from harness.embed import EMBED_MODEL
from harness.progress import progress, say


MADK = 1.0 / ndtri(0.75)

KERNEL_TAU = np.finfo(np.float64).eps

DENSITY_BLOCK = 256

MATCH_EVIDENCE = np.log(2.0)

LADDER_BASE = 2

REACH_BLOCK = 500

SCOPE_TIER = _env_int("HERB_SCOPE_TIER", 1)
if SCOPE_TIER not in (0, 1):
    raise ValueError(
        f"HERB_SCOPE_TIER must be 0 or 1, got {SCOPE_TIER!r} — 1 ranks the "
        f"stated product's file first, 0 ranks the graph unrestricted")

HEARTBEAT_S = 30.0

RETRIEVAL_FLAGS = {
    "HERB_SCOPE_TIER": SCOPE_TIER,
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
    tag_facets: np.ndarray
    reach: np.ndarray
    kernel: np.ndarray
    levels: int
    chunk_ids: list
    pointers: list
    rel_paths: list
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


def _ladder_kernel(n: int) -> tuple:
    levels = 1
    while LADDER_BASE ** (levels - 1) < n:
        levels += 1
    g = np.zeros(n)
    for j in range(levels):
        k = min(LADDER_BASE ** j, n)
        g[:k] += 1.0 / k
    return g / levels, levels


def _reachability(tag_emb: np.ndarray, g: np.ndarray) -> np.ndarray:
    n = len(tag_emb)
    h = np.zeros(n)
    bar = progress(total=n, desc="reachability", unit="tag")
    for start in range(0, n, REACH_BLOCK):
        cos = tag_emb[start:start + REACH_BLOCK] @ tag_emb.T
        for row in cos:
            h[np.argsort(-row, kind="stable")] += g
        bar.update(len(cos))
    bar.close()
    return h


def prepare_over_corpus(corpus) -> Prepared:
    t0 = time.perf_counter()
    print(f"artefact_cluster: opening {DATABASE} …", flush=True)
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
                    f"arm scores every retrievable chunk on its description")
            tags = _pull(s, _TAG_POOL_MATCH, _TAGS_RETURN, {"runId": RUN_ID},
                         "tag layer", "tag")
            chunks = _pull(s, _DESC_POOL_MATCH, _CHUNKS_RETURN, population,
                           "chunk layer", "chunk")
            edges = _pull(s, _EDGES_MATCH, _EDGES_RETURN,
                          {**population, "runId": RUN_ID}, "facet layer", "edge")
    finally:
        drv.close()

    if not tags or not chunks or not edges:
        raise RuntimeError(
            f"{len(tags)} tag(s), {len(chunks)} retrievable chunk(s) and "
            f"{len(edges)} HAS_TAG edge(s) of run {RUN_ID!r} in {DATABASE!r} — "
            f"every layer has to hold something for a cluster to exist")

    emb_of = {row["name"]: row["emb"] for row in tags}
    if len(emb_of) != len(tags):
        raise RuntimeError(
            f"{len(tags) - len(emb_of)} tag name(s) in {DATABASE!r} are not unique "
            f"— the arm addresses a tag by its name")
    tag_names = sorted(emb_of)
    tag_emb = _unit(np.asarray([emb_of[n] for n in tag_names], dtype=np.float32))

    pointer_of = {row["chunkId"]: row for row in chunks}
    if len(pointer_of) != len(chunks):
        raise RuntimeError(
            f"{len(chunks) - len(pointer_of)} chunk id(s) in {DATABASE!r} are not "
            f"unique — pointer resolution would be ambiguous")
    chunk_ids = sorted(pointer_of)
    pointers = [_pointer(pointer_of[cid]) for cid in chunk_ids]
    rel_paths = [pointer_of[cid]["relpath"] for cid in chunk_ids]
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
                f"the arm reads all five of {list(ALL_FACETS)} on every edge")
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
            f"carry no HAS_TAG edge of run {RUN_ID!r} — every chunk's cluster "
            f"evidence is a sum over its edges and would be zero")
    tag_degree = np.bincount(edge_tag, minlength=len(tag_names))
    if not tag_degree.all():
        raise RuntimeError(
            f"{int((tag_degree == 0).sum())} tag(s) in {DATABASE!r} carry no "
            f"HAS_TAG edge of run {RUN_ID!r} to a retrievable chunk — a tag's "
            f"facet vector is the mean over those edges")
    tag_facets = np.stack([np.bincount(edge_tag, weights=edge_w[:, j],
                                       minlength=len(tag_names))
                           for j in range(len(ALL_FACETS))], axis=1) / tag_degree[:, None]

    kernel, levels = _ladder_kernel(len(tag_names))
    print(f"artefact_cluster: {len(tag_names)} tags, {len(chunk_ids)} chunks, "
          f"{len(edge_chunk)} edges in memory; ladder of {levels} levels; "
          f"building the reachability …", flush=True)
    reach = _reachability(tag_emb, kernel)
    if abs(reach.mean() - 1.0) > 1e-9 or (reach < kernel[0]).any():
        raise RuntimeError(
            f"the reachability has mean {reach.mean()!r} and minimum "
            f"{reach.min()!r} against the kernel's g(1) = {kernel[0]!r} — the "
            f"kernel sums to 1 per seed and every tag ranks first in its own "
            f"ordering, so neither can hold")

    print(f"artefact_cluster: reachability median {np.median(reach):.3f}, max "
          f"{reach.max():.2f}; HERB_SCOPE_TIER={SCOPE_TIER}", flush=True)
    return Prepared(
        tag_names=tag_names, tag_emb=tag_emb, tag_facets=tag_facets, reach=reach,
        kernel=kernel, levels=levels,
        chunk_ids=chunk_ids, pointers=pointers, rel_paths=rel_paths,
        desc_emb=desc_emb, edge_chunk=edge_chunk, edge_tag=edge_tag, edge_w=edge_w,
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


def _fit_nu(standardised: np.ndarray) -> tuple:
    sym = np.concatenate([standardised, -standardised])
    nu, _, c = student_t.fit(sym, floc=0.0)
    return nu, c


def _pava_dec(y: np.ndarray, x: np.ndarray) -> np.ndarray:
    order = np.argsort(x, kind="stable")
    v = y[order]
    vals, wts, cnts = [], [], []
    for i in range(len(v)):
        vals.append(v[i])
        wts.append(1.0)
        cnts.append(1)
        while len(vals) > 1 and vals[-2] < vals[-1]:
            m = (vals[-2] * wts[-2] + vals[-1] * wts[-1]) / (wts[-2] + wts[-1])
            vals[-2] = m
            wts[-2] += wts[-1]
            cnts[-2] += cnts[-1]
            vals.pop()
            wts.pop()
            cnts.pop()
    out = np.empty(len(y))
    out[order] = np.concatenate([np.full(c, val) for val, c in zip(vals, cnts)])
    return out


def _kde_exact(x: np.ndarray, h: float) -> np.ndarray:
    if not h > 0.0:
        raise RuntimeError(
            f"kernel bandwidth {h!r}: the population has no spread to smooth over")
    n = len(x)
    r = math.sqrt(2.0 * math.log(n / KERNEL_TAU))
    order = np.argsort(x, kind="stable")
    xs = x[order]
    hi = np.searchsorted(xs, xs + r * h, side="right")
    total = np.zeros(n)
    for start in range(0, n, DENSITY_BLOCK):
        stop = min(start + DENSITY_BLOCK, n)
        b = hi[stop - 1]
        u = (xs[start:stop, None] - xs[None, start:b]) / h
        k = np.exp(-0.5 * u * u)
        k[np.abs(u) > r] = 0.0
        total[start:stop] += k.sum(axis=1)
        total[stop:b] += k[:, stop - start:].sum(axis=0)
    dens = np.empty(n)
    dens[order] = total / (n * h * math.sqrt(2.0 * math.pi))
    return dens


def _local_ell(d_star: np.ndarray, d_by_part: np.ndarray) -> tuple:
    nulls, standardised = [], []
    for p in range(d_by_part.shape[0]):
        mu, s, u = _null(d_by_part[p])
        nulls.append((mu, s))
        standardised.append(u)
    nu, c = _fit_nu(np.concatenate(standardised))
    sd = d_star.std(ddof=1)
    iqr = np.subtract(*np.percentile(d_star, [75, 25]))
    h = 0.9 * min(sd, iqr / 1.34) * len(d_star) ** (-0.2)
    log_f = np.log(np.maximum(_kde_exact(d_star, h), 1e-300))
    log_f0 = logsumexp(np.stack([student_t.logpdf((d_star - mu) / (c * s), nu)
                                 - np.log(c * s) for mu, s in nulls]), axis=0)
    return np.maximum(_pava_dec(log_f - log_f0, d_star), 0.0), float(nu)


def _field(tag_emb: np.ndarray, seeds: np.ndarray, weights: np.ndarray,
           g: np.ndarray) -> np.ndarray:
    F = np.zeros(len(tag_emb))
    cos = tag_emb[seeds] @ tag_emb.T
    started = last = time.perf_counter()
    for i, row in enumerate(cos):
        F[np.argsort(-row, kind="stable")] += weights[i] * g
        now = time.perf_counter()
        if now - last >= HEARTBEAT_S:
            say(f"artefact_cluster: field at seed {i + 1}/{len(seeds)} after "
                f"{now - started:.0f}s")
            last = now
    return F


def _score(probes: np.ndarray, phi: np.ndarray, tag_emb: np.ndarray,
           tag_facets: np.ndarray, reach: np.ndarray, g: np.ndarray,
           desc_emb: np.ndarray, edge_chunk: np.ndarray, edge_tag: np.ndarray,
           edge_w: np.ndarray) -> dict:
    t0 = time.perf_counter()
    dp = (1.0 - (probes @ tag_emb.T).astype(np.float64)) / 2.0
    reached = dp.argmin(axis=0)
    ell, nu = _local_ell(dp.min(axis=0), dp)
    seeds = np.flatnonzero(ell > MATCH_EVIDENCE)
    if not seeds.size:
        raise RuntimeError(
            "no tag carries evidence above ln 2 — every distance sits in the "
            "null's bulk and the query matched nothing to seed the cluster from")
    seed_weight = ell[seeds] * (phi[reached[seeds]] * tag_facets[seeds]).sum(axis=1)
    total = seed_weight.sum()
    if not total > 0.0:
        raise RuntimeError(
            f"{len(seeds)} seed(s) weigh {total!r} together — the facet vectors "
            f"the reaching parts' profiles meet hold nothing on the axes they "
            f"attend to, and a field of zero weight has no expectation to divide by")
    t1 = time.perf_counter()
    field = _field(tag_emb, seeds, seed_weight, g) / ((total / len(tag_emb)) * reach)
    t2 = time.perf_counter()
    member = np.log(np.maximum(field, 1.0))
    r_edge = (phi[reached[edge_tag]] * edge_w).sum(axis=1)
    cluster = np.bincount(edge_chunk, weights=r_edge * member[edge_tag],
                          minlength=len(desc_emb))
    d_c = (1.0 - (desc_emb @ probes[0]).astype(np.float64)) / 2.0
    ell_c, _ = _local_ell(d_c, d_c[None, :])
    t3 = time.perf_counter()
    return {"score": ell_c + cluster, "base": ell_c, "cluster": cluster,
            "ell": ell, "seeds": seeds, "seed_weight": seed_weight,
            "field": field, "d_c": d_c, "r_edge": r_edge, "reached": reached,
            "nu": float(nu),
            "timing": {"evidence_s": t1 - t0, "field_s": t2 - t1,
                       "chunks_s": t3 - t2}}


def _scope_mask(rel_paths: list, product) -> np.ndarray:
    if not product:
        return np.zeros(len(rel_paths), dtype=bool)
    target = f"{product}.json"
    return np.array([PurePosixPath(p).parent.name == "products"
                     and PurePosixPath(p).name == target for p in rel_paths],
                    dtype=bool)


def _tiers(in_scope: np.ndarray, restricted: bool) -> np.ndarray:
    if not restricted or not in_scope.any():
        return np.ones(len(in_scope), dtype=np.int64)
    return np.where(in_scope, 1, 2)


def _order(tier: np.ndarray, score: np.ndarray, desc_dist: np.ndarray) -> np.ndarray:
    return np.lexsort((np.arange(len(tier)), desc_dist, -score, tier))


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

    chain = _score(probes, phi, prepared.tag_emb, prepared.tag_facets,
                   prepared.reach, prepared.kernel, prepared.desc_emb,
                   prepared.edge_chunk, prepared.edge_tag, prepared.edge_w)
    ell, ell_c, cluster, field = chain["ell"], chain["base"], chain["cluster"], chain["field"]
    if not (cluster > 0.0).any() and not (ell_c > 0.0).any():
        raise RuntimeError(
            "no chunk carries cluster evidence and no chunk carries description "
            "evidence — there is nothing to rank on")
    product = (plan.get("gate") or {}).get("product")
    in_scope = _scope_mask(prepared.rel_paths, product)
    tier = _tiers(in_scope, SCOPE_TIER == 1)

    score = np.round(chain["score"], RANK_SCORE_DP)
    desc_dist = np.round(chain["d_c"], RANK_SCORE_DP)
    order = _order(tier, score, desc_dist)
    ranking = {"chunk_ids": [prepared.chunk_ids[i] for i in order],
               "scores": [float(score[i]) for i in order],
               "desc_dist": [float(desc_dist[i]) for i in order],
               "tiers": [int(tier[i]) for i in order]}
    kept = order if keep_all else order[:k]
    rows = [prepared.pointers[i] for i in kept]

    crisp = field > 1.0
    meta = {
        "n_parts": len(parts),
        "nu": chain["nu"],
        "tag_evidence": {**_spread(ell), "positive": int((ell > 0.0).sum()),
                         "admitted": int((ell > MATCH_EVIDENCE).sum())},
        "seeds": int(len(chain["seeds"])),
        "field": {"max": float(field.max()),
                  "members": _spread(field[crisp]),
                  "zero_evidence_members": int((crisp & (ell == 0.0)).sum())},
        "chunk_evidence": {**_spread(cluster), "zero": int((cluster == 0.0).sum())},
        "description_evidence": _spread(ell_c),
        "scope": {"product": bool(product), "matched": bool(in_scope.any()),
                  "size": int(in_scope.sum())},
        "timing": {name: float(secs) for name, secs in chain["timing"].items()},
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
    meta["delivered_tiers"] = meta["ranking"]["tiers"][:len(contexts)]
    chunk_at = {cid: i for i, cid in enumerate(prepared.chunk_ids)}
    meta["delivered_tags_per_chunk"] = _spread(prepared.chunk_degree[
        [chunk_at[cid] for cid in meta["ranking"]["chunk_ids"][:len(contexts)]]])
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

    y = np.array([1.0, 3.0, 2.0, 0.0, 5.0, 0.0])
    fit = _pava_dec(y, np.arange(6.0))
    assert np.allclose(fit, [2.2] * 5 + [0.0])
    assert abs(fit.sum() - y.sum()) < 1e-12
    shuffled = rng.permutation(6)
    assert np.allclose(_pava_dec(y[shuffled], np.arange(6.0)[shuffled]), fit[shuffled])
    print(f"  isotonic fit of {y.tolist()} non-increasing in x: "
          f"{np.round(fit, 4).tolist()}, mean preserved, order-free", flush=True)

    gauss = rng.standard_normal(20000)
    h = 0.9 * min(gauss.std(ddof=1), np.subtract(*np.percentile(gauss, [75, 25])) / 1.34) \
        * len(gauss) ** (-0.2)
    dens = _kde_exact(gauss, h)
    truth = np.exp(-0.5 * gauss ** 2) / math.sqrt(2 * math.pi)
    assert np.abs(dens - truth).max() < 0.02
    few = gauss[:3000]
    pair = (few[:, None] - few[None, :]) / h
    untruncated = (np.exp(-0.5 * pair * pair).sum(axis=1)
                   / (len(few) * h * math.sqrt(2 * math.pi)))
    gap = np.abs(_kde_exact(few, h) / untruncated - 1.0).max()
    assert gap < 16 * KERNEL_TAU
    print(f"  exact kernel density on 20000 standard normals at h {h:.4f}: "
          f"largest gap to the true density {np.abs(dens - truth).max():.4f}; "
          f"against the untruncated sum over 3000 of them, largest relative gap "
          f"{gap:.1e}", flush=True)

    for n in (1, 2, 5, 16, 600, 16714):
        g, levels = _ladder_kernel(n)
        assert levels == int(math.ceil(math.log2(n))) + 1
        assert abs(g.sum() - 1.0) < 1e-12
        assert (np.diff(g) <= 0.0).all()
        ks = [min(LADDER_BASE ** j, n) for j in range(levels)]
        assert abs(g[0] - sum(1.0 / k for k in ks) / levels) < 1e-15
        assert abs(g[-1] - 1.0 / (n * levels)) < 1e-15
    g600, levels600 = _ladder_kernel(600)
    print(f"  ladder over 600: {levels600} levels {[min(LADDER_BASE ** j, 600) for j in range(levels600)]}, "
          f"g(1) {g600[0]:.4f}, g(8) {g600[7]:.4f}, g(600) {g600[-1]:.6f}, mass "
          f"{g600.sum():.12f}", flush=True)

    dim, n_tags, n_chunks = 32, 600, 120
    probes = _unit(rng.standard_normal((2, dim)).astype(np.float32))
    tag_emb = rng.standard_normal((n_tags, dim))
    tag_emb[:12] = 8.0 * probes[0] + rng.standard_normal((12, dim))
    tag_emb[12:18] = 8.0 * probes[1] + rng.standard_normal((6, dim))
    tag_emb = _unit(tag_emb.astype(np.float32))
    desc_emb = rng.standard_normal((n_chunks, dim))
    desc_emb[:5] = 8.0 * probes[0] + rng.standard_normal((5, dim))
    desc_emb = _unit(desc_emb.astype(np.float32))
    reach = _reachability(tag_emb, g600)
    assert abs(reach.mean() - 1.0) < 1e-9 and (reach >= g600[0]).all()
    print(f"  reachability over 600 tags: mean {reach.mean():.12f}, min "
          f"{reach.min():.4f} at or above g(1) {g600[0]:.4f}, max {reach.max():.3f}",
          flush=True)

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
    tag_facets = rng.random((n_tags, len(ALL_FACETS)))

    chain = _score(probes, phi, tag_emb, tag_facets, reach, g600, desc_emb,
                   edge_chunk, edge_tag, edge_w)
    dp = (1.0 - (probes @ tag_emb.T).astype(np.float64)) / 2.0
    assert (chain["reached"] == dp.argmin(axis=0)).all()
    assert chain["reached"][:12].tolist() == [0] * 12
    assert chain["reached"][12:18].tolist() == [1] * 6
    ell = chain["ell"]
    assert (ell >= 0.0).all() and (ell[:18] > MATCH_EVIDENCE).all()
    assert (ell == 0.0).mean() > 0.5
    by_distance = ell[np.argsort(dp.min(axis=0), kind="stable")]
    assert (np.diff(by_distance) <= 1e-12).all()
    seeds = chain["seeds"]
    assert (seeds == np.flatnonzero(ell > MATCH_EVIDENCE)).all()
    assert set(range(18)) <= set(seeds.tolist())
    assert np.allclose(chain["seed_weight"],
                       ell[seeds] * (phi[chain["reached"][seeds]] * tag_facets[seeds]).sum(axis=1))
    assert (chain["seed_weight"] > 0.0).all()
    print(f"  local evidence: {int((ell > 0).sum())} of {n_tags} tags above 0, "
          f"{int((ell > MATCH_EVIDENCE).sum())} above ln 2 (18 planted), planted "
          f"tag evidence {ell[:18].min():.2f}-{ell[:18].max():.2f} nats, "
          f"non-increasing in the distance; t shape nu {chain['nu']:.2f}; "
          f"{len(seeds)} seeds weighing {chain['seed_weight'].sum():.2f} together",
          flush=True)

    field = chain["field"]
    total = chain["seed_weight"].sum()
    raw = np.zeros(n_tags)
    cos = tag_emb[seeds] @ tag_emb.T
    for i in range(len(seeds)):
        raw[np.argsort(-cos[i], kind="stable")] += chain["seed_weight"][i] * g600
    assert np.allclose(field, raw / ((total / n_tags) * reach))
    assert (field[:18] > 1.0).all()
    crisp = field > 1.0
    assert 18 <= crisp.sum() < n_tags / 2
    member = np.log(np.maximum(field, 1.0))
    assert (member >= 0.0).all() and (member[~crisp] == 0.0).all()
    print(f"  field: F~ max {field.max():.2f}, planted tags F~ "
          f"{field[:18].min():.2f}-{field[:18].max():.2f}, crisp extent "
          f"{int(crisp.sum())} of {n_tags} tags, {int((crisp & (ell == 0.0)).sum())} "
          f"admitted with zero evidence", flush=True)

    assert np.allclose(chain["r_edge"],
                       (phi[chain["reached"][edge_tag]] * edge_w).sum(axis=1))
    assert np.allclose(chain["r_edge"][:4], 1.0)
    cluster = chain["cluster"]
    assert np.allclose(cluster, np.bincount(edge_chunk, weights=chain["r_edge"] * member[edge_tag],
                                            minlength=n_chunks))
    assert abs(cluster[0] - (member[0] + member[1])) < 1e-9
    assert abs(cluster[1] - member[0]) < 1e-9
    assert cluster[0] > cluster[1] > 0.0
    ell_c = chain["base"]
    assert (ell_c >= 0.0).all()
    assert ell_c[:5].min() > ell_c[5:].max()
    by_distance = ell_c[np.argsort(chain["d_c"], kind="stable")]
    assert (np.diff(by_distance) <= 1e-12).all()
    assert np.allclose(chain["score"], ell_c + cluster)
    print(f"  chunk 0 cluster evidence: two edges {cluster[0]:.4f} = {member[0]:.4f} + "
          f"{member[1]:.4f}; chunk 1 one edge {cluster[1]:.4f}; planted descriptions "
          f"{ell_c[:5].min():.2f}-{ell_c[:5].max():.2f} nats over a bulk max of "
          f"{ell_c[5:].max():.4f}; score = description evidence + cluster evidence",
          flush=True)

    other = _score(probes, phi[::-1].copy(), tag_emb, tag_facets, reach, g600,
                   desc_emb, edge_chunk, edge_tag, edge_w)
    assert np.allclose(other["ell"], ell)
    assert (other["seeds"] == seeds).all()
    assert not np.allclose(other["seed_weight"], chain["seed_weight"])
    assert np.allclose(other["r_edge"][:4], 0.0)
    assert np.allclose(other["cluster"][:3], 0.0)
    print(f"  parts' profiles swapped: the four planted edges' relevance "
          f"{np.round(other['r_edge'][:4], 4).tolist()} over unchanged tag "
          f"evidence and re-weighted seeds", flush=True)

    rel_paths = ["X/products/A.json", "X/products/a.json", "X/metadata/A.json",
                 "X/products/sub/A.json", "X/products/A.json.bak", "X/products/B.json"]
    assert _scope_mask(rel_paths, "A").tolist() == [True] + [False] * 5
    assert _scope_mask(rel_paths, "B").tolist() == [False] * 5 + [True]
    assert not _scope_mask(rel_paths, None).any()
    assert not _scope_mask(rel_paths, "").any()
    assert not _scope_mask(rel_paths, "C").any()
    scope = np.array([True, False, True, False])
    assert _tiers(scope, True).tolist() == [1, 2, 1, 2]
    assert _tiers(np.zeros(4, dtype=bool), True).tolist() == [1, 1, 1, 1]
    assert _tiers(scope, False).tolist() == [1, 1, 1, 1]
    tier = np.array([2, 1, 1, 1, 1])
    score = np.array([9.0, 5.0, 7.0, 5.0, 5.0])
    dist = np.array([0.1, 0.3, 0.2, 0.2, 0.3])
    assert _order(tier, score, dist).tolist() == [2, 3, 1, 4, 0]
    print(f"  scope: product 'A' over {rel_paths} -> "
          f"{_scope_mask(rel_paths, 'A').astype(int).tolist()}; tiers of "
          f"{scope.astype(int).tolist()} restricted {_tiers(scope, True).tolist()}, "
          f"unrestricted {_tiers(scope, False).tolist()}; rank key (tier, -score, "
          f"distance, chunk index) -> {_order(tier, score, dist).tolist()}",
          flush=True)
    print("artefact_cluster model self-check OK", flush=True)


def _selfcheck() -> None:
    _model_selfcheck()
    corpus = Path(__file__).resolve().parent.parent.parent / "data" / "corpus" / DATASET_ID
    prepared = prepare_over_corpus(corpus)
    n_tags, n_chunks = len(prepared.tag_names), len(prepared.chunk_ids)
    walls, searches, shapes, seeds, extents, admitted, scopes = [], [], [], [], [], [], []
    for probe in progress(_PROBES, desc="probing", unit="q"):
        t0 = time.perf_counter()
        out = answer_one_question(("selfcheck", probe), prepared, None,
                                  char_budget=72000)
        walls.append(time.perf_counter() - t0)
        searches.append(out.search_time_s)
        meta = out.meta
        rank = meta["ranking"]
        budget = meta["char_budget"]
        shapes.append(meta["nu"])
        seeds.append(meta["seeds"])
        extents.append(meta["field"]["members"]["n"])
        admitted.append(meta["field"]["zero_evidence_members"])
        scopes.append(meta["scope"]["size"])
        print(f"\n  {probe}", flush=True)
        print(f"    {meta['n_parts']} part(s); tag evidence {meta['tag_evidence']}; "
              f"t shape nu {meta['nu']:.2f}; {meta['seeds']} seeds", flush=True)
        print(f"    field: {meta['field']}", flush=True)
        print(f"    chunk evidence: {meta['chunk_evidence']}", flush=True)
        print(f"    description evidence: {meta['description_evidence']}", flush=True)
        print(f"    scope {meta['scope']}; timing {meta['timing']}", flush=True)
        print(f"    returned {meta['returned']} context(s), "
              f"{len(out.context_ids)} artifact id(s), "
              f"{sum(len(c) for c in out.contexts)} chars, delivered tiers "
              f"{np.bincount(meta['delivered_tiers'], minlength=3)[1:3].tolist()}, "
              f"tags per delivered chunk {meta['delivered_tags_per_chunk']}; "
              f"retrieval model calls {out.retrieval.calls}, search "
              f"{out.search_time_s:.3f}s, wall {walls[-1]:.3f}s", flush=True)
        print(f"    ranking: {len(rank['chunk_ids'])} rank(s) recorded, "
              f"artifact ids through {rank['ids_through']}, context text "
              f"through {rank['contexts_through']}, "
              f"{len(json.dumps(rank, ensure_ascii=False))} chars of the "
              f"record", flush=True)
        assert (len(rank["chunk_ids"]) == len(rank["scores"]) == len(rank["desc_dist"])
                == len(rank["tiers"]) == n_chunks)
        assert len(set(rank["chunk_ids"])) == n_chunks
        assert all(a <= b for a, b in zip(rank["tiers"], rank["tiers"][1:]))
        assert all(a >= b for (a, ta), (b, tb) in zip(zip(rank["scores"], rank["tiers"]),
                                                      zip(rank["scores"][1:], rank["tiers"][1:]))
                   if ta == tb)
        assert set(rank["tiers"]) <= ({1, 2} if SCOPE_TIER == 1 else {1})
        assert meta["retrieved"] == n_chunks
        if meta["scope"]["matched"]:
            assert meta["scope"]["product"] and meta["scope"]["size"] > 0
            if SCOPE_TIER == 1:
                assert rank["tiers"].count(1) == meta["scope"]["size"]
        else:
            assert meta["scope"]["size"] == 0 and 2 not in rank["tiers"]
        assert rank["contexts_through"] == len(meta["chunk_ids"])
        assert rank["ids_through"] == budget["kept"]
        if budget["boundary"] is not None:
            assert rank["contexts_through"] == budget["kept"] + 1
            assert rank["chunk_ids"][budget["kept"]] == budget["boundary"]["id"]
        assert meta["delivered_tiers"] == rank["tiers"][:rank["contexts_through"]]
        assert meta["delivered_tags_per_chunk"]["n"] == rank["contexts_through"]
        resorted = sorted(zip(rank["chunk_ids"], rank["scores"], rank["desc_dist"],
                              rank["tiers"]),
                          key=lambda row: (row[3], -row[1], row[2], row[0]))
        assert [cid for cid, _, _, _ in resorted] == rank["chunk_ids"]
        assert meta["n_parts"] >= 1
        assert meta["tag_evidence"]["n"] == n_tags
        assert 0.0 <= meta["tag_evidence"]["min"] <= meta["tag_evidence"]["max"]
        assert (0 < meta["seeds"] == meta["tag_evidence"]["admitted"]
                <= meta["tag_evidence"]["positive"] <= n_tags)
        assert meta["nu"] > 0.0
        assert meta["field"]["max"] >= 0.0
        assert 0 <= meta["field"]["zero_evidence_members"] <= meta["field"]["members"]["n"] <= n_tags
        if meta["field"]["members"]["n"]:
            assert meta["field"]["members"]["min"] > 1.0
            assert meta["field"]["members"]["max"] <= meta["field"]["max"] + 1e-4
        assert meta["chunk_evidence"]["n"] == meta["description_evidence"]["n"] == n_chunks
        assert 0.0 <= meta["chunk_evidence"]["min"] <= meta["chunk_evidence"]["max"]
        assert 0 <= meta["chunk_evidence"]["zero"] <= n_chunks
        assert (0.0 <= meta["description_evidence"]["min"]
                <= meta["description_evidence"]["max"])
        assert all(v >= 0.0 for v in meta["timing"].values())
        assert len(out.context_ids) == len(set(out.context_ids))
        assert len(meta["chunk_ids"]) == len(out.contexts)
        assert out.contexts, "a probe returned no context"
    print(f"\nartefact_cluster: prepare {prepared.build_stats.build_time_s:.1f}s — "
          f"{n_tags} tags, {n_chunks} chunks, {len(prepared.edge_tag)} edges in "
          f"memory; ladder of {prepared.levels} levels, reachability median "
          f"{np.median(prepared.reach):.3f}, max {prepared.reach.max():.2f}; "
          f"HERB_SCOPE_TIER={SCOPE_TIER}", flush=True)
    print(f"  t shape over the probes: nu {min(shapes):.2f}-{max(shapes):.2f}; seeds "
          f"{min(seeds)}-{max(seeds)} of {n_tags} tags above ln 2", flush=True)
    print(f"  crisp extent |K~| {min(extents)}-{max(extents)} tags, "
          f"{min(admitted)}-{max(admitted)} admitted with zero evidence; scope "
          f"{min(scopes)}-{max(scopes)} of {n_chunks} chunks", flush=True)
    print(f"  {len(_PROBES)} probe(s): search {min(searches):.3f}-{max(searches):.3f}s, "
          f"wall with resolution {min(walls):.3f}-{max(walls):.3f}s per question",
          flush=True)
    print(f"  every chunk scored on every probe; the record re-sorts to the arm's "
          f"order at {RANK_SCORE_DP} dp", flush=True)
    print("artefact_cluster self-check OK", flush=True)


if __name__ == "__main__":
    _selfcheck()

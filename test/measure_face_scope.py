"""Faces and stated-scope shares over the candidate chunks of a finished run.

Gold-blind: reads a run's plans and its full candidate rankings, writes one row per
candidate chunk with the quantities below, and never touches the questions' text, the
answers or the gold. The gold join belongs to whoever reads the output.

Per edge tag->chunk on a candidate chunk:
  face(t, c)  = unit( sum over u in tags(c) of max(0, cos(t, u) - m) * u )
                m is the median cosine between random tag pairs in the graph, measured here;
                u runs over every tag of c including t itself (cos 1, weight 1 - m).
  share(t | S) = |chunks(t) in S| / |chunks(t)|
                S is the stated scope from the plan's gate (product, channel, employee, years),
                the intersection of whichever are named; None when the gate names nothing.

Per candidate chunk, against the run's own query phrases (description, parts, question):
  tag_cos   max over tags and phrases of cos(phrase, tag)          (the tag as it is)
  face_cos  max over tags and phrases of cos(phrase, face(tag, c)) (the tag as used here)
  share_max max over the chunk's tags of share(t | S)
  face_share max over tags and phrases of cos(phrase, face) * share(t | S)
  in_scope  whether c is in S

Usage:
  python test/measure_face_scope.py --run output/k=chars/<run dir> [--out DIR] [--seed 0]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for sub in ("test", "prod"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np  # noqa: E402

from graph.db import RUN_ID, _driver, _unit  # noqa: E402
from arms.artefact_v2 import DATABASE, _channel_names, _embed_cached, _readable  # noqa: E402

PAIRS = 50_000
CORPUS_ROOT = ROOT / "data" / "corpus"


def _say(msg: str) -> None:
    print(msg, flush=True)


def load_graph(session) -> dict:
    t0 = time.perf_counter()
    names, embs = [], []
    n = session.run("MATCH (t:Tag) WHERE t.emb IS NOT NULL RETURN count(t) AS n").single()["n"]
    _say(f"loading {n} tag vectors from {DATABASE!r} …")
    for i, rec in enumerate(session.run(
            "MATCH (t:Tag) WHERE t.emb IS NOT NULL RETURN t.name AS name, t.emb AS emb")):
        names.append(rec["name"])
        embs.append(np.asarray(rec["emb"], dtype=np.float32))
        if (i + 1) % 4000 == 0:
            _say(f"  {i + 1}/{n} tags  ({time.perf_counter() - t0:.0f}s)")
    T = _unit(np.stack(embs))
    at = {name: i for i, name in enumerate(names)}

    _say("loading HAS_TAG edges and chunk scope facts …")
    chunk_tags: dict = {}
    tag_chunks: dict = {}
    for rec in session.run(
            "MATCH (c:Chunk)-[r:HAS_TAG]->(t:Tag) WHERE r.run_id = $runId AND t.emb IS NOT NULL "
            "RETURN c.chunk_id AS cid, t.name AS name", runId=RUN_ID):
        ti = at[rec["name"]]
        chunk_tags.setdefault(rec["cid"], []).append(ti)
        tag_chunks.setdefault(ti, set()).add(rec["cid"])
    facts: dict = {}
    for rec in session.run(
            "MATCH (c:Chunk) RETURN c.chunk_id AS cid, c.kind AS kind, c.years AS years, "
            "[(c)-[:product]->(p) | p.name][0] AS product, "
            "[(c)-[:channel]->(ch) | ch.id] AS channels"):
        facts[rec["cid"]] = {"kind": rec["kind"], "years": rec["years"] or [],
                             "product": rec["product"], "channels": rec["channels"] or []}
    _say(f"  {len(T)} tags, {sum(len(v) for v in chunk_tags.values())} edges, "
         f"{len(chunk_tags)} tagged chunks, {len(facts)} chunks  "
         f"({time.perf_counter() - t0:.0f}s)")
    return {"T": T, "names": names, "at": at, "chunk_tags": chunk_tags,
            "tag_chunks": tag_chunks, "facts": facts}


def background(T: np.ndarray, seed: int, pairs: int) -> dict:
    rng = np.random.default_rng(seed)
    i = rng.integers(len(T), size=pairs)
    j = rng.integers(len(T), size=pairs)
    keep = i != j
    cos = np.einsum("ij,ij->i", T[i[keep]], T[j[keep]])
    q = np.percentile(cos, [10, 50, 90])
    return {"seed": seed, "pairs": int(keep.sum()), "median": float(q[1]),
            "p10": float(q[0]), "p90": float(q[2]), "mean": float(cos.mean())}


def employee_chunks(session, eid: str) -> set:
    rows = session.run(
        "MATCH (e:Employee {eid: $eid}) "
        "OPTIONAL MATCH (e)-[:slack]->(:Channel)<-[:channel]-(c1:Chunk) "
        "OPTIONAL MATCH (e)-[pl:meeting_transcripts|documents]->(:Product)<-[:product]-(c2:Chunk)"
        "-[:kind]->(k:Kind) WHERE k.name = type(pl) "
        "RETURN collect(DISTINCT c1.chunk_id) + collect(DISTINCT c2.chunk_id) AS cids",
        eid=eid).single()
    return {c for c in (rows["cids"] if rows else []) if c}


def stated_scope(session, gate: dict, facts: dict, channel_ids: dict) -> tuple:
    sets = []
    named = {}
    product = gate.get("product")
    if product:
        sets.append({c for c, f in facts.items() if f["product"] == product})
        named["product"] = product
    channel = gate.get("channel")
    if channel:
        ids = set(channel_ids.get(channel, ()))
        sets.append({c for c, f in facts.items() if ids & set(f["channels"])})
        named["channel"] = channel
        named["channel_ids"] = sorted(ids)
    eid = gate.get("employee_id")
    if eid:
        sets.append(employee_chunks(session, eid))
        named["employee_id"] = eid
    years = [int(y) for y in (gate.get("years") or []) if str(y).isdigit()]
    if years:
        ys = set(years)
        sets.append({c for c, f in facts.items() if ys & set(f["years"])})
        named["years"] = years
    if not sets:
        return None, named
    scope = set.intersection(*sets)
    return scope, named


def share_of(ti: int, scope: set, tag_chunks: dict) -> float:
    chunks = tag_chunks.get(ti, ())
    if not chunks:
        return 0.0
    return len(scope & chunks) / len(chunks)


def score_chunk(cid: str, g: dict, P: np.ndarray, m: float, scope, shares: dict) -> dict:
    idx = g["chunk_tags"].get(cid)
    if not idx:
        return {"tags": 0}
    E = g["T"][idx]                                  # n x d
    C = E @ E.T                                      # n x n
    W = np.maximum(C - m, 0.0)                       # excess similarity, diagonal 1 - m
    F = _unit(W @ E)                                 # faces, n x d
    tag_cos = E @ P.T                                # n x p
    face_cos = F @ P.T                               # n x p
    tag_best = tag_cos.max(axis=1)                   # per tag, over phrases
    face_best = face_cos.max(axis=1)
    out = {
        "tags": len(idx),
        "tag_cos": float(tag_best.max()),
        "face_cos": float(face_best.max()),
        "tag_cos_mean": float(tag_cos.max(axis=0).mean()),   # per phrase best, mean over phrases
        "face_cos_mean": float(face_cos.max(axis=0).mean()),
        "face_gain": float(face_best.max() - tag_best.max()),
        "best_tag": g["names"][idx[int(face_best.argmax())]],
    }
    if scope is not None:
        sh = np.array([shares.setdefault(ti, share_of(ti, scope, g["tag_chunks"])) for ti in idx])
        out["share_max"] = float(sh.max())
        out["share_of_best"] = float(sh[int(face_best.argmax())])
        out["face_share"] = float((face_best * sh).max())
        out["tag_share"] = float((tag_best * sh).max())
        out["in_scope"] = cid in scope
    return out


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, cwd=ROOT, check=True).stdout.strip()
    except Exception:
        return "unknown"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, help="run folder holding arm_outputs.jsonl")
    ap.add_argument("--out", default=None, help="output folder (default output/face_scope/<run>)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--pairs", type=int, default=PAIRS)
    args = ap.parse_args()

    run = Path(args.run)
    out = Path(args.out) if args.out else ROOT / "output" / "face_scope" / run.name
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    _say(f"measure_face_scope: run={run.name} db={DATABASE} -> {out}")

    lines = [json.loads(l) for l in (run / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    _say(f"  {len(lines)} questions in the run")

    drv = _driver()
    rows_path = out / "candidates.jsonl"
    per_q = []
    with drv.session(database=DATABASE) as s, rows_path.open("w", encoding="utf-8") as fh:
        g = load_graph(s)
        bg = background(g["T"], args.seed, args.pairs)
        m = bg["median"]
        _say(f"background tag-tag cosine: median {m:.4f} (p10 {bg['p10']:.4f}, p90 {bg['p90']:.4f}, "
             f"{bg['pairs']} pairs, seed {args.seed})")
        channel_ids = _channel_names(s, CORPUS_ROOT)

        embed_calls = 0
        for qi, line in enumerate(lines):
            qid = line["id"]
            meta = line["meta"]
            plan = meta["plan"]
            if "ranking" in meta:
                ranking = meta["ranking"]
            elif "door_trace" in meta:
                # artefact_v2 with HERB_DOOR_TRACE=1: every candidate, best-first by total
                ranking = {"chunk_ids": [d["chunkId"] for d in meta["door_trace"]],
                           "scores": [d["total"] for d in meta["door_trace"]]}
            else:
                raise SystemExit(
                    f"question {qid}: the run stored no candidate ranking (no meta.ranking, "
                    f"no meta.door_trace) — rerun the arm with HERB_DOOR_TRACE=1")
            texts = [plan["description"]] + [_readable(p["t"]) for p in plan["parts"]] + [line["question"]]
            qmat, calls, _, _, _ = _embed_cached(texts, "query")
            embed_calls += calls
            P = _unit(np.asarray(qmat, dtype=np.float32))
            scope, named = stated_scope(s, plan.get("gate") or {}, g["facts"], channel_ids)
            shares: dict = {}
            kept = (meta.get("char_budget") or {}).get("kept")
            n_in = 0
            for rank, (cid, sc) in enumerate(zip(ranking["chunk_ids"], ranking["scores"]), start=1):
                row = {"id": qid, "chunk_id": cid, "arm_rank": rank, "arm_score": sc}
                row.update(score_chunk(cid, g, P, m, scope, shares))
                n_in += int(bool(row.get("in_scope")))
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            per_q.append({"id": qid, "candidates": len(ranking["chunk_ids"]), "kept": kept,
                          "phrases": len(texts), "scope": named,
                          "scope_size": None if scope is None else len(scope),
                          "candidates_in_scope": None if scope is None else n_in})
            if (qi + 1) % 10 == 0 or qi == 0:
                _say(f"  {qi + 1}/{len(lines)} questions  ({time.perf_counter() - t0:.0f}s)")
    drv.close()

    manifest = {
        "run": str(run), "database": DATABASE, "run_id": RUN_ID,
        "tags": int(len(g["T"])), "edges": int(sum(len(v) for v in g["chunk_tags"].values())),
        "background": bg, "embed_calls": embed_calls,
        "questions": per_q,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "commit": git_commit(), "elapsed_s": round(time.perf_counter() - t0, 1),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    with_scope = [q for q in per_q if q["scope_size"] is not None]
    _say(f"done: {sum(q['candidates'] for q in per_q)} candidate rows, "
         f"{len(with_scope)}/{len(per_q)} questions with a stated scope, "
         f"embed calls {embed_calls}, {manifest['elapsed_s']}s -> {rows_path}")


if __name__ == "__main__":
    main()

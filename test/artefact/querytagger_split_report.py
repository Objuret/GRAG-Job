"""The split check's report: what the forty calls on disk say, with no model call of its own.

Reads `output/querytagger_split/<day>/` and writes REPORT.md beside it. The embedder is the
harness's own, local, through the arm's on-disk vector cache; the graph's candidate tag pool is
the arm's (`artefact_v3._ALL_TAGS_CYPHER`, product-linked, the Product-name tags dropped), and
the pick band is the arm's paraphrase rule floored at COS_NOISE. Questions are q01..q10 and no
question text is printed.
"""
from __future__ import annotations

import argparse
import json
import sys
from itertools import combinations
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DIR = ROOT / "output" / "querytagger_split" / "2026-09-21"


def rankdata(a: np.ndarray) -> np.ndarray:
    """ranks with ties averaged"""
    a = np.asarray(a, dtype=np.float64)
    order = np.argsort(a, kind="stable")
    ranks = np.empty(len(a), dtype=np.float64)
    ranks[order] = np.arange(1, len(a) + 1, dtype=np.float64)
    s = a[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j + 2) / 2.0
        i = j + 1
    return ranks


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    rx, ry = rankdata(x), rankdata(y)
    rx = rx - rx.mean()
    ry = ry - ry.mean()
    d = float(np.linalg.norm(rx) * np.linalg.norm(ry))
    return float(rx @ ry / d) if d else float("nan")


def q(a: list, p: float) -> float:
    return float(np.percentile(np.asarray(a, dtype=np.float64), p)) if a else float("nan")


def fmt(v, nd=3) -> str:
    if v is None:
        return "—"
    if isinstance(v, float) and np.isnan(v):
        return "—"
    return f"{v:.{nd}f}" if isinstance(v, float) else str(v)


def table(head: list, rows: list) -> str:
    out = ["| " + " | ".join(head) + " |",
           "|" + "|".join(["---"] * len(head)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def load_calls(day_dir: Path) -> dict:
    calls = {}
    for path in sorted(day_dir.glob("q*.json")):
        body = json.loads(path.read_text(encoding="utf-8"))
        calls[(body["question_id"], body["stage"], body["ask"])] = body
    return calls


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="the split check's report")
    ap.add_argument("--dir", default=str(DEFAULT_DIR))
    args = ap.parse_args(argv)
    day_dir = Path(args.dir)
    print(f"querytagger split report | {day_dir}", flush=True)

    sys.path.insert(0, str(ROOT / "prod"))
    sys.path.insert(0, str(ROOT / "test"))
    from arms.artefact_v2 import (_driver, _embed_cached, _interp_key, _interpret_cached,
                                  _readable, _unit)
    import arms.artefact_v3 as v3
    from artefact.querytagger import SPLIT_FACETS

    calls = load_calls(day_dir)
    manifest = json.loads((day_dir / "manifest.json").read_text(encoding="utf-8"))
    ids = sorted({k[0] for k in calls})
    print(f"  {len(calls)} call files, {len(ids)} questions", flush=True)

    gen = {(qid, a): calls[(qid, "G", a)] for qid in ids for a in ("g1", "g2")
           if (qid, "G", a) in calls}
    sco = {(qid, a): calls[(qid, "S", a)] for qid in ids for a in ("s1", "s2")
           if (qid, "S", a) in calls}

    # ---------------------------------------------------------------- embeddings, local
    texts = []
    for qid in ids:
        for a in ("g1", "g2"):
            row = gen.get((qid, a))
            if row and row["ok"]:
                texts.append(row["parsed"]["description"])
                texts += [_readable(t) for t in row["parsed"]["tags"]]
        row = gen.get((qid, "g1"))
        if row:
            texts.append(row["input"]["question"])
    texts = list(dict.fromkeys(texts))
    print(f"  embedding {len(texts)} query-side texts (local, cached) …", flush=True)
    mat, ecalls, _, _, esecs = _embed_cached(texts, "query")
    print(f"  embedder: {ecalls} batch(es), {esecs:.1f}s", flush=True)
    vec = {t: _unit(np.asarray(r, dtype=np.float64)) for t, r in zip(texts, mat)}

    # ---------------------------------------------------------------- the graph's tag pool
    print("  loading the arm's candidate tag pool from the graph …", flush=True)
    drv = _driver()
    names, tvecs = [], []
    with drv.session(database=v3.DATABASE) as s:
        for rec in s.run(v3._ALL_TAGS_CYPHER, runId=v3.RUN_ID):
            names.append(rec["name"])
            tvecs.append(np.asarray(rec["emb"], dtype=np.float32))
        prod_names = {str(r["name"]).strip().lower()
                      for r in s.run(v3._PRODUCT_NAMES_CYPHER) if r["name"]}
        chunk_vecs = []
        for rec in s.run(v3._ALL_CHUNKS_CYPHER, datasetId=v3.DATASET_ID,
                         excludedSections=v3._EXCLUDED_PARAM):
            chunk_vecs.append(np.asarray(rec["emb"], dtype=np.float32))
    is_product = np.fromiter((n.strip().lower() in prod_names for n in names),
                             dtype=bool, count=len(names))
    keep = ~is_product
    T = _unit(np.stack(tvecs).astype(np.float64))[keep]
    C = _unit(np.stack(chunk_vecs).astype(np.float64))
    pool = int(keep.sum())
    print(f"  {len(names)} tags, {int(is_product.sum())} carry a Product name -> pool {pool}; "
          f"{len(C)} chunk descriptions", flush=True)

    # ---------------------------------------------------------------- A: generation
    a_rows, reach_rows = [], []
    for qid in ids:
        r1, r2 = gen.get((qid, "g1")), gen.get((qid, "g2"))
        if not (r1 and r1["ok"] and r2 and r2["ok"]):
            a_rows.append([qid] + ["—"] * 9)
            continue
        p1, p2 = r1["parsed"], r2["parsed"]
        d1, d2 = vec[p1["description"]], vec[p2["description"]]
        raw = vec[r1["input"]["question"]]
        t1 = [_readable(t) for t in p1["tags"]]
        t2 = [_readable(t) for t in p2["tags"]]
        M1 = np.stack([vec[t] for t in t1])
        M2 = np.stack([vec[t] for t in t2])
        cross = M1 @ M2.T
        best12 = cross.max(axis=1)
        best21 = cross.max(axis=0)
        both = np.concatenate([best12, best21])
        shared = len(set(p1["tags"]) & set(p2["tags"]))
        a_rows.append([qid, fmt(float(d1 @ d2)), len(p1["tags"]), len(p2["tags"]), shared,
                       fmt(float(np.median(both))), fmt(float(both.min())),
                       fmt(float((both >= 0.9).mean())), fmt(float((both >= 0.8).mean())),
                       fmt(float((both >= 0.7).mean()))])

        row = [qid]
        for dv, tags in ((d1, t1), (d2, t2)):
            band = max(v3.paraphrase_band(C, dv, raw), v3.COS_NOISE)
            sets = {0: set(), 1: set(), 2: set()}
            for t in tags:
                steps = v3.band_steps(T @ vec[t], band)
                for L in (0, 1, 2):
                    sets[L].update(np.flatnonzero(steps <= L).tolist())
            row.append(band)
            row.append(sets)
        reach_rows.append(row)

    # ---------------------------------------------------------------- B: scoring
    b_rows = []
    all_vals = {f: [] for f in SPLIT_FACETS}
    per_facet_delta = {f: [] for f in SPLIT_FACETS}
    per_facet_changed = {f: [0, 0] for f in SPLIT_FACETS}
    argmax_kept = [0, 0]
    facet_pair_flip = [0, 0]
    facet_pair_strict = [0, 0]
    tag_pair_flip = {f: [0, 0] for f in SPLIT_FACETS}
    c_rows = []
    for qid in ids:
        r1, r2 = sco.get((qid, "s1")), sco.get((qid, "s2"))
        if not (r1 and r1["ok"] and r2 and r2["ok"]):
            b_rows.append([qid] + ["—"] * 4)
            continue
        A = np.array([[row["facets"][f] for f in SPLIT_FACETS] for row in r1["parsed"]["tags"]])
        B = np.array([[row["facets"][f] for f in SPLIT_FACETS] for row in r2["parsed"]["tags"]])
        for j, f in enumerate(SPLIT_FACETS):
            d = np.abs(A[:, j] - B[:, j])
            per_facet_delta[f] += d.tolist()
            per_facet_changed[f][0] += int((d > 0).sum())
            per_facet_changed[f][1] += len(d)
            all_vals[f] += A[:, j].tolist()
        # within a tag: the order of two facets
        for i in range(len(A)):
            for x, y in combinations(range(len(SPLIT_FACETS)), 2):
                c1 = np.sign(A[i, x] - A[i, y])
                c2 = np.sign(B[i, x] - B[i, y])
                facet_pair_flip[1] += 1
                facet_pair_strict[1] += 1
                if c1 != c2:
                    facet_pair_flip[0] += 1
                if c1 * c2 == -1:
                    facet_pair_strict[0] += 1
            argmax_kept[1] += 1
            if int(np.argmax(A[i])) == int(np.argmax(B[i])):
                argmax_kept[0] += 1
        # within a facet: the order of two tags
        for j, f in enumerate(SPLIT_FACETS):
            for x, y in combinations(range(len(A)), 2):
                tag_pair_flip[f][1] += 1
                if np.sign(A[x, j] - A[y, j]) != np.sign(B[x, j] - B[y, j]):
                    tag_pair_flip[f][0] += 1
        b_rows.append([qid, len(A),
                       fmt(float(np.mean(np.abs(A - B) > 0))),
                       fmt(float(np.median(np.abs(A - B)))),
                       fmt(float(np.abs(A - B).max()))])
        c_rows.append([qid, len(A)] + [f"{len(set(A[:, j].tolist()))} / "
                                       f"{A[:, j].min():.2f}–{A[:, j].max():.2f}"
                                       for j in range(len(SPLIT_FACETS))])

    # ---------------------------------------------------------------- D: the old description
    d_rows = []
    for qid in ids:
        r1 = gen.get((qid, "g1"))
        if not (r1 and r1["ok"]):
            d_rows.append([qid, "—", "—"])
            continue
        # the cached pass-1 plan only: a miss would be a model call, which this report does
        # not make, so a missing file is reported as missing and nothing is asked
        key = _interp_key(r1["input"]["question"], v3.INTERPRET_MODEL)
        if not (v3.INTERP_CACHE_DIR / f"{key}.json").is_file():
            d_rows.append([qid, "—", "no cached pass-1 plan on disk; nothing asked"])
            continue
        plan, nc, _, _, _ = _interpret_cached(r1["input"]["question"], v3.INTERPRET_MODEL)
        old = plan.get("description")
        if not old:
            d_rows.append([qid, "—", f"cached plan carries no description (calls {nc})"])
            continue
        if old not in vec:
            m, _, _, _, _ = _embed_cached([old], "query")
            vec[old] = _unit(np.asarray(m[0], dtype=np.float64))
        d_rows.append([qid, fmt(float(vec[r1["parsed"]["description"]] @ vec[old])),
                       f"{nc}"])

    # ---------------------------------------------------------------- write
    lines = []
    w = lines.append
    w("# The querytagger split check — 2026-09-21")
    w("")
    w("The query side asked in two calls instead of one: stage G (GENERATE) writes the "
      "description and the tags from the question; stage S (SCORE) weighs g1's tags against "
      "g1's description through the five facets, never seeing the question. Each stage asked "
      "twice as independent calls. Ten 10smoke questions, identified q01..q10 in the order "
      "`data/10smoke.jsonl` lists them. No question text, no gold field, no reference and no "
      "recall was opened. Model calls in this report: 0.")
    w("")
    w(f"Prompts: GENERATE sha256 `{manifest['generate_system_sha256']}`, "
      f"SCORE sha256 `{manifest['score_system_sha256']}`. "
      f"Model `{manifest['model']}`. Facets, by column: {', '.join(SPLIT_FACETS)}.")
    w("")
    w(f"Graph pool for the reach: `herb-eval-volmax`, the arm's own tag Cypher — "
      f"{len(names)} product-linked embedded tags, {int(is_product.sum())} of them a Product "
      f"node's name and dropped, leaving **{pool}**; {len(C)} chunk descriptions carry the "
      f"paraphrase band.")
    w("")

    w("## A — generation stability (g1 vs g2)")
    w("")
    w(table(["q", "description cos", "tags g1", "tags g2", "shared by exact string",
             "soft match median", "min", "share >= 0.9", ">= 0.8", ">= 0.7"], a_rows))
    w("")
    w("Soft match: for every g1 tag its best cosine to any g2 tag and for every g2 tag its "
      "best to any g1 tag, pooled (2n values per question).")
    w("")
    w("### A2 — the graph reach of each ask's tags")
    w("")
    w("Per query tag, the graph tags whose cosine sits within L pick bands of that query "
      "tag's best graph tag, unioned over the ask's tags. The band is the arm's paraphrase "
      "rule computed with that ask's own description against the raw question, floored at "
      "COS_NOISE 0.002.")
    w("")
    rr = []
    for row in reach_rows:
        qid, b1, s1, b2, s2 = row
        cells = [qid, fmt(b1, 4), fmt(b2, 4)]
        for L in (0, 1, 2):
            a, b = s1[L], s2[L]
            j = len(a & b) / len(a | b) if (a | b) else float("nan")
            cells += [len(a), len(b), fmt(j)]
        rr.append(cells)
    w(table(["q", "band g1", "band g2",
             "L0 g1", "L0 g2", "L0 Jaccard",
             "L1 g1", "L1 g2", "L1 Jaccard",
             "L2 g1", "L2 g2", "L2 Jaccard"], rr))
    w("")

    w("## B — scoring stability (s1 vs s2, identical description and identical tags)")
    w("")
    w(table(["q", "tags", "share of the 5n values changed", "median abs delta",
             "max abs delta"], b_rows))
    w("")
    pf = []
    for f in SPLIT_FACETS:
        d = per_facet_delta[f]
        ch, n = per_facet_changed[f]
        pf.append([f, n, fmt(ch / n if n else float("nan")), fmt(q(d, 50)), fmt(q(d, 90)),
                   fmt(max(d) if d else float("nan"))])
    w(table(["facet", "values", "share changed", "median abs delta", "p90 abs delta",
             "max abs delta"], pf))
    w("")
    w("### B2 — reversals")
    w("")
    rev = [["within a tag: facet pairs whose order flips (ties counted apart)",
            facet_pair_flip[1], fmt(facet_pair_flip[0] / facet_pair_flip[1])],
           ["within a tag: facet pairs that strictly reverse",
            facet_pair_strict[1], fmt(facet_pair_strict[0] / facet_pair_strict[1])],
           ["per tag: the argmax facet kept", argmax_kept[1],
            fmt(argmax_kept[0] / argmax_kept[1])]]
    for f in SPLIT_FACETS:
        n0, n = tag_pair_flip[f]
        rev.append([f"within {f}: tag pairs of one question whose order flips", n,
                    fmt(n0 / n) if n else "—"])
    w(table(["reversal", "pairs", "share"], rev))
    w("")

    w("## C — the shape of the values (s1)")
    w("")
    pooled = np.array([all_vals[f] for f in SPLIT_FACETS]).T if all_vals[SPLIT_FACETS[0]] \
        else np.zeros((0, len(SPLIT_FACETS)))
    lattice = np.isclose(np.round(pooled / 0.05) * 0.05, pooled, atol=1e-9)
    top_is_one = float((pooled.max(axis=1) == 1.0).mean()) if len(pooled) else float("nan")
    shape = []
    for j, f in enumerate(SPLIT_FACETS):
        col = pooled[:, j]
        shape.append([f, len(set(col.tolist())), fmt(float(lattice[:, j].mean())),
                      fmt(float(col.mean())), fmt(float(np.median(col))),
                      fmt(float(col.min())), fmt(float(col.max())),
                      fmt(float((col == 1.0).mean())), fmt(float((col == 0.0).mean()))])
    w(table(["facet", "distinct values", "on the 0.05 lattice", "mean", "median", "min",
             "max", "share = 1.00", "share = 0.00"], shape))
    w("")
    w(f"Over all {len(pooled)} (question, tag) rows: "
      f"{len(set(pooled.ravel().tolist()))} distinct values in all five columns together, "
      f"{float(lattice.mean()):.3f} of the {pooled.size} values on the 0.05 lattice, "
      f"{top_is_one:.3f} of tags whose highest facet is exactly 1.00.")
    w("")
    w("### C2 — per question per facet: distinct values / range across that question's tags")
    w("")
    w(table(["q", "tags"] + list(SPLIT_FACETS), c_rows))
    w("")
    w("### C3 — Spearman between the five columns over all (question, tag) rows")
    w("")
    sp = []
    for i, f in enumerate(SPLIT_FACETS):
        sp.append([f] + [fmt(spearman(pooled[:, i], pooled[:, j])) if len(pooled) else "—"
                         for j in range(len(SPLIT_FACETS))])
    w(table(["", *SPLIT_FACETS], sp))
    w("")

    w("## D — g1's description against the cached pass-1 description the arm uses")
    w("")
    w(table(["q", "cosine", "model calls made to read the cached plan"], d_rows))
    w("")

    w("## E — costs")
    w("")
    stage = {}
    for (qid, st, a), body in calls.items():
        s = stage.setdefault(st, {"calls": 0, "reasks": 0, "failures": 0,
                                  "tokens_in": 0, "tokens_out": 0, "seconds": 0.0})
        s["calls"] += body["tries"]
        s["reasks"] += body["tries"] - 1
        s["failures"] += 0 if body["ok"] else 1
        s["tokens_in"] += body["tokens_in"]
        s["tokens_out"] += body["tokens_out"]
        s["seconds"] += body["seconds"]
    e = []
    for st in sorted(stage):
        s = stage[st]
        e.append([st, s["calls"], s["reasks"], s["failures"], f"{s['tokens_in']:,}",
                  f"{s['tokens_out']:,}", f"{s['seconds']:.0f}",
                  f"{s['tokens_in'] / max(1, s['calls']):,.0f}"])
    tot = {k: sum(s[k] for s in stage.values()) for k in
           ("calls", "reasks", "failures", "tokens_in", "tokens_out", "seconds")}
    e.append(["both", tot["calls"], tot["reasks"], tot["failures"], f"{tot['tokens_in']:,}",
              f"{tot['tokens_out']:,}", f"{tot['seconds']:.0f}",
              f"{tot['tokens_in'] / max(1, tot['calls']):,.0f}"])
    w(table(["stage", "calls", "re-asks", "failures", "tokens in", "tokens out",
             "seconds summed", "tokens in per call"], e))
    w("")
    w(f"Wall of the run: {manifest['wall_seconds']} s at {manifest['workers']} workers. "
      f"The input tokens are as the headless CLI counts them — its own agent preamble plus "
      f"cache-creation and cache-read tokens are inside every call.")
    w("")

    (day_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  wrote {day_dir / 'REPORT.md'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

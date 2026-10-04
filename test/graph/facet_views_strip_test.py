"""The instrument alone: does cos(tag, view) register the removal of the edit's words from the
VIEW itself? A controlled test for the facet-view pilot (`output/facet_views/PROGRESS.md`).

`facet_views_coverage.py` found which content words a counterfactual's edit removed and which
of those the write-1 view of the original C carries. Here, for every such row, the words the view
carries are struck out of the view text (whole-word, case-insensitive, whitespace collapsed) and
the cosine of the tag against the struck view is read against the cosine on the untouched view:

    Δ_strip  = cos(E(T), E(view))  −  cos(E(T), E(view minus the edit's words))
    Δ_random = the same with an equal NUMBER of other content words of the view struck at random
               (seeded; the control for "removing any k words moves the cosine")

If Δ_strip sits inside the writer's own noise band and beside Δ_random, the cosine of a phrase
against a 50-word view cannot register the facet's words even when the view carries them — the
instrument, not the writer. If Δ_strip clears the band and Δ_random does not, the instrument
would register the facet and the loss is upstream (coverage, following). Two modes:

    --strings-out  writes every struck string as {"sha","text"} for facet_embed_gpu.py
    --vectors      reads the vectors back and prints the table (per facet: n, median and p95 of
                   Δ_strip and Δ_random, share of Δ_strip above a band given with --band-p95, and
                   the paired share Δ_strip > Δ_random)

    python test/graph/facet_views_strip_test.py --rows output/facet_views/pilot/check_w1/coverage_chunk_w1.jsonl --texts output/facet_views/pilot/texts.jsonl --strings-out out.jsonl
    python test/graph/facet_views_strip_test.py --rows ... --texts ... --vectors v.npz [--vectors w.npz] --band temporal=0.02,why=0.02,...
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "prod", ROOT / "test"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from graph.facet_edits import FACETS  # noqa: E402
from graph.facet_views_coverage import STOP, WORD, sha256_of, words  # noqa: E402


def strike(text: str, drop: set) -> str:
    """Whole-word, case-insensitive removal of every word in `drop`; whitespace collapsed."""
    if not drop:
        return text
    pat = re.compile(r"\b(" + "|".join(re.escape(w) for w in sorted(drop, key=len, reverse=True))
                     + r")\b", re.IGNORECASE)
    out = pat.sub(" ", text)
    return re.sub(r"\s+", " ", out).strip()


def random_drop(text: str, k: int, avoid: set, rng: random.Random) -> set:
    pool = sorted({w for w in WORD.findall(text.lower()) if w not in STOP and w not in avoid})
    if k <= 0 or not pool:
        return set()
    return set(rng.sample(pool, min(k, len(pool))))


def read_rows(path: Path) -> list:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def q(a, p):
    a = np.sort(np.asarray(a, dtype=float))
    if a.size == 0:
        return float("nan")
    return float(a[int(round(p * (a.size - 1)))])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="strip the edit's words from the view itself")
    ap.add_argument("--rows", required=True, help="coverage rows jsonl (facet_views_coverage)")
    ap.add_argument("--texts", required=True)
    ap.add_argument("--strings-out", default="")
    ap.add_argument("--vectors", action="append", default=[])
    ap.add_argument("--band", default="", help="facet=p95 noise band per facet, comma separated")
    ap.add_argument("--seed", type=int, default=20260918)
    ap.add_argument("--rows-out", default="")
    args = ap.parse_args(argv)

    rows = [r for r in read_rows(Path(args.rows)) if r.get("removed_in_view_C")]
    rng = random.Random(args.seed)
    plan = []
    for r in rows:
        view = r["view_C"]
        drop = set(r["removed_in_view_C"])
        struck = strike(view, drop)
        rnd = random_drop(view, len(drop), drop, rng)
        struck_rnd = strike(view, rnd)
        if struck == view.strip() or struck_rnd == view.strip():
            continue
        plan.append({**{k: r[k] for k in ("chunk_id", "tag", "facet", "generation")},
                     "view": view, "drop": sorted(drop), "struck": struck,
                     "random_drop": sorted(rnd), "struck_random": struck_rnd})
    print(f"strip test | rows with the edit's words in the view: {len(rows)} | usable {len(plan)}")

    if args.strings_out:
        need = {}
        for p in plan:
            for s in (p["view"], p["struck"], p["struck_random"], p["tag"]):
                need.setdefault(sha256_of(s), s)
        out = Path(args.strings_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            for sha, s in need.items():
                f.write(json.dumps({"sha": sha, "text": s}, ensure_ascii=False) + "\n")
        print(f"-> {out} ({len(need)} strings)")
        return 0

    vec = {}
    for path in args.vectors:
        z = np.load(path, allow_pickle=False)
        m = np.asarray(z["vec"], dtype=np.float32)
        m /= np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-12)
        for sha, v in zip(z["sha"], m):
            vec[str(sha)] = v
    band = {}
    if args.band:
        for part in args.band.split(","):
            k, v = part.split("=")
            band[k.strip()] = float(v)

    def cos(a: str, b: str) -> float:
        return float(np.dot(vec[sha256_of(a)], vec[sha256_of(b)]))

    per = defaultdict(list)
    detail = []
    missing = 0
    for p in plan:
        try:
            base = cos(p["tag"], p["view"])
            d_strip = base - cos(p["tag"], p["struck"])
            d_rand = base - cos(p["tag"], p["struck_random"])
        except KeyError:
            missing += 1
            continue
        per[p["facet"]].append((d_strip, d_rand, len(p["drop"])))
        detail.append({**p, "cos_base": base, "d_strip": d_strip, "d_random": d_rand})
    if missing:
        print(f"  {missing} rows lacked a vector")
    print("| facet | n | words struck (median) | median Δ_strip | p95 Δ_strip | median Δ_random "
          "| p95 Δ_random | P(Δ_strip > Δ_random) | band p95 | share Δ_strip > band "
          "| share Δ_random > band |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for f in FACETS:
        a = per.get(f, [])
        if not a:
            print(f"| {f} | 0 | — | — | — | — | — | — | — | — | — |")
            continue
        ds = np.array([x[0] for x in a])
        dr = np.array([x[1] for x in a])
        k = np.median([x[2] for x in a])
        win = float(np.mean((ds > dr) + 0.5 * (ds == dr)))
        b = band.get(f)
        sb = f"{b:.4f}" if b is not None else "—"
        s1 = f"{float(np.mean(ds > b)):.3f}" if b is not None else "—"
        s2 = f"{float(np.mean(dr > b)):.3f}" if b is not None else "—"
        print(f"| {f} | {len(a)} | {k:.0f} | {np.median(ds):.4f} | {q(ds, 0.95):.4f} | "
              f"{np.median(dr):.4f} | {q(dr, 0.95):.4f} | {win:.3f} | {sb} | {s1} | {s2} |")
    if args.rows_out:
        out = Path(args.rows_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            for d in detail:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
        print(f"-> {out} ({len(detail)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

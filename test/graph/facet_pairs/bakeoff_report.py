"""The bake-off table and the winner, by the rule PROGRESS.md fixed before any result existed.

Reads every backbone cache present under `--cache-dir`, runs `cache_probe` on each with ONE
fixed seed, writes `results/<backbone>/probe.json` per candidate and one `REPORT.md`. It runs
with whatever caches are on disk and names the candidates that are missing.

The standard errors are a bootstrap over HELD-OUT CHUNKS, and the same resampled chunks are
used for every candidate in a draw, so the SE of a DIFFERENCE between two candidates is the
paired one the winner rule asks for.

The rule, verbatim from PROGRESS.md and implemented in `decide()`:

 1. "X beats Y on a criterion" means the difference is larger than three standard errors of the
    paired difference.
 2. A candidate is OUT if another candidate beats it on A, on B or on C while it beats that
    candidate on none of the three.
 3. Among the candidates left, the winner is the one with the highest A; if the top two are
    within three SE on A, the one with the lower C; if still within three SE, the one with the
    higher B; if still tied, the smaller cache.
 4. If no candidate beats the baseline on A, B or C, the baseline stays.
 5. D, E, F and G decide nothing, with one exception: a candidate whose D is not above zero by
    three SE on any facet is OUT.

Direction, stated here because the text does not spell it out: A higher is better, B higher is
better, C is a collapse EXCESS so lower is better. The order the three OUT/fallback clauses run
in is 5, then 2, then 4, then 3 — 5 and 2 remove candidates, 4 is the fallback when nothing
displaced the baseline, and 3 picks among what is left. That ordering is this file's reading of
the rule; the rule itself fixes no order, and the clause that decided is printed.

    python test/graph/facet_pairs/bakeoff_report.py
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
for _p in (str(HERE), str(HERE.parent)):
    if _p not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from . import data as D
    from . import cache_probe as P
except ImportError:  # run as a script
    import data as D  # noqa: E402
    import cache_probe as P  # noqa: E402

FACETS = D.FACETS

BASELINE = "tasksource/deberta-small-long-nli"
EXPECTED = (BASELINE,
            "tasksource/deberta-base-long-nli",
            "Alibaba-NLP/gte-reranker-modernbert-base",
            "BAAI/bge-reranker-v2-m3")

MARGIN_SE = 3.0


# ---------------------------------------------------------------- per-cluster aggregates
#
# Every statistic is written as a weight vector over the held-out chunks times a small matrix
# of per-chunk sums, so one bootstrap draw is a handful of matrix-vector products rather than
# a pass over the items. A chunk drawn twice contributes its sums twice, which is what a
# cluster bootstrap means.

def _cell(items: list, clusters: dict, cols: list, colkey, fields) -> np.ndarray:
    out = np.zeros((len(clusters), len(cols), len(fields)), dtype=np.float64)
    ci = {c: i for i, c in enumerate(cols)}
    for it in items:
        j = ci.get(colkey(it))
        if j is None:
            continue
        i = clusters[it["cluster"]]
        for k, fn in enumerate(fields):
            out[i, j, k] += fn(it)
    return out


def agg_A(items: list, clusters: dict) -> np.ndarray:
    """(chunk, facet, [n_correct, n])."""
    return _cell(items, clusters, list(FACETS), lambda it: it["facet"],
                 [lambda it: int(it["correct"]), lambda it: 1])


def agg_C(items: list, clusters: dict, keys: list) -> np.ndarray:
    """(chunk, facet pair, [student_same, teacher_same, n])."""
    return _cell(items, clusters, keys, lambda it: it["facet_pair"],
                 [lambda it: int(it["student_same"]), lambda it: int(it["teacher_same"]),
                  lambda it: 1])


def agg_B(items: list, clusters: dict) -> tuple:
    """Flat pred / known arrays and the chunk index of each element."""
    pred = np.array([it["pred"] for it in items], dtype=np.float64)
    known = np.array([it["known"] for it in items], dtype=np.float64)
    ci = np.array([clusters[it["cluster"]] for it in items], dtype=np.int64)
    return pred, known, ci


def agg_D(items: list, clusters: dict) -> dict:
    """Per chunk: the edge count, the per-facet sum, sum of squares and within-chunk SS."""
    nc, nf = len(clusters), len(FACETS)
    by = {}
    for it in items:
        by.setdefault(clusters[it["cluster"]], []).append(it["values"])
    n = np.zeros(nc)
    s = np.zeros((nc, nf))
    sq = np.zeros((nc, nf))
    w = np.zeros((nc, nf))
    for i, rows in by.items():
        v = np.asarray(rows, dtype=np.float64)
        n[i] = v.shape[0]
        s[i] = v.sum(axis=0)
        sq[i] = (v ** 2).sum(axis=0)
        if v.shape[0] > 1:
            w[i] = ((v - v.mean(axis=0)) ** 2).sum(axis=0)
    return {"n": n, "sum": s, "sq": sq, "within": w}


# ---------------------------------------------------------------- the statistics

def stat_A(a: np.ndarray, w: np.ndarray):
    tot = np.tensordot(w, a, axes=(0, 0))          # facet x [correct, n]
    ok = tot[:, 1] > 0
    if not ok.any():
        return None
    return float(np.mean(tot[ok, 0] / tot[ok, 1]))


def stat_C(c: np.ndarray, w: np.ndarray):
    tot = np.tensordot(w, c, axes=(0, 0))          # facet pair x [stu, tea, n]
    ok = tot[:, 2] > 0
    if not ok.any():
        return None
    return float(np.mean((tot[ok, 0] - tot[ok, 1]) / tot[ok, 2]))


def stat_D(d: dict, w: np.ndarray) -> list:
    n = float(w @ d["n"])
    if n < 2:
        return [None] * len(FACETS)
    s = w @ d["sum"]
    sq = w @ d["sq"]
    within = w @ d["within"]
    total = sq - (s ** 2) / n
    return [float(within[i] / total[i]) if total[i] > 0 else None
            for i in range(len(FACETS))]


def _rankdata(a: np.ndarray) -> np.ndarray:
    """Average ranks, ties shared — vectorised, because the bootstrap calls this 40,000 times."""
    uniq, first, counts = np.unique(a, return_index=True, return_counts=True)
    # np.unique returns the values sorted, so `first` in SORTED order is the running offset
    starts = np.concatenate(([0], np.cumsum(counts)[:-1]))
    avg = starts + (counts - 1) / 2.0 + 1.0
    return avg[np.searchsorted(uniq, a)]


def stat_B(b: tuple, w: np.ndarray):
    pred, known, ci = b
    if len(pred) < 3:
        return None
    reps = w[ci].astype(np.int64)
    if reps.sum() < 3:
        return None
    p, k = np.repeat(pred, reps), np.repeat(known, reps)
    x, y = _rankdata(p), _rankdata(k)
    sx, sy = x.std(), y.std()
    if sx == 0 or sy == 0:
        return None
    return float(((x - x.mean()) * (y - y.mean())).mean() / (sx * sy))


# ---------------------------------------------------------------- the bootstrap

def bootstrap(candidates: dict, boot: int, seed: int) -> dict:
    """One resample of held-out chunks per draw, shared by every candidate.

    Returns point estimates, SEs, and the SE of every pairwise difference on A, B and C —
    the paired figure the winner rule reads.
    """
    names = list(candidates)
    keys = set()
    ckeys = set()
    for n in names:
        r = candidates[n]
        keys |= {it["cluster"] for it in r["A"]["items"]}
        keys |= {it["cluster"] for it in r["C"]["items"]}
        keys |= {it["cluster"] for it in r["B"]["items"]}
        keys |= {it["cluster"] for it in r["D"]["items"]}
        ckeys |= {it["facet_pair"] for it in r["C"]["items"]}
    clusters = {c: i for i, c in enumerate(sorted(keys))}
    ckeys = sorted(ckeys)
    nc = len(clusters)

    aggs = {n: {"A": agg_A(candidates[n]["A"]["items"], clusters),
                "C": agg_C(candidates[n]["C"]["items"], clusters, ckeys),
                "B": agg_B(candidates[n]["B"]["items"], clusters),
                "D": agg_D(candidates[n]["D"]["items"], clusters)} for n in names}

    ones = np.ones(nc, dtype=np.float64)
    point = {n: {"A": stat_A(aggs[n]["A"], ones), "B": stat_B(aggs[n]["B"], ones),
                 "C": stat_C(aggs[n]["C"], ones), "D": stat_D(aggs[n]["D"], ones)}
             for n in names}

    rng = np.random.default_rng(seed)
    draws = {n: {"A": [], "B": [], "C": [], "D": []} for n in names}
    for _ in range(boot):
        w = np.bincount(rng.integers(0, nc, nc), minlength=nc).astype(np.float64)
        for n in names:
            draws[n]["A"].append(stat_A(aggs[n]["A"], w))
            draws[n]["B"].append(stat_B(aggs[n]["B"], w))
            draws[n]["C"].append(stat_C(aggs[n]["C"], w))
            draws[n]["D"].append(stat_D(aggs[n]["D"], w))

    def _col(n, crit):
        return np.array([v for v in draws[n][crit] if v is not None], dtype=np.float64)

    se = {n: {} for n in names}
    for n in names:
        for crit in ("A", "B", "C"):
            col = _col(n, crit)
            se[n][crit] = float(col.std()) if len(col) > 1 else None
        dm = np.array([[np.nan if v is None else v for v in row]
                       for row in draws[n]["D"]], dtype=np.float64)
        se[n]["D"] = [float(np.nanstd(dm[:, i])) if dm.shape[0] > 1 else None
                      for i in range(len(FACETS))]

    diff_se = {}
    for crit in ("A", "B", "C"):
        for i, x in enumerate(names):
            for y in names[i + 1:]:
                dx, dy = draws[x][crit], draws[y][crit]
                d = np.array([a - b for a, b in zip(dx, dy)
                              if a is not None and b is not None], dtype=np.float64)
                diff_se[f"{crit}|{x}|{y}"] = float(d.std()) if len(d) > 1 else None
    return {"clusters": nc, "point": point, "se": se, "diff_se": diff_se,
            "boot": boot, "seed": seed, "facet_pairs": ckeys}


def diff_se_of(boot: dict, crit: str, x: str, y: str):
    return boot["diff_se"].get(f"{crit}|{x}|{y}", boot["diff_se"].get(f"{crit}|{y}|{x}"))


# ---------------------------------------------------------------- the frozen rule

HIGHER_IS_BETTER = {"A": True, "B": True, "C": False}


def beats(boot: dict, x: str, y: str, crit: str) -> bool:
    px, py = boot["point"][x][crit], boot["point"][y][crit]
    s = diff_se_of(boot, crit, x, y)
    if px is None or py is None or s is None or s <= 0:
        return False
    d = (px - py) if HIGHER_IS_BETTER[crit] else (py - px)
    return d > MARGIN_SE * s


def decide(boot: dict, cache_bytes: dict, baseline: str = BASELINE) -> dict:
    names = list(boot["point"])
    log = []

    # clause 5 — D not above zero by three SE on ANY facet
    out = set()
    for n in names:
        dv, ds = boot["point"][n]["D"], boot["se"][n]["D"]
        ok = any(v is not None and s is not None and s > 0 and v - MARGIN_SE * s > 0
                 for v, s in zip(dv, ds))
        if not ok:
            out.add(n)
            log.append(f"clause 5: {n} is OUT — D is not above zero by three SE on any facet")

    # clause 2 — dominated on A, B or C
    for x in names:
        if x in out:
            continue
        for y in names:
            if y == x:
                continue
            crits_y = [c for c in ("A", "B", "C") if beats(boot, y, x, c)]
            crits_x = [c for c in ("A", "B", "C") if beats(boot, x, y, c)]
            if crits_y and not crits_x:
                out.add(x)
                log.append(f"clause 2: {x} is OUT — {y} beats it on {'/'.join(crits_y)} "
                           f"and it beats {y} on none of A, B, C")
                break

    # clause 4 — nothing displaced the baseline
    if baseline in names:
        movers = [n for n in names if n != baseline
                  and any(beats(boot, n, baseline, c) for c in ("A", "B", "C"))]
        if not movers:
            log.append("clause 4: no candidate beats the baseline on A, B or C — "
                       "the baseline stays")
            return {"winner": baseline, "clause": 4, "out": sorted(out), "log": log}

    left = [n for n in names if n not in out]
    if not left:
        log.append("every candidate was removed; the baseline stays by clause 4")
        return {"winner": baseline, "clause": 4, "out": sorted(out), "log": log}

    winner, clause, tlog = tiebreak(boot, left, cache_bytes)
    log.extend(tlog)
    return {"winner": winner, "clause": clause, "out": sorted(out), "log": log}


def tiebreak(boot: dict, left: list, cache_bytes: dict) -> tuple:
    """Clause 3 alone: highest A, then the lower C, then the higher B, then the smaller cache.

    Reachability, stated: with clause 2 running first, a survivor that is beaten on B while
    beating nobody is already OUT, so in practice clause 3B only decides when clause 2 removed
    nothing — which is why this is its own function and is tested directly.
    """
    log = []
    left = list(left)
    left.sort(key=lambda n: (-(boot["point"][n]["A"] or -1), n))
    top = left[0]
    tied = [n for n in left[1:]
            if not beats(boot, top, n, "A") and not beats(boot, n, top, "A")]
    group = [top] + tied
    if len(group) == 1:
        log.append(f"clause 3 (A): {top} has the highest A and no other candidate is within "
                   f"three SE of it")
        return top, "3A", log
    log.append(f"clause 3: {len(group)} candidates are within three SE on A "
               f"({', '.join(group)})")
    group.sort(key=lambda n: (boot["point"][n]["C"] if boot["point"][n]["C"] is not None
                              else 1e9, n))
    tc = group[0]
    tied_c = [n for n in group[1:]
              if not beats(boot, tc, n, "C") and not beats(boot, n, tc, "C")]
    if not tied_c:
        log.append(f"clause 3 (C): {tc} has the lower collapse excess")
        return tc, "3C", log
    group2 = [tc] + tied_c
    group2.sort(key=lambda n: (-(boot["point"][n]["B"] if boot["point"][n]["B"] is not None
                                 else -1e9), n))
    tb = group2[0]
    tied_b = [n for n in group2[1:]
              if not beats(boot, tb, n, "B") and not beats(boot, n, tb, "B")]
    if not tied_b:
        log.append(f"clause 3 (B): {tb} has the higher known-topic Spearman")
        return tb, "3B", log
    group3 = sorted([tb] + tied_b, key=lambda n: (cache_bytes.get(n, 1 << 62), n))
    log.append(f"clause 3 (cache): still tied on A, C and B — the smaller cache decides "
               f"({group3[0]})")
    return group3[0], "3cache", log


# ---------------------------------------------------------------- rendering

def _f(v, nd=4):
    return "-" if v is None else f"%.{nd}f" % v


def render(results: dict, boot: dict, verdict: dict, missing: list, cfg: dict) -> str:
    names = list(results)
    L = ["# the backbone bake-off — the diagnostic table and the frozen winner rule", ""]
    L.append(f"Written {cfg['written']}. Caches read from `{cfg['cache_dir']}`. "
             f"Bootstrap B = {boot['boot']} over {boot['clusters']} held-out chunks, "
             f"seed {boot['seed']}; the same resampled chunks for every candidate, so the "
             f"standard error of a difference is paired.")
    if missing:
        L.append("")
        L.append("**Candidates with no cache on disk, so not in the table:** "
                 + ", ".join(f"`{m}`" for m in missing))
    L += ["", "## the table", "",
          "| candidate | selected head / variant | A macro ± SE | B Spearman ± SE | "
          "C excess ± SE | D min..max | F trunc | F s/1k | F cache MB (61,018) |",
          "|---|---|---|---|---|---|---|---|---|"]
    for n in names:
        r, p, s = results[n], boot["point"][n], boot["se"][n]
        dv = [v for v in p["D"] if v is not None]
        L.append(f"| {n} | {r['selected']['head']} / {r['selected']['variant']} | "
                 f"{_f(p['A'])} ± {_f(s['A'])} | {_f(p['B'])} ± {_f(s['B'])} | "
                 f"{_f(p['C'])} ± {_f(s['C'])} | "
                 f"{_f(min(dv), 3) if dv else '-'}..{_f(max(dv), 3) if dv else '-'} | "
                 f"{_f(r['F']['truncation_rate'], 3)} | "
                 f"{_f(r['F']['seconds_per_1000_edges'], 0)} | "
                 f"{r['F']['cache_mb_full_graph']} |")
    L += ["", "## A per facet (held-out, the selected combination)", "",
          "| candidate | " + " | ".join(FACETS) + " |",
          "|---|" + "---|" * len(FACETS)]
    for n in names:
        row = [_f(results[n]["A"]["per_facet"][f]["agreement"]) for f in FACETS]
        L.append(f"| {n} | " + " | ".join(row) + " |")
    L += ["", "## D per facet — the share of the output's variance between tags inside a chunk",
          "", "| candidate | " + " | ".join(FACETS) + " |", "|---|" + "---|" * len(FACETS)]
    for n in names:
        L.append(f"| {n} | " + " | ".join(
            f"{_f(v, 3)} ± {_f(s, 3)}" for v, s in
            zip(boot["point"][n]["D"], boot["se"][n]["D"])) + " |")
    L += ["", "## E — the mean |score gap| on pairs Opus decided against pairs it called equal",
          "", "| candidate | facet | decided | tied | difference |", "|---|---|---|---|---|"]
    for n in names:
        for f in FACETS:
            e = results[n]["E"][f]
            L.append(f"| {n} | {f} | {_f(e['mean_gap_decided'], 3)} | "
                     f"{_f(e['mean_gap_tied'], 3)} | {_f(e['difference'], 3)} |")
    g = [n for n in names if results[n].get("G")]
    if g:
        L += ["", "## G — the rerankers' own relevance logit alone", "",
              "| candidate | A macro | B Spearman |", "|---|---|---|"]
        for n in g:
            L.append(f"| {n} | {_f(results[n]['G']['A_macro'])} | "
                     f"{_f(results[n]['G']['B_spearman'])} |")
    L += ["", "## the \"beats\" matrix at three SE of the paired difference", "",
          "| criterion | X | Y | X − Y | SE of the difference | X beats Y |",
          "|---|---|---|---|---|---|"]
    for crit in ("A", "B", "C"):
        for i, x in enumerate(names):
            for y in names[i + 1:]:
                px, py = boot["point"][x][crit], boot["point"][y][crit]
                s = diff_se_of(boot, crit, x, y)
                d = None if px is None or py is None else px - py
                w = "X" if beats(boot, x, y, crit) else ("Y" if beats(boot, y, x, crit)
                                                         else "neither")
                L.append(f"| {crit} | {x} | {y} | {_f(d)} | {_f(s)} | {w} |")
    L += ["", "## the verdict", "",
          f"**Winner: `{verdict['winner']}`** — decided by clause {verdict['clause']} of the "
          f"rule fixed in PROGRESS.md on 2026-09-19, before any of these numbers existed.", ""]
    for line in verdict["log"]:
        L.append(f"* {line}")
    L += ["", "Only the winner gets the full 61,018-edge pass. D, E, F and G decide nothing "
          "except clause 5."]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- the run

def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="the bake-off table and the frozen winner rule")
    ap.add_argument("--cache-dir", default="output/facet_pairs/bakeoff/cache")
    ap.add_argument("--out", default="output/facet_pairs/bakeoff")
    ap.add_argument("--answers", default="output/facet_pairs/answers")
    ap.add_argument("--rows", default="output/facet_neural/rows_export.jsonl")
    ap.add_argument("--stats", default="output/facet_stats/herb-eval-volmax.jsonl")
    ap.add_argument("--edges", default="output/facet_pairs/bakeoff/edges.jsonl")
    ap.add_argument("--seed", type=int, default=P.SEED)
    ap.add_argument("--boot", type=int, default=P.BOOT)
    ap.add_argument("--topic-pairs", type=int, default=P.TOPIC_PAIRS)
    ap.add_argument("--max-epochs", type=int, default=P.MAX_EPOCHS)
    a = ap.parse_args(argv)

    t0 = time.perf_counter()
    print(f"bakeoff report | caches {a.cache_dir} | seed {a.seed} | B {a.boot}", flush=True)
    caches = sorted(Path(a.cache_dir).glob("*.npz")) if Path(a.cache_dir).is_dir() else []
    caches = [c for c in caches if not c.name.endswith(".part.npz")]
    if not caches:
        print(f"no caches under {a.cache_dir} — nothing to report", flush=True)
        return 1

    results = {}
    out_root = Path(a.out)
    for c in caches:
        r = P.run(str(c), a.answers, a.rows, a.stats, a.edges, a.seed, a.boot,
                  a.topic_pairs, max_epochs=a.max_epochs)
        results[r["candidate"]] = r
        d = out_root / "results" / r["candidate"].replace("/", "__")
        d.mkdir(parents=True, exist_ok=True)
        (d / "probe.json").write_text(json.dumps(r, indent=1), encoding="utf-8")

    missing = [m for m in EXPECTED if m not in results]
    if missing:
        print("missing candidates: " + ", ".join(missing), flush=True)

    print(f"bootstrapping B={a.boot} over held-out chunks", flush=True)
    boot = bootstrap(results, a.boot, a.seed)
    cache_bytes = {n: results[n]["F"]["cache_bytes_full_graph"] for n in results}
    verdict = decide(boot, cache_bytes)

    slim = {n: {k: v for k, v in results[n].items() if k not in ("A", "B", "C", "D")}
            for n in results}
    for n in results:
        slim[n]["A"] = {k: v for k, v in results[n]["A"].items() if k != "items"}
        slim[n]["B"] = {k: v for k, v in results[n]["B"].items() if k != "items"}
        slim[n]["C"] = {k: v for k, v in results[n]["C"].items() if k != "items"}
        slim[n]["D"] = {k: v for k, v in results[n]["D"].items() if k != "items"}
    summary = {"written": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "cache_dir": a.cache_dir, "seed": a.seed, "boot": a.boot,
               "missing": missing, "verdict": verdict,
               "bootstrap": {k: v for k, v in boot.items()},
               "candidates": slim}
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "results").mkdir(parents=True, exist_ok=True)
    (out_root / "results" / "summary.json").write_text(
        json.dumps(summary, indent=1), encoding="utf-8")
    cfg = {"written": summary["written"], "cache_dir": a.cache_dir}
    (out_root / "REPORT.md").write_text(
        render(results, boot, verdict, missing, cfg), encoding="utf-8")

    for n in results:
        p, s = boot["point"][n], boot["se"][n]
        print(f"  {n:<45} A {_f(p['A'])}±{_f(s['A'])} B {_f(p['B'])} C {_f(p['C'])}",
              flush=True)
    print(f"winner: {verdict['winner']} (clause {verdict['clause']})", flush=True)
    print(f"done | {time.perf_counter() - t0:.0f}s | -> {out_root / 'REPORT.md'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

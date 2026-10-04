"""The last step: read off the translation from the judge-derived scales into topic's numbers.

His correction, 2026-09-18. Opus compared pairs on all five facets without ever seeing a topic
number. Five latent scales came out of those choices alone (`train.py`, `score_all.py`). ONLY
NOW are the existing numeric topic values revealed. The mapping from the judge-derived topic
score to the real topic number is read off here, and that same mapping is applied to the other
four scales. This is the only module in the package that opens
`output/facet_stats/<db>.jsonl`; opening it anywhere on the training path would have made the
mapping circular.

Two mappings are emitted, side by side, labelled, and nothing is decided between them:

* **position** — the one he described ("learn rank-position -> Topic-number translation"). A
  column's value is expressed as its within-column position (its quantile over all the edges
  scored) and read off the topic curve at the SAME position. By construction every facet column
  then carries topic's own marginal distribution of mapped values; what differs between the
  columns is only which edge sits where. The test asserts that identity.
* **raw** — the isotonic curve applied to a facet's raw score directly. The five heads sit on
  one shared projection but nothing ties their output scales together, so a raw score of 0.4 on
  `why` is not a claim about the same quantity as 0.4 on `topic`. It is reported because it is
  the other honest reading, not because it is preferred.

The curve itself is isotonic regression (pool-adjacent-violators, Barlow et al. 1972) of the
known topic value on the judge-derived topic score, fitted on TRAINING-chunk edges only, so the
transfer numbers on HELD-OUT-chunk edges are a real out-of-sample reading: Spearman between the
topic score and the known topic, and MAE of the mapped value against the known one.

Nothing here goes to the graph.

    python test/graph/facet_pairs/map_topic.py --round 0 \\
        --scores output/facet_pairs/rounds/round0/scores.jsonl \\
        --topic output/facet_stats/herb-eval-volmax.jsonl
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
for _p in (str(HERE), str(HERE.parent)):
    if _p not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from . import data as D
    from .model import FACETS
except ImportError:  # run as a script on the desktop
    import data as D  # noqa: E402
    from model import FACETS  # noqa: E402

TOPIC = "topic"


# ---------------------------------------------------------------- the known values

def load_known_topic(facet_stats_jsonl: str) -> dict:
    """edge_id -> the known topic value. One row per (chunk_id, tag) in the stats file."""
    out = {}
    with open(facet_stats_jsonl, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("chunk_id") and r.get("tag") is not None and r.get(TOPIC) is not None:
                out[D.edge_id(r["chunk_id"], r["tag"])] = float(r[TOPIC])
    return out


# ---------------------------------------------------------------- isotonic regression

def pava(y: list, w: list | None = None) -> list:
    """Pool-adjacent-violators: the non-decreasing least-squares fit of `y` in its own order."""
    n = len(y)
    if n == 0:
        return []
    w = [1.0] * n if w is None else list(w)
    vals, wts, counts = [], [], []
    for i in range(n):
        v, ww, c = float(y[i]), float(w[i]), 1
        while vals and vals[-1] > v:
            pv, pw, pc = vals.pop(), wts.pop(), counts.pop()
            v = (pv * pw + v * ww) / (pw + ww)
            ww += pw
            c += pc
        vals.append(v)
        wts.append(ww)
        counts.append(c)
    out = []
    for v, c in zip(vals, counts):
        out.extend([v] * c)
    return out


class IsotonicCurve:
    """A non-decreasing step function fitted from (x, y) samples, evaluated by interpolation."""

    def __init__(self, xs: list, ys: list):
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        self.x = [float(xs[i]) for i in order]
        self.y = pava([ys[i] for i in order])

    def __call__(self, v: float) -> float:
        x, y = self.x, self.y
        if not x:
            return float("nan")
        if v <= x[0]:
            return y[0]
        if v >= x[-1]:
            return y[-1]
        lo, hi = 0, len(x) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if x[mid] <= v:
                lo = mid
            else:
                hi = mid
        if x[hi] == x[lo]:
            return y[hi]
        t = (v - x[lo]) / (x[hi] - x[lo])
        return y[lo] + t * (y[hi] - y[lo])

    def map_all(self, vs: list) -> list:
        return [self(v) for v in vs]


# ---------------------------------------------------------------- ranks and statistics

def ordinal_positions(values: list) -> tuple:
    """(rank + 0.5) / n, ascending, ties broken by index so the result is a permutation."""
    n = len(values)
    order = sorted(range(n), key=lambda i: (values[i], i))
    pos = [0.0] * n
    for r, i in enumerate(order):
        pos[i] = (r + 0.5) / n
    return pos, order


def spearman(x: list, y: list):
    if len(x) < 3:
        return None
    rx, ry = _ranks(x), _ranks(y)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    sx = statistics.pstdev(rx)
    sy = statistics.pstdev(ry)
    if sx == 0 or sy == 0:
        return None
    cov = statistics.fmean([(a - mx) * (b - my) for a, b in zip(rx, ry)])
    return cov / (sx * sy)


def _ranks(v: list) -> list:
    order = sorted(range(len(v)), key=lambda i: v[i])
    out = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        r = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            out[order[k]] = r
        i = j + 1
    return out


def dist(v: list) -> dict:
    if not v:
        return {"n": 0}
    s = sorted(v)

    def q(p):
        return s[min(len(s) - 1, int(round(p * (len(s) - 1))))]
    return {"n": len(s), "min": s[0], "p5": q(.05), "median": q(.5), "p95": q(.95),
            "max": s[-1], "distinct": len(set(s))}


def within_group_sd(values: list, keys: list) -> float | None:
    """Mean over groups of the sd inside the group; groups of one contribute nothing."""
    by = {}
    for v, k in zip(values, keys):
        by.setdefault(k, []).append(v)
    sds = [statistics.pstdev(g) for g in by.values() if len(g) > 1]
    return statistics.fmean(sds) if sds else None


def curve_table(scores: list, mapped: list, n_rows: int = 21) -> list:
    """Score quantile -> the topic value the curve gives there."""
    pairs = sorted(zip(scores, mapped))
    if not pairs:
        return []
    out = []
    for i in range(n_rows):
        p = i / (n_rows - 1)
        j = min(len(pairs) - 1, int(round(p * (len(pairs) - 1))))
        out.append({"quantile": round(p, 3), "score": pairs[j][0], "topic": pairs[j][1]})
    return out


# ---------------------------------------------------------------- the run

def build_layer(rows: list, known: dict) -> dict:
    """Everything the two mappings need, given the scored rows and the known topic values."""
    train_idx = [i for i, r in enumerate(rows)
                 if not D.is_heldout(r["chunk_id"]) and r["edge_id"] in known]
    held_idx = [i for i, r in enumerate(rows)
                if D.is_heldout(r["chunk_id"]) and r["edge_id"] in known]
    if len(train_idx) < 3:
        raise SystemExit("map_topic: fewer than three training-chunk edges carry a known "
                         "topic value; there is no curve to fit")

    curve = IsotonicCurve([rows[i][TOPIC] for i in train_idx],
                          [known[rows[i]["edge_id"]] for i in train_idx])

    topic_scores = [r[TOPIC] for r in rows]
    mapped_topic = curve.map_all(topic_scores)
    # The position ladder: topic's mapped values in ascending order. A facet's edge at
    # within-column position p reads the ladder at the same p.
    ladder = sorted(mapped_topic)

    positions, mapped_pos, mapped_raw = {}, {}, {}
    for f in FACETS:
        col = [r[f] for r in rows]
        pos, order = ordinal_positions(col)
        positions[f] = pos
        v = [0.0] * len(rows)
        for rank, i in enumerate(order):
            v[i] = ladder[rank]
        mapped_pos[f] = v
        mapped_raw[f] = curve.map_all(col)

    transfer = {"n_train_edges": len(train_idx), "n_heldout_edges": len(held_idx)}
    for name, idx in (("train", train_idx), ("heldout", held_idx)):
        if len(idx) < 3:
            transfer[name] = {"n": len(idx)}
            continue
        sc = [rows[i][TOPIC] for i in idx]
        kn = [known[rows[i]["edge_id"]] for i in idx]
        mp = [mapped_pos[TOPIC][i] for i in idx]
        mr = [mapped_raw[TOPIC][i] for i in idx]
        transfer[name] = {
            "n": len(idx),
            "spearman_score_vs_known": spearman(sc, kn),
            "mae_mapped_position_vs_known": statistics.fmean(
                abs(a - b) for a, b in zip(mp, kn)),
            "mae_mapped_raw_vs_known": statistics.fmean(abs(a - b) for a, b in zip(mr, kn)),
            "mae_constant_median_baseline": statistics.fmean(
                abs(statistics.median(kn) - b) for b in kn),
        }

    stats = {}
    tags = [r["tag"] for r in rows]
    chunks = [r["chunk_id"] for r in rows]
    for f in FACETS:
        stats[f] = {
            "score": dist([r[f] for r in rows]),
            "mapped_position": dist(mapped_pos[f]),
            "mapped_raw": dist(mapped_raw[f]),
            "within_tag_sd": within_group_sd(mapped_pos[f], tags),
            "within_chunk_sd": within_group_sd(mapped_pos[f], chunks),
        }
    known_col = [known.get(r["edge_id"]) for r in rows]
    have_known = [i for i, v in enumerate(known_col) if v is not None]
    stats["known_topic"] = {
        "value": dist([known_col[i] for i in have_known]),
        "within_tag_sd": within_group_sd([known_col[i] for i in have_known],
                                         [tags[i] for i in have_known]),
        "within_chunk_sd": within_group_sd([known_col[i] for i in have_known],
                                           [chunks[i] for i in have_known]),
    }

    cross = {}
    for i, a in enumerate(FACETS):
        for b in FACETS[i + 1:]:
            cross[f"{a}~{b}"] = spearman([r[a] for r in rows], [r[b] for r in rows])
    for f in FACETS:
        cross[f"{f}~known_topic"] = spearman([rows[i][f] for i in have_known],
                                             [known_col[i] for i in have_known])

    return {"curve": curve, "positions": positions, "mapped_position": mapped_pos,
            "mapped_raw": mapped_raw, "mapped_topic": mapped_topic, "known": known_col,
            "transfer": transfer, "stats": stats, "cross_spearman": cross,
            "curve_table": curve_table([rows[i][TOPIC] for i in train_idx],
                                       [curve(rows[i][TOPIC]) for i in train_idx])}


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="map the judge-derived scales into topic's numbers")
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--scores", default="", help="default <rounds-dir>/round<N>/scores.jsonl")
    ap.add_argument("--topic", default="output/facet_stats/herb-eval-volmax.jsonl")
    ap.add_argument("--rounds-dir", default="output/facet_pairs/rounds")
    ap.add_argument("--out", default="", help="default <rounds-dir>/round<N>/layer")
    args = ap.parse_args(argv)

    t0 = time.perf_counter()
    scores_path = Path(args.scores or f"{args.rounds_dir}/round{args.round}/scores.jsonl")
    out = Path(args.out or f"{args.rounds_dir}/round{args.round}/layer")
    out.mkdir(parents=True, exist_ok=True)
    print(f"facet pairs map_topic | round {args.round} | {scores_path} -> {out}", flush=True)

    rows = []
    with scores_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    rows.sort(key=lambda r: r["edge_id"])
    print(f"  scored edges {len(rows)}", flush=True)

    known = load_known_topic(args.topic)
    print(f"  known topic values {len(known)} | edges with one "
          f"{sum(1 for r in rows if r['edge_id'] in known)}", flush=True)

    L = build_layer(rows, known)

    with (out / "ranks.jsonl").open("w", encoding="utf-8") as f:
        for i, r in enumerate(rows):
            f.write(json.dumps({
                "edge_id": r["edge_id"], "chunk_id": r["chunk_id"], "tag": r["tag"],
                "scores": {fa: r[fa] for fa in FACETS},
                "positions": {fa: L["positions"][fa][i] for fa in FACETS},
            }, ensure_ascii=False) + "\n")
    with (out / "numeric.jsonl").open("w", encoding="utf-8") as f:
        for i, r in enumerate(rows):
            f.write(json.dumps({
                "edge_id": r["edge_id"], "chunk_id": r["chunk_id"], "tag": r["tag"],
                "known_topic": L["known"][i],
                "mapped_position": {fa: L["mapped_position"][fa][i] for fa in FACETS},
                "mapped_raw": {fa: L["mapped_raw"][fa][i] for fa in FACETS},
            }, ensure_ascii=False) + "\n")

    report = {"round": args.round, "scores": str(scores_path), "known_topic": str(args.topic),
              "n_edges": len(rows),
              "heldout_rule":
                  f"sha256('{D.SPLIT_SALT}' + chunk_id) / 2**256 < {D.HELDOUT_FRACTION}",
              "curve_fitted_on": "training-chunk edges only",
              "transfer": L["transfer"], "curve_table": L["curve_table"],
              "per_facet": L["stats"], "cross_spearman": L["cross_spearman"],
              "wall_s": round(time.perf_counter() - t0, 1)}
    (out / "mapping.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    (out / "MAPPING.md").write_text(render_md(report), encoding="utf-8")

    t = L["transfer"].get("heldout", {})
    print(f"  held-out transfer: n {t.get('n')} | Spearman "
          f"{_fmt(t.get('spearman_score_vs_known'), 3)} | MAE position "
          f"{_fmt(t.get('mae_mapped_position_vs_known'))} | MAE raw "
          f"{_fmt(t.get('mae_mapped_raw_vs_known'))} | median baseline "
          f"{_fmt(t.get('mae_constant_median_baseline'))}", flush=True)
    print(f"done | {time.perf_counter() - t0:.0f}s -> {out}", flush=True)
    return 0


def _fmt(v, nd=4):
    return "-" if v is None else f"%.{nd}f" % v


def render_md(r: dict) -> str:
    L = [f"# facet_pairs round {r['round']} — the numeric layer", "",
         f"{r['n_edges']} edges · scores `{r['scores']}` · known topic `{r['known_topic']}`",
         "",
         "The five scales were fitted to the judge's comparisons alone. The isotonic curve "
         "below was fitted on TRAINING-chunk edges only; the held-out line is out of sample.",
         "", "## transfer — the topic scale against the known topic numbers", "",
         "| edges | n | Spearman score vs known | MAE mapped (position) | MAE mapped (raw) | "
         "MAE of the constant median |", "|---|---|---|---|---|---|"]
    for name in ("train", "heldout"):
        t = r["transfer"].get(name) or {}
        L.append(f"| {name} | {t.get('n', 0)} | "
                 f"{_fmt(t.get('spearman_score_vs_known'), 3)} | "
                 f"{_fmt(t.get('mae_mapped_position_vs_known'))} | "
                 f"{_fmt(t.get('mae_mapped_raw_vs_known'))} | "
                 f"{_fmt(t.get('mae_constant_median_baseline'))} |")
    L += ["", "## the curve — topic score quantile -> topic number", "",
          "| quantile | topic score | topic number |", "|---|---|---|"]
    for row in r["curve_table"]:
        L.append(f"| {row['quantile']:.2f} | {row['score']:.4f} | {row['topic']:.4f} |")
    L += ["", "## per facet — the POSITION mapping (each column carries topic's marginal by "
          "construction)", "",
          "| facet | min | 5% | median | 95% | max | distinct | within-tag sd | "
          "within-chunk sd |", "|---|---|---|---|---|---|---|---|---|"]
    for f in FACETS:
        s = r["per_facet"][f]
        d = s["mapped_position"]
        L.append(f"| {f} | {d['min']:.4f} | {d['p5']:.4f} | {d['median']:.4f} | "
                 f"{d['p95']:.4f} | {d['max']:.4f} | {d['distinct']} | "
                 f"{_fmt(s['within_tag_sd'])} | {_fmt(s['within_chunk_sd'])} |")
    k = r["per_facet"]["known_topic"]
    d = k["value"]
    L.append(f"| known_topic (for comparison) | {d['min']:.4f} | {d['p5']:.4f} | "
             f"{d['median']:.4f} | {d['p95']:.4f} | {d['max']:.4f} | {d['distinct']} | "
             f"{_fmt(k['within_tag_sd'])} | {_fmt(k['within_chunk_sd'])} |")
    L += ["", "## per facet — the RAW-score mapping (the heads' scales are not guaranteed "
          "commensurate)", "",
          "| facet | min | 5% | median | 95% | max | distinct |", "|---|---|---|---|---|---|---|"]
    for f in FACETS:
        d = r["per_facet"][f]["mapped_raw"]
        L.append(f"| {f} | {d['min']:.4f} | {d['p5']:.4f} | {d['median']:.4f} | "
                 f"{d['p95']:.4f} | {d['max']:.4f} | {d['distinct']} |")
    L += ["", "## Spearman between the columns (rank-based, so the same for scores, positions "
          "and either mapping)", "", "| pair | Spearman |", "|---|---|"]
    for k2, v in r["cross_spearman"].items():
        L.append(f"| {k2} | {_fmt(v, 3)} |")
    L += ["", "Two mappings are reported side by side and nothing is decided between them."]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    sys.exit(main())

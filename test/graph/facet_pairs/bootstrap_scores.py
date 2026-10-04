"""How far the round-1 facet layer moves when its head is refitted on resampled judgements.

The head is round 1's: the `linear / mean_L-3` combination recorded in
`output/facet_pairs/rounds/round1/model/config.json`, fitted by `cache_probe.fit_head` on the
Davidson pairwise loss over the judge's choices, the epoch selected on the training-chunk
validation carve-out. Nothing here re-derives any of that; the loaders, the split rule, the
standardisation and the fit are imported from the siblings.

A draw resamples, WITH REPLACEMENT, the judged FIT ROWS — one row is one Opus call and carries
up to five facet observations, so the unit of resampling is the row, not the observation. The
validation carve-out is not resampled; it is used exactly as round 1 used it, for early
stopping. The held-out chunks enter no draw and are never read here.

The known topic values are never opened by this module. The head's own topic column is kept in
its own array, named `head_topic`, so that no caller can mistake it for the known topic.

Out: `<round1>/bootstrap/scores_b24.npz` and `meta.json` beside it, then, through `flip_gap`,
the gap at which a difference between two edges survives retraining.

    python test/graph/facet_pairs/bootstrap_scores.py --draws 24
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

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
NON_TOPIC = ("temporal", "why", "activity", "concreteness")
BASE_SEED = 20260921
DRAWS = 24

# The four calibration slopes, in the order temporal, why, activity, concreteness, as the task
# states them. Not measured here.
BETA = (0.722, 0.679, 0.845, 0.603)

WEIGHT_SETS = (
    ("equal", (1.0, 1.0, 1.0, 1.0)),
    ("1/.9/.6/.35", (1.0, 0.9, 0.6, 0.35)),
    ("why only", (0.0, 1.0, 0.0, 0.0)),
)

PAIR_SAMPLE = 200000
SEED_ANY = 20260921
SEED_SAME_CHUNK = 20260922


# ---------------------------------------------------------------- the band
#
# The band and the pair samples live in `bootstrap_band.py`, which imports nothing but numpy,
# so a reader of the band (the arm at prepare time) needs neither torch nor the fit's
# siblings. They are re-exported here: this module stays the one place they are called from.
try:
    from .bootstrap_band import (       # noqa: E402
        flip_gap, pava_nonincreasing, sample_any_pairs, sample_same_chunk_pairs, split_chunk_id,
    )
except ImportError:                     # run as a script
    from bootstrap_band import (        # noqa: E402
        flip_gap, pava_nonincreasing, sample_any_pairs, sample_same_chunk_pairs, split_chunk_id,
    )


# ---------------------------------------------------------------- the fit


def _sha(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def _rows_of(obs: list) -> dict:
    """fit observations grouped by row_id — one row is one judge call."""
    by = {}
    for o in obs:
        by.setdefault(o["row_id"], []).append(o)
    return by


def prepare(cache_path: str, answers: str, config: dict, quiet: bool = False) -> dict:
    """The cache, the judged rows and the fixed pieces every draw reuses."""
    cache = P.Cache(cache_path)
    variant, head_kind = config["variant"], config["head"]
    rows = D.load_answer_rows(answers)
    obs_all = D.observations(rows)
    part = D.partition_observations(obs_all)
    D.assert_no_heldout(part["train"])
    tv = D.training_val_split(part["train"])
    fit_obs, val_obs = tv["fit"], tv["val"]
    D.assert_no_heldout(fit_obs)

    idx = cache.index
    enc_val = P.encode_obs(val_obs, idx)
    val_obs_k = [val_obs[k] for k in enc_val["keep"]]
    by_row = _rows_of(fit_obs)
    row_ids = sorted(by_row)

    feats = cache.features(variant)          # one variant, float32, cast once
    if not quiet:
        print(f"  cache {len(cache.edge_ids)} edges | variant {variant} | head {head_kind} | "
              f"features {feats.shape}", flush=True)
        print(f"  judged rows: fit {len(row_ids)} ({len(fit_obs)} observations) | "
              f"validation {len(val_obs)} ({enc_val['n']} cached)", flush=True)
    return {"cache": cache, "features": feats, "variant": variant, "head_kind": head_kind,
            "idx": idx, "by_row": by_row, "row_ids": row_ids, "fit_obs": fit_obs,
            "enc_val": enc_val, "val_obs_k": val_obs_k,
            "hidden": int(config.get("hidden", P.HIDDEN)),
            "seed": int(config.get("seed", P.SEED)),
            "max_epochs": int(config.get("max_epochs", P.MAX_EPOCHS)),
            "patience": int(config.get("patience", P.PATIENCE)),
            "lr": float(config.get("lr", P.LR)),
            "wd": float(config.get("weight_decay", P.WEIGHT_DECAY))}


def fit_one(prep: dict, fit_obs: list) -> tuple:
    """Standardise on this fit set's own rows, fit the head, score every cached edge."""
    idx = prep["idx"]
    enc_fit = P.encode_obs(fit_obs, idx)
    if enc_fit["n"] == 0:
        raise RuntimeError("a draw produced no cached fit observations")
    fit_rows = sorted({int(v) for v in enc_fit["a"].tolist() + enc_fit["b"].tolist()})
    Fz, _, _ = P.standardise(prep["features"], fit_rows)
    X = torch.from_numpy(Fz)
    sub_rows, (sub_fit, sub_val) = P.subset([enc_fit, prep["enc_val"]])
    head, va = P.fit_head(X[sub_rows], sub_fit, sub_val, prep["val_obs_k"],
                          prep["head_kind"], prep["seed"], prep["max_epochs"],
                          prep["patience"], prep["lr"], prep["wd"], prep["hidden"])
    with torch.no_grad():
        scores = head(X).numpy()
    del Fz, X
    return scores, float(va)


def draw_rows(prep: dict, seed: int) -> list:
    """Resample the judged fit ROWS with replacement; every observation of a drawn row comes."""
    rng = np.random.default_rng(seed)
    ids = prep["row_ids"]
    pick = rng.integers(0, len(ids), len(ids))
    out = []
    for k in pick:
        out.extend(prep["by_row"][ids[int(k)]])
    return out


# ---------------------------------------------------------------- the reproduction check


def reproduction_check(prep: dict, baseline: np.ndarray, shipped: str) -> dict:
    """Compare the un-resampled refit against the shipped round-1 scores, edge for edge."""
    edge_ids, vals = [], []
    with open(shipped, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            edge_ids.append(r["edge_id"])
            vals.append([float(r[x]) for x in FACETS])
    got = prep["cache"].edge_ids
    same_order = (edge_ids == got)
    ship = np.asarray(vals, dtype=np.float64)
    if ship.shape[0] != baseline.shape[0]:
        raise RuntimeError(f"shipped {ship.shape[0]} rows, refit {baseline.shape[0]}")
    if not same_order:
        pos = {e: i for i, e in enumerate(edge_ids)}
        ship = ship[[pos[e] for e in got]]
    dif = np.abs(ship - baseline.astype(np.float64))
    return {"order_matches_cache": bool(same_order), "n_edges": int(ship.shape[0]),
            "max_abs_delta": float(dif.max()),
            "max_abs_delta_per_facet": {f: float(dif[:, i].max())
                                        for i, f in enumerate(FACETS)},
            "median_abs_delta": float(np.median(dif))}


# ---------------------------------------------------------------- the run


def run(cache_path: str, round_dir: str, answers: str, draws: int = DRAWS,
        base_seed: int = BASE_SEED, pair_m: int = PAIR_SAMPLE,
        rate: float = 0.05, grid: float = 0.01, quiet: bool = False,
        bands_only: bool = False) -> dict:
    """bands_only=True reads the stored score matrices and rewrites BANDS.md and the band
    block of meta.json from them. No head is refitted and the .npz is never rewritten, so a
    change to how the band is READ cannot disturb the matrices it is read from."""
    t0 = time.perf_counter()
    rd = Path(round_dir)
    out = rd / "bootstrap"
    out.mkdir(parents=True, exist_ok=True)
    config = json.loads((rd / "model" / "config.json").read_text(encoding="utf-8"))
    print(f"bootstrap_scores | round {config.get('round')} | B={draws}"
          f"{' | bands only' if bands_only else ''}", flush=True)

    if bands_only:
        npz = out / f"scores_b{draws}.npz"
        if not npz.is_file():
            raise RuntimeError(f"--bands-only reads {npz}, which does not exist")
        z = np.load(npz, allow_pickle=True)
        scores = np.asarray(z["scores"])
        edge_ids = [str(e) for e in z["edge_ids"]]
        seeds = np.asarray(z["seeds"])
        vas = np.asarray(z["val_macro_agreement"])
        n_edges = len(edge_ids)
        old = json.loads((out / "meta.json").read_text(encoding="utf-8"))
        rep = old.get("reproduction_check", {})
        base_va = old.get("baseline_val_macro_agreement", float("nan"))
        print(f"  read {npz.name}: {n_edges} edges x {scores.shape[1]} columns x "
              f"{scores.shape[2]} draws (not rewritten)", flush=True)
    else:
        prep = prepare(cache_path, answers, config, quiet)
        n_edges = len(prep["cache"].edge_ids)
        edge_ids = prep["cache"].edge_ids

        tb = time.perf_counter()
        baseline, base_va = fit_one(prep, prep["fit_obs"])
        print(f"  baseline refit (no resampling) | val macro {base_va:.4f} | "
              f"{time.perf_counter() - tb:.1f}s", flush=True)
        rep = reproduction_check(prep, baseline, str(rd / "scores.jsonl"))
        print(f"  vs shipped scores.jsonl: max |delta| {rep['max_abs_delta']:.3e} over "
              f"{rep['n_edges']} edges x 5 facets", flush=True)

        cols = [FACETS.index(f) for f in NON_TOPIC]
        scores = np.zeros((n_edges, len(NON_TOPIC), draws), dtype=np.float32)
        head_topic = np.zeros((n_edges, draws), dtype=np.float32)
        seeds = np.array([base_seed + b for b in range(draws)], dtype=np.int64)
        vas = np.zeros(draws, dtype=np.float64)
        for b in range(draws):
            td = time.perf_counter()
            s, va = fit_one(prep, draw_rows(prep, int(seeds[b])))
            scores[:, :, b] = s[:, cols]
            head_topic[:, b] = s[:, FACETS.index("topic")]
            vas[b] = va
            print(f"  draw {b + 1}/{draws} seed {int(seeds[b])} | val macro {va:.4f} | "
                  f"{time.perf_counter() - td:.1f}s", flush=True)

        npz = out / f"scores_b{draws}.npz"
        np.savez(npz,
                 edge_ids=np.array(edge_ids, dtype=object).astype("U"),
                 facets=np.array(list(NON_TOPIC)),
                 scores=scores, head_topic=head_topic, seeds=seeds,
                 val_macro_agreement=vas)
        print(f"  wrote {npz} ({npz.stat().st_size / 1e6:.1f} MB)", flush=True)

    # ---- the bands
    print("  pair samples", flush=True)
    samples = {
        "any": (sample_any_pairs(n_edges, pair_m, SEED_ANY), SEED_ANY),
        "same_chunk": (sample_same_chunk_pairs(edge_ids, pair_m, SEED_SAME_CHUNK),
                       SEED_SAME_CHUNK),
    }
    bands = {"per_facet": {}, "pooled": {}, "weighted": {}}
    for sname, (pairs, pseed) in samples.items():
        for i, f in enumerate(NON_TOPIC):
            g = flip_gap(scores[:, i, :], pairs, rate, grid)
            bands["per_facet"].setdefault(f, {})[sname] = g
            print(f"    {sname:<11} {f:<13} gap {g['gap']} | sd median "
                  f"{g['retrain_sd']['median']:.3f}", flush=True)
        stacked = np.concatenate([scores[:, i, :] for i in range(len(NON_TOPIC))], axis=0)
        pooled_pairs = np.concatenate([pairs + i * n_edges for i in range(len(NON_TOPIC))],
                                      axis=0)
        g = flip_gap(stacked, pooled_pairs, rate, grid)
        bands["pooled"][sname] = g
        print(f"    {sname:<11} {'POOLED':<13} gap {g['gap']} | {g['n_pairs']} pairs",
              flush=True)
        del stacked, pooled_pairs
        for wname, w in WEIGHT_SETS:
            for cal, betas in (("raw", (1.0, 1.0, 1.0, 1.0)), ("beta", BETA)):
                v = np.zeros((n_edges, draws), dtype=np.float32)
                for i in range(len(NON_TOPIC)):
                    if w[i]:
                        v += np.float32(w[i] * betas[i]) * scores[:, i, :]
                g = flip_gap(v, pairs, rate, grid)
                bands["weighted"].setdefault(wname, {}).setdefault(cal, {})[sname] = g
                print(f"    {sname:<11} w={wname:<12} {cal:<4} gap {g['gap']}", flush=True)
                del v

    wall = round(time.perf_counter() - t0, 1)
    meta = {
        "written": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "draws": draws, "base_seed": base_seed, "seeds": [int(s) for s in seeds],
        "resampling_unit": "one judged answer row (one Opus call, up to five observations)",
        "resampled": "the fit rows only",
        "validation": "the round-1 training-chunk carve-out, not resampled, early stopping only",
        "heldout": "no held-out chunk or pair entered any fit, and none was read here",
        "reads_the_known_values": False,
        "statement": ("no known topic value and no held-out row entered any fit in this file; "
                      "`head_topic` is the head's own topic column, never the known topic"),
        "config": config,
        "code_sha256": {
            "bootstrap_scores.py": _sha(Path(__file__)),
            "bootstrap_band.py": _sha(HERE / "bootstrap_band.py"),
            "cache_probe.py": _sha(HERE / "cache_probe.py"),
            "data.py": _sha(HERE / "data.py"),
        },
        "bands_only": bool(bands_only),
        "cache": ({"path": str(cache_path), "sha256": None,
                   "sha_source": "not recomputed under --bands-only"} if bands_only else
                  {"path": str(cache_path), "sha256": _sha(cache_path),
                   "sha_source": "computed here over the whole .npz"}),
        "reproduction_check": rep,
        "baseline_val_macro_agreement": base_va,
        "val_macro_agreement": {"min": float(vas.min()), "median": float(np.median(vas)),
                                "max": float(vas.max())},
        "flip_gap": {"rate": rate, "grid": grid, "pair_sample_size": pair_m,
                     "seed_any": SEED_ANY, "seed_same_chunk": SEED_SAME_CHUNK,
                     "mode": "local", "window": 2000,
                     "read": "the first grid step whose ISOTONIC (non-increasing, "
                             "pool-adjacent-violators, weights = the window's pair counts) "
                             "local rate is below the rate; a raw-curve dip never names the "
                             "band"},
        "beta": {f: BETA[i] for i, f in enumerate(NON_TOPIC)},
        "wall_s": wall,
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    (out / "BANDS.md").write_text(render_bands(bands, meta), encoding="utf-8")
    print(f"done | {wall}s | -> {out}", flush=True)
    return {"meta": meta, "bands": bands}


def _g(x):
    return "none" if x is None else f"{x:.2f}"


def render_bands(bands: dict, meta: dict) -> str:
    L = []
    L.append("# round 1 — the retrain band over B = %d draws" % meta["draws"])
    L.append("")
    L.append("Written %s. The flip gap is the smallest |mean difference| whose sign survives "
             "refitting on resampled judged rows in more than %.0f%% of draws. Numbers only."
             % (meta["written"], 100 * (1 - meta["flip_gap"]["rate"])))
    L.append("")
    L.append("Pair samples: `any` = %d uniform edge pairs, seed %d; `same_chunk` = %d pairs of "
             "two tags of one chunk, seed %d. Grid %.2f."
             % (meta["flip_gap"]["pair_sample_size"], meta["flip_gap"]["seed_any"],
                meta["flip_gap"]["pair_sample_size"], meta["flip_gap"]["seed_same_chunk"],
                meta["flip_gap"]["grid"]))
    L.append("")
    L.append("## per column")
    L.append("")
    L.append("| column | gap (any) | flip rate at 0 (any) | gap (same chunk) | "
             "flip rate at 0 (same chunk) | retrain sd median | retrain sd p90 |")
    L.append("|---|---|---|---|---|---|---|")
    for f in NON_TOPIC:
        a, s = bands["per_facet"][f]["any"], bands["per_facet"][f]["same_chunk"]
        L.append("| %s | %s | %.4f | %s | %.4f | %.3f | %.3f |"
                 % (f, _g(a["gap"]), a["curve"][0]["flip_rate"], _g(s["gap"]),
                    s["curve"][0]["flip_rate"], a["retrain_sd"]["median"],
                    a["retrain_sd"]["p90"]))
    p_a, p_s = bands["pooled"]["any"], bands["pooled"]["same_chunk"]
    L.append("| **pooled (four columns' pairs concatenated)** | %s | %.4f | %s | %.4f | %.3f | "
             "%.3f |" % (_g(p_a["gap"]), p_a["curve"][0]["flip_rate"], _g(p_s["gap"]),
                         p_s["curve"][0]["flip_rate"], p_a["retrain_sd"]["median"],
                         p_a["retrain_sd"]["p90"]))
    L.append("")
    L.append("Pairs at the gap: " + ", ".join(
        "%s %d/%d" % (f, bands["per_facet"][f]["any"]["curve"][-1]["n_pairs"],
                      bands["per_facet"][f]["any"]["n_pairs"]) for f in NON_TOPIC))
    L.append("")
    L.append("## weighted sums over the four columns")
    L.append("")
    L.append("Weights in the order temporal, why, activity, concreteness. `beta` multiplies "
             "each column by %s before the weighted sum."
             % ", ".join("%s %.3f" % (f, BETA[i]) for i, f in enumerate(NON_TOPIC)))
    L.append("")
    L.append("| weights | calibration | gap (any) | gap (same chunk) |")
    L.append("|---|---|---|---|")
    for wname, w in WEIGHT_SETS:
        for cal in ("raw", "beta"):
            e = bands["weighted"][wname][cal]
            L.append("| %s (%s) | %s | %s | %s |"
                     % (wname, "/".join("%g" % x for x in w), cal,
                        _g(e["any"]["gap"]), _g(e["same_chunk"]["gap"])))
    L.append("")
    L.append("## the flip-rate curve, per column, `any` sample")
    L.append("")
    L.append("| t | " + " | ".join("%s rate / pairs" % f for f in NON_TOPIC) + " |")
    L.append("|---|" + "---|" * len(NON_TOPIC))
    depth = max(len(bands["per_facet"][f]["any"]["curve"]) for f in NON_TOPIC)
    for k in range(depth):
        cells = []
        t = None
        for f in NON_TOPIC:
            c = bands["per_facet"][f]["any"]["curve"]
            if k < len(c):
                t = c[k]["t"] if t is None else t
                cells.append("%.4f / %d" % (c[k]["flip_rate"], c[k]["n_pairs"]))
            else:
                cells.append("-")
        L.append("| %.2f | %s |" % (k * meta["flip_gap"]["grid"], " | ".join(cells)))
    L.append("")
    L.append("## the refits")
    L.append("")
    L.append("Baseline refit (no resampling) against the shipped `scores.jsonl`: "
             "max |delta| %.3e over %d edges x 5 facets."
             % (meta["reproduction_check"]["max_abs_delta"],
                meta["reproduction_check"]["n_edges"]))
    L.append("")
    L.append("Validation macro agreement over the draws: min %.4f, median %.4f, max %.4f "
             "(baseline %.4f)."
             % (meta["val_macro_agreement"]["min"], meta["val_macro_agreement"]["median"],
                meta["val_macro_agreement"]["max"], meta["baseline_val_macro_agreement"]))
    L.append("")
    return "\n".join(L) + "\n"


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="retrain band over the round-1 facet layer")
    ap.add_argument("--cache", default="output/facet_pairs/fullcache/"
                                       "Alibaba-NLP__gte-reranker-modernbert-base.npz")
    ap.add_argument("--round-dir", default="output/facet_pairs/rounds/round1")
    ap.add_argument("--answers", default="output/facet_pairs/answers")
    ap.add_argument("--draws", type=int, default=DRAWS)
    ap.add_argument("--base-seed", type=int, default=BASE_SEED)
    ap.add_argument("--pairs", type=int, default=PAIR_SAMPLE)
    ap.add_argument("--rate", type=float, default=0.05)
    ap.add_argument("--grid", type=float, default=0.01)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--bands-only", action="store_true",
                    help="read the stored scores_b<draws>.npz and rewrite BANDS.md and "
                         "meta.json from it; no head is refitted and the .npz is untouched")
    a = ap.parse_args(argv)
    run(a.cache, a.round_dir, a.answers, a.draws, a.base_seed, a.pairs, a.rate, a.grid,
        a.quiet, a.bands_only)
    return 0


if __name__ == "__main__":
    sys.exit(main())

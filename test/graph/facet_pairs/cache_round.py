"""One round of the pairwise facet ranker over the FULL frozen-backbone cache.

The bake-off chose the backbone (`output/facet_pairs/bakeoff/REPORT.md`, 2026-09-19) and his
Colab run extracted every one of the 61,018 graph edges into one `.npz`. This runs the same
harness over that cache: the same chunk split, the same judged rows, the same heads and
pooling variants, the same selection on the training-chunk validation carve-out ONLY, the same
diagnostics A, C, D, E with a chunk bootstrap, and B — the perfect-label topic control — on the
same topic-sample edges the bake-off used, so the number is comparable to the table there.

Nothing here runs a backbone, calls a model, touches the graph, or opens a benchmark question
or gold. Selection and training read the judge's answers alone. The known topic values are read
in exactly one function of this module, `known_topic()`, for the B control (inside
`cache_probe.run`, which owns its own reader) and for the step-3 comparison column; the
Opus-trained head never sees them, which `test/tests/test_facet_pairs_round.py` asserts against
this file's source.

What it writes under `output/facet_pairs/rounds/round<N>/`:
  edges.jsonl   the split of ALL cached edges by the repo's hash rule;
  scores.jsonl  one row per cached edge: five scores and five within-column positions 0..1;
  model/        the head's weights, the standardisation, the chosen variant, config, seed;
  eval.json     A / B / C / D / E / F / G with chunk-bootstrap SEs;
  eval.md       the same as a table;
  LAYER.md      the layer's statistics over all 61,018 edges;
  CURVE.md      the label-budget learning curve.

Stated defaults of this file, none of them his: the learning-curve sizes 25/50/75/100% of the
judged training ROWS (one row = one Opus call = the label budget's unit), five seeds a size,
nested by a seeded shuffle; curve fits reuse the selected model's standardisation rather than
re-standardising per subset; everything else is `cache_probe`'s.

    python test/graph/facet_pairs/cache_round.py --round 1
"""
from __future__ import annotations

import argparse
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
    from . import bakeoff_report as R
except ImportError:  # run as a script
    import data as D  # noqa: E402
    import cache_probe as P  # noqa: E402
    import bakeoff_report as R  # noqa: E402

FACETS = D.FACETS
N_FACETS = len(FACETS)

CURVE_SIZES = (0.25, 0.50, 0.75, 1.00)
CURVE_SEEDS = 5

# The known topic column's path, here at module level so the guard test can hold every
# function but `known_topic` to naming nothing of it.
STATS_DEFAULT = "output/facet_stats/herb-eval-volmax.jsonl"


# ---------------------------------------------------------------- the known topic column
#
# THE ONLY function in this module that opens the known topic values. The guard test reads
# this file's source and fails if any other function mentions them.

def known_topic(stats_path: str, wanted: set) -> dict:
    return P.load_topic(stats_path, wanted)


# ---------------------------------------------------------------- small statistics

def positions(col: np.ndarray) -> np.ndarray:
    """Within-column position 0..1: the average rank, ties shared, scaled to [0, 1]."""
    n = len(col)
    if n < 2:
        return np.zeros(n, dtype=np.float64)
    r = R._rankdata(np.asarray(col, dtype=np.float64))
    return (r - 1.0) / (n - 1.0)


def spearman(x, y):
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if len(x) < 3 or len(x) != len(y):
        return None
    a, b = R._rankdata(x), R._rankdata(y)
    sa, sb = a.std(), b.std()
    if sa == 0 or sb == 0:
        return None
    return float(((a - a.mean()) * (b - b.mean())).mean() / (sa * sb))


def eta_squared(values, groups) -> float:
    """Share of a column's variance explained by a categorical label alone: between-group
    sum of squares over total sum of squares."""
    v = np.asarray(values, dtype=np.float64)
    if len(v) < 2:
        return float("nan")
    total = float(((v - v.mean()) ** 2).sum())
    if total <= 0:
        return float("nan")
    by = {}
    for i, g in enumerate(groups):
        by.setdefault(g, []).append(i)
    between = 0.0
    for idxs in by.values():
        between += len(idxs) * (v[idxs].mean() - v.mean()) ** 2
    return float(between / total)


def pooled_within_sd(values: np.ndarray, groups: list) -> list:
    """Per column, the pooled standard deviation inside groups of two or more members."""
    by = {}
    for i, g in enumerate(groups):
        by.setdefault(g, []).append(i)
    ss = np.zeros(values.shape[1])
    df = 0
    for idxs in by.values():
        if len(idxs) < 2:
            continue
        v = values[idxs]
        ss += ((v - v.mean(axis=0)) ** 2).sum(axis=0)
        df += len(idxs) - 1
    if df == 0:
        return [None] * values.shape[1]
    return [float(np.sqrt(ss[f] / df)) for f in range(values.shape[1])]


def agreement_per_facet(scores: np.ndarray, enc: dict) -> dict:
    """Share of DECIDED observations the scores order as the judge did, per facet."""
    out = {}
    for f in range(N_FACETS):
        ok = n = 0
        for i in range(enc["n"]):
            if int(enc["facet"][i]) != f or int(enc["outcome"][i]) not in (0, 1):
                continue
            n += 1
            g = scores[int(enc["a"][i]), f] - scores[int(enc["b"][i]), f]
            ok += int((g > 0 and int(enc["outcome"][i]) == 0)
                      or (g < 0 and int(enc["outcome"][i]) == 1))
        out[FACETS[f]] = (ok / n) if n else None
    return out


# ---------------------------------------------------------------- the membership file

def membership_rows(edge_ids: list, judged: set, topic_sample: set) -> list:
    """Every cached edge marked by the repo's hash rule. No topic value, no judge answer."""
    out = []
    for e in edge_ids:
        c, t = D.split_edge_id(e)
        out.append({"edge_id": e, "chunk_id": c, "tag": t,
                    "split": "heldout" if D.is_heldout(c) else "train",
                    "train_val": (not D.is_heldout(c)) and D.is_train_val(c),
                    "in_pairs": e in judged,
                    "topic_sample": e in topic_sample})
    return out


# ---------------------------------------------------------------- the learning curve

def nested_subsets(keys: list, sizes=CURVE_SIZES, seed: int = P.SEED) -> dict:
    """Seeded shuffle once, then prefixes: every smaller subset is inside every larger one."""
    order = list(keys)
    np.random.default_rng(seed).shuffle(order)
    return {s: set(order[:max(1, int(round(s * len(order))))]) for s in sizes}


def curve(art: dict, X: torch.Tensor, sizes=CURVE_SIZES, seeds: int = CURVE_SEEDS,
          quiet: bool = False) -> list:
    """Retrain the SELECTED (head, variant) on nested subsets of the judged training rows.

    The subset unit is the judged row — one Opus call — because that is what a label costs.
    Validation (the training-chunk carve-out) and held-out are the round's own, unchanged.
    """
    fit_obs = [art["fit_obs"][k] for k in art["enc_fit"]["keep"]]
    enc_val, enc_held = art["enc_val"], art["enc_held"]
    val_obs = art["val_obs"]
    rows = sorted({str(o.get("row_id")) for o in fit_obs})
    out = []
    for s in sizes:
        per_seed = []
        for si in range(seeds):
            keep = nested_subsets(rows, [s], P.SEED + si)[s]
            sub_obs = [o for o in fit_obs if str(o.get("row_id")) in keep]
            D.assert_no_heldout(sub_obs)
            enc_sub = P.encode_obs(sub_obs, art["index"])
            rows_idx, (e_sub, e_val, e_held) = P.subset([enc_sub, enc_val, enc_held])
            Xs = X[rows_idx]
            head, _ = P.fit_head(Xs, e_sub, e_val, val_obs, art["head_kind"],
                                 P.SEED + si, art["max_epochs"], art["patience"],
                                 hidden=art["hidden"])
            with torch.no_grad():
                sc = head(Xs).numpy()
            per = agreement_per_facet(sc, e_held)
            vals = [v for v in per.values() if v is not None]
            per_seed.append({"seed": P.SEED + si, "n_rows": len(keep),
                             "n_obs": enc_sub["n"],
                             "macro": float(np.mean(vals)) if vals else None,
                             "per_facet": per})
            if not quiet:
                print(f"    curve {int(s * 100):>3}% seed {si} rows {len(keep):>4} "
                      f"macro {per_seed[-1]['macro']:.4f}", flush=True)
        macro = [p["macro"] for p in per_seed if p["macro"] is not None]
        row = {"size": s, "n_rows": per_seed[0]["n_rows"], "n_obs": per_seed[0]["n_obs"],
               "macro_mean": float(np.mean(macro)), "macro_sd": float(np.std(macro, ddof=1)),
               "per_facet": {}, "seeds": per_seed}
        for f in FACETS:
            v = [p["per_facet"][f] for p in per_seed if p["per_facet"][f] is not None]
            row["per_facet"][f] = {"mean": float(np.mean(v)), "sd": float(np.std(v, ddof=1))}
        out.append(row)
    return out


# ---------------------------------------------------------------- the layer statistics

def layer_stats(scores: np.ndarray, edge_ids: list, kinds: list, topic_col, round0,
                c_pairs: dict) -> dict:
    """Everything step 3 asks for, over every cached edge."""
    chunks = [D.split_edge_id(e)[0] for e in edge_ids]
    tags = [D.split_edge_id(e)[1] for e in edge_ids]
    n_chunk_of_tag = {}
    for t, c in zip(tags, chunks):
        n_chunk_of_tag.setdefault(t, set()).add(c)
    multi = [i for i, t in enumerate(tags) if len(n_chunk_of_tag[t]) >= 2]

    per_facet = {}
    for f, name in enumerate(FACETS):
        col = scores[:, f]
        per_facet[name] = {
            "min": float(col.min()), "p5": float(np.percentile(col, 5)),
            "median": float(np.median(col)), "p95": float(np.percentile(col, 95)),
            "max": float(col.max()), "distinct": int(len(np.unique(col)))}
    wt = pooled_within_sd(scores[multi], [tags[i] for i in multi])
    wc = pooled_within_sd(scores, chunks)
    share = P.within_chunk_share(scores, chunks)
    for f, name in enumerate(FACETS):
        per_facet[name]["within_tag_sd"] = wt[f]
        per_facet[name]["within_chunk_sd"] = wc[f]
        per_facet[name]["between_tags_in_chunk_share"] = share[f]
        per_facet[name]["eta2_kind"] = eta_squared(scores[:, f], kinds)

    inter = {}
    for i in range(N_FACETS):
        for j in range(i + 1, N_FACETS):
            inter[f"{FACETS[i]}~{FACETS[j]}"] = spearman(scores[:, i], scores[:, j])

    vs_topic, vs_round0 = {}, {}
    if topic_col is not None:
        have = [i for i, e in enumerate(edge_ids) if e in topic_col]
        tv = [topic_col[edge_ids[i]] for i in have]
        for f, name in enumerate(FACETS):
            vs_topic[name] = spearman(scores[have, f], tv)
        vs_topic["_n"] = len(have)
        vs_topic["_eta2_kind"] = eta_squared(tv, [kinds[i] for i in have])
    if round0:
        have = [i for i, e in enumerate(edge_ids) if e in round0]
        for f, name in enumerate(FACETS):
            vs_round0[name] = spearman(scores[have, f],
                                       [round0[edge_ids[i]][f] for i in have])
        vs_round0["_n"] = len(have)

    return {"n_edges": len(edge_ids), "n_chunks": len(set(chunks)),
            "n_tags": len(n_chunk_of_tag), "n_edges_multichunk_tag": len(multi),
            "per_facet": per_facet, "inter_facet_spearman": inter,
            "vs_known_topic": vs_topic, "vs_round0": vs_round0,
            "same_side": c_pairs}


# ---------------------------------------------------------------- rendering

def _f(v, nd=4):
    return "-" if v is None or (isinstance(v, float) and np.isnan(v)) else f"%.{nd}f" % v


def render_eval(res: dict, boot: dict, ceiling: dict, cfg: dict) -> str:
    n = res["candidate"]
    p, se = boot["point"][n], boot["se"][n]
    L = [f"# round {cfg['round']} — the full-cache read of the diagnostic table", "",
         f"Written {cfg['written']}. Cache `{cfg['cache']}` ({res['counts']['cached_edges']} "
         f"edges). Backbone `{n}`, chosen by the bake-off's frozen rule. Bootstrap "
         f"B = {boot['boot']} over {boot['clusters']} held-out chunks, seed {boot['seed']}. "
         f"Selection on the training-chunk validation carve-out only; the held-out chunks "
         f"were read once, with the selected combination.", "",
         "## the selection", "",
         f"**{res['selected']['head']} / {res['selected']['variant']}** "
         f"(validation macro agreement {_f(res['selected']['val_agreement'])}), "
         f"the best of {len(res['selection'])} (head, variant) combinations.", "",
         "| head | variant | validation macro agreement |", "|---|---|---|"]
    for s in sorted(res["selection"], key=lambda r: -r["val_agreement"]):
        L.append(f"| {s['head']} | {s['variant']} | {_f(s['val_agreement'])} |")
    L += ["", "## A — held-out agreement with Opus, beside Opus's own repeat agreement", "",
          "| facet | A ± SE | n decided | Opus self-agreement ± SE |", "|---|---|---|---|"]
    for f in FACETS:
        a = res["A"]["per_facet"][f]
        c = ceiling.get(f) or {}
        L.append(f"| {f} | {_f(a['agreement'])} ± {_f(cfg['A_se'][f])} | {a['n']} | "
                 f"{_f(c.get('self_agreement'))} ± {_f(c.get('se'))} |")
    L.append(f"| **macro** | **{_f(p['A'])} ± {_f(se['A'])}** | "
             f"{res['counts']['heldout_obs']} | |")
    types = sorted({t for f in FACETS for t in res["A"]["per_pair_type"].get(f, {})})
    L += ["", "### A per pair type", "", "| facet | " + " | ".join(types) + " |",
          "|---|" + "---|" * len(types)]
    for f in FACETS:
        row = []
        for t in types:
            d = res["A"]["per_pair_type"].get(f, {}).get(t)
            row.append(f"{_f(d['agreement'])} ({d['n']})" if d else "-")
        L.append(f"| {f} | " + " | ".join(row) + " |")
    L += ["", "## B, C, D", "",
          f"* **B**, the known topic order recovered from perfect labels on the bake-off's "
          f"{res['B']['n']} held-out topic-sample edges: Spearman "
          f"{_f(p['B'])} ± {_f(se['B'])} "
          f"(fitted {(res['topic_selected'] or {}).get('head')} / "
          f"{(res['topic_selected'] or {}).get('variant')}).",
          f"* **C**, collapse excess (student same-side share minus Opus's own, mean over the "
          f"ten facet pairs): {_f(p['C'], 4)} ± {_f(se['C'])}.", "",
          "| facet pair | student same side | Opus same side | excess | n |",
          "|---|---|---|---|---|"]
    for k, v in res["C"]["per_facet_pair"].items():
        L.append(f"| {k} | {_f(v['student'])} | {_f(v['teacher'])} | {_f(v['excess'])} | "
                 f"{v['n']} |")
    L += ["", "**D** — the share of each output's variance that lies between tags inside one "
          "chunk, on the bake-off's held-out-split edges:", "",
          "| facet | D ± SE |", "|---|---|"]
    for i, f in enumerate(FACETS):
        L.append(f"| {f} | {_f(p['D'][i], 3)} ± {_f(se['D'][i], 3)} |")
    L += ["", "## E — the mean |score gap| on pairs Opus decided against pairs it called equal",
          "", "| facet | decided | tied | difference | n decided | n tied |",
          "|---|---|---|---|---|---|"]
    for f in FACETS:
        e = res["E"][f]
        L.append(f"| {f} | {_f(e['mean_gap_decided'], 3)} | {_f(e['mean_gap_tied'], 3)} | "
                 f"{_f(e['difference'], 3)} | {e['n_decided']} | {e['n_tied']} |")
    F = res["F"]
    L += ["", "## F, G", "",
          f"* cache: {F['hidden_size']}-wide, {F['n_tokens_median']} tokens median, "
          f"truncated {_f(F['truncation_rate'], 3)} ({F['n_truncated']} edges), "
          f"{F['seconds_per_1000_edges']} s per 1,000 edges on {F['device']}.",
          ]
    if res.get("G"):
        L.append(f"* G, the reranker's own relevance logit alone: A macro "
                 f"{_f(res['G']['A_macro'])}, B Spearman {_f(res['G']['B_spearman'])}.")
    L += ["", f"Wall: probe {res['wall_s']} s, bootstrap {cfg['boot_s']} s, "
          f"scoring {cfg['score_s']} s, round {cfg['wall_s']} s.", ""]
    return "\n".join(L) + "\n"


def render_layer(st: dict, cfg: dict) -> str:
    L = [f"# round {cfg['round']} — the layer over all {st['n_edges']} edges", "",
         f"Written {cfg['written']}. Scores from `{cfg['scores']}`; every number below is over "
         f"every cached edge ({st['n_chunks']} chunks, {st['n_tags']} distinct tags). Numbers "
         f"only.", "",
         "## per facet", "",
         "| facet | min | 5% | median | 95% | max | distinct |", "|---|---|---|---|---|---|---|"]
    for f in FACETS:
        d = st["per_facet"][f]
        L.append(f"| {f} | {_f(d['min'], 3)} | {_f(d['p5'], 3)} | {_f(d['median'], 3)} | "
                 f"{_f(d['p95'], 3)} | {_f(d['max'], 3)} | {d['distinct']} |")
    L += ["", "## spread inside a tag and inside a chunk", "",
          f"Within-tag sd is pooled over the tags that sit on two or more chunks "
          f"({st['n_edges_multichunk_tag']} edges).", "",
          "| facet | within-tag sd | within-chunk sd | share of variance between tags "
          "inside a chunk | eta² by record kind |", "|---|---|---|---|---|"]
    for f in FACETS:
        d = st["per_facet"][f]
        L.append(f"| {f} | {_f(d['within_tag_sd'], 4)} | {_f(d['within_chunk_sd'], 4)} | "
                 f"{_f(d['between_tags_in_chunk_share'], 3)} | {_f(d['eta2_kind'], 3)} |")
    if st["vs_known_topic"]:
        L.append(f"| *known topic (reference)* | - | - | - | "
                 f"{_f(st['vs_known_topic']['_eta2_kind'], 3)} |")
    L += ["", "## Spearman between the five columns", "",
          "| | " + " | ".join(FACETS) + " |", "|---|" + "---|" * N_FACETS]
    for i, a in enumerate(FACETS):
        row = []
        for j, b in enumerate(FACETS):
            if i == j:
                row.append("1")
            else:
                k = f"{a}~{b}" if f"{a}~{b}" in st["inter_facet_spearman"] else f"{b}~{a}"
                row.append(_f(st["inter_facet_spearman"][k], 3))
        L.append(f"| {a} | " + " | ".join(row) + " |")
    L += ["", "## Spearman with the known topic value and with round 0's same column", "",
          f"Known topic on {st['vs_known_topic'].get('_n', 0)} edges; round 0 on "
          f"{st['vs_round0'].get('_n', 0)} edges.", "",
          "| facet | vs known topic | vs round 0, same column |", "|---|---|---|"]
    for f in FACETS:
        L.append(f"| {f} | {_f(st['vs_known_topic'].get(f), 3)} | "
                 f"{_f(st['vs_round0'].get(f), 3)} |")
    L += ["", "## same-side agreement, the student beside Opus (held-out rows)", "",
          "| facet pair | student | Opus | n |", "|---|---|---|---|"]
    for k, v in st["same_side"].items():
        L.append(f"| {k} | {_f(v['student'], 3)} | {_f(v['teacher'], 3)} | {v['n']} |")
    return "\n".join(L) + "\n"


def render_curve(rows: list, cfg: dict) -> str:
    L = [f"# round {cfg['round']} — the label-budget learning curve", "",
         f"Written {cfg['written']}. The selected (head, variant) "
         f"`{cfg['head']} / {cfg['variant']}` retrained on nested random subsets of the judged "
         f"TRAINING rows (one row = one Opus call), {cfg['seeds']} seeds a size, the same "
         f"training-chunk validation carve-out for epoch selection and the same held-out "
         f"chunks for the reading. Mean ± sd over seeds.", "",
         "| share | rows | observations | macro A | " + " | ".join(FACETS) + " |",
         "|---|---|---|---|" + "---|" * N_FACETS]
    for r in rows:
        cols = [f"{_f(r['per_facet'][f]['mean'], 3)} ± {_f(r['per_facet'][f]['sd'], 3)}"
                for f in FACETS]
        L.append(f"| {int(r['size'] * 100)}% | {r['n_rows']} | {r['n_obs']} | "
                 f"{_f(r['macro_mean'], 4)} ± {_f(r['macro_sd'], 4)} | " + " | ".join(cols)
                 + " |")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- the round

def run_round(cache_path: str, out_dir: str, answers: str, rows_path: str, stats: str,
              edges_path: str, round_no: int = 1, seed: int = P.SEED, boot: int = P.BOOT,
              topic_pairs: int = P.TOPIC_PAIRS, max_epochs: int = P.MAX_EPOCHS,
              round0_scores: str = "", ceiling_path: str = "", sizes=CURVE_SIZES,
              curve_seeds: int = CURVE_SEEDS, quiet: bool = False) -> dict:
    t0 = time.perf_counter()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if not quiet:
        print(f"cache_round | round {round_no} | {cache_path}", flush=True)

    art = {}
    res = P.run(cache_path, answers, rows_path, stats, edges_path, seed, boot, topic_pairs,
                max_epochs=max_epochs, quiet=quiet, artifacts=art)
    cache, scores = art["cache"], art["scores"]
    edge_ids = cache.edge_ids
    if scores.shape[0] != len(edge_ids):
        raise RuntimeError(f"scored {scores.shape[0]} rows for {len(edge_ids)} cached edges")

    # every held-out chunk stayed out of every gradient
    fit_obs = [art["fit_obs"][k] for k in art["enc_fit"]["keep"]]
    D.assert_no_heldout(fit_obs)
    held_rows = {int(v) for v in art["enc_fit"]["a"].tolist() + art["enc_fit"]["b"].tolist()
                 if D.is_heldout(D.split_edge_id(edge_ids[int(v)])[0])}
    assert not held_rows, f"{len(held_rows)} held-out edges reached the fit set"

    # ---- the membership file over ALL cached edges
    bake = [json.loads(l) for l in Path(edges_path).read_text(encoding="utf-8").splitlines()
            if l.strip()]
    topic_sample = {r["edge_id"] for r in bake if r.get("topic_sample")}
    judged = set()
    for o in D.observations(D.load_answer_rows(answers)):
        judged.add(o["a_edge_id"])
        judged.add(o["b_edge_id"])
    mem = membership_rows(edge_ids, judged, topic_sample)
    with open(out / "edges.jsonl", "w", encoding="utf-8") as f:
        for r in mem:
            f.write(json.dumps(r) + "\n")
    n_held_edges = sum(1 for r in mem if r["split"] == "heldout")
    if not quiet:
        print(f"  membership: {len(mem)} edges | held-out {n_held_edges} | "
              f"in judged pairs {sum(1 for r in mem if r['in_pairs'])}", flush=True)

    # ---- scores for every edge
    ts = time.perf_counter()
    kind_of = {}
    for r in D.load_chunks(rows_path):
        kind_of[r["chunk_id"]] = r.get("kind")
    pos = np.stack([positions(scores[:, f]) for f in range(N_FACETS)], axis=1)
    with open(out / "scores.jsonl", "w", encoding="utf-8") as f:
        for i, e in enumerate(edge_ids):
            c, t = D.split_edge_id(e)
            row = {"edge_id": e, "chunk_id": c, "tag": t, "kind": kind_of.get(c)}
            for j, name in enumerate(FACETS):
                row[name] = float(scores[i, j])
            for j, name in enumerate(FACETS):
                row[name + "_pos"] = float(pos[i, j])
            f.write(json.dumps(row) + "\n")
    score_s = round(time.perf_counter() - ts, 1)
    if not quiet:
        print(f"  scored {len(edge_ids)} edges in {score_s} s -> {out / 'scores.jsonl'}",
              flush=True)

    # ---- the model
    mdir = out / "model"
    mdir.mkdir(parents=True, exist_ok=True)
    torch.save(art["head"].state_dict(), mdir / "head.pt")
    _, mu, sd = P.standardise(cache.features(art["variant"]), art["fit_rows"])
    np.savez(mdir / "standardisation.npz", mu=mu, sd=sd)
    (mdir / "config.json").write_text(json.dumps({
        "round": round_no, "backbone": res["candidate"], "cache": str(cache_path),
        "cache_meta": cache.meta, "head": art["head_kind"], "variant": art["variant"],
        "hidden": art["hidden"], "seed": seed, "lr": P.LR, "weight_decay": P.WEIGHT_DECAY,
        "max_epochs": max_epochs, "patience": P.PATIENCE,
        "facets": list(FACETS), "n_edges": len(edge_ids),
        "split_rule": {"salt": D.SPLIT_SALT, "fraction": D.HELDOUT_FRACTION,
                       "val_salt": D.VAL_SALT, "val_fraction": D.VAL_FRACTION},
        "selection": "training-chunk validation carve-out only",
        "topic_values_seen_by_this_head": False,
        "written": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }, indent=1), encoding="utf-8")

    # ---- the bootstrap, one candidate
    tb = time.perf_counter()
    if not quiet:
        print(f"  bootstrapping B={boot} over held-out chunks", flush=True)
    bootres = R.bootstrap({res["candidate"]: res}, boot, seed)
    boot_s = round(time.perf_counter() - tb, 1)

    # A's per-facet SE, from the same draws
    A_se = {}
    clusters = {c: i for i, c in enumerate(sorted({it["cluster"]
                                                   for it in res["A"]["items"]}))}
    aggA = R.agg_A(res["A"]["items"], clusters)
    rng = np.random.default_rng(seed)
    nc = len(clusters)
    draws = np.zeros((boot, N_FACETS))
    for b in range(boot):
        w = np.bincount(rng.integers(0, nc, nc), minlength=nc).astype(np.float64)
        tot = np.tensordot(w, aggA, axes=(0, 0))
        draws[b] = np.where(tot[:, 1] > 0, tot[:, 0] / np.maximum(tot[:, 1], 1), np.nan)
    for i, f in enumerate(FACETS):
        A_se[f] = float(np.nanstd(draws[:, i]))

    # ---- the layer statistics
    kinds = [kind_of.get(D.split_edge_id(e)[0]) for e in edge_ids]
    topic_col = known_topic(stats, set(edge_ids))
    r0 = {}
    if round0_scores and Path(round0_scores).is_file():
        with open(round0_scores, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                r0[r["edge_id"]] = [float(r[f]) for f in FACETS]
    st = layer_stats(scores, edge_ids, kinds, topic_col, r0, res["C"]["per_facet_pair"])

    # ---- the curve
    if not quiet:
        print("  learning curve", flush=True)
    Fz, _, _ = P.standardise(cache.features(art["variant"]), art["fit_rows"])
    X = torch.from_numpy(Fz)
    curve_rows = curve(art, X, sizes, curve_seeds, quiet)

    ceiling = {}
    if ceiling_path and Path(ceiling_path).is_file():
        ceiling = json.loads(Path(ceiling_path).read_text(encoding="utf-8")
                             ).get("self_agreement", {})

    wall_s = round(time.perf_counter() - t0, 1)
    cfg = {"round": round_no, "written": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "cache": str(cache_path), "scores": str(out / "scores.jsonl"),
           "A_se": A_se, "boot_s": boot_s, "score_s": score_s, "wall_s": wall_s,
           "head": art["head_kind"], "variant": art["variant"], "seeds": curve_seeds}

    slim = {k: v for k, v in res.items() if k not in ("A", "B", "C", "D", "G")}
    slim["A"] = {k: v for k, v in res["A"].items() if k != "items"}
    slim["A"]["se_per_facet"] = A_se
    slim["B"] = {k: v for k, v in res["B"].items() if k != "items"}
    slim["C"] = {k: v for k, v in res["C"].items() if k != "items"}
    slim["D"] = {k: v for k, v in res["D"].items() if k != "items"}
    if res.get("G"):
        slim["G"] = {k: v for k, v in res["G"].items() if k != "items"}
    evald = {"round": round_no, "written": cfg["written"], "cache": str(cache_path),
             "probe": slim,
             "bootstrap": {"B": boot, "seed": seed, "clusters": bootres["clusters"],
                           "point": bootres["point"][res["candidate"]],
                           "se": bootres["se"][res["candidate"]]},
             "opus_self_agreement": ceiling,
             "membership": {"n_edges": len(mem), "n_heldout_edges": n_held_edges,
                            "n_in_pairs": sum(1 for r in mem if r["in_pairs"])},
             "layer": {k: v for k, v in st.items() if k != "same_side"},
             "curve": [{k: v for k, v in r.items() if k != "seeds"} for r in curve_rows],
             "curve_seeds": curve_rows,
             "wall_s": {"probe": res["wall_s"], "bootstrap": boot_s, "scoring": score_s,
                        "round": wall_s}}
    (out / "eval.json").write_text(json.dumps(evald, indent=1), encoding="utf-8")
    (out / "eval.md").write_text(render_eval(res, bootres, ceiling, cfg), encoding="utf-8")
    (out / "LAYER.md").write_text(render_layer(st, cfg), encoding="utf-8")
    (out / "CURVE.md").write_text(render_curve(curve_rows, cfg), encoding="utf-8")
    if not quiet:
        p, se = bootres["point"][res["candidate"]], bootres["se"][res["candidate"]]
        print(f"  A {_f(p['A'])} ± {_f(se['A'])} | B {_f(p['B'])} ± {_f(se['B'])} | "
              f"C {_f(p['C'])} ± {_f(se['C'])}", flush=True)
        print(f"done | {wall_s}s | -> {out}", flush=True)
    return evald


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="one round over the full frozen-backbone cache")
    ap.add_argument("--cache", default="output/facet_pairs/fullcache/"
                                       "Alibaba-NLP__gte-reranker-modernbert-base.npz")
    ap.add_argument("--round", type=int, default=1)
    ap.add_argument("--out", default="")
    ap.add_argument("--answers", default="output/facet_pairs/answers")
    ap.add_argument("--rows", default="output/facet_neural/rows_export.jsonl")
    ap.add_argument("--stats", default=STATS_DEFAULT)
    ap.add_argument("--edges", default="output/facet_pairs/bakeoff/edges.jsonl")
    ap.add_argument("--round0", default="output/facet_pairs/rounds/round0/scores.jsonl")
    ap.add_argument("--ceiling", default="output/facet_pairs/rounds/round0/eval.json")
    ap.add_argument("--seed", type=int, default=P.SEED)
    ap.add_argument("--boot", type=int, default=P.BOOT)
    ap.add_argument("--topic-pairs", type=int, default=P.TOPIC_PAIRS)
    ap.add_argument("--max-epochs", type=int, default=P.MAX_EPOCHS)
    ap.add_argument("--curve-seeds", type=int, default=CURVE_SEEDS)
    a = ap.parse_args(argv)
    out = a.out or f"output/facet_pairs/rounds/round{a.round}"
    run_round(a.cache, out, a.answers, a.rows, a.stats, a.edges, a.round, a.seed, a.boot,
              a.topic_pairs, a.max_epochs, a.round0, a.ceiling, curve_seeds=a.curve_seeds)
    return 0


if __name__ == "__main__":
    sys.exit(main())

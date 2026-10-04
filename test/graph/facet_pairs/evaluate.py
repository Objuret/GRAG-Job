"""Held-out agreement, the judge's own ceiling, and the frozen stop rules.

Read from `output/facet_pairs/PROGRESS.md`, which fixed these before any call went out and is
the record:

* held-out agreement of the ranker = the share of held-out pairs the judge decided (said first
  or second) where the ranker's two scores order the pair the same way; pairs the judge called
  equal are reported apart, as the ranker's |score gap| distribution on them beside the gap
  distribution on decided pairs;
* the judge's self-agreement per facet, from the identical-repeat rows of the held-out set
  (the same pair, the same presentation order, asked again): the share where both answers are
  the same. That is the measured ceiling the stop rule reads, not an assumption;
* stop rules, per facet:
    done    — held-out agreement within one standard error of the judge's self-agreement;
    stalled — two rounds in a row gaining less than the held-out standard error;
    failed  — still not above 0.50 by three standard errors after round 3;
    else continue.

Nothing here reads the known topic values. The topic-against-cosine Spearman that stood here
until 2026-09-18 belongs to the mapping step (`map_topic.py`), which runs after scoring; at
training time it would be a reading of numbers the model is not allowed to have seen.

Standard errors come from a cluster bootstrap. The cluster is the unordered pair of chunk ids
the observation touches: that is the unit repeated across presentation orders and repeats of
one pair, so resampling it keeps the dependence the repeats create. `--cluster chunk` resamples
single chunk ids instead, anchored on the lexicographically smaller chunk of each observation.

Only a repeated pair's FIRST presentation counts towards agreement — one observation per
(pair_id, facet, presentation order), the smallest repeat index — so a pair asked twice does
not weigh twice. The second answers are used for self-agreement and nowhere else.

Writes `output/facet_pairs/rounds/round<N>/eval.json` and `eval.md`. Previous rounds' eval.json
files are read for the gain-based rules; nothing else is read from them.

    python test/graph/facet_pairs/evaluate.py --model output/facet_pairs/model/round1/model \\
        --round 1 --device cuda
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
for _p in (str(HERE), str(HERE.parent)):
    if _p not in sys.path:
        sys.path.insert(0, str(_p))

try:  # package first: the plain name collides with facet_neural's own data.py
    from . import data as D
except ImportError:  # run as a script on the desktop
    import data as D  # noqa: E402

FACETS = D.FACETS

BOOT_DEFAULT = 10000     # the stated default; the SEs the stop rules read are computed on it


# ---------------------------------------------------------------- presentations

def first_presentations(obs: list) -> list:
    """One observation per (pair_id, facet, order): the smallest repeat index.

    A row with no pair_id is its own presentation (nothing identifies it as a repeat)."""
    best = {}
    loose = []
    for o in obs:
        if o.get("pair_id") is None:
            loose.append(o)
            continue
        k = (o["pair_id"], o["facet"], o.get("order"))
        r = o.get("repeat")
        r = 0 if r is None else int(r)
        if k not in best or r < best[k][0]:
            best[k] = (r, o)
    return [v[1] for v in best.values()] + loose


def repeat_groups(obs: list) -> list:
    """Groups of two or more observations of the identical question: same pair, same facet,
    same presentation order, different repeat index."""
    by = {}
    for o in obs:
        if o.get("pair_id") is None:
            continue
        by.setdefault((o["pair_id"], o["facet"], o.get("order")), []).append(o)
    return [v for v in by.values() if len(v) > 1]


# ---------------------------------------------------------------- bootstrap

def cluster_key(o: dict, mode: str):
    if mode == "chunk":
        return min(o["a_chunk_id"], o["b_chunk_id"])
    return tuple(sorted({o["a_chunk_id"], o["b_chunk_id"]}))


def cluster_bootstrap_se(items: list, keyfn, statfn, boot: int, seed: int = 20260918):
    """SE of `statfn` over `items`, resampling clusters with replacement.

    `items` are (cluster_key, value) pairs; `statfn` takes a list of values.
    Returns (point estimate, se, n_clusters). SE is None when there are fewer than two
    clusters or the statistic is undefined on the resamples.
    """
    if not items:
        return None, None, 0
    groups = {}
    for it in items:
        groups.setdefault(keyfn(it), []).append(it)
    keys = list(groups)
    point = statfn([it for it in items])
    if len(keys) < 2 or boot < 2:
        return point, None, len(keys)
    rnd = random.Random(seed)
    vals = []
    for _ in range(boot):
        draw = []
        for _ in range(len(keys)):
            draw.extend(groups[keys[rnd.randrange(len(keys))]])
        v = statfn(draw)
        if v is not None:
            vals.append(v)
    se = statistics.pstdev(vals) if len(vals) > 1 else None
    return point, se, len(keys)


def _agree_share(items: list):
    if not items:
        return None
    return sum(1 for it in items if it["correct"]) / len(items)


def _same_share(items: list):
    if not items:
        return None
    return sum(1 for it in items if it["same"]) / len(items)


# ---------------------------------------------------------------- stop rules

def stop_decision(rounds: list, se: float | None, self_agreement: float | None,
                  self_se: float | None = None) -> dict:
    """The frozen rules, per facet. `rounds` is [{round, agreement}, ...] oldest first, the
    last entry being this round. `se` is this round's held-out standard error.

    done    — agreement within one standard error of the judge's self-agreement, i.e. it is
              not more than one SE below the ceiling (above the ceiling is also done);
    failed  — round >= 3 and agreement is not above 0.50 by three SE;
    stalled — the last two round-to-round gains are both below the held-out SE;
    continue otherwise.
    """
    if not rounds:
        return {"decision": "continue", "reason": "no rounds yet"}
    cur = rounds[-1]
    a = cur.get("agreement")
    n = cur.get("round")
    if a is None:
        return {"decision": "continue", "reason": "no agreement measured this round"}
    if self_agreement is not None and se is not None and a >= self_agreement - se:
        return {"decision": "done",
                "reason": f"agreement {a:.4f} is within one SE ({se:.4f}) of the judge's "
                          f"self-agreement {self_agreement:.4f}"}
    if n is not None and n >= 3 and se is not None and not (a - 3 * se > 0.50):
        return {"decision": "failed",
                "reason": f"after round {n}, agreement {a:.4f} is not above 0.50 by three SE "
                          f"(3*{se:.4f})"}
    if se is not None and len(rounds) >= 3:
        g1 = rounds[-1]["agreement"] - rounds[-2]["agreement"]
        g2 = rounds[-2]["agreement"] - rounds[-3]["agreement"]
        if g1 < se and g2 < se:
            return {"decision": "stalled",
                    "reason": f"the last two gains ({g2:+.4f}, {g1:+.4f}) are both below the "
                              f"held-out SE {se:.4f}"}
    return {"decision": "continue", "reason": "no stop rule fired"}


def previous_rounds(rounds_dir: str, facet: str, this_round: int) -> list:
    """[{round, agreement}, ...] from earlier rounds' eval.json, oldest first."""
    out = []
    root = Path(rounds_dir)
    if root.is_dir():
        for p in sorted(root.glob("round*/eval.json")):
            try:
                r = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            n = r.get("round")
            if n is None or n >= this_round:
                continue
            per = (r.get("per_facet") or {}).get(facet) or {}
            if per.get("agreement") is not None:
                out.append({"round": n, "agreement": per["agreement"]})
    return sorted(out, key=lambda x: x["round"])


# ---------------------------------------------------------------- the run

def evaluate_scores(obs: list, gaps: dict, boot: int, cluster: str, seed: int) -> dict:
    """Per facet and per pair type, given a score gap (s_a - s_b) per observation key."""
    per = {}
    for facet in FACETS:
        rows = [o for o in obs if o["facet"] == facet]
        dec = [o for o in rows if o["outcome"] in ("first", "second")]
        tie = [o for o in rows if o["outcome"] == "equal"]
        items = []
        for o in dec:
            g = gaps.get(_obskey(o))
            if g is None:
                continue
            items.append({**o, "correct": (g > 0 and o["outcome"] == "first")
                          or (g < 0 and o["outcome"] == "second"), "gap": g})
        point, se, nclu = cluster_bootstrap_se(
            items, lambda it: cluster_key(it, cluster), _agree_share, boot, seed)
        by_type = {}
        for t in sorted({o.get("pair_type") for o in items}):
            sub = [it for it in items if it.get("pair_type") == t]
            p2, se2, n2 = cluster_bootstrap_se(
                sub, lambda it: cluster_key(it, cluster), _agree_share,
                min(boot, 2000), seed)
            by_type[str(t)] = {"n": len(sub), "agreement": p2, "se": se2, "clusters": n2}
        tie_gaps = [abs(gaps[_obskey(o)]) for o in tie if _obskey(o) in gaps]
        dec_gaps = [abs(it["gap"]) for it in items]
        per[facet] = {
            "n_decided": len(items), "clusters": nclu,
            "agreement": point, "se": se,
            "by_pair_type": by_type,
            "n_tied": len(tie_gaps),
            "abs_gap_decided": _dist(dec_gaps),
            "abs_gap_tied": _dist(tie_gaps),
        }
    return per


def _obskey(o: dict) -> tuple:
    return (o["facet"], o["a_edge_id"], o["b_edge_id"], o.get("pair_id"),
            o.get("row_id"), o.get("order"), o.get("repeat"))


def _dist(v: list) -> dict:
    if not v:
        return {"n": 0}
    s = sorted(v)
    def q(p):
        return s[min(len(s) - 1, int(round(p * (len(s) - 1))))]
    return {"n": len(s), "min": s[0], "p25": q(.25), "median": q(.5), "p75": q(.75),
            "max": s[-1], "mean": statistics.fmean(s)}


def self_agreement(obs: list, boot: int, cluster: str, seed: int) -> dict:
    """Per facet: over identical repeats, the share where both answers are the same."""
    out = {}
    groups = repeat_groups(obs)
    for facet in FACETS:
        items = []
        for g in groups:
            if g[0]["facet"] != facet:
                continue
            g = sorted(g, key=lambda o: (0 if o.get("repeat") is None else int(o["repeat"])))
            items.append({**g[0], "same": g[0]["outcome"] == g[1]["outcome"]})
        point, se, nclu = cluster_bootstrap_se(
            items, lambda it: cluster_key(it, cluster), _same_share, boot, seed)
        out[facet] = {"n_repeat_pairs": len(items), "self_agreement": point, "se": se,
                      "clusters": nclu}
    return out


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="held-out evaluation and the frozen stop rules")
    ap.add_argument("--model", required=True, help="an artifact dir (…/model)")
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--answers", default="output/facet_pairs/answers")
    ap.add_argument("--heldout-set", default="heldout")
    ap.add_argument("--rows", default="output/facet_neural/rows_export.jsonl")
    ap.add_argument("--rounds-dir", default="output/facet_pairs/rounds")
    ap.add_argument("--out", default="")
    ap.add_argument("--device", default="")
    ap.add_argument("--boot", type=int, default=BOOT_DEFAULT)
    ap.add_argument("--cluster", choices=("chunkpair", "chunk"), default="chunkpair")
    ap.add_argument("--encode-batch", type=int, default=8)
    ap.add_argument("--seed", type=int, default=20260918)
    args = ap.parse_args(argv)

    import torch
    try:
        from .model import PairRanker, load_tokenizer
        from .train import score_rows
    except ImportError:
        from model import PairRanker, load_tokenizer  # noqa: E402
        from train import score_rows  # noqa: E402

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    t0 = time.perf_counter()
    out = Path(args.out or f"{args.rounds_dir}/round{args.round}")
    out.mkdir(parents=True, exist_ok=True)
    print(f"facet pairs evaluate | round {args.round} | model {args.model} | device {device}",
          flush=True)

    texts = D.load_texts(args.rows)
    rows_in = D.load_answer_rows(args.answers, sets=[args.heldout_set])
    obs_all = D.attach_texts(D.observations(rows_in), texts)
    leaked = [o for o in obs_all
              if not (D.is_heldout(o["a_chunk_id"]) and D.is_heldout(o["b_chunk_id"]))]
    obs = first_presentations(obs_all)
    print(f"  held-out answer rows {len(rows_in)} | observations {len(obs_all)} | "
          f"first presentations {len(obs)} | rows whose chunks are not held-out {len(leaked)}",
          flush=True)

    model, cfg = PairRanker.load(args.model, device=device)
    tok = load_tokenizer(args.model)
    max_len = int(cfg["max_length"])

    gaps = {}
    if obs_all:
        scoring, keys = [], []
        for o in obs_all:
            keys.append(_obskey(o))
            scoring.append({"facet": o["facet"], "edge_id": o["a_edge_id"],
                            "tag": o["a_tag"], "text": texts[o["a_chunk_id"]]})
            scoring.append({"facet": o["facet"], "edge_id": o["b_edge_id"],
                            "tag": o["b_tag"], "text": texts[o["b_chunk_id"]]})
        with torch.no_grad():
            s, _ = score_rows(model, tok, scoring, max_len, device, args.encode_batch)
        s = s.float().cpu().tolist()
        for i, k in enumerate(keys):
            gaps[k] = s[2 * i] - s[2 * i + 1]
    print(f"  scored {len(gaps)} held-out observations | "
          f"{time.perf_counter() - t0:.0f}s", flush=True)

    per = evaluate_scores(obs, gaps, args.boot, args.cluster, args.seed)
    ceiling = self_agreement(obs_all, args.boot, args.cluster, args.seed)

    decisions = {}
    for f in FACETS:
        hist = previous_rounds(args.rounds_dir, f, args.round)
        if per[f]["agreement"] is not None:
            hist = hist + [{"round": args.round, "agreement": per[f]["agreement"]}]
        decisions[f] = stop_decision(hist, per[f]["se"],
                                     ceiling[f]["self_agreement"], ceiling[f]["se"])
        decisions[f]["history"] = hist
        per[f]["self_agreement"] = ceiling[f]["self_agreement"]
        per[f]["self_agreement_se"] = ceiling[f]["se"]
        per[f]["n_repeat_pairs"] = ceiling[f]["n_repeat_pairs"]
        per[f]["decision"] = decisions[f]["decision"]

    result = {
        "round": args.round, "model": str(args.model),
        "heldout_set": args.heldout_set,
        "heldout_rule": f"sha256('{D.SPLIT_SALT}' + chunk_id) / 2**256 < {D.HELDOUT_FRACTION}",
        "n_answer_rows": len(rows_in), "n_observations": len(obs_all),
        "n_first_presentations": len(obs),
        "n_rows_not_from_heldout_chunks": len(leaked),
        "bootstrap": {"B": args.boot, "cluster": args.cluster, "seed": args.seed},
        "per_facet": per, "self_agreement": ceiling,
        "decisions": decisions,
        "wall_s": round(time.perf_counter() - t0, 1),
    }
    (out / "eval.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    (out / "eval.md").write_text(render_md(result), encoding="utf-8")
    for f in FACETS:
        p = per[f]
        print(f"  {f:<13} n {p['n_decided']:>5} agreement "
              f"{_fmt(p['agreement'])} +- {_fmt(p['se'])} | self {_fmt(p['self_agreement'])} "
              f"| {p['decision']}", flush=True)
    print(f"done | -> {out}", flush=True)
    return 0


def _fmt(v, nd=4):
    return "-" if v is None else f"%.{nd}f" % v


def render_md(r: dict) -> str:
    L = [f"# facet_pairs round {r['round']} — held-out evaluation", ""]
    L.append(f"model `{r['model']}` · held-out set `{r['heldout_set']}` · "
             f"{r['n_answer_rows']} answer rows · {r['n_observations']} observations · "
             f"{r['n_first_presentations']} first presentations")
    L.append(f"bootstrap B={r['bootstrap']['B']}, cluster = {r['bootstrap']['cluster']}")
    if r["n_rows_not_from_heldout_chunks"]:
        L.append(f"**{r['n_rows_not_from_heldout_chunks']} held-out rows do not come from "
                 f"held-out chunks** — counted, not dropped")
    L += ["", "| facet | n decided | agreement | SE | judge self-agreement | SE | n repeats | "
          "decision |", "|---|---|---|---|---|---|---|---|"]
    for f in FACETS:
        p = r["per_facet"][f]
        L.append(f"| {f} | {p['n_decided']} | {_fmt(p['agreement'])} | {_fmt(p['se'])} | "
                 f"{_fmt(p['self_agreement'])} | {_fmt(p['self_agreement_se'])} | "
                 f"{p['n_repeat_pairs']} | {p['decision']} |")
    L += ["", "## by pair type", "", "| facet | pair type | n | agreement | SE |",
          "|---|---|---|---|---|"]
    for f in FACETS:
        for t, v in sorted(r["per_facet"][f]["by_pair_type"].items()):
            L.append(f"| {f} | {t} | {v['n']} | {_fmt(v['agreement'])} | {_fmt(v['se'])} |")
    L += ["", "## |score gap| — decided against tied (the judge said equal)", "",
          "| facet | decided n | median | mean | tied n | median | mean |",
          "|---|---|---|---|---|---|---|"]
    for f in FACETS:
        d = r["per_facet"][f]["abs_gap_decided"]
        t = r["per_facet"][f]["abs_gap_tied"]
        L.append(f"| {f} | {d.get('n', 0)} | {_fmt(d.get('median'))} | {_fmt(d.get('mean'))} "
                 f"| {t.get('n', 0)} | {_fmt(t.get('median'))} | {_fmt(t.get('mean'))} |")
    L += ["", "## decisions", ""]
    for f in FACETS:
        d = r["decisions"][f]
        L.append(f"* **{f}** — {d['decision']}: {d['reason']}")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    sys.exit(main())

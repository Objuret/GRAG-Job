"""Fit the PairRanker to the judge's comparisons — and to nothing else.

His correction, 2026-09-18: Opus compares pairs on all five facets without seeing any topic
number; five latent scales are learned from those choices ALONE; only afterwards are the
existing numeric topic values revealed, the mapping from the judge-derived topic scale to the
real numbers is read off (`map_topic.py`), and that same mapping is applied to the other four
scales. So the known topic values must never enter training — a topic scale fitted to them
would make the mapping circular. This file therefore has no stage-0 topic pretraining, no topic
regression loss, no pairs sampled from cosines and no validation against cosines. It never
opens `output/facet_stats/*.jsonl`; a test greps the training path for exactly that.

The tie model is Davidson (1970), "On Extending the Bradley-Terry Model to Accommodate Ties in
Paired Comparison Experiments", JASA 65(329):317-328. With scores s_a, s_b and a tie parameter
nu > 0, writing h = (s_a - s_b) / 2:

    P(a wins) = e^h / (e^h + e^-h + nu)      P(b wins) = e^-h / (e^h + e^-h + nu)
    P(tie)    = nu  / (e^h + e^-h + nu)

Davidson rather than Rao-Kupper (1967) because Davidson's tie probability is symmetric in the
two scores and greatest exactly where the scores are equal, so "equal" is evidence of nearness
rather than of a threshold being straddled; `acquire.py` reads that tie probability directly.
nu is learned per facet, because the five have no reason to share a tie rate.

Training material: every answered row under the given answer sets — the default being every set
that is not `heldout`, which today is `control/` and `train/`. Every judgement is its own
observation: both presentation orders and every repeat are kept. Two independent guards refuse
to take a gradient on held-out material: the chunk-hash rule, and the row's own `set` field.

Validation for checkpoint selection is a carve-out of TRAINING pairs by chunk
(`data.is_train_val`, a third hash), scored by agreement with the judge. With about 1,100
training pairs the frozen-backbone phase A is the main phase; phase B (the last two transformer
layers unfrozen) is optional behind `--phase-b` and is off by default. Epoch count is by early
stopping on validation agreement, patience `--patience` (default 5) — a stated default, not a
measurement. An epoch is one shuffled pass over the fit observations.

    python test/graph/facet_pairs/train.py --round 0 \\
        --answers output/facet_pairs/answers \\
        --rows output/facet_neural/rows_export.jsonl \\
        --out output/facet_pairs/model/round0 --device cuda
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
for _p in (str(HERE), str(HERE.parent)):
    if _p not in sys.path:
        sys.path.insert(0, str(_p))

try:  # package first: the plain names collide with facet_neural's own modules
    from .model import (BACKBONE, FACETS, PairRanker, encode_rows, facet_id_tensor,
                        load_tokenizer)
    from . import data as D
except ImportError:  # run as a script on the desktop
    from model import (BACKBONE, FACETS, PairRanker, encode_rows,  # noqa: E402
                       facet_id_tensor, load_tokenizer)
    import data as D  # noqa: E402

# Pairs per optimiser step. One pair is two encodings, so 4 pairs is 8 encoded rows — the
# batch-8 setting measured on the 1080 Ti on 2026-09-17 (batch 24 is 10x SLOWER there because
# the working set oversubscribes 11 GB and Windows pages it silently).
PAIRS_PER_STEP = 4
ENCODE_BATCH = 8

MAX_LENGTH = 1424   # measured p99 of pair token length, 2026-09-17 (backbone max position 1680)

PATIENCE = 5        # a stated default: epochs without a new best validation agreement


def seed_all(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


# ---------------------------------------------------------------- the tie model

def davidson_log_probs(s_a, s_b, nu):
    """log P(a wins), log P(b wins), log P(tie) under Davidson (1970). nu > 0."""
    h = (s_a - s_b) / 2.0
    log_nu = torch.log(nu.clamp(min=1e-12))
    z = torch.logsumexp(torch.stack([h, -h, log_nu], dim=-1), dim=-1)
    return h - z, -h - z, log_nu - z


def davidson_nll(s_a, s_b, nu, outcome_ids):
    """Mean negative log likelihood. outcome_ids: 0 = a wins, 1 = b wins, 2 = tie."""
    la, lb, lt = davidson_log_probs(s_a, s_b, nu)
    ll = torch.stack([la, lb, lt], dim=-1).gather(
        -1, outcome_ids.unsqueeze(-1)).squeeze(-1)
    return -ll.mean()


OUTCOME_ID = {"first": 0, "second": 1, "equal": 2}


# ---------------------------------------------------------------- forward helpers

def score_rows(model, tok, rows: list, max_len: int, device: str, encode_batch: int):
    """Score (facet, tag, text) rows with ONE encoder pass per distinct EDGE.

    Rows are deduplicated on `edge_id` — not on (facet, edge_id) — because the model returns
    all five facet scores from one pass. An edge appearing on several facets in one step is
    encoded once, and each row reads its own facet's column out of that one forward.
    """
    keys, order, uniq = {}, [], []
    for r in rows:
        k = r["edge_id"]
        if k not in keys:
            keys[k] = len(uniq)
            uniq.append(r)
        order.append(keys[k])
    outs = []
    for i in range(0, len(uniq), encode_batch):
        b = uniq[i:i + encode_batch]
        enc = encode_rows(tok, [r["tag"] for r in b], [r["text"] for r in b], max_len)
        enc = {k: v.to(device) for k, v in enc.items()}
        outs.append(model(**enc))                                   # b x 5
    all_scores = (torch.cat(outs) if outs
                  else torch.zeros(0, len(FACETS), device=device))
    idx = torch.tensor(order, dtype=torch.long, device=device)
    per_row = all_scores.index_select(0, idx)                       # len(rows) x 5
    fid = facet_id_tensor([r["facet"] for r in rows], device=device)
    return per_row.gather(-1, fid.unsqueeze(-1)).squeeze(-1), uniq


def pair_rows(obs: list, texts: dict) -> list:
    """Two scoring rows per observation, a then b, in the observation's order."""
    rows = []
    for o in obs:
        rows.append({"facet": o["facet"], "edge_id": o["a_edge_id"],
                     "tag": o["a_tag"], "text": texts[o["a_chunk_id"]]})
        rows.append({"facet": o["facet"], "edge_id": o["b_edge_id"],
                     "tag": o["b_tag"], "text": texts[o["b_chunk_id"]]})
    return rows


def comparison_loss(model, tok, obs: list, texts: dict, max_len: int, device: str,
                    encode_batch: int):
    scores, _ = score_rows(model, tok, pair_rows(obs, texts), max_len, device, encode_batch)
    s_a, s_b = scores[0::2], scores[1::2]
    fid = facet_id_tensor([o["facet"] for o in obs], device=device)
    out_ids = torch.tensor([OUTCOME_ID[o["outcome"]] for o in obs],
                           dtype=torch.long, device=device)
    return davidson_nll(s_a, s_b, model.nu(fid), out_ids)


# ---------------------------------------------------------------- validation

@torch.no_grad()
def agreement(model, tok, obs: list, texts: dict, max_len: int, device: str,
              encode_batch: int) -> dict:
    """Per facet: the share of DECIDED observations the ranker orders as the judge did, and the
    mean |score gap| on decided and on tied observations."""
    was_training = model.training
    model.eval()
    if not obs:
        if was_training:
            model.train()
        return {"n": 0, "per_facet": {}, "macro": None}
    scores, _ = score_rows(model, tok, pair_rows(obs, texts), max_len, device, encode_batch)
    gaps = (scores[0::2] - scores[1::2]).float().cpu().tolist()
    per = {}
    for f in FACETS:
        dec = [(o, g) for o, g in zip(obs, gaps)
               if o["facet"] == f and o["outcome"] in ("first", "second")]
        tie = [g for o, g in zip(obs, gaps) if o["facet"] == f and o["outcome"] == "equal"]
        if dec:
            ok = sum(1 for o, g in dec
                     if (g > 0 and o["outcome"] == "first")
                     or (g < 0 and o["outcome"] == "second"))
            per[f] = {"n_decided": len(dec), "agreement": ok / len(dec),
                      "n_tied": len(tie),
                      "mean_abs_gap_decided": statistics.fmean(abs(g) for _, g in dec),
                      "mean_abs_gap_tied": statistics.fmean(abs(g) for g in tie) if tie
                      else None}
    macro = statistics.fmean(v["agreement"] for v in per.values()) if per else None
    if was_training:
        model.train()
    return {"n": len(obs), "per_facet": per, "macro": macro}


def spearman(x: list, y: list):
    if len(x) < 3:
        return None
    rx, ry = rankdata(x), rankdata(y)
    if statistics.pstdev(rx) == 0 or statistics.pstdev(ry) == 0:
        return None
    return float(np.corrcoef(rx, ry)[0, 1])


def rankdata(v: list) -> list:
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


# ---------------------------------------------------------------- the run

def load_training_observations(answers_dir: str, rows_export: str, answer_sets=None) -> dict:
    """Every judgement that may be trained on, with both held-out guards applied."""
    texts = D.load_texts(rows_export)
    rows_in = D.load_answer_rows(answers_dir, sets=answer_sets)
    if answer_sets is None:
        rows_in = [r for r in rows_in if r.get("set") != D.HELDOUT_SET]
    D.assert_no_heldout_set(rows_in)                     # guard 1: the row's own set name
    obs = D.attach_texts(D.observations(rows_in), texts)
    D.assert_no_heldout(obs)                             # guard 2: the chunk-hash rule
    split = D.training_val_split(obs)
    return {"texts": texts, "rows": rows_in, "obs": obs,
            "fit": split["fit"], "val": split["val"],
            "sets": sorted({str(r.get("set")) for r in rows_in})}


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="fit the pairwise facet ranker to the judge")
    ap.add_argument("--round", type=int, default=0, help="the acquisition round this fits")
    ap.add_argument("--out", default="", help="default output/facet_pairs/model/round<N>")
    ap.add_argument("--init", default="", help="an artifact dir to start from")
    ap.add_argument("--answers", default="output/facet_pairs/answers")
    ap.add_argument("--answer-sets", default="",
                    help="comma-separated set names to train on; default every set that is "
                         "not 'heldout'")
    ap.add_argument("--rows", default="output/facet_neural/rows_export.jsonl")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--max-length", type=int, default=MAX_LENGTH)
    ap.add_argument("--pairs-per-step", type=int, default=PAIRS_PER_STEP)
    ap.add_argument("--encode-batch", type=int, default=ENCODE_BATCH)
    ap.add_argument("--max-epochs", type=int, default=30)
    ap.add_argument("--max-steps", type=int, default=0,
                    help="stop after N optimiser steps in total; 0 = no cap. A dry run only.")
    ap.add_argument("--patience", type=int, default=PATIENCE,
                    help="epochs without a new best validation agreement before stopping")
    ap.add_argument("--phase-b", action="store_true",
                    help="after phase A, run a phase with the last two transformer layers "
                         "unfrozen; off by default (1,100 pairs, and phase B runs 8x slower)")
    ap.add_argument("--epochs-b", type=int, default=4, help="max epochs of phase B if enabled")
    ap.add_argument("--lr-head", type=float, default=1e-4)
    ap.add_argument("--lr-backbone", type=float, default=1e-5)
    ap.add_argument("--weight-decay", type=float, default=0.01)
    ap.add_argument("--clip", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=20260918)
    args = ap.parse_args(argv)

    t0 = time.perf_counter()
    seed_all(args.seed)
    out = Path(args.out or f"output/facet_pairs/model/round{args.round}")
    out.mkdir(parents=True, exist_ok=True)
    print(f"facet pairs train | round {args.round} | device {args.device} | -> {out}",
          flush=True)

    sets = [s for s in args.answer_sets.split(",") if s] or None
    mat = load_training_observations(args.answers, args.rows, sets)
    texts, fit_obs, val_obs = mat["texts"], mat["fit"], mat["val"]
    print(f"  chunks with text {len(texts)} | answer rows {len(mat['rows'])} "
          f"| sets {','.join(mat['sets'])}", flush=True)
    print(f"  judge observations {len(mat['obs'])} | fit {len(fit_obs)} "
          f"| validation {len(val_obs)}", flush=True)
    if not fit_obs:
        raise SystemExit("facet pairs train: no judge observations to fit")
    if not val_obs:
        raise SystemExit("facet pairs train: no training observation landed in the "
                         "training-validation carve-out; there is nothing to select a "
                         "checkpoint on")
    for f in FACETS:
        n = [o for o in fit_obs if o["facet"] == f]
        print(f"    {f:<13} fit {len(n):>5} | ties "
              f"{sum(1 for o in n if o['outcome'] == 'equal'):>4}", flush=True)

    tok = load_tokenizer(args.init or BACKBONE)
    if args.init:
        model, _ = PairRanker.load(args.init, device=args.device)
        model.train()
        print(f"  started from {args.init}", flush=True)
    else:
        model = PairRanker().to(args.device)

    rnd = random.Random(args.seed)
    steps_per_epoch = max(1, (len(fit_obs) + args.pairs_per_step - 1) // args.pairs_per_step)
    print(f"  an epoch is one shuffled pass: {steps_per_epoch} steps of "
          f"{args.pairs_per_step} pairs", flush=True)

    history, best = [], {"metric": -float("inf"), "phase": None, "epoch": None}
    best_state, freeze_record, total_steps, stopped = None, {}, 0, None

    phases = [("A", args.max_epochs)]
    if args.phase_b:
        phases.append(("B", args.epochs_b))

    for phase, max_epochs in phases:
        freeze_record[phase] = model.set_stage(phase)
        groups = [{"params": model.head_parameters(), "lr": args.lr_head}]
        enc_params = model.encoder_parameters()
        if enc_params:
            groups.append({"params": enc_params, "lr": args.lr_backbone})
        opt = torch.optim.AdamW(groups, weight_decay=args.weight_decay)
        print(f"  phase {phase}: trainable "
              f"{freeze_record[phase]['trainable_parameters']:,} frozen "
              f"{freeze_record[phase]['frozen_parameters']:,}", flush=True)
        since_best = 0
        for ep in range(1, max_epochs + 1):
            model.train()
            deck = list(fit_obs)
            rnd.shuffle(deck)
            e0, tot, n = time.perf_counter(), 0.0, 0
            for step in range(steps_per_epoch):
                batch = deck[step * args.pairs_per_step:(step + 1) * args.pairs_per_step]
                if not batch:
                    continue
                loss = comparison_loss(model, tok, batch, texts, args.max_length,
                                       args.device, args.encode_batch)
                opt.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(
                    [p for p in model.parameters() if p.requires_grad], args.clip)
                opt.step()
                tot += float(loss.item())
                n += 1
                total_steps += 1
                if n % 25 == 0 or n == 1:
                    print(f"    [{phase}{ep}] step {n}/{steps_per_epoch} "
                          f"loss {tot / max(n, 1):.4f} "
                          f"{n / max(time.perf_counter() - e0, 1e-9):.2f} steps/s",
                          flush=True)
                if args.max_steps and total_steps >= args.max_steps:
                    stopped = f"--max-steps {args.max_steps} reached"
                    break

            va = agreement(model, tok, val_obs, texts, args.max_length, args.device,
                           args.encode_batch)
            metric = va.get("macro")
            rec = {"phase": phase, "epoch": ep, "steps": n,
                   "train_loss": tot / max(n, 1), "val_agreement": va,
                   "tie_log": [float(v) for v in model.tie_log.detach().cpu()],
                   "seconds": round(time.perf_counter() - e0, 1)}
            history.append(rec)
            mark = ""
            if metric is not None and metric > best["metric"]:
                best = {"metric": metric, "phase": phase, "epoch": ep, "val_agreement": va}
                best_state = {k: v.detach().cpu().clone()
                              for k, v in model.state_dict().items()}
                since_best, mark = 0, "  <- best"
                # Written the moment it improves, so a stopped run still leaves the best
                # checkpoint on disk rather than only the last one in memory.
                keep = {k: v.detach().clone() for k, v in model.state_dict().items()}
                model.load_state_dict(best_state)
                model.save(out / "model", tokenizer=tok,
                           extra={"max_length": args.max_length, "round": args.round,
                                  "selected_checkpoint": {"phase": phase, "epoch": ep,
                                                          "metric": metric},
                                  "known_topic_values_in_training": False,
                                  "complete_run": False})
                model.load_state_dict(keep)
            else:
                since_best += 1
            (out / "history.json").write_text(json.dumps(history, indent=1), encoding="utf-8")
            print(f"    [{phase}{ep}] loss {rec['train_loss']:.4f} | val agreement "
                  f"{'-' if metric is None else '%.4f' % metric} | "
                  f"{rec['seconds']:.0f}s{mark}", flush=True)
            if stopped:
                break
            if since_best >= args.patience:
                stopped = f"early stop: {since_best} epochs without a new best (patience "
                stopped += f"{args.patience})"
                print(f"  {stopped}", flush=True)
                break
        if stopped and stopped.startswith("--max-steps"):
            break

    if best_state is None:
        raise SystemExit("facet pairs train: no epoch produced a validation metric")
    model.load_state_dict(best_state)
    print(f"  restored best: phase {best['phase']} epoch {best['epoch']} "
          f"metric {best['metric']:.4f}", flush=True)

    cfg = {
        "round": args.round,
        "max_length": args.max_length, "pairs_per_step": args.pairs_per_step,
        "encode_batch": args.encode_batch, "steps_per_epoch": steps_per_epoch,
        "epoch_rule": "one shuffled pass over the fit observations",
        "max_epochs": args.max_epochs, "patience": args.patience,
        "phase_b": bool(args.phase_b), "epochs_phase_b": args.epochs_b if args.phase_b else 0,
        "max_steps": args.max_steps, "stopped_because": stopped or "epochs exhausted",
        "total_steps": total_steps,
        "optimizer": "AdamW", "lr_head": args.lr_head, "lr_backbone": args.lr_backbone,
        "weight_decay": args.weight_decay, "grad_clip": args.clip,
        "loss": "Davidson (1970) Bradley-Terry with ties, nu per facet learned; the judge's "
                "comparisons are the only training signal",
        "known_topic_values_in_training": False,
        "training_sets": mat["sets"],
        "mixed_precision": False,
        "mixed_precision_note": "off: the 1080 Ti is Pascal and has no fast fp16 path",
        "seed": args.seed, "device": args.device, "freezing": freeze_record,
        "checkpoint_selection_metric": "macro agreement over the facets present",
        "checkpoint_selection_set": "judge observations on training-validation chunks",
        "heldout_rule": f"sha256('{D.SPLIT_SALT}' + chunk_id) / 2**256 < {D.HELDOUT_FRACTION}",
        "train_val_rule": f"sha256('{D.VAL_SALT}' + chunk_id) / 2**256 < {D.VAL_FRACTION}",
        "n_judge_fit_observations": len(fit_obs),
        "n_judge_val_observations": len(val_obs),
        "selected_checkpoint": {k: best[k] for k in ("phase", "epoch", "metric")},
        "complete_run": True,
        "wall_s": round(time.perf_counter() - t0, 1),
    }
    model.save(out / "model", tokenizer=tok, extra=cfg)
    (out / "history.json").write_text(json.dumps(history, indent=1), encoding="utf-8")
    (out / "train_metrics.json").write_text(json.dumps(
        {"best": best, "config": cfg}, indent=1), encoding="utf-8")
    print(f"done | {time.perf_counter() - t0:.0f}s -> {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

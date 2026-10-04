"""Train the four-facet cross-encoder on the measured counterfactual targets.

Sections 13-19. Two stages: A with the whole backbone frozen, B with its last two transformer
layers unfrozen. One Huber loss per facet, their mean the total, equal weight and no invented
facet importance. The checkpoint kept is the best macro MAE on the validation chunks; the test
chunks are read exactly once, by `--test`, and never during selection.

    python test/graph/facet_neural/train.py --table output/facet_neural/table/main \\
        --out output/facet_neural/runs/<id> --device cuda
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

HERE = Path(__file__).resolve().parent
for _p in (str(HERE), str(HERE.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from model import BACKBONE, FACETS, FacetModel, encode_pairs, load_tokenizer  # noqa: E402
import data as D  # noqa: E402


def seed_all(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def batches(rows: list, size: int, shuffle: bool, rnd: random.Random):
    idx = list(range(len(rows)))
    if shuffle:
        rnd.shuffle(idx)
    for i in range(0, len(idx), size):
        yield [rows[j] for j in idx[i:i + size]]


def forward_batch(model, tok, batch, max_len, device):
    enc = encode_pairs(tok, [r["tag"] for r in batch], [r["text"] for r in batch], max_len)
    enc = {k: v.to(device) for k, v in enc.items()}
    y = torch.tensor([r["y"] for r in batch], dtype=torch.float32, device=device)
    return model(**enc), y


@torch.no_grad()
def evaluate(model, tok, rows, max_len, device, batch_size, huber) -> dict:
    """Section 17: per facet Huber, MAE, prediction mean/sd, target mean/sd, correlation."""
    model.eval()
    P, Y = [], []
    for b in batches(rows, batch_size, False, random.Random(0)):
        pred, y = forward_batch(model, tok, b, max_len, device)
        P.append(pred.float().cpu())
        Y.append(y.float().cpu())
    if not P:
        return {}
    P = torch.cat(P)
    Y = torch.cat(Y)
    per = {}
    for i, f in enumerate(FACETS):
        p, y = P[:, i], Y[:, i]
        pl, yl = p.tolist(), y.tolist()
        if len(pl) > 1 and statistics.pstdev(pl) > 0 and statistics.pstdev(yl) > 0:
            corr = float(np.corrcoef(pl, yl)[0, 1])
        else:
            corr = None
        per[f] = {
            "huber": float(huber(p, y).item()),
            "mae": float((p - y).abs().mean().item()),
            "pred_mean": float(p.mean().item()), "pred_sd": float(p.std(unbiased=False).item()),
            "target_mean": float(y.mean().item()),
            "target_sd": float(y.std(unbiased=False).item()),
            "corr": corr,
        }
    return {"n": int(P.shape[0]), "per_facet": per,
            "macro_mae": float(statistics.fmean(per[f]["mae"] for f in FACETS)),
            "macro_huber": float(statistics.fmean(per[f]["huber"] for f in FACETS))}


def report(tag: str, m: dict) -> str:
    if not m:
        return f"{tag}: empty"
    p = m["per_facet"]
    bits = []
    for f in FACETS:
        c = p[f]["corr"]
        cs = "-" if c is None else ("%.3f" % c)
        bits.append("%s mae %.4f r %s" % (f[:4], p[f]["mae"], cs))
    return "%s: n %d macro_mae %.4f | %s" % (tag, m["n"], m["macro_mae"], " ".join(bits))


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="train the four-facet cross-encoder")
    ap.add_argument("--table", required=True, help="a dir with table.jsonl and split.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--max-length", type=int, default=0, help="0 = from the measured p99")
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--accum", type=int, default=1)
    ap.add_argument("--epochs-a", type=int, default=12)
    ap.add_argument("--epochs-b", type=int, default=8)
    ap.add_argument("--lr-head", type=float, default=1e-4)
    ap.add_argument("--lr-backbone", type=float, default=1e-5)
    ap.add_argument("--weight-decay", type=float, default=0.01)
    ap.add_argument("--clip", type=float, default=1.0)
    ap.add_argument("--huber-beta", type=float, default=0.0,
                    help="0 = the measured median |target| over the training rows")
    ap.add_argument("--seed", type=int, default=20260917)
    ap.add_argument("--test", action="store_true",
                    help="after training, read the held-out test chunks ONCE")
    args = ap.parse_args(argv)

    t0 = time.perf_counter()
    seed_all(args.seed)
    torch.use_deterministic_algorithms(False)

    tbl = Path(args.table)
    rows = [json.loads(l) for l in (tbl / "table.jsonl").read_text(encoding="utf-8").splitlines()
            if l.strip()]
    split = json.loads((tbl / "split.json").read_text(encoding="utf-8"))
    parts = D.apply_split(rows, split)
    print(f"facet train | rows {len(rows)} | train {len(parts['train'])} "
          f"({len(split['train'])} chunks) val {len(parts['val'])} ({len(split['val'])}) "
          f"test {len(parts['test'])} ({len(split['test'])}) | device {args.device}", flush=True)
    if not parts["train"] or not parts["val"]:
        raise SystemExit("facet train: the split leaves a partition empty")

    tok = load_tokenizer(BACKBONE)
    lens = D.token_lengths(tok, rows)
    p99 = sorted(lens)[min(len(lens) - 1, int(0.99 * (len(lens) - 1)))]
    model_max = 1680
    max_len = args.max_length or min(model_max, int(p99))
    print(f"  pair token length min {min(lens)} median {statistics.median(lens):.0f} "
          f"p95 {sorted(lens)[int(.95*(len(lens)-1))]} p99 {p99} max {max(lens)} "
          f"-> max_length {max_len} (backbone max position {model_max}); "
          f"{sum(1 for x in lens if x > max_len)} pairs truncate", flush=True)

    model = FacetModel().to(args.device)
    ys = [v for r in parts["train"] for v in r["y"]]
    beta = args.huber_beta or max(1e-6, statistics.median([abs(v) for v in ys]))
    huber = nn.SmoothL1Loss(beta=beta)
    print(f"  Huber beta {beta:.6f} (median |target| over the training rows)", flush=True)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(args.seed)
    history, best = [], {"macro_mae": math.inf, "stage": None, "epoch": None}
    best_state = None
    freeze_record = {}

    for stage, epochs in (("A", args.epochs_a), ("B", args.epochs_b)):
        freeze_record[stage] = model.set_stage(stage)
        groups = [{"params": model.head_parameters(), "lr": args.lr_head}]
        enc = model.encoder_parameters()
        if enc:
            groups.append({"params": enc, "lr": args.lr_backbone})
        opt = torch.optim.AdamW(groups, weight_decay=args.weight_decay)
        print(f"  stage {stage}: trainable {freeze_record[stage]['trainable_parameters']:,} "
              f"frozen {freeze_record[stage]['frozen_parameters']:,}", flush=True)
        for ep in range(1, epochs + 1):
            model.train()
            e0, tot, n, step = time.perf_counter(), 0.0, 0, 0
            opt.zero_grad(set_to_none=True)
            for b in batches(parts["train"], args.batch, True, rnd):
                pred, y = forward_batch(model, tok, b, max_len, args.device)
                loss = torch.stack([huber(pred[:, i], y[:, i])
                                    for i in range(len(FACETS))]).mean()
                (loss / args.accum).backward()
                step += 1
                if step % args.accum == 0:
                    torch.nn.utils.clip_grad_norm_(
                        [p for p in model.parameters() if p.requires_grad], args.clip)
                    opt.step()
                    opt.zero_grad(set_to_none=True)
                tot += float(loss.item()) * len(b)
                n += len(b)
            val = evaluate(model, tok, parts["val"], max_len, args.device, args.batch, huber)
            rec = {"stage": stage, "epoch": ep, "train_loss": tot / max(n, 1),
                   "val": val, "seconds": round(time.perf_counter() - e0, 1)}
            history.append(rec)
            mark = ""
            if val and val["macro_mae"] < best["macro_mae"]:
                best = {"macro_mae": val["macro_mae"], "stage": stage, "epoch": ep,
                        "val": val}
                best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
                mark = "  <- best"
            print(f"    [{stage}{ep}] train {rec['train_loss']:.5f} | "
                  f"{report('val', val)} {rec['seconds']:.0f}s{mark}", flush=True)

    if best_state is None:
        raise SystemExit("facet train: no validation evaluation produced a checkpoint")
    model.load_state_dict(best_state)
    print(f"  restored best: stage {best['stage']} epoch {best['epoch']} "
          f"macro_mae {best['macro_mae']:.4f}", flush=True)

    test = None
    if args.test:
        test = evaluate(model, tok, parts["test"], max_len, args.device, args.batch, huber)
        print(f"  {report('TEST (read once)', test)}", flush=True)

    cfg = {
        "max_length": max_len, "token_length_p99": p99,
        "token_length_median": statistics.median(lens), "token_length_max": max(lens),
        "batch_size": args.batch, "grad_accumulation": args.accum,
        "effective_batch_size": args.batch * args.accum,
        "epochs_stage_a": args.epochs_a, "epochs_stage_b": args.epochs_b,
        "optimizer": "AdamW", "lr_head": args.lr_head, "lr_backbone": args.lr_backbone,
        "weight_decay": args.weight_decay, "grad_clip": args.clip,
        "loss": f"SmoothL1(beta={beta}) per facet, mean of four, equal weight",
        "huber_beta": beta, "huber_beta_rule": "median |target| over the training rows",
        "mixed_precision": False,
        "mixed_precision_note": "off: the 1080 Ti is Pascal and has no fast fp16 path "
                                "(docs/ENVIRONMENT.md)",
        "seed": args.seed, "device": args.device,
        "freezing": freeze_record,
        "checkpoint_selection_metric": "validation macro MAE over the four facets",
        "selected_checkpoint": {k: best[k] for k in ("stage", "epoch", "macro_mae")},
        "split": split, "table": str(tbl),
        "table_meta": json.loads((tbl / "table_meta.json").read_text(encoding="utf-8")),
        "wall_s": round(time.perf_counter() - t0, 1),
    }
    model.save(out / "model", tokenizer=tok, extra=cfg)
    (out / "history.json").write_text(json.dumps(history, indent=1), encoding="utf-8")
    (out / "metrics.json").write_text(json.dumps(
        {"best_val": best.get("val"), "test": test, "config": cfg}, indent=1), encoding="utf-8")
    print(f"done | {time.perf_counter() - t0:.0f}s -> {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

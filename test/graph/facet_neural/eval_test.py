"""Evaluate one saved checkpoint against the frozen held-out test chunks. Once.

Section 19 step 4. This file loads the artifact and reads the test partition; it holds no
optimiser and no backward pass, so it cannot train, and it refuses to run twice against the
same artifact unless `--again` is passed, because the test set is read once by rule.

    python test/graph/facet_neural/eval_test.py --model <run>/model --table <table dir>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

import numpy as np
import torch
from torch import nn

HERE = Path(__file__).resolve().parent
for _p in (str(HERE),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from model import FACETS, FacetModel, encode_pairs, load_tokenizer  # noqa: E402
import data as D  # noqa: E402


@torch.no_grad()
def evaluate(model, tok, rows, max_len, device, batch, huber) -> dict:
    model.eval()
    P, Y = [], []
    for i in range(0, len(rows), batch):
        b = rows[i:i + batch]
        enc = encode_pairs(tok, [r["tag"] for r in b], [r["text"] for r in b], max_len)
        enc = {k: v.to(device) for k, v in enc.items()}
        P.append(model(**enc).float().cpu())
        Y.append(torch.tensor([r["y"] for r in b], dtype=torch.float32))
    P, Y = torch.cat(P), torch.cat(Y)
    per = {}
    for i, f in enumerate(FACETS):
        p, y = P[:, i], Y[:, i]
        pl, yl = p.tolist(), y.tolist()
        corr = (float(np.corrcoef(pl, yl)[0, 1])
                if len(pl) > 1 and statistics.pstdev(pl) > 0 and statistics.pstdev(yl) > 0
                else None)
        per[f] = {"huber": float(huber(p, y).item()),
                  "mae": float((p - y).abs().mean().item()),
                  "pred_mean": float(p.mean()), "pred_sd": float(p.std(unbiased=False)),
                  "target_mean": float(y.mean()), "target_sd": float(y.std(unbiased=False)),
                  "corr": corr}
    return {"n": int(P.shape[0]), "per_facet": per,
            "macro_mae": float(statistics.fmean(per[f]["mae"] for f in FACETS)),
            "macro_huber": float(statistics.fmean(per[f]["huber"] for f in FACETS))}


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="the held-out test, read once")
    ap.add_argument("--model", required=True)
    ap.add_argument("--table", required=True)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--again", action="store_true",
                    help="allow a second reading of the test set for this artifact")
    args = ap.parse_args(argv)

    out = Path(args.model) / "test_metrics.json"
    if out.is_file() and not args.again:
        raise SystemExit(f"facet eval: {out} already exists — the held-out test has been read "
                         f"for this checkpoint. Section 17 forbids using it for selection; "
                         f"pass --again only when you mean to read it a second time.")

    model, cfg = FacetModel.load(args.model, device=args.device)
    tok = load_tokenizer(args.model)
    ckpt = hashlib.sha256(Path(args.model, "model.safetensors").read_bytes()).hexdigest()
    tbl = Path(args.table)
    rows = [json.loads(l) for l in (tbl / "table.jsonl").read_text(encoding="utf-8").splitlines()
            if l.strip()]
    split = json.loads((tbl / "split.json").read_text(encoding="utf-8"))
    parts = D.apply_split(rows, split)
    beta = float(cfg.get("huber_beta") or 1.0)
    huber = nn.SmoothL1Loss(beta=beta)

    print(f"facet eval | checkpoint {ckpt[:16]} | test {len(parts['test'])} edges over "
          f"{len(split['test'])} chunks | max_length {cfg['max_length']} | beta {beta}",
          flush=True)
    m = evaluate(model, tok, parts["test"], int(cfg["max_length"]), args.device,
                 args.batch, huber)
    p = m["per_facet"]
    print(f"  TEST macro_mae {m['macro_mae']:.4f} macro_huber {m['macro_huber']:.5f} "
          f"(n {m['n']})", flush=True)
    print("| facet | huber | mae | pred mean | pred sd | target mean | target sd | corr |",
          flush=True)
    print("|---|---|---|---|---|---|---|---|", flush=True)
    for f in FACETS:
        c = p[f]["corr"]
        print(f"| {f} | {p[f]['huber']:.5f} | {p[f]['mae']:.4f} | {p[f]['pred_mean']:.4f} | "
              f"{p[f]['pred_sd']:.4f} | {p[f]['target_mean']:.4f} | {p[f]['target_sd']:.4f} | "
              f"{'-' if c is None else '%.3f' % c} |", flush=True)
    out.write_text(json.dumps({"checkpoint_sha256": ckpt, "table": str(tbl),
                               "test_chunks": len(split["test"]), "metrics": m,
                               "read": "once"}, indent=1), encoding="utf-8")
    print(f"-> {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

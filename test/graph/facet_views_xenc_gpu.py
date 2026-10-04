"""Score (phrase, view) pairs with a fixed cross-encoder on a machine with a GPU.

Standalone on purpose: it is scp'd alone to the desktop, whose checkout is on an old branch and
which carries no spaCy. It imports nothing from this repo — torch and transformers only. The
model and revision are pinned in this file and asserted against the values passed on the command
line, so a drift in either fails the run rather than silently producing a second instrument. The
HF cache is wherever the launching environment points it.

The value written is the model's **raw logit** — the single-label sequence-classification head's
output, no sigmoid. The head is monotone in the logit, so the order is the model's own and the
scale is the logit's; nothing is calibrated, nothing is thresholded, no number is chosen here.

Input:  a jsonl of {"a_sha", "a", "b_sha", "b"} — `a` the phrase, `b` the view string, each sha
        the sha256 of the exact string, asserted on read.
Output: an .npz with `a_sha`, `b_sha` (U64 strings), `score` (float32) and the meta arrays
        `model` and `revision`, resumable — a partial `.part.npz` is written every `--flush`
        pairs and read back on relaunch.

    python facet_views_xenc_gpu.py --in pairs.jsonl --out scores.npz --device cuda --batch 128
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

XENC_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
XENC_REVISION = "233902d25c440f23af6f7d6e94d2946bac0bee0a"
XENC_DTYPE = "float32"


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="a fixed cross-encoder pair scorer, pair list in")
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--batch", type=int, default=128, help="pairs per batch")
    ap.add_argument("--max-len", type=int, default=512,
                    help="the checkpoint's own context; a batch wider than this raises")
    ap.add_argument("--model", default=XENC_MODEL)
    ap.add_argument("--revision", default=XENC_REVISION)
    ap.add_argument("--flush", type=int, default=5000)
    ap.add_argument("--limit", type=int, default=0,
                    help="score only the first N pairs of the input file, in the file's own "
                         "order; 0 is every pair")
    args = ap.parse_args(argv)

    if args.model != XENC_MODEL or args.revision != XENC_REVISION:
        raise SystemExit(f"facet_views_xenc_gpu: this file is pinned to {XENC_MODEL} @ "
                         f"{XENC_REVISION}; got {args.model} @ {args.revision}")

    t0 = time.perf_counter()
    rows = []
    with open(args.src, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            for side in ("a", "b"):
                got = hashlib.sha256(r[side].encode("utf-8")).hexdigest()
                if got != r[f"{side}_sha"]:
                    raise SystemExit(f"facet_views_xenc_gpu: sha mismatch on input "
                                     f"{side} {r[f'{side}_sha'][:12]} -> {got[:12]}")
            rows.append((r["a_sha"], r["a"], r["b_sha"], r["b"]))
    if args.limit:
        rows = rows[:args.limit]
    chars = sum(len(a) + len(b) for _as, a, _bs, b in rows)
    print(f"facet_views_xenc_gpu | {len(rows)} pairs | {chars} chars | "
          f"{args.model} @ {args.revision[:12]} | {args.device} {XENC_DTYPE} | "
          f"raw logit, no sigmoid | batch {args.batch}"
          + (f" | --limit {args.limit}" if args.limit else ""), flush=True)

    out = Path(args.out)
    part = out.with_suffix(".part.npz")
    done: dict = {}
    if part.is_file():
        z = np.load(part, allow_pickle=False)
        done = {(str(a), str(b)): float(s)
                for a, b, s in zip(z["a_sha"], z["b_sha"], z["score"])}
        print(f"  resumed {len(done)} from {part}", flush=True)

    todo = [r for r in rows if (r[0], r[2]) not in done]
    # Batches are padded to their longest member, so a batch of mixed lengths spends most of its
    # work on padding. Sorting by the pair's total length groups like with like; the model masks
    # padding, so a pair's score does not depend on what it is batched with.
    todo.sort(key=lambda r: len(r[1]) + len(r[3]))
    print(f"  {len(todo)} to score, length-sorted", flush=True)

    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(args.model, revision=args.revision)
    model = AutoModelForSequenceClassification.from_pretrained(args.model,
                                                              revision=args.revision)
    model = model.to(torch.float32).to(args.device).eval()
    n_labels = int(model.config.num_labels)
    if n_labels != 1:
        raise SystemExit(f"facet_views_xenc_gpu: {args.model} has {n_labels} labels; this file "
                         f"reads a single-label relevance head's raw logit")
    card = (torch.cuda.get_device_name(0) if args.device.startswith("cuda") else "cpu")
    print(f"  model ready in {time.perf_counter() - t0:.0f}s ({card}, "
          f"{model.config.max_position_embeddings}-position context)", flush=True)

    def save(path):
        keys = list(done)
        np.savez(path,
                 a_sha=np.array([k[0] for k in keys], dtype="U64"),
                 b_sha=np.array([k[1] for k in keys], dtype="U64"),
                 score=np.array([done[k] for k in keys], dtype=np.float32),
                 model=np.array([args.model], dtype="U128"),
                 revision=np.array([args.revision], dtype="U64"))

    t1 = time.perf_counter()
    since = 0
    n_done = 0
    with torch.inference_mode():
        for i in range(0, len(todo), args.batch):
            batch = todo[i:i + args.batch]
            enc = tok([a for _as, a, _bs, _b in batch], [b for _as, _a, _bs, b in batch],
                      return_tensors="pt", padding=True, truncation=False)
            width = int(enc["input_ids"].shape[1])
            if width > args.max_len:
                raise SystemExit(f"facet_views_xenc_gpu: a pair is {width} tokens, past the "
                                 f"{args.max_len}-token context")
            enc = {k: v.to(args.device) for k, v in enc.items()}
            logits = model(**enc).logits.float().squeeze(-1).cpu().numpy()
            for (a_sha, _a, b_sha, _b), s in zip(batch, np.atleast_1d(logits)):
                done[(a_sha, b_sha)] = float(s)
            since += len(batch)
            n_done += len(batch)
            if since >= args.flush or n_done >= len(todo):
                save(part)
                since = 0
                rate = n_done / max(time.perf_counter() - t1, 1e-9)
                print(f"  [{n_done}/{len(todo)}] {rate:.1f} pairs/s | "
                      f"{(len(todo) - n_done) / max(rate, 1e-9) / 60:.1f} min left", flush=True)

    save(out)
    wall = time.perf_counter() - t1
    meta = {"model": args.model, "revision": args.revision, "dtype": XENC_DTYPE,
            "device": args.device, "batch": args.batch, "max_len": args.max_len,
            "value": "raw logit of the single-label relevance head, no sigmoid",
            "pairs_in": len(rows), "pairs_scored": n_done, "pairs_out": len(done),
            "limit": args.limit or None,
            "pairs_per_s": round(n_done / max(wall, 1e-9), 1),
            "wall_s": round(time.perf_counter() - t0, 1)}
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"done | {len(done)} scores -> {out} | "
          f"{n_done / max(wall, 1e-9):.1f} pairs/s | {time.perf_counter() - t0:.0f}s",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

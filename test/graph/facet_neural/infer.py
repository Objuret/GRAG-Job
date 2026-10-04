"""Run a saved facet model over every (tag, chunk) edge and write the facet layer.

Section 21. The model is loaded from its artifact directory alone — no teacher, no
counterfactual, no relevance instrument, no SCALE. The edges come from the same graph export
the teacher ran on, so this file needs no neo4j driver and runs on the desktop.

Resumable: values are appended per chunk and the chunks already in the output file are skipped
on relaunch.

    python test/graph/facet_neural/infer.py --model output/facet_neural/model/<id> \\
        --rows output/facet_neural/rows_export.jsonl \\
        --out output/facet_neural/layer/herb-eval-volmax --device cuda
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from model import FACETS, FacetModel, encode_pairs, load_tokenizer  # noqa: E402


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="the trained facet model over every graph edge")
    ap.add_argument("--model", required=True)
    ap.add_argument("--rows", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(argv)

    t0 = time.perf_counter()
    model, cfg = FacetModel.load(args.model, device=args.device)
    tok = load_tokenizer(args.model)
    max_len = int(cfg["max_length"])
    ckpt = hashlib.sha256(
        Path(args.model, "model.safetensors").read_bytes()).hexdigest()
    print(f"facet infer | model {args.model} | checkpoint sha256 {ckpt[:16]} | "
          f"max_length {max_len} | device {args.device} | batch {args.batch}", flush=True)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    values = out / "values.jsonl"

    chunks = []
    with open(args.rows, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                if r.get("text") and r.get("tags"):
                    chunks.append(r)
    if args.limit:
        chunks = chunks[:args.limit]
    n_edges = sum(len(c["tags"]) for c in chunks)
    want = {c["chunk_id"]: len(c["tags"]) for c in chunks}

    # A chunk counts as done only when EVERY one of its edges is on disk. Counting a chunk as
    # done because one of its rows is there loses the rest when a run is interrupted mid-chunk,
    # which is how 12 edges went missing on 2026-09-17 across three restarts. Short chunks are
    # dropped from the file and re-run whole.
    have, kept = {}, []
    if values.is_file():
        with values.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    have.setdefault(r["chunk_id"], []).append(r)
        done = {c for c, rs in have.items() if len(rs) == want.get(c, -1)}
        partial = [c for c in have if c not in done]
        if partial:
            with values.open("w", encoding="utf-8") as f:
                for c, rs in have.items():
                    if c in done:
                        for r in rs:
                            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            print(f"  resume: dropped {sum(len(have[c]) for c in partial)} rows from "
                  f"{len(partial)} partly written chunks; they are re-run whole", flush=True)
        print(f"  resuming: {len(done)} complete chunks already written", flush=True)
    else:
        done = set()
    todo = [c for c in chunks if c["chunk_id"] not in done]
    print(f"  {len(chunks)} chunks, {n_edges} edges | {len(todo)} chunks to run", flush=True)

    written, t1 = 0, time.perf_counter()
    with values.open("a", encoding="utf-8") as f:
        for i, c in enumerate(todo, 1):
            tags = [t if isinstance(t, str) else t.get("name") for t in c["tags"]]
            tags = [t for t in tags if t]
            preds = []
            with torch.no_grad():
                for j in range(0, len(tags), args.batch):
                    b = tags[j:j + args.batch]
                    enc = encode_pairs(tok, b, [c["text"]] * len(b), max_len)
                    enc = {k: v.to(args.device) for k, v in enc.items()}
                    preds.extend(model(**enc).float().cpu().tolist())
            for tag, p in zip(tags, preds):
                f.write(json.dumps({
                    "edge_key": f"{c['chunk_id']}|{tag}",
                    "chunk_id": c["chunk_id"], "tag": tag,
                    "product": c.get("product"), "kind": c.get("kind"),
                    **{fa: float(v) for fa, v in zip(FACETS, p)},
                    "checkpoint": ckpt,
                }, ensure_ascii=False) + "\n")
                written += 1
            if i % 100 == 0 or i == len(todo):
                f.flush()
                rate = i / max(time.perf_counter() - t1, 1e-9)
                print(f"  [{i}/{len(todo)}] {written} edges | {rate:.1f} chunks/s | "
                      f"{(len(todo) - i) / max(rate, 1e-9) / 60:.1f} min left", flush=True)

    meta = {
        "model_dir": str(args.model), "checkpoint_sha256": ckpt,
        "facets": list(FACETS), "rows_export": str(args.rows),
        "chunks": len(chunks), "edges": n_edges, "edges_written_this_run": written,
        "max_length": max_len, "device": args.device,
        "output_activation": cfg.get("output_activation"),
        "target_definition": cfg.get("relevance_target",
                                     "R(T,C) - R(T,C^(-F,T)), signed, no SCALE"),
        "backbone": cfg.get("backbone"), "wall_s": round(time.perf_counter() - t0, 1),
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"done | {written} edges written -> {values} | "
          f"{time.perf_counter() - t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

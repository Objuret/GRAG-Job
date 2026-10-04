"""Embed a string list on a machine with a GPU, with the harness embedder's exact settings.

Standalone on purpose: it is scp'd alone to the desktop, which carries no spaCy and whose
checkout is on an old branch. It imports nothing from this repo. The model, revision, dtype
and prefix are copied from `prod/harness/embed.py` and are asserted against the values passed
on the command line, so a drift in either file fails the run rather than silently producing a
second instrument.

Input:  a jsonl of {"sha": <sha256 of the exact string>, "text": <the string>}.
Output: an .npz with `sha` (U64 strings) and `vec` (float32, n x dim), resumable — a partial
        `.part.npz` is written every `--flush` strings and read back on relaunch.

    python facet_embed_gpu.py --in strings.jsonl --out vectors.npz --device cuda --batch 16
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

EMBED_MODEL = "nvidia/llama-nemotron-embed-1b-v2"
EMBED_REVISION = "113abe4acafa848e77ead9c0623205e511932348"
EMBED_DTYPE = "float32"
EMBED_PREFIX = {"query": "query: ", "passage": "passage: "}


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="the harness embedder on a GPU, string list in")
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--batch", type=int, default=64, help="cap on strings per batch")
    ap.add_argument("--chars", type=int, default=20000,
                    help="cap on the characters in one batch; with --batch it packs a "
                         "length-sorted list so short sentences and whole chunks both fill "
                         "the card")
    ap.add_argument("--prefix", default="passage", choices=sorted(EMBED_PREFIX))
    ap.add_argument("--model", default=EMBED_MODEL)
    ap.add_argument("--revision", default=EMBED_REVISION)
    ap.add_argument("--flush", type=int, default=2000)
    args = ap.parse_args(argv)

    if args.model != EMBED_MODEL or args.revision != EMBED_REVISION:
        raise SystemExit(f"facet_embed_gpu: this file is pinned to {EMBED_MODEL} @ "
                         f"{EMBED_REVISION}; got {args.model} @ {args.revision}")

    t0 = time.perf_counter()
    rows = []
    with open(args.src, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                got = hashlib.sha256(r["text"].encode("utf-8")).hexdigest()
                if got != r["sha"]:
                    raise SystemExit(f"facet_embed_gpu: sha mismatch on input "
                                     f"{r['sha'][:12]} -> {got[:12]}")
                rows.append((r["sha"], r["text"]))
    print(f"facet_embed_gpu | {len(rows)} strings | {sum(len(t) for _s, t in rows)} chars | "
          f"{args.model} @ {args.revision[:12]} | {args.device} {EMBED_DTYPE} | "
          f"prefix {EMBED_PREFIX[args.prefix]!r} | batch {args.batch}", flush=True)

    out = Path(args.out)
    part = out.with_suffix(".part.npz")
    done: dict = {}
    if part.is_file():
        z = np.load(part, allow_pickle=False)
        done = {str(s): v for s, v in zip(z["sha"], z["vec"].astype(np.float32))}
        print(f"  resumed {len(done)} from {part}", flush=True)

    todo = [(s, t) for s, t in rows if s not in done]
    # Batches are padded to their longest member, so a batch of mixed lengths spends most of
    # its work on padding. Sorting by length groups like with like. The model masks padding,
    # so the vectors do not depend on what a string is batched with (ENVIRONMENT: bit-identical
    # at batch 1 / 4 / 8 / 16 / 32).
    todo.sort(key=lambda r: len(r[1]))
    print(f"  {len(todo)} to embed, length-sorted", flush=True)

    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer(args.model, revision=args.revision, device=args.device,
                            trust_remote_code=True, model_kwargs={"dtype": EMBED_DTYPE})
    print(f"  model ready in {time.perf_counter() - t0:.0f}s "
          f"({m.get_embedding_dimension()} dim, {m.max_seq_length}-token context)", flush=True)

    def save(path):
        shas = list(done)
        np.savez(path, sha=np.array(shas, dtype="U64"),
                 vec=np.stack([done[s] for s in shas]).astype(np.float32))

    # Length-sorted, then packed to a character budget: a batch of 64 short sentences and a
    # batch of 4 whole chunks cost the GPU about the same, and a fixed count makes one of the
    # two wasteful. `--batch` is the cap on items, `--chars` the cap on their total.
    packs, cur, cur_chars = [], [], 0
    for sha, text in todo:
        if cur and (len(cur) >= args.batch or cur_chars + len(text) > args.chars):
            packs.append(cur)
            cur, cur_chars = [], 0
        cur.append((sha, text))
        cur_chars += len(text)
    if cur:
        packs.append(cur)
    print(f"  {len(packs)} batches, {len(todo) / max(len(packs), 1):.1f} strings a batch",
          flush=True)

    t1 = time.perf_counter()
    since = 0
    n_done = 0
    for batch in packs:
        prefixed = [EMBED_PREFIX[args.prefix] + (t or " ") for _s, t in batch]
        lengths = [len(ids) for ids in
                   m.tokenizer(prefixed, add_special_tokens=True,
                               truncation=False)["input_ids"]]
        over = [(j, n) for j, n in enumerate(lengths) if n > m.max_seq_length]
        if over:
            raise SystemExit(f"facet_embed_gpu: input past the {m.max_seq_length}-token "
                             f"context ({over[0][1]} tokens)")
        embs = m.encode(prefixed, batch_size=len(batch), convert_to_numpy=True,
                        show_progress_bar=False)
        for (sha, _t), v in zip(batch, embs):
            done[sha] = np.asarray(v, dtype=np.float32)
        since += len(batch)
        n_done += len(batch)
        n = n_done
        if since >= args.flush or n >= len(todo):
            save(part)
            since = 0
            rate = n / max(time.perf_counter() - t1, 1e-9)
            print(f"  [{n}/{len(todo)}] {rate:.1f} strings/s | "
                  f"{(len(todo) - n) / max(rate, 1e-9) / 60:.1f} min left", flush=True)

    save(out)
    meta = {"model": args.model, "revision": args.revision, "dtype": EMBED_DTYPE,
            "device": args.device, "batch": args.batch,
            "prefix": EMBED_PREFIX[args.prefix], "strings": len(rows),
            "dim": int(next(iter(done.values())).shape[0]) if done else 0,
            "wall_s": round(time.perf_counter() - t0, 1)}
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"done | {len(done)} vectors -> {out} | {time.perf_counter() - t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

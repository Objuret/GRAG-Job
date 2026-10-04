"""Score every graph edge on every facet: ONE encoder pass an edge, five numbers out.

One row per edge with the five scores. The scores are a latent strength — the heads are fitted
to comparisons and nothing anchors them to a unit — so the RANK is what carries, and the rank
is what the stability comparison against the previous round uses. Turning the ranks into
numbers in topic's units is `map_topic.py`, afterwards.

Resumable: a chunk counts as done only when the shard's file already holds one row for every
one of its tags, so an interrupted chunk is re-run whole rather than left half written.

Sharded: `--shard K/N` (K from 1 to N) takes the chunks whose `data.shard_of` is K-1, so two
machines can each take a share and the outputs merge. Each shard writes
`scores.<K>of<N>.jsonl`; when every shard's rows are on disk the merged `scores.jsonl` is
written beside them. The standalone Colab scorer carries the identical shard function.

Batching: `--batch 8` is the default because on the 1080 Ti a larger batch on 1,424-token
DeBERTa pairs oversubscribes the 11 GB card, Windows pages it silently, and the job runs about
ten times slower (measured 2026-09-17: batch 8 = 8.7 rows/s, batch 24 = 0.89).

    python test/graph/facet_pairs/score_all.py --model output/facet_pairs/model/round0/model \\
        --round 0 --rows output/facet_neural/rows_export.jsonl --device cuda --shard 1/2
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
for _p in (str(HERE), str(HERE.parent)):
    if _p not in sys.path:
        sys.path.insert(0, str(_p))

try:  # package first: the plain names collide with facet_neural's own modules
    from . import data as D
    from .model import FACETS
except ImportError:  # run as a script on the desktop
    import data as D  # noqa: E402
    from model import FACETS  # noqa: E402

BATCH = 8   # the measured setting on the 1080 Ti, 2026-09-17


def parse_shard(spec: str) -> tuple:
    """'K/N' -> (K, N), 1-based, K in 1..N. '' or '1/1' is the whole corpus."""
    spec = (spec or "").strip()
    if not spec:
        return 1, 1
    k, _, n = spec.partition("/")
    k, n = int(k), int(n)
    if n < 1 or not (1 <= k <= n):
        raise ValueError(f"--shard {spec!r}: K must be 1..N and N at least 1")
    return k, n


def shard_chunks(chunks: list, k: int, n: int) -> list:
    return [c for c in chunks if D.shard_of(c["chunk_id"], n) == k - 1]


def shard_path(out: Path, k: int, n: int) -> Path:
    return out / f"scores.{k}of{n}.jsonl"


def ranks_desc(values: list) -> list:
    """Average ranks, 1 = the largest value."""
    order = sorted(range(len(values)), key=lambda i: -values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        r = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            out[order[k]] = r
        i = j + 1
    return out


def merge_shards(out: Path, n: int) -> list:
    """Every shard file's rows, deduplicated on edge_id, sorted by edge_id."""
    seen = {}
    for k in range(1, n + 1):
        p = shard_path(out, k, n)
        if not p.is_file():
            continue
        with p.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    seen[r["edge_id"]] = r
    return [seen[e] for e in sorted(seen)]


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="the pairwise ranker over every graph edge")
    ap.add_argument("--model", required=True)
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--rows", default="output/facet_neural/rows_export.jsonl")
    ap.add_argument("--rounds-dir", default="output/facet_pairs/rounds")
    ap.add_argument("--out", default="")
    ap.add_argument("--shard", default="1/1", help="K/N, 1-based; the chunks whose shard_of is "
                                                  "K-1")
    ap.add_argument("--prev", default="", help="a previous round's scores.jsonl; default the "
                                               "highest earlier round in --rounds-dir")
    ap.add_argument("--device", default="")
    ap.add_argument("--batch", type=int, default=BATCH)
    ap.add_argument("--limit", type=int, default=0, help="first N chunks of this shard only (a "
                                                         "throughput measurement, not a layer)")
    args = ap.parse_args(argv)

    import torch
    try:
        from .model import PairRanker, encode_rows, load_tokenizer
    except ImportError:
        from model import PairRanker, encode_rows, load_tokenizer  # noqa: E402

    k, n = parse_shard(args.shard)
    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    t0 = time.perf_counter()
    out = Path(args.out or f"{args.rounds_dir}/round{args.round}")
    out.mkdir(parents=True, exist_ok=True)
    scores_path = shard_path(out, k, n)

    model, cfg = PairRanker.load(args.model, device=device)
    tok = load_tokenizer(args.model)
    max_len = int(cfg["max_length"])
    ckpt = hashlib.sha256(Path(args.model, "model.safetensors").read_bytes()).hexdigest()
    print(f"facet pairs score_all | round {args.round} | shard {k}/{n} | checkpoint "
          f"{ckpt[:16]} | max_length {max_len} | device {device} | batch {args.batch}",
          flush=True)

    all_chunks = D.load_chunks(args.rows)
    chunks = shard_chunks(all_chunks, k, n)
    print(f"  corpus {len(all_chunks)} chunks | this shard {len(chunks)}", flush=True)
    if args.limit:
        chunks = chunks[:args.limit]
    want = {c["chunk_id"]: len(c["tags"]) for c in chunks}
    n_edges = sum(want.values())

    have = {}
    if scores_path.is_file():
        with scores_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    have.setdefault(r["chunk_id"], []).append(r)
        done = {c for c, rs in have.items() if len(rs) == want.get(c, -1)}
        partial = [c for c in have if c not in done]
        if partial:
            with scores_path.open("w", encoding="utf-8") as f:
                for c, rs in have.items():
                    if c in done:
                        for r in rs:
                            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            print(f"  resume: dropped {sum(len(have[c]) for c in partial)} rows from "
                  f"{len(partial)} partly written chunks; re-run whole", flush=True)
        print(f"  resuming: {len(done)} complete chunks on disk", flush=True)
    else:
        done = set()
    todo = [c for c in chunks if c["chunk_id"] not in done]
    print(f"  {len(chunks)} chunks, {n_edges} edges | {len(todo)} chunks to run", flush=True)

    written, t1 = 0, time.perf_counter()
    with scores_path.open("a", encoding="utf-8") as f:
        for i, c in enumerate(todo, 1):
            tags = list(c["tags"])
            preds = []
            with torch.no_grad():
                for j in range(0, len(tags), args.batch):
                    b = tags[j:j + args.batch]
                    enc = encode_rows(tok, b, [c["text"]] * len(b), max_len)
                    enc = {kk: v.to(device) for kk, v in enc.items()}
                    preds.extend(model(**enc).float().cpu().tolist())   # b x 5
            for tag, row in zip(tags, preds):
                f.write(json.dumps({
                    "edge_id": D.edge_id(c["chunk_id"], tag),
                    "chunk_id": c["chunk_id"], "tag": tag,
                    "product": c.get("product"), "kind": c.get("kind"),
                    **{facet: float(v) for facet, v in zip(FACETS, row)},
                    "checkpoint": ckpt,
                }, ensure_ascii=False) + "\n")
                written += 1
            if i % 25 == 0 or i == len(todo):
                f.flush()
                el = max(time.perf_counter() - t1, 1e-9)
                print(f"  [{i}/{len(todo)}] {written} edges | {written / el:.2f} edges/s | "
                      f"{(len(todo) - i) * (el / i) / 60:.1f} min left", flush=True)

    el = max(time.perf_counter() - t1, 1e-9)
    rate = written / el if written else None
    print(f"  shard {k}/{n}: {written} edges this run | "
          f"{'-' if rate is None else '%.2f' % rate} edges/s", flush=True)

    rows_all = merge_shards(out, n)
    complete = len(rows_all) == sum(len(c["tags"]) for c in all_chunks)
    merged_path = out / "scores.jsonl"
    ranks_path = out / "ranks_raw.jsonl"
    stability = {}
    if complete:
        with merged_path.open("w", encoding="utf-8") as f:
            for r in rows_all:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        rk = {facet: ranks_desc([r[facet] for r in rows_all]) for facet in FACETS}
        with ranks_path.open("w", encoding="utf-8") as f:
            for i, r in enumerate(rows_all):
                f.write(json.dumps({"edge_id": r["edge_id"],
                                    **{facet: rk[facet][i] for facet in FACETS}}) + "\n")
        prev = Path(args.prev) if args.prev else _previous_scores(args.rounds_dir, args.round)
        if prev and prev.is_file():
            try:
                from .train import spearman
            except ImportError:
                from train import spearman  # noqa: E402
            pmap = {}
            with prev.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        r = json.loads(line)
                        pmap[r["edge_id"]] = r
            common = [r for r in rows_all if r["edge_id"] in pmap]
            for facet in FACETS:
                stability[facet] = spearman([r[facet] for r in common],
                                            [pmap[r["edge_id"]][facet] for r in common])
            stability["n_common_edges"] = len(common)
            stability["previous"] = str(prev)
        print(f"  every shard is on disk: merged {len(rows_all)} rows -> {merged_path}",
              flush=True)
    else:
        print(f"  {len(rows_all)} of {sum(len(c['tags']) for c in all_chunks)} edges on disk "
              f"across the shards present; the merge waits for the rest", flush=True)

    meta = {"round": args.round, "model": str(args.model), "checkpoint_sha256": ckpt,
            "facets": list(FACETS), "rows_export": str(args.rows),
            "shard": f"{k}/{n}",
            "shard_rule": f"sha256('{D.SHARD_SALT}' + chunk_id) % {n} == {k - 1}",
            "corpus_chunks": len(all_chunks), "shard_chunks": len(chunks),
            "shard_edges": n_edges, "edges_written_this_run": written,
            "edges_per_second": rate,
            "encoder_passes_per_edge": 1,
            "rows_on_disk_all_shards": len(rows_all), "complete": complete,
            "batch": args.batch, "device": device, "max_length": max_len,
            "ranking_stability_spearman_vs_previous_round": stability,
            "wall_s": round(time.perf_counter() - t0, 1)}
    (out / f"scores_meta.{k}of{n}.json").write_text(json.dumps(meta, indent=1),
                                                    encoding="utf-8")
    if stability:
        print("  stability vs previous round (Spearman): " + " ".join(
            f"{x} {'-' if stability[x] is None else '%.4f' % stability[x]}"
            for x in FACETS), flush=True)
    print(f"done | {written} edges written -> {scores_path} | "
          f"{time.perf_counter() - t0:.0f}s", flush=True)
    return 0


def _previous_scores(rounds_dir: str, this_round: int):
    root = Path(rounds_dir)
    if not root.is_dir():
        return None
    best = None
    for p in root.glob("round*/scores.jsonl"):
        try:
            n = int(p.parent.name.replace("round", ""))
        except ValueError:
            continue
        if n < this_round and (best is None or n > best[0]):
            best = (n, p)
    return best[1] if best else None


if __name__ == "__main__":
    sys.exit(main())

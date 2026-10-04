"""Check and concatenate the full-pass shards into one cache the laptop harness reads.

Reads `output/facet_pairs/fullcache/shard<k>/<model>.npz` (+ `.meta.json`), refuses to write
anything unless every check passes, then writes one npz in `cache_probe.py`'s cache shape.

Checks: every shard 0..N-1 present with a finished npz (no `.part.npz` left, no `FAILED_*`);
one model and one revision across shards; rows == unique edge ids == the graph's edge set (the
61,018 (chunk, tag) pairs of `output/facet_stats/<db>.jsonl` whose chunk has text in the rows
export — the ids only, no topic value is read); every array finite; per-shard row counts equal
the bundle's shard files; truncation and token statistics printed.

    python test/graph/facet_pairs/fullcache_merge.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
VEC_KEYS = [f"{p}_L-{k}" for k in (1, 2, 3, 4) for p in ("cls", "mean")]


def graph_edges() -> set:
    chunks = set()
    with open(ROOT / "output" / "facet_neural" / "rows_export.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if "chunk_id" in r and (r.get("text") or "").strip():
                chunks.add(r["chunk_id"])
    out = set()
    with open(ROOT / "output" / "facet_stats" / "herb-eval-volmax.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["chunk_id"] in chunks:
                out.add(f"{r['chunk_id']}::{r['tag']}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="verify and merge the full-pass shards")
    ap.add_argument("--dir", default=str(ROOT / "output" / "facet_pairs" / "fullcache"))
    ap.add_argument("--shards", type=int, default=8)
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    base = Path(a.dir)
    problems, parts, metas = [], [], []
    for k in range(a.shards):
        d = base / f"shard{k}"
        if not d.is_dir():
            problems.append(f"shard{k}: folder missing")
            continue
        if list(d.glob("FAILED_*")):
            problems.append(f"shard{k}: a FAILED_ marker is present")
        if list(d.glob("*.part.npz")):
            problems.append(f"shard{k}: an unfinished .part.npz is present")
        done = [p for p in d.glob("*.npz") if not p.name.endswith(".part.npz")]
        if len(done) != 1:
            problems.append(f"shard{k}: {len(done)} finished npz files, expected 1")
            continue
        z = np.load(done[0], allow_pickle=False)
        meta = json.loads(done[0].with_suffix("").with_suffix(".meta.json").read_text(encoding="utf-8")) \
            if done[0].with_suffix("").with_suffix(".meta.json").is_file() else {}
        missing = [key for key in VEC_KEYS + ["edge_id", "n_tokens", "truncated"] if key not in z.files]
        if missing:
            problems.append(f"shard{k}: arrays missing {missing}")
            continue
        n = len(z["edge_id"])
        for key in VEC_KEYS:
            if z[key].shape[0] != n or not np.isfinite(z[key].astype(np.float32)).all():
                problems.append(f"shard{k}: {key} has wrong rows or non-finite values")
        parts.append(z)
        metas.append(meta)
        print(f"shard{k}: {n:,} edges | model {meta.get('model')} @ {str(meta.get('revision'))[:12]} "
              f"| truncated {int(z['truncated'].sum())} | tokens max {int(z['n_tokens'].max())}")
    revs = {(m.get("model"), m.get("revision")) for m in metas}
    if len(revs) > 1:
        problems.append(f"more than one model/revision across shards: {sorted(map(str, revs))}")
    if not problems:
        ids = np.concatenate([z["edge_id"] for z in parts])
        want = graph_edges()
        got = set(map(str, ids))
        print(f"rows {len(ids):,} | unique edge ids {len(got):,} | graph edge set {len(want):,}")
        if len(ids) != len(got):
            problems.append(f"{len(ids) - len(got)} duplicate edge ids")
        if got != want:
            problems.append(f"edge set differs from the graph: missing {len(want - got)}, extra {len(got - want)}")
    if problems:
        print("NOT MERGED:")
        for p in problems:
            print("  -", p)
        return 1
    model, rev = next(iter(revs))
    out = Path(a.out) if a.out else base / (str(model).replace("/", "__") + ".npz")
    store = {"edge_id": ids,
             "n_tokens": np.concatenate([z["n_tokens"] for z in parts]),
             "truncated": np.concatenate([z["truncated"] for z in parts])}
    for key in VEC_KEYS:
        store[key] = np.concatenate([z[key] for z in parts])
    if all("native_logit" in z.files for z in parts):
        store["native_logit"] = np.concatenate([z["native_logit"] for z in parts])
    np.savez(out, **store)
    meta = dict(metas[0])
    meta.update({"edges": int(len(ids)), "shards": a.shards,
                 "n_truncated": int(store["truncated"].sum()),
                 "truncation_rate": float(store["truncated"].mean()),
                 "seconds": float(sum(m.get("seconds", 0.0) for m in metas)),
                 "verified": "rows == unique edge ids == graph edge set; one model and revision; all finite"})
    out.with_suffix("").with_suffix(".meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"MERGED -> {out} ({out.stat().st_size / 1e6:.0f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

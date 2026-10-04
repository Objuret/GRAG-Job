"""The training table: measured targets joined to the original (tag, chunk) text, split by chunk.

Section 14 forbids splitting by edge: every tag of one chunk stays in one partition, or the
chunk's text leaks across the split. The split here is over chunk ids, with a fixed seed, and
the three id lists are written next to the table so the frozen validation and test sets can be
read back without re-deriving them.

The model sees the ORIGINAL chunk text and the ORIGINAL tag. No counterfactual is an input.
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

FACETS = ("temporal", "why", "activity", "concreteness")


def load_texts(rows_export: str) -> dict:
    """chunk_id -> the original chunk text, from the graph export the teacher ran on."""
    out = {}
    with open(rows_export, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                if "chunk_id" in r and r.get("text"):   # the file's first line is its header
                    out[r["chunk_id"]] = r["text"]
    return out


def load_targets(targets_jsonl: str) -> list:
    out = []
    with open(targets_jsonl, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def build_table(targets: list, texts: dict) -> tuple:
    """One row per (chunk, tag) with the four facet targets, and the counts of what was left out.

    A (chunk, tag) is kept only when all four facets carry a usable target: the four heads are
    trained together on one forward pass and a missing facet would be a hole in `y`."""
    by_edge, counts = {}, {"rejected": 0, "no_text": 0, "incomplete_edges": 0}
    for t in targets:
        if t["status"] == "rejected_below_noise":
            counts["rejected"] += 1
            continue
        if t["chunk_id"] not in texts:
            counts["no_text"] += 1
            continue
        e = by_edge.setdefault((t["chunk_id"], t["tag"]), {})
        e[t["facet"]] = t
    rows = []
    for (cid, tag), fac in sorted(by_edge.items()):
        if any(f not in fac for f in FACETS):
            counts["incomplete_edges"] += 1
            continue
        rows.append({
            "chunk_id": cid, "tag": tag, "text": texts[cid],
            "kind": fac[FACETS[0]].get("kind"), "product": fac[FACETS[0]].get("product"),
            "y": [float(fac[f]["target"]) for f in FACETS],
            "repeats": [int(fac[f]["repeats"]) for f in FACETS],
            "dispersion": [float(fac[f]["dispersion"]) for f in FACETS],
        })
    return rows, counts


def split_by_chunk(rows: list, seed: int = 20260917, val: float = 0.15,
                   test: float = 0.15) -> dict:
    """Chunk-disjoint train / validation / test. The order is the sorted chunk ids shuffled
    under a fixed seed, so the same rows give the same split on any machine."""
    ids = sorted({r["chunk_id"] for r in rows})
    rnd = random.Random(seed)
    rnd.shuffle(ids)
    n = len(ids)
    n_test = max(1, int(round(test * n)))
    n_val = max(1, int(round(val * n)))
    return {
        "test": sorted(ids[:n_test]),
        "val": sorted(ids[n_test:n_test + n_val]),
        "train": sorted(ids[n_test + n_val:]),
        "seed": seed, "fractions": {"val": val, "test": test},
    }


def apply_split(rows: list, split: dict) -> dict:
    want = {p: set(split[p]) for p in ("train", "val", "test")}
    out = {p: [r for r in rows if r["chunk_id"] in want[p]] for p in want}
    return out


def token_lengths(tokenizer, rows: list) -> list:
    enc = tokenizer([r["tag"] for r in rows], [r["text"] for r in rows],
                    truncation=False, padding=False)
    return [len(x) for x in enc["input_ids"]]


def table_sha(rows: list) -> str:
    h = hashlib.sha256()
    for r in rows:
        h.update(f"{r['chunk_id']}|{r['tag']}|{r['y']}".encode("utf-8"))
    return h.hexdigest()


def main(argv: list | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="the training table, split by chunk")
    ap.add_argument("--targets", required=True, help="a facet_targets output dir")
    ap.add_argument("--rows", required=True, help="the graph export the teacher ran on")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=20260917)
    ap.add_argument("--val", type=float, default=0.15)
    ap.add_argument("--test", type=float, default=0.15)
    a = ap.parse_args(argv)

    texts = load_texts(a.rows)
    targets = load_targets(str(Path(a.targets) / "targets.jsonl"))
    rows, counts = build_table(targets, texts)
    if not rows:
        raise SystemExit("facet data: the table is empty")
    split = split_by_chunk(rows, seed=a.seed, val=a.val, test=a.test)
    tmeta = json.loads((Path(a.targets) / "meta.json").read_text(encoding="utf-8"))
    out = write_table(a.out, rows, split, counts,
                      extra={"targets_meta": tmeta, "rows_export": a.rows})
    per = {p: len([r for r in rows if r["chunk_id"] in set(split[p])])
           for p in ("train", "val", "test")}
    print(f"facet data | {len(rows)} edges over {len({r['chunk_id'] for r in rows})} chunks "
          f"| train {per['train']} ({len(split['train'])} chunks) "
          f"val {per['val']} ({len(split['val'])}) test {per['test']} ({len(split['test'])})",
          flush=True)
    print(f"  left out: {counts}", flush=True)
    print(f"-> {out}", flush=True)
    return 0


def write_table(path, rows: list, split: dict, counts: dict, extra: dict | None = None):
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "table.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (out / "split.json").write_text(json.dumps(split, indent=1), encoding="utf-8")
    meta = {"rows": len(rows), "chunks": len({r["chunk_id"] for r in rows}),
            "facets": list(FACETS), "left_out": counts, "table_sha256": table_sha(rows)}
    meta.update(extra or {})
    (out / "table_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(main())

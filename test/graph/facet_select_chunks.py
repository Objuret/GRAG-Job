"""Pick whole chunks for the counterfactual teacher, by a stated rule and nothing else.

The rule, in order:

1. The pool is every product-linked chunk with text and tags, as `facet_counterfactuals
   --export` wrote it. Nothing is read from the benchmark.
2. Chunks are allotted to record kinds in proportion to the kind's share of the pool, so the
   training set carries the corpus's own mix of slack threads, PRs, documents and transcripts.
   Every kind present gets at least one chunk.
3. Inside a kind the chunks are placed in a 3x3 grid: tag-count tercile x character-length
   tercile, both cut on that kind's own quantiles. The kind's allotment is spread over the
   nine cells round-robin, so long/short and tag-rich/tag-poor chunks enter together.
4. Inside a cell the order is sha1(chunk_id) -- a fixed, reproducible order that is not the
   graph's and not a length or tag ranking.

Splits are by chunk and follow the same digest: the sha1 of the chunk id in hex, read as a
fraction of 2**160, cut at the given train/validation shares. A chunk keeps its split whatever
else is selected, so the validation and test sets stay the same chunks as the pool grows.

    .venv/Scripts/python.exe test/graph/facet_select_chunks.py \
        --rows output/facet_neural/rows_export.jsonl --n 260 \
        --out output/facet_neural/selection.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

TRAIN_SHARE = 0.70

VAL_SHARE = 0.15


def digest(chunk_id: str) -> int:
    return int(hashlib.sha1(chunk_id.encode("utf-8")).hexdigest(), 16)


def fraction(chunk_id: str) -> float:
    """The split digest is a different hash from the selection digest. With one hash for both,
    the round-robin (which takes the smallest digests inside a cell) also takes the smallest
    fractions, and every selected chunk lands in the first split."""
    h = hashlib.sha256(("facet_neural_split:" + chunk_id).encode("utf-8")).hexdigest()
    return int(h, 16) / float(1 << 256)


def split_of(chunk_id: str) -> str:
    f = fraction(chunk_id)
    if f < TRAIN_SHARE:
        return "train"
    if f < TRAIN_SHARE + VAL_SHARE:
        return "val"
    return "test"


def terciles(values: list) -> tuple:
    s = sorted(values)
    if not s:
        return (0.0, 0.0)
    return (s[len(s) // 3], s[(2 * len(s)) // 3])


def cell(value, cuts) -> int:
    lo, hi = cuts
    return 0 if value < lo else (1 if value < hi else 2)


def read_rows(path: Path) -> list:
    rows = []
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("chunk_id") and rec.get("text") and rec.get("tags"):
                rows.append(rec)
    return rows


def select(rows: list, n: int, already: set) -> list:
    by_kind = defaultdict(list)
    for r in rows:
        by_kind[r.get("kind") or "?"].append(r)
    total = len(rows)
    kinds = sorted(by_kind, key=lambda k: -len(by_kind[k]))

    quota = {k: max(1, round(n * len(by_kind[k]) / total)) for k in kinds}
    while sum(quota.values()) > n:
        k = max(kinds, key=lambda k: quota[k])
        if quota[k] <= 1:
            break
        quota[k] -= 1
    while sum(quota.values()) < n:
        k = max(kinds, key=lambda k: len(by_kind[k]) / max(1, quota[k]))
        quota[k] += 1

    picked = []
    for k in kinds:
        pool = by_kind[k]
        tcuts = terciles([len(r["tags"]) for r in pool])
        ccuts = terciles([len(r["text"]) for r in pool])
        cells = defaultdict(list)
        for r in pool:
            cells[(cell(len(r["tags"]), tcuts), cell(len(r["text"]), ccuts))].append(r)
        for key in cells:
            cells[key].sort(key=lambda r: digest(r["chunk_id"]))
        order = sorted(cells)
        want = min(quota[k], len(pool))
        taken, i = 0, 0
        while taken < want:
            progressed = False
            for key in order:
                if taken >= want:
                    break
                if i < len(cells[key]):
                    r = cells[key][i]
                    picked.append({
                        "chunk_id": r["chunk_id"], "kind": k, "product": r.get("product"),
                        "n_tags": len(r["tags"]), "n_chars": len(r["text"]),
                        "tag_tercile": cell(len(r["tags"]), tcuts),
                        "len_tercile": cell(len(r["text"]), ccuts),
                        "split": split_of(r["chunk_id"]),
                        "preselected": r["chunk_id"] in already,
                    })
                    taken += 1
                    progressed = True
            i += 1
            if not progressed:
                break
    return picked


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="whole chunks for the counterfactual teacher")
    ap.add_argument("--rows", required=True)
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--already", default="", help="dir of chunk files already measured")
    args = ap.parse_args(argv)

    rows = read_rows(Path(args.rows))
    already = set()
    if args.already:
        for p in Path(args.already).glob("*.json"):
            if p.name.startswith("manifest.") or p.name.endswith(".failed.json"):
                continue
            try:
                already.add(json.loads(p.read_text(encoding="utf-8"))["chunk_id"])
            except (ValueError, OSError, KeyError):
                pass

    print(f"facet_select_chunks | pool {len(rows)} chunks | want {args.n} "
          f"| already measured {len(already)}", flush=True)
    picked = select(rows, args.n, already)

    counts = defaultdict(int)
    splits = defaultdict(int)
    for p in picked:
        counts[p["kind"]] += 1
        splits[p["split"]] += 1
    print("  by kind: " + ", ".join(f"{k} {counts[k]}" for k in sorted(counts)), flush=True)
    print("  by split: " + ", ".join(f"{s} {splits[s]}" for s in sorted(splits)), flush=True)
    print(f"  tags {sum(p['n_tags'] for p in picked)} "
          f"(edges x 4 facets = {sum(p['n_tags'] for p in picked) * 4} counterfactuals)",
          flush=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "rows": str(args.rows), "pool": len(rows), "n_asked": args.n,
        "n_picked": len(picked), "train_share": TRAIN_SHARE, "val_share": VAL_SHARE,
        "rule": "kind-proportional; within kind a 3x3 tag-tercile x length-tercile grid "
                "filled round-robin; within a cell by sha1(chunk_id)",
        "split_rule": "sha256('facet_neural_split:'+chunk_id)/2**256 < 0.70 train, "
                      "< 0.85 val, else test",
        "by_kind": dict(counts), "by_split": dict(splits),
        "chunks": picked,
    }, indent=1), encoding="utf-8")
    (out.parent / (out.stem + ".ids.txt")).write_text(
        "\n".join(p["chunk_id"] for p in picked) + "\n", encoding="utf-8")
    print(f"  -> {out} and {out.parent / (out.stem + '.ids.txt')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

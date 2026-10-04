"""The statistics of a written facet layer. Counts only; nothing here reads them.

    python test/graph/facet_neural/layer_stats.py \\
        --in output/facet_neural/layer/herb-eval-volmax --out .../LAYER.md
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

FACETS = ("temporal", "why", "activity", "concreteness")


def q(xs, p):
    s = sorted(xs)
    return s[min(len(s) - 1, max(0, int(round(p * (len(s) - 1)))))]


def spearman(a: list, b: list) -> float:
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    ra, rb = rank(a), rank(b)
    ma, mb = statistics.fmean(ra), statistics.fmean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = sum((x - ma) ** 2 for x in ra) ** 0.5
    db = sum((y - mb) ** 2 for y in rb) ** 0.5
    return num / (da * db) if da and db else 0.0


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="the facet layer's own statistics")
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    src = Path(args.src)
    rows = []
    with (src / "values.jsonl").open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    meta = json.loads((src / "meta.json").read_text(encoding="utf-8"))
    lines = []

    def out(s=""):
        print(s, flush=True)
        lines.append(s)

    cols = {fa: [r[fa] for r in rows] for fa in FACETS}
    by_tag, by_chunk = defaultdict(lambda: defaultdict(list)), defaultdict(lambda: defaultdict(list))
    for r in rows:
        for fa in FACETS:
            by_tag[r["tag"]][fa].append(r[fa])
            by_chunk[r["chunk_id"]][fa].append(r[fa])

    out(f"# Facet layer — {src.name}")
    out()
    out(f"{len(rows)} edges over {len({r['chunk_id'] for r in rows})} chunks and "
        f"{len(by_tag)} tags. Checkpoint `{meta['checkpoint_sha256'][:16]}`, backbone "
        f"`{meta.get('backbone')}`, output {meta.get('output_activation')}.")
    out()
    out("## Per facet")
    out()
    out("| facet | min | 5% | median | 95% | max | mean | sd | distinct | within-tag sd "
        "(median) | within-chunk sd (median) |")
    out("|---|---|---|---|---|---|---|---|---|---|---|")
    for fa in FACETS:
        v = cols[fa]
        ts = [statistics.pstdev(by_tag[t][fa]) for t in by_tag if len(by_tag[t][fa]) > 1]
        cs = [statistics.pstdev(by_chunk[c][fa]) for c in by_chunk if len(by_chunk[c][fa]) > 1]
        out(f"| {fa} | {min(v):.4f} | {q(v,.05):.4f} | {statistics.median(v):.4f} | "
            f"{q(v,.95):.4f} | {max(v):.4f} | {statistics.fmean(v):.4f} | "
            f"{statistics.pstdev(v):.4f} | {len(set(v))} | "
            f"{statistics.median(ts) if ts else float('nan'):.4f} | "
            f"{statistics.median(cs) if cs else float('nan'):.4f} |")
    out()
    out("`within-tag sd` is the spread of one tag's value across the chunks it sits on, "
        "`within-chunk sd` the spread across the tags of one chunk. A facet that were a chunk "
        "property would read 0 within a chunk; one that were a tag property would read 0 "
        "within a tag.")
    out()
    out("## Spearman between the facets")
    out()
    n = min(len(rows), 20000)
    step = max(1, len(rows) // n)
    idx = list(range(0, len(rows), step))[:n]
    out(f"Over {len(idx)} edges (every {step}th).")
    out()
    out("| | " + " | ".join(FACETS) + " |")
    out("|---|" + "---|" * len(FACETS))
    for a in FACETS:
        cells = []
        for b in FACETS:
            cells.append("1.000" if a == b else
                         f"{spearman([rows[i][a] for i in idx], [rows[i][b] for i in idx]):.3f}")
        out(f"| {a} | " + " | ".join(cells) + " |")
    out()

    if args.out:
        Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"-> {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

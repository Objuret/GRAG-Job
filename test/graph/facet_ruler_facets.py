"""Do the four facets separate, per ruler — and the cleaner paired test.

Reads what `facet_rulers` wrote plus the counterfactual files, and prints, for every ruler
present:

  1. the 4x4 Spearman matrix between the four facets' signed deltas across edges;
  2. per edge, the spread (sd and range) of its four deltas against that ruler's own noise;
  3. the share of edges whose four deltas all sit within the ruler's noise of each other;
  4. R(T,C) on the ORIGINAL text — its distribution — and, for the sentence-level rulers, the
     share of edges whose touched sentence contains the tag phrase verbatim;
  5. the paired AUC restricted to counterfactuals whose edited sentences carry NO other tag of
     the chunk, which is the paired test with the shared-content confound removed.

Counts only. Nothing here chooses a ruler.

    python test/graph/facet_ruler_facets.py --rulers output/facet_neural/rulers/main2 \\
        --cf output/facet_neural/counterfactuals/herb-eval-volmax --out .../FACETSEP.md
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "prod", ROOT / "test"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from graph.facet_edits import FACETS                                        # noqa: E402
from graph import facet_rulers as fr                                        # noqa: E402


def read(p: Path) -> list:
    out = []
    if p.is_file():
        with p.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    return out


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
            avg = (i + j) / 2.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    ra, rb = rank(a), rank(b)
    ma, mb = statistics.fmean(ra), statistics.fmean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = math.sqrt(sum((x - ma) ** 2 for x in ra))
    db = math.sqrt(sum((y - mb) ** 2 for y in rb))
    return num / (da * db) if da and db else float("nan")


def touched_info(cf_dir: Path, chunk_ids: set) -> dict:
    """(chunk, tag, facet) -> {tag_verbatim, other_tags_in_touched, n_touched}.

    Recomputed from the stored original text and the stored edit list, never trusted from the
    model. `other_tags_in_touched` is the number of the chunk's OTHER tags whose phrase appears
    verbatim in the sentences this intervention touched."""
    out = {}
    for p in sorted(cf_dir.glob("*.json")):
        if p.name.startswith("manifest.") or p.name.endswith(".failed.json"):
            continue
        rec = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(rec.get("edges"), list) or rec["chunk_id"] not in chunk_ids:
            continue
        text = rec["text"]
        sents = fr.sentences(text)
        tags = [e["t"] for e in rec["edges"]]
        low = [t.lower() for t in tags]
        for edge in rec["edges"]:
            tag = edge["t"]
            for facet in FACETS:
                cf = edge[facet]
                if not cf["changed"] or not cf["reconstruction_ok"]:
                    continue
                o_spans, _n = fr.edit_spans(text, cf.get("edits") or [])
                hit = fr.sentences_touching(sents, o_spans)
                blob = " ".join(sents[i][0] for i in hit).lower()
                others = sum(1 for t, tl in zip(tags, low)
                             if t != tag and tl in blob)
                out[(rec["chunk_id"], tag, facet)] = {
                    "tag_verbatim": tag.lower() in blob,
                    "other_tags": others,
                    "n_touched": len(hit),
                }
    return out


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="facet separation and the clean paired test")
    ap.add_argument("--rulers", required=True, action="append")
    ap.add_argument("--cf", required=True, action="append")
    ap.add_argument("--sentence-cache", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    if args.sentence_cache:
        fr.load_sentence_cache(args.sentence_cache)

    rows, nulls = [], []
    for d in args.rulers:
        rows.extend(read(Path(d) / "rulers.jsonl"))
        nulls.extend(read(Path(d) / "null.jsonl"))
    rows = [r for r in rows if r["reconstruction_ok"]]
    names = []
    for r in rows:
        for k in r.get("delta", {}):
            if k not in names:
                names.append(k)

    noise = {}
    for n in names:
        d = [abs(r["delta"][n]) for r in nulls if r.get("delta", {}).get(n) is not None]
        noise[n] = q(d, 0.95) if d else None

    chunk_ids = {r["chunk_id"] for r in rows}
    info = {}
    for d in args.cf:
        info.update(touched_info(Path(d), chunk_ids))

    lines = []

    def out(s=""):
        print(s, flush=True)
        lines.append(s)

    out("# Do the four facets separate, per ruler")
    out()
    out(f"{len(rows)} usable (tag, facet) rows over {len(chunk_ids)} chunks, "
        f"{len(nulls)} null rows. Noise is each ruler's own p95 |delta| over its own null.")
    out()

    # edges that carry all four facets
    by_edge = {}
    for r in rows:
        by_edge.setdefault((r["chunk_id"], r["tag"]), {})[r["facet"]] = r
    edges = {k: v for k, v in by_edge.items() if all(f in v for f in FACETS)}
    out(f"Edges carrying all four facets: **{len(edges)}**.")
    out()

    for n in names:
        nz = noise[n]
        vals = {k: [v[f]["delta"].get(n) for f in FACETS] for k, v in edges.items()}
        vals = {k: v for k, v in vals.items() if all(x is not None for x in v)}
        if not vals:
            out(f"## {n} — no rows carry this ruler")
            out()
            continue
        out(f"## {n}  (noise {('%.4f' % nz) if nz is not None else '—'}, "
            f"{len(vals)} complete edges)")
        out()

        # 1. Spearman between facets
        out("### 1. Spearman between the four facets' deltas, across edges")
        out()
        cols = {f: [vals[k][i] for k in vals] for i, f in enumerate(FACETS)}
        out("| | " + " | ".join(FACETS) + " |")
        out("|---|" + "---|" * len(FACETS))
        for a in FACETS:
            cells = ["1.000" if a == b else f"{spearman(cols[a], cols[b]):.3f}" for b in FACETS]
            out(f"| {a} | " + " | ".join(cells) + " |")
        out()

        # 2 and 3. per-edge spread against noise
        sds = [statistics.pstdev(v) for v in vals.values()]
        rngs = [max(v) - min(v) for v in vals.values()]
        out("### 2. Per-edge spread of the four deltas")
        out()
        out("| statistic | p5 | median | p95 | max | / noise (median) |")
        out("|---|---|---|---|---|---|")
        for label, xs in (("sd of the four", sds), ("range of the four", rngs)):
            med = statistics.median(xs)
            out(f"| {label} | {q(xs,.05):.4f} | {med:.4f} | {q(xs,.95):.4f} | {max(xs):.4f} | "
                f"{(med/nz):.2f} |" if nz else
                f"| {label} | {q(xs,.05):.4f} | {med:.4f} | {q(xs,.95):.4f} | {max(xs):.4f} | — |")
        out()
        if nz:
            within = sum(1 for v in vals.values() if (max(v) - min(v)) <= nz)
            out(f"### 3. Edges whose four deltas all sit within the ruler's noise of each other: "
                f"**{within}/{len(vals)} = {within/len(vals):.1%}**")
        out()

        # 4. R on the original
        out("### 4. R(T,C) on the original text")
        out()
        rv = [r["R"][n] for r in rows if r.get("R", {}).get(n) is not None]
        if rv:
            out(f"| n | min | p5 | median | p95 | max | sd |")
            out("|---|---|---|---|---|---|---|")
            out(f"| {len(rv)} | {min(rv):.4f} | {q(rv,.05):.4f} | {statistics.median(rv):.4f} | "
                f"{q(rv,.95):.4f} | {max(rv):.4f} | {statistics.pstdev(rv):.4f} |")
        out()
        if n in ("sent_max", "changed_span", "sent_mean"):
            have = [info[(r["chunk_id"], r["tag"], r["facet"])]
                    for r in rows
                    if (r["chunk_id"], r["tag"], r["facet"]) in info]
            if have:
                vb = sum(1 for h in have if h["tag_verbatim"])
                nt = [h["n_touched"] for h in have]
                out(f"Touched sentences contain the tag phrase verbatim on "
                    f"**{vb}/{len(have)} = {vb/len(have):.1%}** of changed interventions; "
                    f"sentences touched: median {statistics.median(nt):.0f}, "
                    f"p95 {q(nt,.95)}, max {max(nt)}.")
                out()

    # 5. the clean paired test
    out("## 5. The paired test with the shared-content confound removed")
    out()
    out("The paired test reads the same counterfactual for the targeted tag and for the other "
        "tags of the chunk. When another tag's phrase appears in the very sentences the "
        "intervention edited, that tag legitimately shares the content and should move too. "
        "Restricting to counterfactuals whose edited sentences carry NO other tag of the chunk "
        "removes that.")
    out()
    bycf = {}
    for r in nulls:
        bycf.setdefault((r["chunk_id"], r["facet"], r.get("cf_sha256")), []).append(r)
    out("| ruler | all counterfactuals | AUC | clean counterfactuals | AUC (clean) |")
    out("|---|---|---|---|---|")
    for n in names:
        pos_a, neg_a, pos_c, neg_c = [], [], [], []
        for r in rows:
            if not r["changed"] or r["delta"].get(n) is None:
                continue
            others = bycf.get((r["chunk_id"], r["facet"], r.get("cf_sha256")), [])
            od = [o["delta"][n] for o in others if o.get("delta", {}).get(n) is not None]
            if not od:
                continue
            pos_a.append(r["delta"][n])
            neg_a.extend(od)
            h = info.get((r["chunk_id"], r["tag"], r["facet"]))
            if h and h["other_tags"] == 0:
                pos_c.append(r["delta"][n])
                neg_c.extend(od)

        def auc(pos, neg):
            if not pos or not neg:
                return None
            g = sum(1 for a in pos for b in neg if a > b)
            t = sum(1 for a in pos for b in neg if a == b)
            return (g + 0.5 * t) / (len(pos) * len(neg))
        a_all, a_cl = auc(pos_a, neg_a), auc(pos_c, neg_c)
        out(f"| {n} | {len(pos_a)} | {('%.3f' % a_all) if a_all is not None else '—'} | "
            f"{len(pos_c)} | {('%.3f' % a_cl) if a_cl is not None else '—'} |")
    out()

    if args.out:
        Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"-> {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

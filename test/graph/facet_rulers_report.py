"""Read what `facet_rulers` wrote and print the comparison tables, one per candidate ruler.

Correction 2 asks which ruler "behaves consistently with the intervention semantics". The
intervention removes facet F's contribution to tag T's relevance, so on its own scale a ruler
that measures that relationship must:

  1. fall when the contribution is removed — delta = R(T,C) - R(T,C^(-F,T)) above its noise;
  2. not move when the intervention was aimed at a different tag and touched no sentence this
     tag is read on — that is the null, and its spread IS this ruler's noise;
  3. separate the two — the signal's size against that noise;
  4. give the same answer when the same (tag, chunk, facet) is intervened on twice.

Noise is taken per ruler from its own null rows as the 95th percentile of |delta|. Nothing is
inherited from COS_NOISE and no width is chosen.

    python test/graph/facet_rulers_report.py --in output/facet_neural/rulers/<name>
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

FACETS = ("temporal", "why", "activity", "concreteness")


def read(p: Path) -> list:
    out = []
    if not p.is_file():
        return out
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def q(xs: list, p: float):
    if not xs:
        return None
    s = sorted(xs)
    i = min(len(s) - 1, max(0, int(round(p * (len(s) - 1)))))
    return s[i]


def fmt(x, n=4):
    return "—" if x is None else f"{x:.{n}f}"


def rulers_in(rows: list) -> list:
    seen = []
    for r in rows:
        for k in r.get("delta", {}):
            if k not in seen:
                seen.append(k)
    return seen


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="the ruler comparison tables")
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--repeats", default="", help="a second rulers dir over the same chunks, "
                                                  "generated independently, for dispersion")
    ap.add_argument("--out", default="", help="write the tables here as well as printing")
    args = ap.parse_args(argv)

    src = Path(args.src)
    rows = read(src / "rulers.jsonl")
    nulls = read(src / "null.jsonl")
    if not rows:
        raise SystemExit(f"facet_rulers_report: no rows under {src}")
    meta = json.loads((src / "meta.json").read_text(encoding="utf-8"))
    lines = []

    def out(s=""):
        print(s, flush=True)
        lines.append(s)

    names = rulers_in(rows)
    usable = [r for r in rows if r["reconstruction_ok"]]
    dropped = len(rows) - len(usable)
    out(f"# Ruler comparison — {src.name}")
    out()
    out(f"Source `{meta['source']}`, {meta['chunks']} chunks, {len(rows)} (tag, facet) rows, "
        f"{dropped} dropped for a failed reconstruction, {len(usable)} usable, "
        f"{len(nulls)} null rows.")
    out(f"Embedder `{meta['embed_model']}` @ `{meta['embed_revision'][:12]}`, "
        f"{meta['embed_dtype']}, prefix {meta['embed_prefix']}. "
        f"Cross-encoder `{meta.get('xenc_model')}`. Splitter {meta['sentence_splitter']}.")
    out()

    # ---- noise, per ruler, from its own null
    noise = {}
    out("## 1. Each ruler's noise, on its own scale")
    out()
    out("Null = a counterfactual built for a DIFFERENT tag whose changed sentences do not meet "
        "this tag's own best sentence. The ruler should not move. Noise is the 95th percentile "
        "of |delta| over those rows.")
    out()
    out("| ruler | null rows | median delta | sd | p95 \\|delta\\| = noise | max \\|delta\\| |")
    out("|---|---|---|---|---|---|")
    for n in names:
        d = [r["delta"][n] for r in nulls if r.get("delta", {}).get(n) is not None]
        if not d:
            noise[n] = None
            out(f"| {n} | 0 | — | — | — | — |")
            continue
        ab = [abs(x) for x in d]
        noise[n] = q(ab, 0.95)
        sd = statistics.pstdev(d) if len(d) > 1 else 0.0
        out(f"| {n} | {len(d)} | {fmt(statistics.median(d))} | {fmt(sd)} | "
            f"{fmt(noise[n])} | {fmt(max(ab))} |")
    out()

    # ---- signed delta distribution per facet per ruler
    out("## 2. Signed delta per facet — `R(T,C) - R(T,C^(-F,T))`")
    out()
    out("Only rows the teacher actually changed. An unchanged counterfactual is a measured zero "
        "and is counted separately in table 4.")
    out()
    for n in names:
        nz = noise[n]
        out(f"### {n}  (noise {fmt(nz)})")
        out()
        out("| facet | n | min | p5 | median | p95 | max | mean | > +noise | within noise | "
            "< −noise |")
        out("|---|---|---|---|---|---|---|---|---|---|---|")
        for f in FACETS + ("ALL",):
            d = [r["delta"][n] for r in usable
                 if r["changed"] and (f == "ALL" or r["facet"] == f)
                 and r.get("delta", {}).get(n) is not None]
            if not d:
                out(f"| {f} | 0 | | | | | | | | | |")
                continue
            if nz is None:
                up = mid = dn = None
                ups = mids = dns = "—"
            else:
                up = sum(1 for x in d if x > nz) / len(d)
                dn = sum(1 for x in d if x < -nz) / len(d)
                mid = 1 - up - dn
                ups, mids, dns = f"{up:.1%}", f"{mid:.1%}", f"{dn:.1%}"
            out(f"| {f} | {len(d)} | {fmt(min(d))} | {fmt(q(d, .05))} | "
                f"{fmt(statistics.median(d))} | {fmt(q(d, .95))} | {fmt(max(d))} | "
                f"{fmt(statistics.fmean(d))} | {ups} | {mids} | {dns} |")
        out()

    # ---- separation
    out("## 3. Separation — the signal against the ruler's own noise")
    out()
    out("| ruler | median delta (changed) | noise p95 | median/noise | share > +noise | "
        "share < −noise | argmax sentence moved |")
    out("|---|---|---|---|---|---|---|")
    for n in names:
        d = [r["delta"][n] for r in usable
             if r["changed"] and r.get("delta", {}).get(n) is not None]
        if not d:
            continue
        nz = noise[n]
        med = statistics.median(d)
        ratio = (med / nz) if nz else None
        up = sum(1 for x in d if nz is not None and x > nz) / len(d) if nz else None
        dn = sum(1 for x in d if nz is not None and x < -nz) / len(d) if nz else None
        moved = [r for r in usable if r["changed"]]
        mv = sum(1 for r in moved if r.get("argmax_moved")) / len(moved) if moved else None
        out(f"| {n} | {fmt(med)} | {fmt(nz)} | {fmt(ratio, 2)} | "
            f"{'—' if up is None else f'{up:.1%}'} | "
            f"{'—' if dn is None else f'{dn:.1%}'} | "
            f"{'—' if mv is None else f'{mv:.1%}'} |")
    out()

    # ---- paired: the same counterfactual read for the targeted tag and for the others
    out("## 3b. Paired — the SAME counterfactual text, the targeted tag against the others")
    out()
    out("For one counterfactual the targeted tag's delta and every other tag's delta are read "
        "off the same two texts, so whatever the edit does to length or wording is common to "
        "both and cancels. A ruler that measures the targeted relationship puts the targeted "
        "tag above the others; a ruler that measures the edit itself does not.")
    out()
    out("| ruler | counterfactuals | median targeted − median other | targeted above the "
        "others | AUC (targeted vs other) |")
    out("|---|---|---|---|---|")
    bycf = {}
    for r in nulls:
        bycf.setdefault((r["chunk_id"], r["facet"], r.get("cf_sha256")), []).append(r)
    for n in names:
        diffs, wins, pos, neg = [], 0, [], []
        for r in usable:
            if not r["changed"] or r["delta"].get(n) is None:
                continue
            others = bycf.get((r["chunk_id"], r["facet"], r.get("cf_sha256")), [])
            od = [o["delta"][n] for o in others if o.get("delta", {}).get(n) is not None]
            if not od:
                continue
            diffs.append(r["delta"][n] - statistics.median(od))
            wins += 1 if r["delta"][n] > max(od) else 0
            pos.append(r["delta"][n])
            neg.extend(od)
        if not diffs:
            out(f"| {n} | 0 | — | — | — |")
            continue
        greater = sum(1 for a in pos for b in neg if a > b)
        ties = sum(1 for a in pos for b in neg if a == b)
        auc = (greater + 0.5 * ties) / (len(pos) * len(neg))
        out(f"| {n} | {len(diffs)} | {fmt(statistics.median(diffs))} | "
            f"{wins / len(diffs):.1%} | {auc:.3f} |")
    out()

    # ---- unchanged
    out("## 4. Unchanged counterfactuals — the legitimate zeros")
    out()
    unc = [r for r in usable if not r["changed"]]
    out("| facet | unchanged | changed | share unchanged |")
    out("|---|---|---|---|")
    for f in FACETS:
        u = sum(1 for r in unc if r["facet"] == f)
        c = sum(1 for r in usable if r["changed"] and r["facet"] == f)
        out(f"| {f} | {u} | {c} | {u / max(u + c, 1):.1%} |")
    out()
    out(f"Every unchanged row carries `delta = 0.0` on every ruler by construction "
        f"({len(unc)} rows): nothing was removed, so nothing was lost.")
    out()

    # ---- tag- and facet-specificity on the same chunk
    out("## 5. Specificity on one chunk — does the ruler tell tags and facets apart?")
    out()
    out("Within one chunk, the spread of a ruler's deltas ACROSS tags (one facet) and ACROSS "
        "facets (one tag), against that ruler's noise. A ruler blind to the tag gives a spread "
        "at noise level.")
    out()
    out("| ruler | median across-tag spread (one facet) | median across-facet spread (one tag) "
        "| noise | tag spread / noise | facet spread / noise |")
    out("|---|---|---|---|---|---|")
    for n in names:
        by_cf, by_ct = {}, {}
        for r in usable:
            if r.get("delta", {}).get(n) is None:
                continue
            by_cf.setdefault((r["chunk_id"], r["facet"]), []).append(r["delta"][n])
            by_ct.setdefault((r["chunk_id"], r["tag"]), []).append(r["delta"][n])
        ts = [max(v) - min(v) for v in by_cf.values() if len(v) > 1]
        fs = [max(v) - min(v) for v in by_ct.values() if len(v) > 1]
        nz = noise[n]
        mt = statistics.median(ts) if ts else None
        mf = statistics.median(fs) if fs else None
        out(f"| {n} | {fmt(mt)} | {fmt(mf)} | {fmt(nz)} | "
            f"{fmt(mt / nz, 2) if (mt and nz) else '—'} | "
            f"{fmt(mf / nz, 2) if (mf and nz) else '—'} |")
    out()

    # ---- repeats
    if args.repeats:
        rep = read(Path(args.repeats) / "rulers.jsonl")
        key = lambda r: (r["chunk_id"], r["tag"], r["facet"])  # noqa: E731
        a = {key(r): r for r in usable}
        b = {key(r): r for r in rep if r["reconstruction_ok"]}
        both = sorted(set(a) & set(b))
        out("## 6. Repeat dispersion — the same (tag, chunk, facet) intervened on twice")
        out()
        out(f"{len(both)} relationships generated independently under the same teacher "
            f"configuration.")
        out()
        out("| ruler | pairs | median \\|d1 − d2\\| | p95 \\|d1 − d2\\| | noise | median signal | "
            "dispersion / signal |")
        out("|---|---|---|---|---|---|---|")
        for n in names:
            dd, sig = [], []
            for k in both:
                x, y = a[k]["delta"].get(n), b[k]["delta"].get(n)
                if x is None or y is None:
                    continue
                dd.append(abs(x - y))
                sig.extend([x, y])
            if not dd:
                continue
            ms = statistics.median([s for s in sig if s > 0]) if any(s > 0 for s in sig) else None
            md = statistics.median(dd)
            out(f"| {n} | {len(dd)} | {fmt(md)} | {fmt(q(dd, .95))} | {fmt(noise[n])} | "
                f"{fmt(ms)} | {fmt(md / ms, 2) if ms else '—'} |")
        out()

    if args.out:
        Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"-> {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

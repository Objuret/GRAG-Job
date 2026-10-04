"""Turn the ruler measurements into the supervision targets.

Correction 1 fixes the target exactly:

    target_F(T,C) = R(T,C) - R(T,C^(-F,T))

signed, in the ruler's own units. No SCALE, no clipping, no absolute value, no rescaling.

Three rules, all from the specification, applied here and recorded on every row:

  * an intervention the teacher did not make is a measured zero — the facet contributed
    nothing, so nothing was lost. It is supervision, not a missing value;
  * a counterfactual whose edit list did not reconstruct is dropped and counted (§11,
    "malformed interventions must be regenerated or excluded");
  * a delta below minus the ruler's own noise means the intervention or the measurement
    failed. Correction 1 forbids `abs()` and forbids clamping: the row is rejected from
    supervision, kept in full on disk, and counted.

Where the same (chunk, tag, facet) was generated twice, every delta is stored, the dispersion
is stored, and the supervision value is their median — a location estimator over the repeats,
with nothing chosen.

    python test/graph/facet_targets.py --rulers output/facet_neural/rulers/main \\
        --ruler sent_max --out output/facet_neural/targets/main
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
    if p.is_file():
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
    return s[min(len(s) - 1, max(0, int(round(p * (len(s) - 1)))))]


def noise_of(nulls: list, ruler: str):
    d = [abs(r["delta"][ruler]) for r in nulls if r.get("delta", {}).get(ruler) is not None]
    return q(d, 0.95), len(d)


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="the measured counterfactual targets")
    ap.add_argument("--rulers", required=True, action="append",
                    help="a facet_rulers output dir; repeat the flag for repeat generations")
    ap.add_argument("--ruler", required=True, help="the resolved R")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    rows, nulls, metas = [], [], []
    for d in args.rulers:
        d = Path(d)
        rows.append(read(d / "rulers.jsonl"))
        nulls.extend(read(d / "null.jsonl"))
        metas.append(json.loads((d / "meta.json").read_text(encoding="utf-8")))
    R = args.ruler
    noise, n_null = noise_of(nulls, R)
    if noise is None:
        raise SystemExit(f"facet_targets: no null rows carry ruler {R!r}; its noise is unmeasured")
    print(f"facet_targets | ruler {R} | noise p95|delta| {noise:.6f} over {n_null} null rows",
          flush=True)

    by_key: dict = {}
    dropped_recon = 0
    for gen, group in enumerate(rows):
        for r in group:
            if r.get("delta", {}).get(R) is None:
                continue
            if not r["reconstruction_ok"]:
                dropped_recon += 1
                continue
            k = (r["chunk_id"], r["tag"], r["facet"])
            e = by_key.setdefault(k, {
                "chunk_id": r["chunk_id"], "kind": r.get("kind"), "product": r.get("product"),
                "tag": r["tag"], "facet": r["facet"], "ruler": R,
                "measurements": [],
            })
            e["measurements"].append({
                "generation": gen, "R_original": r["R"][R], "R_remaining": r["R_cf"][R],
                "delta": r["delta"][R], "changed": r["changed"], "n_edits": r.get("n_edits"),
                "cf_sha256": r.get("cf_sha256"), "note": r.get("note", ""),
                "argmax_moved": r.get("argmax_moved"),
            })

    out_rows, counts = [], {"kept": 0, "rejected_below_noise": 0, "zero_unchanged": 0,
                            "repeated": 0}
    for k in sorted(by_key):
        e = by_key[k]
        ds = [m["delta"] for m in e["measurements"]]
        e["repeats"] = len(ds)
        e["dispersion"] = (max(ds) - min(ds)) if len(ds) > 1 else 0.0
        e["dispersion_sd"] = statistics.pstdev(ds) if len(ds) > 1 else 0.0
        value = statistics.median(ds)
        e["target"] = value
        e["selection_rule"] = ("the single measurement" if len(ds) == 1
                               else f"median of {len(ds)} independent generations")
        e["noise"] = noise
        if len(ds) > 1:
            counts["repeated"] += 1
        if all(not m["changed"] for m in e["measurements"]):
            e["status"] = "zero_unchanged"
            e["target"] = 0.0
            e["selection_rule"] = ("no intervention was needed: the teacher reported this facet "
                                   "contributes nothing, so the measured loss is exactly 0")
            counts["zero_unchanged"] += 1
            counts["kept"] += 1
        elif value < -noise:
            e["status"] = "rejected_below_noise"
            counts["rejected_below_noise"] += 1
        else:
            e["status"] = "kept"
            counts["kept"] += 1
        out_rows.append(e)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "targets.jsonl").open("w", encoding="utf-8") as f:
        for e in out_rows:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    kept = [e for e in out_rows if e["status"] != "rejected_below_noise"]
    stats = {}
    for fa in FACETS:
        d = [e["target"] for e in kept if e["facet"] == fa]
        if not d:
            continue
        stats[fa] = {
            "n": len(d), "min": min(d), "p5": q(d, .05), "median": statistics.median(d),
            "p95": q(d, .95), "max": max(d), "mean": statistics.fmean(d),
            "sd": statistics.pstdev(d),
            "zeros": sum(1 for x in d if x == 0.0),
        }
    meta = {
        "ruler": R, "noise_p95_abs_delta": noise, "null_rows": n_null,
        "sources": args.rulers, "ruler_meta": metas,
        "target_definition": "R(T,C) - R(T,C^(-F,T)), signed, no SCALE (Correction 1)",
        "dropped_reconstruction_failed": dropped_recon,
        "relationships": len(out_rows), "chunks": len({e["chunk_id"] for e in out_rows}),
        "counts": counts, "per_facet": stats,
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")

    print(f"  relationships {len(out_rows)} over {meta['chunks']} chunks | kept "
          f"{counts['kept']} | rejected below -noise {counts['rejected_below_noise']} | "
          f"measured zeros {counts['zero_unchanged']} | repeated {counts['repeated']} | "
          f"dropped for reconstruction {dropped_recon}", flush=True)
    print("| facet | n | min | p5 | median | p95 | max | mean | sd | zeros |", flush=True)
    print("|---|---|---|---|---|---|---|---|---|---|", flush=True)
    for fa, s in stats.items():
        print(f"| {fa} | {s['n']} | {s['min']:.4f} | {s['p5']:.4f} | {s['median']:.4f} | "
              f"{s['p95']:.4f} | {s['max']:.4f} | {s['mean']:.4f} | {s['sd']:.4f} | "
              f"{s['zeros']} |", flush=True)
    print(f"-> {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Identify what the current pair labels constrain in the linear facet readout.

The counterfactual coefficients below are diagnostic witnesses, NOT candidate
retrievers: they deliberately fit the eight controls to opposite arbitrary
margins while preserving every fitting AND validation comparison score gap.
No heldout observation is used to construct either witness.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from scipy.linalg import svd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "prod"), str(ROOT / "test")]
from graph.facet_pairs import data as D
from artefact.facet_measurement import probabilities

ROUND = ROOT / "output/facet_pairs/rounds/round1"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--controls", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    rows = D.load_answer_rows(str(ROOT / "output/facet_pairs/answers"))
    obs = D.observations(rows)
    part = D.partition_observations(obs)
    tv = D.training_val_split(part["train"])
    learned = torch.load(ROUND / "model/head.pt", map_location="cpu", weights_only=True)
    W = learned["net.weight"].numpy().astype(float)
    eta = learned["tie_log"].numpy().astype(float)
    standard = np.load(ROUND / "model/standardisation.npz")
    cachepath = ROOT / "output/facet_pairs/fullcache/Alibaba-NLP__gte-reranker-modernbert-base.npz"
    z = np.load(cachepath, allow_pickle=False)
    ids = list(z["edge_id"])
    index = {e: i for i, e in enumerate(ids)}
    needed = sorted({o[s] for o in obs for s in ("a_edge_id", "b_edge_id")})
    raw = z["mean_L-3"]
    F = raw[[index[e] for e in needed]].astype(float)
    del raw
    F = (F-standard["mu"])/standard["sd"]
    lookup = {e: i for i, e in enumerate(needed)}

    def differences(oo):
        return np.array([F[lookup[o["a_edge_id"]]]-F[lookup[o["b_edge_id"]]] for o in oo])

    unique = {(o["a_edge_id"], o["b_edge_id"]): o for o in part["train"]}
    design = differences(list(unique.values()))
    _, s, vh = svd(design, full_matrices=False)
    tolerance = np.finfo(float).eps * max(design.shape) * s[0]
    rank = int((s > tolerance).sum())
    basis = vh[:rank]
    identified = (W @ basis.T) @ basis
    free = W-identified
    control_z = np.load(args.controls, allow_pickle=False)
    c = (control_z["features"].astype(float)-standard["mu"])/standard["sd"]
    n = len(control_z["tags"])
    c = c.reshape(n, n, -1)
    G = np.array([c[i, i]-c[i, (i+4)%n] for i in range(n)])
    Gfree = G-(G@basis.T)@basis
    out = {"created_utc": datetime.now(timezone.utc).isoformat(), "protocol": __doc__,
           "constraint_pairs": len(unique), "features": W.shape[1],
           "design_rank": rank, "unconstrained_dimensions": W.shape[1]-rank,
           "rank_tolerance": float(tolerance), "smallest_singular_value": float(s[-1]),
           "free_control_contrast_rank": int(np.linalg.matrix_rank(Gfree)),
           "per_facet": {}}
    held = part["heldout"]
    for fi, facet in enumerate(D.FACETS):
        block = {"weight_norm": float(np.linalg.norm(W[fi])),
                 "unconstrained_weight_norm": float(np.linalg.norm(free[fi])),
                 "control_gaps": (G@W[fi]).tolist(),
                 "identified_control_gaps": (G@identified[fi]).tolist(),
                 "unconstrained_control_gaps": (G@free[fi]).tolist()}
        if facet == "temporal":
            block["witnesses"] = {}
            for target in (-1., 1.):
                delta = np.linalg.lstsq(Gfree, np.full(n, target)-G@W[fi], rcond=None)[0]
                witness = W[fi]+delta
                preserved = float(np.max(np.abs(design@delta)))
                achieved = float(np.max(np.abs(G@witness-target)))
                if preserved > 1e-7 or achieved > 1e-7:
                    raise RuntimeError("witness does not satisfy its claimed constraints")
                evaluation = {}
                for label, oo in [("fit", tv["fit"]), ("validation", tv["val"]), ("heldout", held)]:
                    oo = [o for o in oo if o["facet"] == facet]
                    x = differences(oo)
                    y = np.array([D.OUTCOMES.index(o["outcome"]) for o in oo])
                    values = {}
                    for name, ww in [("original", W[fi]), ("witness", witness)]:
                        gap = x@ww
                        p = probabilities(gap, 1, eta[fi])
                        decided = y < 2
                        ok = ((gap > 0)&(y == 0)) | ((gap < 0)&(y == 1))
                        values[name] = {"nll": float(-np.log(np.maximum(p[np.arange(len(y)), y],1e-300)).mean()),
                                        "decided_agreement": float(ok[decided].mean())}
                    evaluation[label] = values
                block["witnesses"][str(target)] = {
                    "target_control_margin_arbitrary_for_demonstration": target,
                    "coefficient_change_norm": float(np.linalg.norm(delta)),
                    "new_weight_norm": float(np.linalg.norm(witness)),
                    "max_fit_validation_gap_change": preserved,
                    "max_control_target_error": achieved, "evaluation": evaluation}
        out["per_facet"][facet] = block
    out["source_sha256"] = {}
    for p in [Path(__file__), ROUND / "model/head.pt", args.controls,
              ROUND / "model/standardisation.npz"]:
        with p.open("rb") as fp:
            out["source_sha256"][str(p)] = hashlib.file_digest(fp,"sha256").hexdigest()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(out,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in out.items() if k not in ("per_facet","source_sha256","protocol")}))
    print(json.dumps(out["per_facet"]["temporal"],indent=2))


if __name__ == "__main__":
    main()

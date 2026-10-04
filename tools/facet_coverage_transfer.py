"""Exploratory coverage intervention, never a serving-model repair.

Add six relevant-versus-unrelated constraints, leaving both subjects of the other
two contrasts out. Find the smallest coefficient change satisfying those six
constraints while preserving every old fitting AND validation score difference.
Evaluate the two excluded controls and the old heldout labels after fitting.

Four folds exclude {i,i+4}; neither excluded subject occurs in a training contrast.
Margins .25, 1, 2 are a declared sensitivity grid, not calibrated semantic units.
No grid point is selected. Controls have already been inspected: this is diagnostic
cross-validation, not a fresh prospective validation or a retrieval experiment.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from scipy.linalg import svd
from scipy.optimize import minimize
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "prod"), str(ROOT / "test")]
from graph.facet_pairs import data as D
from artefact.facet_measurement import probabilities


def minimum_change(basis, contrasts, original, margin):
    """Closest coefficients obeying contrasts, restricted to basis row span."""
    a = contrasts @ basis.T
    bound = margin - contrasts @ original
    result = minimize(lambda u: (.5 * (u @ u), u), np.zeros(len(basis)), jac=True,
                      method="SLSQP", constraints={"type": "ineq",
                          "fun": lambda u: a @ u - bound, "jac": lambda u: a},
                      options={"ftol": 1e-11, "maxiter": 1000})
    if not result.success or np.min(a @ result.x - bound) < -1e-7:
        raise RuntimeError(f"constraint solution failed: {result.message}")
    return original + result.x @ basis


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--controls", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    round_path = ROOT / "output/facet_pairs/rounds/round1"
    state = torch.load(round_path / "model/head.pt", map_location="cpu", weights_only=True)
    fi = D.FACETS.index("temporal")
    original = state["net.weight"].numpy()[fi].astype(float)
    eta = float(state["tie_log"][fi])
    standard = np.load(round_path / "model/standardisation.npz")
    obs = D.observations(D.load_answer_rows(str(ROOT / "output/facet_pairs/answers")))
    parts = D.partition_observations([o for o in obs if o["facet"] == "temporal"])
    cachepath = ROOT / "output/facet_pairs/fullcache/Alibaba-NLP__gte-reranker-modernbert-base.npz"
    cache = np.load(cachepath, allow_pickle=False)
    lookup = {str(e): i for i, e in enumerate(cache["edge_id"])}
    needed = sorted({o[s] for o in parts["train"] + parts["heldout"]
                     for s in ("a_edge_id", "b_edge_id")})
    raw = cache["mean_L-3"]
    x = raw[[lookup[e] for e in needed]].astype(float)
    del raw
    x = (x - standard["mu"]) / standard["sd"]
    index = {e: i for i, e in enumerate(needed)}

    def differences(rows):
        return np.array([x[index[o["a_edge_id"]]] - x[index[o["b_edge_id"]]] for o in rows])

    pairs = {(o["a_edge_id"], o["b_edge_id"]): o for o in parts["train"]}
    design = differences(list(pairs.values()))
    _, s, vh = svd(design, full_matrices=True)
    rank = int((s > np.finfo(float).eps * max(design.shape) * s[0]).sum())
    basis = vh[rank:]
    control = np.load(args.controls, allow_pickle=False)
    tags = control["tags"].tolist()
    if len(tags) != 8:
        raise ValueError("this prereported protocol is specifically the eight-case rotation")
    c = (control["features"].astype(float) - standard["mu"]) / standard["sd"]
    c = c.reshape(8, 8, -1)
    contrasts = np.array([c[i, i] - c[i, (i+4) % 8] for i in range(8)])
    held = parts["heldout"]
    hx = differences(held)
    hy = np.array([D.OUTCOMES.index(o["outcome"]) for o in held])
    pair_count = Counter((o["a_edge_id"], o["b_edge_id"]) for o in held)
    mass = np.array([1/pair_count[o["a_edge_id"], o["b_edge_id"]] for o in held])
    mass /= mass.sum()

    def metrics(w):
        gap = hx @ w
        p = probabilities(gap, 1., eta)
        decided = hy < 2
        correct = ((gap > 0) & (hy == 0)) | ((gap < 0) & (hy == 1))
        return {"pair_balanced_nll": float(-(mass*np.log(p[np.arange(len(hy)), hy])).sum()),
                "pair_balanced_decided_agreement": float((mass[decided]*correct[decided]).sum()/mass[decided].sum())}

    out = {"protocol": __doc__, "created_utc": datetime.now(timezone.utc).isoformat(),
           "facet": "temporal", "tags": tags, "constraint_pairs": len(pairs),
           "design_rank": rank, "free_dimensions": len(basis),
           "original_control_gaps": (contrasts @ original).tolist(),
           "original_heldout": metrics(original), "sensitivity": []}
    for margin in (.25, 1., 2.):
        folds = []
        for fold in range(4):
            test = [fold, fold+4]
            train = [i for i in range(8) if i not in test]
            train_subjects = {j for i in train for j in (i, (i+4) % 8)}
            if train_subjects.intersection(test):
                raise AssertionError("held-out subject appears in fitting constraints")
            w = minimum_change(basis, contrasts[train], original, margin)
            preserved = float(np.max(np.abs(design @ (w-original))))
            if preserved > 1e-7:
                raise RuntimeError("old comparisons changed")
            folds.append({"train_cases": train, "test_cases": test,
                          "training_gaps": (contrasts[train] @ w).tolist(),
                          "test_gaps": (contrasts[test] @ w).tolist(),
                          "coefficient_change_norm": float(np.linalg.norm(w-original)),
                          "max_old_comparison_gap_change": preserved,
                          "old_heldout": metrics(w)})
        out["sensitivity"].append({"margin": margin, "folds": folds,
            "out_of_fold_correct": sum(g > 0 for f in folds for g in f["test_gaps"])})
    out["source_sha256"] = {}
    for p in [Path(__file__), args.controls, round_path / "model/head.pt",
              round_path / "model/standardisation.npz"]:
        with p.open("rb") as fp:
            out["source_sha256"][str(p)] = hashlib.file_digest(fp, "sha256").hexdigest()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps({"original": out["original_control_gaps"],
        "sensitivity": [{"margin": s["margin"], "correct": s["out_of_fold_correct"],
                         "folds": s["folds"]} for s in out["sensitivity"]]}, indent=2))


if __name__ == "__main__":
    main()

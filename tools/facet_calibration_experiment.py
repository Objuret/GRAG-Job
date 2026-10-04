"""Retrospective calibration experiment on existing facet labels, never retrieval gold.

Protocol fixed in this code: nonnegative slope plus tie logit; calibrate only on
validation pairs whose endpoints never appeared in head fitting; evaluate all
heldout labels with uniform pair mass. No method selected using heldout results.
The validation labels already selected the original head, so this is NOT a new
independent calibration collection or a prospective semantic validation.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "prod"), str(ROOT / "test")]
from graph.facet_pairs import data as D
from artefact.facet_measurement import probabilities, fit_calibration, reference_score_bounds

ROUND = ROOT / "output/facet_pairs/rounds/round1"


def chunks(obs):
    return {c for o in obs for c in (o["a_chunk_id"], o["b_chunk_id"])}


def pair_weights(obs):
    counts = Counter((o["a_edge_id"], o["b_edge_id"]) for o in obs)
    w = np.array([1/counts[(o["a_edge_id"], o["b_edge_id"])] for o in obs])
    return w/w.sum()


def metrics(gap, y, w, alpha, log_nu):
    p = probabilities(gap, alpha, log_nu)
    y = np.asarray(y)
    return {"n_judgements": len(y),
            "nll": float(-(w * np.log(np.maximum(p[np.arange(len(y)), y], 1e-300))).sum()),
            "brier": float((w * ((p-np.eye(3)[y])**2).sum(axis=1)).sum()),
            "observed_tie": float((w*(y==2)).sum()),
            "predicted_tie": float((w*p[:, 2]).sum())}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    started = time.perf_counter()
    rows = D.load_answer_rows(str(ROOT / "output/facet_pairs/answers"))
    obs = D.observations(rows)
    partition = D.partition_observations(obs)
    tv = D.training_val_split(partition["train"])
    seen = chunks(tv["fit"])
    cal = [o for o in tv["val"] if not {o["a_chunk_id"], o["b_chunk_id"]} & seen]
    held = partition["heldout"]
    assert not chunks(held) & (seen | chunks(cal))
    score_rows = [json.loads(line) for line in (ROUND / "scores.jsonl").open(encoding="utf-8")]
    edge_ids = [r["edge_id"] for r in score_rows]
    scores = np.array([[r[f] for f in D.FACETS] for r in score_rows])
    index = {e: i for i, e in enumerate(edge_ids)}
    state = torch.load(ROUND / "model/head.pt", map_location="cpu", weights_only=True)
    old_eta = state["tie_log"].numpy().astype(float)
    out = {"created_utc": datetime.now(timezone.utc).isoformat(),
           "protocol": __doc__, "metric_weighting": "each distinct unordered edge pair has equal mass; all repeats retained within pair",
           "calibration_calls": len({o["row_id"] for o in cal}),
           "dropped_overlapping_validation_calls": len({o["row_id"] for o in tv["val"]}) - len({o["row_id"] for o in cal}),
           "heldout_calls": len({o["row_id"] for o in held}),
           "calibration_chunks": len(chunks(cal)), "heldout_chunks": len(chunks(held)),
           "fit_calibration_chunk_overlap": len(seen & chunks(cal)),
           "heldout_other_chunk_overlap": len(chunks(held) & (seen | chunks(cal))),
           "facets": {}}

    def arrays(oo, f):
        gap = np.array([scores[index[o["a_edge_id"]], f] - scores[index[o["b_edge_id"]], f] for o in oo])
        y = np.array([D.OUTCOMES.index(o["outcome"]) for o in oo])
        return gap, y, pair_weights(oo)

    # The reference population gives equal mass to each eligible chunk, then
    # equal mass to its attached tags. This is an explicit experimental policy.
    count = Counter(D.split_edge_id(e)[0] for e in edge_ids)
    ref_weights = np.array([1/(len(count)*count[D.split_edge_id(e)[0]]) for e in edge_ids])
    lower, upper = np.empty_like(scores), np.empty_like(scores)
    for f, facet in enumerate(D.FACETS):
        fit_rows = [o for o in cal if o["facet"] == facet]
        gap, y, w = arrays(fit_rows, f)
        params = fit_calibration(gap, y, w)
        item = {"calibration": params, "evaluation": {}}
        for label in ["all"] + sorted({o["pair_type"] for o in held}):
            oo = [o for o in held if o["facet"] == facet and (label == "all" or o["pair_type"] == label)]
            gap, y, w = arrays(oo, f)
            item["evaluation"][label] = {
                "raw": metrics(gap, y, w, 1, old_eta[f]),
                "calibrated": metrics(gap, y, w, params["alpha"], params["log_nu"]),
                "n_pairs": len({(o["a_edge_id"], o["b_edge_id"]) for o in oo})}
        lower[:, f], upper[:, f] = reference_score_bounds(
            scores[:, f], scores[:, f], ref_weights,
            alpha=params["alpha"], log_nu=params["log_nu"], bins=1024)
        item["reference_score"] = {"min_lower": float(lower[:, f].min()),
            "max_upper": float(upper[:, f].max()),
            "max_numerical_interval_width": float((upper[:, f]-lower[:, f]).max())}
        out["facets"][facet] = item
        raw, fixed = item["evaluation"]["all"]["raw"], item["evaluation"]["all"]["calibrated"]
        print(f"{facet}: NLL {raw['nll']:.4f} -> {fixed['nll']:.4f}; alpha {params['alpha']:.4f}", flush=True)
    out["reference_population"] = {"policy": "uniform eligible chunk, uniform tag within chunk; versioned fixed corpus",
        "chunks": len(count), "edges": len(edge_ids), "quadrature_bins": 1024,
        "numerical_width_bound": 1/1024, "not_a_confidence_interval": True,
        "topic_column": "the head's learned topic, NOT the retrieval arm's topic cosine"}
    paths = [Path(__file__), ROOT / "test/artefact/facet_measurement.py",
             ROUND / "scores.jsonl", ROUND / "model/head.pt"]
    out["source_sha256"] = {}
    for p in paths:
        with p.open("rb") as fp:
            out["source_sha256"][str(p.relative_to(ROOT))] = hashlib.file_digest(fp, "sha256").hexdigest()
    label_digest = hashlib.sha256()
    for o in sorted(obs, key=lambda r: (r["row_id"], r["facet"])):
        label_digest.update(json.dumps(o, sort_keys=True).encode())
    out["observation_sha256"] = label_digest.hexdigest()
    out["seconds"] = round(time.perf_counter()-started, 2)
    args.out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.out / "reference_scores.npz", edge_ids=np.array(edge_ids),
                        facets=np.array(D.FACETS), lower=lower, upper=upper)
    (args.out / "calibration.json").write_text(json.dumps(out, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(f"Saved {args.out}", flush=True)


if __name__ == "__main__":
    main()

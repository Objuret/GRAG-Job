"""Analyze the prereported synthetic query-conditioned trade-off screen.

No serving scores or configuration are changed. Topic in the frozen-head source
is the learned topic readout, NOT the retrieval arm's cosine. Exact inference and
fixed-reference mappings are cached. Numerical readings are not calibrated human
truth. Four folds transfer between subjects, not broad corpus distributions.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import sys

import numpy as np
import torch
from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "prod"), str(ROOT / "test")]
from artefact.facet_measurement import reference_score_bounds
from artefact.facet_tradeoff import crossfit_nonnegative

FACETS = ("topic", "temporal", "why", "activity", "concreteness")
PENALTIES = (.001, .01, .1, 1.)


def sha(p):
    with p.open("rb") as fp:
        return hashlib.file_digest(fp, "sha256").hexdigest()


def frozen_scores(manifest, out):
    cache = out / "frozen_scores.json"
    round_path = ROOT / "output/facet_pairs/rounds/round1"
    calibration_path = out.parent / "calibration/calibration.json"
    paths = [out / "manifest.json", round_path / "model/head.pt",
             round_path / "model/standardisation.npz", round_path / "model/config.json",
             round_path / "scores.jsonl", calibration_path]
    signatures = {str(p.resolve()): sha(p) for p in paths}
    if cache.exists():
        saved = json.loads(cache.read_text())
        saved_signatures = {str(Path(p).resolve()): value for p,value in saved["source_sha256"].items()}
        if saved_signatures != signatures:
            raise ValueError("frozen scores cache input mismatch")
        return saved
    config = json.loads((round_path / "model/config.json").read_text())
    name, revision = config["backbone"], config["cache_meta"]["revision"]
    rows = [json.loads(line) for line in (round_path / "scores.jsonl").open(encoding="utf-8")]
    keys, features = [], []
    if all("source_edges" in d for d in manifest["cases"]["domains"]):
        lookup = {r["edge_id"]:r for r in rows}
        raw = []
        for domain in manifest["cases"]["domains"]:
            if len(domain["source_edges"]) != len(domain["texts"]):
                raise ValueError("unaligned corpus text and source edges")
            for i, edge_id in enumerate(domain["source_edges"]):
                keys.append(f"{domain['id']}_{i}")
                raw.append([lookup[edge_id][f] for f in FACETS])
        raw = np.array(raw)
    else:
        torch.set_num_threads(4)
        cfg = AutoConfig.from_pretrained(name, revision=revision, local_files_only=True, trust_remote_code=False)
        cfg.reference_compile = False
        cfg.output_hidden_states = True
        model = AutoModelForSequenceClassification.from_pretrained(name, revision=revision,
            config=cfg, local_files_only=True, trust_remote_code=False, attn_implementation="sdpa").float().eval()
        tok = AutoTokenizer.from_pretrained(name, revision=revision, local_files_only=True)
        for domain in manifest["cases"]["domains"]:
            for i, passage in enumerate(domain["texts"]):
                enc = tok(domain["tag"], passage, return_tensors="pt", truncation="only_second", max_length=1694)
                with torch.no_grad():
                    h = model(**enc).hidden_states[-3]
                mask = enc["attention_mask"].unsqueeze(-1).to(h.dtype)
                v = ((h*mask).sum(1)/mask.sum(1))[0].numpy().astype(np.float16).astype(np.float32)
                features.append(v)
                keys.append(f"{domain['id']}_{i}")
        standard = np.load(round_path / "model/standardisation.npz")
        state = torch.load(round_path / "model/head.pt", map_location="cpu", weights_only=True)
        raw = (np.array(features)-standard["mu"])/standard["sd"] @ state["net.weight"].numpy().T + state["net.bias"].numpy()
    count = Counter(r["edge_id"].split("::", 1)[0] for r in rows)
    weights = np.array([1/(len(count)*count[r["edge_id"].split("::", 1)[0]]) for r in rows])
    calibration = json.loads(calibration_path.read_text())
    lower, upper = np.empty_like(raw), np.empty_like(raw)
    for fi, facet in enumerate(FACETS):
        c = calibration["facets"][facet]["calibration"]
        lower[:, fi], upper[:, fi] = reference_score_bounds(raw[:, fi], [r[facet] for r in rows], weights,
            alpha=c["alpha"], log_nu=c["log_nu"], bins=1024)
    result = {"source_sha256": signatures, "keys": keys, "raw": raw.tolist(),
              "lower": lower.tolist(), "upper": upper.tolist(),
              "values": ((lower+upper)/2).tolist(),
              "numerical_bounds_are_not_confidence_intervals": True}
    cache.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    return result


def metrics(p, y, gap, mass):
    mass = mass/mass.sum()
    decided = y < 2
    ok = ((gap > 1e-12)&(y == 0)) | ((gap < -1e-12)&(y == 1))
    resolved = decided & (np.abs(gap) > 1e-12)
    return {"n": len(y), "decided": int(decided.sum()),
        "log_loss": float(-(mass*np.log(np.maximum(p[np.arange(len(y)), y], 1e-300))).sum()),
        "brier": float((mass*((p-np.eye(3)[y])**2).sum(axis=1)).sum()),
        "decided_direction_agreement": float((mass[decided]*ok[decided]).sum()/mass[decided].sum()) if decided.any() else None,
        "decided_direction_coverage": float(mass[resolved].sum()/mass[decided].sum()) if decided.any() else None,
        "agreement_when_direction_resolved": float((mass[resolved]*ok[resolved]).sum()/mass[resolved].sum()) if resolved.any() else None,
        "three_way_accuracy": float((mass*(p.argmax(axis=1) == y)).sum())}


def lex_direction(q, difference):
    q, difference = np.asarray(q, dtype=float), np.asarray(difference, dtype=float)
    if q.ndim != 1 or difference.shape != q.shape or not np.isfinite(q).all() or not np.isfinite(difference).all() or (q < 0).any():
        raise ValueError('Finite aligned differences and nonnegative query relevance required')
    active = tuple(np.flatnonzero(q > 0))
    # Equal query scores do not justify an arbitrary priority. Keep all orders
    # consistent with those scores; resolve only if they imply the same result.
    # A zero query relevance cannot become a last-resort sorting key.
    possible = set()
    for order in itertools.permutations(active):
        if any(q[order[i]] < q[order[i+1]] for i in range(len(order)-1)):
            continue
        sign = next((int(np.sign(difference[i])) for i in order if abs(difference[i]) > 1e-12), 0)
        possible.add(sign)
    return next(iter(possible)) if len(possible) == 1 else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    out = args.out
    manifest = json.loads((out / "manifest.json").read_text())
    # Build/reuse frozen graph measurements before opening new preference responses.
    frozen = frozen_scores(manifest, out)
    readings = {j["id"]: json.loads((out/(j["id"]+".json")).read_text()) for j in manifest["jobs"]}
    for j in manifest["jobs"]:
        for key in ("user", "system"):
            if readings[j["id"]][key+"_sha256"] != hashlib.sha256(j[key].encode()).hexdigest():
                raise RuntimeError("response prompt signature differs")
    values = {}
    repeat_differences = {}
    numeric_counts = {}
    for role in ("query", "graph"):
        a, b = readings[role+"_0"]["answer"], readings[role+"_1"]["answer"]
        expected = set(next(j["case_ids"] for j in manifest["jobs"] if j["id"] == role+"_0"))
        if set(a) | set(b) != expected:
            raise RuntimeError("no numeric reading for at least one required relationship")
        values[role] = {k: np.array([np.mean([v[k][f] for v in (a,b) if k in v]) for f in FACETS]) for k in expected}
        numeric_counts[role] = {k: int(k in a)+int(k in b) for k in expected}
        repeat_differences[role] = {f: float(np.mean([abs(a[k][f]-b[k][f]) for k in set(a)&set(b)])) for f in FACETS}
    cases = []
    for j in manifest["jobs"]:
        if j["role"] != "preference":
            continue
        for cid, label in readings[j["id"]]["answer"].items():
            domain, qi, a, b = cid.split('_')
            a, b = int(a), int(b)
            orientation = j["orientation_not_sent"][cid]
            winner = None if label == "equal" else orientation[0 if label == "A" else 1]
            y = 2 if winner is None else 0 if winner == a else 1
            cases.append({"id": cid, "domain": domain, "qi": int(qi), "a": a, "b": b,
                          "repeat": j["repeat"], "y": y})
    y = np.array([c["y"] for c in cases])
    groups = np.array([c["domain"] for c in cases])
    domains = sorted(set(groups))
    by_id = {cid: [c["y"] for c in cases if c["id"] == cid] for cid in {c["id"] for c in cases}}
    mass = np.array([1/len(by_id[c["id"]]) for c in cases])
    repeated = [v for v in by_id.values() if len(v) == 2]
    result = {"created_utc": datetime.now(timezone.utc).isoformat(), "protocol": manifest["analysis_prespecified"],
        "facet_order": list(FACETS), "observations": len(cases), "distinct_comparisons": len(by_id),
        "orientation_consistency": sum(len(set(v)) == 1 for v in repeated)/len(repeated),
        "repeated_comparisons": len(repeated),
        "missing_readings": {k:r.get("missing_cases",[]) for k,r in readings.items() if r.get("missing_cases")},
        "protocol_deviation": manifest.get("collection_deviations", "No deviation statement in manifest; inspect missing_readings and retained raw responses. Historical synthetic retries are documented in TRADEOFF.md, not assumed for other experiments."),
        "outcomes": dict(Counter(int(v) for v in y)), "numeric_repeat_mean_abs_difference": repeat_differences,
        "numeric_reading_counts": numeric_counts,
        "query_values": {k:v.tolist() for k,v in values["query"].items()}, "sources": {}}
    sources = [("direct", values["graph"]), ("frozen_reference", dict(zip(frozen["keys"], np.array(frozen["values"]))))]
    if (out / "live_topic.json").exists():
        live = json.loads((out / "live_topic.json").read_text())
        for source, edge in list(sources):
            adjusted = {k: np.r_[live["values"][k],v[1:]] for k,v in edge.items()}
            sources.append((source+"_actual_topic_exploratory",adjusted))
    for source, edge in sources:
        q = np.array([values["query"][f"{c['domain']}_{c['qi']}"] for c in cases])
        delta = np.array([edge[f"{c['domain']}_{c['a']}"]-edge[f"{c['domain']}_{c['b']}"] for c in cases])
        features = {"topic_only": delta[:, :1], "static_facets": delta,
                    "equal_products": (q*delta).sum(axis=1, keepdims=True), "fitted_products": q*delta}
        block = {}
        for method, x in features.items():
            fitted = crossfit_nonnegative(x,y,groups,penalties=PENALTIES,sample_weight=mass)
            p, gap, folds = fitted["probabilities"], fitted["gap"], fitted["folds"]
            for fold in folds:
                test = groups == fold["excluded_domain"]
                fold["test_metrics"] = metrics(p[test], y[test], gap[test], mass[test])
            # A control reversal is read only when both repeated labels agree and
            # two sought-content descriptions prefer opposite members of the pair.
            reversals = []
            canonical_index = {c["id"]: i for i, c in enumerate(cases)}
            for domain in domains:
                description = next(d for d in manifest["cases"]["domains"] if d["id"] == domain)
                for a,b in itertools.combinations(range(len(description["texts"])),2):
                    for qa,qb in itertools.combinations(range(len(description["descriptions"])),2):
                        ca, cb = f"{domain}_{qa}_{a}_{b}", f"{domain}_{qb}_{a}_{b}"
                        ya, yb = by_id[ca], by_id[cb]
                        if len(ya) == len(yb) == 2 and len(set(ya)) == len(set(yb)) == 1 and {ya[0], yb[0]} == {0,1}:
                            ga, gb = gap[canonical_index[ca]], gap[canonical_index[cb]]
                            ok = ((ga > 1e-12) == (ya[0] == 0)) and ((gb > 1e-12) == (yb[0] == 0)) and abs(ga)>1e-12 and abs(gb)>1e-12
                            reversals.append(bool(ok))
            block[method] = {"metrics": metrics(p,y,gap,mass), "folds": folds,
                "reader_supported_reversals": len(reversals), "reversals_reproduced": sum(reversals),
                "predictions": [{**c, "gap": float(gap[i]), "probabilities": p[i].tolist()} for i,c in enumerate(cases)]}
        lex = np.array([lex_direction(qq, dd) for qq,dd in zip(q,delta)])
        decided = y < 2
        correct = ((lex == 1)&(y == 0)) | ((lex == -1)&(y == 1))
        block["query_ordered_lexicographic"] = {"unresolved": int((lex == 0).sum()),
            "decided_direction_agreement": float((mass[decided]*correct[decided]).sum()/mass[decided].sum()),
            "note": "ties in query scores retain every compatible priority; disagreement between priorities is unresolved, counted incorrect for decided labels"}
        result["sources"][source] = block
    result["source_sha256"] = {str(p): sha(p) for p in [Path(__file__), ROOT / "test/artefact/facet_tradeoff.py", out / "manifest.json", out / "frozen_scores.json"]}
    if (out / "live_topic.json").exists():
        result["source_sha256"][str(out / "live_topic.json")] = sha(out / "live_topic.json")
    (out / "analysis.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"orientation_consistency":result["orientation_consistency"],"outcomes":result["outcomes"],
        "sources":{s:{m:{k:v for k,v in r.items() if k not in ("predictions","folds")} for m,r in b.items()} for s,b in result["sources"].items()}},indent=2))


if __name__ == "__main__":
    # Tiny convex fits suffer from large BLAS thread-pool overhead. This changes
    # execution resources only, not features, folds, loss or model selection.
    from threadpoolctl import threadpool_limits
    with threadpool_limits(limits=1):
        main()

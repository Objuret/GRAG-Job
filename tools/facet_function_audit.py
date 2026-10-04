"""Read-only facet diagnostics: live Volmax, shipped head, and actual sorting code.

No benchmark questions/gold, model calls, training, or database writes. Only --out
is written. Probability scores measure prediction of the recorded facet judge,
not semantic truth or retrieval utility. Run from any directory with repo Python.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "prod"), str(ROOT / "test")]
FACETS = ("topic", "temporal", "why", "activity", "concreteness")
ROUND = ROOT / "output/facet_pairs/rounds/round1"


def davidson_probabilities(gap, log_nu):
    """Three outcome probabilities; gap is a score DIFFERENCE, not relevance."""
    gap, log_nu = np.broadcast_arrays(np.asarray(gap, dtype=float), np.asarray(log_nu, dtype=float))
    z = np.stack([gap / 2, -gap / 2, log_nu], axis=-1)
    p = np.exp(z - z.max(axis=-1, keepdims=True))
    return p / p.sum(axis=-1, keepdims=True)


def sha(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def sorter_probes():
    # Pin the diagnostic configuration; don't inherit a user's experimental flags.
    for key in list(os.environ):
        if key.startswith("HERB_V3_"):
            del os.environ[key]
    os.environ.update(NEO4J_DATABASE="herb-eval-volmax", HERB_FACET_SOURCE="file",
                      HERB_FACET_FILE=str(ROUND / "overlay.json"),
                      HERB_V3_SORT="weighted")
    a = importlib.import_module("arms.artefact_v3")

    def run(topic, four, weights, mode="weighted"):
        topic, four = np.asarray(topic), np.asarray(four)
        cols, names, _ = a.mode_key_columns(
            mode, topic, four, FACETS, FACETS, topic_band=.028,
            facet_band=1., weights=dict(zip(FACETS[1:], weights)))
        ids = list("ABC")[:len(topic)]
        zeros = np.zeros(len(topic), dtype=int)
        keys, _ = a.pool_key_tuples(0, cols, names, zeros, zeros, zeros, ids)
        result = {"order": sorted(ids, key=lambda x: keys[ids.index(x)]),
                  "keys": {x: list(map(int, keys[i][:-1])) for i, x in enumerate(ids)}}
        if mode == "weighted":
            g, _, _ = a.weighted_g(four, np.asarray(weights), np.ones(4))
            result["adjusted_topic"] = a.bounded_r(topic, g, .028).tolist()
        return result

    topic, four = [.51, .50], [[0., 0, 0, 0], [1., 0, 0, 0]]
    weighted = {"base": run(topic, four, [1, 0, 0, 0]),
                "dominated_candidate_added": run(topic + [0.], four + [[-100., 0, 0, 0]], [1, 0, 0, 0]),
                "weights_times_1e_minus_9": run(topic, four, [1e-9, 0, 0, 0]),
                "zero_weights": run(topic, four, [0, 0, 0, 0])}
    multi = {"base": run([.51, .509], [[0, 0, 0, 0], [2, 0, 0, 0]], [1]*4, "multirank"),
             "new_max_added": run([.51, .509, .5375],
                                  [[0, 0, 0, 0], [2, 0, 0, 0], [-20, 0, 0, 0]],
                                  [1]*4, "multirank")}
    return {"weighted": weighted, "multirank": multi}


def live_database():
    from graph.db import _driver
    queries = {
        "labels": "MATCH (n) UNWIND labels(n) AS label RETURN label,count(*) AS n ORDER BY label",
        "relations": "MATCH (a)-[r]->(b) RETURN labels(a) AS src,type(r) AS rel,labels(b) AS dst,count(*) AS n ORDER BY rel",
        "facet_layouts": "MATCH ()-[r:HAS_TAG]->() RETURN r.run_id AS run,r.facets AS facets,size(r.w_facets) AS width,count(*) AS n",
        "embedding_dimensions": "MATCH (n) WHERE n:Tag OR n:Chunk RETURN labels(n) AS label,size(coalesce(n.emb,n.desc_emb)) AS dimension,count(*) AS n",
        "chunk_text_properties": "MATCH (c:Chunk) RETURN count(c) AS n,count(c.description) AS description,count(c.content) AS content,count(c.desc_emb) AS description_vectors",
        "excluded_chunks": "MATCH (c:Chunk) WHERE NOT EXISTS {(c)-[:product]->(:Product)} RETURN count(c) AS n",
        "edge_rows": "MATCH (c:Chunk)-[r:HAS_TAG]->(t:Tag) RETURN c.chunk_id AS chunk,t.name AS tag,r.w_facets AS weights,EXISTS {(c)-[:product]->(:Product)} AS eligible",
    }
    out = {}
    with _driver() as driver:
        with driver.session(database="herb-eval-volmax", default_access_mode="READ") as session:
            for name, query in queries.items():
                out[name] = session.execute_read(lambda tx, q=query: tx.run(q).data())
    edges = out.pop("edge_rows")
    weights = np.asarray([r["weights"] for r in edges], dtype=float)
    eligible = {(r["chunk"], r["tag"]) for r in edges if r["eligible"]}
    overlay = json.loads((ROUND / "overlay.json").read_text(encoding="utf-8"))
    oe = overlay["edges"]
    overlay_keys = {(r["chunkId"], r["tag"]) for r in oe}
    out["edge_values"] = {"rows": len(edges), "eligible_unique": len(eligible),
                          "eligible_rows": sum(r["eligible"] for r in edges),
                          "finite": bool(np.isfinite(weights).all()),
                          "min_per_column": weights.min(axis=0).tolist(),
                          "max_per_column": weights.max(axis=0).tolist(),
                          "unique_per_column": [len(np.unique(weights[:, i])) for i in range(5)]}
    out["overlay_alignment"] = {"database": overlay.get("database"),
        "run_id": overlay.get("run_id"), "facets": overlay["facets"], "rows": len(oe),
        "duplicates": len(oe) - len(overlay_keys), "missing_live_edges": len(eligible - overlay_keys),
        "extra_edges": len(overlay_keys - eligible),
        "null_per_column": [sum(r["weights"][i] is None for r in oe) for i in range(5)]}
    return out


def component_sizes(obs):
    parent = {}
    def find(x):
        parent.setdefault(x, x)
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]
    for o in obs:
        a, b = find(o["a_edge_id"]), find(o["b_edge_id"])
        if a != b:
            parent[a] = b
    return sorted(Counter(find(x) for x in list(parent)).values(), reverse=True)


def judge_diagnostics():
    import torch
    from graph.facet_pairs import data as d
    rows = d.load_answer_rows(str(ROOT / "output/facet_pairs/answers"))
    obs = d.observations(rows)
    part = d.partition_observations(obs)
    tv = d.training_val_split(part["train"])
    splits = {"fit": tv["fit"], "validation": tv["val"], "heldout": part["heldout"]}
    fit_chunks = {c for o in splits["fit"] for c in (o["a_chunk_id"], o["b_chunk_id"])}
    state = torch.load(ROUND / "model/head.pt", map_location="cpu", weights_only=True)
    # Stored head is a state_dict, verified by exact parameter lookup rather than guessed.
    log_nu = state["tie_log"].numpy().astype(float)
    scores = {}
    for line in (ROUND / "scores.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        scores[r["edge_id"]] = [r[f] for f in FACETS]

    # Remove tag or chunk specificity while preserving the shipped score scale.
    # These are counterfactual score ablations, not additional trained models.
    means = {}
    for side in ("chunk", "tag"):
        sums, counts = {}, Counter()
        for eid, value in scores.items():
            chunk, tag = d.split_edge_id(eid)
            key = chunk if side == "chunk" else tag
            sums.setdefault(key, np.zeros(len(FACETS)))
            sums[key] += value
            counts[key] += 1
        means[side] = {k: v / counts[k] for k, v in sums.items()}

    def vector(eid, ablation):
        if ablation == "full":
            return scores[eid]
        chunk, tag = d.split_edge_id(eid)
        return means[ablation][chunk if ablation == "chunk" else tag]

    def predict(o, ablation="full"):
        f = FACETS.index(o["facet"])
        gap = vector(o["a_edge_id"], ablation)[f] - vector(o["b_edge_id"], ablation)[f]
        return davidson_probabilities(gap, log_nu[f])

    # Fit-only empirical class rates: a simple proper-score reference, not tuned on heldout.
    refs = {}
    for f in FACETS:
        counts = Counter(o["outcome"] for o in splits["fit"] if o["facet"] == f)
        refs[f] = np.array([counts[k] + 1 for k in d.OUTCOMES], dtype=float)
        refs[f] /= refs[f].sum()  # Laplace smoothing explicitly stated.
    out = {"tie_nu": dict(zip(FACETS, np.exp(log_nu).tolist())),
           "teacher_prompt_sha256_counts": dict(Counter(r.get("prompt_sha256") for r in rows)),
           "metric_unit": "recorded judgement, including repeats; no independent-sample confidence claim",
           "splits": {}}
    for name, oo in splits.items():
        sizes = component_sizes(oo)
        distinct_rows = {o["row_id"]: o for o in oo}
        chunks = {c for o in oo for c in (o["a_chunk_id"], o["b_chunk_id"])}
        block = {"observations": len(oo), "judged_rows": len({o["row_id"] for o in oo}),
                 "unique_chunks": len(chunks), "chunks_also_in_fit": len(chunks & fit_chunks),
                 "rows_by_unseen_endpoint_count": dict(Counter(
                     int(o["a_chunk_id"] not in fit_chunks) + int(o["b_chunk_id"] not in fit_chunks)
                     for o in distinct_rows.values())),
                 "unique_edge_pairs": len({(o["a_edge_id"], o["b_edge_id"]) for o in oo}),
                 "comparison_components": len(sizes), "largest_component_edges": max(sizes, default=0),
                 "compared_edges": sum(sizes), "by_facet": {}}
        for f in FACETS:
            fo = [o for o in oo if o["facet"] == f]
            if not fo:
                continue
            p = np.stack([predict(o) for o in fo])
            y = np.array([d.OUTCOMES.index(o["outcome"]) for o in fo])
            target = np.eye(3)[y]
            correct = p.argmax(axis=1) == y
            conf = p.max(axis=1)
            reliability = []
            for lo, hi in zip(np.arange(0, 1, .1), np.arange(.1, 1.01, .1)):
                sel = (conf >= lo) & (conf < hi if hi < .999 else conf <= 1)
                if sel.any():
                    reliability.append({"lo": round(float(lo), 1), "n": int(sel.sum()),
                        "confidence": float(conf[sel].mean()), "accuracy": float(correct[sel].mean())})
            block["by_facet"][f] = {"n": len(fo), "accuracy_three_way": float(correct.mean()),
                "nll": float(-np.log(np.maximum(p[np.arange(len(y)), y], 1e-300)).mean()),
                "brier_sum_three_classes": float(((p - target)**2).sum(axis=1).mean()),
                "fit_prior_nll": float(-np.log(refs[f][y]).mean()),
                "fit_prior_brier": float(((refs[f] - target)**2).sum(axis=1).mean()),
                "observed_tie_rate": float((y == 2).mean()), "predicted_tie_rate": float(p[:, 2].mean()),
                "reliability_descriptive_only": reliability}
        out["splits"][name] = block
    ablations = {}
    for pair_type in sorted({o["pair_type"] for o in splits["heldout"]}):
        ablations[pair_type] = {}
        for f in FACETS:
            oo = [o for o in splits["heldout"] if o["facet"] == f and o["pair_type"] == pair_type]
            if not oo:
                continue
            y = np.array([d.OUTCOMES.index(o["outcome"]) for o in oo])
            block = {}
            for ablation in ("full", "chunk", "tag"):
                p = np.stack([predict(o, ablation) for o in oo])
                decided = y < 2
                # A zero gap is not a correct direction on a decided observation.
                sign_ok = ((p[:, 0] > p[:, 1]) & (y == 0)) | ((p[:, 1] > p[:, 0]) & (y == 1))
                block[ablation] = {"n": len(oo), "n_decided": int(decided.sum()),
                    "decided_agreement": float(sign_ok[decided].mean()) if decided.any() else None,
                    "nll": float(-np.log(np.maximum(p[np.arange(len(y)), y], 1e-300)).mean())}
            ablations[pair_type][f] = block
    out["heldout_score_ablations_by_pair_type"] = ablations
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    sources = [Path(__file__), ROOT / "test/arms/artefact_v3.py",
               ROOT / "test/graph/facet_pairs/cache_probe.py", ROUND / "overlay.json",
               ROUND / "scores.jsonl", ROUND / "model/head.pt"]
    out = {"created_utc": datetime.now(timezone.utc).isoformat(),
           "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in sources},
           "sorter_probes": sorter_probes()}
    print("Sort probes complete; reading live Volmax", flush=True)
    out["live_database"] = live_database()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("Live database read complete; scoring recorded facet judgements", flush=True)
    out["judge_diagnostics"] = judge_diagnostics()
    args.out.write_text(json.dumps(out, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Written {args.out}", flush=True)


if __name__ == "__main__":
    main()

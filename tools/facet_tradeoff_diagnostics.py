"""Post-hoc representational checks; not another selected retrieval method.

Uses all consistent, twice-read decisive preferences to ask whether ANY common
nonnegative product coefficients can express them. This is an optimistic
feasibility diagnosis, not held-out evaluation or a proposal to fit on test labels.
Also checks label-order cycles and the effect of making topic equal across these
deliberately same-topic alternatives. None of these results promotes a model.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import itertools

import numpy as np
from scipy.optimize import linprog

sys.path.insert(0, str(Path(__file__).resolve().parent))
from facet_tradeoff_experiment import FACETS, lex_direction


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    p = args.out
    analysis = json.loads((p / "analysis.json").read_text())
    cases = analysis["sources"]["direct"]["fitted_products"]["predictions"]
    repeated = {cid: [r for r in cases if r["id"] == cid] for cid in {r["id"] for r in cases}}
    consistent = [v[0] for v in repeated.values() if len(v) == 2 and v[0]["y"] == v[1]["y"] and v[0]["y"] < 2]
    qvalues = {k: np.array(v) for k,v in analysis["query_values"].items()}
    a = json.loads((p/'graph_0.json').read_text())["answer"]
    b = json.loads((p/'graph_1.json').read_text())["answer"]
    direct = {k: np.array([np.mean([v[k][f] for v in (a,b) if k in v]) for f in FACETS]) for k in set(a)|set(b)}
    frozen = json.loads((p/'frozen_scores.json').read_text())
    edge_sources = {"direct": direct, "frozen_reference": dict(zip(frozen["keys"], np.array(frozen["values"])))}
    query_groups = sorted({(c["domain"], c["qi"]) for c in consistent})
    cyclic = []
    for group in query_groups:
        cc = [c for c in consistent if (c["domain"], c["qi"]) == group]
        has_order = False
        for order in itertools.permutations(range(4)):
            position = {item:i for i,item in enumerate(order)}
            if all((position[c["a"]] < position[c["b"]]) == (c["y"] == 0) for c in cc):
                has_order = True
                break
        if not has_order:
            cyclic.append(group)
    result = {"protocol": __doc__, "consistent_decisive_pairs": len(consistent),
              "queries_with_strict_preference_cycles": cyclic, "sources": {}}
    for source, edge in edge_sources.items():
        X = []
        dominated = []
        for c in consistent:
            q = qvalues[f"{c['domain']}_{c['qi']}"]
            delta = edge[f"{c['domain']}_{c['a']}"]-edge[f"{c['domain']}_{c['b']}"]
            signed = q*delta*(1 if c["y"] == 0 else -1)
            X.append(signed)
            if (signed <= 0).all():
                dominated.append(c["id"])
        X = np.array(X)
        lp = linprog(np.zeros(X.shape[1]), A_ub=-X, b_ub=-np.ones(len(X)), bounds=(0,None), method="highs")
        # Margin 1 fixes an arbitrary scale for a homogeneous strict feasibility
        # question. Any finite strictly positive margins can be scaled to it.
        if lp.status not in (0,2):
            raise RuntimeError(f"feasibility solver inconclusive: {lp.message}")
        oracle = []
        for c in cases:
            q = qvalues[f"{c['domain']}_{c['qi']}"]
            delta = edge[f"{c['domain']}_{c['a']}"]-edge[f"{c['domain']}_{c['b']}"]
            delta[0] = 0.
            sign = lex_direction(q,delta)
            oracle.append(sign)
        weights = np.array([1/len(repeated[c["id"]]) for c in cases])
        y = np.array([c["y"] for c in cases])
        oracle = np.array(oracle)
        decided = y < 2
        ok = ((oracle == 1)&(y == 0)) | ((oracle == -1)&(y == 1))
        result["sources"][source] = {"common_nonnegative_product_weights_feasible": bool(lp.success),
            "solver_message": lp.message, "preferred_alternative_weakly_dominated_in_all_product_features": dominated,
            "oracle_equal_topic_lexicographic_agreement": float((weights[decided]*ok[decided]).sum()/weights[decided].sum()),
            "oracle_equal_topic_unresolved": int((oracle == 0).sum())}
    (p/'diagnostics.json').write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))


if __name__ == "__main__":
    main()

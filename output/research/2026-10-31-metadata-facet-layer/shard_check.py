"""Does the full pass's encoder, run again today, give back what it stored on 2026-09-19?

One shard of the full pass (its own edge file, texts, extractor, python and graphics card) was
encoded again. This compares the new vectors with the stored ones array by array, and then the
four facet means the kept refits give each edge from either set of vectors.

    python shard_check.py --stored <shard npz> --again <shard npz> --refits <metadata_pool dir>
        --config <round1 model/config.json> --code <test/graph/facet_pairs> --out <json>
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

FACETS = ("topic", "temporal", "why", "activity", "concreteness")
NON_TOPIC = ("temporal", "why", "activity", "concreteness")


def facet_means(vectors, refits_dir, config, code):
    """Each edge's mean over the kept refits of the four facet scores."""
    import torch
    sys.path.insert(0, code)
    import cache_probe as P
    with np.load(Path(refits_dir) / "refits" / "standardisation.npz") as z:
        seeds, mus, sds = [int(s) for s in z["seeds"]], z["mu"], z["sd"]
    feats = vectors.astype(np.float32)
    cols = [FACETS.index(f) for f in NON_TOPIC]
    total = np.zeros((feats.shape[0], len(NON_TOPIC)), dtype=np.float64)
    for b, seed in enumerate(seeds):
        head = P.Head(feats.shape[1], config["head"], int(config.get("hidden", 128)))
        head.load_state_dict(torch.load(Path(refits_dir) / "refits" / f"head_b{b:02d}_seed{seed}.pt",
                                        weights_only=True))
        head.eval()
        X = torch.from_numpy(((feats - mus[b]) / sds[b]).astype(np.float32))
        with torch.no_grad():
            total += head(X).numpy()[:, cols].astype(np.float64)
    return total / len(seeds)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stored", required=True)
    ap.add_argument("--again", required=True)
    ap.add_argument("--refits", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--code", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    s, g = np.load(a.stored), np.load(a.again)
    out = {"stored": a.stored, "again": a.again,
           "edges": int(len(s["edge_id"])),
           "same_edges_in_the_same_order": bool(np.array_equal(s["edge_id"], g["edge_id"])),
           "n_tokens_equal": bool(np.array_equal(s["n_tokens"], g["n_tokens"])),
           "truncated_equal": bool(np.array_equal(s["truncated"], g["truncated"])),
           "arrays": {}}
    for key in sorted(k for k in s.files if k.startswith(("cls_", "mean_")) or k == "native_logit"):
        x, y = s[key].astype(np.float32), g[key].astype(np.float32)
        out["arrays"][key] = {"values": int(x.size), "bit_equal": int((s[key] == g[key]).sum()),
                              "max_abs_difference": float(np.abs(x - y).max()),
                              "mean_abs_difference": float(np.abs(x - y).mean()),
                              "stored_abs_mean": float(np.abs(x).mean())}
    config = json.loads(Path(a.config).read_text(encoding="utf-8"))
    variant = config["variant"]
    ms = facet_means(s[variant], a.refits, config, a.code)
    mg = facet_means(g[variant], a.refits, config, a.code)
    d = np.abs(ms - mg)
    out["facet_means_over_the_kept_refits"] = {
        "variant": variant,
        "per_facet": {f: {"max_abs_difference": float(d[:, i].max()),
                          "mean_abs_difference": float(d[:, i].mean()),
                          "stored_sd": float(ms[:, i].std())}
                      for i, f in enumerate(NON_TOPIC)}}
    Path(a.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

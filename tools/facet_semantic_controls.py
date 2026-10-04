"""Local frozen-head controls, with explicit synthetic hypotheses, not gold labels.

Every text contains timing, a reason, an action and particulars. Compare its named
subject to an unrelated subject from another case. Hypothesis: the related subject
should score higher through each facet. This is a necessary-condition probe, not a
comprehensive interpretation of the user's semantics or a tuned benchmark.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import sys
import time

import numpy as np
import torch
from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "prod"), str(ROOT / "test")]
from graph.facet_pairs.data import FACETS, split_edge_id

ROUND = ROOT / "output/facet_pairs/rounds/round1"
CASES = [
    ("database failover", "On Tuesday at 09:00 the operations team switched the database to its standby server because the primary server had failed. The database failover took 40 seconds and restored access for 120 users."),
    ("battery replacement", "On Monday the maintenance team replaced eight batteries in the emergency lights because they no longer held a charge. Battery replacement finished at 14:00, before the building reopened."),
    ("orchard irrigation", "The farmers irrigated three apple-tree plots on Thursday because the soil had dried out. Orchard irrigation delivered 600 litres before noon, and the next watering was scheduled for Saturday."),
    ("museum ticket refunds", "On Friday the museum refunded 45 tickets because a water leak forced the exhibition to close. The museum ticket refunds totalled 900 euros and reached customers before Monday."),
    ("satellite antenna alignment", "At 18:00 the engineering team rotated the satellite antenna by two degrees because a pointing error was disrupting reception. Satellite antenna alignment restored the signal in twelve minutes."),
    ("bread delivery", "The bakery delivered 80 loaves to the school at 07:30 because the school kitchen's oven had broken. The bread delivery arrived before breakfast and replaced the cancelled baking run."),
    ("bridge inspection", "On Wednesday two engineers inspected the eastern bridge because a driver had reported a crack. The bridge inspection measured a 12-millimetre gap, and the engineers closed the bridge at 16:00."),
    ("payroll correction", "On the first of June the payroll team corrected six salary payments because an overtime calculation was wrong. The payroll correction added 450 euros in total, paid before the next working day."),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    start = time.perf_counter()
    config = json.loads((ROUND / "model/config.json").read_text())
    name, rev = config["backbone"], config["cache_meta"]["revision"]
    model_config = AutoConfig.from_pretrained(name, revision=rev, local_files_only=True,
                                             trust_remote_code=False)
    model_config.reference_compile = False
    model_config.output_hidden_states = True
    print("Loading pinned local backbone on CPU", flush=True)
    torch.set_num_threads(4)
    model = AutoModelForSequenceClassification.from_pretrained(
        name, revision=rev, config=model_config, local_files_only=True,
        attn_implementation="sdpa", trust_remote_code=False).float().eval()
    tok = AutoTokenizer.from_pretrained(name, revision=rev, local_files_only=True)
    state = torch.load(ROUND / "model/head.pt", map_location="cpu", weights_only=True)
    standard = np.load(ROUND / "model/standardisation.npz")
    weight, bias = state["net.weight"].numpy(), state["net.bias"].numpy()

    def encode(pairs):
        vectors = []
        for tag, text in pairs:
            enc = tok(tag, text, return_tensors="pt", truncation="only_second", max_length=1694)
            with torch.no_grad():
                h = model(**enc).hidden_states[-3]
            mask = enc["attention_mask"].unsqueeze(-1).to(h.dtype)
            v = ((h*mask).sum(1)/mask.sum(1).clamp(min=1e-6))[0]
            # Reproduce float16 feature storage followed by float32 head arithmetic.
            vectors.append(v.numpy().astype(np.float16).astype(np.float32))
        return np.stack(vectors)

    def head(features):
        x = (features-standard["mu"])/standard["sd"]
        return x @ weight.T + bias

    # Reproduce three cached corpus edges before interpreting synthetic predictions.
    texts = {}
    with (ROOT / "output/facet_neural/rows_export.jsonl").open(encoding="utf-8") as fp:
        for line in fp:
            r = json.loads(line)
            if r.get("chunk_id") and r.get("text"):
                texts[r["chunk_id"]] = r["text"]
    cached_scores = [json.loads(line) for line in (ROUND / "scores.jsonl").open(encoding="utf-8")]
    picked, seen = [], set()
    for r in cached_scores:
        chunk, tag = split_edge_id(r["edge_id"])
        if chunk in texts and chunk not in seen and len(texts[chunk]) < 1000:
            picked.append(r)
            seen.add(chunk)
        if len(picked) == 3:
            break
    if len(picked) != 3:
        raise RuntimeError("three reproduction samples unavailable")
    pairs = [(split_edge_id(r["edge_id"])[1], texts[split_edge_id(r["edge_id"])[0]]) for r in picked]
    reproduced = head(encode(pairs))
    original = np.array([[r[f] for f in FACETS] for r in picked])
    delta = np.abs(reproduced-original)
    reproduction = {"edge_ids": [r["edge_id"] for r in picked],
                    "max_abs_score_difference": float(delta.max()),
                    "per_facet_max_abs_difference": delta.max(axis=0).tolist(),
                    "original": original.tolist(), "reproduced": reproduced.tolist()}
    print(f"Corpus reproduction max score delta: {delta.max():.8f}", flush=True)
    pairs = [(tag, text) for _, text in CASES for tag, _ in CASES]
    features = encode(pairs)
    values = head(features).reshape(len(CASES), len(CASES), len(FACETS))
    results = []
    for i, (tag, text) in enumerate(CASES):
        other = (i+4) % len(CASES)
        diff = values[i, i]-values[i, other]
        results.append({"related_tag": tag, "unrelated_tag": CASES[other][0], "text": text,
                        "related": dict(zip(FACETS, values[i, i].tolist())),
                        "unrelated": dict(zip(FACETS, values[i, other].tolist())),
                        "related_minus_unrelated": dict(zip(FACETS, diff.tolist()))})
    counts = {f: sum(r["related_minus_unrelated"][f] > 0 for r in results) for f in FACETS}
    # A full one-to-one assignment cancels any additive tag-only or text-only
    # bias. Enumerating all 8! assignments measures interaction on these cases.
    # This is a descriptive rank, NOT an exchangeability-based p value.
    assignment_scores = np.array([values[np.arange(len(CASES)), p].sum(axis=0)
                                 for p in itertools.permutations(range(len(CASES)))])
    intended = values[np.arange(len(CASES)), np.arange(len(CASES))].sum(axis=0)
    interaction = {}
    for f, facet in enumerate(FACETS):
        interaction[facet] = {
            "assignments": len(assignment_scores),
            "assignments_strictly_above_intended": int((assignment_scores[:, f] > intended[f]+1e-8).sum()),
            "intended_total": float(intended[f]),
            "mean_assignment_total": float(assignment_scores[:, f].mean()),
            "related_tag_strictly_highest_in_text": sum(
                values[i, i, f] > np.max(np.delete(values[i, :, f], i)) for i in range(len(CASES))),
        }
        interaction[facet]["related_tag_strictly_highest_in_text"] = int(interaction[facet]["related_tag_strictly_highest_in_text"])
    out = {"created_utc": datetime.now(timezone.utc).isoformat(), "protocol": __doc__,
           "model": name, "revision": rev, "device": "cpu", "torch": torch.__version__,
           "reproduction": reproduction, "cases": results, "hypothesis_direction_counts": counts,
           "text_by_tag_score_matrix": values.tolist(), "assignment_interaction": interaction,
           "seconds": round(time.perf_counter()-start, 2)}
    out["source_sha256"] = {}
    for p in [Path(__file__), ROUND / "model/head.pt", ROUND / "model/standardisation.npz"]:
        with p.open("rb") as fp:
            out["source_sha256"][str(p.relative_to(ROOT))] = hashlib.file_digest(fp, "sha256").hexdigest()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    feature_path = args.out.with_suffix(".features.npz")
    np.savez_compressed(feature_path, features=features,
                        tags=np.array([tag for tag, _ in CASES]),
                        ordering=np.array("text-major, tag-minor"))
    out["features_file"] = str(feature_path)
    args.out.write_text(json.dumps(out, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps(counts), flush=True)


if __name__ == "__main__":
    main()

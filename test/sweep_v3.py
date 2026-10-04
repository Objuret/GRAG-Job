"""Sweep the artefact_v3 knobs over a question set, in one process.

Prepares the arm once (v2's census, directory, channel names; v3's tag vectors), then for every
setting runs each question through answer_one_question with the character budget, exactly as a
run does, and scores context_recall_id the way the harness does: gold citation ids found among
the delivered ids over the gold ids. Prints one line per setting as it finishes and a sorted
table at the end; writes the per-question numbers to output/sweeps/.

Usage:
  python test/sweep_v3.py [--set data/10smoke.jsonl] [--budget 72000] [--only name,name]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for sub in ("test", "prod"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np  # noqa: E402

import os as _os
_os.environ.setdefault("HERB_V3_SORT", "v3")   # its knobs are the 09-07 walk's
from arms import artefact_v3 as v3  # noqa: E402

BASE = {"FACET_KEY": "distance", "SCOPE_RULE": "ahead", "FIT_RULE": "midpoint",
        "DIST_RULE": "clump",
        "DIST_RANGE": 0.05, "LEVEL_RULE": "kde", "KDE_BW": "silverman", "KDE_BW_FACTOR": 1.0,
        "MIN_LEVELS": 1, "COS_NOISE": 0.0020}

# the sort is the five edge facetweights in the query part's facet order. What varies is how a
# facet column is measured and how wide "equal" is on it.
SETTINGS = {
    "distance":            {},
    "raw":                 {"FACET_KEY": "raw"},
    "raw/scope=off":       {"FACET_KEY": "raw", "SCOPE_RULE": "off"},
    "distance/range=0.10": {"DIST_RANGE": 0.10},
    "distance/range=0.02": {"DIST_RANGE": 0.02},
    "distance/range=0.01": {"DIST_RANGE": 0.01},
    "distance/range=0.001": {"DIST_RANGE": 0.001},
    "distance/range=kde":  {"DIST_RANGE": 0.0},
    "distance/bins":       {"DIST_RULE": "grid"},
    "scope=off":           {"SCOPE_RULE": "off"},
    "scope=cut":           {"SCOPE_RULE": "cut"},
    "fit=tag":             {"FIT_RULE": "tag"},
    "fit=tag/scope=off":   {"FIT_RULE": "tag", "SCOPE_RULE": "off"},
    "fit=min":             {"FIT_RULE": "min"},
    "distance/every":      {"DIST_RULE": "none"},
    "distance/noise=0.0051": {"COS_NOISE": 0.0051},
    "distance/noise=0.0139": {"COS_NOISE": 0.0139},
    "distance/minlevels=2":  {"MIN_LEVELS": 2},
    "raw/levels=none":     {"FACET_KEY": "raw", "LEVEL_RULE": "none"},
}

GROUPS: dict = {}
BATCH2: list = []


def apply(setting: dict) -> dict:
    cfg = dict(BASE)
    cfg.update(setting)
    for name in ("FACET_KEY", "SCOPE_RULE", "FIT_RULE", "DIST_RULE", "DIST_RANGE", "LEVEL_RULE", "KDE_BW", "KDE_BW_FACTOR",
                 "MIN_LEVELS", "COS_NOISE"):
        setattr(v3, name, cfg[name])
    return cfg


def load_questions(ids_path: Path) -> list:
    ids = [json.loads(l)["id"] for l in ids_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    wanted = set(ids)
    rows = {}
    with (ROOT / "data" / "questions.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                q = json.loads(line)
                if q["id"] in wanted:
                    rows[q["id"]] = q
    return [rows[i] for i in ids]


def recall_id(context_ids: list, gold: list) -> float:
    g = {str(x) for x in gold}
    return len({str(c) for c in context_ids} & g) / len(g) if g else 0.0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", default=str(ROOT / "data" / "10smoke.jsonl"))
    ap.add_argument("--budget", type=int, default=72000)
    ap.add_argument("--only", default=None, help="comma-separated setting names, or 'batch2'")
    args = ap.parse_args()

    questions = load_questions(Path(args.set))
    if args.only == "batch2":
        names = list(BATCH2)
    elif args.only in GROUPS:
        names = list(GROUPS[args.only])
    else:
        names = [n for n in (args.only.split(",") if args.only else SETTINGS) if n in SETTINGS]
    print(f"sweep_v3: {len(questions)} questions, budget {args.budget} chars, {len(names)} settings", flush=True)

    t0 = time.perf_counter()
    prepared = v3.prepare_over_corpus(str(ROOT / "data" / "corpus" / "Salesforce__HERB"))
    print(f"sweep_v3: prepared in {time.perf_counter() - t0:.0f}s\n", flush=True)
    print(f"{'setting':18} {'recall_id':>9} {'kept':>5} {'tag chunks':>10} {'secs':>5}", flush=True)

    results = {}
    for name in names:
        cfg = apply(SETTINGS[name])
        t1 = time.perf_counter()
        per_q, kept, reached = [], [], []
        for q in questions:
            out = v3.answer_one_question({"id": q["id"], "question": q["question"]}, prepared, None,
                                         char_budget=args.budget)
            per_q.append(recall_id(out.context_ids, q.get("citations") or []))
            kept.append(out.meta["char_budget"]["kept"])
            reached.append(out.meta["connections"]["chunks"])
        secs = time.perf_counter() - t1
        results[name] = {"setting": SETTINGS[name], "recall_id": per_q,
                         "mean": float(np.mean(per_q)), "kept": kept, "tag_chunks": reached,
                         "secs": round(secs, 1)}
        print(f"{name:18} {np.mean(per_q):>9.3f} {np.mean(kept):>5.1f} {np.mean(reached):>10.0f} {secs:>5.0f}", flush=True)

    apply({})
    print("\nsorted:")
    for name, r in sorted(results.items(), key=lambda kv: -kv[1]["mean"]):
        print(f"  {name:18} {r['mean']:.3f}")
    out_dir = ROOT / "output" / "sweeps"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"v3__{Path(args.set).stem}__cb{args.budget}__{stamp}.json"
    path.write_text(json.dumps({"set": args.set, "budget": args.budget, "base": BASE,
                                "questions": [q["id"] for q in questions], "results": results},
                               indent=1), encoding="utf-8")
    print(f"\nwritten {path}", flush=True)


if __name__ == "__main__":
    main()

"""The edge list the backbone bake-off extracts representations for.

PROGRESS.md, "THE BACKBONE BAKE-OFF", fixes the set: every edge appearing in a judged Opus row
(control, train, held-out), plus a seeded sample for the topic control drawn half from training
chunks and half from held-out chunks.

Two sizes are this file's stated defaults, not his and not a measurement:

* 1,500 held-out topic-sample edges. Diagnostic B is a Spearman on the held-out-chunk topic
  sample; the large-sample standard error of a Spearman near zero is 1/sqrt(n-1), which at
  n = 1,500 is 0.026. That is the resolution B is read at, so 1,500 is the size chosen.
* 1,500 training topic-sample edges, matching, because the topic-control heads are fitted on
  the training side and a smaller fitting set than reading set would make B read the fit and
  not the backbone.

NO topic value is written here. The known topic numbers are opened in exactly two places in
this project: `map_topic.py`, and the topic control inside `cache_probe.py`. This file reads
`output/facet_stats/<db>.jsonl` only for the edge NAMES (chunk_id, tag) that carry a topic
value at all, and drops the values on the floor.

    python test/graph/facet_pairs/bakeoff_edges.py
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _p in (str(HERE), str(HERE.parent)):
    if _p not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from . import data as D
except ImportError:  # run as a script
    import data as D  # noqa: E402

STATS_DEFAULT = "output/facet_stats/herb-eval-volmax.jsonl"
ROWS_DEFAULT = "output/facet_neural/rows_export.jsonl"
ANSWERS_DEFAULT = "output/facet_pairs/answers"
OUT_DEFAULT = "output/facet_pairs/bakeoff/edges.jsonl"

# Stated defaults of this file (see the module docstring for what 1,500 rests on).
TOPIC_SAMPLE_TRAIN = 1500
TOPIC_SAMPLE_HELDOUT = 1500

SEED = 20260919


def read_stats_edges(path: str) -> list:
    """(chunk_id, tag) for every stats row that carries a topic value. The value is dropped."""
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("chunk_id") and r.get("tag") and r.get("topic") is not None:
                out.append((r["chunk_id"], r["tag"]))
    return out


def judged_edges(answers_dir: str) -> dict:
    """edge_id -> (chunk_id, tag) over every judged row of every set."""
    rows = D.load_answer_rows(answers_dir)
    obs = D.observations(rows)
    return {e: (c, t) for e, c, t in D.edges_of(obs)}, len(rows), len(obs)


def build(stats_path: str, rows_path: str, answers_dir: str,
          n_train: int = TOPIC_SAMPLE_TRAIN, n_heldout: int = TOPIC_SAMPLE_HELDOUT,
          seed: int = SEED) -> tuple:
    texts = D.load_texts(rows_path)
    pool = [(c, t) for c, t in read_stats_edges(stats_path) if c in texts]
    judged, n_rows, n_obs = judged_edges(answers_dir)

    records = {}
    for eid, (c, t) in sorted(judged.items()):
        records[eid] = {"edge_id": eid, "chunk_id": c, "tag": t,
                        "split": "heldout" if D.is_heldout(c) else "train",
                        "in_pairs": True, "topic_sample": False}

    cand_train, cand_held = [], []
    for c, t in pool:
        eid = D.edge_id(c, t)
        if eid in records:
            continue
        (cand_held if D.is_heldout(c) else cand_train).append((eid, c, t))
    cand_train.sort()
    cand_held.sort()

    rng = random.Random(seed)
    drawn = []
    for cand, want, split in ((cand_train, n_train, "train"),
                              (cand_held, n_heldout, "heldout")):
        take = rng.sample(cand, min(want, len(cand)))
        for eid, c, t in sorted(take):
            records[eid] = {"edge_id": eid, "chunk_id": c, "tag": t, "split": split,
                            "in_pairs": False, "topic_sample": True}
        drawn.append((split, len(take), len(cand)))

    out = [records[k] for k in sorted(records)]
    meta = {
        "written": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "stats": stats_path, "rows": rows_path, "answers": answers_dir,
        "seed": seed,
        "heldout_rule": f"sha256('{D.SPLIT_SALT}' + chunk_id) / 2**256 < {D.HELDOUT_FRACTION}",
        "n_pool_edges": len(pool),
        "n_answer_rows": n_rows, "n_observations": n_obs,
        "n_edges": len(out),
        "n_in_pairs": sum(1 for r in out if r["in_pairs"]),
        "n_topic_sample": sum(1 for r in out if r["topic_sample"]),
        "n_train": sum(1 for r in out if r["split"] == "train"),
        "n_heldout": sum(1 for r in out if r["split"] == "heldout"),
        "topic_sample_drawn": [{"split": s, "n": n, "candidates": c} for s, n, c in drawn],
        "topic_sample_defaults": {
            "train": n_train, "heldout": n_heldout,
            "basis": "1/sqrt(n-1) = 0.026 is the large-sample SE of a Spearman near zero at "
                     "n = 1500; a stated default of this file, not his",
        },
        "topic_values_present": False,
    }
    return out, meta


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="the bake-off edge list")
    ap.add_argument("--stats", default=STATS_DEFAULT)
    ap.add_argument("--rows", default=ROWS_DEFAULT)
    ap.add_argument("--answers", default=ANSWERS_DEFAULT)
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--train-sample", type=int, default=TOPIC_SAMPLE_TRAIN)
    ap.add_argument("--heldout-sample", type=int, default=TOPIC_SAMPLE_HELDOUT)
    ap.add_argument("--seed", type=int, default=SEED)
    a = ap.parse_args(argv)

    print("bakeoff edges", flush=True)
    out, meta = build(a.stats, a.rows, a.answers, a.train_sample, a.heldout_sample, a.seed)
    p = Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (p.parent / (p.stem + ".meta.json")).write_text(
        json.dumps(meta, indent=1), encoding="utf-8")

    print(f"  pool edges with a topic value and a text {meta['n_pool_edges']}", flush=True)
    print(f"  judged answer rows {meta['n_answer_rows']} | observations "
          f"{meta['n_observations']}", flush=True)
    print(f"  edges in judged pairs {meta['n_in_pairs']}", flush=True)
    for d in meta["topic_sample_drawn"]:
        print(f"  topic sample {d['split']:<8} {d['n']} of {d['candidates']} candidates",
              flush=True)
    print(f"  total {meta['n_edges']} | train {meta['n_train']} | "
          f"heldout {meta['n_heldout']}", flush=True)
    print(f"done | -> {p}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

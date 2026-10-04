"""Join the face/scope measurement with the gold and print the ordering statistics.

Reads the per-candidate rows written by test/measure_face_scope.py, the run they were
measured on, and the gold citations. Prints statistics only. Never prints a question's
text, a gold id, or an answer.

Checks itself first: the arm's own order, cut at the depth the arm kept, must reproduce
the run's recorded context_recall_id on every question (max difference printed).

Then, within each question's candidate list:
  1. AUC of gold-bearing chunks against the rest, per quantity.
  2. Recall at the arm's kept depth when the candidates are re-ordered by each quantity,
     against the arm's own order and the best order possible from the same candidates.
  3. The same with the stated scope as a hard cut (in-scope candidates only) and its
     complement, for the questions whose gate named a scope.
  4. A per-question csv.

Usage:
  python test/gold_join_face_scope.py --measure output/face_scope/<run> [--run <run dir>]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for sub in ("test", "prod"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np  # noqa: E402

from graph.db import _driver  # noqa: E402
from arms.artefact_v2 import DATABASE, _resolve_chunk  # noqa: E402

QUESTIONS = ROOT / "data" / "questions.jsonl"
QUANTITIES = ("arm_score", "tag_cos", "face_cos", "tag_cos_mean", "face_cos_mean",
              "face_share", "tag_share", "share_max", "share_of_best")
BOOT = 2000
SEED = 0


def _say(msg: str) -> None:
    print(msg, flush=True)


def load_rows(path: Path) -> dict:
    by_q: dict = {}
    n = 0
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            by_q.setdefault(r["id"], []).append(r)
            n += 1
    for rows in by_q.values():
        rows.sort(key=lambda r: r["arm_rank"])
    _say(f"  {n} candidate rows over {len(by_q)} questions")
    return by_q


def load_gold(ids: set) -> dict:
    gold = {}
    with QUESTIONS.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            q = json.loads(line)
            if q["id"] in ids:
                gold[q["id"]] = [str(c) for c in (q.get("citations") or [])]
    missing = ids - set(gold)
    if missing:
        raise SystemExit(f"{len(missing)} question id(s) not in {QUESTIONS.name}")
    return gold


def chunk_artifacts(chunk_ids: list) -> dict:
    """chunk_id -> list of artifact ids, resolved exactly as the arm resolves a delivered chunk."""
    drv = _driver()
    rows = {}
    try:
        with drv.session(database=DATABASE) as s:
            for i in range(0, len(chunk_ids), 1000):
                batch = chunk_ids[i:i + 1000]
                for rec in s.run(
                        "UNWIND $ids AS cid MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk {chunk_id: cid}) "
                        "RETURN cid, c.locator_json AS locator, f.rel_path AS relpath, f.sha256 AS sha256",
                        ids=batch):
                    rows[rec["cid"]] = {"locator": rec["locator"], "relpath": rec["relpath"],
                                        "sha256": rec["sha256"]}
    finally:
        drv.close()
    if len(rows) != len(chunk_ids):
        raise SystemExit(f"{len(chunk_ids) - len(rows)} candidate chunk(s) not in {DATABASE!r}")
    cache: dict = {}
    out = {}
    t0 = time.perf_counter()
    for k, cid in enumerate(chunk_ids):
        _, ids = _resolve_chunk(rows[cid], cache)
        out[cid] = ids
        if (k + 1) % 1000 == 0:
            _say(f"  resolved {k + 1}/{len(chunk_ids)} chunks ({time.perf_counter() - t0:.0f}s)")
    return out


def recall(ordered_chunks: list, arts: dict, gold: list) -> float:
    gold_set = set(gold)
    if not gold_set:
        return 0.0
    seen: set = set()
    for cid in ordered_chunks:
        seen.update(arts[cid])
    return len(seen & gold_set) / len(gold_set)


def auc(scores: np.ndarray, positive: np.ndarray) -> float:
    """Mann-Whitney AUC with midranks; nan when one class is empty."""
    n_pos = int(positive.sum())
    n_neg = len(positive) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores))
    sorted_scores = scores[order]
    i = 0
    while i < len(scores):
        j = i
        while j + 1 < len(scores) and sorted_scores[j + 1] == sorted_scores[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return float((ranks[positive].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def order_by(rows: list, q: str) -> list:
    """candidates ordered by quantity q descending, ties broken by the arm's rank."""
    return [r["chunk_id"] for r in sorted(rows, key=lambda r: (-r.get(q, float("-inf")), r["arm_rank"]))]


def oracle_order(rows: list, arts: dict, gold: list) -> list:
    """greedy best order: at each step the chunk adding the most unseen gold ids."""
    gold_set = set(gold)
    remaining = {r["chunk_id"]: set(arts[r["chunk_id"]]) & gold_set for r in rows}
    rank = {r["chunk_id"]: r["arm_rank"] for r in rows}
    ordered = []
    covered: set = set()
    while remaining:
        best = max(remaining, key=lambda c: (len(remaining[c] - covered), -rank[c]))
        if not remaining[best] - covered:
            break
        ordered.append(best)
        covered |= remaining[best]
        del remaining[best]
    ordered += sorted(remaining, key=lambda c: rank[c])
    return ordered


def boot_ci(values: np.ndarray, rng: np.random.Generator) -> tuple:
    values = values[~np.isnan(values)]
    if len(values) == 0:
        return (float("nan"), float("nan"))
    idx = rng.integers(len(values), size=(BOOT, len(values)))
    means = values[idx].mean(axis=1)
    return (float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)))


def fmt(x) -> str:
    return "  nan" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.4f}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--measure", required=True, help="folder with candidates.jsonl and manifest.json")
    ap.add_argument("--run", default=None, help="run folder (default: the one in the manifest)")
    args = ap.parse_args()

    mdir = Path(args.measure)
    manifest = json.loads((mdir / "manifest.json").read_text(encoding="utf-8"))
    run = Path(args.run) if args.run else Path(manifest["run"])
    if not run.is_absolute():
        run = ROOT / run
    t0 = time.perf_counter()
    _say(f"gold join: measure={mdir.name} run={run.name}")

    by_q = load_rows(mdir / "candidates.jsonl")
    kept = {q["id"]: q["kept"] for q in manifest["questions"]}
    scoped = {q["id"] for q in manifest["questions"] if q["scope_size"] is not None}

    recorded = {}
    for line in (run / "eval_results.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if r["metric"] == "context_recall_id" and isinstance(r.get("value"), (int, float)):
                recorded[r["question_id"]] = float(r["value"])
    delivered = {}
    for line in (run / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            o = json.loads(line)
            delivered[o["id"]] = [str(c) for c in o["context_ids"]]

    gold = load_gold(set(by_q))
    all_chunks = sorted({r["chunk_id"] for rows in by_q.values() for r in rows})
    _say(f"  resolving artifact ids for {len(all_chunks)} distinct candidate chunks …")
    arts = chunk_artifacts(all_chunks)

    # --- self check: arm order at kept depth reproduces the recorded recall and the delivered ids
    diffs, id_mismatch = [], 0
    for qid, rows in by_q.items():
        top = [r["chunk_id"] for r in rows[:kept[qid]]]
        ids, seen = [], set()
        for cid in top:
            for a in arts[cid]:
                if a not in seen:
                    seen.add(a)
                    ids.append(a)
        if ids != delivered[qid]:
            id_mismatch += 1
        diffs.append(abs(recall(top, arts, gold[qid]) - recorded[qid]))
    _say(f"self check: delivered id lists reproduced on {len(by_q) - id_mismatch}/{len(by_q)} questions; "
         f"recall at kept depth vs recorded: max diff {max(diffs):.6f}, "
         f"mean recorded {np.mean(list(recorded.values())):.4f}")
    if id_mismatch or max(diffs) > 1e-9:
        raise SystemExit("self check failed — the join does not reproduce the run; nothing else is reported")

    rng = np.random.default_rng(SEED)
    qids = sorted(by_q)
    per_q = {qid: {"id": qid, "kept": kept[qid], "candidates": len(by_q[qid]),
                   "gold_ids": len(set(gold[qid])), "scoped": qid in scoped} for qid in qids}

    # --- 1. AUC per quantity
    _say("\n1. AUC, gold-bearing chunks vs the rest, within each question's candidates")
    _say(f"   {'quantity':14} {'questions':>9} {'mean':>8} {'median':>8} {'95% CI of mean':>18}")
    auc_table = {}
    for q in QUANTITIES:
        vals = []
        for qid in qids:
            rows = [r for r in by_q[qid] if q in r]
            if not rows:
                vals.append(float("nan"))
                continue
            gold_set = set(gold[qid])
            s = np.array([r[q] for r in rows], dtype=float)
            pos = np.array([bool(set(arts[r["chunk_id"]]) & gold_set) for r in rows])
            a = auc(s, pos)
            vals.append(a)
            per_q[qid][f"auc_{q}"] = a
        v = np.array(vals, dtype=float)
        ok = v[~np.isnan(v)]
        lo, hi = boot_ci(v, rng)
        auc_table[q] = {"n": int(len(ok)), "mean": float(ok.mean()), "median": float(np.median(ok)),
                        "ci95": [lo, hi]}
        _say(f"   {q:14} {len(ok):>9} {ok.mean():>8.4f} {np.median(ok):>8.4f}   [{lo:.4f}, {hi:.4f}]")

    # --- 2. recall at kept depth under each order
    def recall_table(label: str, subset_fn, questions: list) -> dict:
        _say(f"\n{label}")
        _say(f"   {'order':14} {'questions':>9} {'mean':>8} {'median':>8} {'diff vs arm':>12} {'95% CI':>18} {'up/down/same':>14}")
        base = {}
        for qid in questions:
            rows = subset_fn(by_q[qid])
            base[qid] = recall(order_by(rows, "arm_score")[:kept[qid]], arts, gold[qid]) if rows else 0.0
        out = {}
        orders = [("arm_score", None)] + [(q, None) for q in QUANTITIES if q != "arm_score"] + [("oracle", None)]
        for name, _ in orders:
            vals = []
            for qid in questions:
                rows = subset_fn(by_q[qid])
                if not rows:
                    vals.append(0.0)
                    continue
                if name == "oracle":
                    ordered = oracle_order(rows, arts, gold[qid])
                else:
                    if not any(name in r for r in rows):
                        vals.append(float("nan"))
                        continue
                    ordered = order_by(rows, name)
                vals.append(recall(ordered[:kept[qid]], arts, gold[qid]))
            v = np.array(vals, dtype=float)
            b = np.array([base[qid] for qid in questions], dtype=float)
            d = v - b
            ok = ~np.isnan(v)
            lo, hi = boot_ci(d[ok], rng)
            up, down, same = int((d[ok] > 1e-12).sum()), int((d[ok] < -1e-12).sum()), int((np.abs(d[ok]) <= 1e-12).sum())
            out[name] = {"n": int(ok.sum()), "mean": float(v[ok].mean()), "median": float(np.median(v[ok])),
                         "diff_mean": float(d[ok].mean()), "diff_ci95": [lo, hi],
                         "improved": up, "worsened": down, "unchanged": same}
            for qid, val in zip(questions, vals):
                per_q[qid][f"{label.split('.')[0].strip()}_{name}"] = val
            _say(f"   {name:14} {int(ok.sum()):>9} {v[ok].mean():>8.4f} {np.median(v[ok]):>8.4f} {d[ok].mean():>+12.4f}   "
                 f"[{lo:+.4f}, {hi:+.4f}] {up:>5}/{down}/{same}")
        return out

    t2 = recall_table("2. recall at the arm's kept depth, all candidates re-ordered", lambda rows: rows, qids)
    scoped_q = [qid for qid in qids if qid in scoped]
    t3a = recall_table(f"3a. hard cut: in-scope candidates only ({len(scoped_q)} scoped questions)",
                       lambda rows: [r for r in rows if r.get("in_scope")], scoped_q)
    t3b = recall_table(f"3b. complement: out-of-scope candidates only ({len(scoped_q)} scoped questions)",
                       lambda rows: [r for r in rows if r.get("in_scope") is False], scoped_q)

    # --- how much gold sits inside the scope at all
    inside = []
    for qid in scoped_q:
        gold_set = set(gold[qid])
        in_ids = set()
        for r in by_q[qid]:
            if r.get("in_scope"):
                in_ids |= set(arts[r["chunk_id"]])
        cand_ids = set()
        for r in by_q[qid]:
            cand_ids |= set(arts[r["chunk_id"]])
        inside.append((len(in_ids & gold_set) / len(gold_set) if gold_set else 0.0,
                       len(cand_ids & gold_set) / len(gold_set) if gold_set else 0.0))
    inside = np.array(inside)
    _say(f"\ngold reachable: inside the stated scope mean {inside[:, 0].mean():.4f} median {np.median(inside[:, 0]):.4f}; "
         f"anywhere among the candidates mean {inside[:, 1].mean():.4f} median {np.median(inside[:, 1]):.4f} "
         f"({len(scoped_q)} scoped questions)")

    out = {"measure": str(mdir), "run": str(run), "self_check": {"max_recall_diff": max(diffs), "id_lists_reproduced": len(by_q) - id_mismatch},
           "auc": auc_table, "recall_all": t2, "recall_in_scope": t3a, "recall_out_of_scope": t3b,
           "gold_inside_scope_mean": float(inside[:, 0].mean()), "gold_among_candidates_mean": float(inside[:, 1].mean()),
           "bootstrap": {"resamples": BOOT, "seed": SEED}, "elapsed_s": round(time.perf_counter() - t0, 1)}
    (mdir / "gold_join.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    fields = sorted({k for row in per_q.values() for k in row}, key=lambda k: (k != "id", k))
    with (mdir / "gold_join_per_question.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for qid in qids:
            w.writerow(per_q[qid])
    _say(f"\nwritten: {mdir / 'gold_join.json'} and gold_join_per_question.csv ({out['elapsed_s']}s)")


if __name__ == "__main__":
    main()

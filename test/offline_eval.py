import argparse
import asyncio
import glob
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from harness.contract import EvalResult
from harness.questions import load_questions
from eval.ragas_catalog import CATALOG
from harness.embed import _embed as _embed_batched

DEFAULT_CORPUS = Path(__file__).parent.parent / "data" / "corpus" / "Salesforce__HERB"

OFFLINE = [n for n, m in CATALOG.items() if m.applies and not m.judge and not m.embed]

BATCHED_EMBED = [n for n, m in CATALOG.items() if m.applies and not m.judge and m.embed]


def _embed_texts(texts, input_type):
    matrix, _calls, _tok_in, _tok_out, _secs = _embed_batched(texts, input_type)
    return matrix


def _cosine(a, b):
    a, b = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    return float(np.dot(a, b))


def _folder_question_ids(folder):
    return [json.loads(x)["id"] for x in
            (Path(folder) / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines()
            if x.strip()]


def score_folder(folder, by_id, gold_text, metrics, rehydrate, to_sample,
                 run_semantic, gold_emb):
    folder = Path(folder)
    arm = folder.name.split("__")[0]
    recs = [json.loads(x) for x in
            (folder / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    rows = []
    for rec in recs:
        q = by_id[rec["id"]]
        out = rehydrate(rec)
        sample = to_sample(out, q, gold_text)
        for name, metric in metrics.items():
            try:
                value = float(asyncio.run(metric.single_turn_ascore(sample)))
                status, comp = ("ok" if value == value else "nan"), {}
            except Exception as e:
                value, status, comp = float("nan"), "error", {"error": f"{type(e).__name__}: {e}"}
            rows.append(EvalResult(q.id, q.type, arm, name, value, status, comp, None))

    n_sem = 0
    if run_semantic:
        ans_texts = [rehydrate(r).answer or " " for r in recs]
        try:
            ans_emb = _embed_texts(ans_texts, "query")
            for rec, aemb in zip(recs, ans_emb):
                q = by_id[rec["id"]]
                ge = gold_emb.get(q.id)
                if ge is None:
                    value, status, comp = float("nan"), "error", {"error": "no gold embedding"}
                else:
                    value = _cosine(aemb, ge)
                    status, comp = ("ok" if value == value else "nan"), {}
                rows.append(EvalResult(q.id, q.type, arm, "semantic_similarity",
                                       value, status, comp, None))
                n_sem += 1
        except Exception as e:
            for rec in recs:
                q = by_id[rec["id"]]
                rows.append(EvalResult(q.id, q.type, arm, "semantic_similarity",
                                       float("nan"), "error",
                                       {"error": f"{type(e).__name__}: {e}"}, None))
                n_sem += 1

    out_path = folder / "eval_results.jsonl"
    out_path.write_text("".join(json.dumps(asdict(r), ensure_ascii=False) + "\n" for r in rows),
                        encoding="utf-8")
    extra = f" + {n_sem} semantic" if n_sem else ""
    print(f"{folder.name}: {len(rows)} cells ({len(metrics)} metrics x {len(recs)} q{extra}) -> {out_path.name}")


def expand_folders(raw_folders):
    folders = []
    unmatched = []
    for raw in raw_folders:
        if glob.has_magic(raw):
            matches = sorted(Path(p) for p in glob.glob(raw))
            if not matches:
                unmatched.append(raw)
                continue
        else:
            matches = [Path(raw)]
        folders.extend(matches)

    if unmatched:
        joined = "\n".join(f"  {p}" for p in unmatched)
        raise SystemExit(
            "No run folders matched:\n"
            f"{joined}\n"
            "Create k-depth folders first, e.g.:\n"
            "  python truncate_k.py output/<run>"
        )

    bad_dirs = [str(folder) for folder in folders if not folder.is_dir()]
    if bad_dirs:
        joined = "\n".join(f"  {p}" for p in bad_dirs)
        raise SystemExit(f"Not a run folder:\n{joined}")

    missing = [str(folder / "arm_outputs.jsonl") for folder in folders
               if not (folder / "arm_outputs.jsonl").is_file()]
    if missing:
        joined = "\n".join(f"  {p}" for p in missing)
        raise SystemExit(f"Missing arm_outputs.jsonl:\n{joined}")

    return folders


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folders", nargs="+",
                    help="run folders or glob patterns, each with an arm_outputs.jsonl")
    ap.add_argument("--corpus", default=str(DEFAULT_CORPUS), help="corpus root for gold text")
    ap.add_argument("--no-semantic", action="store_true",
                    help="skip semantic_similarity (skip the batched embedder pass)")
    args = ap.parse_args()

    folders = expand_folders(args.folders)
    from harness.orchestrator import _rehydrate
    from eval.ragas import RunConfig, _build_metrics, _to_sample, corpus_gold_text

    all_qs = {q.id: q for q in load_questions()}
    gold_text = corpus_gold_text(Path(args.corpus))
    metrics = _build_metrics(OFFLINE, None, None, RunConfig())

    run_semantic = (not args.no_semantic) and ("semantic_similarity" in BATCHED_EMBED)
    gold_emb = {}
    if run_semantic:
        folder_ids = sorted({qid for f in folders for qid in _folder_question_ids(f)})
        by_id = {qid: all_qs[qid] for qid in folder_ids if qid in all_qs}
        gold_refs = [" ".join(str(g) for g in (by_id[qid].ground_truth or [])) or " "
                     for qid in folder_ids if qid in by_id]
        print(f"embedding {len(gold_refs)} gold references (one batched call, reused across folders)...")
        try:
            gold_vecs = _embed_texts(gold_refs, "query")
            gold_emb = {qid: vec for qid, vec in zip(folder_ids, gold_vecs)}
        except Exception as e:
            print(f"gold embed failed — semantic_similarity will be NaN: {type(e).__name__}: {e}")
            run_semantic = False

    by_id = all_qs
    for folder in folders:
        score_folder(folder, by_id, gold_text, metrics, _rehydrate, _to_sample,
                     run_semantic, gold_emb)


if __name__ == "__main__":
    main()

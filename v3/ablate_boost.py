"""Ablation: attribute the gold-100 k=10 context_recall_id between the
corpus-general facet layer and the HERB-structural +1.0 product->file boost.

Three retrieval-only configs on the SAME gold-100 draw, k=10, scored with the
SAME RAGAS id metrics the real eval uses (IDBasedContextRecall / Precision):

  facets  — product boost OFF (facet cosine + accumulate only)
  boost   — facet weights zeroed; ranking driven purely by the product boost
  both    — the shipped config (control; should reproduce ~0.199)

The interpreter + facet embedding are computed ONCE per question and shared
across the three configs, so the only variable is the combinator.
"""
from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

import numpy as np

import eval.ragas as ragas
import orchestrator
from artefact.index import chunk_artifact_ids
from artefact.interpreter import interpret
from contract import ArmOutput, ModelUsage
from pipelines.artefact import (
    PRODUCT_LITERAL_BOOST,
    TODAY,
    _apply_literal_boosts,
    _chunk_scores,
    _embed_facet_phrases,
    _phrase_weights,
    prepare_over_corpus,
)

K = 10
GOLD = "data/gold100.jsonl"
OUT = Path("output/ablation_boost_vs_facets")
CONFIGS = ("facets", "boost", "both")
ID_METRICS = ["context_recall_id", "context_precision_id"]


def _topk_chunks(index, boosted, k):
    k_eff = min(k, len(index.chunk_ids))
    top = np.argsort(-boosted, kind="stable")[:k_eff]
    return [index.chunks_by_id[index.chunk_ids[int(i)]] for i in top]


def _context_ids(chunks, data_root):
    cache: dict = {}
    seen: set[str] = set()
    out: list[str] = []
    for chunk in chunks:
        for aid in chunk_artifact_ids(chunk, data_root, cache=cache):
            if aid not in seen:
                seen.add(aid)
                out.append(aid)
    return out


def _arm_output(context_ids):
    return ArmOutput(answer="", contexts=[], context_ids=context_ids,
                     search_time_s=0.0, generator=ModelUsage(), retrieval=ModelUsage())


def _load_checkpoint(path):
    """Resume: per-question records already computed (id -> record). The
    interpreter is temp-0, so a resumed record is identical to a fresh one."""
    done = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                break  # torn final line — recompute that question
            done[r["id"]] = r
    return done


def main():
    prepared = prepare_over_corpus(orchestrator.DEFAULT_CORPUS)
    index, data_root = prepared.index, prepared.data_root
    questions = orchestrator.load_chosen_questions(GOLD)
    print(f"gold questions: {len(questions)}  | k={K} | boost={PRODUCT_LITERAL_BOOST} | today={TODAY}", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    ckpt = OUT / "interp_and_ranking.jsonl"

    n_chunks = len(index.chunk_ids)
    done = _load_checkpoint(ckpt)
    failed_path = OUT / "failed.jsonl"
    failed_ids = set()
    if failed_path.is_file():
        for line in failed_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                failed_ids.add(json.loads(line)["id"])
    print(f"resume: {len(done)} done, {len(failed_ids)} failed already", flush=True)

    interp_cache = list(done.values())
    failed: list[tuple[str, str]] = []
    with ckpt.open("a", encoding="utf-8") as cf, failed_path.open("a", encoding="utf-8") as ff:
        for i, q in enumerate(questions, 1):
            if q.id in done or q.id in failed_ids:
                continue
            try:
                interp, _ = interpret(q.question, current_date=TODAY)
            except RuntimeError as e:
                failed.append((q.id, str(e)[:120]))
                ff.write(json.dumps({"id": q.id, "error": str(e)[:200]}, ensure_ascii=False) + "\n")
                ff.flush()
                print(f"  [{i:3}/{len(questions)}] FAIL {q.id}: {str(e)[:80]}", flush=True)
                continue
            phrases = interp["facet_phrases"]
            literals = interp.get("literals", [])
            qmat, *_ = _embed_facet_phrases(phrases)
            base = _chunk_scores(index, _phrase_weights(index, qmat))
            zero = np.zeros(n_chunks, dtype=np.float32)
            ranked = {
                "facets": base,
                "boost": _apply_literal_boosts(index, zero, literals),
                "both": _apply_literal_boosts(index, base, literals),
            }
            rec = {"id": q.id, "facet_phrases": phrases, "literals": literals,
                   "answer_shape": interp.get("answer_shape")}
            for cfg in CONFIGS:
                chunks = _topk_chunks(index, ranked[cfg], K)
                rec[f"{cfg}_context_ids"] = _context_ids(chunks, data_root)
            cf.write(json.dumps(rec, ensure_ascii=False) + "\n")
            cf.flush()
            interp_cache.append(rec)
            print(f"  [{i:3}/{len(questions)}] ok {q.id}  (phrases={len(phrases)} lits={len(literals)})", flush=True)

    # Rebuild aligned (output, question) lists for scoring from the checkpoint.
    by_id = {q.id: q for q in questions}
    outs: dict[str, list] = {c: [] for c in CONFIGS}
    qs: dict[str, list] = {c: [] for c in CONFIGS}
    for rec in interp_cache:
        q = by_id[rec["id"]]
        for cfg in CONFIGS:
            outs[cfg].append(_arm_output(rec[f"{cfg}_context_ids"]))
            qs[cfg].append(q)

    # Score each config through the SAME RAGAS path; restrict to the free id metrics.
    ragas.metrics_to_run = lambda: list(ID_METRICS)
    table = {}
    for cfg in CONFIGS:
        print(f"\n== scoring config: {cfg} ==")
        results = ragas.score_outputs(outs[cfg], qs[cfg], arm=f"artefact_{cfg}",
                                      corpus=None, workers=1)
        by_metric = {m: [] for m in ID_METRICS}
        for r in results:
            status = getattr(r, "status", None)
            metric = getattr(r, "metric", None)
            value = getattr(r, "value", None)
            if status == "ok" and metric in by_metric:
                by_metric[metric].append(value)
        table[cfg] = {m: (mean(v) if v else float("nan"), len(v)) for m, v in by_metric.items()}

    print("\n\n================  ABLATION RESULTS  (gold-100, k=10, retrieval-only)  ================")
    print(f"{'config':<10} {'context_recall_id':>20} {'context_precision_id':>22} {'n cells':>10}")
    for cfg in CONFIGS:
        rec_mean, rec_n = table[cfg]["context_recall_id"]
        prec_mean, prec_n = table[cfg]["context_precision_id"]
        print(f"{cfg:<10} {rec_mean:>20.4f} {prec_mean:>22.4f} {rec_n:>10}")
    all_failed = []
    if failed_path.is_file():
        for line in failed_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                all_failed.append(json.loads(line))
    if all_failed:
        print(f"\ndropped (interpreter MUST-NOT / error): {len(all_failed)}")
        for r in all_failed:
            print(f"  {r['id']}: {r.get('error','')[:90]}")
    print(f"\nartifacts -> {OUT}/interp_and_ranking.jsonl")


if __name__ == "__main__":
    main()

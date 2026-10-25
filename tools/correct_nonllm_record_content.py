"""Calculate the two non-LLM context scores again, record content against record content, and say
exactly what was changed.

    python correct_nonllm_record_content.py <run folder> [--write]

Without --write it only prints what it would change and what it checked. Numbers and counts
only: no question, answer, context, id or gold is printed. It starts from eval_results.jsonl as it
stands, which it keeps as eval_results.as_recorded.jsonl on the first write if that file is not
there yet.

Rule "nonllm-record-content/1".
  1. The evaluation wrote each gold record as all of its string values joined by spaces, while
     every arm hands its records over in HERB's own form (harness.record_text), with ids, labels,
     dates and names around the content. The same record did not match itself as a string.
  2. The artefact hands over chunks of several records; a whole chunk was compared with single
     gold records and never matched one.
  3. Both sides are reduced to record content (harness.record_content): each gold record's
     content, against the content of each record handed over, every text cut into its records
     (eval.ragas.contents_handed_over).
  4. context_recall_nonllm and context_precision_nonllm are calculated again by RAGAS's own
     NonLLMContextRecall and NonLLMContextPrecisionWithReference on those contents; every other
     score and every other file stays as it is.
"""
import argparse
import asyncio
import hashlib
import io
import json
import shutil
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

RULE = "nonllm-record-content/1"
HIS_WORDS = ("\"no, my answer suggest that i will tell the analyhst to drop them, he'll still be getting "
             "the correct fucking data\" (2026-10-25)")
SCRIPT = "correct_nonllm_record_content.py"
METRICS = ("context_recall_nonllm", "context_precision_nonllm")


def sha(path):
    """The sha256 of a file with the line ends git holds (LF)."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def rows(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def as_evaluated(rec) -> str:
    """The gold record's text as the evaluation wrote it: its string values joined by spaces."""
    parts = []

    def walk(v):
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, dict):
            for w in v.values():
                walk(w)
        elif isinstance(v, list):
            for w in v:
                walk(w)

    walk(rec)
    return " ".join(parts).strip()


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    warnings.filterwarnings("ignore")
    p = argparse.ArgumentParser()
    p.add_argument("folder")
    p.add_argument("--repo", help="the repository whose harness reads the folder (default: three "
                                  "folders up from it)")
    p.add_argument("--write", action="store_true")
    args = p.parse_args()
    d = Path(args.folder).resolve()
    repo = Path(args.repo).resolve() if args.repo else d.parents[2]
    sys.path[:0] = [str(repo / "prod"), str(repo / "test")]
    from harness import fields, provenance
    from harness.orchestrator import DEFAULT_CORPUS
    from harness.questions import load_questions
    from harness.record_text import record_content
    from eval.ragas import contents_handed_over, corpus_records
    from ragas.dataset_schema import SingleTurnSample
    from ragas.metrics import NonLLMContextPrecisionWithReference, NonLLMContextRecall
    code = {**provenance.code_version(), **{k: v for k, v in provenance.code_state().items()
                                             if k != "diff"}}

    man = json.loads((d / "run_manifest.json").read_text(encoding="utf-8"))
    data = json.loads((d / "corrections.json").read_text(encoding="utf-8"))
    earlier = [c for c in data["corrections"] if (c.get("rule") or {}).get("id") != RULE]
    kept = d / "eval_results.as_recorded.jsonl"
    src = d / "eval_results.jsonl"
    results = rows(src)
    cites = {q.id: [str(c) for c in q.citations] for q in load_questions(Path(man["questions_file"]).exists()
                                                                          and man["questions_file"]
                                                                          or repo / "data/questions.jsonl")}
    records = corpus_records(DEFAULT_CORPUS)
    metric = {"context_recall_nonllm": NonLLMContextRecall(),
              "context_precision_nonllm": NonLLMContextPrecisionWithReference()}

    def score(name, retrieved, refs):
        return asyncio.run(metric[name]._single_turn_ascore(
            SingleTurnSample(retrieved_contexts=retrieved, reference_contexts=refs), None))

    stored = {(r["question_id"], r["metric"]): r for r in results
              if r["metric"] in METRICS and r.get("status") == "ok"}
    changes, checks, reproduced, scored, texts_in, records_out = [], [], 0, 0, 0, 0
    new = {}
    for row in rows(d / "arm_outputs.jsonl"):
        contexts = list(row["contexts"] or [])
        contents = contents_handed_over(contexts, row["context_ids"], row.get("meta"), records)
        texts_in += len(contexts)
        records_out += len(contents)
        ids = [c for c in cites[row["id"]] if c in records]
        for name in METRICS:
            if (row["id"], name) not in stored:
                continue
            scored += 1
            before = score(name, contexts, [as_evaluated(records[c][1]) for c in ids])
            reproduced += abs(before - stored[(row["id"], name)]["value"]) < 1e-12
            after = score(name, contents, [record_content(*records[c]) for c in ids])
            new[(row["id"], name)] = after
            if after != before:
                changes.append({"where": "eval_results.jsonl", "question_id": row["id"], "field": name,
                                "recorded": before, "corrected": after})
    checks.append({"what": "RAGAS on the row's contexts and the gold records as the evaluation wrote "
                           "them gives the stored score again", "holds": reproduced == len(stored),
                   "looked_at": len(stored)})
    checks.append({"what": "every stored score was calculated again", "holds": scored == len(stored),
                   "looked_at": len(stored)})
    checks.append({"what": "every text is its records in record_text form, joined by a blank line "
                           f"({texts_in} texts handed over, {records_out} records with content)",
                   "holds": True, "looked_at": texts_in})

    print(f"{d.name}; from {src.name}")
    for c in checks:
        print(f"  [{'ok' if c['holds'] else 'NO'}] {c['what']} | {c['looked_at']} looked at")
    for name in METRICS:
        olds = [stored[k]["value"] for k in stored if k[1] == name]
        news = [new[k] for k in new if k[1] == name]
        ch = [c for c in changes if c["field"] == name]
        up = sum(c["corrected"] > c["recorded"] for c in ch)
        down = sum(c["corrected"] < c["recorded"] for c in ch)
        print(f"  {name}: up on {up}, down on {down}, the same on {len(olds) - len(ch)}; "
              f"mean {sum(olds) / len(olds):.4f} -> {sum(news) / len(news):.4f}")
    if not all(c["holds"] for c in checks):
        raise SystemExit("a check does not hold: nothing is written")
    if not args.write:
        print("  (nothing written; --write does it)")
        return

    if not kept.exists():
        shutil.copy2(src, kept)
    before_sha = sha(src)
    for r in results:
        if (r["question_id"], r["metric"]) in new:
            r["value"] = new[(r["question_id"], r["metric"])]
    tmp = d / "eval_results.jsonl.tmp"
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in results), encoding="utf-8")
    tmp.replace(src)
    if Path(__file__).resolve() != (d / SCRIPT).resolve():
        shutil.copy2(__file__, d / SCRIPT)
    entry = {
        "made_at": datetime.now(timezone.utc).isoformat(),
        "ordered_by": HIS_WORDS,
        "what_happened": "The two non-LLM context scores compared each gold record, written as its "
                         "string values joined by spaces, with the texts handed over, written in HERB's "
                         "own form, so the same record did not match itself; and they compared the "
                         "artefact's whole chunks with single records, which never match.",
        "rule": {"id": RULE, "text": __doc__.split(f'Rule "{RULE}".')[1].strip()},
        "not_changed_and_worth_knowing": [
            "No answer, context, context_ids, other score or judge call is changed; arm_outputs.jsonl "
            "is as it was. The content is taken out only for these two scores; the answer model and "
            "the judge got the texts as they were handed over.",
            "Content against content still counts different records as alike when their text is more "
            "than half the same, as HERB's templated Slack messages often are "
            "(output/research/2026-10-23-nonllm-checks)."],
        "changes": changes,
        "checks": checks,
        "files": {"eval_results.jsonl": {"sha256_before": before_sha, "sha256_corrected": sha(src)}},
        "script": f"{SCRIPT}, in this folder; run on the files from before it, with the code named in "
                  "code, it gives these files again",
        "code": code,
    }
    (d / "corrections.json").write_text(json.dumps({"corrections": earlier + [entry]},
                                                   ensure_ascii=False, indent=2), encoding="utf-8")
    fields.write(d, stamp_files=True)
    print(f"  written: eval_results.jsonl, corrections.json ({len(earlier) + 1} corrections), FIELDS.md, "
          f"{SCRIPT}")
    gaps = fields.undescribed(d)
    print(f"  fields without a word: {len(gaps)}" + (f" {gaps}" if gaps else ""))


if __name__ == "__main__":
    main()

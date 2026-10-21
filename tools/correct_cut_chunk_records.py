"""Count the records of the artefact's cut chunk that the answer model got whole in the two
id-based scores, and say exactly what was changed.

    python correct_cut_chunk_records.py <run folder> [--write]

Without --write it only prints what it would change and what it checked. Numbers and counts
only: no question, answer, context, id or gold is printed. It starts from eval_results.jsonl as
the evaluation wrote it, which it keeps as eval_results.as_recorded.jsonl on the first write and
never changes.

Rule "cut-chunk-records/1".
  1. A record counts as retrieved when the answer model got its text whole. The harness's cut
     (char_budget.cut_at_budget) hands over the start of the text that crosses the limit, and the
     row's context_ids hold only the records of the texts handed over whole.
  2. artefact_v4 only: a chunk's text is its records as JSON, one a line, in the order of its ids
     (artefact_v4._hand_over, artefact_v2._resolve_chunk). In the cut chunk, every line that ends
     before the cut is a record the answer model got whole; a chunk that is part of one record's
     text has none.
  3. context_recall_id and context_precision_id are calculated again by RAGAS's own
     IDBasedContextRecall and IDBasedContextPrecision on the row's context_ids with those records
     added, against the questions file's citations; every other score and every other file stays
     as it is.
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

RULE = "cut-chunk-records/1"
HIS_WORDS = ("\"oh, wait, yes, how does that change the results?\" · \"but this is the honest thing to "
             "update, yes?\" · \"doit\" (2026-10-21)")
SCRIPT = "correct_cut_chunk_records.py"
METRICS = ("context_recall_id", "context_precision_id")


def sha(path):
    """The sha256 of a file with the line ends git holds (LF)."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def rows(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def whole_before_cut(row):
    """The records of the cut chunk whose line ends before the cut, in order."""
    cut = row["meta"]["char_budget"].get("boundary")
    if not cut:
        return []
    kept, ids = row["contexts"][-1], [str(i) for i in row["meta"]["chunk_ids"][-1]]
    if len(kept) != cut["chars_kept"]:
        raise SystemExit(f"{row['id']}: the cut text is not chars_kept long")
    if not kept.startswith("{"):
        return []
    got = list(dict.fromkeys(str(json.loads(line)["id"]) for line in kept.split("\n")[:-1]))
    if got != ids[:len(got)]:
        raise SystemExit(f"{row['id']}: the cut chunk's lines are not its records in the order of its ids")
    return got


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
    from harness.questions import load_questions
    from ragas.dataset_schema import SingleTurnSample
    from ragas.metrics import IDBasedContextPrecision, IDBasedContextRecall
    code = {**provenance.code_version(), **{k: v for k, v in provenance.code_state().items()
                                             if k != "diff"}}

    man = json.loads((d / "run_manifest.json").read_text(encoding="utf-8"))
    if man["arm"] != "artefact_v4":
        raise SystemExit("this correction is for the artefact_v4 folder only")
    data = json.loads((d / "corrections.json").read_text(encoding="utf-8"))
    earlier = [c for c in data["corrections"] if (c.get("rule") or {}).get("id") != RULE]
    kept = d / "eval_results.as_recorded.jsonl"
    src = kept if kept.exists() else d / "eval_results.jsonl"
    results = rows(src)
    cites = {q.id: [str(c) for c in q.citations] for q in load_questions(Path(man["questions_file"]).exists()
                                                                          and man["questions_file"]
                                                                          or repo / "data/questions.jsonl")}
    metric = {"context_recall_id": IDBasedContextRecall(), "context_precision_id": IDBasedContextPrecision()}

    def score(name, got, ref):
        return asyncio.run(metric[name]._single_turn_ascore(
            SingleTurnSample(retrieved_context_ids=got, reference_context_ids=ref), None))

    stored = {(r["question_id"], r["metric"]): r for r in results if r["metric"] in METRICS}
    changes, checks, reproduced, added_in, added = [], [], 0, 0, 0
    new = {}
    for row in rows(d / "arm_outputs.jsonl"):
        old = [str(i) for i in row["context_ids"]]
        more = [i for i in whole_before_cut(row) if i not in old]
        added += len(more)
        added_in += bool(more)
        for name in METRICS:
            before = score(name, old, cites[row["id"]])
            reproduced += before == stored[(row["id"], name)]["value"]
            after = score(name, old + more, cites[row["id"]])
            new[(row["id"], name)] = after
            if after != before:
                changes.append({"where": "eval_results.jsonl", "question_id": row["id"], "field": name,
                                "recorded": before, "corrected": after, "records_added": more})
    checks.append({"what": "RAGAS on the row's context_ids gives the stored score again", "holds":
                   reproduced == len(stored), "looked_at": len(stored)})
    checks.append({"what": "each cut chunk's lines are its records in the order of its ids", "holds": True,
                   "looked_at": sum(1 for r in rows(d / "arm_outputs.jsonl")
                                    if r["meta"]["char_budget"].get("boundary"))})

    print(f"{d.name}; from {src.name}")
    for c in checks:
        print(f"  [{'ok' if c['holds'] else 'NO'}] {c['what']} | {c['looked_at']} looked at")
    for name in METRICS:
        ch = [c for c in changes if c["field"] == name]
        up = [c["corrected"] - c["recorded"] for c in ch if c["corrected"] > c["recorded"]]
        down = [c["recorded"] - c["corrected"] for c in ch if c["corrected"] < c["recorded"]]
        print(f"  {name}: up on {len(up)}, down on {len(down)}, the same on {100 - len(ch)}")
    print(f"  records added: {added}, in {added_in} questions")
    if not all(c["holds"] for c in checks):
        raise SystemExit("a check does not hold: nothing is written")
    if not args.write:
        print("  (nothing written; --write does it)")
        return

    if not kept.exists():
        shutil.copy2(d / "eval_results.jsonl", kept)
    before_sha = sha(src)
    for r in results:
        if (r["question_id"], r["metric"]) in new:
            r["value"] = new[(r["question_id"], r["metric"])]
    tmp = d / "eval_results.jsonl.tmp"
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in results), encoding="utf-8")
    tmp.replace(d / "eval_results.jsonl")
    if Path(__file__).resolve() != (d / SCRIPT).resolve():
        shutil.copy2(__file__, d / SCRIPT)
    entry = {
        "made_at": datetime.now(timezone.utc).isoformat(),
        "ordered_by": HIS_WORDS,
        "what_happened": "The two id-based scores were calculated on the row's context_ids, which hold "
                         "only the records of the texts handed over whole. The artefact's text is a "
                         "chunk of one or more records, so the records of the cut chunk whose text the "
                         "answer model got whole were not counted.",
        "rule": {"id": RULE, "text": __doc__.split(f'Rule "{RULE}".')[1].strip()},
        "not_changed_and_worth_knowing": [
            "No answer, context, context_ids, other score or judge call is changed; arm_outputs.jsonl "
            "is as it was. Lucene and vector are not changed: their cut text is one record, and the "
            "answer model got only its start."],
        "changes": changes,
        "checks": checks,
        "files": {"eval_results.jsonl": {"sha256_before": before_sha, "sha256_corrected": sha(d / "eval_results.jsonl")}},
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

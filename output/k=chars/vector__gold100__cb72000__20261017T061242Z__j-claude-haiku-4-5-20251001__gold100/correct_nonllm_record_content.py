"""Calculate the two non-LLM context scores again, record content against record content, and say
exactly what was changed.

    python correct_nonllm_record_content.py <run folder> [--write] [--method string-leaves|record-text]

Without --write it only prints what it would change and what it checked. Numbers and counts
only: no question, answer, context, id or gold is printed. It starts from eval_results.jsonl as it
stands, which it keeps as eval_results.as_recorded.jsonl on the first write if that file is not
there yet.

Before anything is changed it finds the method that made the stored scores: each method in
BEFORE is run on the folder's own inputs, and the one that gives every stored score again is
named in the corrections entry. When no method gives every stored score again, nothing is
written. A folder with no run_manifest.json (a folder that judged a run's answers again, beside
the run) reads the run's manifest through its eval_manifest.json's source_run, and must hold the
run's own answers and texts.

Rule "nonllm-record-content/1".
  1. The evaluation compared gold records and handed-over texts in two forms that are not the
     same. The code that scored the three final runs on the hundred wrote each gold record as all
     of its string values joined by spaces, while every arm hands its records over in HERB's own
     form (harness.record_text), with ids, labels, dates and names around the content, so the
     same record did not match itself as a string. The code that scored the runs on the 715
     answerable questions wrote each gold record in record_text form, so the ids, labels, dates
     and names of the form were counted in how alike two records are.
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
             "the correct fucking data\" (2026-10-25) · \"do the fucking non-llm, dude, why is this a "
             "question\" (2026-10-25)")
# the methods the evaluation has scored the two non-LLM scores with, before this rule
BEFORE = {
    "string-leaves": "each gold record as all of its string values joined by spaces, against the texts "
                     "as handed over (eval/ragas.py at the commits that scored the three final runs on "
                     "the hundred)",
    "record-text": "each gold record in record_text form, against the texts as handed over, a text of "
                   "several records (meta chunk_ids) cut into their record_text forms (eval/ragas.py as "
                   "it stood uncommitted on 2026-10-23 and 2026-10-24, when the runs on the 715 "
                   "answerable questions were scored)",
}
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


def cut_whole_records(contexts, id_lists, record_texts) -> list:
    """The texts as the record-text method cut them: a text of several records into their
    record_text forms, joined by a blank line, or the start of that join where the character
    budget cut it; a text of one record, or of a part of one, as it is."""
    if id_lists is None:
        return list(contexts)
    if len(id_lists) != len(contexts):
        raise ValueError(f"{len(contexts)} texts but {len(id_lists)} id lists")
    out = []
    for text, ids in zip(contexts, id_lists):
        if len(ids) < 2:
            out.append(text)
            continue
        pieces = [record_texts(str(i)) for i in ids]
        if not "\n\n".join(pieces).startswith(text):
            raise ValueError("a handed-over text is not its records joined by a blank line")
        at = 0
        for piece in pieces:
            if at >= len(text):
                break
            out.append(text[at:at + len(piece)])
            at += len(piece) + 2
    return out


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    warnings.filterwarnings("ignore")
    p = argparse.ArgumentParser()
    p.add_argument("folder")
    p.add_argument("--repo", help="the repository whose harness reads the folder (default: three "
                                  "folders up from it)")
    p.add_argument("--write", action="store_true")
    p.add_argument("--method", choices=sorted(BEFORE),
                   help="check only this method of BEFORE, when it is known which one made the scores")
    args = p.parse_args()
    d = Path(args.folder).resolve()
    repo = Path(args.repo).resolve() if args.repo else d.parents[2]
    sys.path[:0] = [str(repo / "prod"), str(repo / "test")]
    from harness import fields, provenance
    from harness.orchestrator import DEFAULT_CORPUS
    from harness.questions import load_questions
    from harness.record_text import record_content, record_text
    from eval.ragas import contents_handed_over, corpus_records
    from ragas.dataset_schema import SingleTurnSample
    from ragas.metrics import NonLLMContextPrecisionWithReference, NonLLMContextRecall, NonLLMStringSimilarity
    code = {**provenance.code_version(), **{k: v for k, v in provenance.code_state().items()
                                             if k != "diff"}}

    checks = []
    source = None
    if (d / "run_manifest.json").exists():
        man = json.loads((d / "run_manifest.json").read_text(encoding="utf-8"))
    else:
        # a folder beside a run, which judged the run's answers again: the run's manifest says
        # what was read
        ev = json.loads((d / "eval_manifest.json").read_text(encoding="utf-8"))
        source = (repo / Path(ev["source_run"].replace("\\", "/"))).resolve()
        man = json.loads((source / "run_manifest.json").read_text(encoding="utf-8"))
    data = (json.loads((d / "corrections.json").read_text(encoding="utf-8"))
            if (d / "corrections.json").exists() else {"corrections": []})
    earlier = [c for c in data["corrections"] if (c.get("rule") or {}).get("id") != RULE]
    kept = d / "eval_results.as_recorded.jsonl"
    src = d / "eval_results.jsonl"
    results = rows(src)
    qfile = Path(man["questions_file"]) if Path(man["questions_file"]).exists() else repo / "data/questions.jsonl"
    checks.append({"what": "the questions file read here is the one the run read (its sha256 in the run "
                           "manifest's inputs)",
                   "holds": hashlib.sha256(qfile.read_bytes()).hexdigest() == man["inputs"]["questions_sha256"],
                   "looked_at": 1})
    checks.append({"what": "the corpus read here is the one the run read (its digest in the run "
                           "manifest's inputs)",
                   "holds": provenance.tree_digest(DEFAULT_CORPUS) == man["inputs"]["corpus"], "looked_at": 1})
    cites = {q.id: [str(c) for c in q.citations] for q in load_questions(qfile)}
    records = corpus_records(DEFAULT_CORPUS)
    whole_text = {}

    def text_of(i):
        if i not in whole_text:
            whole_text[i] = record_text(*records[i])
        return whole_text[i]

    pairs = {}

    class Similarity(NonLLMStringSimilarity):
        """RAGAS's own string similarity, called without its callback group and usage event, which
        take most of the time and change no value; a pair already compared in the row is not
        compared again."""

        async def single_turn_ascore(self, sample, callbacks=None, timeout=None):
            key = (sample.reference, sample.response)
            if key not in pairs:
                pairs[key] = await self._single_turn_ascore(sample, None)
            return pairs[key]

    metric = {"context_recall_nonllm": NonLLMContextRecall(),
              "context_precision_nonllm": NonLLMContextPrecisionWithReference()}
    # each score's own default similarity (Levenshtein), put in its place
    for name, m in metric.items():
        held = "_distance_measure" if name == "context_recall_nonllm" else "distance_measure"
        default = getattr(m, held)
        if type(default) is not NonLLMStringSimilarity or default.distance_measure != Similarity().distance_measure:
            raise SystemExit(f"{name}: RAGAS's default similarity is not the one replaced here")
        setattr(m, held, Similarity())

    def score(name, retrieved, refs):
        return asyncio.run(metric[name]._single_turn_ascore(
            SingleTurnSample(retrieved_contexts=retrieved, reference_contexts=refs or None), None))

    def score_or_none(name, retrieved, refs):
        try:
            return score(name, retrieved, refs)
        except (AssertionError, ValueError):
            return None

    stored = {(r["question_id"], r["metric"]): r for r in results
              if r["metric"] in METRICS and r.get("status") == "ok"}
    arm_rows = rows(d / "arm_outputs.jsonl")
    if source is not None:
        read = lambda r: (r["contexts"], r["context_ids"], (r.get("meta") or {}).get("chunk_ids"),  # noqa: E731
                          (r.get("meta") or {}).get("char_budget"))
        theirs = {r["id"]: read(r) for r in rows(source / "arm_outputs.jsonl")}
        checks.append({"what": f"the texts and records handed over here are those of the run beside it "
                               f"({source.name})",
                       "holds": {r["id"]: read(r) for r in arm_rows} == theirs, "looked_at": len(arm_rows)})
    changes, scored, texts_in, records_out, several = [], 0, 0, 0, False
    methods = [args.method] if args.method else list(BEFORE)
    gave_again = {m: {name: 0 for name in METRICS} for m in methods}
    not_again = {m: [] for m in methods}
    new = {}
    for row in arm_rows:
        pairs.clear()
        contexts = list(row["contexts"] or [])
        contents = contents_handed_over(contexts, row["context_ids"], row.get("meta"), records)
        texts_in += len(contexts)
        records_out += len(contents)
        chunk_ids = (row.get("meta") or {}).get("chunk_ids")
        several = several or any(len(ids) > 1 for ids in chunk_ids or [])
        ids = [c for c in cites[row["id"]] if c in records]
        try:
            cut = cut_whole_records(contexts, chunk_ids, text_of)
        except ValueError:
            cut = None
        befores = {"string-leaves": lambda: (contexts, [as_evaluated(records[c][1]) for c in ids]),
                   "record-text": lambda: (cut, [text_of(c) for c in ids])}
        for name in METRICS:
            if (row["id"], name) not in stored:
                continue
            scored += 1
            recorded = stored[(row["id"], name)]["value"]
            for m in methods:
                retrieved, refs = befores[m]()
                before = score_or_none(name, retrieved, refs) if retrieved is not None else None
                if before is not None and abs(before - recorded) < 1e-12:
                    gave_again[m][name] += 1
                else:
                    not_again[m].append({"question_id": row["id"], "field": name, "recorded": recorded,
                                         "by_the_method": before})
            after = score(name, contents, [record_content(*records[c]) for c in ids])
            new[(row["id"], name)] = after
            if after != recorded:
                changes.append({"where": "eval_results.jsonl", "question_id": row["id"], "field": name,
                                "recorded": recorded, "corrected": after})
    n_of = {name: sum(k[1] == name for k in stored) for name in METRICS}
    found = [m for m in methods if gave_again[m] == n_of]
    for m in methods:
        print(f"  before-method {m}: gives the stored score again on "
              + ", ".join(f"{gave_again[m][name]} of {n_of[name]} {name}" for name in METRICS))
    check = {"what": ("the method " + args.method if args.method else "one method in BEFORE")
                     + " gives every stored score again" + (f" ({found[0]})" if found else " (none does)"),
             "holds": bool(found), "looked_at": len(stored)}
    if args.method and not found:
        check["not_given_again"] = not_again[args.method]
    checks.append(check)
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
    for m in methods:
        if not_again[m] and (args.method or not found):
            print(f"  not given again by {m}: "
                  + ", ".join(f"{sum(c['field'] == name for c in not_again[m])} {name}" for name in METRICS))
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
        "what_happened": ({"string-leaves": "The two non-LLM context scores compared each gold record, "
                                            "written as its string values joined by spaces, with the "
                                            "texts handed over, written in HERB's own form, so the same "
                                            "record did not match itself",
                           "record-text": "The two non-LLM context scores compared each gold record, "
                                          "written in HERB's own form, with the texts handed over, so the "
                                          "ids, labels, dates and names of the form were counted in how "
                                          "alike two records are"}[found[0]]
                          + ("; and they compared the artefact's whole chunks with single records, which "
                             "never match." if several and found[0] == "string-leaves" else ".")),
        "before": {"method": found[0], "what_it_did": BEFORE[found[0]],
                   "gives_the_stored_scores_again": {m: dict(gave_again[m]) for m in methods},
                   "stored_scores": dict(n_of)},
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

"""Mark for judging again each score cell of a run whose answer a judge time limit below the final runs' limit
picked: a cell cut at a lower limit and answered by a later start under such a limit; say exactly what was
changed.

    python tools/correct_judge_time_limit.py <run folder> [--write]

Without --write it only prints what it would change and what it checked. The final runs judged with a time limit
of 1,280 s per judge call and one try (RAGAS_JUDGE_TIMEOUT_S=1280 in each of their judge starts). A start with a
lower limit cuts each call whose answer takes longer, and a later start under the same limit keeps only an answer
that fits in it, so the cell's value is not one that the final runs' method gives. The correction starts from
eval_results.jsonl as it stands, and keeps it as recorded as eval_results.as_recorded.jsonl on the first write of
any correction, never changed after.

Rule "judge-time-limit/1".
  1. A cell is a row of eval_results.jsonl with status ok. Its answer is the start that gave its value
     (components.usage.eval_leg) and the cell's judge call records of that start in eval_calls.jsonl (the chat
     records with its question_id, its metric as their score and that eval_leg); each call record holds its own
     time limit (timeout_s). Its cuts are the records of eval_failures.jsonl with its question_id and its metric
     whose error is a call cut at its time limit (TimeoutExpired); a cut's limit is the time limit of the cell's
     call records of the cut's start that did not answer, else the time limit of that start's settings in
     eval_manifest.json (judge_timeout_s).
  2. The cell is judged again when a cut of it had a limit below 1,280 s and the call records of its answer ran
     with a limit below 1,280 s. A cell whose answer ran with 1,280 s, or that was never cut, stands.
  3. Its row in eval_results.jsonl gets status "judge-time-limit/1" and keeps its value and components. A start
     of the run drops each row whose status is not ok and judges the cell again (eval.ragas); the start that
     judges these runs with RAGAS_JUDGE_TIMEOUT_S=1280 and one try, the final runs' setting. This correction does
     not start it.
  4. The call records of the answer the cell had stay in eval_calls.jsonl as recorded, and count in the run's
     judging as every judge call that answered counts, the cells that a later start dropped included.
  5. No call record, failure record, judge leg, answer or other cell changes.
"""
import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RULE = "judge-time-limit/1"
SCRIPT = "correct_judge_time_limit.py"
FINAL_LIMIT_S = 1280.0
HIS_WORDS = ("\"go ahead and do this \"for real\"\" (2026-10-31, on the redo) · \"So, what did you not do now "
             "then. It's obvious some thing we're not done correctly here.\" (2026-10-31)")
REPO = Path(__file__).resolve().parents[1]
# the arms are in prod/ and test/: FIELDS.md takes an arm's own words from its file
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def below(limit):
    return limit is not None and float(limit) < FINAL_LIMIT_S


def corrected(d):
    """The rows of eval_results.jsonl as rule 1 to 3 leave them (None when nothing changes), the changes and the
    checks."""
    raw = (d / "eval_results.jsonl").read_text(encoding="utf-8").splitlines(keepends=True)
    lines = [line for line in raw if line.strip()]
    results = [json.loads(line) for line in lines]
    calls = [c for c in rows(d / "eval_calls.jsonl") if c.get("kind") == "chat"]
    failures = rows(d / "eval_failures.jsonl") if (d / "eval_failures.jsonl").exists() else []
    ev = json.loads((d / "eval_manifest.json").read_text(encoding="utf-8"))
    start_limit = {(leg.get("settings") or {}).get("started_at"): (leg.get("settings") or {}).get("judge_timeout_s")
                   for leg in ev.get("judge_legs") or []}
    of_cell, cuts_of = {}, {}
    for c in calls:
        of_cell.setdefault((c.get("question_id"), c.get("score")), []).append(c)
    for f in failures:
        if "TimeoutExpired" in str(f.get("error")):
            cuts_of.setdefault((f["question_id"], f["metric"]), []).append(f)
    changes, out, standing, no_limit = [], [], {"answered with 1,280 s": 0, "cut only at 1,280 s": 0}, 0
    for line, r in zip(lines, results):
        key = (r["question_id"], r["metric"])
        if r["status"] != "ok" or key not in cuts_of:
            out.append(line)
            continue
        mine = of_cell.get(key, [])
        start = r["components"]["usage"]["eval_leg"]
        answer = [c for c in mine if c["eval_leg"] == start]
        answer_limits = {c.get("timeout_s") for c in answer}
        if not answer or not all(c.get("ok") for c in answer) or len(answer_limits) != 1 or None in answer_limits:
            sys.exit(f"{d.name} {key}: the call records of its answer are not as rule 1 reads them")
        cuts = []
        for f in cuts_of[key]:
            limits = sorted({c.get("timeout_s") for c in mine if c["eval_leg"] == f["eval_leg"] and not c.get("ok")}
                            - {None})
            if not limits and start_limit.get(f["eval_leg"]) is not None:
                limits = [start_limit[f["eval_leg"]]]
            no_limit += not limits
            cuts.append({"start": f["eval_leg"], "failed_at": f.get("failed_at"), "time_limits_s": limits})
        answer_limit = next(iter(answer_limits))
        if below(answer_limit) and any(c["time_limits_s"] and all(below(x) for x in c["time_limits_s"]) for c in cuts):
            out.append(json.dumps(dict(r, status=RULE), ensure_ascii=False) + "\n")
            changes.append({"question_id": r["question_id"], "metric": r["metric"], "value_recorded": r["value"],
                            "answer": {"start": start, "time_limit_s": answer_limit, "judge_calls": len(answer)},
                            "cuts": cuts})
        else:
            standing["answered with 1,280 s" if not below(answer_limit) else "cut only at 1,280 s"] += 1
            out.append(line)
    checks = [
        {"what": "cells cut at least once (TimeoutExpired)", "looked_at": "eval_results.jsonl, eval_failures.jsonl",
         "count": sum(1 for r in results if r["status"] == "ok" and (r["question_id"], r["metric"]) in cuts_of),
         "holds": True},
        {"what": "cells that stand although cut, by why", "looked_at": "eval_calls.jsonl", "count": standing,
         "holds": True},
        {"what": "cuts whose time limit no record names", "looked_at": "eval_calls.jsonl, eval_manifest.json",
         "count": no_limit, "holds": no_limit == 0},
        {"what": "rows other than the changed ones kept byte for byte", "looked_at": "eval_results.jsonl",
         "count": sum(1 for a, b in zip(lines, out) if a == b), "holds":
             sum(1 for a, b in zip(lines, out) if a != b) == len(changes) and len(out) == len(lines)},
    ]
    return (out if changes else None), changes, checks, raw


def main():
    p = argparse.ArgumentParser()
    p.add_argument("run")
    p.add_argument("--write", action="store_true")
    p.add_argument("--ordered-by", default=HIS_WORDS, help="his words that ordered this correction")
    args = p.parse_args()
    d = Path(args.run)
    new, changes, checks, raw = corrected(d)
    by_metric = {}
    for c in changes:
        by_metric[c["metric"]] = by_metric.get(c["metric"], 0) + 1
    print(f"{d.name}: cells to judge again {len(changes)} {by_metric}")
    for c in checks:
        print(f"  check {'holds' if c['holds'] else 'DOES NOT HOLD'}: {c['what']}: {json.dumps(c['count'])}")
    if new is None:
        print("nothing to correct")
        return
    if not all(c["holds"] for c in checks):
        sys.exit("  a check does not hold; nothing written")
    if not args.write:
        print("  (nothing written; --write does it)")
        return
    path = d / "eval_results.jsonl"
    before = sha(path)
    kept = d / "eval_results.as_recorded.jsonl"
    if not kept.exists():
        shutil.copy2(path, kept)
    crlf = any(line.endswith("\r\n") for line in raw)
    text = "".join(line if line.endswith("\n") else line + "\n" for line in new)
    if crlf:
        text = "".join(line if line.endswith("\r\n") else line[:-1] + "\r\n" for line in text.splitlines(keepends=True))
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    tmp.replace(path)
    if Path(__file__).resolve() != (d / SCRIPT).resolve():
        shutil.copy2(__file__, d / SCRIPT)
    earlier = (json.loads((d / "corrections.json").read_text(encoding="utf-8"))["corrections"]
               if (d / "corrections.json").exists() else [])
    entry = {
        "made_at": datetime.now(timezone.utc).isoformat(),
        "ordered_by": args.ordered_by,
        "what_happened": (f"The run's judge starts ran with the code's judge time limit of 120 s, where the final "
                          f"runs ran with 1,280 s. {len(changes)} cells were cut at 120 s and answered by a later "
                          "start under 120 s, which keeps only an answer that fits in 120 s; their rows are marked "
                          "so that a start with 1,280 s judges them again."),
        "rule": {"id": RULE, "text": __doc__.split(f'Rule "{RULE}".', 1)[1].strip()},
        "not_changed_and_worth_knowing": [
            "The values the cells had are in eval_results.as_recorded.jsonl and in each change.",
            "The call records of the answers the cells had stay in eval_calls.jsonl and count in the judging.",
            "No call record, failure record, judge leg, answer or other cell is changed.",
        ],
        "changes": changes,
        "checks": checks,
        "files": {"eval_results.jsonl": {"sha256_before": before, "sha256_corrected": sha(path),
                                         "as_recorded": kept.name}},
        "script": f"{SCRIPT}, in this folder",
    }
    (d / "corrections.json").write_text(json.dumps({"corrections": earlier + [entry]},
                                                   ensure_ascii=False, indent=2), encoding="utf-8")
    from harness import fields
    fields.write(d, stamp_files=True)
    print(f"written: {len(changes)} rows of eval_results.jsonl; corrections.json, {SCRIPT}")


if __name__ == "__main__":
    main()

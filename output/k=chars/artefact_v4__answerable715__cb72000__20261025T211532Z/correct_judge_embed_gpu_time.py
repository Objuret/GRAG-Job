"""Give each of RAGAS's own embedding requests that a run's judging made on the CPU the time the same
request takes on the desktop's graphics card; say exactly what was changed.

    python tools/correct_judge_embed_gpu_time.py <run folder> [<run folder> ...] <gpu times json> [--write]

The GPU times are measured by tools/measure_gpu_judge_embed_times.py with the harness's own request
function (harness.embed._embed_request) and settings, on the same texts in the same input type, one
request after the other in a warm process, with HERB_EMBED_DEVICE=cuda. Without --write it only prints
what it would change. It keeps the records as recorded as eval_calls.as_recorded.jsonl on the first write
of any correction, never changed after.

Rule "judge-embed-gpu-time/1".
  1. An embed record of eval_calls.jsonl that says device cpu is corrected; a record that says cuda ran
     on the graphics card and stays as recorded. The evidence names exactly the records of rule 1, by
     their line, question, scoring start and seq, with the same number of texts and the same tokens.
  2. Each record of rule 1 gets its GPU seconds as encode_s and device cuda. No vector, score, judge
     call or other time changes.
"""
import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RULE = "judge-embed-gpu-time/1"
SCRIPT = "correct_judge_embed_gpu_time.py"
EVIDENCE = "judge_embed_gpu_times.json"
HIS_WORDS = ("\"the task is done when the workbook is updated with ... i want the same methods for them, embeddings "
             "via gpu, etc etc..\" (2026-10-27)")
REPO = Path(__file__).resolve().parents[1]
# the arms are in prod/ and test/: FIELDS.md takes an arm's own words from its file
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def correct(d, times, evidence, write):
    path = d / "eval_calls.jsonl"
    lines = path.read_bytes().split(b"\n")
    mine = {t["line"]: t for t in times["requests"] if t["run"] == d.name}
    changes, before_s, after_s, done = [], 0.0, 0.0, set()
    for n, line in enumerate(lines):
        if b'"kind": "embed"' not in line:
            continue
        c = json.loads(line)
        if c.get("kind") != "embed" or c.get("device") != "cpu":
            continue
        t = mine.get(n)
        # rule 1: the evidence names exactly this record
        if (t is None or (t["question_id"], t["eval_leg"], t["seq"]) != (c.get("question_id"), c.get("eval_leg"), c.get("seq"))
                or t["texts"] != len(c["texts"]) or t["recorded_tokens_in"] != c["tokens_in"]
                or t["tokens_in"] != c["tokens_in"] or t["recorded_encode_s"] != c["encode_s"]):
            raise SystemExit(f"{d.name} line {n}: the GPU times do not name this CPU record exactly")
        where = f"eval_calls.jsonl line {n} ({c.get('question_id')})"
        changes.append({"where": where, "field": "encode_s", "recorded": c["encode_s"], "corrected": t["encode_s"]})
        changes.append({"where": where, "field": "device", "recorded": "cpu", "corrected": "cuda"})
        before_s += c["encode_s"]
        after_s += t["encode_s"]
        c["encode_s"], c["device"] = t["encode_s"], "cuda"
        lines[n] = json.dumps(c, ensure_ascii=False, default=repr).encode("utf-8")
        done.add(n)
    if set(mine) != done:
        raise SystemExit(f"{d.name}: the GPU times name records that are not CPU embed records of eval_calls.jsonl")
    print(f"{d.name}: {len(done)} RAGAS embedding requests, {before_s:.1f} s on the CPU, {after_s:.1f} s on the GPU")
    if not write or not done:
        return
    before = sha(path)
    kept = d / "eval_calls.as_recorded.jsonl"
    if not kept.exists():
        shutil.copy2(path, kept)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(b"\n".join(lines))
    tmp.replace(path)
    shutil.copy2(evidence, d / EVIDENCE)
    if Path(__file__).resolve() != (d / SCRIPT).resolve():
        shutil.copy2(__file__, d / SCRIPT)
    earlier = (json.loads((d / "corrections.json").read_text(encoding="utf-8"))["corrections"]
               if (d / "corrections.json").exists() else [])
    entry = {
        "made_at": datetime.now(timezone.utc).isoformat(),
        "ordered_by": HIS_WORDS,
        "what_happened": ("RAGAS embedded answers and references on the CPU while judging. Each such request's time is "
                          "the time the same request takes on the desktop's GTX 1080 Ti; the requests the judging made "
                          "on that card keep their recorded times."),
        "rule": {"id": RULE, "text": __doc__.split(f'Rule "{RULE}".', 1)[1].strip()},
        "not_changed_and_worth_knowing": [
            "The GPU times were measured one request after the other in a warm process; each record's wait for the "
            "embedder's lock (lock_wait_s) stays as recorded and is not part of the judging's time.",
        ],
        "changes": changes,
        "evidence": {"file": EVIDENCE, "sha256": sha(d / EVIDENCE),
                     "what": "per embedding request of the six final runs' judging made on the CPU: its seconds on "
                             "the graphics card, its recorded seconds, texts and tokens"},
        "files": {"eval_calls.jsonl": {"sha256_before": before, "sha256_corrected": sha(path), "as_recorded": kept.name}},
        "script": f"{SCRIPT}, in this folder",
    }
    (d / "corrections.json").write_text(json.dumps({"corrections": earlier + [entry]}, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    from harness import fields
    fields.write(d, stamp_files=True)
    print(f"written: {len(changes)} changes; corrections.json, {EVIDENCE}, {SCRIPT}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("paths", nargs="+")
    p.add_argument("--write", action="store_true")
    args = p.parse_args()
    *runs, evidence = args.paths
    times = json.loads(Path(evidence).read_text(encoding="utf-8"))
    if times["measured"]["device"] != "cuda":
        raise SystemExit("the evidence was not measured on the graphics card")
    for r in runs:
        correct(Path(r).resolve(), times, evidence, args.write)


if __name__ == "__main__":
    main()

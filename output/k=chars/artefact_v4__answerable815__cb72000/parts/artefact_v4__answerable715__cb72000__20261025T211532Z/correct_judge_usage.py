"""Give a judge call whose record holds fewer tokens than its own reply the counts of the whole call, and
count its scoring start's entry, judge_usage and its score cell again with them; say exactly what was
changed.

    python tools/correct_judge_usage.py <run folder> [--transcripts <counts json>] [--write]

Without --write it only prints what it would change. It keeps each file as recorded as
<name>.as_recorded.<ext> on the first write of any correction, never changed after. A changed line keeps
the line end it had.

Rule "judge-usage/1".
  1. A judge call record of eval_calls.jsonl that answered is corrected when the tokens it holds are
     fewer than its reply's own counts per model: the reply's usage field held 0 tokens, or only some
     of the requests the CLI made in the call.
  2. Its counts are the reply's counts per model (modelUsage) for the model it names, counted as the
     harness counts the usage field: tokens in = inputTokens + cacheCreationInputTokens +
     cacheReadInputTokens, cached tokens in = cacheReadInputTokens, tokens out = outputTokens. Where
     the transcript counts given hold the call's session, they must be the same.
  3. They go into the call record's usage. The entry of its scoring start in eval_manifest.json
     (judge_legs, the one whose settings.started_at is the record's eval_leg) and judge_usage get the
     difference added to tokens_in, cached_input_tokens and tokens_out; so does the score cell of
     eval_results.jsonl the call belongs to (the same question, score and scoring start), in
     components.usage. No score, answer, time or other count changes.
"""
import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RULE = "judge-usage/1"
SCRIPT = "correct_judge_usage.py"
HIS_WORDS = ("\"make sure it's all correctly calculated, no sloppy shit or lazy\" (2026-10-27) · "
             "\"ok, and this workbook is now truly correct?\" (2026-10-28)")
KEYS = ("tokens_in", "cached_input_tokens", "tokens_out")
REPO = Path(__file__).resolve().parents[1]
# the arms are in prod/ and test/: FIELDS.md takes an arm's own words from its file
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def counted(m):
    cached = int(m.get("cacheReadInputTokens") or 0)
    return {"prompt_tokens": int(m.get("inputTokens") or 0) + int(m.get("cacheCreationInputTokens") or 0) + cached,
            "completion_tokens": int(m.get("outputTokens") or 0), "cached_input_tokens": cached}


def from_transcript(u):
    cached = int(u.get("cache_read_input_tokens") or 0)
    return {"prompt_tokens": int(u.get("input_tokens") or 0) + int(u.get("cache_creation_input_tokens") or 0) + cached,
            "completion_tokens": int(u.get("output_tokens") or 0), "cached_input_tokens": cached}


def dumped(obj, old_line):
    """A changed line, with the line end the old line had."""
    return json.dumps(obj, ensure_ascii=False, default=repr).encode("utf-8") + (b"\r" if old_line.endswith(b"\r") else b"")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("run")
    p.add_argument("--transcripts")
    p.add_argument("--write", action="store_true")
    args = p.parse_args()
    d = Path(args.run).resolve()
    transcripts = json.loads(Path(args.transcripts).read_text(encoding="utf-8")) if args.transcripts else {}
    calls_path, results_path, manifest_path = d / "eval_calls.jsonl", d / "eval_results.jsonl", d / "eval_manifest.json"
    lines = calls_path.read_bytes().split(b"\n")
    changes, found = [], []
    for n, line in enumerate(lines):
        if b'"kind": "chat"' not in line:
            continue
        c = json.loads(line)
        if not c.get("ok"):
            continue
        env = c.get("envelope") or {}
        per_model = env.get("modelUsage") or {}
        if c.get("model") not in per_model:
            continue
        whole, held = counted(per_model[c["model"]]), c.get("usage") or {}
        if not (int(held.get("prompt_tokens") or 0) < whole["prompt_tokens"]
                or int(held.get("completion_tokens") or 0) < whole["completion_tokens"]):
            continue
        if list(per_model) != [c["model"]]:
            raise SystemExit(f"line {n}: the reply's counts name {list(per_model)}, not only {c['model']}")
        seen = transcripts.get(env.get("session_id"))
        if seen is not None and from_transcript(seen) != whole:
            raise SystemExit(f"line {n}: the CLI's transcript of session {env.get('session_id')} does not hold the reply's counts")
        delta = {"tokens_in": whole["prompt_tokens"] - int(held.get("prompt_tokens") or 0),
                 "cached_input_tokens": whole["cached_input_tokens"] - int(held.get("cached_input_tokens") or 0),
                 "tokens_out": whole["completion_tokens"] - int(held.get("completion_tokens") or 0)}
        changes.append({"where": f"eval_calls.jsonl line {n} ({c.get('question_id')}, {c.get('score')})", "field": "usage",
                         "recorded": dict(held), "corrected": whole, "session_id": env.get("session_id"),
                         "checked_against_transcript": seen is not None})
        found.append((c, delta))
        c["usage"] = whole
        lines[n] = dumped(c, line)
    if not found:
        print(f"{d.name}: no judge call holds fewer tokens than its reply")
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = results_path.read_bytes().split(b"\n")
    for c, delta in found:
        legs = [leg for leg in manifest["judge_legs"] if (leg.get("settings") or {}).get("started_at") == c["eval_leg"]]
        if len(legs) != 1:
            raise SystemExit(f"{c.get('question_id')}: not one judging entry for scoring start {c['eval_leg']}")
        k = manifest["judge_legs"].index(legs[0])
        for where, usage in ((f"eval_manifest.json judge_legs[{k}].usage", legs[0]["usage"]),
                             ("eval_manifest.json judge_usage", manifest["judge_usage"])):
            for key in KEYS:
                changes.append({"where": where, "field": key, "recorded": usage[key], "corrected": usage[key] + delta[key]})
                usage[key] += delta[key]
        cells = []
        for n, line in enumerate(results):
            if not line.strip() or f'"{c["question_id"]}"'.encode() not in line:
                continue
            r = json.loads(line)
            if (r["question_id"], r["metric"], r["components"]["usage"].get("eval_leg")) == (c["question_id"], c["score"], c["eval_leg"]):
                cells.append((n, r))
        for n, r in cells:
            for key in KEYS:
                changes.append({"where": f"eval_results.jsonl line {n} ({r['question_id']}, {r['metric']})",
                                "field": f"components.usage.{key}", "recorded": r["components"]["usage"][key],
                                "corrected": r["components"]["usage"][key] + delta[key]})
                r["components"]["usage"][key] += delta[key]
            results[n] = dumped(r, results[n])
        print(f"{c.get('question_id')} {c.get('score')}: +{delta['tokens_in']} in, +{delta['tokens_out']} out; "
              f"scoring start entry {k}; score cells {len(cells)}")
    if not args.write:
        print("  (nothing written; --write does it)")
        return
    files = {}
    text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    if b"\r\n" in manifest_path.read_bytes():  # the manifest keeps the line ends it had
        text = text.replace("\n", "\r\n")
    for path, data in ((calls_path, b"\n".join(lines)), (results_path, b"\n".join(results)),
                       (manifest_path, text.encode("utf-8"))):
        before = sha(path)
        kept = path.with_name(path.stem + ".as_recorded" + path.suffix)
        if not kept.exists():
            shutil.copy2(path, kept)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
        files[path.name] = {"sha256_before": before, "sha256_corrected": sha(path), "as_recorded": kept.name}
    if Path(__file__).resolve() != (d / SCRIPT).resolve():
        shutil.copy2(__file__, d / SCRIPT)
    earlier = (json.loads((d / "corrections.json").read_text(encoding="utf-8"))["corrections"]
               if (d / "corrections.json").exists() else [])
    entry = {
        "made_at": datetime.now(timezone.utc).isoformat(),
        "ordered_by": HIS_WORDS,
        "what_happened": (f"{len(found)} judge call(s) held fewer tokens in their record than their own reply counts: "
                          "the reply's usage field held 0 tokens or only some of the requests the CLI made in the "
                          "call. The record, its scoring start's entry, judge_usage and its score cell now hold "
                          "the whole call's tokens."),
        "rule": {"id": RULE, "text": __doc__.split(f'Rule "{RULE}".', 1)[1].strip()},
        "not_changed_and_worth_knowing": ["No score, answer or time changes; the reply itself stays as the CLI wrote it."],
        "changes": changes,
        "checks": [{"what": "the call's counts are its own reply's counts for the one model it names, and the CLI's "
                            "transcript where the counts given hold it", "holds": True, "looked_at": len(found)}],
        "files": files,
        "script": f"{SCRIPT}, in this folder",
    }
    (d / "corrections.json").write_text(json.dumps({"corrections": earlier + [entry]}, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    from harness import fields
    fields.write(d, stamp_files=True)
    print(f"written: {len(changes)} changes; corrections.json, {SCRIPT}")


if __name__ == "__main__":
    main()

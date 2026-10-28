"""Give a judge call whose record holds fewer tokens than its own reply the counts of the whole call, and
count its scoring start's entry, judge_usage and its score cell again with them; say exactly what was
changed.

    python tools/correct_judge_usage.py <run folder> [--transcripts <counts json>] [--write]

Without --write it only prints what it would change. It keeps each file as recorded as
<name>.as_recorded.<ext> on the first write of any correction, never changed after. A changed line keeps
the line end it had.

Rule "judge-usage/2".
  1. A judge call record of eval_calls.jsonl that answered is corrected when the tokens it holds are
     fewer than its reply's own counts per model: the reply's usage field held 0 tokens, or only some
     of the requests the CLI made in the call.
  2. Its counts are the reply's counts per model (modelUsage) for the model it names, counted as the
     harness counts the usage field: tokens in = inputTokens + cacheCreationInputTokens +
     cacheReadInputTokens, cached tokens in = cacheReadInputTokens, tokens out = outputTokens. Where
     the transcript counts given hold the call's session, they must be the same.
  3. They go into the call record's usage. The score cell of eval_results.jsonl the call belongs to
     (the same question, score and scoring start) gets the difference between them and the record's
     tokens, in components.usage. The entry of its scoring start in eval_manifest.json (judge_legs, the
     one whose settings.started_at is the record's eval_leg) and judge_usage get the difference between
     them and what the harness counted for the call: the tokens of its usage field, or, where those
     were 0, the harness's own estimate of the prompt and of the reply (eval.ragas._estimate_tokens);
     cached tokens by the usage field. No score, answer, time or other count changes.
  4. In a folder where version 1 of this rule is written, which added the whole call to the entry and
     judge_usage also where the harness had counted its estimate, the entry and judge_usage of each
     call it corrected from a usage field of 0 tokens lose that estimate.
"""
import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RULE = "judge-usage/2"
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


def harness_count(c, held):
    """What the harness counted for a judge call (eval.ragas._claude_verdict): its usage field's tokens, or
    its own estimate of the prompt and of the reply where those were 0."""
    from eval import ragas
    return (int(held.get("prompt_tokens") or 0) or ragas._estimate_tokens(c["model"], c.get("prompt") or ""),
            int(held.get("completion_tokens") or 0) or ragas._estimate_tokens(c["model"], c.get("text") or ""))


def dumped(obj, old_line):
    """A changed line, with the line end the old line had."""
    return json.dumps(obj, ensure_ascii=False, default=repr).encode("utf-8") + (b"\r" if old_line.endswith(b"\r") else b"")


def entry_of(manifest, c):
    legs = [leg for leg in manifest["judge_legs"] if (leg.get("settings") or {}).get("started_at") == c["eval_leg"]]
    if len(legs) != 1:
        raise SystemExit(f"{c.get('question_id')}: not one judging entry for scoring start {c['eval_leg']}")
    return manifest["judge_legs"].index(legs[0]), legs[0]


def write_files(d, files_data):
    files = {}
    for path, data in files_data:
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
    return files


def manifest_bytes(manifest, path):
    text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    if b"\r\n" in path.read_bytes():  # the manifest keeps the line ends it had
        text = text.replace("\n", "\r\n")
    return text.encode("utf-8")


def add_entry(d, what, changes, checks, files):
    earlier = json.loads((d / "corrections.json").read_text(encoding="utf-8"))["corrections"] if (d / "corrections.json").exists() else []
    entry = {"made_at": datetime.now(timezone.utc).isoformat(), "ordered_by": HIS_WORDS, "what_happened": what,
             "rule": {"id": RULE, "text": __doc__.split(f'Rule "{RULE}".', 1)[1].strip()},
             "not_changed_and_worth_knowing": ["No score, answer or time changes; the reply itself stays as the CLI wrote it."],
             "changes": changes, "checks": checks, "files": files, "script": f"{SCRIPT}, in this folder"}
    (d / "corrections.json").write_text(json.dumps({"corrections": earlier + [entry]}, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    from harness import fields
    fields.write(d, stamp_files=True)


def undo_estimates(d, earlier, write):
    """Rule 4: the estimates that version 1 left in the entries and judge_usage."""
    v1 = [e for e in earlier if e["rule"]["id"] == "judge-usage/1"]
    zero = [ch for e in v1 for ch in e["changes"] if ch["field"] == "usage" and ch["where"].startswith("eval_calls.jsonl")
            and not int(ch["recorded"].get("prompt_tokens") or 0) and not int(ch["recorded"].get("completion_tokens") or 0)]
    lines = (d / "eval_calls.jsonl").read_bytes().split(b"\n")
    manifest_path = d / "eval_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    changes = []
    for ch in zero:
        n = int(ch["where"].split("line ")[1].split(" ")[0])
        c = json.loads(lines[n])
        est_in, est_out = harness_count(c, {})
        k, leg = entry_of(manifest, c)
        for where, usage in ((f"eval_manifest.json judge_legs[{k}].usage", leg["usage"]),
                             ("eval_manifest.json judge_usage", manifest["judge_usage"])):
            for key, est in (("tokens_in", est_in), ("tokens_out", est_out)):
                changes.append({"where": where, "field": key, "recorded": usage[key], "corrected": usage[key] - est,
                                "call": ch["where"]})
                usage[key] -= est
        print(f"{ch['where']}: the harness's estimate {est_in} in, {est_out} out out of scoring start entry {k} and judge_usage")
    if not zero:
        print(f"{d.name}: version 1 corrected no call from a usage field of 0 tokens")
        return
    if not write:
        print("  (nothing written; --write does it)")
        return
    files = write_files(d, [(manifest_path, manifest_bytes(manifest, manifest_path))])
    add_entry(d, (f"Version 1 of this rule added the whole of {len(zero)} judge call(s) whose usage field held 0 tokens to their "
                  "scoring start's entry and to judge_usage, where the harness had already counted its own estimate of "
                  "the call; that estimate is taken out (rule 4)."),
              changes, [{"what": "the estimate is the harness's own function on the call's prompt and reply as recorded",
                         "holds": True, "looked_at": len(zero)}], files)
    print(f"written: {len(changes)} changes; corrections.json, {SCRIPT}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("run")
    p.add_argument("--transcripts")
    p.add_argument("--write", action="store_true")
    args = p.parse_args()
    d = Path(args.run).resolve()
    earlier = json.loads((d / "corrections.json").read_text(encoding="utf-8"))["corrections"] if (d / "corrections.json").exists() else []
    if any(e["rule"]["id"] == RULE for e in earlier):
        raise SystemExit(f"{d.name}: {RULE} is already written")
    if any(e["rule"]["id"] == "judge-usage/1" for e in earlier):
        return undo_estimates(d, earlier, args.write)
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
        h_in, h_out = harness_count(c, held)
        cached = whole["cached_input_tokens"] - int(held.get("cached_input_tokens") or 0)
        cell = {"tokens_in": whole["prompt_tokens"] - int(held.get("prompt_tokens") or 0), "cached_input_tokens": cached,
                "tokens_out": whole["completion_tokens"] - int(held.get("completion_tokens") or 0)}
        entry = {"tokens_in": whole["prompt_tokens"] - h_in, "cached_input_tokens": cached,
                 "tokens_out": whole["completion_tokens"] - h_out}
        changes.append({"where": f"eval_calls.jsonl line {n} ({c.get('question_id')}, {c.get('score')})", "field": "usage",
                        "recorded": dict(held), "corrected": whole, "session_id": env.get("session_id"),
                        "checked_against_transcript": seen is not None})
        found.append((c, cell, entry))
        c["usage"] = whole
        lines[n] = dumped(c, line)
    if not found:
        print(f"{d.name}: no judge call holds fewer tokens than its reply")
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = results_path.read_bytes().split(b"\n")
    for c, cell, entry in found:
        k, leg = entry_of(manifest, c)
        for where, usage in ((f"eval_manifest.json judge_legs[{k}].usage", leg["usage"]),
                             ("eval_manifest.json judge_usage", manifest["judge_usage"])):
            for key in KEYS:
                changes.append({"where": where, "field": key, "recorded": usage[key], "corrected": usage[key] + entry[key]})
                usage[key] += entry[key]
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
                                "corrected": r["components"]["usage"][key] + cell[key]})
                r["components"]["usage"][key] += cell[key]
            results[n] = dumped(r, results[n])
        print(f"{c.get('question_id')} {c.get('score')}: record +{cell['tokens_in']} in, +{cell['tokens_out']} out; "
              f"scoring start entry {k} +{entry['tokens_in']} in, +{entry['tokens_out']} out; score cells {len(cells)}")
    if not args.write:
        print("  (nothing written; --write does it)")
        return
    files = write_files(d, [(calls_path, b"\n".join(lines)), (results_path, b"\n".join(results)),
                            (manifest_path, manifest_bytes(manifest, manifest_path))])
    add_entry(d, (f"{len(found)} judge call(s) held fewer tokens in their record than their own reply counts: the reply's "
                  "usage field held 0 tokens or only some of the requests the CLI made in the call. The record, its "
                  "scoring start's entry, judge_usage and its score cell now hold the whole call's tokens."),
              changes, [{"what": "the call's counts are its own reply's counts for the one model it names, and the CLI's "
                                 "transcript where the counts given hold it", "holds": True, "looked_at": len(found)}], files)
    print(f"written: {len(changes)} changes; corrections.json, {SCRIPT}")


if __name__ == "__main__":
    main()

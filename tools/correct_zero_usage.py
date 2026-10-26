"""Give a model call whose CLI reply recorded 0 tokens the counts that the same reply and the CLI's
own transcript of the call hold; say exactly what was changed.

    python tools/correct_zero_usage.py <run folder> <transcript counts json> [--write]

Without --write it only prints what it would change and what it checked. The transcript counts are
read on the machine that made the calls, from the lane's own transcript of each call
(~/.claude-herb-lane/projects/**/<session_id>.jsonl, the usage of every assistant message summed,
one message counted once), and given as {session_id: {input_tokens, cache_creation_input_tokens,
cache_read_input_tokens, output_tokens}}; the file is copied into the run folder. It starts from
the rows as they stand, and keeps the rows as recorded as arm_outputs.as_recorded.jsonl on the
first write of any correction, never changed after.

Rule "zero-usage/2".
  1. A model call that answered (a row's call record of kind chat: the answer call, marked role:
     answer, or a call the arm made itself, such as its first call) is corrected when its reply's
     usage field holds 0 tokens in and 0 out and its list of iterations is empty.
  2. Its counts are the reply's own counts per model (modelUsage), for the one model the call
     names, counted as the harness counts the usage field (harness.chat): tokens in = inputTokens
     + cacheCreationInputTokens + cacheReadInputTokens, cached tokens in = cacheReadInputTokens,
     tokens out = outputTokens.
  3. They must be the counts of the CLI's own transcript of the call, found by the reply's
     session_id; otherwise nothing is written.
  4. They go into the call record's usage. For the answer call they go into the row's generator;
     for a call of the arm the row's retrieval is counted again from its records, as the harness
     counts it (harness.capture.usage_by_model), and only its tokens may change. The reply itself
     (the envelope) stays as the CLI wrote it; no answer, context, score or time changes.
"""
import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RULE = "zero-usage/2"
SCRIPT = "correct_zero_usage.py"
EVIDENCE = "cli_transcript_usage.json"
HIS_WORDS = "\"yeah, why 0?, do so\" (2026-10-23, on the answer calls whose rows held 0 tokens)"
REPO = Path(__file__).resolve().parents[1]
# the arms are in prod/ and test/: FIELDS.md takes an arm's own words from its file
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def counted(model_usage):
    """The harness's three numbers from one model's counts in a reply."""
    cached = int(model_usage.get("cacheReadInputTokens") or 0)
    return {"prompt_tokens": int(model_usage.get("inputTokens") or 0)
            + int(model_usage.get("cacheCreationInputTokens") or 0) + cached,
            "completion_tokens": int(model_usage.get("outputTokens") or 0),
            "cached_input_tokens": cached}


def from_transcript(usage):
    cached = int(usage.get("cache_read_input_tokens") or 0)
    return {"prompt_tokens": int(usage.get("input_tokens") or 0)
            + int(usage.get("cache_creation_input_tokens") or 0) + cached,
            "completion_tokens": int(usage.get("output_tokens") or 0),
            "cached_input_tokens": cached}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("run")
    p.add_argument("transcripts")
    p.add_argument("--write", action="store_true")
    p.add_argument("--ordered-by", default=HIS_WORDS, help="his words that ordered this correction")
    args = p.parse_args()
    d = Path(args.run)
    transcripts = json.loads(Path(args.transcripts).read_text(encoding="utf-8"))
    rows_path = d / "arm_outputs.jsonl"
    raw = rows_path.read_bytes()
    lines = raw.split(b"\n")
    from harness import capture
    changes, checks, durations = [], [], {"corrected": [], "others": []}
    agree = looked = answers = arm_calls = 0
    for n, line in enumerate(lines):
        if not line.strip():
            continue
        row = json.loads(line)
        if len([c for c in row["calls"] if c.get("role") == "answer"]) != 1:
            raise SystemExit(f"row {n} ({row['id']}): not one call record marked role: answer")
        where = f"arm_outputs.jsonl row {n} ({row['id']})"
        arm_touched = row_changed = False
        for i, call in enumerate(row["calls"]):
            if call.get("kind") != "chat" or not call.get("ok"):
                continue
            env = call["envelope"]
            usage = env.get("usage") or {}
            empty = (not usage.get("input_tokens") and not usage.get("output_tokens")
                     and not usage.get("cache_creation_input_tokens")
                     and not usage.get("cache_read_input_tokens") and not usage.get("iterations"))
            if call.get("role") == "answer":
                durations["corrected" if empty else "others"].append(env.get("duration_ms", 0) / 1000)
            if not empty:
                continue
            looked += 1
            per_model = env.get("modelUsage") or {}
            if list(per_model) != [call["model"]]:
                raise SystemExit(f"row {n} ({row['id']}): the reply's counts name {list(per_model)}, "
                                 f"not only {call['model']}")
            new = counted(per_model[call["model"]])
            seen = transcripts.get(env["session_id"])
            if seen is None or from_transcript(seen) != new:
                raise SystemExit(f"row {n} ({row['id']}): the CLI's transcript of session "
                                 f"{env['session_id']} does not hold the reply's counts")
            agree += 1
            row_changed = True
            changes.append({"where": where, "field": f"calls[{i}].usage", "recorded": dict(call["usage"]),
                            "corrected": new, "session_id": env["session_id"]})
            call["usage"] = new
            if call.get("role") == "answer":
                answers += 1
                g = row["generator"]
                for field, old, value in (
                        ("generator.tokens_in", g["tokens_in"], new["prompt_tokens"]),
                        ("generator.cached_input_tokens", g["cached_input_tokens"], new["cached_input_tokens"]),
                        ("generator.tokens_out", g["tokens_out"], new["completion_tokens"])):
                    changes.append({"where": where, "field": field, "recorded": old, "corrected": value,
                                    "session_id": env["session_id"]})
                g["tokens_in"], g["cached_input_tokens"], g["tokens_out"] = (
                    new["prompt_tokens"], new["cached_input_tokens"], new["completion_tokens"])
            else:
                arm_calls += 1
                arm_touched = True
        if arm_touched:
            # rule 4: the arm's own calls counted again, as the harness counts them; only tokens change
            before = row["retrieval"]
            after = capture.usage_by_model([c for c in row["calls"] if c.get("role") != "answer"])
            token_keys = ("tokens_in", "cached_input_tokens", "tokens_out")
            if ([{k: v for k, v in e.items() if k not in token_keys} for e in after]
                    != [{k: v for k, v in e.items() if k not in token_keys} for e in before]):
                raise SystemExit(f"row {n} ({row['id']}): its retrieval counted again differs in more than "
                                 "its tokens; nothing written")
            changes.append({"where": where, "field": "retrieval", "recorded": before, "corrected": after})
            row["retrieval"] = after
        if row_changed:
            lines[n] = json.dumps(row, ensure_ascii=False, default=repr).encode("utf-8")
    checks += [
        {"what": "every model call corrected has counts for its one model in its own reply",
         "holds": True, "looked_at": looked},
        {"what": "those counts are the CLI's own transcript of the call, by session_id",
         "holds": agree == looked, "looked_at": looked},
    ]
    med = lambda xs: sorted(xs)[len(xs) // 2] if xs else None  # noqa: E731
    print(f"{looked} model calls with 0 tokens in their reply's usage field ({answers} answer calls, "
          f"{arm_calls} calls of the arm); {agree} of them match the CLI's transcript")
    print(f"answer call seconds, median: corrected {med(durations['corrected'])}, "
          f"others {med(durations['others'])}")
    if not looked:
        print("nothing to correct")
        return
    if not args.write:
        print("  (nothing written; --write does it)")
        return
    before = sha(rows_path)
    kept = d / "arm_outputs.as_recorded.jsonl"
    if not kept.exists():
        shutil.copy2(rows_path, kept)
    tmp = rows_path.with_name(rows_path.name + ".tmp")
    tmp.write_bytes(b"\n".join(lines))
    tmp.replace(rows_path)
    shutil.copy2(args.transcripts, d / EVIDENCE)
    if Path(__file__).resolve() != (d / SCRIPT).resolve():
        shutil.copy2(__file__, d / SCRIPT)
    earlier = (json.loads((d / "corrections.json").read_text(encoding="utf-8"))["corrections"]
               if (d / "corrections.json").exists() else [])
    entry = {
        "made_at": datetime.now(timezone.utc).isoformat(),
        "ordered_by": args.ordered_by,
        "what_happened": (f"On {looked} model calls ({answers} answer calls, {arm_calls} calls of the arm) "
                          "the CLI's reply held 0 in its usage field and an empty list of iterations, "
                          "while the same reply's counts per model and the CLI's own transcript of the "
                          "call held the tokens. The harness reads the usage field, so the rows held 0 "
                          "tokens for those calls."),
        "rule": {"id": RULE, "text": __doc__.split(f'Rule "{RULE}".', 1)[1].strip()},
        "not_changed_and_worth_knowing": [
            "Why the CLI wrote 0 in its usage field on these calls is not known. On them its list "
            "of iterations is empty, and they took longer: a median of "
            f"{med(durations['corrected']):.1f} s against {med(durations['others']):.1f} s for "
            "the other answer calls.",
            "No answer, context, score or time is changed: only the tokens of those calls.",
        ],
        "changes": changes,
        "checks": checks,
        "evidence": {"file": EVIDENCE, "sha256": sha(d / EVIDENCE),
                     "what": "the CLI's own transcript counts of each corrected call, read on the "
                             "machine that made the calls"},
        "files": {"arm_outputs.jsonl": {"sha256_before": before, "sha256_corrected": sha(rows_path),
                                        "as_recorded": kept.name}},
        "script": f"{SCRIPT}, in this folder",
    }
    (d / "corrections.json").write_text(json.dumps({"corrections": earlier + [entry]},
                                                   ensure_ascii=False, indent=2), encoding="utf-8")
    from harness import fields
    fields.write(d, stamp_files=True)
    print(f"written: {len(changes)} changes in {looked} rows; corrections.json, {EVIDENCE}, {SCRIPT}")


if __name__ == "__main__":
    main()

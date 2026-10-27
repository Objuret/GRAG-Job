"""Give each answer call and each first call of a run the answer model's own time for its answering
try, and a call that the login's load slowed the time its arm's calls take for an answer of that
length when nothing slows them; say exactly what was changed.

    python tools/correct_model_call_time.py <run folder> [<run folder> ...] [--check <re-sent calls json>] [--write]

The login's backlog and the clean relations are worked out once from the run folders under
output/k=chars, the same for every run folder this corrects; model_call_times.json, written beside
the rows, holds them and every corrected call's numbers. --check names the calls sent again one at a
time to test the relations; their result goes into the evidence as it is. Without --write it only
prints what it would change. It keeps the rows as recorded as arm_outputs.as_recorded.jsonl on the
first write of any correction, never changed after.

Rule "model-call-time/1".
  1. A call is an answer call (role answer) or a first call (the artefact's call without a role) on
     claude-sonnet-5 that answered. Its time is its answering try's server time: the CLI's own
     duration_api_ms, the time spent with the model, without the program's start on our machine.
  2. The login's backlog: every claude-sonnet-5 chat call that started from 1 to 26 October (UTC), in
     any run folder under output/k=chars, adds its input tokens at its start; between two starts the
     backlog drops by R tokens per second and never below 0. R is the rate, from 10,000 to 22,000 by
     500, whose backlog ranks the answer calls' server seconds per 1,000 output tokens best (rank
     correlation); the limit is the backlog at which log(seconds per 1,000 output tokens) against the
     backlog bends (two straight segments, least squares, the bend at one of 181 quantiles from 5% to
     95%).
  3. A call that started at or past the limit gets the time of its arm's clean relation at its own
     output tokens: seconds = a + b * output tokens, fitted on the server times of the arm's calls of
     the same kind (answer, first call) in the final runs that started below the limit (for the first
     calls, with the run they were read from). Every call past the limit gets it, whatever its own
     server time.
  4. In the row, the call's entry (generator for the answer call, the retrieval entry of kind chat for
     the first call) gets request_s = the time of rules 1 and 3, and time_s = request_s + wait_s +
     retry_s; wait_s and retry_s stay as recorded, and the harness's own time in the call is out.
  5. The question's timing.wall_s changes by the same amount as the entry's time_s for a call made
     inside the row's span; a first call read from the run's store, made by an earlier start before
     the row's span began, changes no wall_s. No call record, answer, context, score or token count
     changes.
"""
import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

RULE = "model-call-time/1"
SCRIPT = "correct_model_call_time.py"
EVIDENCE = "model_call_times.json"
HIS_WORDS = ("\"answer seconds looks really fucked up btw, there is litterally no chance those times are correct for "
             "real.. take a serious look at them\" · \"do a selected test/fix for a bunch and see if its the correct "
             "way\" · \"doit\" (2026-10-27)")
MODEL = "claude-sonnet-5"
WINDOW = (datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp(), datetime(2026, 10, 27, tzinfo=timezone.utc).timestamp())
R_GRID = range(10000, 22001, 500)
REPO = Path(__file__).resolve().parents[1]
K = REPO / "output" / "k=chars"
# the arms are in prod/ and test/: FIELDS.md takes an arm's own words from its file
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test"), str(REPO / "tools")]
from export_finished_data import MADE_IN, RUNS  # noqa: E402  the final runs, and the run the hundred's first calls are from

ARM_OF = {f: arm for arm, folders in RUNS.items() for f in folders}
ARM_OF.update({src: ARM_OF[f] for f, src in MADE_IN.items()})


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stamp(s):
    return datetime.fromisoformat(s).timestamp()


def tokens(c):
    """A call record's input and output tokens: its usage, or the CLI's counts per model."""
    u = c.get("usage") or {}
    mu = ((c.get("envelope") or {}).get("modelUsage") or {}).get(c.get("model")) or {}
    tin = int(u.get("prompt_tokens") or 0) or int((mu.get("inputTokens") or 0) + (mu.get("cacheReadInputTokens") or 0)
                                                 + (mu.get("cacheCreationInputTokens") or 0))
    return tin, int(u.get("completion_tokens") or 0) or int(mu.get("outputTokens") or 0)


def login_calls():
    """Every claude-sonnet-5 chat call in WINDOW, once, from every run folder's arm_outputs.jsonl and
    eval_calls.jsonl; and the files read, with their sha256."""
    calls, read = {}, {}
    for d in sorted(K.iterdir()):
        m = re.search(r"(2026\d{4})", d.name)
        if not d.is_dir() or not m or m.group(1) < "20261001":
            continue
        for fn in ("arm_outputs.jsonl", "eval_calls.jsonl"):
            p = d / fn
            if not p.exists():
                continue
            found = 0
            with open(p, encoding="utf-8") as fh:
                for n, line in enumerate(fh):
                    if MODEL not in line:
                        continue
                    obj = json.loads(line)
                    for i, c in enumerate((obj.get("calls") or []) if fn == "arm_outputs.jsonl" else [obj]):
                        if c.get("kind") != "chat" or c.get("model") != MODEL or not c.get("started_at"):
                            continue
                        a = stamp(c["started_at"])
                        if not WINDOW[0] <= a < WINDOW[1]:
                            continue
                        tin, tout = tokens(c)
                        key = (round(a, 3), round(stamp(c["finished_at"]), 3) if c.get("finished_at") else None, tin)
                        rec = calls.setdefault(key, {
                            "start": a, "in": tin, "out": tout, "ok": bool(c.get("ok")), "role": c.get("role"),
                            "server": ((c.get("envelope") or {}).get("duration_api_ms") or 0) / 1000, "at": []})
                        rec["at"].append((d.name, fn, n, i))
                        found += 1
            if found:
                read[f"{d.name}/{fn}"] = {"sha256": sha(p), "claude_sonnet_5_calls": found}
    return sorted(calls.values(), key=lambda c: c["start"]), read


def backlog(calls, R):
    out, A, prev = np.empty(len(calls)), 0.0, calls[0]["start"]
    for k, c in enumerate(calls):
        A = max(0.0, A - R * (c["start"] - prev)) + c["in"]
        prev = c["start"]
        out[k] = A
    return out


def ranks(x):
    return np.argsort(np.argsort(x, kind="stable"), kind="stable").astype(float)


def hinge(x, y):
    best = None
    for x0 in np.quantile(x, np.linspace(0.05, 0.95, 181)):
        X = np.column_stack([np.ones_like(x), np.maximum(0, x - x0)])
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        sse = float(((X @ coef - y) ** 2).sum())
        if best is None or sse < best[0]:
            best = (sse, float(x0), coef)
    return best


def method():
    """Rule 2 and rule 3: the backlog's rate and limit, each login call's backlog, the clean relations."""
    calls, read = login_calls()
    answers = [k for k, c in enumerate(calls) if c["role"] == "answer" and c["ok"] and c["server"] > 0 and c["out"] > 0]
    y = np.array([calls[k]["server"] / calls[k]["out"] * 1000 for k in answers])
    grid = [(float(np.corrcoef(ranks(backlog(calls, R)[answers]), ranks(y))[0, 1]), R) for R in R_GRID]
    best_r, R = max(grid)
    A = backlog(calls, R)
    _, limit, coef = hinge(A[answers], np.log(y))
    rng = np.random.default_rng(0)
    boots = [hinge(A[answers][b], np.log(y)[b])[1] for b in (rng.integers(0, len(answers), len(answers)) for _ in range(300))]
    for k, c in enumerate(calls):
        c["backlog"] = float(A[k])
    relations = {}
    for kind in ("answer", "first"):
        for arm in sorted(set(ARM_OF.values())):
            rows = [c for c in calls if c["ok"] and c["server"] > 0 and c["out"] > 0 and c["backlog"] < limit
                    and (c["role"] == "answer" if kind == "answer" else c["role"] is None)
                    and any(ARM_OF.get(f) == arm and (kind == "first" or f not in MADE_IN.values()) and fn == "arm_outputs.jsonl"
                            for f, fn, _, _ in c["at"])]
            if len(rows) < 10:
                continue
            x = np.array([c["out"] for c in rows], float)
            s = np.array([c["server"] for c in rows])
            b, a = np.polyfit(x, s, 1)
            loo = [abs(s[k] - np.polyval(np.polyfit(np.delete(x, k), np.delete(s, k), 1), x[k])) for k in range(len(x))]
            relations[f"{kind}|{arm}"] = {"a_seconds": float(a), "b_seconds_per_output_token": float(b), "calls": len(rows),
                                          "output_tokens_range": [int(x.min()), int(x.max())],
                                          "leave_one_out_abs_error_median_s": float(np.median(loo)),
                                          "leave_one_out_abs_error_p90_s": float(np.percentile(loo, 90))}
    where = {(f, n, i): c for c in calls for f, fn, n, i in c["at"] if fn == "arm_outputs.jsonl"}
    summary = {
        "window_utc": ["2026-10-01T00:00:00Z", "2026-10-27T00:00:00Z"], "model": MODEL, "files_read": read,
        "claude_sonnet_5_calls": len(calls), "answer_calls_fitted": len(answers),
        "rate_grid_rank_correlation": [[R_, round(r, 4)] for r, R_ in grid],
        "rate_tokens_per_second": R, "rank_correlation_at_rate": best_r,
        "limit_backlog_tokens": limit, "limit_bootstrap_5_95_tokens": [float(np.percentile(boots, 5)), float(np.percentile(boots, 95))],
        "seconds_per_1000_output_tokens_below_limit_fitted": float(np.exp(coef[0])),
        "relations": relations,
    }
    return summary, where


def main():
    p = argparse.ArgumentParser()
    p.add_argument("run", nargs="+")
    p.add_argument("--check")
    p.add_argument("--write", action="store_true")
    args = p.parse_args()
    folders = [Path(r).resolve() for r in args.run]
    for d in folders:
        if d.name not in ARM_OF:
            raise SystemExit(f"{d.name} is not a final run or the run a final run's first calls are from")
        if (d / "corrections.json").exists() and any(
                e["rule"]["id"] == RULE for e in json.loads((d / "corrections.json").read_text(encoding="utf-8"))["corrections"]):
            raise SystemExit(f"{d.name}: {RULE} is already written")
    summary, where = method()
    for d in folders:
        correct(d, summary, where, args)


def correct(d, summary, where, args):
    earlier = (json.loads((d / "corrections.json").read_text(encoding="utf-8"))["corrections"]
               if (d / "corrections.json").exists() else [])
    arm = ARM_OF[d.name]
    rows_path = d / "arm_outputs.jsonl"
    lines = rows_path.read_bytes().split(b"\n")
    changes, per_call, before_s, after_s = [], [], 0.0, 0.0
    for n, line in enumerate(lines):
        if not line.strip():
            continue
        row = json.loads(line)
        where_ = f"arm_outputs.jsonl row {n} ({row['id']})"
        row_start = stamp(row["timing"]["started_at"])
        for kind, entry in (("answer", row["generator"]),
                            ("first", next((e for e in row["retrieval"] if e["kind"] == "chat"), None))):
            recs = [(i, c) for i, c in enumerate(row["calls"]) if c.get("kind") == "chat" and c.get("model") == MODEL
                    and (c.get("role") == "answer" if kind == "answer" else c.get("role") is None)]
            if entry is None and not recs:
                continue
            answered = [(i, c) for i, c in recs if c.get("ok")]
            if entry is None or len(answered) != 1:
                raise SystemExit(f"{where_}: the {kind} call's entry has not exactly one answering record")
            i, c = answered[0]
            server = ((c.get("envelope") or {}).get("duration_api_ms") or 0) / 1000
            ok_try = c["attempts"][-1]
            if server <= 0 or ok_try.get("outcome") != "ok" or abs(float(ok_try["seconds"]) - entry["request_s"]) > 1e-6:
                raise SystemExit(f"{where_}: the {kind} call has no server time, or its entry's request_s is not its answering try")
            login = where[(d.name, n, i)]
            rel = summary["relations"][f"{kind}|{arm}"]
            out_tokens = tokens(c)[1]
            past = login["backlog"] >= summary["limit_backlog_tokens"]
            value = rel["a_seconds"] + rel["b_seconds_per_output_token"] * out_tokens if past else server
            inside = stamp(c["started_at"]) >= row_start
            new_time = value + entry["wait_s"] + entry["retry_s"]
            delta = new_time - entry["time_s"]
            name = "generator" if kind == "answer" else "retrieval.chat"
            for field, old, new in ((f"{name}.request_s", entry["request_s"], value), (f"{name}.time_s", entry["time_s"], new_time)):
                changes.append({"where": where_, "field": field, "recorded": old, "corrected": new})
            if inside:
                changes.append({"where": where_, "field": "timing.wall_s", "recorded": row["timing"]["wall_s"],
                                "corrected": row["timing"]["wall_s"] + delta})
                row["timing"]["wall_s"] += delta
            before_s += entry["request_s"]
            after_s += value
            per_call.append({"question_id": row["id"], "kind": kind, "record": f"calls[{i}]", "seq": c.get("seq"),
                             "started_at": c["started_at"], "output_tokens": out_tokens, "our_clock_s": entry["request_s"],
                             "server_s": server, "login_backlog_tokens": login["backlog"], "past_limit": past,
                             "relation_s": rel["a_seconds"] + rel["b_seconds_per_output_token"] * out_tokens,
                             "seconds": value, "inside_row_span": inside})
            entry["request_s"], entry["time_s"] = value, new_time
        lines[n] = json.dumps(row, ensure_ascii=False, default=repr).encode("utf-8")
    past_n = sum(c["past_limit"] for c in per_call)
    print(f"{d.name}: {len(per_call)} calls ({past_n} past the limit): {before_s:.1f} s by our clock, {after_s:.1f} s corrected; "
          f"rate {summary['rate_tokens_per_second']} tokens/s, limit {summary['limit_backlog_tokens']:,.0f} tokens")
    for k, r in summary["relations"].items():
        print(f"   relation {k}: {r['a_seconds']:.2f} s + {r['b_seconds_per_output_token'] * 1000:.2f} s per 1,000 output tokens "
              f"(n {r['calls']}, leave-one-out error median {r['leave_one_out_abs_error_median_s']:.2f} s)")
    if not args.write:
        print("  (nothing written; --write does it)")
        return
    evidence = dict(summary, run=d.name, arm=arm, calls=per_call)
    if args.check:
        evidence["check"] = {"what": "calls past the limit sent again one at a time on 2026-10-27, each checked equal to its "
                                     "record (flags, system, prompt, schema, environment apart from the config folder); "
                                     "claude-sonnet-5 takes no temperature, so each gives a new answer: its server time is "
                                     "compared with the relation at the new answer's own output tokens",
                             "calls": json.loads(Path(args.check).read_text(encoding="utf-8"))}
    before = sha(rows_path)
    kept = d / "arm_outputs.as_recorded.jsonl"
    if not kept.exists():
        shutil.copy2(rows_path, kept)
    tmp = rows_path.with_name(rows_path.name + ".tmp")
    tmp.write_bytes(b"\n".join(lines))
    tmp.replace(rows_path)
    (d / EVIDENCE).write_text(json.dumps(evidence, ensure_ascii=False, indent=1), encoding="utf-8")
    if Path(__file__).resolve() != (d / SCRIPT).resolve():
        shutil.copy2(__file__, d / SCRIPT)
    entry = {
        "made_at": datetime.now(timezone.utc).isoformat(),
        "ordered_by": HIS_WORDS,
        "what_happened": ("A model call's time was our clock around the whole CLI program, which holds the program's start "
                          "on our machine (longer with more calls at once), and the calls that started while the login's "
                          "backlog of claude-sonnet-5 input tokens was past its limit were slowed by the server. Each answer "
                          "call and first call now has the server's own time for its answering try, and a call past the "
                          "limit the time its arm's calls take for an answer of that length below it."),
        "rule": {"id": RULE, "text": __doc__.split(f'Rule "{RULE}".', 1)[1].strip()},
        "not_changed_and_worth_knowing": [
            "Every call record keeps each try's seconds as our clock measured them; only the row's entries and wall_s change.",
            "The backlog holds the calls of the run folders on this laptop; a call on the login that no folder here holds "
            "(another machine's own folders, an interactive session) is not in it.",
            "The judge calls are not changed: their server time shows no slowing at any load.",
            f"{past_n} of the run's {len(per_call)} calls are past the limit and hold the relation's time.",
        ],
        "changes": changes,
        "checks": [{"what": "each changed entry held exactly one answering record, whose answering try's seconds were the "
                            "entry's request_s and which has a server time", "holds": True, "looked_at": len(per_call)}],
        "evidence": {"file": EVIDENCE, "sha256": sha(d / EVIDENCE),
                     "what": "the backlog's rate and limit, the clean relations, the files they were read from with their "
                             "sha256, and per corrected call its server time, backlog, relation time and time"
                             + ("; the check of the relations on calls sent again" if args.check else "")},
        "files": {"arm_outputs.jsonl": {"sha256_before": before, "sha256_corrected": sha(rows_path), "as_recorded": kept.name}},
        "script": f"{SCRIPT}, in this folder",
    }
    (d / "corrections.json").write_text(json.dumps({"corrections": earlier + [entry]}, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    from harness import fields
    fields.write(d, stamp_files=True)
    print(f"written: {len(changes)} changes; corrections.json, {EVIDENCE}, {SCRIPT}")


if __name__ == "__main__":
    main()

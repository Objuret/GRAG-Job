"""Give eval_manifest.json an entry in judge_legs for every scoring start whose call records are in
eval_calls.jsonl and whose entry was never written, built from that start's own call records, and
judge_usage again as the sum of the entries; say exactly what was changed.

    python tools/correct_missing_judge_legs.py <run folder> [--write]

Without --write it only prints what it would change and what it checked. A start writes its entry
when it ends; a start whose process was killed, or whose machine shut down, wrote none, while
eval_calls.jsonl holds every call of each score cell that finished, written as the cell finished.
The correction starts from the manifest as it stands, and keeps the manifest as recorded as
eval_manifest.as_recorded.json on the first write of any correction, never changed after.

Rule "missing-judge-legs/2".
  1. A scoring start is missing when eval_calls.jsonl holds records with its eval_leg and no entry
     of judge_legs has that time as its settings.started_at. An entry that names no start (a start
     of prod/run.py --rejudge writes its entry with no settings) belongs to the one start, not named
     by another entry, whose judge calls that answered, counted by rule 2, are the entry's calls and
     whose last call record ended before the entry's timestamp; it gets that start as
     settings.started_at. When no start, or more than one, fits an entry, nothing is written.
  2. Its usage is counted from its records the way the harness counts a judge call (eval.ragas,
     harness.chat): calls = its judge call records that answered (ok); attempts = their tries;
     tokens_in, cached_input_tokens and tokens_out = the sums of those calls' usage; request_s =
     the seconds of each call's try that answered; retry_s = the seconds of its other tries and of
     every pause between tries; time_s = from each call's started_at to its finished_at;
     reasoning_tokens and wait_s 0, as the harness always has them. A judge call that gave up (no
     try answered) counts in none of these, as in the harness.
  3. Its judge_model is the one model of its judge calls (empty when it made none); its
     judge_backend the evaluation's. Its settings hold started_at (its eval_leg), interrupted (that
     the start wrote no entry) and embedding (its embedder records summed: requests, texts,
     tokens_in, lock_wait_s, encode_s, as the harness sums them). Its timestamp, elapsed_s and
     settings.finished_at are empty: when the start ended is not recorded. Nothing else of the
     settings is recorded for it.
  4. The entries stand in the order of their starts. judge_usage is their sum, as the harness sums
     it; judge_elapsed_s stays the sum of the entries' elapsed_s. No written entry changes but for
     the settings.started_at of rule 1; no score, cell or call record changes.
  5. The same counting is done on every written entry's start and compared with that entry; what
     differs is printed and kept with the correction, and changes nothing.
"""
import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RULE = "missing-judge-legs/2"
SCRIPT = "correct_missing_judge_legs.py"
HIS_WORDS = ("\"commit, correct answer tokens, , make sure this is the same quality as all my previous "
             "runs and can be added to the workbook\" (2026-10-25)")
REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "prod")]
COUNTS = ("calls", "attempts", "tokens_in", "cached_input_tokens", "tokens_out")
USAGE = ("calls", "tokens_in", "cached_input_tokens", "tokens_out", "reasoning_tokens", "time_s",
         "attempts", "request_s", "wait_s", "retry_s")
EMBEDDING = ("requests", "texts", "tokens_in", "lock_wait_s", "encode_s")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def seconds(a, b):
    return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds()


def usage_of(records):
    """Rule 2: the usage of a start's judge calls, from their records."""
    ok = [c for c in records if c.get("kind") == "chat" and c.get("ok")]
    u = dict.fromkeys(USAGE, 0)
    u.update(time_s=0.0, request_s=0.0, wait_s=0.0, retry_s=0.0)
    for c in ok:
        tries, use = c.get("attempts") or [], c.get("usage") or {}
        if not tries or tries[-1].get("outcome") != "ok":
            raise SystemExit(f"a judge call that answered has no answering try last "
                             f"({c.get('eval_leg')}, {c.get('question_id')}, {c.get('score')})")
        u["calls"] += 1
        u["attempts"] += len(tries)
        u["tokens_in"] += int(use.get("prompt_tokens") or 0)
        u["cached_input_tokens"] += int(use.get("cached_input_tokens") or 0)
        u["tokens_out"] += int(use.get("completion_tokens") or 0)
        u["request_s"] += float(tries[-1].get("seconds") or 0.0)
        u["retry_s"] += (sum(float(t.get("seconds") or 0.0) for t in tries[:-1])
                         + sum(float(t.get("backoff_s") or 0.0) for t in tries))
        u["time_s"] += seconds(c["started_at"], c["finished_at"])
    return u


def embedding_of(records):
    emb = [c for c in records if c.get("kind") == "embed"]
    return {"requests": len(emb), "texts": sum(int(c.get("n_texts") or 0) for c in emb),
            "tokens_in": sum(int(c.get("tokens_in") or 0) for c in emb),
            "lock_wait_s": sum(float(c.get("lock_wait_s") or 0.0) for c in emb),
            "encode_s": sum(float(c.get("encode_s") or 0.0) for c in emb)}


def summed(legs):
    total = dict.fromkeys(USAGE, 0)
    for leg in legs:
        for k in USAGE:
            total[k] += (leg.get("usage") or {}).get(k) or 0
    for k in ("time_s", "request_s", "wait_s", "retry_s"):
        total[k] = float(total[k])
    return total


def differs(a, b, keys):
    return {k: [a.get(k), b.get(k)] for k in keys if a.get(k) != b.get(k)}


def corrected(d):
    """The manifest as it stands, the corrected manifest (None when no start is missing), the
    changes and the checks."""
    d = Path(d)
    ev = json.loads((d / "eval_manifest.json").read_text(encoding="utf-8"))
    calls = rows(d / "eval_calls.jsonl")
    by_leg = {}
    for c in calls:
        by_leg.setdefault(c["eval_leg"], []).append(c)
    legs = [dict(leg) for leg in ev.get("judge_legs") or []]
    unnamed = [n for n, leg in enumerate(legs) if not (leg.get("settings") or {}).get("started_at")]
    changes = []
    # rule 1: an entry that names no start belongs to the one free start with its calls, ended before it
    free = sorted(set(by_leg) - {(leg.get("settings") or {}).get("started_at") for leg in legs})
    for n in unnamed:
        leg, want = legs[n], (legs[n].get("usage") or {}).get("calls")
        fits = [s for s in free if usage_of(by_leg[s])["calls"] == want and leg.get("timestamp")
                and datetime.fromisoformat(max(c["finished_at"] for c in by_leg[s]))
                <= datetime.fromisoformat(leg["timestamp"])]
        if len(fits) != 1:
            raise SystemExit(f"{d.name}: the entry {n} of judge_legs names no start, and {len(fits)} starts "
                             f"have its {want} judge calls and ended before its timestamp; nothing written")
        free.remove(fits[0])
        leg["settings"] = dict(leg.get("settings") or {}, started_at=fits[0])
        changes.append({"where": f"eval_manifest.json judge_legs[{n}]", "field": "settings.started_at",
                        "recorded": None, "corrected": fits[0]})
    written = {(leg.get("settings") or {}).get("started_at") for leg in legs}
    missing = sorted(set(by_leg) - written)
    checks, recorded_differ = [], []
    for leg in legs:
        start = (leg.get("settings") or {}).get("started_at")
        mine, theirs = usage_of(by_leg.get(start, [])), leg.get("usage") or {}
        diff = differs(theirs, mine, COUNTS)
        if diff:
            recorded_differ.append({"start": start, "entry_and_records": diff})
    checks.append({"what": "rule 5: each written entry's counts (calls, attempts, tokens in, cached and "
                           "out) are those of its start's records, counted by rule 2",
                   "holds": not recorded_differ, "looked_at": len(legs),
                   **({"differs": recorded_differ} if recorded_differ else {})})
    backends = {leg.get("judge_backend") for leg in legs}
    new_legs = list(legs)
    for start in missing:
        recs = by_leg[start]
        models = sorted({c["model"] for c in recs if c.get("kind") == "chat"})
        if len(models) > 1:
            raise SystemExit(f"start {start}: its judge calls name {models}, not one model")
        entry = {"timestamp": None,
                 "judge_model": models[0] if models else None,
                 "judge_backend": ev.get("judge_backend"),
                 "usage": usage_of(recs),
                 "elapsed_s": None,
                 "settings": {"started_at": start, "finished_at": None,
                              "interrupted": (f"the start wrote no entry; rebuilt from its records in "
                                              f"eval_calls.jsonl by correction {RULE} (corrections.json)"),
                              "embedding": embedding_of(recs)}}
        new_legs.append(entry)
        changes.append({"where": "eval_manifest.json judge_legs", "field": f"the entry of start {start}",
                        "recorded": None, "corrected": entry,
                        "records": {"judge_calls": sum(1 for c in recs if c.get("kind") == "chat"),
                                    "judge_calls_that_gave_up": sum(1 for c in recs if c.get("kind") == "chat"
                                                                    and not c.get("ok")),
                                    "embedder_requests": sum(1 for c in recs if c.get("kind") == "embed"),
                                    "first_started_at": min(c["started_at"] for c in recs),
                                    "last_finished_at": max(c["finished_at"] for c in recs)}})
    if not missing and not unnamed:
        return ev, None, changes, checks
    if backends != {ev.get("judge_backend")}:
        raise SystemExit(f"the written entries name the backends {sorted(map(str, backends))}, not the "
                         f"evaluation's {ev.get('judge_backend')}")
    new_legs.sort(key=lambda x: (x.get("settings") or {}).get("started_at") or "")
    new = dict(ev, judge_legs=new_legs, judge_usage=summed(new_legs))
    changes.append({"where": "eval_manifest.json", "field": "judge_usage",
                    "recorded": ev.get("judge_usage"), "corrected": new["judge_usage"]})
    # what holds afterwards, against the call records and the score cells
    ok = [c for c in calls if c.get("kind") == "chat" and c.get("ok")]
    of_records = usage_of(calls)
    # a folder that judged a run's answers again holds the run's other scores, judged by the run's
    # own starts, whose calls are in the run's folder: only the rows of this folder's starts count
    res = [r for r in rows(d / "eval_results.jsonl") if r["components"]["usage"].get("eval_leg") in by_leg]
    cells = [r["components"]["usage"] for r in res]
    kept = {(r["question_id"], r["metric"], r["components"]["usage"]["eval_leg"]) for r in res}
    in_cells = [c for c in calls if c.get("kind") == "chat"
                and (c.get("question_id"), c.get("score"), c["eval_leg"]) in kept]
    cell_sum = {"calls": sum(u["chat_calls"] for u in cells), "attempts": sum(u["chat_attempts"] for u in cells),
                "tokens_in": sum(u["tokens_in"] for u in cells),
                "cached_input_tokens": sum(u["cached_input_tokens"] for u in cells),
                "tokens_out": sum(u["tokens_out"] for u in cells)}
    outside = usage_of([c for c in ok if (c.get("question_id"), c.get("score"), c["eval_leg"]) not in kept])
    rest = {k: new["judge_usage"][k] - cell_sum[k] for k in COUNTS}
    embed_records = embedding_of(calls)["tokens_in"]
    embed_legs = sum(((leg.get("settings") or {}).get("embedding") or {}).get("tokens_in") or 0 for leg in new_legs)
    checks += [
        {"what": "every start in eval_calls.jsonl has an entry in judge_legs",
         "holds": set(by_leg) <= {(leg.get("settings") or {}).get("started_at") for leg in new_legs},
         "looked_at": len(by_leg)},
        {"what": "each rebuilt entry's counts are its start's records (rule 2)", "holds": True,
         "looked_at": len(missing)},
        {"what": "judge_usage's counts are those of every judge call record that answered",
         "holds": not differs(new["judge_usage"], of_records, COUNTS), "looked_at": len(ok),
         **({"differs_usage_and_records": differs(new["judge_usage"], of_records, COUNTS)}
            if differs(new["judge_usage"], of_records, COUNTS) else {})},
        {"what": "the score cells' usage (components.usage) is their own judge call records, and every "
                 "one of those answered",
         "holds": (not differs(cell_sum, usage_of(in_cells), COUNTS)
                   and all(c.get("ok") for c in in_cells)), "looked_at": len(res)},
        {"what": "judge_usage less the score cells' usage is the judge calls that answered in cells with no "
                 "row in eval_results.jsonl (cells that failed, or that a later start dropped)",
         "holds": not differs(rest, outside, COUNTS), "looked_at": outside["calls"],
         **({"differs_rest_and_records": differs(rest, outside, COUNTS)} if differs(rest, outside, COUNTS) else {})},
        {"what": "the entries' embedding tokens are those of every embedder record",
         "holds": embed_legs == embed_records, "looked_at": sum(1 for c in calls if c.get("kind") == "embed")},
    ]
    return ev, new, changes, checks


def main():
    p = argparse.ArgumentParser()
    p.add_argument("run")
    p.add_argument("--write", action="store_true")
    p.add_argument("--ordered-by", default=HIS_WORDS, help="his words that ordered this correction")
    args = p.parse_args()
    d = Path(args.run)
    ev, new, changes, checks = corrected(d)
    print(f"{d.name}: {len(ev.get('judge_legs') or [])} entries in judge_legs; "
          f"{sum(1 for c in changes if c['field'].startswith('the entry'))} starts without one")
    for c in changes:
        if c["field"].startswith("the entry"):
            u = c["corrected"]["usage"]
            print(f"  {c['field']}: {u['calls']} judge calls, {u['attempts']} tries, {u['tokens_in']} tokens in "
                  f"({u['cached_input_tokens']} cached), {u['tokens_out']} out, time_s {u['time_s']:.1f}, "
                  f"request_s {u['request_s']:.1f}, retry_s {u['retry_s']:.1f}; embedding "
                  f"{c['corrected']['settings']['embedding']['tokens_in']} tokens; records {c['records']}")
        elif c["field"] == "settings.started_at":
            print(f"  {c['where']}: named no start; its start is {c['corrected']}")
        else:
            print(f"  {c['field']}: {json.dumps({k: c['recorded'][k] for k in COUNTS})} -> "
                  f"{json.dumps({k: c['corrected'][k] for k in COUNTS})}")
    for c in checks:
        print(f"  check {'holds' if c['holds'] else 'DOES NOT HOLD'}: {c['what']} (looked at {c['looked_at']})"
              + "".join(f"; {k}: {json.dumps(v)}" for k, v in c.items() if k.startswith("differs")))
    if new is None:
        print("nothing to correct")
        return
    if not all(c["holds"] for c in checks[1:]):
        print("  (a check after the correction does not hold; it is kept with the correction)")
    if not args.write:
        print("  (nothing written; --write does it)")
        return
    path = d / "eval_manifest.json"
    raw = path.read_bytes()
    before = sha(path)
    kept = d / "eval_manifest.as_recorded.json"
    if not kept.exists():
        shutil.copy2(path, kept)
    text = json.dumps(new, ensure_ascii=False, indent=2, default=repr)
    if b"\r\n" in raw:
        text = text.replace("\n", "\r\n")
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    tmp.replace(path)
    if Path(__file__).resolve() != (d / SCRIPT).resolve():
        shutil.copy2(__file__, d / SCRIPT)
    earlier = (json.loads((d / "corrections.json").read_text(encoding="utf-8"))["corrections"]
               if (d / "corrections.json").exists() else [])
    n = sum(1 for c in changes if c["field"].startswith("the entry"))
    entry = {
        "made_at": datetime.now(timezone.utc).isoformat(),
        "ordered_by": args.ordered_by,
        "what_happened": (f"{n} scoring starts wrote no entry in judge_legs: their processes were killed or "
                          "their machine shut down before the start ended. Their judge calls and embedder "
                          "requests are in eval_calls.jsonl and their cells in eval_results.jsonl, so "
                          "judge_usage, the sum of the entries, was short of them."
                          + (f" {sum(1 for c in changes if c['field'] == 'settings.started_at')} written entries "
                             "named no start (prod/run.py --rejudge writes its entries with no settings) and "
                             "now name the start they belong to." if any(
                                 c["field"] == "settings.started_at" for c in changes) else "")),
        "rule": {"id": RULE, "text": __doc__.split(f'Rule "{RULE}".', 1)[1].strip()},
        "not_changed_and_worth_knowing": [
            "A cell under way when a start's process ended wrote no call record; what its calls cost is "
            "in no file and in no rebuilt entry.",
            "When a rebuilt start ended is not recorded; each change gives the end of its last call record.",
            "judge_elapsed_s stays the sum of the written entries' elapsed_s.",
            "No written entry, score, cell or call record is changed.",
        ],
        "changes": changes,
        "checks": checks,
        "files": {"eval_manifest.json": {"sha256_before": before, "sha256_corrected": sha(path),
                                         "as_recorded": kept.name}},
        "script": f"{SCRIPT}, in this folder",
    }
    (d / "corrections.json").write_text(json.dumps({"corrections": earlier + [entry]},
                                                   ensure_ascii=False, indent=2), encoding="utf-8")
    from harness import fields
    fields.write(d, stamp_files=True)
    print(f"written: {n} entries in judge_legs and judge_usage; corrections.json, {SCRIPT}")


if __name__ == "__main__":
    main()

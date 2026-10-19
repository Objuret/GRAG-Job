"""Take the machine's sleep out of the stored times of a run folder, and say exactly what was changed.

    python correct_slept_tries.py <run folder> --events <print of the machine's sleep and wake events> [--write]

Without --write it only prints what it would change. Numbers, ids and stamps only: no question,
answer or context text is printed. Running it again gives the same files: it always starts from
the files as recorded (*.as_recorded.*), which it makes on the first write and never changes.

Rule "slept-try/1". A try of a model call is one the machine slept under when all three hold:
  1. it ended as a timeout;
  2. it lasted longer than its own timeout (a call that is running is cut at its timeout, so a
     longer one was not running the whole time);
  3. the low-power time the machine itself logged inside the try's start and end is at least the
     try's overrun past its timeout.
The seconds recorded for such a try are taken out of the three sums they went into: the row's
generator.time_s and generator.retry_s, the row's timing.wall_s, and the wall_s of that start in
the run manifest. What those sums hold afterwards: the try that answered, the pause the harness
waits before it tries again, and the harness's own overhead. The slept try's own share of awake
seconds, in which its reply came back, cannot be told apart from the sleep by the run's clock and
goes out with it.

Not changed: the stamps (clock times), the number of tries, the tokens, every score, and the
try's own record, which gets one added key. The files as recorded stay beside the corrected ones.
"""
import argparse
import hashlib
import io
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RULE = "slept-try/1"
HIS_WORDS = ("\"why did you add sleep to the metrics.. ffs\" · \"i thought you were done so i slapped the "
             "laptop lid down and fell asleep yesterday, thats why it fucking 'broke connection'\" · \"no, i "
             "meant, while you still have the stats and information since YOU are the conversation.. you can "
             "correct the data based on that\" (2026-10-09)")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def stamp(text):
    """An ISO time, with any number of second decimals and Z or an offset, as seconds since 1970 UTC."""
    m = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(\.\d+)?(Z|[+-]\d\d:\d\d)?$", text.strip())
    base = datetime.fromisoformat(m.group(1) + (m.group(3) or "+00:00").replace("Z", "+00:00"))
    return base.timestamp() + float(m.group(2) or 0)


def low_power_intervals(events_text):
    """(start, end, what) from the machine's own events: each 'entering Modern Standby' with the
    next 'exiting Modern Standby', and each 'returned from a low power state' with the Sleep Time
    and Wake Time it names."""
    out, entered = [], None
    for line in events_text.splitlines():
        line = line.replace("\u200e", "").replace("\ufeff", "")
        m = re.match(r"(\S+)\s+id\s+(\d+)\s+(.*)$", line.strip())
        if not m:
            continue
        t, eid, msg = stamp(m.group(1)), int(m.group(2)), m.group(3)
        if eid == 506:
            entered = (t, msg)
        elif eid == 507 and entered:
            out.append((entered[0], t, "Modern Standby: " + entered[1].split("|")[-1].strip()))
            entered = None
        elif eid == 1:
            s = re.search(r"Sleep Time:\s*(\S+)", msg)
            w = re.search(r"Wake Time:\s*(\S+)", msg)
            if s and w:
                out.append((stamp(s.group(1)), stamp(w.group(1)), "sleep or hibernate"))
    return sorted(out)


def inside(intervals, start, end):
    """Seconds of the logged low-power intervals that lie between start and end, counted once."""
    total, cursor = 0.0, start
    for a, b, _ in intervals:
        a, b = max(a, cursor), min(b, end)
        if b > a:
            total += b - a
            cursor = b
    return total


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser()
    p.add_argument("folder")
    p.add_argument("--events", required=True)
    p.add_argument("--write", action="store_true")
    args = p.parse_args()
    d = Path(args.folder)
    rows_path, man_path = d / "arm_outputs.jsonl", d / "run_manifest.json"
    kept_rows, kept_man = d / "arm_outputs.as_recorded.jsonl", d / "run_manifest.as_recorded.json"
    src_rows = kept_rows if kept_rows.exists() else rows_path
    src_man = kept_man if kept_man.exists() else man_path
    events_text = Path(args.events).read_text(encoding="utf-8-sig", errors="replace")
    intervals = low_power_intervals(events_text)

    raw = src_rows.read_bytes().split(b"\n")
    changes, lost, new_lines, per_leg = [], [], [], {}
    for n, line in enumerate(raw):
        if not line.strip():
            new_lines.append(line)
            continue
        row = json.loads(line)
        slept, tries = 0.0, []
        for c in row.get("calls") or []:
            if c.get("kind") != "chat":
                continue
            for a in c.get("attempts") or []:
                if a.get("outcome") != "timeout" or a["seconds"] <= float(c["timeout_s"]):
                    continue
                start = stamp(a["started_at"])
                logged = inside(intervals, start, start + a["seconds"])
                if logged < a["seconds"] - float(c["timeout_s"]):
                    continue
                slept += a["seconds"]
                a["machine_asleep"] = True
                try:
                    u = (json.loads(a.get("stdout") or "").get("usage")) or {}
                    usage = {k: u.get(k) for k in ("input_tokens", "cache_creation_input_tokens",
                                                   "cache_read_input_tokens", "output_tokens")}
                except ValueError:
                    usage = None
                tries.append({"try": a["n"], "started_at": a["started_at"],
                              "recorded_seconds": a["seconds"], "timeout_s": c["timeout_s"],
                              "low_power_seconds_the_machine_logged_inside_it": logged,
                              "a_whole_reply_had_come_back": usage is not None,
                              "tokens_of_the_discarded_reply": usage})
        if not slept:
            new_lines.append(line)
            continue
        where = f"arm_outputs.jsonl row {n} ({row['id']})"
        g, t = row["generator"], row["timing"]
        recorded = {"generator.time_s": g["time_s"], "generator.retry_s": g["retry_s"],
                    "timing.wall_s": t["wall_s"]}
        g["time_s"], g["retry_s"], t["wall_s"] = g["time_s"] - slept, g["retry_s"] - slept, t["wall_s"] - slept
        corrected = {"generator.time_s": g["time_s"], "generator.retry_s": g["retry_s"],
                     "timing.wall_s": t["wall_s"]}
        for field in recorded:
            changes.append({"where": where, "field": field, "recorded": recorded[field],
                            "corrected": corrected[field], "taken_out": slept})
        row["correction"] = {"rule": RULE, "taken_out_s": slept, "recorded": recorded,
                             "corrected": corrected, "slept_tries": tries,
                             "see": "corrections.json, arm_outputs.as_recorded.jsonl"}
        for item in tries:
            lost.append({"question_id": row["id"], "row": n, **item})
        per_leg[row.get("leg")] = per_leg.get(row.get("leg"), 0.0) + slept
        new_lines.append(json.dumps(row, ensure_ascii=False, default=repr).encode("utf-8"))

    man = json.loads(src_man.read_text(encoding="utf-8"))
    as_recorded = {"arm_outputs.jsonl": sha(src_rows), "run_manifest.json": sha(src_man)}
    for leg in man.get("legs") or []:
        out = per_leg.get(leg.get("leg"))
        if out:
            changes.append({"where": f"run_manifest.json legs[leg={leg['leg']}]", "field": "wall_s",
                            "recorded": leg["wall_s"], "corrected": leg["wall_s"] - out, "taken_out": out})
            leg["correction"] = {"rule": RULE, "taken_out_s": out,
                                 "recorded": {"wall_s": leg["wall_s"]},
                                 "corrected": {"wall_s": leg["wall_s"] - out},
                                 "sha256_of_the_files_as_recorded": as_recorded,
                                 "see": "corrections.json; started_at and finished_at are clock times"}
            leg["wall_s"] = leg["wall_s"] - out

    # the judging: low-power intervals the machine logged while a judge call was under way
    judging = []
    calls_path = d / "eval_calls.jsonl"
    if calls_path.is_file():
        for line in calls_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            c = json.loads(line)
            if c.get("kind") != "chat" or not c.get("started_at") or not c.get("finished_at"):
                continue
            s, e = stamp(c["started_at"]), stamp(c["finished_at"])
            logged = inside(intervals, s, e)
            if logged > 0:
                judging.append({"question_id": c.get("question_id"), "score": c.get("score"),
                                "started_at": c["started_at"], "finished_at": c["finished_at"],
                                "tries": [(a["n"], a["outcome"], a["seconds"]) for a in c.get("attempts") or []],
                                "low_power_seconds_the_machine_logged_inside_it": logged})

    print(f"{d.name}")
    print("low-power intervals the machine logged:")
    for a, b, what in intervals:
        print(f"   {iso(a)[:23]}Z -> {iso(b)[:23]}Z  {b - a:>10,.1f} s  {what}")
    print(f"tries the machine slept under: {len(lost)} | seconds taken out {sum(per_leg.values()):,.3f}")
    for item in lost:
        u = item["tokens_of_the_discarded_reply"] or {}
        print(f"   row {item['row']} {item['question_id']} try {item['try']}: started {item['started_at'][:19]}Z, recorded {item['recorded_seconds']:,.3f} s "
              f"against a timeout of {item['timeout_s']:.0f} s, logged low power inside it {item['low_power_seconds_the_machine_logged_inside_it']:,.3f} s | "
              f"a whole reply had come back: {item['a_whole_reply_had_come_back']} (in {u.get('input_tokens')} + cache_creation {u.get('cache_creation_input_tokens')}, out {u.get('output_tokens')})")
    for c in changes:
        print(f"   {c['where']} · {c['field']}: {c['recorded']:,.3f} -> {c['corrected']:,.3f}")
    print(f"judge calls with logged low-power time inside them (no change made): {len(judging)}")
    for j in judging:
        print(f"   {j['question_id']} {j['score']}: {j['started_at'][11:23]} -> {j['finished_at'][11:23]} tries {[(n, o, round(s, 1)) for n, o, s in j['tries']]} "
              f"| logged low power inside {j['low_power_seconds_the_machine_logged_inside_it']:.1f} s")
    if not changes:
        print("nothing to correct")
        return
    if not args.write:
        print("(nothing written; --write does it)")
        return

    if not kept_rows.exists():
        shutil.copy2(rows_path, kept_rows)
        shutil.copy2(man_path, kept_man)
    assert sha(kept_rows) == as_recorded["arm_outputs.jsonl"] and sha(kept_man) == as_recorded["run_manifest.json"]
    tmp = rows_path.with_name(rows_path.name + ".tmp")
    tmp.write_bytes(b"\n".join(new_lines))
    tmp.replace(rows_path)
    tmp = man_path.with_name(man_path.name + ".tmp")
    tmp.write_text(json.dumps(man, ensure_ascii=False, indent=2, default=repr), encoding="utf-8")
    tmp.replace(man_path)
    (d / "machine_sleep_events.txt").write_text(events_text, encoding="utf-8")
    if Path(__file__).resolve().parent != d.resolve():
        shutil.copy2(__file__, d / "correct_slept_tries.py")
    (d / "corrections.json").write_text(json.dumps({
        "made_at": datetime.now(timezone.utc).isoformat(),
        "ordered_by": HIS_WORDS,
        "what_happened": "The laptop's lid was closed while the answers were being made. Two answer "
                         "calls were under way, one after the other. Each was cut as a timeout when the "
                         "laptop woke, although its reply had come back, and was asked again. The second "
                         "reply is the answer that was kept and judged. No answer, context or score is "
                         "changed by this correction: only times.",
        "rule": {"id": RULE, "text": __doc__.split("Rule \"slept-try/1\".")[1].split("Not changed:")[0].strip()},
        "not_changed_and_worth_knowing": [
            "generator.attempts is 2 and generator.calls is 1 in these rows: two requests were made "
            "and paid for, one answer was kept.",
            "The tokens of the discarded reply are listed under slept_tries. They are not part of the "
            "row's token counts, which are those of the try that answered.",
            "The try that answered read the prompt from the cache the first try had written "
            "(generator.cached_input_tokens), which no other row of this run does.",
            "started_at, finished_at and answered_at are clock times and have the sleep between them.",
        ],
        "slept_tries": lost,
        "changes": changes,
        "judge_calls_with_logged_low_power_time_inside_them": {
            "note": "No change is made to these. Whether the call was held while the machine was in "
                    "this state is not known from the record, so its seconds stand as recorded.",
            "calls": judging},
        "low_power_intervals_the_machine_logged": [
            {"start": iso(a), "end": iso(b), "seconds": b - a, "what": what} for a, b, what in intervals],
        "files": {name: {"sha256_as_recorded": as_recorded[name], "sha256_corrected": sha(d / name),
                         "as_recorded_copy": kept.name}
                  for name, kept in (("arm_outputs.jsonl", kept_rows), ("run_manifest.json", kept_man))},
        "evidence": "machine_sleep_events.txt (Windows' System log, Kernel-Power and Power-Troubleshooter, in UTC)",
        "script": "correct_slept_tries.py, in this folder; run on the files as recorded it gives these files again",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    old, new = kept_rows.read_bytes().split(b"\n"), rows_path.read_bytes().split(b"\n")
    same = sum(1 for a, b in zip(old, new) if a == b)
    print(f"written. Lines of arm_outputs.jsonl identical to the recorded file: {same} of {len(old)}; changed: {len(old) - same}")
    print(f"kept as recorded: {kept_rows.name} (sha256 {as_recorded['arm_outputs.jsonl'][:16]}), {kept_man.name} (sha256 {as_recorded['run_manifest.json'][:16]})")


if __name__ == "__main__":
    main()

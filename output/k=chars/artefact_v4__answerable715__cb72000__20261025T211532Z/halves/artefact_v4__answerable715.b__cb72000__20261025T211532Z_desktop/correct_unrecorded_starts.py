"""Give run_manifest.json an entry in legs for every start of the run that wrote rows and no entry,
from that start's own log, and give each row and failure the number of the start that wrote it;
say exactly what was changed.

    python tools/correct_unrecorded_starts.py record <log> [<log> ...] --out <starts.json>
    python tools/correct_unrecorded_starts.py <run folder> <starts.json> [--write]

`record` runs on the machine that ran the starts: it writes, for each log (a start's command
output, the run's command written into it by the command line that launched the start), its name,
sha256 and the times the file system holds for it (created, last written; UTC), since a copy of a
file keeps neither. Without --write the correction only prints what it would change and what it
checked. A start writes its entry in legs when it ends; a start whose process was stopped, or whose
machine stopped, wrote none, while the rows it answered are in arm_outputs.jsonl, each carrying the
number the start gave itself (the number of entries written before it, plus one), the same number
as the next start that did write one. The correction keeps the files as recorded as
arm_outputs.as_recorded.jsonl, failures.as_recorded.jsonl and run_manifest.as_recorded.json on the
first write of any correction, never changed after, and the logs and starts.json under starts/.

Rule "unrecorded-starts/1".
  1. A start is one log of starts.json: it began when its log was created and ended before the
     next start's log was created. A written entry belongs to the start whose span holds its
     started_at; each start holds at most one.
  2. A row belongs to the start whose span holds its timing.finished_at, a failure to the one whose
     span holds its failed_at, and must carry the number that start gave itself (rule above);
     otherwise nothing is written. The rows a start with an entry answered must be its n_answered.
  3. A start with no entry gets one: started_at the creation of its log, finished_at its last
     write, workers the number its log's first line names, n_answered its rows, aborted how its
     log ends (a process stopped from outside writes "exit -1" or no exit line), and from_its_log:
     the log, its embedder device and its last lines that name no question. Every other field of
     an entry is empty: not recorded.
  4. The entries are numbered again in the order of their starts; each row's and failure's leg is
     the new number of its start. No other value changes.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RULE = "unrecorded-starts/1"
SCRIPT = "correct_unrecorded_starts.py"
HIS_WORDS = ("\"resume and finish them, make sure they are all finished, correct, complete with all data, "
             "metadata and so on\" (2026-10-26)")
REPO = Path(__file__).resolve().parents[1]
# the arms are in prod/ and test/: FIELDS.md takes an arm's own words from its file
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
QUESTION = re.compile(r"[A-Za-z]+::[a-z]::\d+")
HEAD = re.compile(r"\| (\d+) workers \|")
DEVICE = re.compile(r"^embedder: loading .* on (\w+) \(")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


def at(s):
    return datetime.fromisoformat(s)


def record(args):
    out = []
    for p in args.logs:
        st = os.stat(p)
        out.append({"log": Path(p).name, "sha256": sha(p), "created": utc(st.st_ctime),
                    "last_written": utc(st.st_mtime), "bytes": st.st_size})
    out.sort(key=lambda x: x["created"])
    Path(args.out).write_text(json.dumps({"recorded_at": utc(datetime.now().timestamp()),
                                          "host": os.environ.get("COMPUTERNAME"), "starts": out},
                                         ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(out)} logs -> {args.out}")


def lines(path):
    return [x.rstrip("\n") for x in Path(path).read_text(encoding="utf-8").splitlines()]


def log_facts(path):
    text = Path(path).read_text(encoding="utf-8", errors="replace").replace("\r", "\n")
    plain = [x for x in text.splitlines() if x.strip() and not QUESTION.search(x)]
    workers = next((int(m.group(1)) for x in plain for m in [HEAD.search(x)] if m), None)
    device = next((m.group(1) for x in plain for m in [DEVICE.match(x)] if m), None)
    ends = [x for x in plain if not x.startswith(("Loading weights", "answering", "scoring"))][-3:]
    exit_line = next((x.strip() for x in reversed(plain) if x.strip().startswith("exit ")), None)
    return workers, device, ends, exit_line


def corrected(d, starts_file):
    d = Path(d)
    starts = json.loads(Path(starts_file).read_text(encoding="utf-8"))["starts"]
    logs_dir = Path(starts_file).parent
    for s in starts:
        if sha(logs_dir / s["log"]) != s["sha256"]:
            raise SystemExit(f"{s['log']}: not the file starts.json names")
    man = json.loads((d / "run_manifest.json").read_text(encoding="utf-8"))
    legs = man.get("legs") or []
    spans = [(at(s["created"]), at(starts[i + 1]["created"]) if i + 1 < len(starts) else None)
             for i, s in enumerate(starts)]

    def start_of(moment):
        t = at(moment)
        hits = [i for i, (a, b) in enumerate(spans) if a <= t and (b is None or t < b)]
        return hits[0] if len(hits) == 1 else None

    owner = {}
    for leg in legs:
        i = start_of(leg["started_at"])
        if i is None or i in owner:
            raise SystemExit(f"leg {leg['leg']} (started {leg['started_at']}): not in exactly one start's span, "
                             "or a start holds two entries")
        owner[i] = leg
    # the number each start gave itself: the entries written before it, plus one
    own_number = {i: 1 + sum(1 for j in owner if j < i) for i in range(len(starts))}
    rows_path, fail_path = d / "arm_outputs.jsonl", d / "failures.jsonl"
    rows = [json.loads(x) for x in lines(rows_path) if x.strip()]
    fails = [json.loads(x) for x in lines(fail_path) if x.strip()] if fail_path.exists() else []
    belongs, wrong = {}, []
    for kind, recs, moment in (("row", rows, lambda r: r["timing"]["finished_at"]),
                               ("failure", fails, lambda r: r["failed_at"])):
        for n, r in enumerate(recs):
            i = start_of(moment(r))
            if i is None or r.get("leg") != own_number[i]:
                wrong.append(f"{kind} {n} ({r.get('id')}): leg {r.get('leg')}, written {moment(r)}")
            belongs[(kind, n)] = i
    if wrong:
        raise SystemExit("rows or failures not in the start that carries their number; nothing written:\n  "
                         + "\n  ".join(wrong[:10]))
    answered = {i: sum(1 for (k, n), j in belongs.items() if k == "row" and j == i) for i in range(len(starts))}
    differ = {owner[i]["leg"]: [owner[i].get("n_answered"), answered[i]] for i in owner
              if answered[i] != owner[i].get("n_answered")}
    checks = [{"what": "each written entry's n_answered is the rows of its start", "holds": not differ,
               "looked_at": len(owner), **({"differs": differ} if differ else {})}]
    if differ:
        raise SystemExit(f"a written entry's n_answered is not its start's rows: {differ}")
    wrote = {i for (k, n), i in belongs.items()}
    missing = [i for i in range(len(starts)) if i not in owner and i in wrote]
    idle = [i for i in range(len(starts)) if i not in owner and i not in wrote]
    keys = sorted({k for leg in legs for k in leg})
    new_legs, changes, number = [], [], {}
    for i, s in enumerate(starts):
        if i in owner:
            entry = dict(owner[i])
        elif i in missing:
            workers, device, ends, exit_line = log_facts(logs_dir / s["log"])
            how = ("its log ends in \"exit -1\": the process was stopped from outside" if exit_line == "exit -1"
                   else f"its log ends in \"{exit_line}\"" if exit_line
                   else "its log has no exit line: the process, or its machine, stopped before it wrote one")
            entry = dict.fromkeys(keys)
            entry.update(started_at=s["created"], finished_at=s["last_written"], workers=workers,
                         n_answered=answered[i], aborted=f"the start wrote no entry; {how}",
                         from_its_log={"log": f"starts/{s['log']}", "embedder_device": device,
                                       "last_lines": ends, "rule": RULE})
        else:
            continue
        number[i] = len(new_legs) + 1
        old = entry.get("leg")
        entry["leg"] = number[i]
        new_legs.append(entry)
        if i in missing:
            changes.append({"where": "run_manifest.json legs", "field": f"the entry of the start of {s['created']}",
                            "recorded": None, "corrected": entry})
        elif old != number[i]:
            changes.append({"where": "run_manifest.json legs", "field": f"the entry of the start of {s['created']}: leg",
                            "recorded": old, "corrected": number[i]})
    for kind, recs, path in (("row", rows, "arm_outputs.jsonl"), ("failure", fails, "failures.jsonl")):
        for n, r in enumerate(recs):
            new = number[belongs[(kind, n)]]
            if r.get("leg") != new:
                changes.append({"where": f"{path} line {n} ({r.get('id')})", "field": "leg",
                                "recorded": r.get("leg"), "corrected": new})
                r["leg"] = new
    new_man = dict(man, legs=new_legs)
    checks.append({"what": "every row and failure is in one start's span and carries that start's own number",
                   "holds": True, "looked_at": len(rows) + len(fails)})
    checks.append({"what": "starts with no entry, no row and no failure (left out: they wrote nothing)",
                   "holds": True, "looked_at": len(idle), "starts": [starts[i]["log"] for i in idle]})
    return man, new_man, rows, fails, changes, checks, missing, starts


def write_jsonl(path, recs, raw):
    text = "".join(json.dumps(r, ensure_ascii=False, default=repr) + "\n" for r in recs)
    if b"\r\n" in raw:
        text = text.replace("\n", "\r\n")
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    tmp.replace(path)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "record":
        p = argparse.ArgumentParser()
        p.add_argument("cmd")
        p.add_argument("logs", nargs="+")
        p.add_argument("--out", required=True)
        record(p.parse_args())
        return
    p = argparse.ArgumentParser()
    p.add_argument("run")
    p.add_argument("starts")
    p.add_argument("--write", action="store_true")
    args = p.parse_args()
    d = Path(args.run)
    man, new_man, rows, fails, changes, checks, missing, starts = corrected(d, args.starts)
    print(f"{d.name}: {len(starts)} starts in starts.json, {len(man.get('legs') or [])} entries in legs, "
          f"{len(missing)} starts that wrote rows and no entry")
    for c in changes:
        if c["field"].startswith("the entry") and isinstance(c["corrected"], dict):
            e = c["corrected"]
            print(f"  new entry {e['leg']}: started {e['started_at']}, ended {e['finished_at']}, {e['workers']} workers, "
                  f"{e['n_answered']} rows, embedder {e['from_its_log']['embedder_device']}; {e['aborted']}")
    moved = sum(1 for c in changes if c["field"] == "leg")
    print(f"  {moved} rows and failures get another leg number; "
          f"{sum(1 for c in changes if c['field'].endswith(': leg'))} written entries are numbered again")
    for c in checks:
        print(f"  check {'holds' if c['holds'] else 'DOES NOT HOLD'}: {c['what']} (looked at {c['looked_at']})")
    if not missing:
        print("nothing to correct")
        return
    if not args.write:
        print("  (nothing written; --write does it)")
        return
    files = {}
    for name, new in (("arm_outputs.jsonl", rows), ("failures.jsonl", fails)):
        path = d / name
        raw = path.read_bytes()
        before = sha(path)
        kept = d / name.replace(".jsonl", ".as_recorded.jsonl")
        if not kept.exists():
            shutil.copy2(path, kept)
        write_jsonl(path, new, raw)
        files[name] = {"sha256_before": before, "sha256_corrected": sha(path), "as_recorded": kept.name}
    path = d / "run_manifest.json"
    raw = path.read_bytes()
    before = sha(path)
    kept = d / "run_manifest.as_recorded.json"
    if not kept.exists():
        shutil.copy2(path, kept)
    text = json.dumps(new_man, ensure_ascii=False, indent=2, default=repr)
    if b"\r\n" in raw:
        text = text.replace("\n", "\r\n")
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    tmp.replace(path)
    files["run_manifest.json"] = {"sha256_before": before, "sha256_corrected": sha(path), "as_recorded": kept.name}
    ev_dir = d / "starts"
    ev_dir.mkdir(exist_ok=True)
    src = Path(args.starts).parent
    for s in starts:
        if not (ev_dir / s["log"]).exists():
            shutil.copy2(src / s["log"], ev_dir / s["log"])
    if Path(args.starts).resolve() != (ev_dir / "starts.json").resolve():
        shutil.copy2(args.starts, ev_dir / "starts.json")
    if Path(__file__).resolve() != (d / SCRIPT).resolve():
        shutil.copy2(__file__, d / SCRIPT)
    earlier = (json.loads((d / "corrections.json").read_text(encoding="utf-8"))["corrections"]
               if (d / "corrections.json").exists() else [])
    entry = {
        "made_at": datetime.now(timezone.utc).isoformat(),
        "ordered_by": HIS_WORDS,
        "what_happened": (f"{len(missing)} starts of the run answered questions and wrote no entry in legs: their "
                          "processes were stopped, or their machine stopped, before they ended. Their rows carried "
                          "the number of the next start that wrote an entry, so legs named fewer starts than wrote "
                          "rows and gave those rows another start's settings."),
        "rule": {"id": RULE, "text": __doc__.split(f'Rule "{RULE}".', 1)[1].strip()},
        "not_changed_and_worth_knowing": [
            "A rebuilt entry's started_at is when its command was launched (its log's creation), before the "
            "harness began; a written entry's started_at is when the harness began.",
            "A rebuilt entry's code, flags, switches and settings are not recorded and stay empty; the rows' own "
            "call records hold the device each embedding ran on.",
            "No answer, context, score, call record or time changes.",
        ],
        "changes": changes,
        "checks": checks,
        "evidence": {"starts": "starts/starts.json", "logs": [f"starts/{s['log']}" for s in starts]},
        "files": files,
        "script": f"{SCRIPT}, in this folder",
    }
    (d / "corrections.json").write_text(json.dumps({"corrections": earlier + [entry]},
                                                   ensure_ascii=False, indent=2), encoding="utf-8")
    from harness import fields
    fields.write(d, stamp_files=True)
    print(f"written: {len(missing)} entries in legs, {moved} leg numbers; corrections.json, starts/, {SCRIPT}")


if __name__ == "__main__":
    main()

"""Give each question's search time the time its retrieval takes with one question at a time on one
machine; say exactly what was changed.

    python tools/correct_search_time.py <run folder> <re-made run folder> [--first-warm <warm run folder>] [--write]

The re-made run is the run's retrieval made again with prod/run.py --workers 1 --retrieval-only, on the
laptop, with no model call (the baselines make none; the artefact reads each first call's answer from
the run's own store, HERB_V4_OFFLINE=on). Without --write it only prints what it would change. It keeps
the rows as recorded as arm_outputs.as_recorded.jsonl on the first write of any correction, never
changed after.

Rule "search-time/2".
  1. The re-made run holds the run's questions, each once, and each question's retrieval in it hands
     over the same records as in the run: the same contexts and record ids, as many of each. A
     question whose records come in another order is named in the check, with the first rank at which
     the order differs.
  2. Each row gets search_time_s = the re-made row's search_time_s; its timing.wall_s changes by the
     same amount.
  3. Each row's embed entry in retrieval gets wait_s = 0: the time the question waited for the
     embedder's lock while other questions of the run embedded; its time_s and the row's
     timing.wall_s lose the same amount. No answer, context, score, token count or other time changes.
  4. The question that was the first of the re-made run's process, which also made the process's
     first loads and graph queries, gets its search_time_s from a warm run (--first-warm): the same
     retrieval, made second in a fresh process after the re-made run's second question; that other
     question's time is not used. Its timing.wall_s changes by the same amount. A run whose rules 1
     to 3 are already written gets rule 4 alone.
"""
import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RULE = "search-time/2"
SCRIPT = "correct_search_time.py"
HIS_WORDS = ("\"make sure it's all correctly calculated, no sloppy shit or lazy, i want the same methods for them\" "
             "(2026-10-27) · \"doit\" (2026-10-27)")
REPO = Path(__file__).resolve().parents[1]
# the arms are in prod/ and test/: FIELDS.md takes an arm's own words from its file
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def entry_for(d, rows_path, before, kept, what, changes, checks, evidence, worth_knowing):
    earlier = (json.loads((d / "corrections.json").read_text(encoding="utf-8"))["corrections"]
               if (d / "corrections.json").exists() else [])
    entry = {
        "made_at": datetime.now(timezone.utc).isoformat(),
        "ordered_by": HIS_WORDS,
        "what_happened": what,
        "rule": {"id": RULE, "text": __doc__.split(f'Rule "{RULE}".', 1)[1].strip()},
        "not_changed_and_worth_knowing": worth_knowing,
        "changes": changes,
        "checks": checks,
        "evidence": evidence,
        "files": {"arm_outputs.jsonl": {"sha256_before": before, "sha256_corrected": sha(rows_path), "as_recorded": kept.name}},
        "script": f"{SCRIPT}, in this folder",
    }
    (d / "corrections.json").write_text(json.dumps({"corrections": earlier + [entry]}, ensure_ascii=False, indent=2),
                                        encoding="utf-8")


def write_rows(d, rows_path, lines):
    before = sha(rows_path)
    kept = d / "arm_outputs.as_recorded.jsonl"
    if not kept.exists():
        shutil.copy2(rows_path, kept)
    tmp = rows_path.with_name(rows_path.name + ".tmp")
    tmp.write_bytes(b"\n".join(lines))
    tmp.replace(rows_path)
    if Path(__file__).resolve() != (d / SCRIPT).resolve():
        shutil.copy2(__file__, d / SCRIPT)
    return before, kept


def first_warm(d, r, w, write):
    """Rule 4 alone, for a run whose rules 1 to 3 are written."""
    earlier = json.loads((d / "corrections.json").read_text(encoding="utf-8"))["corrections"]
    if not any(e["rule"]["id"].startswith("search-time/") for e in earlier):
        raise SystemExit(f"{d.name}: rules 1 to 3 are not written yet")
    made = sorted(rows(r / "arm_outputs.jsonl"), key=lambda x: x["timing"]["started_at"])
    warm = sorted(rows(w / "arm_outputs.jsonl"), key=lambda x: x["timing"]["started_at"])
    man = json.loads((w / "run_manifest.json").read_text(encoding="utf-8"))
    if man.get("workers") != 1 or [x["id"] for x in warm] != [made[1]["id"], made[0]["id"]]:
        raise SystemExit(f"{w.name}: not the re-made run's second question and then its first, one at a time")
    x = warm[1]
    rows_path = d / "arm_outputs.jsonl"
    lines = rows_path.read_bytes().split(b"\n")
    changes = []
    for n, line in enumerate(lines):
        if not line.strip() or f'"id": "{x["id"]}"'.encode() not in line:
            continue
        row = json.loads(line)
        if row["id"] != x["id"]:
            continue
        if sorted(x["contexts"]) != sorted(row["contexts"]) or sorted(x["context_ids"]) != sorted(row["context_ids"]):
            raise SystemExit(f"row {n} ({row['id']}): the warm run does not hand over the same records")
        if row["search_time_s"] != made[0]["search_time_s"]:
            raise SystemExit(f"row {n} ({row['id']}): the row's search time is not the re-made run's")
        where = f"arm_outputs.jsonl row {n} ({row['id']})"
        delta = x["search_time_s"] - row["search_time_s"]
        changes += [{"where": where, "field": "search_time_s", "recorded": row["search_time_s"], "corrected": x["search_time_s"]},
                    {"where": where, "field": "timing.wall_s", "recorded": row["timing"]["wall_s"],
                     "corrected": row["timing"]["wall_s"] + delta}]
        row["search_time_s"] = x["search_time_s"]
        row["timing"]["wall_s"] += delta
        lines[n] = json.dumps(row, ensure_ascii=False, default=repr).encode("utf-8")
    if len(changes) != 2:
        raise SystemExit(f"{d.name}: not one row for the re-made run's first question")
    print(f"{d.name}: the re-made run's first question {made[0]['search_time_s']:.3f} s first in its process, "
          f"{x['search_time_s']:.3f} s second")
    if not write:
        print("  (nothing written; --write does it)")
        return
    before, kept = write_rows(d, rows_path, lines)
    entry_for(d, rows_path, before, kept,
              "The first question of the re-made run was the first in its process and also held the process's first "
              "loads and graph queries. Its search time is the time of the same retrieval made second in a fresh "
              "process, after the re-made run's second question.",
              changes,
              [{"what": "rule 4: the warm run made the re-made run's second question and then its first, one at a time, "
                        "and hands over the same records for it", "holds": True, "looked_at": 1}],
              {"file": f"../{w.name}/arm_outputs.jsonl", "sha256": sha(w / "arm_outputs.jsonl"),
               "what": "the warm run's rows: the first question's search_time_s and contexts"},
              ["The other question of the warm run, made first in its process, is not used."])
    from harness import fields
    fields.write(d, stamp_files=True)
    print(f"written: {len(changes)} changes; corrections.json, {SCRIPT}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("run")
    p.add_argument("remade")
    p.add_argument("--first-warm")
    p.add_argument("--write", action="store_true")
    args = p.parse_args()
    d, r = Path(args.run).resolve(), Path(args.remade).resolve()
    if args.first_warm:
        return first_warm(d, r, Path(args.first_warm).resolve(), args.write)
    remade = {x["id"]: x for x in rows(r / "arm_outputs.jsonl")}
    man = json.loads((r / "run_manifest.json").read_text(encoding="utf-8"))
    if man.get("workers") != 1 or man.get("generator") is not None and man.get("generator_model"):
        raise SystemExit(f"{r.name}: not a re-made run with one worker and no answers")
    rows_path = d / "arm_outputs.jsonl"
    lines = rows_path.read_bytes().split(b"\n")
    changes, seen, before_s, after_s, waits, reordered = [], set(), 0.0, 0.0, 0.0, []
    for n, line in enumerate(lines):
        if not line.strip():
            continue
        row = json.loads(line)
        x = remade.get(row["id"])
        # rule 1: the same records handed over
        if (x is None or sorted(x["contexts"]) != sorted(row["contexts"])
                or sorted(x["context_ids"]) != sorted(row["context_ids"])):
            raise SystemExit(f"row {n} ({row['id']}): the re-made run does not hand over the same records")
        if x["contexts"] != row["contexts"] or x["context_ids"] != row["context_ids"]:
            reordered.append({"question_id": row["id"], "records": len(row["context_ids"]),
                              "first_rank_that_differs": next(i for i, (a, b) in enumerate(zip(
                                  row["contexts"], x["contexts"])) if a != b) if row["contexts"] != x["contexts"] else
                              next(i for i, (a, b) in enumerate(zip(row["context_ids"], x["context_ids"])) if a != b)})
        seen.add(row["id"])
        where = f"arm_outputs.jsonl row {n} ({row['id']})"
        delta = x["search_time_s"] - row["search_time_s"]
        changes.append({"where": where, "field": "search_time_s", "recorded": row["search_time_s"],
                        "corrected": x["search_time_s"]})
        before_s += row["search_time_s"]
        after_s += x["search_time_s"]
        row["search_time_s"] = x["search_time_s"]
        for e in row["retrieval"]:
            if e["kind"] == "embed" and e["wait_s"]:
                changes.append({"where": where, "field": "retrieval.embed.wait_s", "recorded": e["wait_s"], "corrected": 0.0})
                changes.append({"where": where, "field": "retrieval.embed.time_s", "recorded": e["time_s"],
                                "corrected": e["time_s"] - e["wait_s"]})
                delta -= e["wait_s"]
                waits += e["wait_s"]
                e["time_s"] -= e["wait_s"]
                e["wait_s"] = 0.0
        changes.append({"where": where, "field": "timing.wall_s", "recorded": row["timing"]["wall_s"],
                        "corrected": row["timing"]["wall_s"] + delta})
        row["timing"]["wall_s"] += delta
        lines[n] = json.dumps(row, ensure_ascii=False, default=repr).encode("utf-8")
    if seen != set(remade):
        raise SystemExit(f"{r.name} holds other questions than {d.name}")
    print(f"{d.name}: {len(seen)} questions, search {before_s:.1f} s as run, {after_s:.1f} s one question at a time; "
          f"embedder lock waits taken out {waits:.1f} s; the same records in another order: {len(reordered)}")
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
    if Path(__file__).resolve() != (d / SCRIPT).resolve():
        shutil.copy2(__file__, d / SCRIPT)
    earlier = (json.loads((d / "corrections.json").read_text(encoding="utf-8"))["corrections"]
               if (d / "corrections.json").exists() else [])
    entry = {
        "made_at": datetime.now(timezone.utc).isoformat(),
        "ordered_by": HIS_WORDS,
        "what_happened": ("The run answered several questions at once in one process, and a question's search, Python "
                          "work in a thread, waited for the others: its time grew with the number of questions under way. "
                          "Each question's search time is the time of the same retrieval made again with one question at a "
                          "time on the laptop, with no model call; a question's wait for the embedder's lock is out."),
        "rule": {"id": RULE, "text": __doc__.split(f'Rule "{RULE}".', 1)[1].strip()},
        "not_changed_and_worth_knowing": [
            "The re-made run's own embedding and first-call times are not used: the query embeddings keep their "
            "graphics-card times and the first calls their server times.",
            f"The re-made run is {r.name}, in output/k=chars; its run_manifest.json names its commit and machine.",
        ],
        "changes": changes,
        "checks": [{"what": "rule 1: each question's re-made retrieval hands over the same records, as many of each",
                    "holds": True, "looked_at": len(seen),
                    "the_same_records_in_another_order": reordered}],
        "evidence": {"file": f"../{r.name}/arm_outputs.jsonl", "sha256": sha(r / "arm_outputs.jsonl"),
                     "what": "the re-made run's rows: each question's search_time_s and contexts"},
        "files": {"arm_outputs.jsonl": {"sha256_before": before, "sha256_corrected": sha(rows_path), "as_recorded": kept.name}},
        "script": f"{SCRIPT}, in this folder",
    }
    (d / "corrections.json").write_text(json.dumps({"corrections": earlier + [entry]}, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    from harness import fields
    fields.write(d, stamp_files=True)
    print(f"written: {len(changes)} changes; corrections.json, {SCRIPT}")


if __name__ == "__main__":
    main()

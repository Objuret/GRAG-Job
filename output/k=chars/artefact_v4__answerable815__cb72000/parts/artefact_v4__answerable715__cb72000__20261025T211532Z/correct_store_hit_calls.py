"""Give a row whose first call the run read from its own first-call store the record of that call,
as the store kept it when the call was asked; say exactly what was changed.

    python tools/correct_store_hit_calls.py <run folder> <store> [<store> ...] [--write]

Each store is a first-call store of the run (HERB_V4_CACHE: a new, empty one for each run, so every
answer in it was asked by a start of this run), the folder that holds <stage>/<key>.json. Without
--write it only prints what it would change and what it checked. A start that asked a first call
and was stopped before it wrote the question's row left the answer in the store; the start that
wrote the row read the answer from there, which the arm counts as no call (its index_info,
"first_call"), so the row held no record and no cost of the call that its answer rests on. The
store keeps, with each answer, the lane's record of the call that gave it (response.call). It keeps
the rows as recorded as arm_outputs.as_recorded.jsonl on the first write of any correction, never
changed after, and the records it gives as first_call_records.jsonl.

Rule "store-hit-calls/1".
  1. A row is corrected when every stage of its first call (meta.interpreter.stages) was read from
     the store (cache_hit) and the row holds no call record of a language model but the answer
     call's.
  2. Each stage's record is the store's <stage>/<key>.json, whose signature has the key as its
     sha256 and whose answer is ok; the record of the call is its response.call. It must be the
     record a row holds when it asks: on every row that asked its own first call, the store's
     response.call is the row's record of that call, the capture's seq left out; otherwise nothing
     is written.
  3. The records go first in the row's calls, in the order of the stages, as a call that asked
     them goes; every record's seq is its place again. The row's retrieval is counted again from
     its records, as the harness counts it (harness.capture.usage_by_model, the answer call left
     out); it must hold the row's other entries as they were.
  4. timing.wall_s stays as recorded: it is the span of the start that wrote the row, and the call
     was made before it, by another start. No answer, context, score or other value changes.
"""
import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RULE = "store-hit-calls/1"
SCRIPT = "correct_store_hit_calls.py"
EVIDENCE = "first_call_records.jsonl"
HIS_WORDS = ("\"we literally have ALL THE FUCKING DATA possibly available! From tokens in/out, times, stamps, "
             "DATAPOINTERS and so on and on and on.. YOU just have to make fucking sure that is KEPT every "
             "run..\" (2026-10-07) · \"resume and finish them, make sure they are all finished, correct, "
             "complete with all data, metadata and so on\" (2026-10-26)")
REPO = Path(__file__).resolve().parents[1]
# the arms are in prod/ and test/: FIELDS.md takes an arm's own words from its file
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def key_of(signature):
    return hashlib.sha256(json.dumps(signature, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def stored(stores, stage, key):
    hits = [s / stage / f"{key}.json" for s in stores if (s / stage / f"{key}.json").is_file()]
    if len(hits) != 1:
        raise SystemExit(f"{stage}/{key}: in {len(hits)} of the stores, not one; nothing written")
    rec = json.loads(hits[0].read_text(encoding="utf-8"))
    if key_of(rec["signature"]) != key or not rec.get("ok"):
        raise SystemExit(f"{stage}/{key}: its signature is not its key, or its answer is not ok; nothing written")
    return rec, hits[0]


def model_records(row):
    return [c for c in row.get("calls") or [] if c.get("kind") == "chat" and c.get("role") != "answer"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("run")
    p.add_argument("stores", nargs="+")
    p.add_argument("--write", action="store_true")
    args = p.parse_args()
    from harness import capture
    d, stores = Path(args.run), [Path(s) for s in args.stores]
    rows_path = d / "arm_outputs.jsonl"
    raw = rows_path.read_bytes()
    rows = [json.loads(x) for x in raw.decode("utf-8").splitlines() if x.strip()]
    asked_same = asked_differ = asked_skipped = 0
    changes, evidence, corrected, zero = [], [], 0, 0
    for n, row in enumerate(rows):
        stages = row["meta"]["interpreter"]["stages"]
        mine = model_records(row)
        if not all(s.get("cache_hit") for s in stages):
            # rule 2's check: a row that asked: the store's record of its last stage is the row's own
            if len(mine) != len(stages):
                asked_skipped += 1
                continue
            for s, c in zip(stages, mine):
                rec, _ = stored(stores, s["stage"], s["key"])
                same = rec["response"]["call"] == {k: v for k, v in c.items() if k != "seq"}
                asked_same += same
                asked_differ += not same
            continue
        if mine:
            raise SystemExit(f"row {n} ({row['id']}): read its first call from the store and holds a call "
                             "record of a language model; nothing written")
        records = []
        for s in stages:
            rec, path = stored(stores, s["stage"], s["key"])
            records.append(rec["response"]["call"])
            evidence.append({"id": row["id"], "stage": s["stage"], "key": s["key"],
                             "store_file": f"{path.parent.parent.name}/{s['stage']}/{path.name}",
                             "record": rec})
            u = rec["response"]["call"].get("usage") or {}
            zero += not (u.get("prompt_tokens") or u.get("completion_tokens"))
        before = row["retrieval"]
        old = row["calls"]
        new_calls = [dict(r, seq=i) for i, r in enumerate(records)] + [
            dict(c, seq=len(records) + i) for i, c in enumerate(old)]
        new_retrieval = capture.usage_by_model([c for c in new_calls if c.get("role") != "answer"])
        kept = [e for e in new_retrieval if e["kind"] != "chat"]
        if kept != [e for e in before if e["kind"] != "chat"] or any(e["kind"] == "chat" for e in before):
            raise SystemExit(f"row {n} ({row['id']}): its other retrieval entries do not count again as they "
                             "were; nothing written")
        where = f"arm_outputs.jsonl row {n} ({row['id']})"
        for i, r in enumerate(records):
            changes.append({"where": where, "field": f"calls[{i}]", "recorded": None,
                            "corrected": f"the store's record of {stages[i]['stage']}/{stages[i]['key']} "
                                         f"({EVIDENCE})"})
        for i, c in enumerate(old):
            changes.append({"where": where, "field": f"calls[{len(records) + i}].seq", "recorded": c.get("seq"),
                            "corrected": len(records) + i})
        changes.append({"where": where, "field": "retrieval", "recorded": before, "corrected": new_retrieval})
        row["calls"], row["retrieval"] = new_calls, new_retrieval
        corrected += 1
    checks = [
        {"what": "rule 2: on every row that asked its own first call, the store's response.call is the row's "
                 "record of that call, the capture's seq left out",
         "holds": asked_differ == 0 and asked_same > 0, "looked_at": asked_same + asked_differ,
         "rows_asked_more_than_once_left_out_of_the_check": asked_skipped},
        {"what": "the restored records whose usage holds 0 tokens in and 0 out", "holds": zero == 0,
         "looked_at": len(evidence), "with_0_tokens": zero},
    ]
    print(f"{d.name}: {corrected} rows read their first call from the store and get its record; "
          f"{len(evidence)} records")
    for c in checks:
        print(f"  check {'holds' if c['holds'] else 'DOES NOT HOLD'}: {c['what']} (looked at {c['looked_at']})")
    if asked_differ or not asked_same:
        raise SystemExit("rule 2 does not hold; nothing written")
    if not corrected:
        print("nothing to correct")
        return
    if not args.write:
        print("  (nothing written; --write does it)")
        return
    before_sha = sha(rows_path)
    kept_path = d / "arm_outputs.as_recorded.jsonl"
    if not kept_path.exists():
        shutil.copy2(rows_path, kept_path)
    text = "".join(json.dumps(r, ensure_ascii=False, default=repr) + "\n" for r in rows)
    if b"\r\n" in raw:
        text = text.replace("\n", "\r\n")
    tmp = rows_path.with_name(rows_path.name + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    tmp.replace(rows_path)
    (d / EVIDENCE).write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in evidence),
                              encoding="utf-8", newline="\n")
    if Path(__file__).resolve() != (d / SCRIPT).resolve():
        shutil.copy2(__file__, d / SCRIPT)
    earlier = (json.loads((d / "corrections.json").read_text(encoding="utf-8"))["corrections"]
               if (d / "corrections.json").exists() else [])
    entry = {
        "made_at": datetime.now(timezone.utc).isoformat(),
        "ordered_by": HIS_WORDS,
        "what_happened": (f"{corrected} rows read their first call's answer from the run's own store, where a start "
                          "of the run that was stopped before it wrote the row had left it; the arm counts such a "
                          "read as no call, so these rows held neither the record nor the cost of the call their "
                          "answer rests on."),
        "rule": {"id": RULE, "text": __doc__.split(f'Rule "{RULE}".', 1)[1].strip()},
        "not_changed_and_worth_knowing": [
            "A call that a start was making when it was stopped wrote no answer and no record; what it cost is "
            "in no file. Its marker, with no usage, was moved aside before the run was started again.",
            "timing.wall_s stays the span of the start that wrote the row; the restored call was made before "
            "that span, and its time is in its record and in the row's retrieval.",
            "No answer, context, score or time of the start that wrote the row changes.",
        ],
        "changes": changes,
        "checks": checks,
        "evidence": {"file": EVIDENCE, "sha256": sha(d / EVIDENCE),
                     "what": "each restored record: the row, the stage, the key, and the store's whole file"},
        "files": {"arm_outputs.jsonl": {"sha256_before": before_sha, "sha256_corrected": sha(rows_path),
                                        "as_recorded": kept_path.name}},
        "script": f"{SCRIPT}, in this folder",
    }
    (d / "corrections.json").write_text(json.dumps({"corrections": earlier + [entry]},
                                                   ensure_ascii=False, indent=2), encoding="utf-8")
    from harness import fields
    fields.write(d, stamp_files=True)
    print(f"written: {corrected} rows; corrections.json, {EVIDENCE}, {SCRIPT}")


if __name__ == "__main__":
    main()

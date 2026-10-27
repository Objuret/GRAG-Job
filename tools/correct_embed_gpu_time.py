"""Give each question's query-embedding time the time the same embeddings take on the desktop's
GTX 1080 Ti; say exactly what was changed.

    python tools/correct_embed_gpu_time.py <run folder> <gpu times json> [--all] [--write]

The GPU times are measured with the harness's own request function (harness.embed._embed_request)
and settings, on the same texts in the same input type, one call after the other in a warm
process, with HERB_EMBED_DEVICE=cuda (tools/measure_gpu_embed_times.py, with --all for --all); the
file holds, per question, each embed call's seq, its GPU seconds and, where the run kept the CPU
vector, the cosine of its vector to it. Without --write it only prints what it would change. It
keeps the rows as recorded as arm_outputs.as_recorded.jsonl on the first write of any correction,
never changed after.

Rule "embed-gpu-time/3".
  1. An embed call record that says device cpu is corrected; with --all, every embed call record,
     also one made on the graphics card while other questions of the run were under way. The
     evidence file names, per question, exactly the records of rule 1, by their seq.
  2. Each question with such records gets in its embed entry in retrieval request_s = the GPU
     seconds of its embed calls added, and time_s = request_s + wait_s + retry_s; wait_s and
     retry_s stay as recorded.
  3. The question's timing.wall_s changes by the same amount as the embed entry's request_s.
  4. Each record of rule 1 gets its GPU seconds as encode_s and device cuda. No vector, answer,
     context, score or other time changes; the vectors are the same (cosine checked).
"""
import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RULE = "embed-gpu-time/3"
SCRIPT = "correct_embed_gpu_time.py"
EVIDENCE = "gpu_embed_times.json"
EVIDENCE_ALL = "gpu_embed_times_all.json"
HIS_WORDS = ("\"ffs, redo them on the gpu\" · \"only the embeddings, because i want the true times\" "
             "(2026-10-25, on the final runs' query embeddings made on the CPU)")
HIS_WORDS_ALL = ("\"i want the same methods for them, embeddings via gpu, etc etc..\" (2026-10-27) · "
                 + HIS_WORDS)
MIN_COSINE = 0.9999
REPO = Path(__file__).resolve().parents[1]
# the arms are in prod/ and test/: FIELDS.md takes an arm's own words from its file
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("run")
    p.add_argument("times")
    p.add_argument("--all", action="store_true")
    p.add_argument("--write", action="store_true")
    args = p.parse_args()
    d = Path(args.run)
    times = json.loads(Path(args.times).read_text(encoding="utf-8"))[d.name]
    rows_path = d / "arm_outputs.jsonl"
    lines = rows_path.read_bytes().split(b"\n")
    changes, before_s, after_s = [], 0.0, 0.0
    for n, line in enumerate(lines):
        if not line.strip():
            continue
        row = json.loads(line)
        calls = [c for c in row["calls"] if c.get("kind") == "embed" and (args.all or c.get("device") == "cpu")]
        gpu = times.get(row["id"], [])
        # rule 1: the evidence names exactly the row's embed calls of rule 1; a row without any is left
        if [c["seq"] for c in calls] != [t["seq"] for t in gpu]:
            raise SystemExit(f"row {n} ({row['id']}): the GPU times are not for this row's embed calls of rule 1")
        if not calls:
            continue
        if not args.all and any(c.get("kind") == "embed" and c.get("device") != "cpu" for c in row["calls"]):
            raise SystemExit(f"row {n} ({row['id']}): the row has embed calls on another device too")
        if any((t["texts"], t["recorded_tokens_in"], t["recorded_encode_s"]) != (len(c["texts"]), c["tokens_in"], c["encode_s"])
               for c, t in zip(calls, gpu)):
            raise SystemExit(f"row {n} ({row['id']}): the GPU times were measured on other records than this row's")
        low = [t["cosine_to_stored_cpu"] for t in gpu if t.get("cosine_to_stored_cpu", 1.0) < MIN_COSINE]
        if low:
            raise SystemExit(f"row {n} ({row['id']}): a GPU vector differs from the CPU one (cosine {low[0]})")
        entry = [e for e in row["retrieval"] if e["kind"] == "embed"]
        if len(entry) != 1:
            raise SystemExit(f"row {n} ({row['id']}): not one embed entry in retrieval")
        e = entry[0]
        new = sum(t["encode_s"] for t in gpu)
        delta = new - e["request_s"]
        where = f"arm_outputs.jsonl row {n} ({row['id']})"
        for field, old, value in (("retrieval.embed.request_s", e["request_s"], new),
                                  ("retrieval.embed.time_s", e["time_s"], new + e["wait_s"] + e["retry_s"]),
                                  ("timing.wall_s", row["timing"]["wall_s"], row["timing"]["wall_s"] + delta)):
            changes.append({"where": where, "field": field, "recorded": old, "corrected": value})
        before_s += e["request_s"]
        after_s += new
        e["request_s"], e["time_s"] = new, new + e["wait_s"] + e["retry_s"]
        row["timing"]["wall_s"] += delta
        by_seq = {t["seq"]: t["encode_s"] for t in gpu}
        for i, c in enumerate(row["calls"]):
            if c.get("kind") == "embed":
                changes.append({"where": where, "field": f"calls[{i}].encode_s", "recorded": c["encode_s"],
                                "corrected": by_seq[c["seq"]]})
                changes.append({"where": where, "field": f"calls[{i}].device", "recorded": c.get("device"),
                                "corrected": "cuda"})
                c["encode_s"], c["device"] = by_seq[c["seq"]], "cuda"
        lines[n] = json.dumps(row, ensure_ascii=False, default=repr).encode("utf-8")
    print(f"{len(times)} questions: query embedding {before_s:.2f} s as recorded, {after_s:.2f} s on the GPU "
          f"one call after the other")
    if not args.write:
        print("  (nothing written; --write does it)")
        return
    evidence = EVIDENCE_ALL if args.all else EVIDENCE
    if (d / evidence).exists():
        raise SystemExit(f"{d.name}: {evidence} is already there")
    before = sha(rows_path)
    kept = d / "arm_outputs.as_recorded.jsonl"
    if not kept.exists():
        shutil.copy2(rows_path, kept)
    tmp = rows_path.with_name(rows_path.name + ".tmp")
    tmp.write_bytes(b"\n".join(lines))
    tmp.replace(rows_path)
    shutil.copy2(args.times, d / evidence)
    if Path(__file__).resolve() != (d / SCRIPT).resolve():
        shutil.copy2(__file__, d / SCRIPT)
    earlier = (json.loads((d / "corrections.json").read_text(encoding="utf-8"))["corrections"]
               if (d / "corrections.json").exists() else [])
    entry = {
        "made_at": datetime.now(timezone.utc).isoformat(),
        "ordered_by": HIS_WORDS_ALL if args.all else HIS_WORDS,
        "what_happened": (("The run embedded queries on the graphics card while other questions of the run were "
                           "under way. Each question's query-embedding time is the time the same embeddings take "
                           "on the desktop's GTX 1080 Ti one call after the other, as for the runs on the hundred.")
                          if args.all else
                          ("The run embedded queries on the CPU. Each such question's query-embedding "
                           "time is the time the same embeddings take on the desktop's GTX 1080 Ti; "
                           "the questions the run embedded on that card keep their recorded times.")),
        "rule": {"id": RULE, "text": __doc__.split(f'Rule "{RULE}".', 1)[1].strip()},
        "not_changed_and_worth_knowing": [
            "The GPU times were measured one call after the other in a warm process; the lock "
            "waits of the run (wait_s) stay as recorded.",
        ] + ([] if args.all else [
            "Questions the run embedded on the graphics card keep the times recorded then, while other "
            "questions of the run were under way at the same time."]),
        "changes": changes,
        "evidence": {"file": evidence, "sha256": sha(d / evidence),
                     "what": "per question, each embed call's GPU seconds and, where the run kept the CPU vector, "
                             "the cosine of its vector to it"},
        "files": {"arm_outputs.jsonl": {"sha256_before": before, "sha256_corrected": sha(rows_path),
                                        "as_recorded": kept.name}},
        "script": f"{SCRIPT}, in this folder",
    }
    (d / "corrections.json").write_text(json.dumps({"corrections": earlier + [entry]},
                                                   ensure_ascii=False, indent=2), encoding="utf-8")
    from harness import fields
    fields.write(d, stamp_files=True)
    print(f"written: {len(changes)} changes; corrections.json, {evidence}, {SCRIPT}")


if __name__ == "__main__":
    main()

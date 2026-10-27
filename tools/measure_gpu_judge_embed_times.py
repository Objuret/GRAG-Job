"""Measure, on the graphics card, the time each of RAGAS's own embedding requests that a run's judging made
on the CPU takes: the evidence of correction judge-embed-gpu-time (tools/correct_judge_embed_gpu_time.py).

    python tools/measure_gpu_judge_embed_times.py export <records.jsonl> <run folder> [...]
    HERB_EMBED_DEVICE=cuda python tools/measure_gpu_judge_embed_times.py measure <records.jsonl> <out.json>

export, on the machine that holds the run folders, writes each embed record of the runs' eval_calls.jsonl
that says device cpu, with its run, question, scoring start and line. measure, on the machine with the
graphics card, makes each request again with the harness's own request function
(harness.embed._embed_request), on the same texts in the same input type, one after the other in one warm
process; its time is the record's encode_s as the harness takes it (the encoding inside the lock). Nothing
is sent to a model; nothing of a run is written.
"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "prod")]
WARM = 20


def export(out, folders):
    n = 0
    with open(out, "w", encoding="utf-8") as w:
        for d in folders:
            with open(d / "eval_calls.jsonl", encoding="utf-8") as fh:
                for line_no, line in enumerate(fh):
                    if '"kind": "embed"' not in line:
                        continue
                    c = json.loads(line)
                    if c.get("kind") != "embed" or c.get("device") != "cpu":
                        continue
                    w.write(json.dumps({"run": d.name, "line": line_no, "question_id": c.get("question_id"),
                                        "eval_leg": c.get("eval_leg"), "seq": c.get("seq"), "input_type": c["input_type"],
                                        "texts": c["texts"], "encode_s": c["encode_s"], "tokens_in": c["tokens_in"],
                                        "model": c["model"], "revision": c["revision"], "dtype": c["dtype"],
                                        "batch": c["batch"]}, ensure_ascii=False) + "\n")
                    n += 1
    print(f"{n} embed records made on the CPU -> {out}")


def measure(records, out):
    if os.environ.get("HERB_EMBED_DEVICE") != "cuda":
        raise SystemExit("set HERB_EMBED_DEVICE=cuda: the times are the graphics card's")
    from harness import capture, embed
    work = [json.loads(x) for x in Path(records).read_text(encoding="utf-8").splitlines() if x.strip()]
    other = {(w["model"], w["revision"], w["dtype"], w["batch"]) for w in work} - {
        (embed.EMBED_MODEL, embed.EMBED_REVISION, embed.EMBED_DTYPE, embed.EMBED_BATCH)}
    if other:
        raise SystemExit(f"records made with another embedder setting than this harness's: {sorted(other)}")
    print(f"{len(work)} embed requests made on the CPU", flush=True)
    # a warm process: the model loaded and its kernels run before anything is timed
    for w in work[:WARM]:
        embed._embed_request(w["texts"], w["input_type"])
    times, t0 = [], time.perf_counter()
    for n, w in enumerate(work, 1):
        cap, token = capture.start()
        try:
            embed._embed_request(w["texts"], w["input_type"])
        finally:
            capture.stop(token)
        rec = cap.close()["calls"][-1]
        times.append({"run": w["run"], "line": w["line"], "question_id": w["question_id"], "eval_leg": w["eval_leg"],
                      "seq": w["seq"], "encode_s": rec["encode_s"], "recorded_encode_s": w["encode_s"],
                      "texts": len(w["texts"]), "tokens_in": rec["tokens_in"], "recorded_tokens_in": w["tokens_in"]})
        if n % 200 == 0:
            print(f"  {n}/{len(work)} requests, {time.perf_counter() - t0:.0f}s", flush=True)
    result = {"requests": times,
              "measured": {"device": embed.EMBED_DEVICE, "model": embed.EMBED_MODEL, "revision": embed.EMBED_REVISION,
                           "dtype": embed.EMBED_DTYPE, "batch": embed.EMBED_BATCH, "requests": len(work),
                           "warm_up_requests": min(WARM, len(work)),
                           "records_sha256": hashlib.sha256(Path(records).read_bytes()).hexdigest(),
                           "script": "tools/measure_gpu_judge_embed_times.py",
                           "script_sha256": hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()}}
    Path(out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"done: {len(work)} requests -> {out}", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "export":
        export(Path(sys.argv[2]), [Path(p) for p in sys.argv[3:]])
    elif sys.argv[1] == "measure":
        measure(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(__doc__)

"""Measure, on the graphics card, the time each query-embedding call a run made on the CPU takes:
the evidence file of correction embed-gpu-time (tools/correct_embed_gpu_time.py).

    HERB_EMBED_DEVICE=cuda python tools/measure_gpu_embed_times.py <run folder> <out.json> <cpu vector folder> [...]

For each row of the run's arm_outputs.jsonl, each embed call record that says device cpu is made
again with the harness's own request function (harness.embed._embed_request), on the same texts in
the same input type, one call after the other in one warm process; its time is the record's encode_s
as the harness takes it (the encoding inside the lock). Each text's vector is compared with the one
the run kept on the side on the CPU (output/query_embed_cache/<model>@<revision>__float32__cpu, the
folders given), by its cosine. Nothing is sent to a model; nothing of the run is written.
"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "prod")]
WARM = 20


def main():
    run, out, folders = Path(sys.argv[1]), Path(sys.argv[2]), [Path(p) for p in sys.argv[3:]]
    if os.environ.get("HERB_EMBED_DEVICE") != "cuda":
        raise SystemExit("set HERB_EMBED_DEVICE=cuda: the times are the graphics card's")
    from harness import capture, embed
    rows = [json.loads(x) for x in (run / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines()
            if x.strip()]
    work = [(r["id"], c) for r in rows for c in r.get("calls") or []
            if c.get("kind") == "embed" and c.get("device") == "cpu"]
    print(f"{run.name}: {len(rows)} rows, {len(work)} embed calls made on the CPU", flush=True)
    # a warm process: the model loaded and its kernels run before anything is timed
    for _, c in work[:WARM]:
        embed._embed_request(c["texts"], c["input_type"])
    times, cosines, missing = {}, [], 0
    t0 = time.perf_counter()
    for n, (qid, c) in enumerate(work, 1):
        cap, token = capture.start()
        try:
            vecs = embed._embed_request(c["texts"], c["input_type"])[0]
        finally:
            capture.stop(token)
        rec = cap.close()["calls"][-1]
        lows = []
        for text, v in zip(c["texts"], vecs):
            name = hashlib.sha256((embed.EMBED_PREFIX[c["input_type"]] + (text or " ")).encode("utf-8")).hexdigest()
            kept = next((f / f"{name}.npy" for f in folders if (f / f"{name}.npy").is_file()), None)
            if kept is None:
                missing += 1
                continue
            g = np.asarray(v, dtype=np.float64)
            k = np.load(kept).astype(np.float64)
            lows.append(float(g @ k / (np.linalg.norm(g) * np.linalg.norm(k))))
        entry = {"seq": c["seq"], "encode_s": rec["encode_s"], "recorded_encode_s": c["encode_s"],
                 "texts": len(c["texts"]), "tokens_in": rec["tokens_in"], "recorded_tokens_in": c["tokens_in"]}
        if lows:
            entry["cosine_to_stored_cpu"] = min(lows)
            cosines.append(min(lows))
        times.setdefault(qid, []).append(entry)
        if n % 200 == 0:
            print(f"  {n}/{len(work)} calls, {time.perf_counter() - t0:.0f}s", flush=True)
    result = {run.name: times,
              "measured": {"device": embed.EMBED_DEVICE, "model": embed.EMBED_MODEL,
                           "revision": embed.EMBED_REVISION, "dtype": embed.EMBED_DTYPE,
                           "calls": len(work), "warm_up_calls": min(WARM, len(work)),
                           "texts_without_a_kept_cpu_vector": missing,
                           "min_cosine_to_stored_cpu": min(cosines) if cosines else None,
                           "script": "tools/measure_gpu_embed_times.py",
                           "script_sha256": hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()}}
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"done: {len(work)} calls, min cosine {result['measured']['min_cosine_to_stored_cpu']}, "
          f"texts without a kept CPU vector {missing} -> {out}", flush=True)


if __name__ == "__main__":
    main()

"""Run the full pass shard by shard on one machine (the desktop), resumable.

Stands in for the Colab notebook's cell 4: for every `edges.shard<k>.jsonl` beside this file,
run `extract_standalone.py` for the bake-off's winning backbone into `<out>/shard<k>/`. A shard
with a finished npz is skipped; a half-done one resumes from its `.part.npz`. Python 3.10+.

    python fullcache_run.py --work A:/exjobbet/facet_pairs/fullcache_work --out A:/exjobbet/facet_pairs/fullcache
"""
import argparse
import glob
import os
import subprocess
import sys
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True, help="folder holding the extractor, the shard edge files and rows_export.jsonl.gz")
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="gte-reranker-modernbert")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--max-batch", type=int, default=8)
    a = ap.parse_args()
    shards = sorted(glob.glob(os.path.join(a.work, "edges.shard*.jsonl")))
    print("shards found:", len(shards), flush=True)
    t0 = time.time()
    for path in shards:
        k = os.path.basename(path).split("shard")[1].split(".")[0]
        d = os.path.join(a.out, "shard" + k)
        os.makedirs(d, exist_ok=True)
        done = [f for f in os.listdir(d) if f.endswith(".npz") and not f.endswith(".part.npz")]
        if done:
            print("=== shard", k, "already done", flush=True)
            continue
        print("=== shard", k, "start", time.strftime("%H:%M:%S"), flush=True)
        r = subprocess.run([sys.executable, "-u", os.path.join(a.work, "extract_standalone.py"),
                            "--edges", path, "--rows", os.path.join(a.work, "rows_export.jsonl.gz"),
                            "--out", d, "--device", a.device, "--flush", "1024",
                            "--max-batch", str(a.max_batch), "--only", a.only])
        if r.returncode != 0:
            print("SHARD", k, "FAILED rc", r.returncode, flush=True)
            return 1
        print("=== shard", k, "done", time.strftime("%H:%M:%S"),
              "| elapsed min", round((time.time() - t0) / 60, 1), flush=True)
    print("ALL SHARDS DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

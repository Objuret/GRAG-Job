"""Build the Colab bundle for the ONE full pass: the bake-off's winning backbone over every edge.

The bake-off extractor (`extract_standalone.py`) re-saves its whole store at every flush, which is
fine for 5,469 edges and would rewrite hundreds of megabytes to Drive hundreds of times at 61,018.
So the full pass is cut into shards by chunk (sha1 of the chunk id), each shard extracted into its
own folder and resumable on its own; `fullcache_merge.py` concatenates them on the laptop.

No topic value, no judge answer and no gold is put in the bundle: edges and chunk texts only.

    python test/graph/facet_pairs/fullcache_bundle.py
"""
from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROWS = ROOT / "output" / "facet_neural" / "rows_export.jsonl"
STATS = ROOT / "output" / "facet_stats" / "herb-eval-volmax.jsonl"
BAKEOFF = Path.home() / "OneDrive - Högskolan Dalarna" / "Coding" / "state-transfer" / "GRAG-Job" / "colab" / "facet_pairs_bakeoff"
BUNDLE = BAKEOFF.parent / "facet_pairs_fullcache"
WINNER = "Alibaba-NLP/gte-reranker-modernbert-base"
# 8 shards of ~7,600 edges: about 95 MB a shard, so a flush rewrites tens of MB, not hundreds.
N_SHARDS = 8


def shard_of(chunk_id: str) -> int:
    return int(hashlib.sha1(("facet_pairs_fullcache:" + chunk_id).encode()).hexdigest(), 16) % N_SHARDS


def main() -> int:
    chunks = {}
    with open(ROWS, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if "chunk_id" in r and (r.get("text") or "").strip():
                chunks[r["chunk_id"]] = r
    edges = []
    with open(STATS, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["chunk_id"] in chunks:
                edges.append((r["chunk_id"], r["tag"]))      # the topic value is NOT carried
    assert len(edges) == 61018 and len(chunks) == 4808, (len(edges), len(chunks))
    BUNDLE.mkdir(parents=True, exist_ok=True)
    work = BUNDLE / "_build"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    counts = [0] * N_SHARDS
    outs = [open(work / f"edges.shard{k}.jsonl", "w", encoding="utf-8") for k in range(N_SHARDS)]
    for cid, tag in edges:
        k = shard_of(cid)
        outs[k].write(json.dumps({"edge_id": f"{cid}::{tag}", "chunk_id": cid, "tag": tag},
                                 ensure_ascii=False) + "\n")
        counts[k] += 1
    for o in outs:
        o.close()
    shutil.copy(BAKEOFF / "extract_standalone.py", work / "extract_standalone.py")
    shutil.copy(BAKEOFF / "rows_export.jsonl.gz", work / "rows_export.jsonl.gz")
    zpath = BUNDLE / "facet_pairs_fullcache_code.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(work.iterdir()):
            z.write(p, p.name)
    shutil.rmtree(work)

    def code(src):
        return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                "source": src}
    nb = {"nbformat": 4, "nbformat_minor": 5, "metadata": {"accelerator": "GPU"}, "cells": [
        code("# cell 1 - mount Drive\nfrom google.colab import drive\ndrive.mount('/content/drive')\n"
             "import os, torch\nOUT = '/content/drive/MyDrive/GRAG-Job-colab/fullcache'\n"
             "os.makedirs(OUT, exist_ok=True)\nprint('cuda:', torch.cuda.is_available())\n"
             "print('already there:', sorted(os.listdir(OUT)))\n"),
        code("# cell 2 - unzip the bundle you dragged into /content\nimport zipfile, os\n"
             "ZIP = '/content/facet_pairs_fullcache_code.zip'\n"
             "assert os.path.isfile(ZIP), 'drag facet_pairs_fullcache_code.zip into /content first'\n"
             "zipfile.ZipFile(ZIP).extractall('/content/fullcache')\n"
             "print(sorted(os.listdir('/content/fullcache')))\n"),
        code("# cell 3 - pin only if needed (ModernBERT needs transformers >= 4.48)\n"
             "import transformers\nfrom packaging.version import Version\n"
             "print('transformers', transformers.__version__)\n"
             "if Version(transformers.__version__) < Version('4.48'):\n"
             "    !pip install -q -U 'transformers>=4.48,<6'\n"
             "    print('RESTART THE RUNTIME, then run cells 1 and 2 again.')\n"),
        code("# cell 4 - the long one: %d shards, one after the other. Resumable: after a disconnect\n"
             "# run cells 1, 2 and this one again; finished shards are skipped, a half-done one resumes.\n"
             "import os, subprocess\nOUT = '/content/drive/MyDrive/GRAG-Job-colab/fullcache'\n"
             "for k in range(%d):\n"
             "    d = f'{OUT}/shard{k}'\n    os.makedirs(d, exist_ok=True)\n"
             "    if any(f.endswith('.npz') and not f.endswith('.part.npz') for f in os.listdir(d)):\n"
             "        print('shard', k, 'already done'); continue\n"
             "    print('=== shard', k, flush=True)\n"
             "    subprocess.run(['python', '/content/fullcache/extract_standalone.py',\n"
             "                    '--edges', f'/content/fullcache/edges.shard{k}.jsonl',\n"
             "                    '--rows', '/content/fullcache/rows_export.jsonl.gz',\n"
             "                    '--out', d, '--device', 'cuda', '--flush', '1024',\n"
             "                    '--only', 'gte-reranker-modernbert'], check=True)\n" % (N_SHARDS, N_SHARDS)),
        code("# cell 5 - what is on Drive now\nimport os\n"
             "OUT = '/content/drive/MyDrive/GRAG-Job-colab/fullcache'\ntotal = 0\n"
             "for root, _, files in os.walk(OUT):\n    for f in sorted(files):\n"
             "        n = os.path.getsize(os.path.join(root, f)); total += n\n"
             "        print('%-70s %8.1f MB' % (os.path.join(os.path.basename(root), f), n / 1e6))\n"
             "print('total %.1f MB' % (total / 1e6))\n"),
    ]}
    (BUNDLE / "fullcache.ipynb").write_text(json.dumps(nb, indent=1), encoding="utf-8")
    readme = f"""# facet_pairs — the one full pass ({WINNER})

Every one of the 61,018 edges through the bake-off's winning backbone, once. After this no
experiment needs a GPU: heads train on the cache on the laptop, and scoring the whole graph is a
matrix product.

1. Colab, T4 runtime. Open `fullcache.ipynb`.
2. Drag `facet_pairs_fullcache_code.zip` ({zpath.stat().st_size / 1e6:.1f} MB) into the session files.
3. Run cells 1-4. Cell 4 runs {N_SHARDS} shards in turn ({', '.join(str(c) for c in counts)} edges)
   and writes each to `MyDrive/GRAG-Job-colab/fullcache/shard<k>/`. Measured in the bake-off:
   133 s per 1,000 edges on a T4, so about 2.3 h in all (a measurement scaled up, not a guarantee).
   If the session drops: run cells 1, 2 and 4 again; done shards are skipped, a half-done one resumes.
4. Bring the whole `MyDrive/GRAG-Job-colab/fullcache/` folder back to
   `C:/Coding/exjobbet/GRAG-Job/output/facet_pairs/fullcache/`. About 750 MB.

Nothing in the bundle carries a topic value, a judge answer or a benchmark question.
"""
    (BUNDLE / "README.md").write_text(readme, encoding="utf-8")
    print("bundle", BUNDLE)
    print("shards", counts, "sum", sum(counts))
    print("zip MB", round(zpath.stat().st_size / 1e6, 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""The 200-unit sample embedded on the laptop's CPU with the repo's embedder: the reference the
desktop's GPU rows are held against. Counts only."""
import io
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "prod"))
from harness import embed  # noqa: E402

rows = [json.loads(x) for x in (HERE / "sample.jsonl").open(encoding="utf-8") if x.strip()]
t0 = time.perf_counter()
mat, calls, tokens, _, secs = embed._embed([r["text"] for r in rows], "passage", embed.EMBED_BATCH, bar=False)
np.savez(HERE / "sample_laptop.npz", ids=np.array([r["id"] for r in rows], dtype=object), matrix=mat)
print(f"laptop reference: {mat.shape} {mat.dtype}, {tokens} tokens, {calls} forward passes, "
      f"{time.perf_counter() - t0:.0f} s in all (model load included), encode {secs:.0f} s, device {embed.EMBED_DEVICE}")

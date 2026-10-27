"""The judge calls of the six final runs and their re-judging folders: our clock around the answering try
against the CLI's own times (duration_ms, duration_api_ms), by how many judge calls of the same folder
were in flight at the start. Also the same for the sonnet answer calls. Reads run folders only; makes no
model call; prints medians only."""
import json
from datetime import datetime
from pathlib import Path

import numpy as np

K = Path("C:/Coding/exjobbet/GRAG-Job/output/k=chars")
T = lambda s: datetime.fromisoformat(s).timestamp()  # noqa: E731
FINALS = ["lucene__gold100__cb72000__20261008T234209Z", "vector__gold100__cb72000__20261017T061242Z",
          "artefact_v4__gold100__cb72000__20261023T021439Z", "lucene__answerable715__cb72000__20261023T112745Z",
          "vector__answerable715__cb72000__20261024T004317Z", "artefact_v4__answerable715__cb72000__20261025T211532Z"]
folders = [K / f for f in FINALS] + sorted(d for f in FINALS for d in K.glob(f + "__j-*"))


def load(path, answers):
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if '"kind": "chat"' not in line:
                continue
            obj = json.loads(line)
            for c in (obj.get("calls") or []) if answers else [obj]:
                if c.get("kind") != "chat" or not c.get("ok") or not c.get("attempts") or (answers and c.get("role") != "answer"):
                    continue
                env = c.get("envelope") or {}
                if not env.get("duration_api_ms"):
                    continue
                out.append((T(c["started_at"]), T(c["finished_at"]), float(c["attempts"][-1]["seconds"]),
                            env.get("duration_ms", 0) / 1000, env["duration_api_ms"] / 1000))
    return out


def report(name, rows):
    if not rows:
        return
    s = np.array([r[0] for r in rows]); e = np.sort([r[1] for r in rows])
    fl = np.array([np.sum(s <= x) for x in s]) - np.searchsorted(e, s, side="right")
    ours = np.array([r[2] for r in rows]); cli = np.array([r[3] for r in rows]); api = np.array([r[4] for r in rows])
    print(f"{name[:58]:58} n={len(rows):6} in flight median {np.median(fl):4.0f}")
    for lo_, hi_ in ((0, 2), (2, 8), (8, 20), (20, 40), (40, 1000)):
        k = (fl >= lo_) & (fl < hi_)
        if k.sum() >= 20:
            print(f"      {lo_:3}-{hi_:4} in flight: {k.sum():6} calls | ours {np.median(ours[k]):5.1f} s | CLI total {np.median(cli[k]):5.1f} | server {np.median(api[k]):5.1f}"
                  f" | ours minus server, median {np.median(ours[k] - api[k]):5.1f}, p90 {np.percentile(ours[k] - api[k], 90):5.1f}")


for d in folders:
    if (d / "eval_calls.jsonl").exists():
        report(f"judge  {d.name}", load(d / "eval_calls.jsonl", False))
for d in folders[:6]:
    report(f"answer {d.name}", load(d / "arm_outputs.jsonl", True))

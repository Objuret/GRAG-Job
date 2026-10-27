"""Every chat call on the login from 1 to 27 October: start, model, role, tokens, server time. For each
call, the login's input tokens per second in the 60 s before its start, counted per model and in all,
and the earlier measure (tokens spread over each call's span, the minute before and the minute of the
start). Prints, per load band, the server seconds per 1,000 output tokens of sonnet answer calls and of
haiku judge calls, and per final run how many of its sonnet calls fall in each band. Reads run folders
only; makes no model call; prints counts and medians only. Writes the per-call table beside itself."""
import collections
import json
import re
from datetime import datetime
from pathlib import Path

import numpy as np

K = Path("C:/Coding/exjobbet/GRAG-Job/output/k=chars")
OUT = Path(__file__).with_name("load_per_call.json")
T = lambda s: datetime.fromisoformat(s).timestamp()  # noqa: E731
FINALS = {"lucene100": "lucene__gold100__cb72000__20261008T234209Z", "vector100": "vector__gold100__cb72000__20261017T061242Z",
          "artefact100": "artefact_v4__gold100__cb72000__20261023T021439Z", "lucene715": "lucene__answerable715__cb72000__20261023T112745Z",
          "vector715": "vector__answerable715__cb72000__20261024T004317Z", "artefact715": "artefact_v4__answerable715__cb72000__20261025T211532Z",
          "artefact100_first_calls": "artefact_v4__gold100__cb72000__20261020T041923Z"}
BY_NAME = {v: k for k, v in FINALS.items()}

calls = {}
for d in sorted(K.iterdir()):
    m = re.search(r"(2026\d{4})", d.name)
    if not d.is_dir() or not m or m.group(1) < "20261001":
        continue
    final = BY_NAME.get(d.name)
    for fn in ("arm_outputs.jsonl", "eval_calls.jsonl"):
        p = d / fn
        if not p.exists():
            continue
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                if '"kind": "chat"' not in line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                recs = (obj.get("calls") or []) if fn == "arm_outputs.jsonl" else [obj]
                for c in recs:
                    if c.get("kind") != "chat" or not c.get("started_at") or not c.get("finished_at"):
                        continue
                    a, b = T(c["started_at"]), T(c["finished_at"])
                    u, env = c.get("usage") or {}, c.get("envelope") or {}
                    mu = (env.get("modelUsage") or {}).get(c.get("model")) or {}
                    tin = int(u.get("prompt_tokens") or 0) or int((mu.get("inputTokens") or 0) + (mu.get("cacheReadInputTokens") or 0)
                                                                 + (mu.get("cacheCreationInputTokens") or 0))
                    tout = int(u.get("completion_tokens") or 0) or int(mu.get("outputTokens") or 0)
                    key = (round(a, 3), round(b, 3), c.get("model"), tin)
                    r = calls.setdefault(key, {"start": a, "end": b, "model": c.get("model") or "", "role": c.get("role"),
                                               "in": tin, "out": tout, "server": (env.get("duration_api_ms") or 0) / 1000,
                                               "ok": bool(c.get("ok")), "final": None, "id": None, "file": fn})
                    if final and fn == "arm_outputs.jsonl":
                        r["final"], r["id"] = final, obj.get("id")

allc = sorted(calls.values(), key=lambda r: r["start"])
starts = np.array([r["start"] for r in allc])
pref = {}
for kind, sel in (("all", lambda r: True), ("sonnet", lambda r: "sonnet" in r["model"]), ("haiku", lambda r: "haiku" in r["model"])):
    pref[kind] = np.concatenate([[0.0], np.cumsum([r["in"] if sel(r) else 0 for r in allc])])
spread = collections.Counter()
for r in allc:
    n = max(1, int((r["end"] - r["start"]) // 60) + 1)
    for i in range(n):
        spread[int(r["start"] // 60) + i] += r["in"] / n
for i, r in enumerate(allc):
    j = int(np.searchsorted(starts, r["start"] - 60, side="right"))
    for kind in pref:
        r[f"load_{kind}"] = float(pref[kind][i + 1] - pref[kind][j]) / 60
    r["load_spread"] = (spread[int(r["start"] // 60) - 1] + spread[int(r["start"] // 60)]) / 120
    r["per1k"] = r["server"] / r["out"] * 1000 if r["out"] and r["server"] else None

print(f"chat calls read (1-27 Oct, deduplicated): {len(allc)}; by model: {dict(collections.Counter(r['model'] for r in allc))}")
print("roles in the six final runs:", dict(collections.Counter((r["final"], r["role"], r["model"]) for r in allc if r["final"])))


def ranks(x):
    return np.argsort(np.argsort(x)).astype(float)


def bands(rows, measure, edges):
    print(f"   by {measure}:")
    v = np.array([r[measure] for r in rows]); y = np.array([r["per1k"] for r in rows])
    for lo_, hi_ in zip(edges[:-1], edges[1:]):
        s = y[(v >= lo_) & (v < hi_)]
        if len(s):
            print(f"      {lo_/1000:5.0f}k-{hi_/1000 if hi_ < 1e9 else float('inf'):>4.0f}k: {len(s):5} calls | median {np.median(s):6.1f} | p75 {np.percentile(s, 75):6.1f} | p90 {np.percentile(s, 90):6.1f}")
    print(f"      rank correlation with seconds per 1,000 tokens: {np.corrcoef(ranks(v), ranks(y))[0, 1]:+.3f}")


edges = [0, 2000, 4000, 6000, 8000, 10000, 12000, 14000, 16000, 18000, 20000, 25000, 30000, 40000, 1e12]
ans = [r for r in allc if r["role"] == "answer" and "sonnet" in r["model"] and r["ok"] and r["per1k"]]
print(f"\n== sonnet answer calls: {len(ans)}; server seconds per 1,000 output tokens by the login's input tokens per second")
for measure in ("load_sonnet", "load_all", "load_haiku", "load_spread"):
    bands(ans, measure, edges)
judge = [r for r in allc if "haiku" in r["model"] and r["ok"] and r["per1k"]]
print(f"\n== haiku calls: {len(judge)}; roles: {dict(collections.Counter(r['role'] for r in judge).most_common(6))}")
for measure in ("load_haiku", "load_all", "load_sonnet"):
    bands(judge, measure, edges)

print("\n== the six final runs: their sonnet calls by the sonnet load at the start (input tokens per second, 60 s before)")
fe = [0, 4000, 8000, 10000, 12000, 14000, 16000, 20000, 1e12]
for f in FINALS:
    for role in sorted({r["role"] for r in allc if r["final"] == f and "sonnet" in r["model"]}, key=str):
        rs = [r for r in allc if r["final"] == f and r["role"] == role and "sonnet" in r["model"]]
        cnt = [sum(1 for r in rs if lo_ <= r["load_sonnet"] < hi_) for lo_, hi_ in zip(fe[:-1], fe[1:])]
        print(f"   {f:12} {str(role):14} {len(rs):4} calls | " + " ".join(f"{int(lo_/1000)}k+:{c}" for lo_, c in zip(fe[:-1], cnt)))

keep = [{k: r[k] for k in ("start", "end", "model", "role", "in", "out", "server", "ok", "final", "id", "per1k",
                           "load_all", "load_sonnet", "load_haiku", "load_spread")} for r in allc if "sonnet" in r["model"] or r["final"]]
OUT.write_text(json.dumps(keep), encoding="utf-8")
print(f"\nper-call table: {OUT} ({len(keep)} calls)")

"""The numbers of one or more run folders, side by side: every score's mean, and the run's own data
(calls, tokens, seconds). Numbers only: no question, answer, context or prompt text is printed.

    .venv/Scripts/python.exe output/research/2026-10-09-baseline-unit-text/run_stats.py <folder> [<folder> ...]
"""
import io
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def lines(path):
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def summary(d):
    out = {"folder": d.name}
    man = json.loads((d / "run_manifest.json").read_text(encoding="utf-8")) if (d / "run_manifest.json").is_file() else {}
    rows = lines(d / "arm_outputs.jsonl")
    res = lines(d / "eval_results.jsonl")
    ev = json.loads((d / "eval_manifest.json").read_text(encoding="utf-8")) if (d / "eval_manifest.json").is_file() else {}
    by = defaultdict(list)
    status = defaultdict(lambda: defaultdict(int))
    for r in res:
        status[r["metric"]][r["status"]] += 1
        if r["status"] == "ok":
            by[r["metric"]].append(r["value"])
    out["scores"] = {m: (st.mean(v), len(v)) for m, v in by.items()}
    out["not_ok"] = {m: dict(s) for m, s in status.items() if set(s) - {"ok"}}
    g = [r["generator"] for r in rows]
    rt = [r["retrieval"] for r in rows]
    out["run"] = {
        "rows": len(rows),
        "commit": ((man.get("code_version") or {}).get("commit") or "")[:7],
        "changed code paths": len((man.get("code_state") or {}).get("status") or []),
        "workers": man.get("workers"),
        "starts": len(man.get("legs") or []),
        "units": (man.get("index") or {}).get("units"),
        "contexts per question, mean": st.mean(len(r["contexts"]) for r in rows) if rows else None,
        "ids per question, mean": st.mean(len(r["context_ids"]) for r in rows) if rows else None,
        "delivered characters per question, mean": st.mean(sum(map(len, r["contexts"])) for r in rows) if rows else None,
        "questions that did not fill the budget": man.get("n_exhausted"),
        "search seconds, mean": st.mean(r["search_time_s"] for r in rows) if rows else None,
        "search seconds, median": st.median(r["search_time_s"] for r in rows) if rows else None,
        "search seconds, max": max((r["search_time_s"] for r in rows), default=None),
        "question embedding seconds, mean": st.mean(x.get("time_s", 0.0) for x in rt) if rt else None,
        "question embedding tokens, sum": sum(x.get("tokens_in", 0) for x in rt),
        "answer calls": sum(x.get("calls", 0) for x in g),
        "answer tries": sum(x.get("attempts", 0) for x in g),
        "answer tokens in, sum": sum(x.get("tokens_in", 0) for x in g),
        "answer tokens in, mean": st.mean(x.get("tokens_in", 0) for x in g) if g else None,
        "answer tokens out, sum": sum(x.get("tokens_out", 0) for x in g),
        "answer tokens out, mean": st.mean(x.get("tokens_out", 0) for x in g) if g else None,
        "answer seconds, mean": st.mean(x.get("time_s", 0.0) for x in g) if g else None,
        "answer seconds, median": st.median(x.get("time_s", 0.0) for x in g) if g else None,
        "answer seconds, sum": sum(x.get("time_s", 0.0) for x in g),
        "question wall seconds, mean": st.mean((r.get("timing") or {}).get("wall_s", 0.0) for r in rows) if rows else None,
        "index build seconds": ((man.get("build_stats") or {}).get("build_time_s")),
        "index build tokens in": (((man.get("build_stats") or {}).get("model") or {}).get("tokens_in")),
        "prepare seconds, per start": [round(leg.get("prepare_s") or 0.0, 1) for leg in man.get("legs") or []],
        "wall seconds, per start": [round(leg.get("wall_s") or 0.0, 1) for leg in man.get("legs") or []],
        "peak memory GB, per start": [round((leg.get("peak_memory_bytes") or 0) / 1e9, 2) for leg in man.get("legs") or []],
    }
    ju = ev.get("judge_usage") or {}
    out["evaluation"] = {
        "judge model": ev.get("judge_model"),
        "scoring starts": len(ev.get("judge_legs") or []),
        "judge calls": ju.get("calls"), "judge tries": ju.get("attempts"),
        "judge tokens in": ju.get("tokens_in"), "judge tokens out": ju.get("tokens_out"),
        "judge request seconds": ju.get("request_s"), "evaluation wall seconds": ev.get("judge_elapsed_s"),
        "result rows": len(res), "failed cells on file": len(lines(d / "eval_failures.jsonl")),
        "kept calls": len(lines(d / "eval_calls.jsonl")),
    }
    return out


def fmt(v):
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:,.4f}" if abs(v) < 100 else f"{v:,.1f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


folders = [Path(a) for a in sys.argv[1:]]
S = [summary(d) for d in folders]
w = 30
print(f"{'':<44}" + "".join(f"{s['folder'].split('__')[0] + ' ' + s['folder'].split('__')[-1]:>{w}}" for s in S))
print("scores, mean over the questions with an ok value (n)")
names = []
for s in S:
    for m in s["scores"]:
        if m not in names:
            names.append(m)
for m in names:
    print(f"   {m:<41}" + "".join(
        f"{(fmt(s['scores'][m][0]) + ' (' + str(s['scores'][m][1]) + ')') if m in s['scores'] else '-':>{w}}" for s in S))
for s in S:
    if s["not_ok"]:
        print(f"   cells not ok in {s['folder']}: {s['not_ok']}")
for block in ("run", "evaluation"):
    print(block)
    keys = []
    for s in S:
        for k in s[block]:
            if k not in keys:
                keys.append(k)
    for k in keys:
        print(f"   {k:<41}" + "".join(f"{fmt(s[block].get(k)):>{w}}" for s in S))

"""judge_probe.py — survey every chat-capable NIM model as a RAGAS-judge candidate.

Two tiny faithfulness verdicts with known ground truth (one true, one false) go to
every candidate; each model gets a latency, a JSON-parse verdict, and a correctness
mark. The ranked table prints to stdout and lands in output/judge_probe.json.

    python judge_probe.py                # full catalog sweep, 3 workers
    python judge_probe.py --workers 5    # one worker per account lane
"""
import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

# Not judge material: embedders, rerankers, safety/reward heads, vision/audio,
# parsers. Everything else in the catalog gets probed — the long list.
_EXCLUDE = ("embed", "rerank", "safety", "reward", "parse", "-vl", "vl-", "vision",
            "asr", "tts", "audio", "clip", "ocr", "riva", "guard")

_CONTEXT = "The quarterly report was written by Ana Torres and reviewed by Ben Kim."
_PROBES = [  # (answer, correct_verdict)
    ("Ana Torres wrote the quarterly report.", 1),
    ("Ben Kim wrote the quarterly report.", 0),
]
_PROMPT = (
    "Context: '{ctx}'\nAnswer: '{ans}'\n"
    "Is the answer faithful to the context? "
    'Reply ONLY with JSON: {{"verdict": 1 or 0}}'
)


def _verdict(text: str):
    m = re.search(r'"verdict"\s*:\s*([01])', text or "")
    return int(m.group(1)) if m else None


def _probe_model(nim, model: str) -> dict:
    lat, correct, note = [], 0, ""
    for ans, want in _PROBES:
        payload = {"model": model, "temperature": 0, "max_tokens": 300,
                   "messages": [{"role": "user",
                                 "content": _PROMPT.format(ctx=_CONTEXT, ans=ans)}]}
        t0 = time.perf_counter()
        try:
            resp = nim.post("/chat/completions", payload, timeout=90, max_tries=1)
        except Exception as e:
            return {"model": model, "ok": False, "note": f"{type(e).__name__}: {str(e)[:80]}"}
        el = time.perf_counter() - t0
        msg = (resp.get("choices") or [{}])[0].get("message") or {}
        content = msg.get("content") or ""
        if not content.strip():  # reasoning model — pin thinking off and retry once
            payload["chat_template_kwargs"] = {"enable_thinking": False}
            t0 = time.perf_counter()
            try:
                resp = nim.post("/chat/completions", payload, timeout=90, max_tries=1)
                el = time.perf_counter() - t0
                msg = (resp.get("choices") or [{}])[0].get("message") or {}
                content = msg.get("content") or ""
                note = "needed enable_thinking=false"
            except Exception as e:
                return {"model": model, "ok": False,
                        "note": f"thinking-off retry: {type(e).__name__}"}
        if not content.strip():
            return {"model": model, "ok": False, "note": "empty content both ways"}
        lat.append(el)
        got = _verdict(content)
        if got is None:
            return {"model": model, "ok": False, "note": f"unparseable: {content[:60]!r}"}
        correct += int(got == want)
    return {"model": model, "ok": True, "latency_s": round(sum(lat) / len(lat), 1),
            "correct": f"{correct}/2", "both_correct": correct == 2, "note": note}


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--workers", type=int, default=3, metavar="W",
                   help="models probed in parallel (default 3; one key lane each)")
    args = p.parse_args()

    print("judge probe | 2 known-truth verdicts per model | timeout 90s, 1 try", flush=True)
    import httpx
    import nim
    from progress import progress
    nim._load_dotenv()
    key = nim.require_key()
    r = httpx.get(f"{nim.BASE_URL}/models",
                  headers={"Authorization": f"Bearer {key}"}, timeout=30)
    r.raise_for_status()
    all_ids = sorted(m["id"] for m in r.json()["data"])
    cands = [i for i in all_ids if not any(x in i.lower() for x in _EXCLUDE)]
    print(f"catalog: {len(all_ids)} models, {len(cands)} chat-capable candidates\n", flush=True)

    rows = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {ex.submit(_probe_model, nim, m): m for m in cands}
        for fut in progress([f for f in futs], desc="probing", unit="model"):
            rows.append(fut.result())

    rows.sort(key=lambda r: (not r.get("both_correct", False),
                             not r["ok"], r.get("latency_s", 999)))
    out = _HERE / "output" / "judge_probe.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")

    print(f"\n{'model':52} {'lat(s)':>7} {'verdicts':>8}  note")
    for r_ in rows:
        if r_["ok"]:
            print(f"{r_['model']:52} {r_['latency_s']:>7} {r_['correct']:>8}  {r_['note']}")
        else:
            print(f"{r_['model']:52} {'-':>7} {'FAIL':>8}  {r_['note']}")
    good = [r_ for r_ in rows if r_.get("both_correct")]
    print(f"\n{len(good)} models got both verdicts right  ->  {out}")


if __name__ == "__main__":
    main()

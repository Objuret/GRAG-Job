"""The time of the claude-opus-5 calls that judged the facet pairs the layer was fitted on (the control
and train runs of 2026-09-18), by the CLI's own transcript of each call: from its prompt entry to its
reply entry, without the program's start on our machine. The calls' own records keep only our clock
around each call (wall_s); no record kept the CLI's duration_api_ms for them.

    python tools/recount_opus_build_times.py [--write]

The answers are output/facet_pairs/answers/<set>/*.json; the transcripts the lane's CLI wrote on this
laptop, ~/.claude/projects/C--Users-jocke-AppData-Local-Temp-herb-claude-lane/*.jsonl. A set's
transcripts are the claude-opus-5 ones whose prompt entry falls in the set's window (its first answer's
start, 3 s before, to its last answer); they must be as many as the answers and hold the same pairs of
tokens in and out. On the final runs' calls, which have both, this span is the CLI's duration_api_ms
within a median of 0.02 s (output/research/2026-10-27-model-call-times/transcript_span_check.py).
With --write it writes test/graph/build_cost_opus_transcript_times.json, which the export reads.
"""
import collections
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ANSWERS = REPO / "output/facet_pairs/answers"
LANE = Path.home() / ".claude/projects/C--Users-jocke-AppData-Local-Temp-herb-claude-lane"
OUT = REPO / "test/graph/build_cost_opus_transcript_times.json"
SETS = ("control", "train")


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def transcript(path):
    user = reply = None
    usage, model = None, None
    for line in path.read_text(encoding="utf-8").splitlines():
        d = json.loads(line)
        if d.get("type") == "user" and user is None:
            user = d.get("timestamp")
        if d.get("type") == "assistant":
            m = d.get("message") or {}
            reply, model, usage = d.get("timestamp"), m.get("model") or model, m.get("usage") or usage
    if not (user and reply and usage):
        return None
    tin = (usage.get("input_tokens") or 0) + (usage.get("cache_creation_input_tokens") or 0) + (usage.get("cache_read_input_tokens") or 0)
    return {"session": path.stem, "model": model, "prompt_at": user, "reply_at": reply,
            "seconds": (ts(reply) - ts(user)).total_seconds(), "tokens_in": tin, "tokens_out": usage.get("output_tokens")}


def main():
    answers = {s: [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ANSWERS / s).glob("*.json"))] for s in SETS}
    windows = {s: (min(ts(a["timestamp"]) - timedelta(seconds=a["wall_s"]) for a in xs) - timedelta(seconds=3),
                   max(ts(a["timestamp"]) for a in xs)) for s, xs in answers.items()}
    lo, hi = min(w[0] for w in windows.values()), max(w[1] for w in windows.values())
    found = {s: [] for s in SETS}
    for p in sorted(LANE.glob("*.jsonl")):
        mtime = datetime.fromtimestamp(p.stat().st_mtime).astimezone()
        if not (lo - timedelta(days=1) <= mtime <= hi + timedelta(days=1)):
            continue
        t = transcript(p)
        if t is None or t["model"] != "claude-opus-5":
            continue
        for s, (a, b) in windows.items():
            if a <= ts(t["prompt_at"]) <= b:
                found[s].append(t)
    result = {"what": "seconds of the claude-opus-5 facet-pair calls of the control and train runs, by the CLI's own "
                      "transcript of each call: from its prompt entry to its reply entry", "sets": {}}
    for s in SETS:
        want = collections.Counter((a["usage"]["tokens_in"], a["usage"]["tokens_out"]) for a in answers[s])
        got = collections.Counter((t["tokens_in"], t["tokens_out"]) for t in found[s])
        if want != got:
            raise SystemExit(f"{s}: the transcripts in the window are not the set's calls "
                             f"({sum(got.values())} transcripts, {sum(want.values())} answers)")
        result["sets"][s] = {"calls": len(found[s]), "seconds": sum(t["seconds"] for t in found[s]),
                             "wall_s_added": sum(a["wall_s"] for a in answers[s]),
                             "window": [windows[s][0].isoformat(), windows[s][1].isoformat()],
                             "calls_by_transcript": sorted(found[s], key=lambda t: t["prompt_at"])}
        print(f"{s}: {len(found[s])} calls, {result['sets'][s]['seconds']:.1f} s by the transcripts, "
              f"{result['sets'][s]['wall_s_added']:.1f} s by our clock")
    result["seconds"] = sum(v["seconds"] for v in result["sets"].values())
    result["script"] = "tools/recount_opus_build_times.py"
    print(f"together: {result['seconds']:.1f} s")
    if "--write" in sys.argv:
        OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"written: {OUT}")


if __name__ == "__main__":
    main()

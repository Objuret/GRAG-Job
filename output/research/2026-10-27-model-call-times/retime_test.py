"""Re-time a selected set of answer calls one at a time, and test the per-call fix: does the clean
relation (server time from the answer's length, learned on calls the login's load did not slow)
give the time the same call takes when nothing else loads the login? Prints numbers only."""
import collections
import json
import statistics as st
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

REPO = Path("C:/Coding/exjobbet/GRAG-Job")
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
from harness import chat  # noqa: E402
from harness.orchestrator import _GENERATOR_SETTINGS  # noqa: E402

K = REPO / "output/k=chars"
OUT = Path(__file__).with_name("retime_test_results.json")
T = lambda s: datetime.fromisoformat(s).timestamp()  # noqa: E731


def answers(name):
    out = []
    for line in open(K / name / "arm_outputs.jsonl", encoding="utf-8"):
        r = json.loads(line)
        c = next(c for c in r["calls"] if c.get("role") == "answer")
        env = c.get("envelope") or {}
        out.append({"run": name, "id": r["id"], "rec": c, "start": T(c["started_at"]),
                    "out": r["generator"]["tokens_out"], "server": (env.get("duration_api_ms") or 0) / 1000})
    return sorted(out, key=lambda x: x["start"])


def spread(xs, n):
    xs = sorted(xs, key=lambda x: x["out"])
    return [xs[int(i * (len(xs) - 1) / (n - 1))] for i in range(n)] if len(xs) > n else xs


def slowed(xs):
    t0 = xs[0]["start"]
    return [x for x in xs if x["start"] > t0 + 45 and x["out"] and x["server"] / x["out"] * 1000 > 30]


runs = {"lucene100": "lucene__gold100__cb72000__20261008T234209Z", "vector100": "vector__gold100__cb72000__20261017T061242Z",
        "lucene715": "lucene__answerable715__cb72000__20261023T112745Z", "vector715": "vector__answerable715__cb72000__20261024T004317Z",
        "artefact100": "artefact_v4__gold100__cb72000__20261023T021439Z", "artefact715": "artefact_v4__answerable715__cb72000__20261025T211532Z"}
data = {k: answers(v) for k, v in runs.items()}

# the clean relation per arm: server seconds = a + b * output tokens, on calls the load did not slow
def relation(xs):
    b, a = np.polyfit([x["out"] for x in xs], [x["server"] for x in xs], 1)
    return float(a), float(b)

art = data["artefact715"]
art_clean = [x for x in art if x["out"] and x["server"] / x["out"] * 1000 < 25]
rel = {"lucene": relation(data["lucene100"]), "vector": relation(data["vector100"]), "artefact": relation(art_clean)}
for arm, (a, b) in rel.items():
    print(f"clean relation {arm}: server s = {a:.2f} + {b*1000:.2f} per 1000 output tokens")

chosen = ([("control: lucene, hundred (clean)", x) for x in spread(data["lucene100"], 10)]
          + [("lucene, 715 (slowed)", x) for x in spread(slowed(data["lucene715"]), 25)]
          + [("vector, 715 (slowed)", x) for x in spread(slowed(data["vector715"]), 25)]
          + [("artefact, hundred (slowed tail)", x) for x in sorted(slowed(data["artefact100"]),
                                                                     key=lambda x: -x["server"] / x["out"])[:10]])
print(f"calls chosen: {len(chosen)}", dict(collections.Counter(g for g, _ in chosen)), flush=True)

results = []
for n, (group, x) in enumerate(chosen, 1):
    rec = x["rec"]
    payload = {"model": rec["model"], **_GENERATOR_SETTINGS,
               "messages": [{"role": "system", "content": rec["system"]}, {"role": "user", "content": rec["prompt"]}],
               "response_format": {"type": "json_schema", "json_schema": {"name": "answer", "schema": rec["schema"]}}}
    s = chat.call_settings(payload)
    same = (s["flags"] == rec["flags"], s["system"] == rec["system"], s["prompt"] == rec["prompt"], s["schema"] == rec["schema"])
    env_diff = sorted(k for k in set(s["env_set"]) | set(rec.get("env_set") or {})
                      if k != "CLAUDE_CONFIG_DIR" and s["env_set"].get(k) != (rec.get("env_set") or {}).get(k))
    if not all(same):
        print(f"{n:3} {group}: NOT the recorded call (flags, system, prompt, schema same: {same}); skipped", flush=True)
        continue
    t0 = time.perf_counter()
    try:
        resp = chat.post("/chat/completions", payload, timeout=480.0, max_tries=1)
    except Exception as e:  # a failed call is reported, not retried
        print(f"{n:3} {group}: failed: {str(e)[:120]}", flush=True)
        continue
    c = resp["call"]; env = c.get("envelope") or {}
    new_out = int((resp.get("usage") or {}).get("completion_tokens") or 0)
    if not new_out:  # the reply's usage field can hold 0; its counts per model hold the tokens
        new_out = int(((env.get("modelUsage") or {}).get(rec["model"]) or {}).get("outputTokens") or 0)
    arm = "lucene" if "lucene" in group else "vector" if "vector" in group else "artefact"
    a, b = rel[arm]
    row = {"group": group, "id": x["id"], "orig_out": x["out"], "orig_server": x["server"],
           "fix_value": a + b * x["out"], "new_out": new_out, "new_server": (env.get("duration_api_ms") or 0) / 1000,
           "new_cli": (env.get("duration_ms") or 0) / 1000, "new_wall": float(c["attempts"][-1]["seconds"]),
           "predicted_new": a + b * new_out, "env_diff": env_diff}
    results.append(row)
    OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(f"{n:3}/{len(chosen)} {group[:34]:34} | recorded {row['orig_server']:6.1f} s ({row['orig_out']} tok) | now {row['new_server']:5.1f} s ({new_out} tok)"
          f" | relation for now's length {row['predicted_new']:5.1f} s | fix value {row['fix_value']:5.1f} s", flush=True)

print("\n== by group (medians)")
for g in dict.fromkeys(r["group"] for r in results):
    rs = [r for r in results if r["group"] == g]
    err = [r["new_server"] - r["predicted_new"] for r in rs]
    fix_err = [r["new_server"] - r["fix_value"] for r in rs]
    print(f"{g:34} n={len(rs):2} | recorded {st.median(r['orig_server'] for r in rs):6.1f} s | re-timed {st.median(r['new_server'] for r in rs):5.1f} s"
          f" | re-timed minus relation (same length): median {st.median(err):+.2f}, |err| median {st.median(map(abs, err)):.2f}, 90% {np.percentile(np.abs(err), 90):.2f} s"
          f" | re-timed minus fix value: median {st.median(fix_err):+.2f} s | length now / recorded, median {st.median(r['new_out'] / r['orig_out'] for r in rs):.2f}"
          f" | env differs: {sorted({k for r in rs for k in r['env_diff']})}")

"""The check of the clean relations on calls made past the login's limit: the calls picked by
relations.py (per arm 25 answer calls past the bend, spread over their output length, and 10 first
calls), each rebuilt from its record, checked equal to the recorded call (flags, system, prompt,
schema, environment apart from the config folder), and sent again one at a time. Compares each fresh
server time with the arm's clean relation at the fresh answer's own length. Prints numbers only."""
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
from artefact import querytagger_split_check as S  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "check_retime_results.json"
K = REPO / "output/k=chars"
RUNS = {"lucene715": "lucene__answerable715__cb72000__20261023T112745Z", "vector715": "vector__answerable715__cb72000__20261024T004317Z",
        "artefact100": "artefact_v4__gold100__cb72000__20261023T021439Z", "artefact715": "artefact_v4__answerable715__cb72000__20261025T211532Z"}
ARM = {"lucene715": "lucene", "vector715": "vector", "artefact100": "artefact", "artefact715": "artefact"}
T = lambda s: datetime.fromisoformat(s).timestamp()  # noqa: E731

sel = json.loads((HERE / "check_selection.json").read_text(encoding="utf-8"))
# A call sent again in the last hour can be read from the prompt cache (one hour on the subscription):
# each picked call that retime_test.py sent is replaced by the nearest call of the same pool by length.
GROUP_FINAL = {"control: lucene, hundred (clean)": "lucene100", "lucene, 715 (slowed)": "lucene715",
               "vector, 715 (slowed)": "vector715", "artefact, hundred (slowed tail)": "artefact100"}
resent = {(GROUP_FINAL[r["group"]], r["id"]) for r in json.loads((HERE / "retime_test_results.json").read_text(encoding="utf-8"))}
son = sorted([c for c in json.loads((HERE / "load_per_call.json").read_text(encoding="utf-8")) if "sonnet" in c["model"]], key=lambda c: c["start"])
A, prev = 0.0, son[0]["start"]
for c in son:
    A = max(0.0, A - sel["R"] * (c["start"] - prev)) + c["in"]; prev = c["start"]
    c["past"] = A >= sel["bend"]
ARM_OF = {"lucene715": "lucene", "vector715": "vector", "artefact100": "artefact", "artefact715": "artefact"}
taken = {(c["final"], c["id"], c["role"]) for c in sel["calls"]}
for c in sel["calls"]:
    if (c["final"], c["id"]) not in resent:
        continue
    pool = sorted((p for p in son if p["final"] in ARM_OF and ARM_OF[p["final"]] == ARM_OF[c["final"]] and p["role"] == c["role"]
                   and p["past"] and p["ok"] and p["server"] > 0 and p["out"] > 0 and (p["final"], p["id"]) not in resent
                   and (p["final"], p["id"], p["role"]) not in taken), key=lambda p: abs(p["out"] - c["out"]))
    new = pool[0]
    print(f"replaced a call sent in the last hour ({c['final']}, {c['out']} tokens) by one of {new['out']} tokens ({new['final']})")
    taken.add((new["final"], new["id"], new["role"]))
    c.update({k: new[k] for k in ("final", "id", "start", "out", "server")})
done = []
if OUT.exists():  # the calls an earlier start of this check sent: kept, not sent twice
    done = json.loads(OUT.read_text(encoding="utf-8"))
want = {}
for c in sel["calls"]:
    want.setdefault(c["final"], []).append(c)
records = {}
for final, cs in want.items():
    keys = {(c["id"], c["role"], round(c["start"], 3)) for c in cs}
    with open(K / RUNS[final] / "arm_outputs.jsonl", encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            for c in r["calls"]:
                if c.get("kind") == "chat" and (r["id"], c.get("role"), round(T(c["started_at"]), 3)) in keys:
                    records[(final, r["id"], c.get("role"), round(T(c["started_at"]), 3))] = c
print(f"calls picked: {len(sel['calls'])}; records found: {len(records)}", flush=True)

results = []
for n, c in enumerate(sel["calls"], 1):
    rec = records.get((c["final"], c["id"], c["role"], round(c["start"], 3)))
    kind = "answer" if c["role"] == "answer" else "first"
    group = f"{kind} {ARM[c['final']]}"
    if rec is None:
        print(f"{n:3} {group}: record not found; skipped", flush=True)
        continue
    earlier = next((r for r in done if r["final"] == c["final"] and r["orig_out"] == c["out"] and r["orig_server"] == c["server"]), None)
    if earlier:
        earlier.setdefault("id", c["id"]); results.append(earlier)
        print(f"{n:3}/{len(sel['calls'])} {group:16} | sent by the earlier start of this check; kept", flush=True)
        continue
    switch = (rec.get("env_set") or {}).get("ENABLE_PROMPT_CACHING_1H")
    if switch is None:  # the record's CLI ran without the switch: so does this one
        chat._ENV_FIXED.pop("ENABLE_PROMPT_CACHING_1H", None)
    else:
        chat._ENV_FIXED["ENABLE_PROMPT_CACHING_1H"] = switch
    msgs = [{"role": "system", "content": rec["system"]}, {"role": "user", "content": rec["prompt"]}]
    if kind == "answer":
        payload = {"model": rec["model"], **_GENERATOR_SETTINGS, "messages": msgs,
                   "response_format": {"type": "json_schema", "json_schema": {"name": "answer", "schema": rec["schema"]}}}
    else:
        payload = {"model": rec["model"], "temperature": 0, "max_tokens": S.MAX_TOKENS_S, "messages": msgs,
                   "response_format": {"type": "json_schema", "json_schema": {"name": "querytag", "schema": rec["schema"]}}}
    s = chat.call_settings(payload)
    same = (s["flags"] == rec["flags"], s["system"] == rec["system"], s["prompt"] == rec["prompt"], s["schema"] == rec["schema"])
    env_diff = sorted(k for k in set(s["env_set"]) | set(rec.get("env_set") or {})
                      if k != "CLAUDE_CONFIG_DIR" and s["env_set"].get(k) != (rec.get("env_set") or {}).get(k))
    if not all(same) or env_diff:
        print(f"{n:3} {group}: NOT the recorded call (flags, system, prompt, schema same: {same}; environment differs: {env_diff}); skipped", flush=True)
        continue
    try:
        resp = chat.post("/chat/completions", payload, timeout=480.0, max_tries=1)
    except Exception as e:  # a failed call is reported, not retried
        print(f"{n:3} {group}: failed: {str(e)[:120]}", flush=True)
        continue
    call = resp["call"]; env = call.get("envelope") or {}
    new_out = int((resp.get("usage") or {}).get("completion_tokens") or 0) or \
        int(((env.get("modelUsage") or {}).get(rec["model"]) or {}).get("outputTokens") or 0)
    a, b = sel["relations"][f"{kind}|{ARM[c['final']]}"]
    mu = (env.get("modelUsage") or {}).get(rec["model"]) or {}
    mu0 = ((rec.get("envelope") or {}).get("modelUsage") or {}).get(rec["model"]) or {}
    row = {"group": group, "final": c["final"], "id": c["id"], "orig_out": c["out"], "orig_server": c["server"], "new_out": new_out,
           "new_server": (env.get("duration_api_ms") or 0) / 1000, "relation_at_new": a + b * new_out, "relation_at_orig": a + b * c["out"],
           "cache_read_now": int(mu.get("cacheReadInputTokens") or 0), "cache_read_then": int(mu0.get("cacheReadInputTokens") or 0)}
    results.append(row)
    OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(f"{n:3}/{len(sel['calls'])} {group:16} | recorded {row['orig_server']:6.1f} s ({c['out']} tok) | now {row['new_server']:5.1f} s ({new_out} tok)"
          f" | relation at now's length {row['relation_at_new']:5.1f} s", flush=True)
    time.sleep(1)

print("\n== by group: fresh server time minus the clean relation at the fresh length")
for g in dict.fromkeys(r["group"] for r in results):
    rs = [r for r in results if r["group"] == g]
    err = np.array([r["new_server"] - r["relation_at_new"] for r in rs])
    print(f"{g:16} n={len(rs):2} | recorded median {st.median(r['orig_server'] for r in rs):6.1f} s | now {st.median(r['new_server'] for r in rs):5.1f} s"
          f" | error median {np.median(err):+.2f} s, |error| median {np.median(np.abs(err)):.2f}, 90% {np.percentile(np.abs(err), 90):.2f}"
          f" | length now / recorded, median {st.median(r['new_out'] / r['orig_out'] for r in rs):.2f}"
          f" | calls read from the prompt cache: now {sum(1 for r in rs if r.get('cache_read_now'))}, then {sum(1 for r in rs if r.get('cache_read_then'))}")

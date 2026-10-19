"""Why the May tagger covered one post: what it was asked and what it answered, by how many posts the chunk held.
From the run's own request log (io.jsonl in the snapshot zip) and the chunks' locators in herb-eval-volmax; no
question read. Argument: the unzipped snapshot folder
(git show bcc3156:backend/data/tagging_runs/pilot_full_herb_snapshot_20260514T052226Z.zip).

    .venv/Scripts/python.exe output/research/2026-10-16-what-the-tagger-saw/what_the_tagger_answered.py <folder>
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
from graph.db import _driver  # noqa: E402

folder = Path(sys.argv[1])
dr = _driver()
with dr.session(database="herb-eval-volmax") as s:
    posts = {}
    for r in s.run("MATCH (c:Chunk) WHERE c.kind IN ['pr_batch','slack_thread_batch','url_batch','meeting_chat_batch'] "
                   "RETURN c.chunk_id AS id, c.kind AS kind, c.locator_json AS loc"):
        loc = json.loads(r["loc"])
        posts[r["id"]] = (r["kind"], len(loc["indices"]) if "indices" in loc else 1)
dr.close()

calls, stops, sample = defaultdict(list), Counter(), {}
system_prompts = Counter()
for line in (folder / "io.jsonl").open(encoding="utf-8"):
    r = json.loads(line)
    if r["stage"] != "extract" or r["target_id"] not in posts:
        continue
    kind, m = posts[r["target_id"]]
    system_prompts[r["request"]["system"]] += 1
    stops[(kind, r.get("stop_reason"))] += 1
    out = r.get("response_tool_input") or {}
    usage = r.get("usage") or {}
    calls[kind].append((m, len(out.get("tags") or []), len(out.get("description") or ""),
                        usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)))
    if kind == "pr_batch" and m == 4 and "pr" not in sample:
        sample["pr"] = (r["target_id"], (r.get("response_reasoning") or "")[:1200])

print(f"system prompts used on the batch chunks: {len(system_prompts)} different, {sum(system_prompts.values())} calls")
for text, count in system_prompts.items():
    print(f"--- {count} calls:\n{text}---")
print("\nhow each call ended: " + ", ".join(f"{k} {v}: {c}" for (k, v), c in sorted(stops.items(), key=lambda x: (x[0][0], str(x[0][1])))))
print("\n== by kind and posts in the chunk: calls | tags returned, middle | description characters, middle | "
      "tokens in, middle | tokens out, middle ==")
for kind, rows in calls.items():
    by_m = defaultdict(list)
    for row in rows:
        by_m[min(row[0], 20) if kind != "slack_thread_batch" else (row[0] // 5) * 5].append(row)
    for m in sorted(by_m):
        g = np.array(by_m[m], dtype=np.float64)
        label = f"{m}" if kind != "slack_thread_batch" else f"{m}-{m + 4}"
        print(f"   {kind}, {label} posts: {len(g)} | {np.median(g[:, 1]):.0f} | {np.median(g[:, 2]):.0f} | "
              f"{np.median(g[:, 3]):.0f} | {np.median(g[:, 4]):.0f}")
    g = np.array(rows, dtype=np.float64)
    print(f"   {kind}, posts against tags returned: correlation {np.corrcoef(g[:, 0], g[:, 1])[0, 1]:.2f}; posts against "
          f"description characters: {np.corrcoef(g[:, 0], g[:, 2])[0, 1]:.2f}")
if "pr" in sample:
    print(f"\nthe model's own reasoning on the first PR batch of four pull requests ({sample['pr'][0]}), first 1200 "
          f"characters:\n{sample['pr'][1] or '(empty)'}")

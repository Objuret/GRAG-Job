"""Two counts on top of coverage_by_post.npz (run coverage_by_post.py first).
1. PR batches, no gold: where the product's own pull requests stand in the chunk (own = the pull request's
   repository is under github.com/salesforce/, read off its record id) and whether the last pull request, the one
   the tagger described, is the product's own.
2. The hundred, ids only, WITH THE GOLD IN HAND: context_recall_id of the arm's default run if every cited record
   of a group were delivered and nothing else changed (the 72,000-character cut ignored). An upper bound of what
   is at stake in a group, not a result of any build.

    .venv/Scripts/python.exe output/research/2026-10-16-what-the-tagger-saw/own_pull_requests_and_the_stake.py
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
from harness import questions as HQ  # noqa: E402

RUN = REPO / "output/k=chars/artefact_v4__gold100__cb72000__20261016T013552Z_influence_question"
z = np.load(HERE / "coverage_by_post.npz", allow_pickle=True)
chunk, position, m = z["chunk"], z["position"], z["posts_in_chunk"]
record = [str(r) for r in z["record"]]
kinds, chunk_ids = [str(k) for k in z["kinds"]], [str(c) for c in z["chunk_ids"]]
desc_place, tags_place, own_tag = z["desc_place"], z["tags_place"], z["own_tag"]


def own(rid):
    return rid.startswith("github_com_salesforce_")


by_chunk = defaultdict(list)
for i in range(len(record)):
    by_chunk[int(chunk[i])].append(i)
pattern, last_own, places = Counter(), Counter(), Counter()
for c, members in by_chunk.items():
    if kinds[c] != "pr_batch" or len(members) < 2:
        continue
    members.sort(key=lambda i: position[i])
    flags = "".join("o" if own(record[i]) else "x" for i in members)
    pattern[flags] += 1
    last_own["the last pull request is the product's own" if own(record[members[-1]]) else
             "the last pull request is another project's"] += 1
    for k, i in enumerate(members):
        if own(record[i]):
            places["first" if k == 0 else "last" if k == len(members) - 1 else "in between"] += 1
total = sum(pattern.values())
print(f"== PR batches with two or more pull requests: {total} ==")
print("   " + ", ".join(f"{k}: {v}" for k, v in last_own.most_common()))
print("   the product's own pull requests stand: " + ", ".join(f"{k} {v}" for k, v in places.most_common()))
print("   the chunks' order of own (o) and other projects' (x) pull requests, the ten most common:")
for flags, count in pattern.most_common(10):
    print(f"      {flags}: {count}")
own_posts = [i for i in range(len(record)) if kinds[int(chunk[i])] == "pr_batch" and m[i] > 1 and own(record[i])]
print(f"   own pull requests in those chunks {len(own_posts)}: the description finds its chunk first for "
      f"{sum(desc_place[i] == 1 for i in own_posts)}, an own tag stands in it for {sum(own_tag[i] for i in own_posts)}")

wanted = [json.loads(line)["id"] for line in (REPO / "data/gold100.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
cites = {q.id: {str(c) for c in q.citations} for q in HQ.load_questions()}
delivered = {}
for line in (RUN / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        r = json.loads(line)
        delivered[r["id"]] = set(map(str, r["context_ids"]))
post_of = defaultdict(list)
for i, rid in enumerate(record):
    post_of[rid].append(i)
cited_pr = [rid for q in wanted for rid in cites[q] if any(kinds[int(chunk[i])] == "pr_batch" for i in post_of[rid])]
print(f"\n== the hundred: cited records in PR batches {len(cited_pr)}, of them the product's own "
      f"{sum(own(r) for r in cited_pr)} ==")


def bare(i):
    return m[i] > 1 and desc_place[i] != 1 and tags_place[i] != 1 and not own_tag[i]


def recall_if(group):
    vals = []
    for q in wanted:
        if not cites[q]:
            continue
        got = delivered[q] | {rid for rid in cites[q] if any(group(i) for i in post_of[rid])}
        vals.append(len(cites[q] & got) / len(cites[q]))
    return float(np.mean(vals))


print("== WITH THE GOLD IN HAND, every cited record of the group delivered, nothing else changed, the 72,000 cut "
      "ignored: context_recall_id (the run as it is: "
      f"{recall_if(lambda i: False):.4f}) ==")
print(f"   the cited records in PR batches: {recall_if(lambda i: kinds[int(chunk[i])] == 'pr_batch'):.4f}")
print(f"   the cited records in Slack batches: {recall_if(lambda i: kinds[int(chunk[i])] == 'slack_thread_batch'):.4f}")
print(f"   the cited posts that neither the description nor the tags find first and that hold no own tag (PR and Slack "
      f"batches): {recall_if(bare):.4f}")
print(f"   of those, only the PR batches': "
      f"{recall_if(lambda i: bare(i) and kinds[int(chunk[i])] == 'pr_batch'):.4f}")
print("done")

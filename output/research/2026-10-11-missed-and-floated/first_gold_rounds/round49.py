"""Round 49, under his 2026-10-12 goal "solve this": a third of the cited records lies beyond the
72,000 characters (round 48), in conversations that are the product's own. Is a question's gold
held together by the stage of the work it comes from (planning, development, support: the
benchmark's own three stages, each with its own channels and its own stretch of time), and do
the first hits say which stage? His scope is where the hits gather; the tree has no level for
this (a product's channels of one stage are separate parents). The hundred, the combo order as
built, numbers only.

  the stage of a record: by the first word of its channel's name (planning, develop, bug) for a
  Slack message; a diagnosis by name, the time is counted beside it
  1  share of a question's cited Slack messages in the stage that holds most of them
  2  the stage holding most of the combo's first two steps' chunks is that stage on how many questions
  3  the time: the cited messages' days, as a share of the product's whole stretch of days:
     from first to last cited message
"""
import pickle
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

import ties as TI  # noqa: E402
from explore import load, standing  # noqa: E402

HERE = Path(__file__).resolve().parent
T = load()
Q, KINDS = T["questions"], T["kind_names"]
with open(HERE / "first_gold_signals_tags__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
purity, agree, spread, stages_cited = [], 0, [], Counter()
slack_share = []
for qid, d in Q.items():
    d.update(extra[qid])
    P = TI.product(qid.split("::")[0])
    m = d["gold"].size
    cited = set(d["cited_ids"])
    kind = [KINDS[x] for x in d["kind"]]
    stage_of = lambda r: P["channel_of"][r].split("-")[0]  # noqa: E731
    per = Counter(stage_of(r) for r in cited if r in P["channel_of"])
    slack_share.append(sum(per.values()) / len(cited))
    if not per:
        continue
    main, held = per.most_common(1)[0]
    purity.append(held / sum(per.values()))
    stages_cited[main] += 1
    D, Tg = np.asarray(d["question_bare"], dtype=np.float64), np.asarray(d["tags"], dtype=np.float64)
    step = WK.levels(D, 5) + WK.levels(Tg, 5)
    hits = step <= 3 if (step <= 3).any() else step == step.min()
    votes = Counter()
    for k in np.flatnonzero(hits).tolist():
        if kind[k] == "slack_thread_batch":
            own = [r for r in d["records"][k] if not TI.apart(r, P)]
            if own:
                votes[stage_of(own[0])] += 1
    agree += bool(votes) and votes.most_common(1)[0][0] == main
    when = sorted(datetime.fromisoformat(P["raw"][r][1]["Message"]["User"]["timestamp"]).timestamp() for r in cited if r in P["channel_of"])
    every = [datetime.fromisoformat(v[1]["Message"]["User"]["timestamp"]).timestamp() for v in P["raw"].values() if v[0] == "slack"]
    spread.append((when[-1] - when[0]) / (max(every) - min(every)))
print(f"questions with cited Slack messages: {len(purity)} of {len(Q)}; share of a question's cited records that are Slack messages: "
      f"{np.mean(slack_share):.0%}")
print(f"1: share of a question's cited Slack messages in the stage that holds most of them: mean {np.mean(purity):.0%}; all of them "
      f"in one stage on {int(np.sum(np.array(purity) > 0.999))} questions; which stage: {dict(stages_cited)}")
print(f"2: the stage holding most of the combo's first two steps' Slack chunks is that stage on {agree} of {len(purity)} questions")
s = np.array(spread)
print(f"3: from the first to the last cited message, as a share of the product's whole stretch of time: middle {np.median(s):.0%}, "
      f"quarters {np.percentile(s, 25):.0%} to {np.percentile(s, 75):.0%}; under a tenth on {int((s < 0.1).sum())} questions")

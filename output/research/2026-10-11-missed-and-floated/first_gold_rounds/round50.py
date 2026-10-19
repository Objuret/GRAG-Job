"""Round 50, under his 2026-10-12 goal "solve this": 90% of a question's cited Slack messages lie in
one stage of the work, and the stage holding most of the combo's first hits is that stage on 88
of 100 questions (round 49). His scope: where the hits gather, the majority's branch, as weight.
The tree has no level for the stage (its channels are separate parents). Tried here with the
stage read two ways. The hundred, the combo as built, handed over as whole own conversations
with the records that are not the product's own work left out; numbers only.

  the stage of a chunk
    by name   the first word of its channel's name (a diagnosis: the dataset's naming)
    by time   the product's Slack channels that are not apart, each from its first to its last
              message; channels whose stretches overlap are one stage (no number given); a chunk
              is in the stage whose stretch holds its first record's time, else the nearest
  the scope   the stage holding the most chunks of the combo's first two steps (every kind of
              chunk counted by its time; for "by name" the Slack chunks only)

  S0  as built: the majority's parents first inside a step
  S1  the stage in place of the parents: in-stage chunks first inside a step
  S2  both: in-stage first, then the majority's parents, inside a step
  S3  the stage before the steps: every in-stage chunk before any other, the combo order inside
  S4  S3 for the Slack chunks only; meetings, documents and pull requests stay where the combo has them
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
from explore import BUDGET, load, standing  # noqa: E402

HERE = Path(__file__).resolve().parent
T = load()
Q, KINDS = T["questions"], T["kind_names"]
with open(HERE / "first_gold_signals_tags__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
PARTS = ("document_part", "meeting_transcript_part")


def stamp(kind, r):
    raw = r["Message"]["User"]["timestamp"] if kind == "slack" else r.get("date") or r.get("created_at")
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00").replace(" ", "T")).replace(tzinfo=None).timestamp()
    except (TypeError, ValueError):
        return None


def stages_by_time(P, kept={}):
    """The channels that are not apart, each a stretch of time; overlapping stretches are one stage."""
    key = id(P)
    if key in kept:
        return kept[key]
    spans = defaultdict(lambda: [float("inf"), float("-inf")])
    for rid, (kind, r) in P["raw"].items():
        if kind == "slack" and P["channel_of"][rid] not in P["stops"]:
            t = stamp(kind, r)
            span = spans[P["channel_of"][rid]]
            span[0], span[1] = min(span[0], t), max(span[1], t)
    merged = []
    for channel, (a, b) in sorted(spans.items(), key=lambda kv: kv[1][0]):
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
            merged[-1][2].add(channel)
        else:
            merged.append([a, b, {channel}])
    kept[key] = merged
    return merged


def stage_at(t, stages):
    if t is None:
        return -1
    for at, (a, b, _) in enumerate(stages):
        if a <= t <= b:
            return at
    return int(np.argmin([min(abs(t - a), abs(t - b)) for a, b, _ in stages]))


def hand_over(units, cited, cites):
    used, got, first = 0, set(), None
    for records, chars, part in units:
        new = [r for r in records if r not in got]
        if not new and not part:
            continue
        if used + chars > BUDGET:
            break
        used += chars
        got.update(records)
        if first is None:
            first = bool(cited & set(records))
    return bool(first), len(cited & got) / cites


def length_of(records, P):
    return sum(P["size"][r] for r in records) + max(len(records) - 1, 0)


results = defaultdict(list)
n_stages, right = Counter(), Counter()
for qid, d in Q.items():
    d.update(extra[qid])
    P = TI.product(qid.split("::")[0])
    m = d["gold"].size
    cited, cites = set(d["cited_ids"]), d["cites"]
    kind = [KINDS[x] for x in d["kind"]]
    own = [[r for r in d["records"][k] if not TI.apart(r, P)] for k in range(m)]
    chunk_len = d["length"].astype(np.int64)
    D, Tg = np.asarray(d["question_bare"], dtype=np.float64), np.asarray(d["tags"], dtype=np.float64)
    step = (WK.levels(D, 5) + WK.levels(Tg, 5)).astype(np.float64)
    z = standing(D) + standing(Tg)
    hits = step <= 3 if (step <= 3).any() else step == step.min()
    ids = np.unique(d["parent"])
    held = np.array([int(hits[d["parent"] == a].sum()) for a in ids])
    total, last = 0, None
    for at in np.lexsort((ids, -held)):
        total += int(held[at])
        last = int(held[at])
        if total * 2 > int(held.sum()):
            break
    scope = np.isin(d["parent"], ids[held >= last])
    stages = stages_by_time(P)
    n_stages[len(stages)] += 1
    is_slack = np.array([k_ == "slack_thread_batch" for k_ in kind])
    stage = {"by name": np.full(m, -1), "by time": np.full(m, -1)}
    names = {}
    for k in range(m):
        recs = own[k] or list(d["records"][k])
        if not recs:
            continue
        r0 = recs[0]
        if r0 in P["raw"]:
            stage["by time"][k] = stage_at(stamp(*P["raw"][r0]), stages)
        if is_slack[k] and r0 in P["channel_of"]:
            stage["by name"][k] = names.setdefault(P["channel_of"][r0].split("-")[0], len(names))
    main_cited = Counter()
    for way in stage:
        per = Counter(int(stage[way][k]) for k in range(m) for r in own[k] if r in cited and stage[way][k] >= 0)
        main_cited[way] = per.most_common(1)[0][0] if per else -2

    talk_records = defaultdict(list)
    for k in sorted(range(m), key=lambda k: (int(d["parent"][k]), int(d["id_rank"][k]))):
        if kind[k] == "slack_thread_batch":
            for r in own[k]:
                talk_records[P["talk_of"][r]].append(r)

    def send(order):
        units, seen, sent = [], set(), set()
        for k in order.tolist():
            if not own[k]:
                continue
            if kind[k] != "slack_thread_batch":
                size = int(chunk_len[k]) if kind[k] in PARTS or len(own[k]) == len(d["records"][k]) else length_of(own[k], P)
                units.append((own[k], size, kind[k] in PARTS))
                continue
            rs = []
            for r in own[k]:
                t = P["talk_of"][r]
                if t not in seen:
                    seen.add(t)
                    rs.extend(talk_records[t])
            rs = [r for r in dict.fromkeys(rs) if r not in sent]
            if rs:
                units.append((rs, length_of(rs, P), False))
                sent.update(rs)
        return hand_over(units, cited, cites)

    results["S0  as built: the majority's parents first inside a step"].append(send(np.lexsort((d["id_rank"], -z, ~scope, step))))
    for way in ("by name", "by time"):
        counted = hits & (stage[way] >= 0)
        votes = Counter(stage[way][counted].tolist())
        if not votes:
            inside = np.ones(m, dtype=bool)
        else:
            inside = stage[way] == votes.most_common(1)[0][0]
            right[way] += votes.most_common(1)[0][0] == main_cited[way]
        soft = inside | (stage[way] < 0)
        results[f"S1  the stage {way} in place of the parents, first inside a step"].append(
            send(np.lexsort((d["id_rank"], -z, ~soft, step))))
        results[f"S2  the stage {way} first, then the majority's parents, inside a step"].append(
            send(np.lexsort((d["id_rank"], -z, ~scope, ~soft, step))))
        results[f"S3  the stage {way} before the steps, the combo order inside"].append(
            send(np.lexsort((d["id_rank"], -z, ~scope, step, ~soft))))
        slack_out = is_slack & ~soft
        results[f"S4  the stage {way} before the steps for the Slack chunks only"].append(
            send(np.lexsort((d["id_rank"], -z, ~scope, step, slack_out))))

n = len(Q)
print(f"stages a product has by time: {dict(n_stages)} (questions); the hits' stage is the stage of most of the cited records: "
      f"by name on {right['by name']} of {n}, by time on {right['by time']} of {n}")
print("\nfirst handed over holds a cited record (of 100) | context_recall_id")
base = np.array([r[1] for r in results["S0  as built: the majority's parents first inside a step"]])
for name, got in results.items():
    a = np.array(got, dtype=np.float64)
    diff = a[:, 1] - base
    print(f"  {int(a[:, 0].sum()):3d} | {a[:, 1].mean():.3f}  {name}"
          + ("" if name.startswith("S0") else f"   [{diff.mean():+.3f}, standard error {diff.std(ddof=1) / 10:.3f}, higher on "
             f"{int((diff > 1e-9).sum())}, lower on {int((diff < -1e-9).sum())}]"))

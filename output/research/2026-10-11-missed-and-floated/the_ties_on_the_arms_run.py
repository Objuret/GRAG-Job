"""For his 2026-10-12 goal "solve this": the ties of a product's records (`first_gold_rounds/ties.py`)
put on the arm's own run of the hundred, the order exactly as the run folder holds it
(`meta.ranking.ordered_chunk_ids`), handed over three ways through the harness's own cut
(`harness.char_budget.cut_at_budget`, 72,000 characters). No model call; the graph is read for
the chunks' pointers.

  as the run has it   every chunk whole (must give the run's own context_recall_id)
  own work only       each chunk without the records that are not the product's own work by the
                      ties (another project's pull request, a message of a talk about another
                      project's, a message of the planning team that does not continue); a chunk
                      that is nothing else is left out
  whole talks         that, and a talk is handed over whole where it first shows: its messages
                      in the chunk before or after come with it, and are not handed over again
  whole talks, nothing left out   a talk handed over whole where it first shows, the records that
                      are not the product's own work included (the two things apart)

context_recall_id: the share of the question's cited records that are handed over whole inside
72,000 characters. The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/the_ties_on_the_arms_run.py [run folder]
"""
import json
import os
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test"), str(HERE / "first_gold_rounds")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"

import ties as TI  # noqa: E402
from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from harness import questions as HQ  # noqa: E402
from harness.char_budget import cut_at_budget  # noqa: E402

RUN = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "output/k=chars/artefact_v4__gold100__cb72000__20261012T212549Z_combo"
BUDGET = 72000
rows = [json.loads(line) for line in (RUN / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
asked = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the ties on the arm's run")
at = {chunk_id: i for i, chunk_id in enumerate(p.chunk_ids)}
doc_cache = {}
print(f"prepared; {len(rows)} rows of {RUN.name}", flush=True)


def records_of(i, kept={}):
    if i not in kept:
        row = p.chunk_rows[i]
        loc = json.loads(row["locator"])
        text, ids = _resolve_chunk(row, doc_cache)
        kept[i] = (text, [str(x) for x in ids], None if "char_range" in loc else loc)
    return kept[i]


def text_of(ids, P):
    """The arm's own text of a chunk: its records as JSON, one a line."""
    return "\n".join(json.dumps(P["raw"][r][1], ensure_ascii=False) for r in ids)


def hand_over(units, cites):
    """units: (unit id, text, record ids). The harness's cut; a record counts when its unit is handed over whole."""
    units = list(units)
    cut = cut_at_budget(((uid, text) for uid, text, _ in units), BUDGET)
    got = set()
    for _, _, ids in units[:cut.kept]:
        got.update(ids)
    first = bool(cites & set(units[0][2])) if units else False
    return first, len(cites & got) / len(cites), cut.kept


WAYS = ("as the run has it", "own work only", "whole talks", "whole talks, nothing left out")
results = {way: [] for way in WAYS}
types, own_run = [], []
share_apart = []
same_text = Counter()
for row in rows:
    q = asked[row["id"]]
    cites = {str(c) for c in q.citations}
    order = [at[c] for c in row["meta"]["ranking"]["ordered_chunk_ids"]]
    product = str(p.chunk_rows[order[0]]["parent"]).split(".")[1]
    P = TI.product(product)
    whole, own, part = {}, {}, {}
    for i in order:
        text, ids, loc = records_of(i)
        whole[i] = (text, ids)
        part[i] = loc is None
        own[i] = ids if part[i] else [r for r in ids if not TI.apart(r, P)]
        if not part[i]:
            same_text[text_of(ids, P) == text] += 1      # the records' text made here is the arm's own
    slack = {i: bool(whole[i][1]) and whole[i][1][0] in P["talk_of"] for i in order}

    def own_text(i):
        return whole[i][0] if part[i] or len(own[i]) == len(whole[i][1]) else text_of(own[i], P)

    def whole_talks(kept_records, kept_text):
        talk_records = defaultdict(list)
        for i in sorted(order, key=lambda i: (str(p.chunk_rows[i]["parent"]), int(p.layer["id_rank"][i]))):
            if slack[i]:
                for r in kept_records[i]:
                    talk_records[P["talk_of"][r]].append(r)
        seen, sent = set(), set()
        for i in order:
            if not kept_records[i]:
                continue
            if not slack[i]:
                yield p.chunk_ids[i], kept_text(i), kept_records[i]
                continue
            ids = []
            for r in kept_records[i]:
                t = P["talk_of"][r]
                if t not in seen:
                    seen.add(t)
                    ids.extend(talk_records[t])
            ids = [r for r in dict.fromkeys(ids) if r not in sent]
            if ids:
                yield p.chunk_ids[i], text_of(ids, P), ids
                sent.update(ids)

    results["as the run has it"].append(hand_over(((p.chunk_ids[i], whole[i][0], whole[i][1]) for i in order), cites))
    results["own work only"].append(hand_over(((p.chunk_ids[i], own_text(i), own[i]) for i in order if own[i]), cites))
    results["whole talks"].append(hand_over(whole_talks(own, own_text), cites))
    results["whole talks, nothing left out"].append(
        hand_over(whole_talks({i: whole[i][1] for i in order}, lambda i: whole[i][0]), cites))
    types.append(str(q.type))
    own_run.append(len(cites & {str(x) for x in row["context_ids"]}) / len(cites))
    kept = results["as the run has it"][-1][2]
    chars = sum(len(whole[i][0]) for i in order[:kept])
    share_apart.append(sum(len(whole[i][0]) - len(own_text(i)) if own[i] else len(whole[i][0]) for i in order[:kept]) / max(chars, 1))

count = len(rows)
print(f"\nthe run's own context_recall_id from its delivered record ids: {np.mean(own_run):.4f}; "
      f"this script's 'as the run has it': {np.mean([r[1] for r in results['as the run has it']]):.4f}")
print(f"chunk texts made here from the records, the same as the arm's own text: {same_text[True]} of {sum(same_text.values())}")
print(f"of the characters the run hands over whole, in records that are not the product's own work: {np.mean(share_apart):.1%}")
print("\n== units handed over whole, a question | first handed over holds a cited record (of 100) | context_recall_id ==")
base = np.array([r[1] for r in results["as the run has it"]])
for way in WAYS:
    a = np.array(results[way], dtype=np.float64)
    diff = a[:, 1] - base
    tail = "" if way == WAYS[0] else (f"   [against the run: {diff.mean():+.3f}, standard error "
                                      f"{diff.std(ddof=1) / np.sqrt(diff.size):.3f}, higher on {int((diff > 1e-9).sum())}, "
                                      f"lower on {int((diff < -1e-9).sum())}]")
    print(f"  {a[:, 2].mean():5.1f} | {int(a[:, 0].sum()):3d} | {a[:, 1].mean():.3f}  {way}{tail}")
print("\n== by the benchmark's own type of question: questions | first handed over holds a cited record, context_recall_id: "
      + " ; ".join(WAYS) + " ==")
types = np.array(types)
for kind in sorted(set(types.tolist())):
    pick = types == kind
    line = " ; ".join(f"{int(np.array(results[way], dtype=np.float64)[pick, 0].sum()):2d}, "
                      f"{np.array(results[way], dtype=np.float64)[pick, 1].mean():.3f}" for way in WAYS)
    print(f"  {kind:8s} {int(pick.sum()):3d} | {line}")
print("done", flush=True)

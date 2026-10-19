"""His 2026-10-10 "do an independent test and see if you can see a relationship between goldchunks
and tags and desc" · "and scope ofc".

Per question: the gold chunks are the pool chunks that hold a record the gold answer cites. How
they stand against the other chunks by what the graph gives:

  description   the chunk description's closeness to the query description
  question      the chunk description's closeness to the question
  tags          the closeness of the chunk's closest tag to a query tag
  scope         where the gold chunks sit in the tree: branch, kind of record, own scope

Not the arm's ordering code: only its read of the graph, its query side (the cached first call,
the kept query vectors) and the harness's own cut at the budget. The gold ids are read inside this
script; it prints numbers and ids only: no question text, no answer, no record text.

    .venv/Scripts/python.exe output/research/2026-10-10-gold-relationship/gold_tags_desc_scope.py [10smoke]
"""
import json
import os
import sys
import warnings
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"            # the cached first call only, no model call

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "10smoke"
BUDGET = 72000
KS = (3, 4, 5, 6, 7)
DRAWS = 200
SIGNALS = ("description", "question", "tags")

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the gold relationship test")
layer, n = p.layer, len(p.chunk_ids)

# every pool chunk as the harness hands it over: its records and its length
docs, records, length = {}, [], np.zeros(n, dtype=np.int64)
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    records.append(frozenset(str(x) for x in ids))
    length[i] = len(text)
in_pool = frozenset().union(*records)
branches = V.tree_level(p.tree, "product")
branch_names = [name for name, _ in branches]
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, members) in enumerate(branches):
    branch_of[members] = b
leaves = V.tree_leaves(p.tree)
kind_names, kind_of = layer["kind_names"], layer["kind"]
id_rank = layer["id_rank"]
print(f"{SET}: {len(wanted)} questions; pool {n} chunks, {len(in_pool)} records; a chunk is "
      f"{int(np.median(length))} characters at the middle; budget {BUDGET}")


def recall_of(order, cites):
    """context_recall_id of an order cut at the budget as the harness cuts it: whole chunks while
    they fit, and the share of the cited records among the records of those chunks."""
    fits = np.cumsum(length[order]) <= BUDGET
    kept = int(fits.sum()) if fits.all() else int(np.argmin(fits))
    got = set().union(*(records[i] for i in order[:kept])) if kept else set()
    return len(cites & got) / len(cites), kept


def ceiling(cites, within):
    """The most the budget can hold: again and again the chunk that adds the most cited records
    not yet in and still fits, the shorter chunk on a tie."""
    left, room, got, kept = set(within.tolist()), BUDGET, set(), 0
    while True:
        best = None
        for i in left:
            add = len((records[i] & cites) - got)
            if add and length[i] <= room and (best is None or (add, -length[i]) > best[0]):
                best = ((add, -length[i]), i)
        if best is None:
            return len(got) / len(cites), kept
        i = best[1]
        got |= records[i] & cites
        room -= length[i]
        left.discard(i)
        kept += 1


rng = np.random.default_rng(20261010)
total = {"pool": {s: [] for s in SIGNALS}, "branch": {s: [] for s in SIGNALS}}
places = {"pool": {s: [] for s in SIGNALS}, "branch": {s: [] for s in SIGNALS}}
top, random_branch, branch_sizes = {"pool": [], "branch": []}, [], []
TOGETHER = {"tags and description": ("tags", "description"), "tags and question": ("tags", "question"),
            "all three": SIGNALS}
together = {where: {name: [] for name in TOGETHER} for where in ("pool", "branch")}
same = {where: Counter() for where in ("pool", "branch")}
same_recall = {where: {"either, at twice the budget": [], "side by side inside the budget": []}
               for where in ("pool", "branch")}
clouds = {k: Counter() for k in KS}
gauge = {k: Counter() for k in KS}
gold_kinds, branch_kinds, scope_rows = Counter(), Counter(), []
facet = Counter()
print("\nper question: gold chunks | cited records in the pool of all cited | branches holding gold "
      "(share in the largest) | own scopes holding gold | context_recall_id at the budget by one "
      "signal alone: description, question, tags over the whole pool, then inside the gold's branch | "
      "the most the budget can hold")
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    content, _, _ = V._interpret(q.question, p)
    tags = [t.text for t in content.tags]
    asked = [t.text for t in content.query_tags]
    got, _, _ = V._tag_cosines(content.description, tags, p)
    rows, d_description = list(got["tags"]), np.asarray(got["description"], dtype=np.float64)
    if asked:
        rows += list(V._tag_cosines(content.description, asked, p)[0]["tags"])
    rows = np.array(rows, dtype=np.float64)
    named = np.array([t.facet_index for t in (*content.tags, *content.query_tags)], dtype=np.int64)
    d_question = np.asarray(V._query_cosines(content.question, [], p)[0]["query_description_cosines"],
                            dtype=np.float64)
    on_edge = rows[:, layer["edge_tag"]]
    t_near, t_edge = WK.best_edges(on_edge.max(axis=0), layer["edge_chunk"], n)
    has = t_edge >= 0
    t_near = np.where(has, t_near, t_near[has].min())
    signal = {"description": d_description, "question": d_question, "tags": t_near}

    gold = np.array([bool(records[i] & cites) for i in range(n)])
    g = np.flatnonzero(gold)
    held = Counter(branch_of[g].tolist())
    main, most = held.most_common(1)[0]
    inside = np.flatnonzero(branch_of == main)
    own = [k for k, (_, members) in enumerate(leaves) if gold[members].any()]
    largest_own = max(int(gold[leaves[k][1]].sum()) for k in own) if own else 0
    line = []
    for where, chunks in (("pool", np.arange(n)), ("branch", inside)):
        for s in SIGNALS:
            x = signal[s][chunks]
            order = chunks[np.lexsort((id_rank[chunks], -x))]
            r, _ = recall_of(order, cites)
            total[where][s].append(r)
            line.append(r)
            place = rankdata(-x, method="average")
            places[where][s] += place[gold[chunks]].tolist()
        # two or three signals together: each chunk's place by each signal, averaged
        place_of = {s: rankdata(-signal[s][chunks], method="average") for s in SIGNALS}
        for name, parts in TOGETHER.items():
            joint = np.mean([place_of[s] for s in parts], axis=0)
            together[where][name].append(recall_of(chunks[np.lexsort((id_rank[chunks], joint))], cites)[0])
        c, _ = ceiling(cites, chunks)
        top[where].append(c)
    # do the two routes deliver the same chunks? each route's own order cut at the budget
    for where, chunks in (("pool", np.arange(n)), ("branch", inside)):
        orders = {s: chunks[np.lexsort((id_rank[chunks], -signal[s][chunks]))] for s in ("tags", "description")}
        kept = {s: orders[s][:recall_of(orders[s], cites)[1]] for s in orders}
        t_set, d_set = set(kept["tags"].tolist()), set(kept["description"].tolist())
        t_gold, d_gold = {i for i in t_set if gold[i]}, {i for i in d_set if gold[i]}
        either = t_set | d_set
        both_records = set().union(*(records[i] for i in either)) if either else set()
        # side by side inside one budget: one chunk from each order in turn, a chunk taken once
        turn, seen = [], set()
        for a, b in zip(orders["tags"], orders["description"]):
            for i in (int(a), int(b)):
                if i not in seen:
                    seen.add(i)
                    turn.append(i)
        same[where].update({"tags": len(t_set), "description": len(d_set), "same": len(t_set & d_set),
                            "gold_tags": len(t_gold), "gold_description": len(d_gold),
                            "gold_same": len(t_gold & d_gold), "gold_either": len(t_gold | d_gold),
                            "gold": int(g.size)})
        same_recall[where]["either, at twice the budget"].append(len(cites & both_records) / len(cites))
        same_recall[where]["side by side inside the budget"].append(recall_of(np.array(turn), cites)[0])
    random_branch.append(float(np.mean([recall_of(rng.permutation(inside), cites)[0] for _ in range(DRAWS)])))
    branch_sizes.append(int(inside.size))
    print(f"  {qid.split('::')[0]}:{qid.split('::')[-1]} | {g.size} | {len(cites & in_pool)} of {len(cites)} | "
          f"{len(held)} ({most / g.size:.2f}) | {len(own)} | "
          + " ".join(f"{v:.2f}" for v in line[:3]) + " | " + " ".join(f"{v:.2f}" for v in line[3:])
          + f" | pool {top['pool'][-1]:.2f}, branch {top['branch'][-1]:.2f}")
    scope_rows.append((g.size, len(held), most / g.size, len(own), largest_own / g.size))
    gold_kinds.update(kind_names[k] for k in kind_of[g].tolist())
    branch_kinds.update(kind_names[k] for k in kind_of[inside].tolist())

    for k in KS:
        cloud = {s: WK.levels(signal[s], k) == 1 for s in SIGNALS}
        both = cloud["tags"] & cloud["description"]
        clouds[k].update({"gold": int(g.size), "gold_tags": int(cloud["tags"][g].sum()),
                          "gold_desc": int(cloud["description"][g].sum()), "gold_both": int(both[g].sum()),
                          "gold_neither": int((~cloud["tags"][g] & ~cloud["description"][g]).sum()),
                          "tags": int(cloud["tags"].sum()), "desc": int(cloud["description"].sum()),
                          "both": int(both.sum()), "gold_question": int(cloud["question"][g].sum()),
                          "question": int(cloud["question"].sum())})
        for name, mask in (("tags", cloud["tags"]), ("description", cloud["description"]),
                           ("question", cloud["question"]), ("both", both)):
            if mask.any():
                counts = np.bincount(branch_of[mask], minlength=len(branches))
                gauge[k][name] += int(counts.argmax() == main and (counts == counts.max()).sum() == 1)

    # the facets on the edge of each chunk's closest tag, inside the gold's branch
    edge = t_edge[inside]
    values = layer["raw"][edge][:, 1:]
    name_of = named[on_edge.argmax(axis=0)[edge]]
    first_raw = values.argmax(axis=1) == name_of
    first_pos = layer["pos"][edge][:, 1:].argmax(axis=1) == name_of
    is_gold = gold[inside]
    for label, mask in (("gold", is_gold), ("other", ~is_gold)):
        facet[label + "_n"] += int(mask.sum())
        facet[label + "_raw"] += int(first_raw[mask].sum())
        facet[label + "_pos"] += int(first_pos[mask].sum())
        facet[label + "_topic"] += float(layer["raw"][edge][mask, 0].sum())

m = len(wanted)
mean = lambda values: float(np.mean(values))
print(f"\n== context_recall_id at {BUDGET} characters by one signal alone, mean over the {m} questions ==")
for where, label in (("pool", "over the whole pool"), ("branch", "inside the branch that holds the gold (known only from the gold)")):
    print(f"  {label}: " + ", ".join(f"{s} {mean(total[where][s]):.3f}" for s in SIGNALS)
          + f"; the most the budget can hold {mean(top[where]):.3f}"
          + (f"; a random order {mean(random_branch):.3f}" if where == "branch" else ""))
    print("      signals together (each chunk's place by each signal, averaged): "
          + ", ".join(f"{name} {mean(together[where][name]):.3f}" for name in TOGETHER))
print("\n== do the tags and the chunk descriptions deliver the same chunks? each alone, cut at the budget, "
      "summed over the questions ==")
for where, label in (("pool", "over the whole pool"), ("branch", "inside the gold's branch")):
    c = same[where]
    print(f"  {label}: delivered by the tags {c['tags']} chunks, by the descriptions {c['description']}, "
          f"the same chunk in both {c['same']}")
    print(f"      gold chunks delivered: by the tags {c['gold_tags']}, by the descriptions {c['gold_description']}, "
          f"the same gold chunk in both {c['gold_same']}, by one or the other {c['gold_either']}, of {c['gold']} "
          "gold chunks in all")
    print("      context_recall_id: " + ", ".join(f"{name} {mean(values):.3f}"
                                                  for name, values in same_recall[where].items()))
print(f"\n== where the gold chunks stand in the order by one signal (1 is first), all {len(places['pool']['tags'])} gold chunks ==")
for where, label, size in (("pool", "over the whole pool", f"{n} chunks"),
                           ("branch", "inside the gold's branch", f"{int(np.median(branch_sizes))} chunks at the middle")):
    print(f"  {label} ({size}): " + "; ".join(
        f"{s}: middle place {np.median(places[where][s]):.0f}, a quarter within {np.percentile(places[where][s], 25):.0f}, "
        f"three quarters within {np.percentile(places[where][s], 75):.0f}" for s in SIGNALS))
print("\n== the clouds (the first of k clusters, over the whole pool), summed over the questions ==")
for k in KS:
    c = clouds[k]
    print(f"  k={k}: of {c['gold']} gold chunks: in the tags' cloud {c['gold_tags']}, in the descriptions' cloud "
          f"{c['gold_desc']}, in both {c['gold_both']}, in neither {c['gold_neither']}, in the question's cloud "
          f"{c['gold_question']} | cloud sizes: tags {c['tags']}, descriptions {c['desc']}, both {c['both']}, "
          f"question {c['question']}")
print("\n== scope ==")
rows_ = np.array(scope_rows, dtype=np.float64)
print(f"  gold chunks per question: middle {np.median(rows_[:, 0]):.0f} (from {rows_[:, 0].min():.0f} to {rows_[:, 0].max():.0f})")
print(f"  branches holding gold per question: {sorted(int(v) for v in rows_[:, 1])}; share of the gold chunks in the largest branch: "
      f"{', '.join(f'{v:.2f}' for v in rows_[:, 2])}")
print(f"  own scopes (a channel, or a kind of record) holding gold per question: {sorted(int(v) for v in rows_[:, 3])}; "
      f"share of the gold chunks in the largest own scope: middle {np.median(rows_[:, 4]):.2f}")
all_gold, all_branch = sum(gold_kinds.values()), sum(branch_kinds.values())
print("  kind of record, share of the gold chunks against share of the gold's branches: "
      + "; ".join(f"{name} {gold_kinds[name] / all_gold:.2f} against {branch_kinds[name] / all_branch:.2f}"
                  for name in sorted(branch_kinds, key=lambda x: -branch_kinds[x])))
print(f"  questions (of {m}) where the branch holding most of a cloud is the gold's branch:")
for k in KS:
    print(f"    k={k}: " + ", ".join(f"{name} {gauge[k][name]}" for name in ("tags", "description", "question", "both")))
print("\n== the facets on the edge of each chunk's closest tag, inside the gold's branch, summed ==")
for label in ("gold", "other"):
    count = facet[label + "_n"]
    print(f"  {label} chunks {count}: the query tag's named facet is the edge's strongest on "
          f"{facet[label + '_raw'] / count:.2f} by the stored values, {facet[label + '_pos'] / count:.2f} by each "
          f"value's place among all edges; topic on that edge, mean {facet[label + '_topic'] / count:.3f}")
print("done", flush=True)

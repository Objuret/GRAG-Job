"""His 2026-10-11 goal: something that beats tags and descriptions half and half. On the hundred,
from the cached query side (no model call): (1) does a route's own delivery point at the gold's
branch; (2) inside that branch, published ways of joining the three routes, each with and without
the structure around a chunk (its neighbours in its parent, the chunks it shares a link with).

Routes: tags (the chunk's closest tag to a query tag), description (chunk description against the
query description), question (chunk description against the question).

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-10-gold-relationship/fusions.py [gold100]
"""
import json
import os
import re
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
os.environ["HERB_V4_OFFLINE"] = "on"

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _load_verified_doc, _resolve_chunk  # noqa: E402
from arms.artefact_v3 import file_adjacency  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
BUDGET = 72000
ROUTES = ("tags", "description", "question")
URL = re.compile(r"https?://[^\s\"'<>\)\]]+")
OWN = ("document_link", "link")
CACHE = REPO / "output/private/artefact_v4_cache/querytag"

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("fusions")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def clean(link):
    return link.rstrip(".,;:!?").rstrip("/").lower()


docs, records, length = {}, [], np.zeros(n, dtype=np.int64)
owns, mentions = [set() for _ in range(n)], [set() for _ in range(n)]
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    records.append(frozenset(str(x) for x in ids))
    length[i] = len(text)
    loc = json.loads(row["locator"])
    arr = _load_verified_doc(row["relpath"], row["sha256"], docs)[loc["section"]]
    for r in [arr[k] for k in (loc["indices"] if "indices" in loc else [loc["index"]])]:
        for key in OWN:
            if isinstance(r.get(key), str) and r[key].startswith("http"):
                owns[i].add(clean(r[key]))
        body = (r[loc["field"]][loc["char_range"][0]:loc["char_range"][1]] if "char_range" in loc
                else " ".join(strings({k: v for k, v in r.items() if k not in OWN})))
        mentions[i].update(clean(u) for u in URL.findall(body))
    mentions[i] -= owns[i]
owner = {}
for i in range(n):
    for link in owns[i]:
        owner.setdefault(link, set()).add(i)
adjacency = file_adjacency([dict(r) for r in p.chunk_rows])
ptr, members = np.asarray(adjacency["ptr"]), np.asarray(adjacency["members"])
next_to = [set(members[ptr[i]:ptr[i + 1]].tolist()) for i in range(n)]
linked = [set() for _ in range(n)]
points_to, pointed_by = [set() for _ in range(n)], [set() for _ in range(n)]
for i in range(n):
    for link in mentions[i]:
        for j in owner.get(link, ()):
            if j != i:
                linked[i].add(j)
                linked[j].add(i)
                points_to[i].add(j)
                pointed_by[j].add(i)
links = Counter()
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b


def cached_sides():
    out = []
    for f in CACHE.glob("*.json"):
        if f.name.endswith(".started.json"):
            continue
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        raw = j.get("raw")
        if j.get("ok") and isinstance(raw, dict) and raw.get("description") and raw.get("tags"):
            out.append((f.stat().st_mtime, (j.get("signature") or {}).get("user") or "", raw))
    return sorted(out, key=lambda row: -row[0])


SIDES = cached_sides()


def side_of(q):
    def names(rows):
        return list(dict.fromkeys(str(r["t"]).strip() for r in rows or []
                                  if isinstance(r, dict) and str(r.get("t", "")).strip()))
    for _, user, raw in SIDES:
        if q.question in user:
            return str(raw["description"]), names(raw.get("tags")), names(raw.get("query_tags"))
    raise SystemExit(f"no cached first call for {q.id}")


def kept_of(order):
    fits = np.cumsum(length[order]) <= BUDGET
    return int(fits.sum()) if fits.all() else int(np.argmin(fits))


def recall_of(order, cites):
    order = np.asarray(order, dtype=np.int64)
    kept = kept_of(order)
    got = set().union(*(records[i] for i in order[:kept])) if kept else set()
    return len(cites & got) / len(cites)


def by_value(chunks, value):
    return chunks[np.lexsort((id_rank[chunks], -value))]


def standing(x):
    """The value less the middle, over the spread (1.4826 times the middle distance from the middle)."""
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


def unit(x):
    lo, hi = x.min(), x.max()
    return (x - lo) / (hi - lo) if hi > lo else np.zeros_like(x)


def around(chunks, value, relation):
    """Per chunk the largest value among the chunks it is related to inside `chunks`; the lowest
    value of all where it has none."""
    at = {int(c): k for k, c in enumerate(chunks)}
    out = np.full(chunks.size, value.min())
    for k, c in enumerate(chunks.tolist()):
        near = [at[j] for j in relation[c] if j in at]
        if near:
            out[k] = value[near].max()
    return out


gauge = Counter()
kinds = Counter()
missed_place, missed_linked = [], []
kind_names, kind_of = layer["kind_names"], layer["kind"]
scores = {}
done = 0
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    description, tags, asked = side_of(q)
    got, _, _ = V._tag_cosines(description, tags, p)
    rows, d_description = list(got["tags"]), np.asarray(got["description"], dtype=np.float64)
    if asked:
        rows += list(V._tag_cosines(description, asked, p)[0]["tags"])
    rows = np.array(rows, dtype=np.float64)
    d_question = np.asarray(V._query_cosines(q.question, [], p)[0]["query_description_cosines"], dtype=np.float64)
    on_edge = rows[:, layer["edge_tag"]]
    t_near, t_edge = WK.best_edges(on_edge.max(axis=0), layer["edge_chunk"], n)
    t_near = np.where(t_edge >= 0, t_near, t_near[t_edge >= 0].min())
    signal = {"tags": t_near, "description": d_description, "question": d_question}
    gold = np.array([bool(records[i] & cites) for i in range(n)])
    main = Counter(branch_of[np.flatnonzero(gold)].tolist()).most_common(1)[0][0]
    done += 1

    # (1) the branch most of a route's own delivery sits in, over the whole pool
    everything = np.arange(n)
    own = {}
    for r in ROUTES:
        order = by_value(everything, signal[r])
        own[r] = order[:kept_of(order)]
        counts = np.bincount(branch_of[own[r]], minlength=len(branches))
        gauge[r] += int(counts.argmax() == main and (counts == counts.max()).sum() == 1)
    for name, parts in (("tags and description", ("tags", "description")), ("all three", ROUTES)):
        counts = sum(np.bincount(branch_of[own[r]], minlength=len(branches)) for r in parts)
        gauge[name] += int(counts.argmax() == main and (counts == counts.max()).sum() == 1)

    # (2) inside the gold's branch
    inside = np.flatnonzero(branch_of == main)
    x = {r: signal[r][inside] for r in ROUTES}
    z = {r: standing(x[r]) for r in ROUTES}
    u = {r: unit(x[r]) for r in ROUTES}
    place = {r: rankdata(-x[r], method="average") for r in ROUTES}
    related = [next_to[c] | linked[c] for c in range(n)]
    cand = {}
    for label, parts in (("tags + description", ("tags", "description")), ("three routes", ROUTES)):
        cand[f"{label}: standings added"] = sum(z[r] for r in parts)
        cand[f"{label}: values stretched to 0-1, added"] = sum(u[r] for r in parts)
        cand[f"{label}: reciprocal places added (RRF, 60)"] = sum(1. / (60. + place[r]) for r in parts)
        cand[f"{label}: the larger standing"] = np.max([z[r] for r in parts], axis=0)
    base = cand["three routes: standings added"]
    for label, relation in (("neighbours", next_to), ("links", linked), ("neighbours and links", related)):
        near = around(inside, base, relation)
        cand[f"three routes, standings added, plus the best of its {label} (standing of that, added)"] = base + standing(near)
        cand[f"three routes, standings added; a chunk is raised to its best {label[:-1] if label.endswith('s') and ' ' not in label else label} when that is higher, less one spread"] = \
            np.maximum(base, near - 1.4826 * np.median(np.abs(base - np.median(base))))
    for name, value in cand.items():
        scores.setdefault(name, []).append(recall_of(by_value(inside, value), cites))
    # orders that walk the structure from the three routes' sum
    first = by_value(inside, base).tolist()
    within = set(inside.tolist())

    def followed(order, relation):
        """Each chunk of the order, then the chunks the relation ties to it that are not taken yet."""
        out, seen = [], set()
        for i in order:
            for j in [i] + sorted((x for x in relation[i] if x in within), key=lambda x: first.index(x)):
                if j not in seen:
                    seen.add(j)
                    out.append(j)
        return out

    def in_turn_with(order, relation):
        """One chunk from the order, then one the relation ties to a chunk already taken (the one
        tied to the earliest taken chunk first), in turn."""
        out, seen, edge, at = [], set(), [], 0
        while len(out) < len(order):
            while at < len(order) and order[at] in seen:
                at += 1
            if at < len(order):
                i = order[at]
                seen.add(i)
                out.append(i)
                edge += [x for x in sorted(relation[i] & within, key=lambda x: first.index(x)) if x not in seen]
            edge = [x for x in edge if x not in seen]
            if edge:
                i = edge.pop(0)
                seen.add(i)
                out.append(i)
                edge += [x for x in sorted(relation[i] & within, key=lambda x: first.index(x)) if x not in seen]
        return out

    walks = {
        "three routes' sum, each chunk followed by the chunks whose link it shares": followed(first, points_to),
        "three routes' sum, each chunk followed by the chunks it shares a link with, either way": followed(first, linked),
        "three routes' sum, each chunk followed by the chunks next to it": followed(first, next_to),
        "three routes' sum, each chunk followed by its links and the chunks next to it": followed(first, related),
        "three routes' sum and, in turn, a chunk whose link a taken chunk shares": in_turn_with(first, points_to),
        "three routes' sum and, in turn, a chunk linked either way with a taken chunk": in_turn_with(first, linked),
        "three routes' sum and, in turn, a chunk next to a taken chunk": in_turn_with(first, next_to),
        "three routes' sum and, in turn, a chunk linked with or next to a taken chunk": in_turn_with(first, related),
    }
    for name, order in walks.items():
        scores.setdefault(name, []).append(recall_of(order, cites))
    kept_first = set(first[:kept_of(np.array(first))])
    for c in inside.tolist():
        if gold[c]:
            kind = kind_names[kind_of[c]]
            links["gold", kind] += 1
            links["pointed to by a chunk of the branch", kind] += int(bool(pointed_by[c] & within))
            links["pointed to by a gold chunk", kind] += int(any(gold[j] for j in pointed_by[c]))
            links["pointed to by a chunk the sum delivers", kind] += int(bool(pointed_by[c] & kept_first))
            links["points to a gold chunk", kind] += int(any(gold[j] for j in points_to[c]))
    for c in kept_first:
        targets = points_to[c] & within
        links["delivered chunks", "all"] += 1
        links["delivered chunks that share a link", "all"] += int(bool(targets))
        links["chunks whose link a delivered chunk shares", "all"] += len(targets)
        links["of those gold", "all"] += sum(int(gold[j]) for j in targets)
    # which gold is delivered, by kind of record, for the half-and-half-like sum and for the best with structure
    for label, name in (("three", "three routes: standings added"),
                        ("structure", "three routes, standings added, plus the best of its neighbours and links (standing of that, added)")):
        order = by_value(inside, cand[name])
        kept = set(order[:kept_of(order)].tolist())
        for c in inside.tolist():
            kind = kind_names[kind_of[c]]
            kinds[label, kind, "delivered"] += int(c in kept)
            kinds[label, kind, "gold"] += int(gold[c])
            kinds[label, kind, "gold delivered"] += int(gold[c] and c in kept)
            kinds[label, kind, "chunks"] += 1
            if gold[c] and c not in kept and label == "structure":
                missed_place.append(float(rankdata(-cand[name], method="average")[list(inside).index(c)]))
                missed_linked.append(bool((next_to[c] | linked[c]) & kept))
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

m = len(wanted)
print(f"\n{SET}: {m} questions")
print("== the branch most of a route's own delivery (over the whole pool) sits in is the gold's branch, questions of "
      f"{m} ==")
print("  " + ", ".join(f"{name} {gauge[name]}" for name in (*ROUTES, "tags and description", "all three")))
print("\n== context_recall_id at the budget inside the gold's branch, mean over the questions ==")
for name, values in sorted(scores.items(), key=lambda kv: -float(np.mean(kv[1]))):
    print(f"  {float(np.mean(values)):.3f}  {name}")
print()
print("== links, inside the gold's branch, summed: gold chunks by kind | a chunk of the branch shares their link | "
      "a gold chunk does | a chunk the three routes' sum delivers does | they share a gold chunk's link ==")
for kind in kind_names:
    if links["gold", kind]:
        print(f"  {kind}: {links['gold', kind]} | {links['pointed to by a chunk of the branch', kind]} | "
              f"{links['pointed to by a gold chunk', kind]} | {links['pointed to by a chunk the sum delivers', kind]} | "
              f"{links['points to a gold chunk', kind]}")
print(f"  of {links['delivered chunks', 'all']} chunks the sum delivers, {links['delivered chunks that share a link', 'all']} "
      f"share a link; the chunks owning those links: {links['chunks whose link a delivered chunk shares', 'all']}, "
      f"gold among them {links['of those gold', 'all']}")
print()
print("== by kind of record, inside the gold's branch, summed: chunks | gold | delivered and gold delivered by "
      "the three routes' sum | by the sum with structure ==")
for kind in kind_names:
    if kinds["three", kind, "chunks"]:
        print(f"  {kind}: {kinds['three', kind, 'chunks']} | {kinds['three', kind, 'gold']} | "
              f"{kinds['three', kind, 'delivered']} and {kinds['three', kind, 'gold delivered']} | "
              f"{kinds['structure', kind, 'delivered']} and {kinds['structure', kind, 'gold delivered']}")
print(f"  gold chunks the sum with structure does not deliver: {len(missed_place)}; their place in that order: middle "
      f"{np.median(missed_place):.0f}, a quarter within {np.percentile(missed_place, 25):.0f}, three quarters within "
      f"{np.percentile(missed_place, 75):.0f}; next to or linked with a delivered chunk: {np.mean(missed_linked):.2f}")
np.save(HERE / f"fusions__{SET}.npy", {name: values for name, values in scores.items()}, allow_pickle=True)
print("done", flush=True)

"""After `the_questions_own_words`: the words of a question that are rare in its branch, and where in
a record they sit. A record's parts: the people on it (a message's user, an author, participants,
a pull request's author and reviewers), its time, its links, its type (a document's or meeting's
type, a pull request's state), its channel, and its running text. And whether the chunk's own
tags or description carry the word.

On the hundred, inside the gold's branch, no model call. A word is rare when at most a tenth of
the branch's chunks hold it; that tenth is the agent's own line, drawn only to have a count.

The gold ids and the question texts are read inside this script; it prints numbers only: no word
of a question is printed.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/where_the_words_sit.py [gold100]
"""
import json
import os
import re
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"
os.environ["HERB_V4_SCOPE_STEP"] = "both"

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _load_verified_doc  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
KEPT = REPO / "output/embed_local/20261007_rev113abe4acafa_float32"
TOKEN = re.compile(r"[a-z0-9]+")
PARTS = ("people", "time", "link", "type", "channel", "running text")
PEOPLE_KEYS = {"userid", "author", "participants", "login"}
TIME_KEYS = {"timestamp", "date", "created_at", "submitted_at"}
LINK_KEYS = {"link", "document_link"}
TYPE_KEYS = {"type", "document_type", "state", "merged", "mergeable"}
CHANNEL_KEYS = {"name", "channelid"}
SKIP_KEYS = {"id", "utterranceid", "number"}


def part_of(key):
    k = key.lower()
    return ("people" if k in PEOPLE_KEYS else "time" if k in TIME_KEYS else "link" if k in LINK_KEYS
            else "type" if k in TYPE_KEYS else "channel" if k in CHANNEL_KEYS else None if k in SKIP_KEYS
            else "running text")


def walk(value, key, out):
    """Every string of a record with the part its field belongs to."""
    if isinstance(value, dict):
        for k, v in value.items():
            walk(v, k, out)
    elif isinstance(value, list):
        for v in value:
            walk(v, key, out)
    elif value is not None:
        part = part_of(key or "")
        if part:
            out[part].update(TOKEN.findall(str(value).lower()))


def kind_of_word(word):
    return "digits" if word.isdigit() else "letters and digits" if any(ch.isdigit() for ch in word) else "letters"


wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("where the words sit")
layer, n = p.layer, len(p.chunk_ids)
et, ec = layer["edge_tag"], layer["edge_chunk"]
texts = {}
for line in (KEPT / "descriptions.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        row = json.loads(line)
        texts[str(row["id"])] = row["text"]
graph_words = [set(TOKEN.findall(texts.get(str(c), "").lower())) for c in p.chunk_ids]
for e in range(et.size):
    graph_words[ec[e]].update(TOKEN.findall(str(p.graph_tags[et[e]]).lower()))
docs, records, parts = {}, [], []
for row in p.chunk_rows:
    loc = json.loads(row["locator"])
    arr = _load_verified_doc(row["relpath"], row["sha256"], docs)[loc["section"]]
    recs = [arr[k] for k in (loc["indices"] if "indices" in loc else [loc["index"]])]
    records.append(frozenset(str(r["id"]) for r in recs if r.get("id") is not None))
    held = {part: set() for part in PARTS}
    for r in recs:
        walk(r, None, held)
    parts.append(held)
every = [set().union(*held.values()) for held in parts]
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b

rare_per_question, by_kind = [], Counter()
cells = defaultdict(lambda: [0, 0])          # part -> gold, chunks: chunks holding a rare word of the question there
in_graph = defaultdict(lambda: [0, 0])       # part -> pairs where the chunk's tags or description hold the word, pairs
questions_with = Counter()
base = [0, 0]
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    gold = np.array([bool(records[i] & cites) for i in range(n)])
    main = Counter(branch_of[np.flatnonzero(gold)].tolist()).most_common(1)[0][0]
    inside = np.flatnonzero(branch_of == main).tolist()
    base[0] += int(gold[inside].sum())
    base[1] += len(inside)
    held_by = Counter()
    for c in inside:
        held_by.update(every[c])
    rare = {w for w in set(TOKEN.findall(q.question.lower())) if 0 < held_by[w] <= len(inside) / 10}
    rare_per_question.append(len(rare))
    by_kind.update(kind_of_word(w) for w in rare)
    seen = set()
    for c in inside:
        for part in PARTS:
            hit = rare & parts[c][part]
            if hit:
                cell = cells[part]
                cell[0] += int(gold[c])
                cell[1] += 1
                seen.add(part)
                for w in hit:
                    pair = in_graph[part]
                    pair[0] += int(w in graph_words[c])
                    pair[1] += 1
    questions_with.update(seen)

m = len(wanted)
print(f"\n{SET}: {m} questions, inside the gold's branch; gold is {base[0]} of {base[1]} chunks ({base[0] / base[1]:.3f})")
q1, mid, q3 = np.percentile(rare_per_question, [25, 50, 75])
print(f"words of a question that at most a tenth of its branch's chunks hold: {mid:.0f} ({q1:.0f}-{q3:.0f}) per "
      f"question; questions with none: {sum(1 for v in rare_per_question if v == 0)}; "
      + ", ".join(f"{k} {v}" for k, v in by_kind.most_common()))
print("\n== where such a word sits in a chunk's records: questions with a chunk holding one there | chunks holding one "
      "there, gold of chunks (share) | of those word-and-chunk pairs, the chunk's own tags or description hold the "
      "word too ==")
for part in PARTS:
    g, t = cells[part]
    a, b = in_graph[part]
    print(f"  {part}: {questions_with[part]} | {g} of {t} ({(g / t if t else 0):.3f}) | {a} of {b} "
          f"({(a / b if b else 0):.2f})")
print("done", flush=True)

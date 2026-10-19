"""The baselines' new unit texts, written out for the embedding job, with the counts that describe them.

    .venv/Scripts/python.exe output/research/2026-10-09-baseline-unit-text/prep_units.py

Writes beside this file: corpus_units.jsonl (id + text of every unit, the order the arms index
them in), sample.jsonl (200 units, evenly spaced, for the two-machine check). Prints counts only:
no unit's text is printed. The earlier unit texts are read from the vector arm's cache of 10-07.
"""
import hashlib
import io
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "prod"))

from arms import lucene, vector  # noqa: E402
from harness import embed, orchestrator  # noqa: E402
from harness.record_text import FORM, units_digest  # noqa: E402

OLD_CACHE = REPO / "output" / "embed_cache" / "llama-nemotron-embed-1b-v2_a43c8c706908de3a.npz"
N_SAMPLE = 200


def q(v):
    v = np.asarray(v)
    return f"min {int(v.min())} median {int(np.median(v))} mean {v.mean():.0f} 99% {int(np.percentile(v, 99))} max {int(v.max())}"


docs = lucene.ingest_corpus(orchestrator.DEFAULT_CORPUS)
vdocs = vector._read_corpus(orchestrator.DEFAULT_CORPUS)
ids = [d["id"] for d in docs]
texts = [d["text"] for d in docs]
assert ids == [d["id"] for d in vdocs] and texts == [d["text"] for d in vdocs]
print(f"form: {FORM}")
print(f"units {len(ids)} | same ids and texts in both arms: True | units_sha256 {units_digest(ids, texts)}")
print(f"the arm's cache file for these texts: {vector._cache_path(ids, texts).name} | exists: {vector._cache_path(ids, texts).is_file()}")

old = np.load(OLD_CACHE, allow_pickle=True)
old_ids, old_texts = list(old["ids"]), list(old["texts"])
assert old_ids == ids, "the unit ids are not those of the 10-07 cache"
print(f"same {len(ids)} unit ids, in the same order, as the 10-07 vectors: True")

kind_of = {d["id"]: d["kind"] for d in docs}
before, after = defaultdict(list), defaultdict(list)
for i, o, n in zip(ids, old_texts, texts):
    before[kind_of[i]].append(len(o))
    after[kind_of[i]].append(len(n))
print("\ncharacters per unit, by kind (vector's text of 10-07 -> the new text):")
for kind in before:
    b, a = np.array(before[kind]), np.array(after[kind])
    print(f"   {kind:<20} n {len(b):>6} | before: {q(b)} | after: {q(a)} | total {b.sum():,} -> {a.sum():,} (x{a.sum() / b.sum():.2f})")
tb, ta = sum(map(len, old_texts)), sum(map(len, texts))
print(f"   all                  n {len(ids):>6} | total {tb:,} -> {ta:,} (x{ta / tb:.2f}) | mean {tb / len(ids):.0f} -> {ta / len(ids):.0f} | "
      f"units that fit in 72,000 characters at the mean: {72000 * len(ids) // tb} -> {72000 * len(ids) // ta}")
print(f"   longer than 72,000 characters: {sum(len(t) > 72000 for t in texts)}")
dup_b = sum(c - 1 for c in Counter(old_texts).values() if c > 1)
dup_a = sum(c - 1 for c in Counter(texts).values() if c > 1)
print(f"units whose text equals an earlier unit's text: before {dup_b}, after {dup_a}")

# the embedder cuts a text at its own longest length: how many units are over it
model = embed._embedder()
limit = int(model.max_seq_length)
prefix = embed.EMBED_PREFIX["passage"]
long_first = sorted(range(len(texts)), key=lambda i: -len(texts[i]))
over, counted, longest = 0, 0, 0
for i in long_first:
    n_tok = len(model.tokenizer(prefix + texts[i], truncation=False)["input_ids"])
    counted += 1
    longest = max(longest, n_tok)
    if n_tok > limit:
        over += 1
    elif len(texts[i]) < limit:      # a text has at most one token per character
        break
print(f"embedder's longest input {limit} tokens | units over it: {over} (longest unit {longest} tokens; "
      f"{counted} longest units tokenised, the rest are shorter than {limit} characters)")


def write(name, rows):
    path = HERE / name
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{name}: {len(rows)} rows, sha256 {hashlib.sha256(path.read_bytes()).hexdigest()}")


corpus = [{"id": i, "text": t} for i, t in zip(ids, texts)]
write("corpus_units.jsonl", corpus)
idx = [int(i) for i in np.linspace(0, len(corpus) - 1, N_SAMPLE)]
write("sample.jsonl", [corpus[i] for i in idx])
(HERE / "sample_idx.json").write_text(json.dumps(idx), encoding="utf-8")

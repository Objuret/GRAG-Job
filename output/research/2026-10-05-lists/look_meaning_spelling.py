"""Does a tag-to-tag score follow meaning or spelling? On the graph's own tag vectors (stored,
passage mode), tag against tag:

  same letters, other capitals        pairs whose names are equal once lower-cased
  singular against plural             pairs equal once a final s is dropped (and lower-cased)
  one word in common                  random pairs sharing at least one word, not the above
  no word in common                   random pairs sharing none
and, for 400 random tags, the closest tag that shares NO word with it, by name.

Graph tag names only; no gold, no question, no model call. Reads the graph through the arm."""
import io
import os
import re
import sys
from pathlib import Path

import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.environ['HERB_V4_OFFLINE'] = 'on'
ROOT = Path('C:/Coding/exjobbet/GRAG-Job')
sys.path[:0] = [str(ROOT / 'prod'), str(ROOT / 'test')]
from harness import chat, orchestrator


def _blocked(*args, **kwargs):
    raise RuntimeError('model call blocked: this measurement makes none')


chat.post = _blocked
import arms.artefact_v4 as A
from graph.db import _readable

prepared = A.prepare_over_corpus(orchestrator.open_corpus(orchestrator.DEFAULT_CORPUS))
try:
    names = [_readable(t) for t in prepared.graph_tags]
    eligible = np.asarray(prepared.casefold_eligible, dtype=bool)
    vectors = np.array(prepared.tag_vectors, dtype=np.float64)
finally:
    prepared.close()
vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
keep = np.flatnonzero(eligible)
names = [names[i] for i in keep]
vectors = vectors[keep]
n = len(names)
STOP = {'the', 'and', 'for', 'of', 'in', 'to', 'on', 'with', 'a', 'an', 'by', 'at', 'from', 'vs', 'as', 'is'}


def words(name):
    return {w for w in re.findall(r"[a-z0-9]+", name.casefold()) if len(w) > 2 and w not in STOP}


def stem(name):
    return ' '.join(w[:-1] if w.endswith('s') and len(w) > 3 else w for w in name.casefold().split())


def five(values):
    v = np.asarray(values)
    return ' / '.join(f'{x:.3f}' for x in np.percentile(v, [5, 25, 50, 75, 95])) + f'   ({v.size} pairs)'


by_fold, by_stem = {}, {}
for i, name in enumerate(names):
    by_fold.setdefault(name.casefold(), []).append(i)
    by_stem.setdefault(stem(name), []).append(i)
case_pairs = [(a, b) for group in by_fold.values() if len(group) > 1
              for k, a in enumerate(group) for b in group[k + 1:]]
plural_pairs = [(a, b) for group in by_stem.values() if len(group) > 1
                for k, a in enumerate(group) for b in group[k + 1:]
                if names[a].casefold() != names[b].casefold()]
rng = np.random.default_rng(20261005)
a, b = rng.integers(0, n, size=60000), rng.integers(0, n, size=60000)
ok = a != b
a, b = a[ok], b[ok]
word_sets = [words(name) for name in names]
shared = np.array([len(word_sets[i] & word_sets[j]) for i, j in zip(a, b)])
cos = np.einsum('ij,ij->i', vectors[a], vectors[b])


def score(pairs):
    p = np.array(pairs)
    return np.einsum('ij,ij->i', vectors[p[:, 0]], vectors[p[:, 1]])


print(f'{n} graph tags, tag against tag, both stored in the same mode; score at 5 / 25 / 50 / 75 / 95%')
print('   same letters, other capitals:  ' + five(score(case_pairs)))
print('   singular against plural:       ' + five(score(plural_pairs)))
print('   random pairs, a word in common:' + ' ' + five(cos[shared >= 1]))
print('   random pairs, no word in common:' + ' ' + five(cos[shared == 0]))
print()
print('examples, same letters with other capitals:')
for i, j in case_pairs[:6]:
    print(f'   {names[i][:36]!r} / {names[j][:36]!r}: {float(vectors[i] @ vectors[j]):.3f}')
print('examples, singular against plural:')
for i, j in plural_pairs[:6]:
    print(f'   {names[i][:36]!r} / {names[j][:36]!r}: {float(vectors[i] @ vectors[j]):.3f}')
print()
print('the closest tag with NO word in common, for 400 random tags (score, the pair):')
picks = rng.choice(n, size=400, replace=False)
found = []
for i in picks:
    if not word_sets[i]:
        continue
    row = vectors @ vectors[i]
    order = np.argsort(-row)
    for j in order[1:200]:
        if not (word_sets[i] & word_sets[j]) and stem(names[i]) != stem(names[j]):
            found.append((float(row[j]), names[i], names[j], int(np.flatnonzero(order == j)[0])))
            break
found.sort(reverse=True)
scores = [f[0] for f in found]
print('   its score, 5 / 25 / 50 / 75 / 95%: ' + ' / '.join(f'{x:.3f}' for x in np.percentile(scores, [5, 25, 50, 75, 95])))
print('   the fifteen highest:')
for s, x, y, place in found[:15]:
    print(f'      {s:.3f}  {x[:38]!r} / {y[:38]!r}')
print('   fifteen around the middle:')
mid = len(found) // 2
for s, x, y, place in found[mid - 7:mid + 8]:
    print(f'      {s:.3f}  {x[:38]!r} / {y[:38]!r}')

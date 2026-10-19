"""How the similarity between two embedded texts actually counts in the local embedder, token
by token, and what the "passage: " in front puts into it. Seeded random letters and sha256
hashes of different lengths stand in for text with no meaning. Embeds about 200 short texts on
the laptop; no other model call, no benchmark file. Run from the repo root.

A  how the model makes one vector of the tokens (its own modules; checked by redoing it)
B  whether the prefix's tokens come out the same whatever stands after them
C  random letters and hashes of growing length: tokens, the cosine between two different ones,
   the cosine to the bare prefix, against the prefix's share of the tokens
D  the vector split in two sums: the prefix's tokens and the text's own tokens
E  the prefix's tokens left out of the vector ("normalized away"), and what is then left
   between unrelated texts; against "query: ", no prefix, and the mean taken off
"""
import hashlib
import itertools
import pathlib
import sys

import numpy as np
import torch

sys.path.insert(0, 'prod')
sys.stdout.reconfigure(encoding='utf-8')
from harness import embed  # noqa: E402

SEED = 20261008
rng = np.random.default_rng(SEED)
model = embed._embedder()
tokenizer = model.tokenizer


def unit(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def token_states(text):
    """The model's output vector for every token of one text, and the tokens."""
    features = model.tokenize([text])
    features = {k: v.to(model.device) for k, v in features.items() if hasattr(v, 'to')}
    with torch.no_grad():
        out = model[0](features)
    states = out['token_embeddings'][0].float().cpu().numpy().astype(np.float64)
    mask = out['attention_mask'][0].cpu().numpy().astype(bool)
    ids = features['input_ids'][0].cpu().numpy()[mask]
    return states[mask], tokenizer.convert_ids_to_tokens(ids.tolist())


def pooled(text):
    return unit(model.encode([text], batch_size=1, convert_to_numpy=True,
                             show_progress_bar=False)[0])


def pairwise(vs):
    return float(np.mean([a @ b for a, b in itertools.combinations(vs, 2)]))


print('== A. how one vector is made of the tokens ==')
for i, module in enumerate(model):
    config = module.get_config_dict() if hasattr(module, 'get_config_dict') else {}
    print(f'  module {i}: {type(module).__name__} '
          + str({k: v for k, v in config.items() if v not in (False, None)})[:300])
states, toks = token_states('passage: rollback procedure')
print(f'  "passage: rollback procedure" is {len(toks)} tokens: {toks}')
print(f'  the bare "passage: " is {token_states("passage: ")[1]}; "query: " is '
      f'{token_states("query: ")[1]}')
mean_of_tokens = unit(states.mean(axis=0))
last_token = unit(states[-1])
whole = pooled('passage: rollback procedure')
print(f'  the model\'s vector against the plain average of its token vectors: '
      f'{whole @ mean_of_tokens:.6f}; against its last token alone: {whole @ last_token:.6f}')

print('\n== B. do the prefix\'s tokens come out the same whatever follows? ==')
bare = token_states('passage: ')[0]
first, second = token_states('passage: a')[1], token_states('passage: b')[1]
k = next(i for i, (a, b) in enumerate(zip(first, second)) if a != b)
print(f'  with a text after it the prefix is the first {k} tokens: {first[:k]}')
for text in ('rollback procedure', 'banana bread', 'xqzvkj wplmrt'):
    s, t = token_states('passage: ' + text)
    shared = min(k, len(t))
    same = [float(unit(s[j]) @ unit(bare[j])) for j in range(shared)]
    print(f'  "passage: {text}": tokens {t}')
    print(f'    its first {shared} token vectors against the bare prefix\'s, token by token: '
          + ' '.join(f'{c:.4f}' for c in same))

print(f'\n== C. random letters and hashes of growing length (seed {SEED}) ==')
LETTERS = list('abcdefghijklmnopqrstuvwxyz')


def letters(n):
    return ''.join(rng.choice(LETTERS, size=n))


def hashes(n):
    out = ''
    while len(out) < n:
        out += hashlib.sha256(rng.bytes(32)).hexdigest()
    return out[:n]


bare_vec = {p: pooled(p) for p in ('passage: ', 'query: ')}
print('  kind | characters | tokens with "passage: " | prefix share of the tokens | cosine '
      'between two different ones: passage / query / no prefix | cosine to the bare '
      '"passage: " | cosine to the bare "query: "')
for kind, make in (('letters', letters), ('sha256', hashes)):
    for n in (3, 6, 12, 24, 48, 96, 192):
        texts = [make(n) for _ in range(5)]
        vp = [pooled('passage: ' + t) for t in texts]
        vq = [pooled('query: ' + t) for t in texts]
        v0 = [pooled(t) for t in texts]
        count = np.mean([len(tokenizer('passage: ' + t)['input_ids']) for t in texts])
        print(f'  {kind:7s} | {n:3d} | {count:5.1f} | {k / count:.2f} | {pairwise(vp):.3f} / '
              f'{pairwise(vq):.3f} / {pairwise(v0):.3f} | '
              f'{np.mean([v @ bare_vec["passage: "] for v in vp]):.3f} | '
              f'{np.mean([v @ bare_vec["query: "] for v in vq]):.3f}')

print('\n== D. the vector as two sums: the prefix\'s tokens and the text\'s own tokens ==')
print('  text | tokens (prefix + own) | length of the prefix\'s sum / of the own sum | cosine '
      'between the two sums | cosine of the whole vector to the prefix\'s sum / to the own sum')
long_text = ('The glacier has retreated almost two kilometres since the first survey, leaving '
             'behind a chain of small lakes held back by ridges of loose rock, and the '
             'researchers who return each summer now have to walk for an extra hour.')
for text in ('GDPR', 'rollback procedure', 'kubernetes pod eviction', long_text):
    s, t = token_states('passage: ' + text)
    head, own = s[:k].sum(axis=0), s[k:].sum(axis=0)
    whole = unit(s.sum(axis=0))
    print(f'  {text[:28]!r:30s} | {k} + {len(t) - k} | {np.linalg.norm(head):.1f} / '
          f'{np.linalg.norm(own):.1f} | {unit(head) @ unit(own):.3f} | '
          f'{whole @ unit(head):.3f} / {whole @ unit(own):.3f}')

print('\n== E. the prefix\'s tokens left out of the vector ==')
SHORT = ['rollback procedure', 'UX improvement', 'banana bread', 'GDPR',
         'quarterly sales forecast', 'kubernetes pod eviction', 'wedding photography',
         'medieval castle']
FAMILY = ['rollback procedures', 'rollback process', 'rollback mechanisms',
          'incorrect rollbacks', 'backup procedures']


def own_only(text):
    s, _ = token_states('passage: ' + text)
    return unit(s[k:].mean(axis=0))


z = np.load(pathlib.Path('output/embed_local/20261007_rev113abe4acafa_float32/tags_passage.npz'),
            allow_pickle=True)
tag_mean = unit(z['matrix'].astype(np.float64)).mean(axis=0)
ways = {
    'behind "passage: ", as the arm has it': lambda t: pooled('passage: ' + t),
    'the same, the prefix\'s tokens left out': own_only,
    'the same, the tags\' mean taken off': lambda t: unit(pooled('passage: ' + t) - tag_mean),
    'behind "query: "': lambda t: pooled('query: ' + t),
    'with no prefix': pooled,
}
print('  way | two unrelated ones: lowest, middle, highest | "rollback procedures" against: '
      + ', '.join(FAMILY[1:]) + ' | against the unrelated: middle')
for label, way in ways.items():
    vs = [way(t) for t in SHORT]
    pw = [a @ b for a, b in itertools.combinations(vs, 2)]
    probe = way(FAMILY[0])
    near = [float(probe @ way(t)) for t in FAMILY[1:]]
    far = float(np.median([probe @ v for v in vs[1:]]))
    print(f'  {label:42s} | {min(pw):+.3f} {np.median(pw):+.3f} {max(pw):+.3f} | '
          + ' '.join(f'{c:+.3f}' for c in near) + f' | {far:+.3f}')

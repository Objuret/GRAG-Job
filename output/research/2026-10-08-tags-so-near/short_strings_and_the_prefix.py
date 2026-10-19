"""What the shared direction of the tag vectors comes from: the local embedder run on a few
unrelated strings of my own (none from a test question), short and long, behind "passage: ",
behind "query: " and with no prefix; the bare prefix alone; and each against the mean of the
graph's tag vectors (local embedder, output/embed_local/20261007_...). Embeds 30 texts on the
laptop, no other model call, no benchmark file. Run from the repo root."""
import itertools
import pathlib
import sys

import numpy as np

sys.path.insert(0, 'prod')
sys.stdout.reconfigure(encoding='utf-8')
from harness import embed  # noqa: E402

SHORT = ['rollback procedure', 'UX improvement', 'banana bread', 'GDPR',
         'quarterly sales forecast', 'kubernetes pod eviction', 'wedding photography',
         'medieval castle']
LONG = [
    'The team spent the afternoon repainting the fence along the northern edge of the garden, '
    'starting with the posts that had rotted over the winter and replacing three of them before '
    'the first coat of green paint could go on, which took until well after the sun had set.',
    'Interest rates were raised by a quarter of a point after the committee reviewed the latest '
    'employment figures, and several members said they expected one more increase before the '
    'end of the year if consumer prices kept climbing at the pace seen during the spring months.',
    'To make the sauce, soften two chopped onions in butter, add a tin of tomatoes and a pinch '
    'of sugar, and let it simmer for at least forty minutes with the lid off, stirring now and '
    'then, until it has thickened enough to coat the back of a wooden spoon without running.',
    'The glacier has retreated almost two kilometres since the first survey, leaving behind a '
    'chain of small lakes held back by ridges of loose rock, and the researchers who return each '
    'summer now have to walk for an extra hour to reach the ice face they used to measure.']
model = embed._embedder()


def vectors(texts):
    out = np.asarray(model.encode(texts, batch_size=1, convert_to_numpy=True,
                                  show_progress_bar=False), dtype=np.float64)
    return out / np.linalg.norm(out, axis=1, keepdims=True)


def pairwise(m):
    return [float(m[a] @ m[b]) for a, b in itertools.combinations(range(m.shape[0]), 2)]


def tokens(texts):
    return [len(ids) for ids in model.tokenizer(texts, add_special_tokens=True)['input_ids']]


z = np.load(pathlib.Path('output/embed_local/20261007_rev113abe4acafa_float32/tags_passage.npz'),
            allow_pickle=True)
tags = z['matrix'].astype(np.float64)
tags /= np.linalg.norm(tags, axis=1, keepdims=True)
mean = tags.mean(axis=0)
mean /= np.linalg.norm(mean)

print('tokens: the bare "passage: " ' + str(tokens(['passage: '])[0]) + ', the bare "query: " '
      + str(tokens(['query: '])[0]) + ', an empty text ' + str(tokens([''])[0]))
for label, prefix in (('behind "passage: "', 'passage: '), ('behind "query: "', 'query: '),
                      ('with no prefix', '')):
    texts = [prefix + s for s in SHORT]
    m = vectors(texts)
    pw = pairwise(m)
    print(f'eight unrelated short strings {label}: tokens a string {min(tokens(texts))}-'
          f'{max(tokens(texts))}; cosine between two of them: lowest {min(pw):.3f}, middle '
          f'{np.median(pw):.3f}, highest {max(pw):.3f}; cosine to the tags\' mean: middle '
          f'{np.median(m @ mean):.3f}')
for label, prefix in (('behind "passage: "', 'passage: '), ('with no prefix', '')):
    texts = [prefix + s for s in LONG]
    m = vectors(texts)
    pw = pairwise(m)
    print(f'four unrelated long texts {label}: tokens a text {min(tokens(texts))}-'
          f'{max(tokens(texts))}; cosine between two of them: lowest {min(pw):.3f}, middle '
          f'{np.median(pw):.3f}, highest {max(pw):.3f}; cosine to the tags\' mean: middle '
          f'{np.median(m @ mean):.3f}')
bare = vectors(['passage: ', 'query: ', 'passage: a'])
print(f'the bare "passage: " against the tags\' mean: {bare[0] @ mean:.3f}; the bare "query: " '
      f'against it: {bare[1] @ mean:.3f}; "passage: a" against it: {bare[2] @ mean:.3f}')
same = vectors(['passage: rollback procedures'])[0]
names = [str(i) for i in z['ids']]
print(f'"rollback procedures" embedded now against its saved local vector: '
      f'{same @ tags[names.index("rollback procedures")]:.6f}')

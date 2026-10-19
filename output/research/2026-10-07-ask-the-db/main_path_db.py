"""The chain's main path asked of the database, against the same path on the arm's arrays, on
the made-up question: a query tag's closeness to every graph tag, its standing among them, that
standing handed along the links to the chunks, each chunk keeping its best.

Read-only, no model call: the first call's answer is read from the cache. Run from the repo
root. The same-thing step, the description side and the lifts are not in this check."""
import json
import pathlib
import sys
import time

import numpy as np

sys.path[:0] = ['prod', 'test']
sys.stdout.reconfigure(encoding='utf-8')
from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_facet_joint import _query_cosines  # noqa: E402
from artefact import query_content as Q  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from graph.db import _driver  # noqa: E402

# One query tag: its closeness to every graph tag of the pool that is not a product's name, the
# middle and the spread of those, each tag's standing above the middle, and that standing handed
# along the tag's links to the pool's chunks. The database's closeness is (1 + cosine) / 2.
MAIN_PATH = '''
MATCH (t:Tag) WHERE t.emb IS NOT NULL
  AND EXISTS { MATCH (t)<-[r:HAS_TAG]-(c:Chunk) WHERE r.run_id = $run AND (c)-[:product]->() }
  AND NOT EXISTS { MATCH (p:Product) WHERE toLower(p.name) = toLower(t.name) }
WITH t, 2 * vector.similarity.cosine(t.emb, $vector) - 1 AS cosine
WITH collect({tag: t, cosine: cosine}) AS rows, percentileCont(cosine, 0.5) AS middle
UNWIND rows AS row
WITH rows, middle, percentileCont(abs(row.cosine - middle), 0.5) AS deviation
UNWIND rows AS row
WITH row.tag AS t, middle, 1.4826 * deviation AS spread,
     CASE WHEN row.cosine > middle THEN (row.cosine - middle) / (1.4826 * deviation)
          ELSE 0.0 END AS standing
MATCH (t)<-[r:HAS_TAG]-(c:Chunk)
WHERE r.run_id = $run AND c.desc_emb IS NOT NULL AND (c)-[:product]->()
RETURN c.chunk_id AS chunk, max(standing) AS value, middle, spread
'''

cache = pathlib.Path('output/private/artefact_v4_cache')
question = json.loads(pathlib.Path('output/walkthrough/20261005T040000Z/walkthrough.json')
                      .read_text(encoding='utf-8'))['question']


def validate(raw):
    cleaned, _ = V._collapse_duplicate_tags(raw)
    return Q.parse(question, cleaned)


content, _, _ = V._ask('querytag', Q.request(question), validate, cache, True)
tags = [t.text for t in (*content.tags, *content.query_tags)]
print(f'{len(tags)} query tags from the saved first-call answer', flush=True)

prepared = V.prepare_over_corpus('data/corpus')
layer = prepared.layer
n = len(prepared.chunk_ids)
dim = prepared.chunk_vectors.shape[1]
matrices, _, _ = _query_cosines(content.description, tags,
                                V._QueryAxes(prepared.tag_vectors, np.eye(dim)), 'passage')
vectors = np.asarray(matrices['query_chunk_cosines'], dtype=np.float64)
cosines = np.asarray(matrices['query_tag_cosines'], dtype=np.float64)
at = {chunk: i for i, chunk in enumerate(prepared.chunk_ids)}

driver = _driver()
worst_value = worst_middle = worst_spread = 0.
seconds = []
same_best = 0
with driver.session(database=V.DATABASE, default_access_mode='READ') as session:
    for i, tag in enumerate(tags):
        # the arrays
        z, bulk, spread = WK.standing(cosines[i][layer['eligible']])
        fit = np.zeros(layer['eligible'].size)
        fit[layer['eligible']] = np.clip(z, 0., None)
        best, _ = WK.best_edges(fit[layer['edge_tag']], layer['edge_chunk'], n)
        arrays = np.where(layer['n_c'] > 0, best, 0.)
        # the database
        started = time.perf_counter()
        rows = list(session.run(MAIN_PATH, run=V.RUN_ID, vector=vectors[i].tolist()))
        seconds.append(time.perf_counter() - started)
        asked = np.zeros(n)
        for row in rows:
            asked[at[row['chunk']]] = row['value']
        apart = float(np.abs(asked - arrays).max())
        worst_value = max(worst_value, apart)
        worst_middle = max(worst_middle, abs(rows[0]['middle'] - bulk))
        worst_spread = max(worst_spread, abs(rows[0]['spread'] - spread))
        same_best += int(np.argmax(asked) == np.argmax(arrays))
        print(f'  {tag!r}: {len(rows)} chunks reached, largest value {arrays.max():.4f} (arrays) '
              f'{asked.max():.4f} (database), furthest apart {apart:.2e}, '
              f'{seconds[-1]:.1f}s', flush=True)
driver.close()
print(f'over the {len(tags)} query tags: a chunk\'s value is at most {worst_value:.2e} apart '
      f'between the database and the arrays; the middle at most {worst_middle:.2e}, the spread '
      f'at most {worst_spread:.2e}')
print(f'the same chunk on top for {same_best} of {len(tags)} query tags')
print(f'the database took {sum(seconds):.1f}s for the {len(tags)} query tags, '
      f'{np.median(seconds):.1f}s at the median')

"""What each part of the walk did on the hundred, read from the saved rows and the graph only:
the picked (facet-ranked) edges, the text side, the tag count and record kind of what was
delivered. No gold file, no question text, no model call, no arm run."""
import io
import json
import os
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = Path('C:/Coding/exjobbet/GRAG-Job')
sys.path[:0] = [str(ROOT / 'prod'), str(ROOT / 'test')]
os.environ['NEO4J_DATABASE'] = 'herb-eval-volmax'
from graph import db

driver = db._driver()
with driver.session(database='herb-eval-volmax', default_access_mode='READ') as session:
    rows = session.run('MATCH (c:Chunk)-[:product]->(p:Product) OPTIONAL MATCH (c)-[:HAS_TAG]->(t:Tag) '
                       'RETURN c.chunk_id AS chunk, c.kind AS kind, p.name AS product, count(t) AS tags').data()
    channel = {r['chunk'] for r in session.run('MATCH (c:Chunk)-[:channel]->() RETURN DISTINCT c.chunk_id AS chunk')}
driver.close()
kind = {r['chunk']: r['kind'] for r in rows}
tags = {r['chunk']: r['tags'] for r in rows}
product_of = {r['chunk']: r['product'] for r in rows}
all_tags = np.array(list(tags.values()))
print(f'pool: {len(rows)} chunks; tags per chunk mean {all_tags.mean():.1f}, median {np.median(all_tags):.0f}; '
      f'in a channel {len(channel & set(kind))} ({len(channel & set(kind)) / len(rows):.3f}); kinds {dict(Counter(kind.values()))}')

out = ROOT / 'output/k=chars/artefact_v4__gold100__cb72000__20261005T223320Z'
recall = {}
for line in (out / 'eval_results.jsonl').read_text(encoding='utf-8').splitlines():
    if line.strip():
        r = json.loads(line)
        if r['metric'] == 'context_recall_id':
            recall[r['question_id']] = r['value']
delivered_tags, delivered_kind, delivered_channel = [], Counter(), 0
picked_class, total_delivered = 0, 0
qs_above, rows_n = 0, 0
spearman = []
query_tags_total = picked_none = 0
picked_edges = []
shares = {k: [] for k in ('tags', 'description', 'product', 'near')}
term_tag_zero = 0
in_product_tags, out_product_tags = [], []
for line in open(out / 'arm_outputs.jsonl', encoding='utf-8'):
    if not line.strip():
        continue
    row = json.loads(line)
    meta = row['meta']
    d = meta['diagnostics']
    ranking = meta['ranking']
    ids = ranking['delivered_chunk_ids']
    total_delivered += len(ids)
    product = row['id'].split('::')[0]
    for c in ids:
        delivered_tags.append(tags[c])
        delivered_kind[kind[c]] += 1
        delivered_channel += c in channel
        (in_product_tags if product_of[c] == product else out_product_tags).append(tags[c])
    classes = d['rank']['delivered_winning_edge_class']
    picked_class += sum(1 for x in classes if x == 0)
    qs_above += d['delivered_rows_with_Qs_above_D']
    rows_n += d['credited_delivered_rows']
    pe = d['rank']['picked_edges_per_query_tag']
    query_tags_total += len(pe)
    picked_none += sum(1 for x in pe if not x)
    picked_edges.extend(pe)
    for k in shares:
        shares[k].append(d['delivered_term_shares'][k])
    order = ranking['ordered_chunk_ids']
    position = np.arange(len(order))
    count = np.array([tags[c] for c in order])
    rp = position.argsort().argsort().astype(float)
    rc = count.argsort(kind='stable').argsort().astype(float)
    from_ranks = np.corrcoef(rp, np.array([np.mean(rc[count == v]) for v in count]))[0, 1]
    spearman.append(from_ranks)
delivered_tags = np.array(delivered_tags)
print(f'delivered (credited) chunks over the 99 questions: {total_delivered}')
print(f'   tags per delivered chunk: mean {delivered_tags.mean():.1f}, median {np.median(delivered_tags):.0f} '
      f'(pool mean {all_tags.mean():.1f}); under the id product {np.mean(in_product_tags):.1f}, outside it {np.mean(out_product_tags):.1f}')
print(f'   Spearman between a chunk\'s place in the order (0 = first) and its number of tags, per question: '
      f'median {np.median(spearman):+.3f} (5% {np.percentile(spearman, 5):+.3f}, 95% {np.percentile(spearman, 95):+.3f}); below 0 on {int(np.sum(np.array(spearman) < 0))} of {len(spearman)}')
print(f'   in a channel: {delivered_channel} ({delivered_channel / total_delivered:.3f}); by kind: '
      + ', '.join(f'{k} {v} ({v / total_delivered:.3f})' for k, v in delivered_kind.most_common()))
pool_kind = Counter(kind.values())
print('   pool by kind: ' + ', '.join(f'{k} {v / len(rows):.3f}' for k, v in pool_kind.most_common()))
print(f'   winning edge among the picked (facet-ranked) edges: {picked_class} of {total_delivered} ({picked_class / total_delivered:.3f})')
print(f'   the raw question stands above the description on {qs_above} of {rows_n} delivered rows ({qs_above / rows_n:.3f})')
pe = np.array(picked_edges)
print(f'query tags {query_tags_total}; picking no graph tag at the same-thing level {picked_none} ({picked_none / query_tags_total:.3f}); '
      f'picked edges per query tag: median {np.median(pe):.0f}, 75% {np.percentile(pe, 75):.0f}, 95% {np.percentile(pe, 95):.0f}, largest {int(pe.max())}')
print('delivered strength shares, median (25%–75%) over questions: '
      + ', '.join(f'{k} {np.median(v):.3f} ({np.percentile(v, 25):.3f}–{np.percentile(v, 75):.3f})' for k, v in shares.items()))

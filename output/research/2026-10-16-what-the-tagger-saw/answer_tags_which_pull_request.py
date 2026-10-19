# Which pull request of a PR batch the May tagger's own answer tags come from. Argument: the unzipped run snapshot
# (git show bcc3156:backend/data/tagging_runs/pilot_full_herb_snapshot_20260514T052226Z.zip).
import json, re, sys, collections
d = sys.argv[1]
kinds = {}
with open(d + '/neo4j_chunks_final.jsonl', encoding='utf-8') as f:
    for l in f:
        r = json.loads(l); kinds[r['cid']] = r['k']
hits = collections.Counter(); n = 0; ntags = collections.Counter()
for l in open(d + '/io.jsonl', encoding='utf-8'):
    r = json.loads(l)
    if r['stage'] != 'extract' or kinds.get(r['target_id']) != 'pr_batch' or not r.get('response_tool_input'):
        continue
    body = r['request']['user'].split('Pull requests:\n', 1)[1]
    recs = re.split(r'\n(?=PR #\d+ \| )', body)
    if len(recs) < 2:
        continue
    n += 1
    tags = r['response_tool_input'].get('tags', [])
    where = set()
    for t in tags:
        tl = t.lower().strip()
        inside = [i for i, rec in enumerate(recs) if tl and tl in rec.lower()]
        if len(inside) == 1:
            where.add('last' if inside[0] == len(recs) - 1 else 'other')
    key = ('only the last PR' if where == {'last'} else
           'the last PR and others' if where == {'last', 'other'} else
           'only other PRs' if where == {'other'} else 'no tag found in one PR alone')
    hits[key] += 1
    ntags[key] += len(tags)
print('PR batches with 2+ pull requests in the request:', n)
for k, v in hits.most_common():
    print(f'  tags that stand in one PR alone point at {k}: {v} chunks, tags a chunk {ntags[k]/v:.1f}')

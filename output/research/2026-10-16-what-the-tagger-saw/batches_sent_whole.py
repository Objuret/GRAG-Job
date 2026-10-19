# Was every record of a batch chunk in the May tagger's request? Argument: the unzipped run snapshot
# (git show bcc3156:backend/data/tagging_runs/pilot_full_herb_snapshot_20260514T052226Z.zip).
import json, sys, collections
sys.path[:0] = ['prod', 'test']
from graph.db import _driver
from arms.artefact_v2 import _load_verified_doc
d = sys.argv[1]
dr = _driver()
with dr.session(database='herb-eval-volmax') as s:
    rows = {r['chunkId']: dict(r) for r in s.run(
        "MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk) WHERE c.kind IN ['pr_batch','slack_thread_batch','meeting_chat_batch','url_batch'] "
        "RETURN c.chunk_id AS chunkId, c.locator_json AS locator, f.rel_path AS relpath, f.sha256 AS sha256, c.kind AS kind")}
dr.close()
cache = {}; whole = collections.Counter(); n = collections.Counter()
for l in open(d + '/io.jsonl', encoding='utf-8'):
    r = json.loads(l)
    if r['stage'] != 'extract' or r['target_id'] not in rows:
        continue
    row = rows[r['target_id']]; loc = json.loads(row['locator'])
    arr = _load_verified_doc(row['relpath'], row['sha256'], cache)[loc['section']]
    recs = [arr[i] for i in (loc['indices'] if 'indices' in loc else [loc['index']])]
    u = r['request']['user']
    def probe(rec):
        vals = [v for v in rec.values() if isinstance(v, str)]
        return max(vals, key=len)[:40] if vals else ''
    found = sum(1 for rec in recs if probe(rec) and (probe(rec) in u or json.dumps(probe(rec), ensure_ascii=False)[1:-1] in u))
    n[row['kind']] += 1
    whole[row['kind']] += found == len(recs)
for k in n:
    print(f'{k}: {n[k]} chunks; every record of the chunk stands in the request on {whole[k]}')

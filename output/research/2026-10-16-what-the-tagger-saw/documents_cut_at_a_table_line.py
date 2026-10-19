# Document and transcript chunks whose text the May tagger cut: its _text_payload split the chunk on "---". Argument: the
# unzipped run snapshot (git show bcc3156:backend/data/tagging_runs/pilot_full_herb_snapshot_20260514T052226Z.zip).
import json, sys, statistics
sys.path[:0] = ['prod', 'test']
from graph.db import _driver
from arms.artefact_v2 import _load_verified_doc
d = sys.argv[1]
dr = _driver()
with dr.session(database='herb-eval-volmax') as s:
    rows = {r['chunkId']: dict(r) for r in s.run(
        "MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk) WHERE c.kind IN ['document','document_part','meeting_transcript','meeting_transcript_part'] "
        "RETURN c.chunk_id AS chunkId, c.locator_json AS locator, f.rel_path AS relpath, f.sha256 AS sha256, c.kind AS kind")}
dr.close()
cache = {}; cut = []; total = 0
for l in open(d + '/io.jsonl', encoding='utf-8'):
    r = json.loads(l)
    if r['stage'] != 'extract' or r['target_id'] not in rows:
        continue
    row = rows[r['target_id']]; loc = json.loads(row['locator'])
    rec = _load_verified_doc(row['relpath'], row['sha256'], cache)[loc['section']][loc['index']]
    field = loc.get('field') or ('content' if 'content' in rec else 'transcript')
    text = rec[field]
    if 'char_range' in loc:
        a, b = loc['char_range']; text = text[a:b]
    total += 1
    sent = r['request']['user'].split('\n---\n')[1]
    if sent.endswith('\n---'):
        sent = sent[:-4]
    if '---' in text and len(sent.strip()) < len(text.strip()):
        cut.append((row['kind'], len(sent.strip()) / len(text.strip())))
print('document and transcript chunks:', total)
print('cut where the text holds "---" (a markdown table line):', len(cut), 'by kind', {k: sum(1 for x in cut if x[0] == k) for k in set(x[0] for x in cut)})
print('share of the chunk\'s text that was sent, middle', round(statistics.median(x[1] for x in cut), 2), 'lowest', round(min(x[1] for x in cut), 2))

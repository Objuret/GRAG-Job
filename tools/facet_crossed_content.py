"""Prepare a method-hidden crossed audit; join independently read source claims."""
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'output/research/2026-09-22-joint-streams/independent_sources'
OUT = BASE / 'crossed_content'
QIDS = ('sentiment_intended_use', 'sentiment_review_observations')
COMPONENTS = {'sentiment_intended_use': ('offering', 'tailoring'),
              'sentiment_review_observations': ('accuracy', 'tests', 'documentation')}

def read(path): return json.loads(path.read_text(encoding='utf-8'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path, value):
    if path.exists(): raise RuntimeError(f'Frozen file already exists: {path}')
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
def payload(path): return json.loads(gzip.decompress(path.read_bytes()))

def prepare():
    gp = ROOT / 'output/research/2026-09-21-facet-validity/route_snapshot/graph.json'
    chunks = {c['chunkId']: c for c in read(gp)['chunks']}
    qp = BASE / 'questions.json'
    sp = BASE / 'query_reconstruction/run/selection_summary.json'
    paths = [Path(__file__), OUT/'PROTOCOL.md', gp, qp, sp]
    questions = [q for q in read(qp) if q['id'] in QIDS]
    rows = [r for r in read(sp) if r['question_id'] in QIDS]
    assert len(rows) == 12 and len(questions) == 2
    union = set(); runs = []
    for r in rows:
        p = sp.parent / r['file']; assert sha(p) == r['sha256']; paths.append(p)
        rec = payload(p)['recruitment']
        union.update(rec['selected_chunk_ids']); union.update(rec['crossing_frontier_chunk_ids'])
        runs.append({k:r[k] for k in ('question_id','reading_id','mode')} |
                    {'file':str(p.relative_to(ROOT))})
    ordered = sorted(union, key=lambda cid:hashlib.sha256(('crossed-content-v1:'+cid).encode()).hexdigest())
    aliases = {cid:f'item_{i:03d}' for i,cid in enumerate(ordered,1)}
    entries = []
    for cid in ordered:
        c = chunks[cid]
        assert hashlib.sha256(c['source_text'].encode()).hexdigest() == c['source_text_sha256']
        entries.append({'passage_id':aliases[cid],
                        'graph_products':[p['name'] for p in c['scope'].get('product',[])],
                        'source_kind':c['source_kind'], 'text':c['source_text']})
    write(OUT/'reader_packet.json', {'questions':questions, 'passages':entries})
    write(OUT/'private_manifest.json', {'input_sha256':{str(p.relative_to(ROOT)):sha(p) for p in paths},
          'packet_sha256':sha(OUT/'reader_packet.json'), 'aliases':aliases, 'runs':runs,
          'passage_count':len(entries), 'source_characters':sum(len(e['text']) for e in entries)})
    print(json.dumps({'passages':len(entries),'characters':sum(len(e['text']) for e in entries)}))

def join():
    manifest = read(OUT/'private_manifest.json'); packet = read(OUT/'reader_packet.json')
    assert sha(OUT/'reader_packet.json') == manifest['packet_sha256']
    assert all(sha(ROOT/p) == h for p,h in manifest['input_sha256'].items())
    texts = {p['passage_id']:p['text'] for p in packet['passages']}
    components = set(sum(COMPONENTS.values(), ())); readers = {}; quotes = 0
    paths = [OUT/'private_manifest.json', OUT/'reader_packet.json', OUT/'PROTOCOL.md', Path(__file__)]
    for name in ('reader_a','reader_b'):
        p = OUT/(name+'.json'); paths.append(p); data = read(p)
        entries = {e['passage_id']:e for e in data['entries']}
        assert len(entries) == len(data['entries']) == len(texts) and set(entries) == set(texts)
        for alias,e in entries.items():
            assert set(e['components']) == components
            for v in e['components'].values():
                assert v['category'] in {'none','context','partial','direct'}
                assert v['scope'] in {'supported','other_system','uncertain'}
                assert v['claim_status'] in {'intended_or_proposed','implemented_or_reviewed','mixed','unclear','none'}
                assert isinstance(v['quotes'],list) and isinstance(v['reason'],str)
                if v['category'] in {'partial','direct'}: assert v['quotes'] and v['reason']
                for quote in v['quotes']:
                    assert isinstance(quote,str) and quote and quote in texts[alias], (name,alias,quote)
                    quotes += 1
        readers[name] = entries
    aliases = manifest['aliases']
    support = {r:{component:{cid for cid,alias in aliases.items()
                  if entries[alias]['components'][component]['category']=='direct'
                  and entries[alias]['components'][component]['scope']=='supported'}
                  for component in components} for r,entries in readers.items()}
    support['intersection'] = {c:support['reader_a'][c] & support['reader_b'][c] for c in components}
    results = []; selections = {}
    for run in manifest['runs']:
        rec = payload(ROOT/run['file'])['recruitment']
        chosen = set(rec['selected_chunk_ids']); selections[(run['question_id'],run['reading_id'],run['mode'])]=chosen
        costs = {cid:f['cumulative_source_characters'] for f in rec['frontiers'] for cid in f['chunk_ids']}
        audits = {}
        for reader,by_component in support.items():
            needs = {}
            for qid,cs in COMPONENTS.items():
                details = {}
                for component in cs:
                    candidates = by_component[component]; finite = {cid:costs[cid] for cid in candidates if cid in costs}
                    minimum = min(finite.values()) if finite else None
                    details[component] = {'selected_support':sorted(aliases[cid] for cid in candidates & chosen),
                        'minimum_known_cost':minimum,
                        'earliest_witnesses':sorted(aliases[cid] for cid,v in finite.items() if v==minimum)}
                minima = [v['minimum_known_cost'] for v in details.values()]
                needs[qid] = {'components':details,'all_components_selected':all(v['selected_support'] for v in details.values()),
                             'minimum_known_complete_cost':max(minima) if all(v is not None for v in minima) else None}
            audits[reader] = needs
        results.append(run | {'selected_count':len(chosen),'audits':audits})
    disagreements = []
    for alias in texts:
        for component in components:
            a = readers['reader_a'][alias]['components'][component]
            b = readers['reader_b'][alias]['components'][component]
            delta = {k:[a[k],b[k]] for k in ('category','scope','claim_status') if a[k]!=b[k]}
            if delta: disagreements.append({'passage_id':alias,'component':component,'differences':delta})
    overlaps=[]
    for mode in ('max','equal','reconstruction'):
        a=[(r,ids) for r,ids in selections.items() if r[0]==QIDS[0] and r[2]==mode]
        b=[(r,ids) for r,ids in selections.items() if r[0]==QIDS[1] and r[2]==mode]
        for ar,ai in a:
            for br,bi in b:
                overlaps.append({'mode':mode,'reading_ids':[ar[1],br[1]],'intersection':len(ai&bi),'union':len(ai|bi),
                    'jaccard':len(ai&bi)/len(ai|bi),'intended_only':len(ai-bi),'review_only':len(bi-ai)})
    write(OUT/'join.json', {'input_sha256':{str(p.relative_to(ROOT)):sha(p) for p in paths},
          'runs':results,'disagreements':disagreements,'overlaps':overlaps,'validated_quotes':quotes,
          'limits':'Two model readers; finite pooled support, not human gold or exhaustive recall. Known complete support is component coverage, not exhaustive answer sufficiency. No facet causality claim.'})
    print(json.dumps({'quotes':quotes,'disagreements':len(disagreements),'runs':len(results)}))

if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','join'])
    args=parser.parse_args(); {'prepare':prepare,'join':join}[args.action]()

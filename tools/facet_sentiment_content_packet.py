"""Freeze source text only for the already selected intended-use contexts."""
import gzip
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'output/research/2026-09-22-joint-streams/independent_sources'
OUT=BASE/'product_connectivity/content_audit'
QID='sentiment_intended_use'

def read(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v): p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def main():
    if OUT.exists(): raise RuntimeError('Existing frozen packet')
    gp=ROOT/'output/research/2026-09-21-facet-validity/route_snapshot/graph.json'
    graph=read(gp);chunks={c['chunkId']:c for c in graph['chunks']}
    question=next(q['question'] for q in read(BASE/'questions.json') if q['id']==QID)
    target=next(t for t in read(BASE/'protocol.json')['targets'] if t['question_id']==QID)
    rows=[r for r in read(BASE/'query_reconstruction/run/selection_summary.json') if r['question_id']==QID]
    assert len(rows)==6
    paths=[Path(__file__),OUT.parent/'CONTENT_PROTOCOL.md',gp,BASE/'questions.json',BASE/'protocol.json',BASE/'query_reconstruction/run/selection_summary.json']
    union={target['preferred']}; runs=[]
    for r in rows:
        p=BASE/'query_reconstruction/run'/r['file'];assert sha(p)==r['sha256'];paths.append(p)
        payload=json.loads(gzip.decompress(p.read_bytes()));rec=payload['recruitment']
        chosen=rec['selected_chunk_ids'];cross=rec['crossing_frontier_chunk_ids']
        union.update(chosen);union.update(cross)
        runs.append({'reading_id':r['reading_id'],'mode':r['mode'],'selected_chunk_ids':chosen,'crossing_chunk_ids':cross,'file':str(p.relative_to(ROOT))})
        for variant,subdir,key in (('Product','product_connectivity/run','aggregation'),('anchor','product_connectivity/anchor_run','mode')):
            vp=BASE/subdir/(r['reading_id']+'_'+r['mode']+'.json.gz');paths.append(vp)
            other=json.loads(gzip.decompress(vp.read_bytes()))
            assert set(other['recruitment']['selected_chunk_ids'])==set(chosen)
    ordered=sorted(union,key=lambda cid:hashlib.sha256(('sentiment-content-v1:'+cid).encode()).hexdigest())
    aliases={cid:f'passage_{i:03d}' for i,cid in enumerate(ordered,1)}
    entries=[]
    for cid in ordered:
        c=chunks[cid]
        assert hashlib.sha256(c['source_text'].encode()).hexdigest()==c['source_text_sha256']
        entries.append({'passage_id':aliases[cid],'graph_products':[p['name'] for p in c['scope'].get('product',[])],
            'source_kind':c['source_kind'],'text':c['source_text']})
    OUT.mkdir()
    write(OUT/'reader_packet.json',{'question':question,'passages':entries})
    write(OUT/'private_manifest.json',{'input_sha256':{str(p.relative_to(ROOT)):sha(p) for p in paths},
        'aliases':aliases,'runs':runs,'control_chunk_id':target['preferred'],
        'packet_sha256':sha(OUT/'reader_packet.json'),'passages':len(entries),
        'source_characters':sum(len(e['text']) for e in entries)})
    print(json.dumps({'passages':len(entries),'source_characters':sum(len(e['text']) for e in entries)}))

if __name__=='__main__': main()

"""Apply the existing frozen graph-anchor resolver to fresh-smoke scores."""
import gzip
import json
from pathlib import Path
import sys
import numpy as np

from facet_fresh_regression import ROOT,BASE,FRESH,STATIC,read,sha,write
from artefact.facet_scope_recruitment import recruit_with_verified_area

OUT=FRESH/'graph_anchor'
ANCHOR=BASE/'product_connectivity/anchor_run'

def main():
    if (OUT/'manifest.json').exists():raise RuntimeError('Preserve prior anchor probe')
    fp=FRESH/'analysis.json';audit=read(fp)
    assert all(sha(ROOT/p)==h for p,h in audit['input_sha256'].items())
    am=read(ANCHOR/'manifest.json');rp=ANCHOR/'resolutions.json'
    assert sha(rp)==am['output_sha256']['resolutions.json']
    for n in ('graph.json','arrays.npz'):
        p=STATIC/n;assert sha(p)==am['input_sha256'][str(p.relative_to(ROOT))]
    resolutions=read(rp);graph=read(STATIC/'graph.json');chunks=graph['chunks'];ids=graph['chunk_ids']
    assert ids==[c['chunkId'] for c in chunks]
    paths=[Path(__file__),ROOT/'tools/facet_fresh_regression.py',OUT/'PROTOCOL.md',fp,
           ANCHOR/'manifest.json',rp,STATIC/'graph.json',STATIC/'arrays.npz',
           *[ROOT/'test/artefact'/n for n in ('facet_scope_recruitment.py','facet_recruitment_candidate.py','facet_need_frontier.py')]]
    inputs=[]
    for r in audit['runs']:
        p=ROOT/r['file'];d=read(p);paths.append(p);a=p.parent/'ranking_arrays.npz';paths.append(a)
        assert sha(a)==d['ranking_arrays_sha256']
        with np.load(a,allow_pickle=False) as arr:
            assert arr['chunk_ids'].tolist()==ids;scores=arr['scores'].copy()
        resolution=resolutions[d['question_id']];assert resolution['question']==d['question']
        area=resolution['area_chunk_ids'];pid=resolution['Product_node_id']
        actual=sorted(c['chunkId'] for c in chunks if any(p['node_id']==pid for p in c['scope'].get('product',[]))) if pid else None
        assert area==actual
        oldarea=d['verified_area']['area']['chunk_ids']
        control=recruit_with_verified_area(chunk_rows=chunks,joint_scores=scores,area_chunk_ids=oldarea,source_character_budget=72000)['recruitment']
        assert control==d['recruitment']
        inputs.append((d,scores,resolution))
    frozen={str(p.relative_to(ROOT)):sha(p) for p in paths}
    write(OUT/'manifest.json',{'input_sha256':frozen,'conditions':14,'baseline_controls_exact':14})
    outputs=[]
    for d,scores,resolution in inputs:
        area=resolution['area_chunk_ids'];oldarea=d['verified_area']['area']['chunk_ids']
        rec=recruit_with_verified_area(chunk_rows=chunks,joint_scores=scores,area_chunk_ids=area,area_provenance=resolution,source_character_budget=72000)['recruitment']
        unchanged=set(area or [])==set(oldarea or [])
        if unchanged:assert rec==d['recruitment']
        chosen=set(rec['selected_chunk_ids']);oldchosen=set(d['recruitment']['selected_chunk_ids'])
        row={'question_id':d['question_id'],'reading_id':d['reading_id'],'area_name':resolution['Product_name'],
             'resolution_status':resolution['status'],'area_unchanged':unchanged,
             'selected_chunks':len(chosen),'source_characters':rec['selected_source_characters'],
             'outside_area_chunks':len(chosen-set(area)) if area else None,
             'added_ids':sorted(chosen-oldchosen),'removed_ids':sorted(oldchosen-chosen)}
        name=d['reading_id']+'.json.gz';payload={'summary':row,'resolution':resolution,'recruitment':rec}
        (OUT/name).write_bytes(gzip.compress(json.dumps(payload).encode()))
        row.update(file=name,sha256=sha(OUT/name));outputs.append((row,rec))
    # Every ranking is now saved. Join existing sentiment source judgments only.
    sent=BASE/'crossed_content';aliases=read(sent/'private_manifest.json')['aliases']|read(sent/'supplement_manifest.json')['aliases']
    readers={}
    for reader in ('reader_a','reader_b'):
        entries={}
        for suffix in ('','_supplement'):
            p=sent/(reader+suffix+'.json');entries.update({e['passage_id']:e for e in read(p)['entries']});paths.append(p)
        readers[reader]={c:{cid for cid,a in aliases.items() if entries[a]['components'][c]['scope']=='supported' and entries[a]['components'][c]['category']=='direct'} for c in ('offering','tailoring','accuracy','tests','documentation')}
    readers['intersection']={c:readers['reader_a'][c]&readers['reader_b'][c] for c in readers['reader_a']}
    reverse={a:cid for cid,a in aliases.items()};events={'PR6':{reverse['item_048'],reverse['item_060']},'PR10':{reverse['item_058']}}
    cs={'sentiment_intended_use':('offering','tailoring'),'sentiment_review_observations':('accuracy','tests','documentation')}
    for row,rec in outputs:
        qid=row['question_id']
        if qid not in cs:continue
        chosen=set(rec['selected_chunk_ids']);costs={cid:f['cumulative_source_characters'] for f in rec['frontiers'] for cid in f['chunk_ids']}
        row['known_support']={}
        for reader,ss in readers.items():
            components={c:{'cost':min((costs[cid] for cid in ss[c] if cid in costs),default=None),'selected_ids':sorted(chosen&ss[c])} for c in cs[qid]}
            minima=[v['cost'] for v in components.values()]
            row['known_support'][reader]={'components':components,'complete_cost':max(minima) if all(v is not None for v in minima) else None,'all_selected':all(v['selected_ids'] for v in components.values())}
        row['events']={e:{'cost':min((costs[cid] for cid in cids if cid in costs),default=None),'selected':bool(chosen&cids)} for e,cids in events.items()}
        row['unjudged_selected_ids']=sorted(chosen-set(aliases))
    assert all(sha(ROOT/p)==h for p,h in frozen.items())
    assert all(sha(ROOT/p)==h for p,h in audit['input_sha256'].items())
    write(OUT/'results.json',{'input_sha256':frozen,'support_manifest':str(fp.relative_to(ROOT)),
         'unchanged_exact':sum(r['area_unchanged'] for r,_ in outputs),'rows':[r for r,_ in outputs],
         'limits':'Existing resolver applied to fresh scores; posthoc structural intervention, not semantic entity-resolution or facet calibration validation.'})
    for r,_ in outputs:
        if not r['area_unchanged']:print(json.dumps(r))

if __name__=='__main__':main()

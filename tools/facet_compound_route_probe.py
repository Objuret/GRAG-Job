"""One declared whole-route removal/graft probe; not a proposed retrieval policy."""
import gzip
import json
from pathlib import Path

import numpy as np
from facet_fresh_regression import ROOT,BASE,FRESH,STATIC,QID,TARGET,BETA,read,sha,write
from artefact.facet_scope_recruitment import recruit_with_verified_area

OUT=FRESH/'regression/compound_route'
TAG='multilingual contextual analysis'

def main():
    if OUT.exists():raise RuntimeError('Preserve existing route probe')
    parent=read(FRESH/'regression/results.json')
    assert all(sha(ROOT/p)==h for p,h in parent['input_sha256'].items())
    graph=read(STATIC/'graph.json');chunks=graph['chunks'];ids=graph['chunk_ids'];ci=ids.index(TARGET)
    prior=BASE/'query_reconstruction/run/manifest.json';old_manifest=read(prior)
    paths=[Path(__file__),FRESH/'regression/COMPOUND_PROTOCOL.md',FRESH/'regression/results.json',
           ROOT/'tools/facet_fresh_regression.py',prior,STATIC/'graph.json']
    qs={}
    for label,b in [('old',BASE),('fresh',FRESH)]:
        qp=b/'query_snapshot/queries.json';ap=b/'query_snapshot/arrays.npz';paths += [qp,ap]
        query=next(q for q in read(qp)['queries'] if q['question_id']==QID)
        with np.load(ap,allow_pickle=False) as a:qs[label]=np.maximum(a['description_chunk_cos'][query['description_index']],0)
    data={}
    for repeat in (0,1):
        rid=f'{QID}_0_score_{repeat}'
        op=BASE/'need_selection/replay'/f'{rid}_routes.npz'
        assert sha(op)==old_manifest['input_sha256'][str(op.relative_to(ROOT))]
        fp=FRESH/'retrieval'/rid/'ranking_arrays.npz';jp=fp.parent/'retrieval.json';fresh=read(jp)
        assert sha(fp)==fresh['ranking_arrays_sha256']
        paths += [op,fp,jp]
        with np.load(op,allow_pickle=False) as a:
            assert a['chunk_ids'].tolist()==ids
            tags=a['query_tag_ids'].tolist();oldroute=np.maximum(a['direct_scores'],a['graph_scores'])
        ti=tags.index(TAG)
        with np.load(fp,allow_pickle=False) as a:
            assert a['chunk_ids'].tolist()==ids
            freshroute=np.maximum(a['direct_scores'],a['graph_scores'])
        assert TAG not in fresh['query_tags']
        routes={'old':oldroute,'fresh':freshroute,'old_remove_compound':np.delete(oldroute,ti,axis=1),
                'fresh_add_compound':np.concatenate([freshroute,oldroute[:,ti:ti+1,:]],axis=1)}
        data[repeat]=(routes,oldroute[:,ti,:].T)
    hashes={str(p.relative_to(ROOT)):sha(p) for p in paths}
    OUT.mkdir();write(OUT/'manifest.json',{'input_sha256':hashes,'tag':TAG,'protocol':'../COMPOUND_PROTOCOL.md'})
    rows=[]
    for is_probe in (False,True):
        for repeat,(routes,compound) in data.items():
            for mode in ('old_remove_compound','fresh_add_compound') if is_probe else ('old','fresh'):
                origin='old' if mode.startswith('old') else 'fresh'
                z=routes[mode].max(axis=1).T;scores=qs[origin]*(z@BETA)
                rec=recruit_with_verified_area(chunk_rows=chunks,joint_scores=scores,source_character_budget=72000)['recruitment']
                if not is_probe:
                    p=FRESH/'regression'/f'reading_{repeat}_Q_{origin}_Z_{origin}.json.gz'
                    baseline=json.loads(gzip.decompress(p.read_bytes()))
                    assert rec==baseline['recruitment']
                    assert np.allclose(z[ci],baseline['summary']['Z'],rtol=0,atol=1e-15)
                frontier=next(f for f in rec['frontiers'] if TARGET in f['chunk_ids'])
                tr=next(r for r in rec['rows'] if r['chunk_id']==TARGET)
                row={'reading_index':repeat,'mode':mode,'target_Z':z[ci].tolist(),
                     'target_compound_Z':compound[ci].tolist(),'target_score':float(scores[ci]),
                     'target_original_depth':tr['original_depth'],'target_recovered_depth':tr['depth'],
                     'acquisition_cost':frontier['cumulative_source_characters'],
                     'selected':TARGET in rec['selected_chunk_ids'],
                     'selected_chunks':len(rec['selected_chunk_ids']),'source_characters':rec['selected_source_characters']}
                name=f'reading_{repeat}_{mode}.json.gz'
                (OUT/name).write_bytes(gzip.compress(json.dumps({'summary':row,'recruitment':rec}).encode()))
                row.update(file=name,sha256=sha(OUT/name));rows.append(row)
    assert all(sha(ROOT/p)==h for p,h in hashes.items())
    write(OUT/'results.json',{'input_sha256':hashes,'rows':rows,'limits':'Route bundle includes saved old query facet readings; not a standalone phrase or one-facet intervention.'})
    for r in rows:print(json.dumps({k:r[k] for k in ('reading_index','mode','target_original_depth','acquisition_cost','selected')}))

if __name__=='__main__':main()

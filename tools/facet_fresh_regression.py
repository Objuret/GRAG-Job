"""Disposable numeric-factor diagnosis of the frozen fresh review regression."""
import gzip
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'test'))
from artefact.facet_scope_recruitment import recruit_with_verified_area

BASE=ROOT/'output/research/2026-09-22-joint-streams/independent_sources'
FRESH=BASE/'fresh_smoke'
OUT=FRESH/'regression'
STATIC=ROOT/'output/research/2026-09-21-facet-validity/route_snapshot'
QID='sentiment_review_observations'
TARGET='80728cd305e3e83e0448c948'
BETA=np.array([1,.25,.25,.25,.25])

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):
    if p.exists():raise RuntimeError('Preserve existing artifact: '+str(p))
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
    paths=[Path(__file__),OUT/'PROTOCOL.md',STATIC/'graph.json',
        BASE/'query_reconstruction/run/selection_summary.json',FRESH/'analysis.json',
        *[ROOT/'test/artefact'/n for n in ('facet_scope_recruitment.py','facet_recruitment_candidate.py','facet_need_frontier.py')]]
    audit=read(FRESH/'analysis.json')
    assert all(sha(ROOT/p)==h for p,h in audit['input_sha256'].items())
    graph=read(STATIC/'graph.json');chunks=graph['chunks'];ids=graph['chunk_ids'];at=ids.index(TARGET)
    assert ids==[c['chunkId'] for c in chunks]
    costs={c['chunkId']:len(c['source_text']) for c in chunks}
    descriptions={};qs={}
    for label,b in [('old',BASE),('fresh',FRESH)]:
        mp=b/'query_snapshot/manifest.json';m=read(mp);paths.append(mp)
        for name in ('queries.json','arrays.npz'):
            p=b/'query_snapshot'/name;assert sha(p)==m['output_sha256'][name];paths.append(p)
        meta=read(b/'query_snapshot/queries.json');assert meta['chunk_ids']==ids
        query=next(q for q in meta['queries'] if q['question_id']==QID)
        descriptions[label]=query['description']
        with np.load(b/'query_snapshot/arrays.npz',allow_pickle=False) as a:
            qs[label]=np.maximum(a['description_chunk_cos'][query['description_index']],0)
    originals={r['reading_id']:r for r in read(BASE/'query_reconstruction/run/selection_summary.json')
               if r['question_id']==QID and r['mode']=='max'}
    frozen={str(p.relative_to(ROOT)):sha(p) for p in paths}
    data={}
    for repeat in (0,1):
        rid=f'{QID}_0_score_{repeat}'
        oldp=BASE/'query_reconstruction/run'/originals[rid]['file'];assert sha(oldp)==originals[rid]['sha256']
        old=json.loads(gzip.decompress(oldp.read_bytes()))
        fp=FRESH/'retrieval'/rid/'retrieval.json';fresh=read(fp)
        ap=fp.parent/'ranking_arrays.npz';assert sha(ap)==fresh['ranking_arrays_sha256']
        assert fresh['verified_area']['area']['chunk_ids'] is None
        assert fresh['verified_area']['stream_ids']==['all']
        with np.load(ap,allow_pickle=False) as a:
            assert a['chunk_ids'].tolist()==ids
            profiles={'old':np.asarray(old['facet_profiles']).T,'fresh':a['per_facet_scores'].copy()}
            fresh_scores=a['scores'].copy()
        for p in (oldp,fp,ap):frozen[str(p.relative_to(ROOT))]=sha(p)
        data[repeat]=(old,fresh,profiles,fresh_scores)
    write(OUT/'manifest.json',{'input_sha256':frozen,'question_id':QID,'target':TARGET,
          'coefficients':BETA.tolist(),'budget':72000,'conditions':'two Q origins x two Z origins x two saved readings'})
    rows=[]
    # All endpoint controls are checked before mixed conditions are computed.
    for mixed in (False,True):
        for repeat,(old,fresh,profiles,fresh_scores) in data.items():
            for q_origin,z_origin in [('old','old'),('fresh','fresh')] if not mixed else [('old','fresh'),('fresh','old')]:
                scores=qs[q_origin]*(profiles[z_origin]@BETA)
                rec=recruit_with_verified_area(chunk_rows=chunks,joint_scores=scores,
                      source_character_budget=72000)['recruitment']
                control=None
                if not mixed:
                    saved=old if q_origin=='old' else fresh
                    saved_scores=np.asarray(old['joint_scores']) if q_origin=='old' else fresh_scores
                    delta=float(np.max(np.abs(scores-saved_scores)))
                    assert delta<1e-12
                    assert rec==saved['recruitment'],(repeat,q_origin,'recruitment mismatch')
                    control={'max_score_abs_error':delta,'complete_recruitment_equal':True}
                target=next(r for r in rec['rows'] if r['chunk_id']==TARGET)
                frontier=next(f for f in rec['frontiers'] if TARGET in f['chunk_ids'])
                raw_ids={ids[i] for i,v in enumerate(scores) if v>=scores[at] and v>0}
                full_ids={cid for f in rec['frontiers'] if f['depth']<=target['depth'] for cid in f['chunk_ids']}
                assert target['depth']==target['original_depth'] and target['component_id'] is None
                assert raw_ids<=full_ids
                added=full_ids-raw_ids
                row={'reading_index':repeat,'Q_origin':q_origin,'Z_origin':z_origin,
                     'control':control,'Q':float(qs[q_origin][at]),'Z':profiles[z_origin][at].tolist(),
                     'weighted_Z':float(profiles[z_origin][at]@BETA),'score':float(scores[at]),
                     'target_recovery':target,'selected':TARGET in rec['selected_chunk_ids'],
                     'raw_prefix_characters':sum(costs[c] for c in raw_ids),
                     'recovered_prefix_characters':frontier['cumulative_source_characters'],
                     'recovery_added_characters':sum(costs[c] for c in added),
                     'raw_prefix_ids':sorted(raw_ids),'recovered_prefix_ids':sorted(full_ids),
                     'recovery_added_ids':sorted(added),
                     'selected_chunks':len(rec['selected_chunk_ids']),
                     'selected_source_characters':rec['selected_source_characters']}
                assert row['raw_prefix_characters']+row['recovery_added_characters']==row['recovered_prefix_characters']
                name=f'reading_{repeat}_Q_{q_origin}_Z_{z_origin}.json.gz'
                (OUT/name).write_bytes(gzip.compress(json.dumps({'summary':row,'recruitment':rec}).encode()))
                row['file']=name;row['sha256']=sha(OUT/name);rows.append(row)
    assert all(sha(ROOT/p)==h for p,h in frozen.items())
    write(OUT/'results.json',{'input_sha256':frozen,'descriptions':descriptions,'rows':rows,
          'limits':'Saved-function factor isolation only. Z bundles changing tags, query readings and embeddings. No source judgments or semantic generalization.'})
    for r in rows:
        print(json.dumps({k:r[k] for k in ('reading_index','Q_origin','Z_origin','Q','weighted_Z','selected','raw_prefix_characters','recovered_prefix_characters','recovery_added_characters')}))

if __name__=='__main__':main()

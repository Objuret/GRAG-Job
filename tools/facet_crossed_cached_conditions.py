"""Join new source judgments to old scored conditions, without rescoring."""
import sys
import numpy as np
from facet_crossed_content import ROOT, BASE, OUT, QIDS, COMPONENTS, read, write, sha, payload

sys.path.insert(0, str(ROOT/'test'))
from artefact.facet_recruitment_candidate import recruit_with_record_context

def main():
    manifest=read(OUT/'private_manifest.json'); aliases=manifest['aliases']
    joined=read(OUT/'join.json')
    assert all(sha(ROOT/p)==h for p,h in joined['input_sha256'].items())
    gp=ROOT/'output/research/2026-09-21-facet-validity/route_snapshot/graph.json'
    graph=read(gp); ids=graph['chunk_ids']; chunks=graph['chunks']
    assert [c['chunkId'] for c in chunks]==ids
    old=BASE/'facet_stream_envelope';sp=old/'summary.json'
    rows=[r for r in read(sp) if r['question_id'] in QIDS]
    assert len(rows)==12
    paths=[Path(__file__),gp,sp,OUT/'join.json',OUT/'CACHED_CONDITIONS_PROTOCOL.md',
           ROOT/'test/artefact/facet_recruitment_candidate.py',ROOT/'test/artefact/facet_need_frontier.py']
    support={}
    for reader in ('reader_a','reader_b'):
        entries={e['passage_id']:e for e in read(OUT/(reader+'.json'))['entries']}
        support[reader]={c:{cid for cid,a in aliases.items() if entries[a]['components'][c]['scope']=='supported'
                            and entries[a]['components'][c]['category']=='direct'}
                         for cs in COMPONENTS.values() for c in cs}
    support['intersection']={c:support['reader_a'][c]&support['reader_b'][c] for c in support['reader_a']}
    results=[]; exact=0
    for r in rows:
        p=old/r['file'];paths.append(p);assert sha(p)==r['sha256']
        data=read(p);by_id={v['chunk_id']:v['score'] for v in data['rows']}
        assert set(by_id)==set(ids)
        scores=np.array([by_id[c] for c in ids])
        rec=recruit_with_record_context(chunk_rows=chunks,stream_ids=['all'],stream_scores=scores[None,:],source_character_budget=72000)
        if r['condition']=='intact':
            match=next(v for v in manifest['runs'] if v['reading_id']==r['reading_id'] and v['mode']=='max')
            p0=ROOT/match['file'];paths.append(p0);baseline=payload(p0)
            assert np.array_equal(scores,np.array(baseline['joint_scores']))
            assert rec==baseline['recruitment'], 'Intact recovery mismatch'
            exact+=1
        chosen=set(rec['selected_chunk_ids'])
        costs={cid:f['cumulative_source_characters'] for f in rec['frontiers'] for cid in f['chunk_ids']}
        audits={}
        for reader,ss in support.items():
            needs={}
            for qid,cs in COMPONENTS.items():
                details={}
                for c in cs:
                    finite={cid:costs[cid] for cid in ss[c] if cid in costs}
                    minimum=min(finite.values()) if finite else None
                    details[c]={'selected_support':sorted(aliases[cid] for cid in chosen&ss[c]),
                         'minimum_known_cost':minimum,'earliest_witnesses':sorted(aliases[cid] for cid,v in finite.items() if v==minimum)}
                minima=[d['minimum_known_cost'] for d in details.values()]
                needs[qid]={'components':details,'all_components_selected':all(d['selected_support'] for d in details.values()),
                      'minimum_known_complete_cost':max(minima) if all(v is not None for v in minima) else None}
            audits[reader]=needs
        results.append({k:r[k] for k in ('question_id','reading_id','condition')}|{
              'audits':audits,'selected_count':len(chosen),'unjudged_selected_chunk_ids':sorted(chosen-set(aliases)),
              'selected_source_characters':rec['selected_source_characters']})
    assert exact==4
    write(OUT/'cached_conditions.json',{'input_sha256':{str(p.relative_to(ROOT)):sha(p) for p in paths},
          'runs':results,'exact_baselines':exact,'limits':'Existing scored conditions; fixed finite source pool. Unjudged alternatives can supply earlier or missing information; known-support cost is not exhaustive.'})
    print('Saved',len(results),'cached conditions;',exact,'exact full baseline matches')

if __name__=='__main__':
    from pathlib import Path
    main()

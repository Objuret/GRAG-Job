"""Four matched topic measurements on source-frozen, independently reviewed pairs."""
from pathlib import Path
import json
import hashlib
import numpy as np
from facet_source_first_snapshot import ROOT, read, write, sha, unit, source_helper

BASE = ROOT / 'output/research/2026-09-22-topic-validation'
STATIC = ROOT / 'output/research/2026-09-21-facet-validity/route_snapshot'
OUT = BASE / 'measurement'
EXCLUDED = {'WorkFlowGenie','EdgeForce','ActionGenie','SentimentForce','TrendForce'}


def main():
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError('Refusing to overwrite a frozen measurement')
    graph = read(STATIC/'graph.json')
    chunks = {c['chunkId']:c for c in graph['chunks']}
    cases = []
    inputs = [BASE/'EVALUATION.md',BASE/'cases_even.json',BASE/'cases_odd.json',BASE/'blind_review.json',
              BASE/'exposure.json',BASE/'HEAD_PROVENANCE.md',
              ROOT/'output/facet_pairs/rounds/round1/scores.jsonl',
              ROOT/'output/facet_pairs/rounds/round1/model/config.json',
              STATIC/'graph.json',STATIC/'arrays.npz',Path(__file__),ROOT/'prod/harness/embed.py',
              ROOT/'tools/facet_source_first_snapshot.py',ROOT/'test/graph/db.py']
    review = read(BASE/'blind_review.json')
    assert review['source_snapshot_sha256'] == sha(STATIC/'graph.json')
    judgments = {j['id']:j for j in review['judgments']}
    assert len(judgments) == len(review['judgments'])
    with np.load(STATIC/'arrays.npz') as data:
        et,ec = data['edge_tag'],data['edge_chunk']
    edges = {(graph['chunk_ids'][ci],graph['graph_tags'][ti]) for ti,ci in zip(et,ec)}
    for partition,name in [(0,'cases_even.json'),(1,'cases_odd.json')]:
        doc = read(BASE/name)
        assert doc['source_snapshot_sha256'] == sha(STATIC/'graph.json')
        recorded = review['case_file_sha256']
        assert recorded.get(name,recorded.get(str((BASE/name).relative_to(ROOT)))) == sha(BASE/name)
        assert len(doc['cases']) <= 3
        for case in doc['cases']:
            assert int(hashlib.sha256(case['tag'].encode()).hexdigest(),16)%2 == partition
            assert case['preferred'] in {'a','b','tie'}
            assert case['id'] in judgments and judgments[case['id']]['preferred'] in {'a','b','tie','uncertain'}
            assert case['chunk_a'] != case['chunk_b']
            memberships = []
            for side in ['a','b']:
                cid=case['chunk_'+side]; c=chunks[cid]
                assert (cid,case['tag']) in edges
                products = c['scope'].get('product',[])
                assert not (EXCLUDED & {p['name'] for p in products})
                memberships.append({p['node_id'] for p in products})
                assert hashlib.sha256(c['source_text'].encode()).hexdigest() == c['source_text_sha256']
                for label in [case,judgments[case['id']]]:
                    assert label['quotes_'+side]
                    for quote in label['quotes_'+side]:
                        assert quote and quote in c['source_text'], (case['id'],side,'quote mismatch')
            assert memberships[0]&memberships[1]
            cases.append(case)
    assert len({c['id'] for c in cases}) == len(cases) and cases
    assert set(judgments) == {c['id'] for c in cases}
    exposure=read(BASE/'exposure.json')
    assert exposure['status']=='complete'
    assert exposure['model_config_sha256']==sha(ROOT/'output/facet_pairs/rounds/round1/model/config.json')
    assert {c['id'] for c in exposure['cases']}=={c['id'] for c in cases}
    assert all(exposure['case_file_sha256'][n]==sha(BASE/n) for n in ['cases_even.json','cases_odd.json'])
    ids=sorted({c['chunk_'+side] for c in cases for side in ['a','b']})
    tags=sorted({c['tag'] for c in cases})
    readable=source_helper(ROOT/'test/graph/db.py','_readable')
    label_texts={t:readable(t) for t in tags}
    query_texts=list(dict.fromkeys(label_texts.values()))
    passage_texts=list(dict.fromkeys([*label_texts.values(),
        *[chunks[c]['original_description'] for c in ids],*[chunks[c]['source_text'] for c in ids]]))
    assert all(t.strip() for t in query_texts+passage_texts)
    q_at={t:i for i,t in enumerate(query_texts)};p_at={t:i for i,t in enumerate(passage_texts)}
    from harness import embed
    hashes={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    protocol={'status':'frozen_before_encoding','input_sha256':hashes,'cases':cases,'review':review,
        'graph_structure_verified':True,'quotes_verified':True,'excluded_products':sorted(EXCLUDED),
        'model':{'name':embed.EMBED_MODEL,'revision':embed.EMBED_REVISION,'prefixes':embed.EMBED_PREFIX,
                 'device':embed.EMBED_DEVICE,'dtype':embed.EMBED_DTYPE},
        'query_texts':query_texts,'passage_texts':passage_texts,'tag_texts':label_texts,
        'chunk_ids':ids,'conditions':['passage_description','query_description','passage_source','query_source','cached_topic_head'],
        'head_exposure':exposure,
        'numeric_tie_tolerance':1e-12,'generation_calls':0,'db_calls':0,
        'interpretation':'Purposive source-pair topical-relevance judgments conditional on actual existing graph edges. No retrieval, calibration, CDF, weights, production recommendation or population-accuracy claim.'}
    OUT.mkdir(parents=True)
    write(OUT/'protocol.json',protocol)
    # Read predictions only after all source judgments, exposure and conditions are frozen.
    wanted={(c['chunk_'+side],c['tag']) for c in cases for side in ['a','b']}
    head={}
    with (ROOT/'output/facet_pairs/rounds/round1/scores.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            r=json.loads(line)
            key=(r['chunk_id'],r['tag'])
            if key in wanted:
                assert key not in head
                head[key]=float(r['topic'])
    assert set(head)==wanted and all(np.isfinite(v) for v in head.values())
    import torch
    torch.set_num_threads(4)
    assert embed._model is None
    vectors={};usage={}
    for role,texts in [('query',query_texts),('passage',passage_texts)]:
        value,calls,tokens,_,seconds=embed._embed(texts,role,bar=False)
        vectors[role]=unit(value)
        usage[role]={'calls':calls,'tokens':tokens,'seconds':seconds}
        print(role,len(texts),'texts complete',flush=True)
    np.savez_compressed(OUT/'vectors.npz',**vectors)
    rows=[]
    for case in cases:
        verdict=judgments[case['id']]['preferred']
        agreed=verdict==case['preferred'] and verdict in {'a','b'}
        tag=label_texts[case['tag']]
        measurements={}
        for role in ['passage','query']:
            left=vectors[role][p_at[tag] if role=='passage' else q_at[tag]]
            for form,field in [('description','original_description'),('source','source_text')]:
                values=[float(left @ vectors['passage'][p_at[chunks[case['chunk_'+side]][field]]]) for side in ['a','b']]
                delta=values[0]-values[1]
                predicted='tie' if abs(delta)<=1e-12 else 'a' if delta>0 else 'b'
                measurements[role+'_'+form]={'a':values[0],'b':values[1],'a_minus_b':delta,
                    'preferred_minus_comparison':delta*(1 if verdict=='a' else -1) if agreed else None,
                    'predicted':predicted,'matches_agreed_preference':predicted==verdict if agreed else None}
        values=[head[(case['chunk_'+side],case['tag'])] for side in ['a','b']]
        delta=values[0]-values[1]
        predicted='tie' if abs(delta)<=1e-12 else 'a' if delta>0 else 'b'
        measurements['cached_topic_head']={'a':values[0],'b':values[1],'a_minus_b':delta,
            'preferred_minus_comparison':delta*(1 if verdict=='a' else -1) if agreed else None,
            'predicted':predicted,'matches_agreed_preference':predicted==verdict if agreed else None}
        row={'id':case['id'],'tag':case['tag'],'chunk_a':case['chunk_a'],'chunk_b':case['chunk_b'],
             'source_reader_preferred':case['preferred'],'blind_reviewer_preferred':verdict,
             'agreed_strict_preference':agreed,'measurements':measurements}
        rows.append(row)
        print(case['id'],'agreed',agreed,{k:v['predicted'] for k,v in measurements.items()},flush=True)
    summary={key:{'matches':sum(r['measurements'][key]['matches_agreed_preference'] is True for r in rows),
                  'agreed_strict_pairs':sum(r['agreed_strict_preference'] for r in rows)} for key in protocol['conditions']}
    assert all(sha(ROOT/p)==h for p,h in hashes.items())
    write(OUT/'results.json',{'rows':rows,'descriptive_counts':summary,'usage':usage})
    write(OUT/'verification.json',{'inputs_unchanged':True,'pair_count':len(cases),'unique_tags':len(tags),
         'unique_chunks':len(ids),'vectors_sha256':sha(OUT/'vectors.npz'),'results_sha256':sha(OUT/'results.json')})
    print(summary,flush=True)


if __name__=='__main__':
    main()

"""Recruit an unresolved area via literal graph-Tag-to-Product paths."""
from collections import defaultdict
import gzip
import json
from pathlib import Path
import re
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'prod'),str(ROOT/'test')]
from artefact.facet_scope_recruitment import recruit_with_verified_area
from facet_query_reconstruction_replay import read,write,sha
from facet_product_connectivity import inclusion

BASE=ROOT/'output/research/2026-09-22-joint-streams/independent_sources'
STATIC=ROOT/'output/research/2026-09-21-facet-validity/route_snapshot'
OUT=BASE/'product_connectivity/anchor_run'


def main():
    if OUT.exists():
        raise RuntimeError('Existing anchor run; inspect rather than overwrite')
    graph=read(STATIC/'graph.json')
    ids,chunks=graph['chunk_ids'],graph['chunks']
    with np.load(STATIC/'arrays.npz') as a:
        et,ec=a['edge_tag'],a['edge_chunk']
    tag_chunks=defaultdict(set)
    variants=defaultdict(set)
    products=defaultdict(set)
    product_names={}
    for ti,c in zip(et,ec):
        t=graph['graph_tags'][int(ti)]
        tag_chunks[t.casefold()].add(int(c))
        variants[t.casefold()].add(t)
    for i,c in enumerate(chunks):
        for p in c['scope'].get('product',[]):
            products[p['node_id']].add(ids[i])
            product_names[p['node_id']]=p['name']
    destinations={t:sorted({p['node_id'] for i in cs for p in chunks[i]['scope'].get('product',[])}) for t,cs in tag_chunks.items()}
    old_res=read(BASE/'scope_recruitment/run/resolutions.json')
    queries=read(BASE/'query_snapshot/queries.json')['queries']
    resolutions={}
    for q in queries:
        qid=q['question_id']; raw=q['question'].casefold()
        matches=[{'phrase':t,'variants':sorted(variants[t]),'chunk_ids':sorted(ids[i] for i in cs),
                  'Product_node_ids':destinations[t]} for t,cs in sorted(tag_chunks.items())
                 if re.search(r'(?<!\w)'+re.escape(t)+r'(?!\w)',raw)]
        unique_destinations=sorted({m['Product_node_ids'][0] for m in matches if len(m['Product_node_ids'])==1})
        old=old_res[qid]
        if len(old['matched_product_names'])==1:
            found=[pid for pid,name in product_names.items() if name==old['used_area']]
            assert len(found)==1
            pid=found[0]; status='existing_literal_Product'
        elif old['matched_product_names']:
            pid=None; status='explicit_multiple_Products_no_fallback'
        elif len(unique_destinations)==1:
            pid=unique_destinations[0];status='literal_Tag_paths_agree'
        else:
            pid=None;status='no_anchor_or_conflicting_anchors'
        resolutions[qid]={'question':q['question'],'status':status,'Product_node_id':pid,
            'Product_name':product_names.get(pid),'area_chunk_ids':sorted(products[pid]) if pid else None,
            'all_literal_Tag_matches':matches,'exclusive_anchor_destinations':unique_destinations,
            'old_resolution':old}
    scope_rows={r['reading_id']:r for r in read(BASE/'scope_recruitment/run/summary.json')}
    previous=read(BASE/'query_reconstruction/run/selection_summary.json')
    old_manifest=read(BASE/'query_reconstruction/run/manifest.json')
    paths=[Path(__file__),ROOT/'tools/facet_product_connectivity.py',
        ROOT/'tools/facet_query_reconstruction_replay.py',OUT.parent/'ANCHOR_PROTOCOL.md',
        STATIC/'graph.json',STATIC/'arrays.npz',BASE/'query_snapshot/queries.json',
        BASE/'scope_recruitment/run/resolutions.json',BASE/'scope_recruitment/run/summary.json',
        BASE/'query_reconstruction/run/selection_summary.json',BASE/'query_reconstruction/run/manifest.json',
        ROOT/'test/artefact/facet_scope_recruitment.py',ROOT/'test/artefact/facet_recruitment_candidate.py',
        ROOT/'test/artefact/facet_need_frontier.py',ROOT/'test/artefact/facet_stream_envelope.py',
        ROOT/'test/artefact/facet_joint_candidate.py']
    old_payloads=[]
    for row in previous:
        p=BASE/'query_reconstruction/run'/row['file']
        assert sha(p)==row['sha256']==old_manifest['output_sha256'][p.name]
        sp=BASE/'scope_recruitment/run'/scope_rows[row['reading_id']]['file']
        assert sha(sp)==scope_rows[row['reading_id']]['sha256']
        old_payloads.append((row,json.loads(gzip.decompress(p.read_bytes())),json.loads(gzip.decompress(sp.read_bytes()))))
        paths.extend([p,sp])
    initial={str(p.relative_to(ROOT)):sha(p) for p in paths}
    OUT.mkdir(parents=True)
    write(OUT/'resolutions.json',resolutions)
    write(OUT/'inputs.json',{'input_sha256':initial})
    outputs=[];exact=unchanged=0
    for row,old,scope in old_payloads:
        qid=row['question_id'];resolution=resolutions[qid]
        s=np.array(old['joint_scores'])
        baseline=recruit_with_verified_area(chunk_rows=chunks,joint_scores=s,
            area_chunk_ids=scope['area_chunk_ids'] or None,source_character_budget=72000)['recruitment']
        assert baseline==old['recruitment'];exact+=1
        r=recruit_with_verified_area(chunk_rows=chunks,joint_scores=s,
            area_chunk_ids=resolution['area_chunk_ids'],area_provenance=resolution,
            source_character_budget=72000)['recruitment']
        if set(resolution['area_chunk_ids'] or [])==set(scope['area_chunk_ids'] or []):
            assert r==baseline;unchanged+=1
        payload={'reading_id':row['reading_id'],'question_id':qid,'mode':row['mode'],
                 'joint_scores':old['joint_scores'],'recruitment':r,'resolution_status':resolution['status']}
        name=row['file']
        (OUT/name).write_bytes(gzip.compress(json.dumps(payload,separators=(',', ':'),allow_nan=False).encode(),mtime=0))
        outputs.append((name,payload,old))
    assert exact==len(outputs)==42
    target_path=BASE/'protocol.json'
    targets={t['question_id']:t for t in read(target_path)['targets']}
    summary=[]
    for name,payload,old in outputs:
        t=targets[payload['question_id']]
        focal={'preferred':t['preferred'],'comparison':t['comparison']} if t.get('preferred') else dict(enumerate(t['required_within_selected_pair']))
        chosen=set(payload['recruitment']['selected_chunk_ids']); before=set(old['recruitment']['selected_chunk_ids'])
        summary.append({k:payload[k] for k in ('reading_id','question_id','mode','resolution_status')} |
            {'focal':{role:{'id':cid,'old':inclusion(old['recruitment'],cid),'new':inclusion(payload['recruitment'],cid)} for role,cid in focal.items()},
             'added_chunk_ids':sorted(chosen-before),'removed_chunk_ids':sorted(before-chosen),
             'selected_chunks':len(chosen),'selected_source_characters':payload['recruitment']['selected_source_characters'],
             'file':name,'sha256':sha(OUT/name)})
    write(OUT/'summary.json',summary)
    assert all(sha(ROOT/p)==h for p,h in initial.items())
    initial[str(target_path.relative_to(ROOT))]=sha(target_path)
    write(OUT/'manifest.json',{'input_sha256':initial,'output_sha256':{p.name:sha(p) for p in OUT.iterdir()},
        'baseline_exact':exact,'unchanged_area_exact':unchanged,'selections':len(outputs),'new_model_calls':0,'db_calls':0})
    print(json.dumps({'selections':len(outputs),'baselines_exact':exact,'unchanged_area_exact':unchanged,
        'resolved_names':{qid:{'name':r['Product_name'],'status':r['status']} for qid,r in resolutions.items()}}),flush=True)


if __name__=='__main__':
    main()

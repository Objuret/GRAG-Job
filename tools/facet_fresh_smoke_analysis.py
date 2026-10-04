"""Known-support audit of fresh-query retrievals; no new judgments or scoring."""
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'output/research/2026-09-22-joint-streams/independent_sources'
OUT = BASE/'fresh_smoke'

def read(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,d):
    if p.exists(): raise RuntimeError('Preserve existing smoke audit: '+str(p))
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def verify_frozen_inputs(manifest_path, inputs, paths, key_path=('input_sha256',)):
    """Check reused evidence against a prior freeze, not a newly recorded hash."""
    expected=read(manifest_path)
    for key in key_path:
        expected=expected[key]
    paths.append(manifest_path)
    for path in inputs:
        name=str(path.relative_to(ROOT))
        if name not in expected or sha(path)!=expected[name]:
            raise ValueError('Previously frozen support input differs: '+name)
        paths.append(path)

def main():
    gp=ROOT/'output/research/2026-09-21-facet-validity/route_snapshot/graph.json'
    chunks={c['chunkId']:c for c in read(gp)['chunks']}
    paths=[Path(__file__),gp,OUT/'PROTOCOL.md',OUT/'EXECUTION_NOTE.md']
    cp=OUT/'query_capture/query_captures.json'; paths.append(cp); captures=read(cp)
    expected={(c['question_id'],r['id']) for c in captures['captures'] for r in c['readings'] if r['ok']}
    assert len(expected)==14 and captures['counts']['successful_generations']==7
    oldcp=BASE/'query_capture/query_captures.json';paths.append(oldcp)
    old_captures={c['question_id']:c for c in read(oldcp)['captures']}
    all_support={};pool_by_case={};readers_by_case={};events={}
    action=BASE/'need_selection/content_audit'; sent=BASE/'crossed_content'
    verify_frozen_inputs(BASE/'query_interpretation_intervention/content_cost.json',
        [gp,action/'private_manifest.json',action/'record_context_probe.json',
         *[action/(r+suffix+'.json') for r in ('reader_one','reader_two')
           for suffix in ('','_additional')]],paths)
    verify_frozen_inputs(sent/'private_manifest.json',[gp],paths)
    verify_frozen_inputs(sent/'join.json',
        [sent/'private_manifest.json',sent/'reader_a.json',sent/'reader_b.json'],paths)
    verify_frozen_inputs(sent/'verification.json',
        [sent/'supplement_manifest.json',sent/'supplement_packet.json',
         sent/'reader_a_supplement.json',sent/'reader_b_supplement.json'],paths,
        key_path=('supplement','input_sha256'))
    p=action/'private_manifest.json';q=action/'record_context_probe.json';paths += [p,q]
    aliases=read(p)['aliases']|read(q)['additional_reader_aliases']
    aq='independent_durable_messages_current_models'; readers={}
    for r in ('reader_one','reader_two'):
        entries={}
        for suffix in ('','_additional'):
            p=action/(r+suffix+'.json');paths.append(p)
            entries.update({e['passage_id']:e for e in read(p)['entries']})
        readers[r]={c:{cid for cid,a in aliases.items() if entries[a]['scope']=='supports_requested_system'
                         and entries[a]['components'][c]['category']=='direct'}
                    for c in ('durability','model_updates','refresh_frequency')}
        for cid,a in aliases.items():
            for v in entries[a]['components'].values():
                for quote in v['quotes']: assert quote and quote in chunks[cid]['source_text']
    readers['intersection']={c:readers['reader_one'][c]&readers['reader_two'][c] for c in readers['reader_one']}
    all_support[aq]=readers;pool_by_case[aq]=set(aliases)
    p=sent/'private_manifest.json';q=sent/'supplement_manifest.json';paths += [p,q]
    aliases=read(p)['aliases']|read(q)['aliases'];reverse={a:cid for cid,a in aliases.items()}
    for qid,components in {'sentiment_intended_use':('offering','tailoring'),
                           'sentiment_review_observations':('accuracy','tests','documentation')}.items():
        readers={}
        for r in ('reader_a','reader_b'):
            entries={}
            for suffix in ('','_supplement'):
                p=sent/(r+suffix+'.json');paths.append(p)
                entries.update({e['passage_id']:e for e in read(p)['entries']})
            readers[r]={c:{cid for cid,a in aliases.items() if entries[a]['components'][c]['scope']=='supported'
                           and entries[a]['components'][c]['category']=='direct'} for c in components}
            for cid,a in aliases.items():
                for v in entries[a]['components'].values():
                    for quote in v['quotes']: assert quote and quote in chunks[cid]['source_text']
        readers['intersection']={c:readers['reader_a'][c]&readers['reader_b'][c] for c in components}
        all_support[qid]=readers;pool_by_case[qid]=set(aliases)
        events[qid]={'PR6':{reverse['item_048'],reverse['item_060']},'PR10':{reverse['item_058']}}
    def audit(qid,rec):
        chosen=set(rec['selected_chunk_ids'])
        costs={cid:f['cumulative_source_characters'] for f in rec['frontiers'] for cid in f['chunk_ids']}
        if qid not in all_support:return None
        result={}
        for reader,cs in all_support[qid].items():
            details={}
            for c,cids in cs.items():
                finite={cid:costs[cid] for cid in cids if cid in costs};minimum=min(finite.values()) if finite else None
                details[c]={'selected_witness_ids':sorted(chosen&cids),'known_acquisition_cost':minimum,
                            'first_known_witness_ids':sorted(cid for cid,v in finite.items() if v==minimum)}
            minima=[x['known_acquisition_cost'] for x in details.values()]
            result[reader]={'components':details,'all_components_selected':all(x['selected_witness_ids'] for x in details.values()),
                            'known_complete_acquisition_cost':max(minima) if all(x is not None for x in minima) else None}
        return {'readers':result,'unjudged_selected_chunk_ids':sorted(chosen-pool_by_case[qid]),
                'events':{e:{'selected':bool(chosen&cids),'selected_witness_ids':sorted(chosen&cids),
                              'known_acquisition_cost':min((costs[cid] for cid in cids if cid in costs),default=None)}
                          for e,cids in events.get(qid,{}).items()}}
    sp=BASE/'query_reconstruction/run/selection_summary.json';paths.append(sp)
    originals={(r['question_id'],r['reading_id']):r for r in read(sp) if r['mode']=='max'}
    outputs=sorted(OUT.rglob('retrieval.json')); rows=[];seen=set()
    for p in outputs:
        paths.append(p);d=read(p);key=d['question_id'],d['reading_id'];assert key in expected and key not in seen;seen.add(key)
        assert all(sha(ROOT/q)==h for q,h in d['input_sha256'].items())
        assert d['policy']['coefficients']==[1,.25,.25,.25,.25]
        assert d['policy']['source_character_budget']==72000
        rec=d['recruitment'];chosen=set(rec['selected_chunk_ids'])
        assert {c['chunk_id'] for c in d['contexts']}==chosen
        assert all(c['source_text']==chunks[c['chunk_id']]['source_text'] for c in d['contexts'])
        assert sum(len(chunks[c]['source_text']) for c in chosen)==rec['selected_source_characters']<=72000
        running=0;frontier_ids=set();budget_prefix=set();crossed_budget=False
        for f in rec['frontiers']:
            assert not frontier_ids&set(f['chunk_ids']);frontier_ids.update(f['chunk_ids'])
            running+=sum(len(chunks[c]['source_text']) for c in f['chunk_ids'])
            assert running==f['cumulative_source_characters']
            if not crossed_budget:
                if running<=72000:
                    budget_prefix.update(f['chunk_ids'])
                else:
                    crossed_budget=True
        assert chosen==budget_prefix, 'Selection must be the maximal complete-frontier budget prefix'
        old=originals[key];op=sp.parent/old['file'];paths.append(op);assert sha(op)==old['sha256']
        od=json.loads(gzip.decompress(op.read_bytes()));oldchosen=set(od['recruitment']['selected_chunk_ids'])
        rows.append({'question_id':key[0],'reading_id':key[1],'file':str(p.relative_to(ROOT)),
                     'selected_chunks':len(chosen),'selected_source_characters':rec['selected_source_characters'],
                     'old_selected_chunks':len(oldchosen),'old_selected_source_characters':od['recruitment']['selected_source_characters'],
                     'old_new_selection_jaccard':len(chosen&oldchosen)/len(chosen|oldchosen),
                     'known_support':audit(key[0],rec),'old_known_support':audit(key[0],od['recruitment'])})
    assert seen==expected, 'Do not label an incomplete retrieval stage complete'
    interpretations=[]
    for c in captures['captures']:
        old=old_captures[c['question_id']]
        interpretations.append({'question_id':c['question_id'],'question':c['question'],
                'old_description':old['description'],'fresh_description':c['description'],
                'old_tags':old['clean_tags'],'fresh_tags':c['clean_tags'],
                'tag_jaccard':len(set(c['clean_tags'])&set(old['clean_tags']))/len(set(c['clean_tags'])|set(old['clean_tags']))})
    results=[c['generation_result'] for c in captures['captures']]+[r for c in captures['captures'] for r in c['readings']]
    reported=[r['cost_usd_reported'] for r in results if r.get('cost_usd_reported') is not None]
    put(OUT/'analysis.json',{'input_sha256':{str(p.relative_to(ROOT)):sha(p) for p in set(paths)},
          'capture_counts':captures['counts'],'reported_cost_usd_sum':sum(reported),'cost_reports_available':len(reported),
          'runs':rows,'interpretations':interpretations,'retrievals_verified':len(rows),
          'limits':'Fresh interpretations of seven development questions, not held-out tasks or benchmark/answer evaluation. Component and event costs trace previously judged support only. Unjudged selections remain unknown. Repeat indices are not paired stochastic replications.'})
    print(json.dumps({'counts':captures['counts'],'cost_usd_reported':sum(reported),'retrievals':len(rows),
          'known_support':[{'qid':r['question_id'],'reading':r['reading_id'],'cost':r['known_support']['readers']['intersection']['known_complete_acquisition_cost'],
          'covered':r['known_support']['readers']['intersection']['all_components_selected'],'unjudged':len(r['known_support']['unjudged_selected_chunk_ids'])}
          for r in rows if r['known_support']]}))

if __name__=='__main__':main()

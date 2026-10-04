"""Verify frozen source readings, then measure known support in saved contexts."""
import gzip
import json
from pathlib import Path

from facet_sentiment_content_packet import ROOT, BASE, OUT, read, write, sha

def main():
    result_path=OUT/'content_join.json'
    if result_path.exists(): raise RuntimeError('Existing content join; inspect rather than overwrite')
    manifest=read(OUT/'private_manifest.json');packet=read(OUT/'reader_packet.json')
    assert sha(OUT/'reader_packet.json')==manifest['packet_sha256']
    assert all(sha(ROOT/p)==h for p,h in manifest['input_sha256'].items())
    texts={e['passage_id']:e['text'] for e in packet['passages']}
    aliases=manifest['aliases'];readers={};quote_count=0
    input_paths=[Path(__file__),OUT/'private_manifest.json',OUT/'reader_packet.json',OUT.parent/'CONTENT_PROTOCOL.md']
    for name in ('reader_a','reader_b'):
        path=OUT/(name+'.json');input_paths.append(path);data=read(path)
        assert data['question']==packet['question']
        by_id={e['passage_id']:e for e in data['entries']}
        assert len(by_id)==len(data['entries'])==len(texts) and set(by_id)==set(texts)
        for alias,e in by_id.items():
            assert e['scope'] in {'supported','other_system','uncertain'}
            assert set(e['components'])=={'offering','tailoring'}
            for component,v in e['components'].items():
                assert v['category'] in {'none','context','partial','direct'}
                assert v['claim_status'] in {'intended_or_proposed','implemented_or_reviewed','unclear','none'}
                assert isinstance(v['quotes'],list) and isinstance(v['reason'],str)
                if v['category'] in {'partial','direct'}: assert v['quotes']
                for quote in v['quotes']:
                    assert isinstance(quote,str) and quote and quote in texts[alias],(name,alias,component,quote)
                    quote_count+=1
        readers[name]=by_id
    runs=[]
    for run in manifest['runs']:
        path=ROOT/run['file'];input_paths.append(path)
        rec=json.loads(gzip.decompress(path.read_bytes()))['recruitment']
        costs={cid:f['cumulative_source_characters'] for f in rec['frontiers'] for cid in f['chunk_ids']}
        chosen=set(run['selected_chunk_ids']);crossing=set(run['crossing_chunk_ids'])
        assert chosen==set(rec['selected_chunk_ids'])
        analysis={}
        for reader,entries in readers.items():
            components={}
            for component in ('offering','tailoring'):
                eligible={cid for cid,alias in aliases.items() if entries[alias]['scope']=='supported'
                          and entries[alias]['components'][component]['category']=='direct'}
                finite={cid:costs[cid] for cid in eligible if cid in costs}
                minimum=min(finite.values()) if finite else None
                components[component]={'direct_selected_aliases':sorted(aliases[cid] for cid in chosen & eligible),
                    'direct_crossing_aliases':sorted(aliases[cid] for cid in crossing & eligible),
                    'minimum_known_support_source_characters':minimum,
                    'earliest_witness_aliases':sorted(aliases[cid] for cid,cost in finite.items() if cost==minimum),
                    'selected_partial_aliases':sorted(aliases[cid] for cid in chosen if entries[aliases[cid]]['scope']=='supported'
                          and entries[aliases[cid]]['components'][component]['category']=='partial')}
            minima=[v['minimum_known_support_source_characters'] for v in components.values()]
            analysis[reader]={'components':components,'both_components_direct_at_budget':all(v['direct_selected_aliases'] for v in components.values()),
                'minimum_known_both_components_source_characters':max(minima) if all(x is not None for x in minima) else None,
                'selected_other_system_aliases':sorted(aliases[cid] for cid in chosen if entries[aliases[cid]]['scope']=='other_system'),
                'selected_uncertain_system_aliases':sorted(aliases[cid] for cid in chosen if entries[aliases[cid]]['scope']=='uncertain')}
        runs.append({'reading_id':run['reading_id'],'mode':run['mode'],'selected_passages':len(chosen),'readers':analysis})
    disagreements=[]
    for alias in texts:
        a,b=readers['reader_a'][alias],readers['reader_b'][alias]
        changes={}
        if a['scope']!=b['scope']:changes['scope']=[a['scope'],b['scope']]
        for component in ('offering','tailoring'):
            if a['components'][component]['category']!=b['components'][component]['category']:
                changes[component]=[a['components'][component]['category'],b['components'][component]['category']]
        if changes:disagreements.append({'passage_id':alias,'differences':changes})
    control=aliases[manifest['control_chunk_id']]
    write(result_path,{'input_sha256':{str(p.relative_to(ROOT)):sha(p) for p in input_paths},'runs':runs,
        'validated_quote_occurrences':quote_count,'validated_passages_per_reader':len(texts),
        'disagreements':disagreements,'control_alias':control,
        'control_assessments':{r:entries[control] for r,entries in readers.items()},
        'limits':'Model judgments over a finite source pool, not human gold or exhaustive recall. Acquiring a designated document is separate from selected content supporting the information need.'})
    print(json.dumps({'quotes':quote_count,'passages_per_reader':len(texts),'disagreements':len(disagreements),
        'outcomes':[{'reading_id':r['reading_id'],'mode':r['mode'],
            'readers':{k:{'both':v['both_components_direct_at_budget'],'cost':v['minimum_known_both_components_source_characters']} for k,v in r['readers'].items()}} for r in runs]}),flush=True)

if __name__=='__main__':main()

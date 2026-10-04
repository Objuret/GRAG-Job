"""Diagnose existing orders at equal serialized cost; never call a retriever/model."""
from pathlib import Path
import json
import sys
import facet_gold_trace as T


def cut(order, units):
    used=0; credit=set(); kept=[]
    for cid in order:
        size=units[cid]['serialized_chars']
        if used+size>72000:
            return credit,kept,{'budget':72000,'chars':72000,'kept':len(kept),
                              'boundary':{'id':cid,'chars_kept':72000-used,'chars_full':size},'exhausted':False}
        used+=size; kept.append(cid); credit.update(units[cid]['artifact_ids'])
        if used==72000:
            return credit,kept,{'budget':72000,'chars':72000,'kept':len(kept),'boundary':None,'exhausted':False}
    return credit,kept,{'budget':72000,'chars':used,'kept':len(kept),'boundary':None,'exhausted':True}


def pack_known_gold(gold,index,units):
    """A feasible diagnostic witness, not an optimal bound or retrieval policy."""
    candidates=set().union(*(set(index['artifacts'][aid]) for aid in gold))
    covered=set(); used=0; selected=[]
    while True:
        available=[]
        for cid in candidates:
            cost=units[cid]['serialized_chars']; gain=len((set(units[cid]['artifact_ids'])&gold)-covered)
            if gain and cost and used+cost<=72000:
                available.append((-gain/cost,-gain,cost,cid))
        if not available:break
        _,_,cost,cid=min(available)
        selected.append(cid); used+=cost; covered.update(set(units[cid]['artifact_ids'])&gold); candidates.remove(cid)
    assert used<=72000
    return {'covered_gold_ids':len(covered),'serialized_chars':used,'chunks':selected,
            'recall_id':len(covered)/len(gold)}


def main(folder):
    out=folder/'bottleneck_diagnosis/stage_budget.json'
    if out.exists():raise ValueError('Preserve diagnosis')
    index=T.read(T.OUT/'gold_source_index.json'); units=T.read(T.OUT/'chunk_delivery_index.json')
    cases=[]
    for saved in T.rows(folder/'arm_outputs.jsonl'):
        m=saved['meta']; qid=saved['id']; gold=set(index['questions'][qid]); rows=m['ranking']['rows']
        ranking=sorted(rows,key=lambda r:(-r['score'],r['chunk_id']))
        topic=sorted(rows,key=lambda r:(-(r['provenance']['topic'] or {}).get('contribution',0.),r['chunk_id']))
        nomination=m['recruitment']['nomination']['rows']
        orders={'joint_score':[r['chunk_id'] for r in ranking if r['score']>0],
                'topic_score':[r['chunk_id'] for r in topic if (r['provenance']['topic'] or {}).get('contribution',0.)>0],
                'with_scope':[r['chunk_id'] for r in nomination if r['depth'] is not None],
                'with_scope_and_recovery':m['full_recovered_order']}
        case={'question_id':qid,'gold_ids':len(gold),'stages':{}}
        for stage,order in orders.items():
            credit,kept,budget=cut(order,units)
            case['stages'][stage]={'gold_hits':len(credit&gold),'recall_id':len(credit&gold)/len(gold),
                                   'precision_id':len(credit&gold)/len(credit) if credit else None,
                                   'retrieved_ids':len(credit),'full_chunks':len(kept),
                                   'credited_ids':sorted(credit),'full_chunk_ids':kept}
            if stage=='with_scope_and_recovery':
                assert credit==set(saved['context_ids']) and budget==m['char_budget']
        a,b=(set(case['stages'][name]['full_chunk_ids']) for name in ('joint_score','topic_score'))
        case['score_only_full_chunk_jaccard']=len(a&b)/len(a|b) if a|b else 1.
        case['known_gold_feasible_packing']=pack_known_gold(gold,index,units)
        cases.append(case)
    n=len(cases); summary={}
    for stage in orders:
        summary[stage]={'questions':n,'mean_recall_id':sum(c['stages'][stage]['recall_id'] for c in cases)/n,
                        'total_gold_links':sum(c['stages'][stage]['gold_hits'] for c in cases)}
    summary['known_gold_feasible_packing']={'mean_recall_id':sum(c['known_gold_feasible_packing']['recall_id'] for c in cases)/n,
        'fully_covered_questions':sum(c['known_gold_feasible_packing']['recall_id']==1 for c in cases),
        'meaning':'Uses gold knowledge and ignores routing/recovery. Feasible storage witness only, not an achievable target or upper bound.'}
    summary['mean_score_only_full_chunk_jaccard']=sum(c['score_only_full_chunk_jaccard'] for c in cases)/n
    result={'summary':summary,'questions':cases,'actual_delivery_parity':n,'model_calls':0,'new_retrievals':0,
            'limits':'Exploratory assembly interventions on saved scores, not independent validation or answer-quality evidence. Partial units receive no source-ID credit.'}
    T.write(out,result); print(json.dumps(summary,indent=2))


if __name__=='__main__':main(Path(sys.argv[1]).resolve())

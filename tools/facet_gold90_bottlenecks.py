"""Attribute saved delivery decisions to score, scope, and recovery; no reranking."""
from collections import Counter
import json
from pathlib import Path
import sys
import numpy as np
import facet_gold_trace as T


def stats(values):
    return {'n':len(values), 'mean':float(np.mean(values)) if values else None,
            'median':float(np.median(values)) if values else None,
            'p10':float(np.quantile(values,.1)) if values else None,
            'p90':float(np.quantile(values,.9)) if values else None}


def main(folder):
    out=folder/'bottleneck_diagnosis'
    if (out/'results.json').exists():
        raise ValueError('Preserve completed diagnosis')
    index=T.read(T.OUT/'gold_source_index.json')
    units=T.read(T.OUT/'chunk_delivery_index.json')
    totals=Counter(); cases=[]; ratios=[]; samepaths=[]; score_correlations=[]
    gold_score_ranks=[]; gold_delivery_positions=[]
    for saved in T.rows(folder/'arm_outputs.jsonl'):
        m=saved['meta']; rows=m['ranking']['rows']; byid={r['chunk_id']:r for r in rows}
        order=m['full_recovered_order']; budget=m['char_budget']; kept=budget['kept']
        recovery={r['chunk_id']:r for r in m['recruitment']['rows']}
        nomination={r['chunk_id']:r for r in m['recruitment']['nomination']['rows']}
        delivered=order[:kept]; delivered_set=set(delivered)
        boundary=budget['boundary']; boundary_id=boundary['id'] if boundary else None
        qid=saved['id']; gold=set(index['questions'][qid]); credit=set(saved['context_ids'])
        score_order=sorted(byid,key=lambda c:(-byid[c]['score'],c))
        off=np.array([(byid[c]['provenance']['topic'] or {}).get('contribution',0.) for c in score_order])
        combined=np.array([byid[c]['score'] for c in score_order])
        score_correlations.append(float(np.corrcoef(off,combined)[0,1]))
        scope_advanced=[c for c in delivered if nomination[c]['stream_ranks'].get('verified_area',len(rows)+1)
                        < nomination[c]['stream_ranks'].get('all',len(rows)+1)]
        context_advanced=[c for c in delivered if recovery[c]['context_added']]
        context_chars=sum(units[c]['serialized_chars'] for c in context_advanced)
        scope_chars=sum(units[c]['serialized_chars'] for c in scope_advanced)
        tie_members=[]; higher_omitted=[]; withheld_gold=set()
        if boundary_id:
            depth=recovery[boundary_id]['depth']
            tie_members=[c for c in order if recovery[c]['depth']==depth]
            selected_here=delivered_set & set(tie_members)
            missing_here=set(tie_members)-delivered_set
            if selected_here:
                threshold=min(byid[c]['score'] for c in selected_here)
                higher_omitted=[c for c in missing_here if byid[c]['score']>threshold]
            for c in higher_omitted:
                withheld_gold.update(set(units[c]['artifact_ids']) & (gold-credit))
        paths=0; same=0; active_winners=set(); query_tags=len(m['interpreter']['tags'])
        for c in delivered:
            p=byid[c]['provenance']; top=p['topic']
            topic=(top or {}).get('contribution',0.)
            aux=sum((p[f] or {}).get('contribution',0.) for f in T.FACETS[1:])
            if topic>0: ratios.append(aux/topic)
            for w in p.values():
                if w: active_winners.add(w['query_tag_index'])
            if top:
                for f in T.FACETS[1:]:
                    w=p[f]
                    if w:
                        paths+=1
                        same+=all(w[k]==top[k] for k in ('query_tag_index','edge_id','seed_chunk_id','route_type'))
        samepaths.append(same/paths if paths else 0.)
        positions={c:i+1 for i,c in enumerate(order)}
        bestscore=[]; bestdelivery=[]; before_topk=0; displaced_topk=0
        for aid in gold:
            cs=index['artifacts'][aid]
            rank=min((byid[c]['rank'] for c in cs),default=len(rows)+1)
            pos=min((positions.get(c,len(rows)+1) for c in cs),default=len(rows)+1)
            bestscore.append(rank); bestdelivery.append(pos)
            before_topk+=rank<=kept
            displaced_topk+=rank<=kept and aid not in credit
        gold_score_ranks.extend(bestscore); gold_delivery_positions.extend(bestdelivery)
        case={'question_id':qid,'full_delivered_chunks':kept,'gold_ids':len(gold),'gold_hits':len(gold&credit),
              'scope_resolved':m['area']['area']['chunk_ids'] is not None,
              'scope_advanced_chunks':len(scope_advanced),'scope_advanced_full_chars':scope_chars,
              'recovery_advanced_chunks':len(context_advanced),'recovery_advanced_full_chars':context_chars,
              'boundary_group_chunks':len(tie_members),'boundary_omitted_higher_score_chunks':len(higher_omitted),
              'boundary_omitted_higher_score_gold_ids':len(withheld_gold),
              'same_topic_auxiliary_path_fraction':same/paths if paths else None,
              'query_tags':query_tags,'winning_query_tags_in_delivered_chunks':len(active_winners),
              'gold_in_score_top_k':before_topk,'gold_in_score_top_k_but_not_credited':displaced_topk,
              'k_for_rank_diagnostic':kept,
              'gold_best_score_rank':stats(bestscore),'gold_first_delivery_position':stats(bestdelivery)}
        cases.append(case)
        totals.update({'questions':1,'full_delivered_chunks':kept,'gold_links':len(gold),'gold_hits':len(gold&credit),
                       'scope_advanced_chunks':len(scope_advanced),'scope_advanced_full_chars':scope_chars,
                       'recovery_advanced_chunks':len(context_advanced),'recovery_advanced_full_chars':context_chars,
                       'delivered_chars':budget['chars'],'boundary_multi_chunk_groups':len(tie_members)>1,
                       'questions_omitting_higher_score_in_boundary_group':bool(higher_omitted),
                       'questions_with_withheld_gold_in_that_group':bool(withheld_gold),
                       'withheld_gold_in_that_group':len(withheld_gold),
                       'gold_in_score_top_k':before_topk,'gold_in_score_top_k_but_not_credited':displaced_topk})
    result={'counts':dict(totals),'auxiliary_to_topic_contribution_ratio_in_full_chunks':stats(ratios),
            'same_topic_auxiliary_path_fraction_per_question':stats(samepaths),
            'joint_topic_score_pearson_per_question':stats(score_correlations),
            'gold_best_score_rank':stats(gold_score_ranks),'gold_first_delivery_position':stats(gold_delivery_positions),
            'questions':cases,'model_calls':0,'new_retrievals':0,
            'limits':['Scope and recovery classifications overlap and are not causal independent shares.',
                      'Same-K is a rank diagnostic only; chunks differ in serialized size.',
                      'Gold absent from citation sets is not evidence of semantic irrelevance.',
                      'Boundary higher-score omissions establish arbitrary tie priority, not measured benefit from reordering.']}
    T.write(out/'results.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='questions'},indent=2))


if __name__=='__main__':main(Path(sys.argv[1]).resolve())

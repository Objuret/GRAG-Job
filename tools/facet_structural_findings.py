"""Matched structural effects including explicit custom ordering dimensions."""
import argparse
from collections import defaultdict
from itertools import combinations
import json
from pathlib import Path


def dimensions(program):
    result = {**program['factors'], 'graph_route':program.get('graph_route','product_channel'),
              'scope_input':program.get('scope_input_signature','frozen')}
    ordering = program.get('ordering', {})
    # The canonical reference's implicit ordering is explicit here.
    result.update({'reduction':'after_graph', 'description_gate':'each_step', 'rounds':1, 'feedback':'latest'})
    result.update({k:v for k,v in ordering.items() if k != 'reference'})
    feedback=program.get('recruitment_feedback',{})
    result['early_recruitment_mode']=feedback.get('mode','off')
    result['early_recruitment_placement']=feedback.get('placement','none')
    result['tie_break']=program.get('tie_break','id')
    for key in ('evidence','streams','sponsors'):
        result['tag_frontier_'+key]=program.get('tag_frontier',{}).get(key,'off')
    for key in ('streams','sponsors','weighting','arrival'):
        result['tag_admission_'+key]=program.get('tag_frontier_followup',{}).get(key,'off')
    for key in ('route','direction','placement','aggregation'):
        result['directed_'+key]=program.get('directed_choices',{}).get(key,'off')
    for key in ('method','sponsors'):
        result['query_priority_'+key]=program.get('query_priority',{}).get(key,'off')
    result['record_assembly']=program.get('record_assembly',{}).get('mode','unspecified')
    if 'record_assembly' in program:
        # The declared record policy includes whether late recovery is present;
        # counting its compiled on/off flag again would hide matched mode pairs.
        result['recovery']='explicit_record_policy'
    return result


def summarize(programs, cases):
    programs = {p['id']:p for p in programs}
    rows = {pid:[] for pid in programs}
    for cid, held in cases.items():
        if len(held) != len(programs) or {r['program_id'] for r in held} != set(programs):
            raise ValueError('Incomplete checkpoint: '+cid)
        for r in held:
            rows[r['program_id']].append(r)
    if not cases:
        raise ValueError('No completed cases')
    dims = {pid:dimensions(p) for pid,p in programs.items()}
    keys = sorted(next(iter(dims.values())))
    if any(sorted(d) != keys for d in dims.values()):
        raise ValueError('Unaligned construction dimensions')
    buckets = defaultdict(list)
    for pid,d in dims.items():
        for omitted in keys:
            context = tuple((k,d[k]) for k in keys if k != omitted)
            buckets[omitted,context].append(pid)
    effects = []
    for (factor,context), ids in buckets.items():
        for a,b in combinations(sorted(ids, key=lambda pid:str(dims[pid][factor])),2):
            if dims[a][factor] == dims[b][factor]:
                continue
            left,right = rows[a],rows[b]
            deltas = [y['hits']-x['hits'] for x,y in zip(left,right)]
            effects.append(dict(factor=factor, left=a, right=b,
                left_value=dims[a][factor], right_value=dims[b][factor], context=dict(context),
                gold_hits_delta=sum(deltas),
                macro_recall_delta=sum(y['recall_id']-x['recall_id'] for x,y in zip(left,right))/len(cases),
                wins=sum(d>0 for d in deltas), losses=sum(d<0 for d in deltas), ties=sum(d==0 for d in deltas),
                order_changed_cases=sum(x['order_sha256']!=y['order_sha256'] for x,y in zip(left,right))))
    conditional = defaultdict(list)
    for effect in effects:
        conditional[effect['factor'],effect['left_value'],effect['right_value']].append(effect)
    reversals = []
    interactions = []
    for (factor,a,b), held in conditional.items():
        low = min(held,key=lambda e:e['gold_hits_delta'])
        high = max(held,key=lambda e:e['gold_hits_delta'])
        if low['gold_hits_delta'] < 0 < high['gold_hits_delta']:
            reversals.append(dict(factor=factor, left_value=a, right_value=b,
                                  negative_context=low, positive_context=high))
        for first,second in combinations(held,2):
            changed = [k for k in first['context'] if first['context'][k] != second['context'][k]]
            if len(changed) == 1 and first['gold_hits_delta'] * second['gold_hits_delta'] < 0:
                modifier = changed[0]
                if factor < modifier:  # One record per complete four-corner comparison.
                    interactions.append(dict(factor=factor, modifier=modifier,
                        first_context=first, second_context=second,
                        difference_in_hit_deltas=second['gold_hits_delta']-first['gold_hits_delta']))
    leaders = sorted([dict(program_id=pid, dimensions=dims[pid],
                        total_gold_hits=sum(r['hits'] for r in held),
                        macro_recall=sum(r['recall_id'] for r in held)/len(held))
                      for pid,held in rows.items()],
                     key=lambda r:(-r['total_gold_hits'],-r['macro_recall']))
    signatures = {tuple(r['order_sha256'] for r in held) for held in rows.values()}
    return dict(completed_cases=len(cases), distinct_order_signatures=len(signatures),
                leaders=leaders[:20], matched_effects=effects, conditional_sign_reversals=reversals,
                matched_four_corner_reversals=sorted(interactions,key=lambda x:-abs(x['difference_in_hit_deltas'])),
                interpretation='Gold-informed development diagnostics. Sign reversals demonstrate dependence on the stated context, not a general causal or held-out performance claim.')


def analyze(out):
    read = lambda p:json.loads(p.read_text(encoding='utf-8'))
    plan = read(out/'plan.json')
    cases = {cid:read(out/'cases'/(cid+'.json')) for cid in plan['case_ids']
             if (out/'cases'/(cid+'.json')).exists()}
    result = summarize(plan['programs'],cases)
    result['expected_cases'] = len(plan['case_ids'])
    result['population_complete'] = len(cases) == len(plan['case_ids'])
    result['smoke_only'] = plan.get('smoke_only',False)
    name = 'structural-findings.json' if result['population_complete'] else 'structural-checkpoint-findings.json'
    temp = out/(name+'.tmp')
    temp.write_text(json.dumps(result,indent=2),encoding='utf-8')
    temp.replace(out/name)
    return {k:result[k] for k in ['completed_cases','expected_cases','population_complete','smoke_only','distinct_order_signatures']}


if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    print(json.dumps(analyze(ap.parse_args().out)))

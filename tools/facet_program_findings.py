"""Measure effective construction changes, not just the number of settings.

Can inspect checkpoints, but marks their population explicitly. Oracle results
are finite-catalog diagnostics and never a configuration selection policy.
"""
from collections import defaultdict
from pathlib import Path
import argparse
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def analyze(out):
    plan=read(out/'plan.json');programs={p['id']:p for p in plan['programs']}
    cases={cid:read(out/'cases'/(cid+'.json')) for cid in plan['case_ids'] if (out/'cases'/(cid+'.json')).exists()}
    if not cases:raise ValueError('No completed cases')
    rows={pid:[] for pid in programs};diversity=[]
    for cid,held in cases.items():
        if len(held)!=len(programs) or {r['program_id'] for r in held}!=set(programs):raise ValueError('Incomplete case')
        for r in held:rows[r['program_id']].append(r)
        diversity.append({'case_id':cid,'distinct_full_orders':len({r['order_sha256'] for r in held}),
            'distinct_delivered_ordered_prefixes':len({tuple(r['full_chunk_ids']) for r in held}),
            'distinct_delivered_sets':len({tuple(sorted(r['full_chunk_ids'])) for r in held}),
            'distinct_gold_hit_counts':len({r['hits'] for r in held})})
    groups=defaultdict(list);summaries=[]
    for pid,held in rows.items():
        signature=hashlib.sha256(''.join(r['order_sha256'] for r in held).encode()).hexdigest()
        groups[signature].append(pid)
        summaries.append({'program_id':pid,'factors':programs[pid]['factors'],
            'graph_route':programs[pid].get('graph_route','product_channel'),
            'total_gold_hits':sum(r['hits'] for r in held),
            'macro_recall':sum(r['recall_id'] for r in held)/len(held),'order_signature':signature})
    summaries.sort(key=lambda s:(-s['total_gold_hits'],-s['macro_recall'],s['program_id']))
    by_id={s['program_id']:s for s in summaries}
    def factors(pid):return {**programs[pid]['factors'],'graph_route':programs[pid].get('graph_route','product_channel')}
    # Every matched one-factor contrast present, including nonreference contexts.
    contrasts=[];buckets=defaultdict(list)
    keys=list(factors(next(iter(programs))))
    for pid in programs:
        f=factors(pid)
        for omitted in keys:
            buckets[(omitted,tuple((k,f[k]) for k in keys if k!=omitted))].append(pid)
    for (factor,context),ids in buckets.items():
        for i,a in enumerate(ids):
            for b in ids[i+1:]:
                ar,br=rows[a],rows[b]
                contrasts.append({'factor':factor,'left':a,'right':b,
                    'left_value':factors(a)[factor],'right_value':factors(b)[factor],
                    'gold_hits_delta':by_id[b]['total_gold_hits']-by_id[a]['total_gold_hits'],
                    'macro_recall_delta':by_id[b]['macro_recall']-by_id[a]['macro_recall'],
                    'order_changed_cases':sum(x['order_sha256']!=y['order_sha256'] for x,y in zip(ar,br)),
                    'delivered_set_changed_cases':sum(set(x['full_chunk_ids'])!=set(y['full_chunk_ids']) for x,y in zip(ar,br)),
                    'wins':sum(y['hits']>x['hits'] for x,y in zip(ar,br)),
                    'losses':sum(y['hits']<x['hits'] for x,y in zip(ar,br))})
    # Oracle only chooses from the tested catalog. It does not pack arbitrary
    # gold chunks or claim an attainable or universal retrieval upper bound.
    oracle=[max(held,key=lambda r:(r['hits'],r['recall_id'],r['program_id'])) for held in cases.values()]
    result={'completed_cases':len(cases),'expected_cases':len(plan['case_ids']),
        'population_complete':len(cases)==len(plan['case_ids']),'declared_programs':len(programs),
        'distinct_population_order_signatures':len(groups),'case_diversity':diversity,
        'equivalent_on_observed_cases':[ids for ids in groups.values() if len(ids)>1],
        'fixed_rule_leaders_by_hits':summaries[:20],
        'fixed_rule_leaders_by_macro':sorted(summaries,key=lambda s:(-s['macro_recall'],-s['total_gold_hits'],s['program_id']))[:20],
        'matched_contrasts':sorted(contrasts,key=lambda c:-abs(c['gold_hits_delta'])),
        'finite_catalog_oracle':{'total_gold_hits':sum(r['hits'] for r in oracle),
            'macro_recall':sum(r['recall_id'] for r in oracle)/len(oracle),
            'usable_without_gold':False,'meaning':'Per-case gold-selected diagnostic over this catalog only; not an achievable policy or universal upper bound.'}}
    dest=out/('construction-findings.json' if result['population_complete'] else 'checkpoint-findings.json')
    temporary=dest.with_suffix('.tmp');temporary.write_text(json.dumps(result,indent=2),encoding='utf-8');temporary.replace(dest)
    return {k:result[k] for k in ('completed_cases','expected_cases','population_complete','declared_programs','distinct_population_order_signatures')}


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True)
    print(json.dumps(analyze(ap.parse_args().out)))

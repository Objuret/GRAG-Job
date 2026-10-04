import json
from facet_program_findings import analyze
from facet_joint_search import choose_seeds


def test_effective_orders_and_oracle_are_distinct_from_fixed_rule_results(tmp_path):
    (tmp_path/'cases').mkdir()
    plan={'case_ids':['a','b'],'programs':[{'id':p,'factors':{'recruitment':'joint','scope':'saved','choice':p}} for p in ['x','y','z']]}
    (tmp_path/'plan.json').write_text(json.dumps(plan))
    for cid,hits in [('a',[2,2,0]),('b',[0,0,2])]:
        rows=[{'program_id':p,'hits':h,'recall_id':h/2,'order_sha256':cid+('xy' if p!='z' else 'z'),
               'full_chunk_ids':[cid+str(h)]} for p,h in zip(['x','y','z'],hits)]
        (tmp_path/'cases'/(cid+'.json')).write_text(json.dumps(rows))
    result=analyze(tmp_path)
    assert result['distinct_population_order_signatures']==2
    report=json.loads((tmp_path/'construction-findings.json').read_text())
    assert report['fixed_rule_leaders_by_hits'][0]['total_gold_hits']==2
    assert report['finite_catalog_oracle']['total_gold_hits']==4
    assert report['finite_catalog_oracle']['usable_without_gold'] is False


def seed(key,hits,recall,recruitment='joint',signature=None,size=2):
    return {'candidate_key':key,'hits':hits,'recall':recall,'order_signature':signature or key,
            'program':{'nodes':[{}]*size},'factors':{'recruitment':recruitment,'scope':'saved'}}


def test_pareto_seeds_preserve_mechanism_families_and_two_objectives():
    candidates=[seed('a',10,.4),seed('b',8,.6),seed('c',8,.3),
                seed('d',2,.1,recruitment='facets'),seed('alias',10,.4,signature='a',size=3)]
    assert {c['candidate_key'] for c in choose_seeds(candidates)}=={'a','b','d'}

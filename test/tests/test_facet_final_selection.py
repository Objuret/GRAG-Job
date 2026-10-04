import json
import pytest
import facet_final_selection as selection


def test_fixed_objectives_remain_distinct_and_partial_parent_is_rejected(tmp_path,monkeypatch):
    monkeypatch.setattr(selection.L,'ROOT',tmp_path)
    monkeypatch.setattr(selection,'verify',lambda p:{'population_complete':True})
    parents=[]
    for name,hits,recall in [('a',10,.3),('b',9,.4)]:
        p=tmp_path/name;p.mkdir();parents.append(p)
        for file,value in [('plan.json',{'case_ids':['case_001'],'programs':[{'id':name,'nodes':[{}]}]}),
                           ('status.json',{'status':'complete'}),('independent-verification.json',{}),
                           ('report.json',[{'program_id':name,'cases':1,'total_gold_hits':hits,'recall_id':recall}])]:
            (p/file).write_text(json.dumps(value))
    result=selection.select(parents,tmp_path/'selected')
    assert result['best-total-hits']['program_id']=='a'
    assert result['best-macro-recall']['program_id']=='b'
    (parents[1]/'status.json').write_text(json.dumps({'status':'running'}))
    with pytest.raises(ValueError,match='Completed population'):
        selection.select(parents,tmp_path/'rejected')

import json
import numpy as np
import facet_scope_program_lab as scope


def test_scope_override_is_query_grounded_and_does_not_mutate_saved_case(tmp_path,monkeypatch):
    monkeypatch.setattr(scope,'SCOPE_INPUTS',tmp_path)
    (tmp_path/'case_001.json').write_text(json.dumps({'landings':[{'node_bindings':[
        {'label':'Product','node_id':'p','routes':{'product':['a']}}]}]}))
    class Base:
        ids=['a','b']
        def execute(self,case,program):return case
    class Lab(scope.ScopeOverride,Base):pass
    original={'meta':{'case_id':'case_001'},'area':np.array([False,True])}
    program={'factors':{'scope':'saved'},'scope_policy':{}}
    changed=Lab().execute(original,program)
    assert changed['area'].tolist()==[True,False]
    assert original['area'].tolist()==[False,True]
    assert Lab().execute(original,{}) is original

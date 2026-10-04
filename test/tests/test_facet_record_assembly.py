import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
from artefact.facet_record_assembly import component_max,contiguous_order
from facet_record_assembly_programs import transform

def test_component_transport_preserves_streams_and_can_rescue_missing_evidence():
    values=np.array([[[3.,0.,5.],[0.,7.,2.]],[[1.,0.,0.],[4.,0.,9.]]])
    actual=component_max(values,np.array([0,0,2]))
    assert actual.tolist()==[[[3.,3.,5.],[7.,7.,2.]],[[1.,1.,0.],[4.,4.,9.]]]
    assert np.array_equal(component_max(actual,np.array([0,0,2])),actual)
    assert values[0,0,1]==0
    with pytest.raises(ValueError):component_max(values,np.array([0,0,3]))

def test_contiguous_assembly_changes_order_without_changing_access():
    # Native a,b at depth1; c is context sibling of a. Existing late recovery
    # puts native b before c; contiguous assembly retains a+c as a record.
    order=np.array([0,1,2,3]);original=np.array([1,1,4,2]);components=np.array([0,1,0,3]);ids=np.arange(4)
    actual=contiguous_order(order,original,components,ids)
    assert actual.tolist()==[0,2,1,3]
    assert set(actual)==set(order)
    # Unsupported/filtered members cannot be introduced by assembly alone.
    assert contiguous_order(np.array([0,1,3]),original,components,ids).tolist()==[0,1,3]

def test_transport_placement_and_late_controls_explicit():
    seed={'nodes':[{'id':'seed','op':'source'}, {'id':'walk_1','op':'propagate','inputs':['seed']},
       {'id':'nomination','op':'nominate','inputs':['walk_1']},{'id':'recovery','op':'recover','inputs':['nomination']}],
       'output':'recovery','factors':{'recovery':'on'}}
    early=transform(seed,'before_nomination')
    assert early['output']=='nomination'
    assert not any(n['op']=='recover' for n in early['nodes'])
    assert next(n for n in early['nodes'] if n['id']=='nomination')['inputs']==['record_component_evidence']
    walk=transform(seed,'before_walk')
    assert walk['output']=='recovery'
    assert next(n for n in walk['nodes'] if n['id']=='walk_1')['inputs']==['record_component_evidence']
    assert transform(seed,'late')['nodes']==seed['nodes']
    assert transform(seed,'contiguous')['nodes'][-1]['op']=='record_component_assembly'

def test_record_transport_before_graph_can_enable_otherwise_unreachable_neighbor():
    from artefact.facet_graph_input import GraphInput
    from artefact.facet_record_assembly_engine import run_program
    graph=GraphInput(('a','b','c'),np.array([0]),np.array([0]),np.ones((1,5)),{},((1,2),),())
    matrices={'query_tag_cosines':np.ones((1,1)),'query_chunk_cosines':np.array([[1.,0.,0.]]),'query_description_cosines':np.zeros(3)}
    source={'id':'seed','op':'source','params':{'name':'query_description'}}
    transport={'id':'record','op':'record_component_max','inputs':['seed']}
    walk={'id':'walk','op':'propagate','inputs':['record'],'params':{'relation':'adjacency','decay':.5}}
    nom={'id':'nom','op':'nominate','inputs':['walk'],'params':{'method':'best_rank'}}
    early={'nodes':[source,transport,walk,nom],'output':'nom'}
    late={'nodes':[source,{**walk,'inputs':['seed']},{**transport,'inputs':['walk']},{**nom,'inputs':['record']}],'output':'nom'}
    args=(graph,matrices,np.ones((1,5)),None,np.array([0,0,2]),np.arange(3))
    assert run_program(early,*args)['order'].tolist()==[2]
    assert run_program(late,*args)['order'].tolist()==[]

def test_assembly_cut_audit_detects_component_tie_inside_bundle():
    from facet_record_assembly_inspection import ordering_audit
    # Cut inside component0; adjacent native depths 1 and4 differ, but tied
    # component1 could move its entire bundle before component0 by head ID.
    result=ordering_audit([0,2,1,3],np.array([1,1,4,2]),np.array([0,1,0,3]),np.arange(4),1)
    assert result['id_sensitive_serving_cut']
    assert result['crossing_id_ties'][0]['kind']=='component_head_id'
    assert result['effective_keys'][1]['key']==[1,0,4,2]
    complete=ordering_audit([0,2,1,3],np.array([1,1,4,2]),np.array([0,1,0,3]),np.arange(4),4)
    assert not complete['id_sensitive_serving_cut']

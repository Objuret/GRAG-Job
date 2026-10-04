import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
from facet_directed_values import project,propagate

def test_direction_cycles_duplicates_isolation_and_sponsors():
    ids=('a','b','c','isolated')
    payload={'eligible_chunk_ids':ids,'employees':{e:{'employee_channel':[c],'employee_product':[c]} for e,c in [('A','a'),('B','b'),('C','c'),('D','a')]},'manages_edges':[('A','B'),('A','B'),('D','B'),('C','B'),('B','A')]}
    routes=project(ids,payload);values=np.array([[[2.,0.,4.,9.]]])
    f=propagate(values,routes,'employee_channel:forward',decay=1)
    assert f.tolist()==[[[0.,4.,0.,0.]]]
    assert propagate(values,routes,'employee_channel:forward','sum',1).tolist()==[[[0.,6.,0.,0.]]]
    assert propagate(values,routes,'employee_channel:forward','mean',1).tolist()==[[[0.,3.,0.,0.]]]
    b=np.array([[[0.,3.,0.,0.]]])
    assert propagate(b,routes,'employee_channel:reverse',decay=1).tolist()==[[[3.,0.,3.,0.]]]
    assert propagate(b,routes,'employee_channel:symmetric',decay=1).tolist()==[[[3.,0.,3.,0.]]]
    assert propagate(f,routes,'employee_channel:forward',decay=1).tolist()==[[[4.,0.,0.,0.]]]
    assert all(not m.diagonal().any() for m in routes.matrices.values())

def test_destination_gate_preserves_facet_and_query_streams():
    ids=('a','b')
    p={'eligible_chunk_ids':ids,'employees':{e:{'employee_channel':[c],'employee_product':[c]} for e,c in [('A','a'),('B','b')]},'manages_edges':[('A','B')]}
    routes=project(ids,p)
    values=np.array([[[2.,0.],[4.,0.]],[[6.,0.],[8.,0.]]])
    gate=np.array([[1.,.5],[1.,.25]])
    out=propagate(values,routes,'employee_channel:forward',decay=.5,destination=gate)
    assert out.shape==values.shape
    assert np.array_equal(out,np.array([[[0.,.5],[0.,.5]],[[0.,1.5],[0.,1.]]]))
    assert all(not a.flags.writeable for m in routes.matrices.values() for a in (m.data,m.indices,m.indptr))

def test_placement_is_in_graph_flow_not_final_sort():
    from facet_directed_lab import variant
    seed={'nodes':[{'id':'seed','op':'source'}, {'id':'gate','op':'source'},
      {'id':'walk_1','op':'propagate','inputs':['seed','gate'],'params':{}},
      {'id':'walk_2','op':'propagate','inputs':['walk_1','gate'],'params':{}},
      {'id':'nomination','op':'nominate','inputs':['walk_2'],'params':{'method':'best_rank'}}], 'output':'nomination'}
    replacement=variant(seed,'employee_channel','forward','replace')
    assert [n['op'] for n in replacement['nodes']][2:4]==['directed_propagate']*2
    assert replacement['nodes'][-1]==seed['nodes'][-1]
    before=variant(seed,'employee_channel','forward','before')
    assert next(n for n in before['nodes'] if n['id']=='walk_1')['inputs']==['directed_entry','gate']
    parallel=variant(seed,'employee_channel','forward','parallel')
    assert next(n for n in parallel['nodes'] if n['id']=='directed_join')['inputs']==['seed','directed_entry']
    assert seed['nodes'][2]['op']=='propagate'

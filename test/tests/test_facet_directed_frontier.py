import numpy as np
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
from artefact.facet_graph_input import GraphInput
from artefact.facet_tag_frontier import inject
from artefact.facet_directed_frontier_engine import run_program
from facet_directed_values import project
from facet_program_catalog import build

def fixture():
    graph=GraphInput(('a','b','c'),np.array([0,1,0]),np.array([0,0,1]),np.ones((3,5)),{},(),())
    matrices={'query_tag_cosines':np.array([[.8,.4]]),'query_chunk_cosines':np.ones((1,3)),'query_description_cosines':np.ones(3)}
    return graph,matrices,np.ones((1,5))

def test_gate_values_invalidate_cache_binding():
    graph,matrices,weights=fixture();p=inject(build({}));cache={}
    args=(graph,matrices,weights,None,np.arange(3),np.arange(3))
    zero=run_program(p,*args,cache=cache,frontier_gate=np.zeros((5,1,3)))
    one=run_program(p,*args,cache=cache,frontier_gate=np.ones((5,1,3)))
    assert not zero['states']['tag_frontier_edge_evidence'].values.any()
    assert one['states']['tag_frontier_edge_evidence'].values.any()

def test_gate_precedes_chunk_reduction_and_directed_transit():
    graph,matrices,weights=fixture()
    payload={'eligible_chunk_ids':graph.chunk_ids,'employees':{'A':{'employee_channel':['a'],'employee_product':['a']},'B':{'employee_channel':['c'],'employee_product':['c']}},'manages_edges':[('A','B')]}
    routes=project(graph.chunk_ids,payload)
    p={'nodes':[{'id':'gate','op':'source','params':{'name':'tag_frontier_gate'}},
       {'id':'chunks','op':'edges_to_chunks','inputs':['gate'],'params':{'method':'maximum'}},
       {'id':'road','op':'directed_propagate','inputs':['chunks'],'params':{'route':'employee_channel','direction':'forward','decay':1}},
       {'id':'nom','op':'nominate','inputs':['road'],'params':{'method':'best_rank'}}],'output':'nom'}
    gate=np.zeros((5,1,3));gate[:,:,0]=1
    r=run_program(p,graph,matrices,weights,None,np.arange(3),np.arange(3),frontier_gate=gate,directed_routes=routes)
    assert r['order'].tolist()==[2]
    assert r['stages']['road']['inputs']==['chunks']
    assert r['states']['road'].values[:,:,2].min()==1

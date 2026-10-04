import copy
from types import SimpleNamespace
import numpy as np
import pytest
from artefact.facet_construction_program import run_program
from artefact.facet_graph_input import GraphInput
from artefact.facet_construction_routes import independent_batches, reduce_edges
from artefact.facet_joint_candidate import freeze_reference
from artefact.facet_operator_matrix import score_families
from facet_program_catalog import build,catalog
from facet_retrieval_lab import schedule,DEFAULT


def fixture():
 p=SimpleNamespace(chunks=[{}, {}, {}, {}],edge_tag=np.array([0,1,0,1,0]),
   edge_chunk=np.array([0,0,1,2,3]),edge_facets=np.array([[.2]*5,[.4]*5,[.7]*5,[.9]*5,[.1]*5]),
   groups={'g':[(0,1,2)]},adjacency_pairs=[(0,1),(1,2)])
 p.reference=freeze_reference(p.edge_facets)
 m={'query_tag_cosines':np.array([[.9,.1],[.1,.9]]),
    'query_chunk_cosines':np.array([[.8,.7,0,.05],[.4,.5,.9,.02]]),
    'query_description_cosines':np.array([.7,.8,.9,.1])}
 graph=GraphInput(tuple('abcd'),p.edge_tag,p.edge_chunk,p.reference.transform(p.edge_facets),
   p.groups,p.adjacency_pairs,((0,1,2),))
 return graph,m,np.ones((2,5)),np.array([True,True,False,False]),np.arange(4),np.arange(4)


def test_reference_numerical_and_full_order_parity():
 p,m,u,area,components,ids=fixture()
 legacy=SimpleNamespace(chunks=[{}]*4,edge_tag=p.edge_tag,edge_chunk=p.edge_chunk,
   edge_facets=p.facet_readings,reference=SimpleNamespace(transform=lambda x:x),
   groups=p.groups,adjacency_pairs=p.adjacency_pairs)
 expected=next(v for k,v in score_families(legacy,m,u) if k==dict(match='product',topology='both',graph_join='union',facet='separate_facet_sum'))
 result=run_program(build({}),p,m,u,area,components,ids)
 assert np.allclose(result['states']['description_at_destination'].values.reshape(1,4),expected*m['query_description_cosines'],rtol=0,atol=1e-16)
 old=schedule(expected,m['query_description_cosines'],DEFAULT,area,components,ids)[0]
 assert np.array_equal(old,result['order'])


def test_every_declared_program_runs_without_gold():
 args=fixture();cache={}
 for program in catalog():
  result=run_program(program,*args,cache=cache)
  assert len(set(result['order']))==len(result['order'])
  assert np.all(result['order']<4)


def test_independent_batches_advance_past_shared_nominations():
 values=np.array([[9,8,7,0],[9,7,0,8]])
 depth,sponsors=independent_batches(values,np.arange(4))
 assert depth.tolist()==[1,2,3,2]
 assert sponsors[0]==[0,1]
 # All ties form a complete batch, rather than being cut at a made-up k.
 depth,_=independent_batches(np.array([[1,1,1,0],[0,0,1,1]]),np.arange(4))
 assert depth.tolist()==[1,1,1,1]


def test_edge_duplicate_control_and_conflicting_duplicate_rejection():
 values=np.array([[[.2,.4,.5]]]);targets=np.array([0,0,1]);tags=np.array([1,2,1])
 for mode in ['maximum','mean','sum']:
  expected=reduce_edges(values,targets,tags,mode,2)
  actual=reduce_edges(np.concatenate([values,values[:,:,:1]],axis=2),np.r_[targets,0],np.r_[tags,1],mode,2)
  assert np.array_equal(expected,actual)
 with pytest.raises(ValueError):reduce_edges(np.array([[[.2,.9]]]),np.array([0,0]),np.array([1,1]),'sum',1)


def test_reach_stops_on_cycles_and_does_not_reach_disconnected_chunk():
 args=fixture();program=build({'scope':'seed_union'})
 r=run_program(program,*args)
 assert r['states']['discovered_area'].values.tolist()==[True,True,True,False]
 assert r['stages']['reachable_regions']['expansion_rounds']<=4


def test_cache_matches_uncached_and_invalidates_for_changed_inputs():
 args=list(fixture());cache={};program=build({'path_support':'sum','recruitment':'facets'})
 a=run_program(program,*args,cache=cache);b=run_program(program,*args)
 assert np.array_equal(a['order'],b['order'])
 args[1]['query_description_cosines'][0]=0
 a=run_program(program,*args,cache=cache);b=run_program(program,*args)
 assert np.array_equal(a['order'],b['order'])


def test_missing_input_and_cycle_are_rejected():
 program=build({});program['nodes'][0]['inputs']=['nomination']
 with pytest.raises(ValueError):run_program(program,*fixture())


def test_rich_snapshot_rejected_before_any_field_is_read():
 class Forbidden:
  def __getattribute__(self,name):
   raise AssertionError('Read forbidden snapshot field: '+name)
 args=list(fixture());args[0]=Forbidden()
 with pytest.raises(TypeError,match='GraphInput'):run_program(build({}),*args)


def test_graph_input_does_not_retain_rich_records_or_mutable_arrays():
 graph=fixture()[0]
 for name in ('chunks','source_text','gold','resolver','relpath','reference','__dict__'):
  assert not hasattr(graph,name)
 with pytest.raises(ValueError):graph.edge_chunk.setflags(write=True)
 with pytest.raises(TypeError):graph.groups[0]=()
 with pytest.raises(TypeError):GraphInput(**{name:getattr(graph,name) for name in graph.__slots__},source_text='forbidden')


def test_product_traversal_has_real_membership_and_excludes_self():
 args=list(fixture());args[1]['query_description_cosines']=np.array([1.,0.,0.,0.])
 for method in ('maximum','mean','sum'):
  program={'nodes':[
   {'id':'q','op':'source','params':{'name':'whole_description'}},
   {'id':'p','op':'propagate','inputs':['q'],'params':{'relation':'product','aggregation':method,'decay':1.}},
   {'id':'n','op':'nominate','inputs':['p'],'params':{'method':'best_rank'}}], 'output':'n'}
  result=run_program(program,*args)
  assert set(result['order'])=={1,2}
  assert result['states']['p'].values.ravel().tolist()==[0.,.5 if method=='mean' else 1.,.5 if method=='mean' else 1.,0.]


def test_facet_combination_before_edges_cannot_borrow_different_winning_tags():
 graph=GraphInput(('c',),np.array([0,1]),np.array([0,0]),
   np.array([[.9,.1,0,0,0],[.1,.9,0,0,0]]),{},(),())
 matrices={'query_tag_cosines':np.ones((1,2)),'query_chunk_cosines':np.ones((1,1)),
   'query_description_cosines':np.ones(1)}
 def score(binding):
  result=run_program(build({'facet_binding':binding,'path':'direct','description':'off','recovery':'off'}),
    graph,matrices,np.ones((1,5)),None,np.array([0]),np.array([0]))
  return result['states']['joint_stream'].values.item()
 assert score('separate')==pytest.approx(1.125)
 assert score('same_path')==pytest.approx(.925)


def test_reversing_graph_route_order_reaches_different_chunk():
 graph=GraphInput(tuple('abcd'),np.array([0]),np.array([0]),np.ones((1,5)),
   {'shared':((1,2),)},((0,1),),())
 matrices={'query_tag_cosines':np.ones((1,1)),'query_chunk_cosines':np.ones((1,4)),
   'query_description_cosines':np.ones(4)}
 def run(path,scope_stage='after_paths'):
  return run_program(build({'path':path,'join':'graph_only','description':'off','recovery':'off',
    'scope_stage':scope_stage}),graph,matrices,np.ones((1,5)),np.array([False,True,True,True]),np.arange(4),np.arange(4))
 assert run('adjacency_then_group')['order'].tolist()==[2]
 assert run('group_then_adjacency')['order'].tolist()==[]
 # Gating the only seed before traversal prevents its offer; after-traversal
 # scheduling still allows that seed to reach the in-area destination.
 assert run('adjacency_then_group','before_paths')['order'].tolist()==[]


def test_nomination_union_conjunction_and_independent_rounds_differ():
 graph,m,u,area,components,ids=fixture()
 m['query_chunk_cosines']=np.array([[9.,8.,7.,0.],[9.,7.,0.,8.]])
 for method,expected in [('best_rank',[1,2,3,2]),('independent_batches',[1,2,3,2]),
                          ('all_streams',[1,3,5,5])]:
  program={'nodes':[{'id':'q','op':'source','params':{'name':'query_description'}},
    {'id':'n','op':'nominate','inputs':['q'],'params':{'method':method}}],'output':'n'}
  assert run_program(program,graph,m,u,area,components,ids)['final'].depth.tolist()==expected
 # A second stream recruits the first stream's next chunk in round one;
 # independent recruitment skips it in round two, unlike best-rank merging.
 m['query_chunk_cosines']=np.array([[9.,8.,7.,6.],[0.,9.,0.,0.]])
 depths=[]
 for method in ['best_rank','independent_batches']:
  program['nodes'][-1]['params']['method']=method
  depths.append(run_program(program,graph,m,u,area,components,ids)['final'].depth.tolist())
 assert depths==[[1,1,3,4],[1,1,2,3]]


def test_exclusive_join_removes_shared_support_instead_of_taking_minimum():
 graph,m,u,area,components,ids=fixture()
 m['query_chunk_cosines']=np.array([[1.,.5,0.,0.],[1.,.5,0.,0.]])
 m['query_description_cosines']=np.array([0.,.9,.8,0.])
 program={'nodes':[{'id':'a','op':'source','params':{'name':'query_description'}},
   {'id':'b','op':'source','params':{'name':'whole_description'}},
   {'id':'x','op':'exclusive','inputs':['a','b']},
   {'id':'n','op':'nominate','inputs':['x'],'params':{'method':'best_rank'}}],'output':'n'}
 result=run_program(program,graph,m,u,area,components,ids)
 assert result['states']['x'].values.tolist()==[[[1.,0.,.8,0.],[1.,0.,.8,0.]]]

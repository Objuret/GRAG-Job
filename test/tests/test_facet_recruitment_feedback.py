import numpy as np
from artefact.facet_recruitment_feedback import nomination_evidence
from artefact.facet_construction_program import Nomination
from artefact.facet_construction_routes import independent_batches
from artefact.facet_construction_fast import run_program as original
from artefact.facet_construction_feedback import run_program
from facet_program_catalog import catalog
from facet_ordering_programs import transform
from facet_recruitment_programs import recruit_before_walk
from test_facet_construction_program import fixture


def test_early_sponsors_vs_other_supporters_and_rank_priority():
    values=np.array([[[9.,8.,7.,0.]],[[9.,7.,0.,8.]]])
    depth,sponsors=independent_batches(values.reshape(2,4),np.arange(4))
    n=Nomination(depth,depth.copy(),sponsors)
    scores=nomination_evidence(n,values,'sponsor_scores')
    assert scores[:,0,1].tolist()==[8.,0.]
    ranks=nomination_evidence(n,values,'inverse_sponsors')
    assert ranks[:,0,1].tolist()==[.5,0.]
    all_support=nomination_evidence(n,values,'inverse_all')
    assert all_support[:,0,1].tolist()==[.5,.5]


def test_extension_preserves_existing_program_outputs():
    a_cache={};b_cache={};args=fixture()
    for p in catalog():
        a=original(p,*args,cache=a_cache);b=run_program(p,*args,cache=b_cache)
        assert np.array_equal(a['order'],b['order'])
        for key in a['states']:
            if hasattr(a['states'][key],'values'):
                assert np.array_equal(a['states'][key].values,b['states'][key].values)


def test_recruitment_precedes_walk_and_reaches_ranking():
    seed=transform(dict(path='groups',query='mean',recruitment='facets'),reduction='before_edges',rounds=2)
    for mode in ('sponsor_scores','inverse_sponsors','inverse_all'):
        for placement in ('graph_only','all_paths'):
            p=recruit_before_walk(seed,mode,placement,'independent_batches')
            result=run_program(p,*fixture())
            assert result['stages']['walk_1']['inputs'][0]=='recruited_evidence'
            assert result['stages']['recruited_evidence']['supported_chunks']>0
            assert len(result['order'])>0

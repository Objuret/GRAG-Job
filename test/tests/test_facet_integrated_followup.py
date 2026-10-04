import numpy as np
from facet_integrated_followup import compose
from facet_ordering_programs import transform
from artefact.facet_construction_fast import run_program
from test_facet_construction_program import fixture


def test_integration_preserves_seed_and_masks_before_early_reduction():
    seed={**transform(dict(path='groups',query='mean',admission='area_first'),reduction='before_graph',rounds=2),'id':'seed'}
    a=run_program(seed,*fixture());b=run_program(compose(seed,'product_channel'),*fixture())
    assert np.array_equal(a['order'],b['order'])
    assert np.array_equal(a['states']['graph'].values,b['states']['graph'].values)
    for recruitment in ('joint','facets'):
        program=compose(seed,'product_channel',stage='before_paths',admission='area_only',recruitment=recruitment)
        result=run_program(program,*fixture())
        assert result['states']['graph'].values.shape[1]==1
        assert set(result['order'])<=set(np.flatnonzero(fixture()[3]))
        assert np.all(result['states']['scope_before_paths'].values[...,~fixture()[3]]==0)

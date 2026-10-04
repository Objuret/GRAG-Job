import numpy as np
from facet_depth_followup import extend
from facet_ordering_programs import transform
from artefact.facet_construction_fast import run_program
from test_facet_construction_program import fixture


def test_depth_extension_reproduces_original_and_preserves_feedback():
    seed={**transform(dict(path='groups',query='mean'),rounds=4),'id':'seed'}
    for depth in (1,2,4):
        for feedback in ('latest','retain_seed'):
            expected=run_program(transform(seed['factors'],rounds=depth,feedback=feedback),*fixture())
            actual=run_program(extend(seed,depth,feedback),*fixture())
            assert np.array_equal(actual['order'],expected['order'])
            assert np.array_equal(actual['states']['graph'].values,expected['states']['graph'].values)
    for depth in (3,7,15,31,32):
        for feedback in ('latest','retain_seed'):
            program=extend(seed,depth,feedback)
            assert len(program['nodes'])<=100
            result=run_program(program,*fixture())
            assert np.isfinite(result['states']['graph'].values).all()

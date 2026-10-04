import numpy as np
import pytest
from artefact.facet_construction_fast import _first_distinct_rows, run_program as fast
from artefact.facet_construction_program import run_program, Signal
from facet_program_catalog import catalog
from test_facet_construction_program import fixture


@pytest.mark.parametrize('dtype',[np.float32,np.float64])
def test_duplicate_rows_preserve_first_occurrence_and_signed_zero(dtype):
    x=np.array([[1,0,3],[2,1,2],[1,-0.,3],[1,0,4],[2,1,2]],dtype=dtype)
    _,expected=np.unique(x,axis=0,return_index=True);expected.sort()
    assert np.array_equal(_first_distinct_rows(x),expected)
    rng=np.random.default_rng(20260923);x=rng.normal(size=(20,20000)).astype(dtype)
    x[10:15]=x[1:6]
    _,expected=np.unique(x,axis=0,return_index=True);expected.sort()
    assert np.array_equal(_first_distinct_rows(x),expected)


def test_every_program_has_exact_intermediate_values_and_orders():
    args=fixture();a_cache={};b_cache={}
    for p in catalog():
        a=run_program(p,*args,cache=a_cache);b=fast(p,*args,cache=b_cache)
        assert np.array_equal(a['order'],b['order'])
        assert a['stages']==b['stages']
        for name,x in a['states'].items():
            y=b['states'][name]
            if isinstance(x,Signal):assert np.array_equal(x.values,y.values)
            else:
                assert np.array_equal(x.depth,y.depth)
                assert np.array_equal(x.original,y.original)
                assert x.sponsors==y.sponsors

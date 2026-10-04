import itertools
import numpy as np
import pytest
from artefact.facet_partial_order import interval_order


def test_cycle_in_naive_fallback_is_avoided():
    # Baseline B>C>A; interval evidence A>B. Pairwise fallback would cycle.
    ids=['A','B','C'];lo=[2,0,.5];hi=[3,1,2.5];base=[1,3,2]
    assert interval_order(ids,lo,hi,base)==['C','A','B']


def test_input_permutation_and_dominated_addition_preserve_order():
    rows=[('A',2,3,1),('B',0,1,3),('C',.5,2.5,2)]
    expected=['C','A','B']
    for order in itertools.permutations(rows):
        cols=list(zip(*order))
        assert interval_order(*cols)==expected
    # Huge baseline cannot lift an unambiguously worse candidate over old ones.
    assert interval_order(*zip(*(rows+[('D',-2,-1,100)])))==expected+['D']


def test_random_orders_preserve_every_interval_constraint():
    rng=np.random.default_rng(92501)
    for _ in range(30):
        lo=rng.normal(size=20);hi=lo+rng.uniform(0,2,size=20)
        ids=[str(i) for i in range(20)]
        result=interval_order(ids,lo,hi,rng.normal(size=20));at={k:i for i,k in enumerate(result)}
        assert all(at[ids[i]]<at[ids[j]] for i in range(20) for j in range(20) if lo[i]>hi[j])


def test_no_constraints_uses_fixed_baseline_and_stable_ids():
    assert interval_order(['z','a','m'],[0,0,0],[1,1,1],[1,1,2])==['m','a','z']
    assert interval_order([],[],[],[])==[]


def test_invalid_measurements_are_rejected():
    with pytest.raises(ValueError):interval_order(['a'],[1],[0],[1])
    with pytest.raises(ValueError):interval_order(['a'],[0],[1],[np.nan])
    with pytest.raises(ValueError):interval_order(['a','a'],[0,0],[1,1],[1,1])

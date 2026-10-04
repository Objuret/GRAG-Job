"""Behavioral invariants for the experimental ordinal comparator."""
from pathlib import Path
import sys
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from facet_tradeoff_experiment import lex_direction

def test_unrelated_facet_cannot_break_an_otherwise_unresolved_comparison():
    assert lex_direction([1,0],[0,1000])==0
    assert lex_direction([0,0],[1,-1])==0
    assert lex_direction([1,.3,0],[0,-.1,1000])==-1

def test_equal_priority_disagreement_does_not_create_an_arbitrary_winner():
    assert lex_direction([1,1,.5],[1,-1,1])==0
    assert lex_direction([1,1,.5],[0,-1,1])==-1
    assert lex_direction([1,1,.5],[-1,-1,1])==-1

def test_orders_survive_scale_and_coordinate_permutation():
    q=np.array([.9,.4,.4,0]);d=np.array([0,1,1,-20])
    for order in ([0,1,2,3],[3,2,0,1],[2,1,3,0]):
        assert lex_direction(q[order]*.2,d[order]*23)==1

def test_invalid_relevance_is_not_a_sorting_key():
    for q,d in [([-1],[1]),([np.nan],[1]),([1],[np.inf]),([1],[1,2])]:
        with pytest.raises(ValueError):lex_direction(q,d)

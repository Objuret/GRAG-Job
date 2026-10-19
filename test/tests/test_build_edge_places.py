"""What `build_edge_places` premakes from the graph's edges."""
import numpy as np

from artefact import v4_walk as WK
from graph.build_edge_places import placed


def test_the_places_middle_and_spread_are_those_of_the_eligible_edges():
    rng = np.random.default_rng(4)
    endpoints = [('Alpha', 'c1'), ('beta', 'c1'), ('ALPHA', 'c2')] + [(f't{i}', f'c{i % 7}')
                                                                    for i in range(60)]
    values = rng.normal(size=(len(endpoints), 5))
    kept, pos, node = placed(endpoints, values, ['alpha', 'Gamma'])
    # a tag that is a product's name, case left aside, is not placed
    assert kept == endpoints[1:2] + endpoints[3:]
    raw = values[[1] + list(range(3, len(endpoints)))]
    assert pos.tolist() == WK.positions(raw).tolist()
    assert set(node) == {'place_middle', 'place_spread'}
    middle = np.median(pos[:, 1:], axis=0)
    assert node['place_middle'] == middle.tolist()
    assert node['place_spread'] == (WK.MAD_TO_SPREAD
                                    * np.median(np.abs(pos[:, 1:] - middle), axis=0)).tolist()

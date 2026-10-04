"""Value-only graph input to the construction experiment.

No corpus records, source locators, resolver, gold, or delivery costs belong in
this type. Description similarities are supplied separately as numeric query
readings from graph-held description embeddings. This is a data contract, not
an operating-system sandbox or approval of every possible retrieval program.
"""
from dataclasses import dataclass
from types import MappingProxyType
import numpy as np


def _array(value, dtype):
    a = np.asarray(value, dtype=dtype)
    # Immutable backing bytes, with no references into a richer input object.
    return np.frombuffer(a.tobytes(), dtype=a.dtype).reshape(a.shape)


@dataclass(frozen=True, slots=True)
class GraphInput:
    chunk_ids: tuple
    edge_tag: np.ndarray
    edge_chunk: np.ndarray
    facet_readings: np.ndarray
    groups: object
    adjacency_pairs: tuple
    product_groups: tuple

    def __post_init__(self):
        ids = tuple(self.chunk_ids)
        if not ids or any(type(c) is not str for c in ids) or len(set(ids)) != len(ids):
            raise ValueError('Unique opaque chunk IDs required')
        object.__setattr__(self, 'chunk_ids', ids)
        for name, dtype in [('edge_tag', int), ('edge_chunk', int), ('facet_readings', float)]:
            object.__setattr__(self, name, _array(getattr(self, name), dtype))
        et, ec, f = self.edge_tag, self.edge_chunk, self.facet_readings
        if et.ndim != 1 or ec.shape != et.shape or f.shape != (len(et), 5):
            raise ValueError('Graph edge arrays must align')
        if (et < 0).any() or ((ec < 0) | (ec >= len(ids))).any() or not np.isfinite(f).all() or (f < 0).any():
            raise ValueError('Invalid graph edge readings or endpoints')
        def members(values):
            result = tuple(int(v) for v in values)
            if any(v < 0 or v >= len(ids) for v in result):
                raise ValueError('Relation endpoint outside graph')
            return result
        # Relation labels are ordinal; no arbitrary metadata is retained.
        object.__setattr__(self, 'groups', MappingProxyType({
            i: tuple(members(g) for g in groups)
            for i, groups in enumerate(self.groups.values())}))
        pairs = tuple(members(p) for p in self.adjacency_pairs)
        if any(len(p) != 2 for p in pairs):
            raise ValueError('Adjacency requires pairs')
        object.__setattr__(self, 'adjacency_pairs', pairs)
        object.__setattr__(self, 'product_groups', tuple(members(g) for g in self.product_groups))

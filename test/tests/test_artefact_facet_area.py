"""Serving wiring for the explicit area-first candidate, no model calls."""
from types import SimpleNamespace

import numpy as np
import pytest

from arms import artefact_facet_area as area
from arms import artefact_facet_joint as joint


def test_variant_preparation_selects_and_records_its_source(monkeypatch):
    calls = []
    def prepare(corpus, *, scope_scheduling):
        calls.append((corpus, scope_scheduling))
        return SimpleNamespace(scope_scheduling=scope_scheduling, provenance={'source_sha256': {}})
    monkeypatch.setattr(joint, 'prepare_over_corpus', prepare)
    prepared = area.prepare_over_corpus('synthetic-corpus')
    assert calls == [('synthetic-corpus', 'area_first')]
    assert prepared.scope_scheduling == 'area_first'
    assert any(path.replace('\\', '/') == 'test/arms/artefact_facet_area.py'
               for path in prepared.provenance['source_sha256'])
    assert area.answer_one_question is joint.answer_one_question


@pytest.mark.parametrize('schedule,expected', [
    ('equal_depth', ['a', 'c', 'b']), ('area_first', ['a', 'b', 'c'])])
def test_actual_rank_dispatches_scope_policy_without_changing_scores(monkeypatch, schedule, expected):
    chunks = tuple({'chunkId': cid, 'locator': {}, 'relpath': 'synthetic', 'source_text': cid}
                   for cid in 'abc')
    prepared = SimpleNamespace(chunks=chunks, edge_ids=[], edge_tag=[], edge_chunk=[], edge_facets=[],
        reference=None, groups={}, adjacency_pairs=(), structural_index=object(), scope_scheduling=schedule)
    monkeypatch.setattr(joint, 'retrieve_prepared_query', lambda **kwargs: {
        'ranking': {'scores': np.array([.8, .7, .9])}})
    monkeypatch.setattr(joint, 'resolve_structural_area', lambda text, index: (
        frozenset('ab'), {'status': 'resolved'}))
    result = joint._rank(prepared, 'synthetic', {'tags': ['tag']}, np.ones((1, 5)), {})
    assert result['recruitment']['selected_chunk_ids'] == expected
    assert result['area']['policy']['scheduling'] == schedule
    np.testing.assert_array_equal(result['ranking']['scores'], [.8, .7, .9])


def test_invalid_schedule_fails_before_snapshot_read(monkeypatch):
    monkeypatch.setattr(joint, '_read', lambda *args: pytest.fail('must fail before preparation'))
    with pytest.raises(ValueError, match='scope_scheduling'):
        joint.prepare_over_corpus('unused', scope_scheduling='invented')

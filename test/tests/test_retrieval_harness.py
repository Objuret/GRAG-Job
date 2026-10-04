"""Resume boundaries and reports must not silently change the experiment."""
import json
import numpy as np
import pytest
import retrieval_harness as H


def fake_run(tmp_path, monkeypatch):
    monkeypatch.setattr(H, 'RUNS', tmp_path)
    out = H.run_path('test')
    out.mkdir()
    (out / 'shards').mkdir()
    plan = dict(case_ids=['case_a', 'case_b'], cases=[{}, {}], policies=[H.L.DEFAULT],
                coefficients=[[1, .25, .25, .25, .25]], expected_shards=2,
                original_failed_question_ids=[], input_sha256={},
                runtime=dict(python=H.sys.version.split()[0], implementation=H.sys.implementation.name,
                             numpy=np.__version__))
    H.atomic_json(out / 'plan.json', plan)
    H.atomic_json(out / 'plan.sha256.json', {'sha256': H.L.digest(out / 'plan.json')})
    return out, plan


def add_shard(out, cid, metrics):
    path = out / 'shards' / (H.shard_name(cid, 0) + '.npz')
    np.savez_compressed(path, metrics=np.array([metrics]))
    H.atomic_json(path.with_suffix('.json'), dict(case_id=cid, policy_index=0,
        plan_sha256=H.L.digest(out / 'plan.json'), npz_sha256=H.L.digest(path)))
    return path


def test_partial_population_cannot_win_and_nan_precision_is_explicit(tmp_path, monkeypatch):
    out, _ = fake_run(tmp_path, monkeypatch)
    add_shard(out, 'case_a', [1., .5, 2/3])
    assert H.report_run('test')['leaders'] == []
    add_shard(out, 'case_b', [0., np.nan, 0.])
    row = H.report_run('test')['leaders'][0]
    assert row['recall_id'] == .5
    assert row['precision_id'] == .5
    assert row['f1_id'] == pytest.approx(1/3)
    assert row['defined_metric_cases'] == dict(recall_id=2, precision_id=1, f1_id=2)


def test_corrupt_completed_shard_refuses_resume(tmp_path, monkeypatch):
    out, plan = fake_run(tmp_path, monkeypatch)
    path = add_shard(out, 'case_a', [1., .5, 2/3])
    path.write_bytes(b'broken test data')
    with pytest.raises(ValueError, match='hash mismatch'):
        H.execute_run('test')
    assert not (out / 'writer.lock').exists()


def test_second_writer_cannot_remove_first_writers_lock(tmp_path, monkeypatch):
    out, _ = fake_run(tmp_path, monkeypatch)
    (out / 'writer.lock').write_text('owner', encoding='utf-8')
    with pytest.raises(FileExistsError):
        H.execute_run('test')
    assert (out / 'writer.lock').read_text() == 'owner'


def test_source_change_refuses_resume_and_releases_own_lock(tmp_path, monkeypatch):
    out, plan = fake_run(tmp_path, monkeypatch)
    source = tmp_path / 'fixture.txt'
    source.write_text('original')
    plan['input_sha256'] = {str(source): H.L.digest(source)}
    H.atomic_json(out / 'plan.json', plan)
    H.atomic_json(out / 'plan.sha256.json', {'sha256': H.L.digest(out / 'plan.json')})
    source.write_text('changed')
    with pytest.raises(ValueError, match='Frozen input changed'):
        H.execute_run('test')
    assert not (out / 'writer.lock').exists()


def test_recorded_grid_and_incompatible_combinations():
    cases, policies, betas, _ = H.normalize_spec(dict(
        policy_filters={'facet': ['separate_facet_sum']}, coefficient_grid='recorded_509'))
    assert (len(cases), len(policies), len(betas)) == (95, 1600, 509)
    with pytest.raises(ValueError, match='Every policy must use separate_facet_sum'):
        H.normalize_spec(dict(policy_filters={'facet': ['topic_only']}, coefficients=[[0, 1, 0, 0, 0]]))


@pytest.mark.parametrize('name', ['../batch', 'a/b', 'con'])
def test_run_names_cannot_escape_or_use_windows_devices(name):
    with pytest.raises(ValueError):
        H.run_path(name)

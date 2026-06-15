import json

import pytest

from v2.derive_corpus import derive_corpus


def _make_raw(tmp_path, product):
    ds = tmp_path / "raw" / "ds"
    (ds / "products").mkdir(parents=True)
    (ds / "metadata").mkdir()
    (ds / "products" / "p.json").write_text(json.dumps(product), encoding="utf-8")
    (ds / "metadata" / "dir.json").write_text('{"eid_1": {"name": "Anna"}}', encoding="utf-8")
    (ds / "README.md").write_text("# benchmark", encoding="utf-8")
    (ds / ".cache").mkdir()
    (ds / ".cache" / "blob.json").write_text("{}", encoding="utf-8")
    return ds


def _full_product():
    return {
        "team": ["eid_1", "eid_2"],
        "customers": ["CUST-0001"],
        "slack": [{"id": "1"}],
        "answerable_questions": [{"question": "q", "ground_truth": "a", "citations": []}],
        "unanswerable_questions": ["u1", "u2"],
    }


def test_corpus_view_strips_rag_unsafe_keys_and_copies_rest_verbatim(tmp_path):
    product = _full_product()
    ds = _make_raw(tmp_path, product)
    report = derive_corpus(ds)

    corpus = json.loads((tmp_path / "corpus" / "ds" / "products" / "p.json").read_text("utf-8"))
    assert set(corpus) == {"slack"}

    # nothing stripped is copied anywhere — it stays in raw, read in place
    assert not (tmp_path / "eval").exists()

    # metadata/ is the legitimate membership source (dataset card) — kept,
    # byte-identical with the raw
    assert (tmp_path / "corpus" / "ds" / "metadata" / "dir.json").read_bytes() == (
        ds / "metadata" / "dir.json"
    ).read_bytes()
    # non-json and dot-dirs never reach the corpus view
    assert not (tmp_path / "corpus" / "ds" / "README.md").exists()
    assert not (tmp_path / "corpus" / "ds" / ".cache").exists()

    assert report.n_stripped == 1
    assert report.n_copied == 1
    assert report.stripped_counts == {
        "answerable_questions": 1,
        "unanswerable_questions": 2,
        "team": 2,
        "customers": 1,
    }

    # the raw is untouched
    assert json.loads((ds / "products" / "p.json").read_text("utf-8")) == product


def test_partial_strip_keys_fail_loud(tmp_path):
    ds = _make_raw(tmp_path, {"slack": [], "answerable_questions": []})
    with pytest.raises(ValueError, match="not all of"):
        derive_corpus(ds)


def test_dataset_without_strip_keys_fails_loud(tmp_path):
    ds = _make_raw(tmp_path, {"slack": []})
    with pytest.raises(RuntimeError, match="nothing to strip"):
        derive_corpus(ds)


def test_requires_raw_working_root(tmp_path):
    ds = tmp_path / "elsewhere" / "ds"
    ds.mkdir(parents=True)
    with pytest.raises(ValueError, match="raw/"):
        derive_corpus(ds)

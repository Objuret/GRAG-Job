import json

import pytest

from artefact.scan import scan_dataset, scan_file


def test_scan_file_identity_and_format(tmp_path):
    f = tmp_path / "a.json"
    f.write_text('{"x": 1}', encoding="utf-8")
    rec = scan_file(f, tmp_path)
    assert rec.file_id == rec.sha256[:24]
    assert len(rec.sha256) == 64
    assert rec.format == "json"
    assert rec.relpath == "a.json"


def test_scan_dataset_skips_cache_dirs_and_fails_on_broken_json(tmp_path):
    ds = tmp_path / "ds"
    (ds / ".cache").mkdir(parents=True)
    (ds / ".cache" / "junk.json").write_text("{}", encoding="utf-8")
    (ds / "good.json").write_text(json.dumps({"a": [1, 2]}), encoding="utf-8")
    (ds / "notes.md").write_text("# hi", encoding="utf-8")
    records = scan_dataset(ds, tmp_path)
    assert {r.relpath for r in records} == {"ds/good.json", "ds/notes.md"}

    (ds / "bad.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(RuntimeError, match="unparseable JSON"):
        scan_dataset(ds, tmp_path)


def test_scan_empty_dataset_fails_loud(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(RuntimeError, match="zero files"):
        scan_dataset(empty, tmp_path)

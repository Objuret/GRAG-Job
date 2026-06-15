"""Golden tests for the shape probe — the deterministic prefix is cheap to
lock down (design §16): pure functions, no LLM, so these run on every edit."""

import pytest

from v2.probe import (
    LONG_TEXT_CHARS,
    derive_candidates,
    escape_pointer_token,
    fuse,
    profile,
)


def test_scalar_kinds():
    assert profile(None)["kinds"] == {"null"}
    assert profile(True)["kinds"] == {"bool"}
    assert profile(3)["kinds"] == {"int"}
    assert profile(3.5)["kinds"] == {"float"}
    assert profile("hi")["kinds"] == {"str"}
    assert profile("x" * (LONG_TEXT_CHARS + 1))["kinds"] == {"str_long"}


def test_array_fuses_elements():
    shape = profile([{"a": 1}, {"a": 2, "b": "x"}])
    elem = shape["elem"]
    assert elem["t"] == "object"
    assert not elem["keys"]["a"].get("optional")
    assert elem["keys"]["b"]["optional"] is True


def test_cross_file_fusion_marks_optional_and_merges_lengths():
    f1 = profile({"msgs": [{"u": "a", "text": "hi"}]})
    f2 = profile({"msgs": [{"u": "b"}, {"u": "c"}], "extra": 1})
    fused = fuse(f1, f2)
    msgs = fused["keys"]["msgs"]
    assert (msgs["len_min"], msgs["len_max"]) == (1, 2)
    assert msgs["elem"]["keys"]["text"]["optional"] is True
    assert fused["keys"]["extra"]["optional"] is True


def test_scalar_fusion_merges_kinds():
    fused = fuse(profile(1), profile("x"))
    assert fused["t"] == "scalar"
    assert fused["kinds"] == {"int", "str"}


def test_ragged_on_type_conflict():
    fused = fuse(profile(1), profile({"a": 1}))
    assert fused["t"] == "ragged"
    assert fused["kinds"] == {"int", "object"}


def test_empty_array_fuses_with_populated():
    # the §10 finding: one file's empty array under-determines the schema;
    # fusing with a populated sibling must reveal the element shape
    empty = profile({"meeting_chats": []})
    full = profile({"meeting_chats": [{"who": "a", "said": "b"}]})
    fused = fuse(empty, full)
    mc = fused["keys"]["meeting_chats"]
    assert mc["len_min"] == 0 and mc["len_max"] == 1
    assert mc["elem"]["t"] == "object"
    assert set(mc["elem"]["keys"]) == {"who", "said"}


def test_candidates_collections_and_docleaves():
    data = {
        "prs": [{"title": "t", "reviews": [{"user": "u", "body": "x" * 300}]}],
        "doc": "y" * 300,
        "n": 5,
    }
    collections, docleaves = derive_candidates(profile(data))
    pointers = {c.pointer for c in collections}
    assert "/prs" in pointers
    assert "/prs/*/reviews" in pointers          # nested collection found
    leaf_pointers = {d.pointer for d in docleaves}
    assert "/doc" in leaf_pointers
    assert "/prs/*/reviews/*/body" in leaf_pointers


def test_pointer_escaping():
    assert escape_pointer_token("a/b~c") == "a~1b~0c"
    collections, _ = derive_candidates(profile({"a/b": [{"k": 1}]}))
    assert collections[0].pointer == "/a~1b"


def test_unsupported_type_fails_loud():
    with pytest.raises(TypeError):
        profile({"x": object()})

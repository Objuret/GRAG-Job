"""Golden tests for the shape probe — the deterministic prefix is cheap to
lock down (design §16): pure functions, no LLM, so these run on every edit."""

import pytest

from artefact.probe import (
    LONG_TEXT_CHARS,
    derive_candidates,
    escape_pointer_token,
    fuse,
    is_content_file,
    profile,
    typical_str_len,
)


def test_scalar_kinds():
    assert profile(None)["kinds"] == {"null"}
    assert profile(True)["kinds"] == {"bool"}
    assert profile(3)["kinds"] == {"int"}
    assert profile(3.5)["kinds"] == {"float"}
    assert profile("hi")["kinds"] == {"str"}
    # a long string is still a `str`; whether it is prose is a typical-length
    # judgment over instances (typical_str_len), not a per-instance kind
    long_one = profile("x" * (LONG_TEXT_CHARS + 1))
    assert long_one["kinds"] == {"str"}
    assert typical_str_len(long_one) == LONG_TEXT_CHARS + 1


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


def test_docleaf_discriminator_is_typical_not_max():
    # a position whose instances are TYPICALLY short is NOT a prose leaf, even
    # when one outlier instance is long: median decides, not the max.
    short = profile({"f": [{"summary": "ok"}] * 3 + [{"summary": "x" * 5000}]})
    leaves = {d.pointer for d in derive_candidates(short)[1]}
    assert "/f/*/summary" not in leaves          # typical length is 2 chars
    # a position whose instances are typically long IS a prose leaf
    longp = profile({"f": [{"content": "y" * 3000} for _ in range(3)]})
    leaves = {d.pointer for d in derive_candidates(longp)[1]}
    assert "/f/*/content" in leaves


def test_str_lens_fuse_accumulates_across_instances():
    fused = fuse(profile("aaa"), profile("aaaaa"))
    assert fused["t"] == "scalar"
    assert sorted(fused["str_lens"]) == [3, 5]
    assert typical_str_len(fused) == 4          # median of {3, 5}


def test_is_content_file_scopes_to_collection_roots():
    # a product-shaped object (collection-of-objects root) is a content file
    assert is_content_file({"slack": [{"a": 1}], "n": 2}) is True
    # an id-directory (flat dict keyed by id) is not — its values are objects,
    # not collections
    assert is_content_file({"eid_1": {"name": "x"}, "eid_2": {"name": "y"}}) is False
    # a top-level-array file is not (it is not even a top-level object)
    assert is_content_file([{"id": 1}, {"id": 2}]) is False


def test_pointer_escaping():
    assert escape_pointer_token("a/b~c") == "a~1b~0c"
    collections, _ = derive_candidates(profile({"a/b": [{"k": 1}]}))
    assert collections[0].pointer == "/a~1b"


def test_unsupported_type_fails_loud():
    with pytest.raises(TypeError):
        profile({"x": object()})

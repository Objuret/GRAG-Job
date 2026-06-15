from v2.baselines.common import sanitize_lucene
from v2.baselines.lucene import retrieve_baseline_content


def test_sanitize_lucene_strips_special_chars():
    assert sanitize_lucene('foo+bar "baz"') == "foo bar baz"


def test_retrieve_baseline_content_empty_question():
    assert retrieve_baseline_content("   ") == []

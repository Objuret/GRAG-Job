import json

import pytest

from graph import facet_counterfactuals as fc

TEXT = ("The database migration was postponed until Friday because the security review "
        "was not completed. The team will retry next sprint.")


def edit(find, replace):
    return {"find": find, "replace": replace}


# ------------------------------------------------------------------ apply_edits

def test_apply_edits_replaces_a_unique_span():
    out, problems = fc.apply_edits(TEXT, [edit("postponed until Friday", "postponed")])
    assert problems == []
    assert out.startswith("The database migration was postponed because")
    assert out.endswith("retry next sprint.")


def test_apply_edits_deletes_with_empty_replacement():
    out, problems = fc.apply_edits(TEXT, [edit(" The team will retry next sprint.", "")])
    assert problems == []
    assert out.endswith("was not completed.")


def test_apply_edits_keeps_every_untouched_character():
    out, _ = fc.apply_edits(TEXT, [edit("Friday", "a later date")])
    assert out.replace("a later date", "Friday") == TEXT


def test_apply_edits_applies_several_spans_in_text_order_whatever_the_list_order():
    a = [edit("next sprint", "later"), edit("until Friday", "for now")]
    b = [edit("until Friday", "for now"), edit("next sprint", "later")]
    assert fc.apply_edits(TEXT, a)[0] == fc.apply_edits(TEXT, b)[0]
    assert "for now" in fc.apply_edits(TEXT, a)[0]
    assert "later" in fc.apply_edits(TEXT, a)[0]


def test_apply_edits_refuses_an_anchor_that_is_not_in_the_text():
    out, problems = fc.apply_edits(TEXT, [edit("postponed until Monday", "x")])
    assert out == TEXT
    assert len(problems) == 1 and "not in the text" in problems[0]


def test_apply_edits_refuses_an_anchor_that_occurs_twice():
    text = "the review is done. the review is done."
    out, problems = fc.apply_edits(text, [edit("the review", "it")])
    assert out == text
    assert len(problems) == 1 and "occurs 2 times" in problems[0]


def test_apply_edits_refuses_overlapping_spans():
    out, problems = fc.apply_edits(TEXT, [edit("postponed until Friday", "postponed"),
                                          edit("until Friday because", "because")])
    assert any("overlaps" in p for p in problems)
    assert out.count("because") == 1


def test_apply_edits_names_a_malformed_edit_and_applies_the_rest():
    out, problems = fc.apply_edits(TEXT, [{"replace": "x"}, edit("Friday", "soon")])
    assert "soon" in out
    assert len(problems) == 1 and "no `find`" in problems[0]


def test_apply_edits_empty_list_returns_the_original():
    out, problems = fc.apply_edits(TEXT, [])
    assert out == TEXT and problems == []


def test_apply_edits_rejects_a_non_string_replacement():
    out, problems = fc.apply_edits(TEXT, [{"find": "Friday", "replace": None}])
    assert out == TEXT
    assert len(problems) == 1 and "not a string" in problems[0]


# ------------------------------------------------------------------ parse, edits format

def payload_edits(tag="database migration", **over):
    facets = {f: {"edits": [edit("Friday", "a later date")], "note": "n"}
              for f in fc.FACETS}
    facets.update(over)
    return {"edges": [{"t": tag, **facets}]}


def test_parse_edits_reconstructs_every_facet():
    rows, problems = fc.parse_counterfactuals(payload_edits(), ["database migration"], TEXT,
                                              "edits")
    assert problems == []
    assert len(rows) == 1 and rows[0]["matched"] is True
    for f in fc.FACETS:
        rec = rows[0][f]
        assert rec["text"] != TEXT and rec["changed"] is True
        assert rec["reconstruction_ok"] is True and rec["applied"] == 1


def test_parse_edits_empty_edit_list_is_an_unchanged_counterfactual():
    rows, _ = fc.parse_counterfactuals(
        payload_edits(temporal={"edits": [], "note": "nothing temporal here"}),
        ["database migration"], TEXT, "edits")
    rec = rows[0]["temporal"]
    assert rec["text"] == TEXT and rec["changed"] is False
    assert rec["reconstruction_ok"] is True and rec["note"] == "nothing temporal here"


def test_parse_edits_marks_a_failed_anchor_on_that_facet_only():
    rows, problems = fc.parse_counterfactuals(
        payload_edits(why={"edits": [edit("no such span", "x")], "note": "n"}),
        ["database migration"], TEXT, "edits")
    assert rows[0]["why"]["reconstruction_ok"] is False
    assert rows[0]["temporal"]["reconstruction_ok"] is True
    assert any("why" in p for p in problems)


def test_parse_drops_a_row_missing_a_facet():
    bad = payload_edits()
    del bad["edges"][0]["activity"]
    with pytest.raises(ValueError):
        fc.parse_counterfactuals(bad, ["database migration"], TEXT, "edits")


def test_parse_keeps_an_unasked_phrase_and_marks_it():
    rows, _ = fc.parse_counterfactuals(payload_edits(tag="something else"),
                                       ["database migration"], TEXT, "edits")
    assert rows[0]["matched"] is False


def test_parse_refuses_a_payload_with_no_edges():
    with pytest.raises(ValueError):
        fc.parse_counterfactuals({"edges": []}, ["t"], TEXT, "edits")
    with pytest.raises(ValueError):
        fc.parse_counterfactuals([], ["t"], TEXT, "edits")


# ------------------------------------------------------------------ parse, full format

def test_parse_full_takes_the_returned_text():
    rewritten = TEXT.replace("Friday", "a later date")
    payload = {"edges": [{"t": "database migration",
                          **{f: {"chunk": rewritten, "note": "n"} for f in fc.FACETS}}]}
    rows, problems = fc.parse_counterfactuals(payload, ["database migration"], TEXT, "full")
    assert problems == []
    assert rows[0]["temporal"]["text"] == rewritten
    assert rows[0]["temporal"]["edits"] is None
    assert rows[0]["temporal"]["changed"] is True


def test_parse_full_unchanged_text_is_recorded_as_unchanged():
    payload = {"edges": [{"t": "t", **{f: {"chunk": TEXT, "note": "n"} for f in fc.FACETS}}]}
    rows, _ = fc.parse_counterfactuals(payload, ["t"], TEXT, "full")
    assert rows[0]["why"]["changed"] is False


def test_parse_full_refuses_an_empty_chunk():
    payload = {"edges": [{"t": "t", **{f: {"chunk": "", "note": "n"} for f in fc.FACETS}}]}
    with pytest.raises(ValueError):
        fc.parse_counterfactuals(payload, ["t"], TEXT, "full")


# ------------------------------------------------------------------ prompt and resume

def test_the_two_prompts_share_the_body_and_differ_in_the_tail():
    a, b = fc.prompt_text("edits"), fc.prompt_text("full")
    body = fc.BODY_PATH.read_text(encoding="utf-8").rstrip()
    assert a.startswith(body) and b.startswith(body)
    assert a != b and fc.prompt_sha(a) != fc.prompt_sha(b)


def test_prompt_text_refuses_an_unknown_format():
    with pytest.raises(SystemExit):
        fc.prompt_text("paraphrase")


def test_status_of_a_complete_file_is_done(tmp_path):
    rows, _ = fc.parse_counterfactuals(payload_edits(), ["database migration"], TEXT, "edits")
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"prompt_sha256": "s", "given": 1, "answered": 1,
                             "complete": True, "edges": rows}), encoding="utf-8")
    assert fc.status_of(p, "s") == "done"
    assert fc.status_of(p, "other") == "prompt_mismatch"


def test_status_of_a_partial_payload_is_not_done(tmp_path):
    rows, _ = fc.parse_counterfactuals(payload_edits(), ["database migration"], TEXT, "edits")
    del rows[0]["activity"]
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"prompt_sha256": "s", "given": 1, "answered": 1,
                             "complete": True, "edges": rows}), encoding="utf-8")
    assert fc.status_of(p, "s") == "incomplete"


def test_status_of_a_half_answered_file_is_not_done(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"prompt_sha256": "s", "given": 5, "answered": 2,
                             "complete": False, "edges": []}), encoding="utf-8")
    assert fc.status_of(p, "s") == "incomplete"


def test_status_of_a_missing_or_broken_file(tmp_path):
    assert fc.status_of(tmp_path / "nope.json") == "missing"
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    assert fc.status_of(p) == "unreadable"


# ------------------------------------------------------------------ the lane

def test_workers_above_eight_is_refused():
    with pytest.raises(SystemExit):
        fc.main(["--workers", "9", "--dry-run"])


def test_a_lane_error_with_no_backend_is_not_retried():
    assert fc.retryable(RuntimeError("model 'x' has no backend")) is False
    assert fc.retryable(RuntimeError("rate limit reached")) is True


def test_user_message_carries_the_text_and_every_phrase():
    msg = fc.user_message(TEXT, ["a", "b"])
    assert msg.startswith("Text:\n") and "\nPhrases:\n- a\n- b" in msg


# ------------------------------------------------------------------ multi-message replies

def test_join_stream_joins_every_assistant_text_block():
    """A long answer arrives as several assistant messages; the `json` envelope keeps only the
    last, which is why two chunks came back beginning mid-JSON on 2026-09-17."""
    import json as _json
    from harness.chat import join_stream
    lines = [
        {"type": "system", "subtype": "init"},
        {"type": "assistant", "message": {"content": [{"type": "thinking"}]}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": '{"edges": ['}]}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": '{"t": "a"}]}'}]}},
        {"type": "result", "result": '{"t": "a"}]}', "num_turns": 3, "usage": {}},
    ]
    joined, result = join_stream("\n".join(_json.dumps(x) for x in lines))
    assert joined == '{"edges": [{"t": "a"}]}'
    assert _json.loads(joined)["edges"][0]["t"] == "a"
    assert result["num_turns"] == 3


def test_join_stream_ignores_non_json_and_missing_result():
    from harness.chat import join_stream
    joined, result = join_stream("not json\n\n")
    assert joined == "" and result == {}


# ------------------------------------------------------------------ phrase grouping

def test_group_size_comes_from_the_measured_ceiling_and_rate():
    from graph.facet_counterfactuals import (GROUP_TAGS, MAX_PARSED_OUTPUT_TOKENS,
                                             P90_OUTPUT_TOKENS_PER_COUNTERFACTUAL)
    assert GROUP_TAGS == MAX_PARSED_OUTPUT_TOKENS // (P90_OUTPUT_TOKENS_PER_COUNTERFACTUAL * 4)
    assert GROUP_TAGS > 0


def test_a_chunk_under_the_ceiling_is_one_call():
    from graph.facet_counterfactuals import GROUP_TAGS, tag_groups
    tags = [f"t{i}" for i in range(GROUP_TAGS)]
    assert tag_groups(tags) == [tags]


def test_a_chunk_over_the_ceiling_is_split_and_loses_no_phrase():
    from graph.facet_counterfactuals import GROUP_TAGS, tag_groups
    for n in (GROUP_TAGS + 1, 31, 37, 48):
        tags = [f"t{i}" for i in range(n)]
        groups = tag_groups(tags)
        assert len(groups) > 1
        assert [t for g in groups for t in g] == tags
        assert all(len(g) <= GROUP_TAGS for g in groups)


def test_groups_are_evened_out_not_a_full_group_and_a_remainder_of_one():
    from graph.facet_counterfactuals import tag_groups
    groups = tag_groups([f"t{i}" for i in range(20)], size=19)
    assert len(groups) == 2
    assert max(len(g) for g in groups) - min(len(g) for g in groups) <= 1


def test_grouped_ask_shows_the_other_phrases_as_context_only():
    from graph.facet_counterfactuals import user_message
    msg = user_message("some text", ["a", "b"], ["a", "b", "c"])
    assert "do NOT answer for these" in msg
    assert msg.index("- c") > msg.index("do NOT answer")


def test_ungrouped_ask_carries_no_context_section():
    from graph.facet_counterfactuals import user_message
    msg = user_message("some text", ["a", "b"], ["a", "b"])
    assert "do NOT answer" not in msg

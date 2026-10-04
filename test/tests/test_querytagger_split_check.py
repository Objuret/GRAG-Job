import json

import pytest

from artefact import querytagger_split_check as sc
from artefact.querytagger import GENERATE_SYSTEM, SCORE_SYSTEM, SPLIT_FACETS


def five(v=0.5):
    return {f: v for f in SPLIT_FACETS}


# ------------------------------------------------------------------ the prompts

def test_prompt_shas_are_the_texts_on_disk():
    assert sc.GENERATE_SHA == sc.sha(GENERATE_SYSTEM)
    assert sc.SCORE_SHA == sc.sha(SCORE_SYSTEM)


def test_generate_prompt_carries_the_question():
    system, user = sc.generate_prompt("who decided the rollout?")
    assert system == GENERATE_SYSTEM
    assert user == "Question: who decided the rollout?"


def test_score_prompt_lists_the_tags_and_never_the_question():
    system, user = sc.score_prompt("a record of decisions", ["rollout decision", "latency"])
    assert system == SCORE_SYSTEM
    assert user == ("Description: a record of decisions\n\nTags:\n"
                    "- rollout decision\n- latency")


# ------------------------------------------------------------------ parse_generate

def test_generate_parses_and_cleans():
    got = sc.parse_generate({"description": "  a record  ",
                             "tags": ["rollout  decision", "Rollout decision", "x", "latency"]})
    assert got == {"description": "a record", "tags": ["rollout decision", "latency"]}


@pytest.mark.parametrize("raw", [
    [],
    {"tags": ["a tag"]},
    {"description": "   ", "tags": ["a tag"]},
    {"description": "a record", "tags": []},
    {"description": "a record", "tags": "a tag"},
    {"description": "a record", "tags": [{"t": "a tag"}]},
    {"description": "a record", "tags": ["x"]},
])
def test_generate_refuses_a_wrong_payload(raw):
    with pytest.raises(ValueError):
        sc.parse_generate(raw)


# ------------------------------------------------------------------ parse_score

def test_score_returns_the_tags_in_the_order_given():
    tags = ["rollout decision", "latency"]
    raw = {"tags": [{"t": "latency", "facets": five(0.2)},
                    {"t": "Rollout Decision", "facets": five(0.9)}]}
    got = sc.parse_score(raw, tags)
    assert [r["t"] for r in got["tags"]] == tags
    assert got["tags"][0]["facets"]["topic"] == 0.9
    assert got["tags"][1]["facets"]["topic"] == 0.2


def test_score_refuses_a_missing_tag():
    with pytest.raises(ValueError, match="unanswered"):
        sc.parse_score({"tags": [{"t": "latency", "facets": five()}]},
                       ["latency", "rollout decision"])


def test_score_refuses_an_unknown_tag():
    with pytest.raises(ValueError, match="was not given"):
        sc.parse_score({"tags": [{"t": "latency", "facets": five()},
                                 {"t": "something else", "facets": five()}]},
                       ["latency"])


def test_score_refuses_a_repeat():
    with pytest.raises(ValueError, match="twice"):
        sc.parse_score({"tags": [{"t": "latency", "facets": five()},
                                 {"t": "latency", "facets": five()}]},
                       ["latency"])


@pytest.mark.parametrize("facets", [
    {"topic": 0.5, "temporal": 0.5, "why": 0.5, "activity": 0.5},
    dict(five(), concreteness="0.5"),
    dict(five(), concreteness=True),
    dict(five(), concreteness=1.5),
    dict(five(), concreteness=-0.1),
    dict(five(), evidence=0.5, concreteness=None),
])
def test_score_refuses_bad_facets(facets):
    with pytest.raises(ValueError):
        sc.parse_score({"tags": [{"t": "latency", "facets": facets}]}, ["latency"])


def test_score_refuses_a_facets_object_that_is_not_one():
    with pytest.raises(ValueError, match="no facets object"):
        sc.parse_score({"tags": [{"t": "latency", "facets": [0.5] * 5}]}, ["latency"])


# ------------------------------------------------------------------ the call and the re-ask

def _lane(replies):
    seen = []

    def post(path, payload, timeout=0.0):
        seen.append(payload)
        body = replies[len(seen) - 1]
        return {"choices": [{"message": {"content": body}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 10}}
    return post, seen


def test_ask_returns_on_the_first_good_reply():
    post, seen = _lane([json.dumps({"description": "a record", "tags": ["latency"]})])
    got = sc.ask("sys", "user", sc.parse_generate, post=post)
    assert got["ok"] and got["tries"] == 1 and len(seen) == 1
    assert got["parsed"]["tags"] == ["latency"]
    assert got["tokens_in"] == 100 and got["tokens_out"] == 10


def test_ask_re_asks_once_then_returns():
    post, seen = _lane(["not json at all",
                        json.dumps({"description": "a record", "tags": ["latency"]})])
    got = sc.ask("sys", "user", sc.parse_generate, post=post)
    assert got["ok"] and got["tries"] == 2 and len(seen) == 2
    assert got["tokens_in"] == 200


def test_ask_never_loops_past_two():
    post, seen = _lane(["nope", "still nope"])
    got = sc.ask("sys", "user", sc.parse_generate, post=post)
    assert not got["ok"] and got["tries"] == 2 and len(seen) == 2
    assert got["error"]


def test_ask_counts_a_truncated_reply_as_a_failure():
    def post(path, payload, timeout=0.0):
        return {"choices": [{"message": {"content": "{"}, "finish_reason": "length"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
    got = sc.ask("sys", "user", sc.parse_generate, post=post)
    assert not got["ok"] and "truncated" in got["error"]


# ------------------------------------------------------------------ the guard

def test_guard_trips_on_the_per_call_input_tokens():
    g = sc.Guard(45000)
    g.check("q01 G g1", 44000, 1)
    assert not g.stopped()
    g.check("q02 G g1", 92000, 2)      # two tries, 46,000 each
    assert g.stopped() and "46,000" in g.tripped


# ------------------------------------------------------------------ resume

def test_a_finished_call_is_read_back_and_a_failed_one_is_not(tmp_path):
    ok = tmp_path / "a.json"
    ok.write_text(json.dumps({"ok": True, "parsed": {"tags": []}}), encoding="utf-8")
    bad = tmp_path / "b.json"
    bad.write_text(json.dumps({"ok": False}), encoding="utf-8")
    broken = tmp_path / "c.json"
    broken.write_text("{ not json", encoding="utf-8")
    assert sc._read_done(ok) is not None
    assert sc._read_done(bad) is None
    assert sc._read_done(broken) is None
    assert sc._read_done(tmp_path / "missing.json") is None


def test_run_stage_skips_what_is_already_on_disk(tmp_path):
    calls = []

    def post(path, payload, timeout=0.0):
        calls.append(payload)
        return {"choices": [{"message": {"content": json.dumps(
            {"description": "a record", "tags": ["latency"]})}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5}}

    job = ("q01", "G", "g1", "sys", "user", sc.parse_generate, 256, {"question": "hidden"})
    counters = {"calls": 0, "reasks": 0, "failures": 0, "skipped": 0,
                "tokens_in": 0, "tokens_out": 0}
    guard = sc.Guard(10 ** 9)
    sc.run_stage([job], tmp_path, 1, guard, counters, post)
    assert len(calls) == 1 and counters["calls"] == 1 and counters["skipped"] == 0
    sc.run_stage([job], tmp_path, 1, guard, counters, post)
    assert len(calls) == 1 and counters["skipped"] == 1


def test_the_written_file_carries_what_the_report_needs(tmp_path):
    def post(path, payload, timeout=0.0):
        return {"choices": [{"message": {"content": json.dumps(
            {"description": "a record", "tags": ["latency"]})}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 7, "completion_tokens": 3}}

    job = ("q01", "G", "g1", GENERATE_SYSTEM, "Question: x", sc.parse_generate, 256,
           {"question": "x"})
    counters = {"calls": 0, "reasks": 0, "failures": 0, "skipped": 0,
                "tokens_in": 0, "tokens_out": 0}
    sc.run_stage([job], tmp_path, 1, sc.Guard(10 ** 9), counters, post)
    body = json.loads((tmp_path / "q01.G.g1.json").read_text(encoding="utf-8"))
    for field in ("question_id", "stage", "ask", "system_sha256", "model", "raw", "parsed",
                  "tokens_in", "tokens_out", "seconds", "tries", "timestamp"):
        assert field in body
    assert body["system_sha256"] == sc.GENERATE_SHA

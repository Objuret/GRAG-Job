import json

import pytest

from graph import facet_answers as fa
from graph import facet_views as fv
from graph import facet_views_texts as fvt
from graph.facet_edits import FACETS

ORIGINAL_A = ("The database migration was postponed until Friday because the security review "
              "was not completed. The team will retry next sprint.")

ORIGINAL_B = "The dashboard shows 42 open tickets for the payments team this week."

TAGS_A = ["database migration", "security review"]

TAGS_B = ["dashboard"]


# ------------------------------------------------------------------ synthetic counterfactuals

def cf_facet(text, changed=True, ok=True, note="n"):
    return {"note": note, "edits": [], "text": text, "applied": 0, "asked": 0,
            "changed": changed, "problems": [], "reconstruction_ok": ok}


def write_cf(directory, chunk_id, kind, product, text, tags, per_edge):
    """`per_edge` is {tag: {facet: facet record}}; anything left out is an unchanged facet."""
    edges = []
    for tag in tags:
        row = {"t": tag, "matched": True}
        for facet in FACETS:
            row[facet] = per_edge.get(tag, {}).get(facet, cf_facet(text, changed=False))
        edges.append(row)
    rec = {"chunk_id": chunk_id, "kind": kind, "product": product, "tags": list(tags),
           "given": len(tags), "answered": len(tags), "complete": True, "format": "edits",
           "text": text, "edges": edges, "prompt_sha256": "p"}
    path = directory / f"{fa.file_stem(chunk_id)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def cf_dirs(tmp_path):
    """Two chunks in two generations. Chunk A: one changed text per facet on its first tag, one
    unchanged, one reconstruction failure, and two facets of the second tag producing the same
    text. Chunk B: one changed text and three unchanged."""
    main = tmp_path / "counterfactuals" / "db"
    repeat = tmp_path / "counterfactuals_repeat" / "db"

    dup = ORIGINAL_A.replace("Friday", "a later date")
    write_cf(main, "aaa", "slack_thread", "FlowForce", ORIGINAL_A, TAGS_A, {
        "database migration": {
            "temporal": cf_facet(ORIGINAL_A.replace("until Friday", "")),
            "why": cf_facet(ORIGINAL_A.replace("because the security review was not completed",
                                               "")),
            "activity": cf_facet(ORIGINAL_A, changed=False),
            "concreteness": cf_facet(ORIGINAL_A.replace("Friday", "x"), ok=False),
        },
        "security review": {
            "temporal": cf_facet(dup),
            "why": cf_facet(dup),
            "activity": cf_facet(ORIGINAL_A.replace("The team", "Someone")),
            "concreteness": cf_facet(ORIGINAL_A, changed=False),
        },
    })
    write_cf(repeat, "aaa", "slack_thread", "FlowForce", ORIGINAL_A, TAGS_A, {
        "database migration": {"temporal": cf_facet(ORIGINAL_A.replace("Friday", "Monday"))},
    })
    write_cf(main, "bbb", "pr_batch", "VizForce", ORIGINAL_B, TAGS_B, {
        "dashboard": {"concreteness": cf_facet(ORIGINAL_B.replace("42", "some"))},
    })
    write_cf(repeat, "bbb", "pr_batch", "VizForce", ORIGINAL_B, TAGS_B, {})

    ids = tmp_path / "ids.txt"
    ids.write_text("aaa\nbbb\n", encoding="utf-8")
    return {"main": main, "repeat": repeat, "ids": ids, "tmp": tmp_path, "dup": dup}


def build_texts(cf_dirs, out=None):
    out = out or (cf_dirs["tmp"] / "texts.jsonl")
    fvt.main(["--cf-dir", str(cf_dirs["main"]), "--cf-dir", str(cf_dirs["repeat"]),
              "--ids-file", str(cf_dirs["ids"]), "--out", str(out)])
    return fvt.read_texts(out)


# ------------------------------------------------------------------ the text set

def test_generation_label_comes_from_the_path(tmp_path):
    assert fvt.split_cf_dir("output/facet_neural/counterfactuals/db")[0] == "main"
    assert fvt.split_cf_dir("output/facet_neural/counterfactuals_repeat/db")[0] == "repeat"
    label, path = fvt.split_cf_dir("repeat=C:/somewhere/else")
    assert label == "repeat" and path.as_posix() == "C:/somewhere/else"


def test_texts_counts_every_counterfactual_and_keeps_only_changed_ones(cf_dirs):
    header, rows = build_texts(cf_dirs)
    # 2 tags x 4 facets + 1 tag x 4 facets, in two generations
    assert header["counterfactuals"] == (8 + 4) * 2
    assert header["unchanged"] == 2 + 3 + 7 + 4            # main A, main B, repeat A, repeat B
    assert header["recon_fail"] == 1
    assert header["ids"] == 2
    assert header["texts"] == len(rows)
    assert header["by_kind"] == {"pr_batch": 2, "slack_thread": len(rows) - 2}


def test_every_text_is_distinct_and_its_sha_is_its_own(cf_dirs):
    _header, rows = build_texts(cf_dirs)
    shas = [r["sha"] for r in rows]
    assert len(set(shas)) == len(shas)
    for r in rows:
        assert fvt.sha256_of(r["text"]) == r["sha"]


def test_the_originals_come_first_and_carry_the_original_origin(cf_dirs):
    _header, rows = build_texts(cf_dirs)
    by_sha = {r["sha"]: r for r in rows}
    original = by_sha[fvt.sha256_of(ORIGINAL_A)]
    assert original["origins"] == [{"generation": "original"}]
    assert original["chunk_id"] == "aaa" and original["tags"] == TAGS_A
    assert original["kind"] == "slack_thread" and original["product"] == "FlowForce"


def test_a_text_two_counterfactuals_produce_carries_both_origins(cf_dirs):
    _header, rows = build_texts(cf_dirs)
    row = {r["sha"]: r for r in rows}[fvt.sha256_of(cf_dirs["dup"])]
    assert row["origins"] == [
        {"generation": "main", "tag": "security review", "facet": "temporal"},
        {"generation": "main", "tag": "security review", "facet": "why"},
    ]


def test_an_unchanged_or_failed_counterfactual_is_not_a_text(cf_dirs):
    _header, rows = build_texts(cf_dirs)
    texts = {r["text"] for r in rows}
    assert ORIGINAL_A.replace("Friday", "x") not in texts          # reconstruction failed
    assert sum(1 for r in rows if r["chunk_id"] == "bbb") == 2     # original + one changed


def test_a_repeat_original_that_differs_is_refused(cf_dirs):
    write_cf(cf_dirs["repeat"], "aaa", "slack_thread", "FlowForce", ORIGINAL_A + " x", TAGS_A,
             {})
    with pytest.raises(SystemExit) as err:
        build_texts(cf_dirs)
    assert "different" in str(err.value)


def test_a_missing_generation_file_is_refused(cf_dirs):
    (cf_dirs["repeat"] / f"{fa.file_stem('bbb')}.json").unlink()
    with pytest.raises(SystemExit) as err:
        build_texts(cf_dirs)
    assert "no file for bbb" in str(err.value)


def test_the_summary_carries_a_row_per_chunk(cf_dirs):
    out = cf_dirs["tmp"] / "texts.jsonl"
    build_texts(cf_dirs, out)
    summary = json.loads(fvt.summary_path(out).read_text(encoding="utf-8"))
    rows = {c["chunk_id"]: c for c in summary["chunks"]}
    assert rows["aaa"]["tags"] == 2
    assert rows["aaa"]["texts"] == {"main": 5, "repeat": 1}
    assert rows["aaa"]["recon_fail"] == {"main": 1, "repeat": 0}
    assert rows["bbb"]["texts"] == {"main": 1, "repeat": 0}


def test_read_texts_refuses_a_line_whose_sha_is_wrong(cf_dirs):
    out = cf_dirs["tmp"] / "texts.jsonl"
    build_texts(cf_dirs, out)
    lines = out.read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[1])
    row["text"] += " tampered"
    lines[1] = json.dumps(row)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        fvt.read_texts(out)


# ------------------------------------------------------------------ the prompt and the message

def test_the_prompt_default_falls_back_to_the_draft():
    path = fv.prompt_path("chunk")
    assert path.name in ("facet_views_chunk.txt", "facet_views_chunk.v1.txt")
    assert fv.prompt_sha(fv.prompt_text(path)) != fv.prompt_sha(
        fv.prompt_text(fv.prompt_path("edge")))


def test_an_unknown_variant_is_refused():
    with pytest.raises(SystemExit):
        fv.prompt_path("sentence")


def test_chunk_user_message_is_the_text_alone():
    msg = fv.user_message(ORIGINAL_A + "\n\n")
    assert msg == f"Text:\n{ORIGINAL_A}"


def test_edge_user_message_carries_the_text_and_every_phrase():
    msg = fv.user_message(ORIGINAL_A, TAGS_A)
    assert msg.startswith(f"Text:\n{ORIGINAL_A}")
    assert msg.endswith("\n\nPhrases:\n- database migration\n- security review")


# ------------------------------------------------------------------ the payload

def chunk_payload(**over):
    payload = {f: f"the {f} view" for f in fv.CHUNK_FIELDS}
    payload.update(over)
    return payload


def edge_payload(tags=TAGS_A):
    return {"edges": [{"t": t, **{f: f"{t} {f}" for f in fv.EDGE_FIELDS}} for t in tags]}


def test_chunk_parse_takes_the_five_strings():
    out = fv.parse_chunk_views(chunk_payload())
    assert list(out) == list(fv.CHUNK_FIELDS)
    assert out["description"] == "the description view"


def test_chunk_parse_refuses_a_missing_or_empty_field():
    bad = chunk_payload()
    del bad["why"]
    with pytest.raises(ValueError):
        fv.parse_chunk_views(bad)
    with pytest.raises(ValueError):
        fv.parse_chunk_views(chunk_payload(activity="   "))
    with pytest.raises(ValueError):
        fv.parse_chunk_views(chunk_payload(temporal=3))


def test_edge_parse_takes_a_row_per_phrase():
    rows, problems = fv.parse_edge_views(edge_payload(), TAGS_A)
    assert problems == []
    assert [r["t"] for r in rows] == TAGS_A
    assert rows[0]["temporal"] == "database migration temporal"


def test_edge_parse_leaves_an_unanswered_phrase_out():
    rows, _ = fv.parse_edge_views(edge_payload(["database migration"]), TAGS_A)
    assert [r["t"] for r in rows] == ["database migration"]


def test_edge_parse_drops_a_row_with_a_missing_field_and_names_it():
    payload = edge_payload()
    del payload["edges"][0]["activity"]
    rows, problems = fv.parse_edge_views(payload, TAGS_A)
    assert [r["t"] for r in rows] == ["security review"]
    assert any("activity" in p for p in problems)


# ------------------------------------------------------------------ resume

def write_view_file(tmp_path, variant, write, sha, **over):
    rec = {"sha": sha, "chunk_id": "aaa", "variant": variant, "write": write,
           "prompt_sha256": "p", "model": "m"}
    if variant == "chunk":
        rec["views"] = dict(chunk_payload())
    else:
        rows, _ = fv.parse_edge_views(edge_payload(), TAGS_A)
        rec.update({"tags": TAGS_A, "given": len(TAGS_A), "answered": len(TAGS_A),
                    "complete": True, "views": rows})
    rec.update(over)
    path = fv.view_path(tmp_path, variant, write, sha)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    return path


def test_status_of_a_finished_chunk_file(tmp_path):
    path = write_view_file(tmp_path, "chunk", 1, "s" * 64)
    assert fv.status_of(path, "p", "chunk") == "done"
    assert fv.status_of(path, "other", "chunk") == "prompt_mismatch"


def test_status_of_a_chunk_file_missing_a_view(tmp_path):
    views = dict(chunk_payload())
    del views["concreteness"]
    path = write_view_file(tmp_path, "chunk", 1, "s" * 64, views=views)
    assert fv.status_of(path, "p", "chunk") == "incomplete"


def test_status_of_a_finished_and_a_half_answered_edge_file(tmp_path):
    path = write_view_file(tmp_path, "edge", 1, "e" * 64)
    assert fv.status_of(path, "p", "edge") == "done"
    path = write_view_file(tmp_path, "edge", 2, "e" * 64, answered=1, complete=False)
    assert fv.status_of(path, "p", "edge") == "incomplete"


def test_status_of_a_missing_or_broken_file(tmp_path):
    assert fv.status_of(tmp_path / "nope.json", None, "chunk") == "missing"
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert fv.status_of(bad, None, "chunk") == "unreadable"


def test_a_failed_marker_sits_beside_the_view_file(tmp_path):
    assert (fv.failed_path(tmp_path, "chunk", 1, "s" * 64).parent
            == fv.view_path(tmp_path, "chunk", 1, "s" * 64).parent)
    assert fv.failed_path(tmp_path, "chunk", 1, "abc").name == "abc.failed.json"
    assert fv.run_dir(tmp_path, "edge", 2).as_posix().endswith("edge/w2")


# ------------------------------------------------------------------ the shard

def test_the_shards_partition_every_sha_exactly_once(cf_dirs):
    _header, rows = build_texts(cf_dirs)
    shas = [r["sha"] for r in rows]
    for n in (2, 3, 8):
        taken = [s for k in range(n) for s in shas if fv.in_shard(s, k, n)]
        assert sorted(taken) == sorted(shas)


def test_the_shard_rule_does_not_depend_on_the_variant_or_the_write():
    sha = fvt.sha256_of("some text")
    assert fv.shard_of(sha, 2) == fv.shard_of(sha, 2)
    assert 0 <= fv.shard_of(sha, 2) < 2


# ------------------------------------------------------------------ the run, lane mocked

class FakeLane:
    """`chat.post` with a scripted reply per call; no model is ever called."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.users = []

    def __call__(self, _path, payload, **_kw):
        self.users.append(payload["messages"][1]["content"])
        content = self.replies.pop(0)
        if isinstance(content, Exception):
            raise content
        return {"choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7}}


def run_one(monkeypatch, tmp_path, variant, replies, row):
    from harness import chat
    lane = FakeLane(replies)
    monkeypatch.setattr(chat, "post", lane)
    state = fa.State(total=1, done=0)
    fv.write_views(row, tmp_path, variant, 1, "system", "p", "claude-haiku-4-5", state)
    return lane, state


def a_row(sha=None, tags=TAGS_A):
    return {"sha": sha or fvt.sha256_of(ORIGINAL_A), "text": ORIGINAL_A, "chunk_id": "aaa",
            "kind": "slack_thread", "product": "FlowForce", "tags": list(tags),
            "origins": [{"generation": "original"}]}


def test_a_chunk_text_is_one_call_and_five_views(monkeypatch, tmp_path):
    row = a_row()
    lane, state = run_one(monkeypatch, tmp_path, "chunk",
                          [json.dumps(chunk_payload())], row)
    assert len(lane.users) == 1 and lane.users[0] == f"Text:\n{ORIGINAL_A}"
    assert state.done == 1 and state.calls == 1
    rec = json.loads(fv.view_path(tmp_path, "chunk", 1, row["sha"]).read_text(encoding="utf-8"))
    assert list(rec["views"]) == list(fv.CHUNK_FIELDS)
    assert rec["usage"] == {"tokens_in": 11, "tokens_out": 7}
    assert rec["variant"] == "chunk" and rec["write"] == 1
    assert rec["origins"] == row["origins"] and rec["prompt_sha256"] == "p"
    assert fv.status_of(fv.view_path(tmp_path, "chunk", 1, row["sha"]), "p", "chunk") == "done"


def test_a_payload_that_does_not_parse_is_asked_once_more_then_recorded(monkeypatch, tmp_path):
    row = a_row()
    lane, state = run_one(monkeypatch, tmp_path, "chunk", ["not json", "still not json"], row)
    assert len(lane.users) == fa.PARSE_TRIES
    assert state.done == 0 and state.failures == 1
    assert fv.failed_path(tmp_path, "chunk", 1, row["sha"]).is_file()
    assert not fv.view_path(tmp_path, "chunk", 1, row["sha"]).is_file()


def test_an_edge_text_asks_the_unanswered_phrases_once_more(monkeypatch, tmp_path):
    row = a_row()
    lane, state = run_one(monkeypatch, tmp_path, "edge",
                          [json.dumps(edge_payload(["database migration"])),
                           json.dumps(edge_payload(["security review"]))], row)
    assert len(lane.users) == fa.ASK_ROUNDS
    assert "- security review" in lane.users[1] and "- database migration" not in lane.users[1]
    rec = json.loads(fv.view_path(tmp_path, "edge", 1, row["sha"]).read_text(encoding="utf-8"))
    assert rec["given"] == 2 and rec["answered"] == 2 and rec["complete"] is True
    assert [r["t"] for r in rec["views"]] == TAGS_A
    assert state.done == 1


def test_an_edge_text_left_incomplete_is_written_and_marked(monkeypatch, tmp_path):
    row = a_row()
    reply = json.dumps(edge_payload(["database migration"]))
    _lane, state = run_one(monkeypatch, tmp_path, "edge", [reply, reply], row)
    assert state.done == 0 and state.incomplete == 1
    path = fv.view_path(tmp_path, "edge", 1, row["sha"])
    assert fv.status_of(path, "p", "edge") == "incomplete"
    assert fv.failed_path(tmp_path, "edge", 1, row["sha"]).is_file()


# ------------------------------------------------------------------ merge

def test_merge_copies_a_new_file_and_counts_a_duplicate(tmp_path):
    here, there = tmp_path / "here", tmp_path / "there"
    write_view_file(here, "chunk", 1, "a" * 64)
    write_view_file(there, "chunk", 1, "a" * 64)
    write_view_file(there, "chunk", 1, "b" * 64)
    result = fv.merge(here, "chunk", 1, fv.run_dir(there, "chunk", 1), "p")
    assert result == {"copied": 1, "duplicates": 1, "conflicts": 0, "skipped": 0}
    assert fv.view_path(here, "chunk", 1, "b" * 64).is_file()


def test_merge_counts_a_conflict_and_keeps_what_is_here(tmp_path):
    here, there = tmp_path / "here", tmp_path / "there"
    write_view_file(here, "chunk", 1, "a" * 64)
    write_view_file(there, "chunk", 1, "a" * 64,
                    views=dict(chunk_payload(description="another reading")))
    result = fv.merge(here, "chunk", 1, fv.run_dir(there, "chunk", 1), "p")
    assert result["conflicts"] == 1 and result["copied"] == 0
    kept = json.loads(fv.view_path(here, "chunk", 1, "a" * 64).read_text(encoding="utf-8"))
    assert kept["views"]["description"] == "the description view"


def test_merge_refuses_a_file_written_under_another_prompt(tmp_path):
    here, there = tmp_path / "here", tmp_path / "there"
    write_view_file(there, "chunk", 1, "a" * 64, prompt_sha256="other")
    with pytest.raises(SystemExit):
        fv.merge(here, "chunk", 1, fv.run_dir(there, "chunk", 1), "p")


# ------------------------------------------------------------------ the strings

def test_collect_strings_takes_every_view_and_every_phrase(tmp_path):
    out = tmp_path / "views"
    write_view_file(out, "chunk", 1, "a" * 64)
    write_view_file(out, "edge", 1, "a" * 64)
    rows = [{"sha": "a" * 64, "text": ORIGINAL_A, "tags": TAGS_A}]
    target = tmp_path / "strings.jsonl"
    result = fv.collect_strings(out, rows, target)
    lines = [json.loads(line) for line in
             target.read_text(encoding="utf-8").splitlines() if line.strip()]
    texts = [line["text"] for line in lines]
    assert result["strings"] == len(lines) == len(set(texts))
    assert "the description view" in texts
    assert "database migration temporal" in texts
    assert set(TAGS_A) <= set(texts)
    assert {(r["variant"], r["write"]) for r in result["runs"]} == {("chunk", "w1"),
                                                                   ("edge", "w1")}
    assert all(r["nothing_lines"] == 0 for r in result["runs"])


def test_every_collected_line_carries_the_sha_of_its_own_text(tmp_path):
    out = tmp_path / "views"
    write_view_file(out, "chunk", 1, "a" * 64)
    target = tmp_path / "strings.jsonl"
    fv.collect_strings(out, [{"tags": TAGS_A}], target)
    for line in target.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        assert fvt.sha256_of(row["text"]) == row["sha"]


def test_collect_strings_skips_an_unfinished_file(tmp_path):
    out = tmp_path / "views"
    views = dict(chunk_payload())
    del views["why"]
    write_view_file(out, "chunk", 1, "a" * 64, views=views)
    result = fv.collect_strings(out, [], tmp_path / "strings.jsonl")
    assert result["strings"] == 0
    assert result["runs"] == [{"variant": "chunk", "write": "w1", "files": 0, "strings": 0,
                               "nothing_lines": 0}]


# ------------------------------------------------------------------ the plan

def test_the_dry_run_prints_a_plan_and_calls_nothing(monkeypatch, capsys, cf_dirs):
    from harness import chat
    monkeypatch.setattr(chat, "post", lambda *a, **k: pytest.fail("the lane was called"))
    out = cf_dirs["tmp"] / "texts.jsonl"
    build_texts(cf_dirs, out)
    capsys.readouterr()
    fv.main(["--texts", str(out), "--variant", "edge", "--write", "1",
             "--out", str(cf_dirs["tmp"] / "views"), "--dry-run"])
    printed = capsys.readouterr().out
    assert "two-machine split" in printed
    assert "cost estimate" in printed and "tokens in" in printed


def test_the_cost_estimate_rests_on_the_stated_figures():
    rows = [{"tags": ["a", "b"]}, {"tags": ["c"]}]
    chunk = "\n".join(fv.cost_lines(rows, "chunk"))
    assert f"{2 * fv.REASK_FACTOR * fv.TOKENS_OUT_CHUNK:,.0f}" in chunk
    edge = "\n".join(fv.cost_lines(rows, "edge"))
    assert f"{3 * fv.REASK_FACTOR * fv.TOKENS_OUT_PER_PHRASE:,.0f}" in edge
    assert f"{fv.TOKENS_IN_PER_CALL:,}" in edge


# ------------------------------------------------------------------ the absence line

def test_the_absence_line_is_an_ordinary_view_and_is_counted(monkeypatch, tmp_path):
    row = a_row()
    payload = chunk_payload(why=fv.NOTHING_LINE, activity=f"  {fv.NOTHING_LINE}  ")
    _lane, state = run_one(monkeypatch, tmp_path, "chunk", [json.dumps(payload)], row)
    path = fv.view_path(tmp_path, "chunk", 1, row["sha"])
    rec = json.loads(path.read_text(encoding="utf-8"))
    assert rec["nothing_lines"] == 2
    assert rec["views"]["why"] == fv.NOTHING_LINE
    assert fv.status_of(path, "p", "chunk") == "done"
    assert state.nothing_lines == 2


def test_the_absence_line_is_collected_like_any_other_string(tmp_path):
    out = tmp_path / "views"
    write_view_file(out, "chunk", 1, "a" * 64,
                    views=dict(chunk_payload(why=fv.NOTHING_LINE)))
    target = tmp_path / "strings.jsonl"
    result = fv.collect_strings(out, [], target)
    texts = [json.loads(line)["text"] for line in
             target.read_text(encoding="utf-8").splitlines()]
    assert fv.NOTHING_LINE in texts
    assert result["runs"][0]["nothing_lines"] == 1


def test_nothing_lines_counts_only_the_exact_line():
    padded = " " + fv.NOTHING_LINE + "  "
    assert fv.nothing_lines([fv.NOTHING_LINE, padded]) == 2
    assert fv.nothing_lines(["The text gives nothing here", "nothing here"]) == 0


# ------------------------------------------------------------------ the call

def test_the_call_joins_a_reply_that_spans_two_messages(monkeypatch, tmp_path):
    """A long edge reply runs past one CLI message; without `join_parts` the envelope carries
    only the tail and the payload arrives beginning mid-object."""
    from harness import chat
    seen = {}

    def fake_post(_path, payload, **_kw):
        seen.update(payload)
        return {"choices": [{"message": {"content": json.dumps(edge_payload())}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1}}

    monkeypatch.setattr(chat, "post", fake_post)
    fv.call_once("system", "user", "claude-haiku-4-5")
    assert seen["join_parts"] is True
    assert seen["temperature"] == 0 and seen["model"] == "claude-haiku-4-5"
    assert "effort" not in seen


# ------------------------------------------------------------------ the chunk keys

def test_the_five_chunk_keys_are_read_case_strictly():
    payload = chunk_payload()
    payload["Why"] = payload.pop("why")
    with pytest.raises(ValueError) as err:
        fv.parse_chunk_views(payload)
    assert "why" in str(err.value)

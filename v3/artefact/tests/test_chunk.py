"""Golden tests for the deterministic chunker (design §9, §16): pure functions,
no LLM, so they run on every edit."""

from artefact.chunk import (
    Ref,
    chunk_file,
    expand,
    split_prose,
    _get,
    _segment,
)

KEY = {
    "content": [
        "/slack/*/Message/User/text",
        "/prs/*/summary",
        "/prs/*/reviews/*/comment",
        "/documents/*/content",
        "/meeting_transcripts/*/transcript",
        "/urls/*/description",
    ],
    "conversation": [
        {"collection": "/slack", "channel": "/Channel/channelID", "timestamp": "/Message/User/timestamp"}
    ],
}

# the probe-derived prose classification (typical-length leaves): documents and
# transcripts are prose; prs/urls/slack are not.
PROSE_LEAVES = frozenset({"/documents/*/content", "/meeting_transcripts/*/transcript"})

IDENT = {"file_id": "fid", "relpath": "p.json", "sha256": "sha"}


def _slack_msg(channel, ts, text):
    return {"Channel": {"channelID": channel}, "Message": {"User": {"timestamp": ts, "text": text}}}


def _resolve(data, ref: Ref) -> str:
    if ref.scheme == "json_pointer":
        return _get(data, ref.address)
    ptr, s, e = ref.address
    return _get(data, ptr)[s:e]


# ---------- expand ----------

def test_expand_wildcard_and_missing_optional():
    data = {"prs": [{"summary": "a"}, {"notsummary": "x"}, {"summary": "c"}]}
    got = list(expand(data, "/prs/*/summary"))
    assert got == ["/prs/0/summary", "/prs/2/summary"]  # index 1 has no summary -> skipped


def test_expand_nested_wildcard():
    data = {"prs": [{"reviews": [{"comment": "a"}, {"comment": "b"}]}]}
    assert list(expand(data, "/prs/*/reviews/*/comment")) == [
        "/prs/0/reviews/0/comment",
        "/prs/0/reviews/1/comment",
    ]


# ---------- prose splitting ----------

def test_split_prose_tiles_exactly_under_cap():
    text = "para one.\n\npara two.\n\npara three."
    spans = split_prose(text, 12)
    assert spans[0][0] == 0 and spans[-1][1] == len(text)
    for s, e in spans:
        assert e > s and (e - s) <= 12
    assert "".join(text[s:e] for s, e in spans) == text  # contiguous, lossless


def test_split_prose_cuts_on_sentence_when_no_paragraph():
    text = "Alpha sentence. Beta sentence. Gamma sentence."
    spans = split_prose(text, 20)
    # every span ends at a sentence boundary or end-of-text, never mid-word past the cap
    assert all(text[e - 1] in ".\n " or e == len(text) for s, e in spans)


# ---------- conversation segmentation ----------

def test_segment_splits_on_large_gap():
    mk = lambda i, ts: (i, "c", _dt(ts), [])
    stream = [mk(0, "T10:00:00"), mk(1, "T10:01:00"), mk(2, "T13:00:00"), mk(3, "T13:01:00")]
    episodes = _segment(stream)
    assert len(episodes) == 2 and [len(e) for e in episodes] == [2, 2]


def test_segment_splits_on_day_boundary():
    from artefact.chunk import _segment as seg
    stream = [(0, "c", _dt("T23:59:00"), []), (1, "c", _dt("T00:01:00", day=11), [])]
    assert len(seg(stream)) == 2


def _dt(t, day=10):
    from datetime import datetime
    return datetime.fromisoformat(f"2026-06-{day:02d}{t}")


# ---------- conversation chunking ----------

def test_conversation_groups_by_channel_and_episode():
    data = {"slack": [
        _slack_msg("chA", "2026-06-10T10:00:00", "a1"),
        _slack_msg("chA", "2026-06-10T10:01:00", "a2"),
        _slack_msg("chB", "2026-06-10T10:00:00", "b1"),
    ]}
    chunks = chunk_file(data, key=KEY, prose_leaves=PROSE_LEAVES, **IDENT)
    assert all(c.kind == "conversation" for c in chunks)
    # two channels -> at least two chunks; chA's two messages coalesce (no gap)
    paths = sorted(c.path for c in chunks)
    assert paths == [(0, 0, 0), (0, 1, 0)]
    cha = next(c for c in chunks if c.path == (0, 0, 0))
    assert [_resolve(data, r) for r in cha.refs] == ["a1", "a2"]


def test_conversation_cap_split_at_largest_gap():
    # one channel, one day, four messages with an increasing gap before #2: an
    # over-cap episode splits at the LARGEST internal gap, not the nearest.
    msgs = [
        _slack_msg("c", "2026-06-10T10:00:00", "x" * 600),
        _slack_msg("c", "2026-06-10T10:00:30", "x" * 600),  # +30s
        _slack_msg("c", "2026-06-10T10:10:00", "x" * 600),  # +9.5min — biggest gap
        _slack_msg("c", "2026-06-10T10:10:30", "x" * 600),  # +30s
    ]
    chunks = chunk_file({"slack": msgs}, key=KEY, prose_leaves=PROSE_LEAVES, cap_tokens=400, **IDENT)
    assert len(chunks) == 2
    sizes = [len(c.refs) for c in sorted(chunks, key=lambda c: c.path)]
    assert sizes == [2, 2]  # cut before message #2 (the largest gap), not elsewhere
    assert all(c.kind == "conversation" for c in chunks)


def test_whitespace_only_content_is_kept_not_silently_dropped():
    # a whitespace-only declared content leaf stays (no silent fallback): it is
    # referenced AND its timestamp still participates in segmentation
    data = {"slack": [
        _slack_msg("c", "2026-06-10T10:00:00", "real one"),
        _slack_msg("c", "2026-06-10T10:00:30", "   "),       # whitespace-only — kept
        _slack_msg("c", "2026-06-10T10:01:00", "real two"),
    ]}
    chunks = chunk_file(data, key=KEY, prose_leaves=PROSE_LEAVES, cap_tokens=1000, **IDENT)
    texts = [_resolve(data, r) for c in chunks for r in c.refs]
    assert texts == ["real one", "   ", "real two"]   # the whitespace message survives, in order


# ---------- prose-leaf records: one chunk per record, never merged ----------

def test_prose_records_stay_one_per_record():
    # three sibling documents, each tiny — they must remain THREE chunks, never
    # packed together (a document is a coherent unit; merging corrupts the facets)
    data = {"documents": [{"content": "doc one"}, {"content": "doc two"}, {"content": "doc three"}]}
    chunks = chunk_file(data, key=KEY, prose_leaves=PROSE_LEAVES, cap_tokens=10000, **IDENT)
    assert len(chunks) == 3
    assert all(c.kind == "prose" for c in chunks)
    assert sorted(c.path for c in chunks) == [(0, 0), (0, 1), (0, 2)]
    assert [_resolve(data, c.refs[0]) for c in sorted(chunks, key=lambda c: c.path)] == [
        "doc one", "doc two", "doc three",
    ]


def test_prose_record_over_cap_splits_and_char_spans_tile_the_leaf():
    big = "x" * 400 + ". " + "y" * 400  # ~200 est-tokens, over a tiny cap
    data = {"documents": [{"content": big}]}
    chunks = chunk_file(data, key=KEY, prose_leaves=PROSE_LEAVES, cap_tokens=50, **IDENT)
    assert len(chunks) > 1
    assert all(c.kind == "prose" and c.est_tokens <= 50 for c in chunks)
    # the over-cap leaf's char spans tile it EXACTLY: resolving them in order
    # reproduces that leaf (the per-leaf lossless guarantee)
    assert "".join(_resolve(data, r) for c in chunks for r in c.refs) == big
    assert all(c.path[:2] == (0, 0) for c in chunks)  # fragments share the record prefix


# ---------- short structured records: pack consecutive, break at the cap ----------

def test_short_records_pack_consecutive_into_one_chunk():
    # many tiny prs records pack into ONE chunk (design §9.4), not one micro-chunk each
    data = {"prs": [{"summary": f"s{i}"} for i in range(5)]}
    chunks = chunk_file(data, key=KEY, prose_leaves=PROSE_LEAVES, cap_tokens=50, **IDENT)
    assert len(chunks) == 1
    assert chunks[0].kind == "record"
    assert chunks[0].path == (0, 0)  # anchored at the run's first record
    assert [_resolve(data, r) for r in chunks[0].refs] == ["s0", "s1", "s2", "s3", "s4"]


def test_short_records_break_at_cap_referencing_every_record_once():
    txt = "word " * 24  # ~30 est-tokens each
    data = {"prs": [{"summary": txt} for _ in range(4)]}
    chunks = chunk_file(data, key=KEY, prose_leaves=PROSE_LEAVES, cap_tokens=70, **IDENT)
    assert len(chunks) > 1 and all(c.kind == "record" and c.est_tokens <= 70 for c in chunks)
    assert [_resolve(data, r) for c in chunks for r in c.refs] == [txt] * 4  # every record once, in order


def test_short_record_single_record_keeps_its_leaves_together():
    data = {"prs": [{"summary": "the summary", "reviews": [{"comment": "lgtm"}, {"comment": "nit"}]}]}
    chunks = chunk_file(data, key=KEY, prose_leaves=PROSE_LEAVES, **IDENT)
    assert len(chunks) == 1
    c = chunks[0]
    assert c.kind == "record" and c.path == (0, 0)
    assert [_resolve(data, r) for r in c.refs] == ["the summary", "lgtm", "nit"]


# ---------- per-position dispatch in one mixed file ----------

def test_mixed_file_dispatches_each_collection_by_kind():
    # one file with a conversation + a prose-record + a short-record collection —
    # each handled by its own kind, decided per position not per file
    data = {
        "slack": [
            _slack_msg("c", "2026-06-10T10:00:00", "hi"),
            _slack_msg("c", "2026-06-10T10:00:30", "there"),
        ],
        "documents": [{"content": "long-form doc A"}, {"content": "long-form doc B"}],
        "urls": [{"description": "u0"}, {"description": "u1"}, {"description": "u2"}],
    }
    chunks = chunk_file(data, key=KEY, prose_leaves=PROSE_LEAVES, cap_tokens=1000, **IDENT)
    by_kind = {}
    for c in chunks:
        by_kind.setdefault(c.kind, []).append(c)
    assert set(by_kind) == {"conversation", "prose", "record"}
    assert len(by_kind["conversation"]) == 1          # one channel, one episode
    assert len(by_kind["prose"]) == 2                 # two documents, never merged
    assert len(by_kind["record"]) == 1                # three urls packed into one


# ---------- references-not-copies: refs resolve into the untouched raw ----------

def test_references_resolve_into_raw_content_leaves():
    data = {
        "documents": [{"content": "alpha beta gamma"}],
        "prs": [{"summary": "p0"}, {"summary": "p1"}],
    }
    chunks = chunk_file(data, key=KEY, prose_leaves=PROSE_LEAVES, cap_tokens=1000, **IDENT)
    # every chunk's references resolve back to a content leaf in the raw
    for c in chunks:
        for r in c.refs:
            assert isinstance(_resolve(data, r), str)
    doc_chunk = next(c for c in chunks if c.kind == "prose")
    assert _resolve(data, doc_chunk.refs[0]) == "alpha beta gamma"


# ---------- directory file is inert ----------

def test_directory_file_yields_no_chunks():
    # a metadata/id-directory file has no content pointers -> no chunks (safe over a dataset)
    assert chunk_file({"eid_1": {"name": "x"}}, key=KEY, prose_leaves=PROSE_LEAVES, **IDENT) == []

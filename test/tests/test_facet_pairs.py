import json
import random

import pytest

from graph import facet_pairs_control as fpc
from graph import facet_pairs_judge as fpj
from graph import facet_pairs_select as fps


# ------------------------------------------------------------------ a synthetic corpus

def make_corpus(tmp_path, n_chunks=120, tags_per_chunk=6, n_tags=40, seed=7):
    """A rows export and a facet_stats file with the shape the real ones have."""
    rng = random.Random(seed)
    vocab = [f"tag {i}" for i in range(n_tags)]
    rows_path = tmp_path / "rows_export.jsonl"
    stats_path = tmp_path / "stats.jsonl"
    with open(rows_path, "w", encoding="utf-8") as rf, \
            open(stats_path, "w", encoding="utf-8") as sf:
        rf.write(json.dumps({"header": {"db": "test", "n_chunks": n_chunks}}) + "\n")
        for c in range(n_chunks):
            chunk_id = f"chunk{c:04d}"
            tags = rng.sample(vocab, tags_per_chunk)
            rf.write(json.dumps({"chunk_id": chunk_id, "kind": "document",
                                 "product": "P", "tags": tags,
                                 "text": f"text of {chunk_id}. " * 5}) + "\n")
            for t in tags:
                sf.write(json.dumps({"chunk_id": chunk_id, "tag": t,
                                     "topic": rng.random()}) + "\n")
    return rows_path, stats_path


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    rows_path, stats_path = make_corpus(tmp_path)
    # the real build asserts the real corpus's counts; the synthetic one is its own size
    monkeypatch.setattr(fps, "CANDIDATES", 4000)
    return rows_path, stats_path


def small(tmp_path, corpus, seed, frac=0.25):
    """The production `build`, on the synthetic corpus, with the corpus-size guard off."""
    rows_path, stats_path = corpus
    out = tmp_path / "pairs"
    meta = fps.build(out, stats_path, rows_path, seed, frac, expect=None)
    return out, meta


@pytest.fixture
def built(tmp_path, corpus, monkeypatch):
    monkeypatch.setattr(fps, "CONTROL_N", {"cross": 24, "same_tag": 8, "same_chunk": 8})
    monkeypatch.setattr(fps, "CONTROL_REPEATS", 12)
    monkeypatch.setattr(fps, "HELDOUT_N", 40)
    monkeypatch.setattr(fps, "HELDOUT_REPEATS", 16)
    monkeypatch.setattr(fps, "TRAIN_N", 32)
    return small(tmp_path, corpus, 5)


def read(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


# ------------------------------------------------------------------ the split

def test_split_is_deterministic_and_disjoint():
    ids = [f"chunk{i}" for i in range(2000)]
    first = {i for i in ids if fps.held_out(i)}
    second = {i for i in ids if fps.held_out(i)}
    assert first == second
    assert 0.10 < len(first) / len(ids) < 0.20


# ------------------------------------------------------------------ selection

def test_counts_and_mix(built):
    out, meta = built
    control = read(out / "control.jsonl")
    heldout = read(out / "heldout.jsonl")
    train = read(out / "train_round0.jsonl")
    assert len({r["pair_id"] for r in control}) == 40
    assert len({r["pair_id"] for r in heldout}) == 40
    assert len({r["pair_id"] for r in train}) == 32
    types = {}
    for r in heldout:
        types.setdefault(r["pair_type"], set()).add(r["pair_id"])
    assert len(types["cross"]) == 20
    assert len(types["same_tag"]) == 10
    assert len(types["same_chunk"]) == 10


def test_heldout_is_chunk_disjoint(built):
    out, _ = built
    hold = {r[s]["chunk_id"] for r in read(out / "heldout.jsonl") for s in ("a", "b")}
    other = {r[s]["chunk_id"]
             for f in ("control.jsonl", "train_round0.jsonl")
             for r in read(out / f) for s in ("a", "b")}
    assert hold and other
    assert not (hold & other)


def test_control_has_both_orders_and_identical_repeats(built):
    out, _ = built
    rows = read(out / "control.jsonl")
    by_pair = {}
    for r in rows:
        by_pair.setdefault(r["pair_id"], []).append(r)
    for pid, group in by_pair.items():
        orders = sorted((r["order"], r["repeat"]) for r in group)
        assert ("AB", 1) in orders and ("BA", 1) in orders
        ab = [r for r in group if r["order"] == "AB"]
        if len(ab) == 2:
            assert ab[0]["a"] == ab[1]["a"] and ab[0]["b"] == ab[1]["b"]
            assert {r["repeat"] for r in ab} == {1, 2}
    assert sum(1 for r in rows if r["repeat"] == 2) == 12


def test_heldout_repeats_carry_the_same_order(built):
    out, _ = built
    rows = read(out / "heldout.jsonl")
    by_pair = {}
    for r in rows:
        by_pair.setdefault(r["pair_id"], []).append(r)
    repeated = [g for g in by_pair.values() if len(g) == 2]
    assert len(repeated) == 16
    for g in repeated:
        assert g[0]["order"] == g[1]["order"]
        assert g[0]["a"] == g[1]["a"] and g[0]["b"] == g[1]["b"]


def test_pair_types_hold(built):
    out, _ = built
    for f in ("control.jsonl", "heldout.jsonl", "train_round0.jsonl"):
        for r in read(out / f):
            a, b = r["a"], r["b"]
            assert a["edge_id"] != b["edge_id"]
            if r["pair_type"] == "same_tag":
                assert a["tag"] == b["tag"] and a["chunk_id"] != b["chunk_id"]
            elif r["pair_type"] == "same_chunk":
                assert a["chunk_id"] == b["chunk_id"] and a["tag"] != b["tag"]
            else:
                assert a["chunk_id"] != b["chunk_id"] and a["tag"] != b["tag"]


def test_no_pair_twice_across_the_files(built):
    out, _ = built
    seen = set()
    for f in ("control.jsonl", "heldout.jsonl", "train_round0.jsonl"):
        ids = {r["pair_id"] for r in read(out / f)}
        assert not (ids & seen)
        seen |= ids


def test_pair_rows_carry_no_topic(built):
    out, _ = built
    for f in ("control.jsonl", "heldout.jsonl", "train_round0.jsonl"):
        text = (out / f).read_text(encoding="utf-8")
        assert "topic" not in text
        for r in read(out / f):
            assert set(r["a"]) == {"edge_id", "chunk_id", "tag"}
            assert set(r["b"]) == {"edge_id", "chunk_id", "tag"}
    key = read(out / "topic_key.jsonl")
    assert all("topic" in k["first"] for k in key)


def test_determinism(tmp_path, corpus, monkeypatch):
    monkeypatch.setattr(fps, "CONTROL_N", {"cross": 12, "same_tag": 4, "same_chunk": 4})
    monkeypatch.setattr(fps, "CONTROL_REPEATS", 8)
    monkeypatch.setattr(fps, "HELDOUT_N", 20)
    monkeypatch.setattr(fps, "HELDOUT_REPEATS", 8)
    monkeypatch.setattr(fps, "TRAIN_N", 16)
    rows_path, stats_path = corpus
    a = tmp_path / "a"
    b = tmp_path / "b"
    fps.build(a, stats_path, rows_path, 11, 0.25, expect=None)
    fps.build(b, stats_path, rows_path, 11, 0.25, expect=None)
    for f in ("control.jsonl", "heldout.jsonl", "train_round0.jsonl"):
        assert (a / f).read_text(encoding="utf-8") == (b / f).read_text(encoding="utf-8")


def test_row_of_presents_BA_reversed(built):
    out, _ = built
    rows = read(out / "control.jsonl")
    by_pair = {}
    for r in rows:
        by_pair.setdefault(r["pair_id"], {})[r["order"]] = r
    for pid, g in by_pair.items():
        assert g["AB"]["a"] == g["BA"]["b"]
        assert g["AB"]["b"] == g["BA"]["a"]


# ------------------------------------------------------------------ the judge's payload

def test_parse_choices_valid():
    out = fpj.parse_choices({"topic": "A", "temporal": "B", "why": "equal",
                             "activity": "A", "concreteness": "B"})
    assert out["why"] == "equal"


@pytest.mark.parametrize("payload", [
    {"topic": "a", "temporal": "B", "why": "equal", "activity": "A", "concreteness": "B"},
    {"topic": "A", "temporal": "B", "why": "EQUAL", "activity": "A", "concreteness": "B"},
    {"topic": "A", "temporal": "B", "why": "equal", "activity": "A"},
    {"topic": "A", "temporal": "B", "why": "equal", "activity": "A", "concreteness": "either"},
    {"Topic": "A", "temporal": "B", "why": "equal", "activity": "A", "concreteness": "B"},
])
def test_parse_choices_refuses(payload):
    with pytest.raises(ValueError):
        fpj.parse_choices(payload)


def test_extract_json_tolerates_prose():
    from graph import facet_answers as fa
    raw = ('Here is my judgement.\n```json\n{"topic":"A","temporal":"equal","why":"B",'
           '"activity":"A","concreteness":"equal"}\n```\nThat is all.')
    assert fpj.parse_choices(fa.extract_json(raw))["why"] == "B"


def test_canonical_mapping():
    answers = {"topic": "A", "temporal": "B", "why": "equal"}
    assert fpj.canonical(answers, "AB") == {"topic": "first", "temporal": "second",
                                            "why": "equal"}
    assert fpj.canonical(answers, "BA") == {"topic": "second", "temporal": "first",
                                            "why": "equal"}


def test_user_message_shape():
    msg = fpj.user_message("alpha", "text one\n\n", "beta", "text two  ")
    assert msg == ("Relationship A\nPhrase A: alpha\nText A:\ntext one\n\n"
                   "Relationship B\nPhrase B: beta\nText B:\ntext two")


def test_runner_never_reads_the_topic_key():
    src = (fpj.__file__).replace(".pyc", ".py")
    text = open(src, encoding="utf-8").read()
    assert "topic_key" not in text


# ------------------------------------------------------------------ resume

def full_record(row_id="r1", set_name="control", sha="p", answers=None):
    answers = answers or {f: "A" for f in fpj.FACETS}
    return {"row_id": row_id, "set": set_name, "order": "AB", "repeat": 1,
            "pair_id": "p1", "pair_type": "cross",
            "a": {"edge_id": "c1::t1", "chunk_id": "c1", "tag": "t1"},
            "b": {"edge_id": "c2::t2", "chunk_id": "c2", "tag": "t2"},
            "answers": answers, "answers_canonical": fpj.canonical(answers, "AB"),
            "prompt_sha256": sha}


def test_status_of(tmp_path):
    p = tmp_path / "control" / "r1.json"
    assert fpj.status_of(p, "p") == "missing"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(full_record()), encoding="utf-8")
    assert fpj.status_of(p, "p") == "done"
    assert fpj.status_of(p, "other") == "prompt_mismatch"
    bad = full_record()
    bad["answers"]["topic"] = "maybe"
    p.write_text(json.dumps(bad), encoding="utf-8")
    assert fpj.status_of(p, "p") == "incomplete"
    p.write_text("{ not json", encoding="utf-8")
    assert fpj.status_of(p, "p") == "unreadable"


def test_failed_marker_is_left_alone(tmp_path):
    f = fpj.failed_path(tmp_path, "control", "r1")
    f.parent.mkdir(parents=True)
    f.write_text("{}", encoding="utf-8")
    assert f.is_file()
    assert fpj.answer_path(tmp_path, "control", "r1") != f


# ------------------------------------------------------------------ the runner end to end

class FakeLane:
    """The headless lane, replaced. `replies` is a function of the user message."""

    def __init__(self, replies):
        self.replies = replies
        self.calls = []

    def post(self, path, payload, timeout=None, **kw):
        user = payload["messages"][1]["content"]
        self.calls.append(payload)
        return {"choices": [{"message": {"content": self.replies(user)}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20}}


def install_lane(monkeypatch, replies):
    from harness import chat
    lane = FakeLane(replies)
    monkeypatch.setattr(chat, "post", lane.post)
    monkeypatch.setattr(chat, "reset_timing", lambda: None)
    monkeypatch.setattr(chat, "take_timing", lambda: {"attempts": 1})
    return lane


def test_dry_run_calls_nothing(tmp_path, monkeypatch, corpus, built):
    out_pairs, _ = built
    rows_path, _ = corpus
    answers_dir = tmp_path / "answers"
    lane = install_lane(monkeypatch, lambda u: json.dumps({f: "A" for f in fpj.FACETS}))
    rc = fpj.main(["--pairs", str(out_pairs / "control.jsonl"), "--rows", str(rows_path),
                   "--out", str(answers_dir), "--limit", "2", "--dry-run"])
    assert rc == 0
    assert not lane.calls
    assert not answers_dir.exists()


def test_runner_calls_and_resumes(tmp_path, monkeypatch, corpus):
    rows_path, stats_path = corpus
    pairs_dir = tmp_path / "pairs"
    monkeypatch.setattr(fps, "CONTROL_N", {"cross": 4, "same_tag": 2, "same_chunk": 2})
    monkeypatch.setattr(fps, "CONTROL_REPEATS", 2)
    monkeypatch.setattr(fps, "HELDOUT_N", 4)
    monkeypatch.setattr(fps, "HELDOUT_REPEATS", 2)
    monkeypatch.setattr(fps, "TRAIN_N", 4)
    fps.build(pairs_dir, stats_path, rows_path, 3, 0.25, expect=None)
    answers_dir = tmp_path / "answers"
    lane = install_lane(monkeypatch, lambda u: json.dumps({f: "B" for f in fpj.FACETS}))
    fpj.main(["--pairs", str(pairs_dir / "control.jsonl"), "--rows", str(rows_path),
              "--out", str(answers_dir), "--workers", "2"])
    made = len(lane.calls)
    assert made > 0
    files = list((answers_dir / "control").glob("*.json"))
    assert len(files) == made
    rec = json.loads(files[0].read_text(encoding="utf-8"))
    assert set(rec["answers"]) == set(fpj.FACETS)
    assert rec["answers_canonical"]["topic"] in ("first", "second")
    assert rec["model"] == "claude-opus-5" and rec["effort"] == "high"
    fpj.main(["--pairs", str(pairs_dir / "control.jsonl"), "--rows", str(rows_path),
              "--out", str(answers_dir), "--workers", "2"])
    assert len(lane.calls) == made      # nothing re-asked


def test_runner_records_a_parse_failure(tmp_path, monkeypatch, corpus):
    rows_path, stats_path = corpus
    pairs_dir = tmp_path / "pairs"
    monkeypatch.setattr(fps, "CONTROL_N", {"cross": 2, "same_tag": 1, "same_chunk": 1})
    monkeypatch.setattr(fps, "CONTROL_REPEATS", 1)
    monkeypatch.setattr(fps, "HELDOUT_N", 2)
    monkeypatch.setattr(fps, "HELDOUT_REPEATS", 1)
    monkeypatch.setattr(fps, "TRAIN_N", 2)
    fps.build(pairs_dir, stats_path, rows_path, 4, 0.25, expect=None)
    answers_dir = tmp_path / "answers"
    lane = install_lane(monkeypatch, lambda u: '{"topic":"maybe"}')
    fpj.main(["--pairs", str(pairs_dir / "control.jsonl"), "--rows", str(rows_path),
              "--out", str(answers_dir), "--workers", "1"])
    failed = list((answers_dir / "control").glob("*.failed.json"))
    assert failed
    # two tries a row, never mended
    assert len(lane.calls) == 2 * len(failed)


def test_runner_refuses_a_prompt_mismatch(tmp_path, monkeypatch, corpus):
    rows_path, stats_path = corpus
    pairs_dir = tmp_path / "pairs"
    monkeypatch.setattr(fps, "CONTROL_N", {"cross": 2, "same_tag": 1, "same_chunk": 1})
    monkeypatch.setattr(fps, "CONTROL_REPEATS", 1)
    monkeypatch.setattr(fps, "HELDOUT_N", 2)
    monkeypatch.setattr(fps, "HELDOUT_REPEATS", 1)
    monkeypatch.setattr(fps, "TRAIN_N", 2)
    fps.build(pairs_dir, stats_path, rows_path, 6, 0.25, expect=None)
    answers_dir = tmp_path / "answers"
    row = read(pairs_dir / "control.jsonl")[0]
    rec = full_record(row_id=row["row_id"], sha="not the prompt")
    p = fpj.answer_path(answers_dir, "control", row["row_id"])
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(rec), encoding="utf-8")
    install_lane(monkeypatch, lambda u: json.dumps({f: "A" for f in fpj.FACETS}))
    with pytest.raises(SystemExit):
        fpj.main(["--pairs", str(pairs_dir / "control.jsonl"), "--rows", str(rows_path),
                  "--out", str(answers_dir), "--dry-run"])


# ------------------------------------------------------------------ the control

def plant(pairs_dir, answers_dir, decide):
    """Write an answer file for every control row; `decide(pair_key, row) -> 'A'|'B'|'equal'`
    for topic, the other facets always equal."""
    keys = {k["pair_id"]: k for k in read(pairs_dir / "topic_key.jsonl")}
    for row in read(pairs_dir / "control.jsonl"):
        key = keys[row["pair_id"]]
        choice = decide(key, row)
        answers = {f: ("equal" if f != "topic" else choice) for f in fpj.FACETS}
        rec = dict(row)
        rec.update({"answers": answers,
                    "answers_canonical": fpj.canonical(answers, row["order"]),
                    "prompt_sha256": "p", "model": "planted", "effort": "high"})
        p = fpj.answer_path(answers_dir, "control", row["row_id"])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rec), encoding="utf-8")


def truthful(noise, seed):
    """A judge that reads topic and slips more often the closer the two edges are."""
    rng = random.Random(seed)

    def decide(key, row):
        higher = "first" if key["first"]["topic"] >= key["second"]["topic"] else "second"
        if rng.random() < max(0.02, noise - 0.5 * key["gap"]):
            higher = "second" if higher == "first" else "first"
        if row["order"] == "AB":
            return "A" if higher == "first" else "B"
        return "B" if higher == "first" else "A"
    return decide


def run_control(tmp_path, pairs_dir, answers_dir, monkeypatch):
    monkeypatch.setattr(fpc, "B", 400)
    out = tmp_path / "control_out"
    fpc.main(["--pairs", str(pairs_dir), "--answers", str(answers_dir), "--out", str(out)])
    return json.loads((out / "verdict.json").read_text(encoding="utf-8")), \
        (out / "report.md").read_text(encoding="utf-8")


@pytest.fixture
def control_pairs(tmp_path, corpus, monkeypatch):
    rows_path, stats_path = corpus
    monkeypatch.setattr(fps, "CONTROL_N", {"cross": 120, "same_tag": 20, "same_chunk": 20})
    monkeypatch.setattr(fps, "CONTROL_REPEATS", 60)
    monkeypatch.setattr(fps, "HELDOUT_N", 8)
    monkeypatch.setattr(fps, "HELDOUT_REPEATS", 4)
    monkeypatch.setattr(fps, "TRAIN_N", 8)
    d = tmp_path / "pairs"
    fps.build(d, stats_path, rows_path, 9, 0.2, expect=None)
    return d


def test_control_passes_a_judge_that_follows_topic(tmp_path, monkeypatch, control_pairs):
    answers = tmp_path / "answers"
    plant(control_pairs, answers, truthful(0.35, 1))
    verdict, report = run_control(tmp_path, control_pairs, answers, monkeypatch)
    assert verdict["verdict"] == "PASS", report


def test_control_fails_a_coin(tmp_path, monkeypatch, control_pairs):
    answers = tmp_path / "answers"
    rng = random.Random(3)
    plant(control_pairs, answers, lambda k, r: rng.choice(("A", "B")))
    verdict, report = run_control(tmp_path, control_pairs, answers, monkeypatch)
    assert verdict["verdict"] == "FAIL"
    assert verdict["deciding"].startswith("1."), report


def test_control_fails_a_position_bias(tmp_path, monkeypatch, control_pairs):
    answers = tmp_path / "answers"
    plant(control_pairs, answers, lambda k, r: "A")
    verdict, report = run_control(tmp_path, control_pairs, answers, monkeypatch)
    assert verdict["verdict"] == "FAIL"
    topic = verdict["topic"]["cross"]
    assert topic["order_flip_rate"] == 1.0
    assert topic["repeat_flip_rate"] == 0.0
    assert not topic["line3_pass"], report


# ------------------------------------------------------------------ acquisition

def test_acquire_refuses_held_out_and_duplicates(tmp_path, corpus, built):
    out, _ = built
    rows_path, stats_path = corpus
    train = read(out / "train_round0.jsonl")
    hold = read(out / "heldout.jsonl")
    req = tmp_path / "req.jsonl"
    ids = []
    for r in train:
        for side in ("a", "b"):
            if r[side]["edge_id"] not in ids:
                ids.append(r[side]["edge_id"])
    taken = {frozenset((r["a"]["edge_id"], r["b"]["edge_id"])) for r in train}
    fresh = next({"a": x, "b": y} for x in ids for y in ids
                 if x != y and frozenset((x, y)) not in taken)
    req.write_text("\n".join(json.dumps(r) for r in [
        {"a": train[0]["a"]["edge_id"], "b": train[0]["b"]["edge_id"]},   # already asked
        {"a": hold[0]["a"]["edge_id"], "b": hold[0]["b"]["edge_id"]},     # held out
        {"a": "nope::x", "b": train[1]["b"]["edge_id"]},                  # unknown edge
        fresh,
    ]), encoding="utf-8")
    result = fps.acquire(out, req, 1, stats_path, rows_path, 5, 0.25)
    assert result["written"] == 1
    assert result["refused"] == {"held_out": 1, "unknown_edge": 1, "duplicate": 1,
                                 "same_edge": 0}
    written = read(out / "train_round1.jsonl")
    assert written[0]["round"] == 1 and written[0]["set"] == "train"
    assert {written[0]["a"]["edge_id"], written[0]["b"]["edge_id"]} == set(fresh.values())

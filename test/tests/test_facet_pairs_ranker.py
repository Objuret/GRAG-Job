"""The pairwise facet ranker: shapes, the tie model, the split guards, the stop rules.

Nothing here downloads a checkpoint or a tokenizer. The backbone is a tiny DeBERTa built from a
config and the tokenizer is a deterministic stand-in, so the whole file runs on CPU in seconds.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "test", ROOT / "prod"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

torch = pytest.importorskip("torch")
pytest.importorskip("transformers")

# Imported as a package: `model` and `data` are also the names of facet_neural's modules, and a
# plain import would hand whichever test file ran first to whichever ran second.
from graph.facet_pairs.model import FACETS, PairRanker, pair_first_segment  # noqa: E402
from graph.facet_pairs import data as D  # noqa: E402
from graph.facet_pairs import train as T  # noqa: E402
from graph.facet_pairs import evaluate as E  # noqa: E402
from graph.facet_pairs import acquire as A  # noqa: E402
from graph.facet_pairs import diagnostics as G  # noqa: E402
from graph.facet_pairs import score_all as S  # noqa: E402
from graph.facet_pairs import map_topic as M  # noqa: E402

VOCAB = 128
MAXLEN = 48


def tiny_encoder():
    from transformers import AutoModel, DebertaV2Config
    cfg = DebertaV2Config(hidden_size=32, num_hidden_layers=3, num_attention_heads=2,
                          intermediate_size=64, vocab_size=VOCAB, max_position_embeddings=64)
    return AutoModel.from_config(cfg)


def tiny_model():
    return PairRanker(encoder=tiny_encoder(), proj_dim=16, head_dim=8, dropout=0.0)


class FakeTokenizer:
    """Deterministic character-level ids, the same call shape the real tokenizer is used with."""

    def __call__(self, first, second, truncation=None, max_length=MAXLEN, padding=True,
                 return_tensors=None):
        seqs = []
        for a, b in zip(first, second):
            ids = [1] + [ord(c) % (VOCAB - 3) + 2 for c in a[:20]] + [2]
            ids += [ord(c) % (VOCAB - 3) + 2 for c in b][:max(0, max_length - len(ids) - 1)]
            ids += [2]
            seqs.append(ids[:max_length])
        n = max(len(s) for s in seqs)
        ids = torch.tensor([s + [0] * (n - len(s)) for s in seqs], dtype=torch.long)
        mask = torch.tensor([[1] * len(s) + [0] * (n - len(s)) for s in seqs],
                            dtype=torch.long)
        return {"input_ids": ids, "attention_mask": mask}

    def save_pretrained(self, path):
        Path(path).mkdir(parents=True, exist_ok=True)
        (Path(path) / "fake_tokenizer.json").write_text("{}", encoding="utf-8")


# ------------------------------------------------------------------ architecture

def test_forward_gives_five_scalars_per_row():
    m, tok = tiny_model(), FakeTokenizer()
    enc = tok(["tag one", "tag two"], ["chunk a", "chunk b"], max_length=MAXLEN)
    m.eval()
    with torch.no_grad():
        out = m(**enc)
    assert out.shape == (2, len(FACETS))


def test_one_encoder_pass_per_edge_not_per_facet(monkeypatch):
    """Five facet rows on ONE edge must encode that edge once, not five times."""
    m, tok = tiny_model(), FakeTokenizer()
    calls = []
    real = m.pair_representation
    def counting(input_ids, attention_mask, **kw):
        calls.append(int(input_ids.shape[0]))
        return real(input_ids, attention_mask, **kw)
    monkeypatch.setattr(m, "pair_representation", counting)
    rows = [{"facet": f, "edge_id": "c::t", "tag": "t", "text": "chunk body"}
            for f in FACETS]
    s, uniq = T.score_rows(m, tok, rows, MAXLEN, "cpu", 8)
    assert len(uniq) == 1                 # one distinct edge
    assert sum(calls) == 1                # one encoded row in total
    assert s.shape == (len(FACETS),)
    # the five facets read five different heads off that one pass
    assert len(set(round(float(v), 6) for v in s)) > 1


def test_the_tag_is_the_whole_first_segment():
    assert pair_first_segment("a tag") == "a tag"
    for f in FACETS:
        assert f not in pair_first_segment("a tag")


def test_repeated_edge_is_encoded_once_per_step():
    m, tok = tiny_model(), FakeTokenizer()
    rows = [{"facet": "topic", "edge_id": "c::t", "tag": "t", "text": "x"} for _ in range(5)]
    s, uniq = T.score_rows(m, tok, rows, MAXLEN, "cpu", 8)
    assert len(uniq) == 1
    assert s.shape == (5,)
    assert torch.allclose(s, s[0].expand(5))


def test_save_load_round_trip(tmp_path):
    torch.manual_seed(1)
    m, tok = tiny_model(), FakeTokenizer()
    m.eval()
    rows = [{"facet": "activity", "edge_id": "c::t", "tag": "t", "text": "chunk"}]
    with torch.no_grad():
        before, _ = T.score_rows(m, tok, rows, MAXLEN, "cpu", 8)
    with torch.no_grad():
        m.tie_log[2] = 0.7
    m.save(tmp_path / "model", tokenizer=tok, extra={"max_length": MAXLEN})
    back, cfg = PairRanker.load(tmp_path / "model", device="cpu")
    assert cfg["max_length"] == MAXLEN
    assert cfg["facets"] == list(FACETS)
    assert cfg["encoder_passes_per_edge"] == 1
    assert cfg["known_topic_values_in_training"] is False
    with torch.no_grad():
        after, _ = T.score_rows(back, tok, rows, MAXLEN, "cpu", 8)
    assert torch.allclose(before, after, atol=1e-6)
    assert pytest.approx(float(back.tie_log[2]), abs=1e-6) == 0.7


# ------------------------------------------------------------------ the tie model

def test_equal_scores_give_the_largest_tie_probability():
    nu = torch.tensor([1.0, 1.0, 1.0])
    s_a = torch.tensor([0.0, 0.5, 2.0])
    s_b = torch.tensor([0.0, 0.0, 0.0])
    la, lb, lt = T.davidson_log_probs(s_a, s_b, nu)
    p = torch.stack([la, lb, lt], dim=-1).exp()
    assert torch.allclose(p.sum(-1), torch.ones(3), atol=1e-6)
    # equal scores: a win and b win are equally likely, and the tie is at its maximum
    assert pytest.approx(float(p[0, 0]), abs=1e-6) == float(p[0, 1])
    assert float(p[0, 2]) > float(p[1, 2]) > float(p[2, 2])
    # with nu = 1 and equal scores every outcome is a third
    assert pytest.approx(float(p[0, 2]), abs=1e-6) == 1.0 / 3.0


def test_nu_controls_how_likely_a_tie_is():
    s = torch.zeros(2)
    for small, big in [(0.1, 10.0)]:
        _, _, lt_small = T.davidson_log_probs(s, s, torch.tensor([small, small]))
        _, _, lt_big = T.davidson_log_probs(s, s, torch.tensor([big, big]))
        assert float(lt_big[0]) > float(lt_small[0])


def test_nll_is_lowest_on_the_outcome_the_scores_predict():
    nu = torch.tensor([1.0])
    s_a, s_b = torch.tensor([3.0]), torch.tensor([0.0])
    ids = {k: torch.tensor([v]) for k, v in T.OUTCOME_ID.items()}
    losses = {k: float(T.davidson_nll(s_a, s_b, nu, v)) for k, v in ids.items()}
    assert losses["first"] < losses["equal"] < losses["second"]


# ------------------------------------------------------------------ learning

def test_a_planted_five_facet_order_is_recovered_from_synthetic_comparisons():
    """Eight edges, each facet with its OWN planted order; the ranker sees only who won."""
    torch.manual_seed(20260918)
    m, tok = tiny_model(), FakeTokenizer()
    n = 8
    edges = [{"edge_id": f"chunk{i}::tag{i}", "chunk_id": f"chunk{i}", "tag": f"tag {i}"}
             for i in range(n)]
    texts = {e["chunk_id"]: f"chunk body number {i}" for i, e in enumerate(edges)}
    # a different permutation per facet, so no single order can satisfy all five
    planted = {f: [((k + 1) * (i + 1)) % n for i in range(n)] for k, f in enumerate(FACETS)}
    planted["topic"] = list(range(n))
    obs = []
    for f in FACETS:
        for i in range(n):
            for j in range(i + 1, n):
                a, b = edges[i], edges[j]
                pa, pb = planted[f][i], planted[f][j]
                if pa == pb:
                    continue
                obs.append({"facet": f, "a_edge_id": a["edge_id"],
                            "a_chunk_id": a["chunk_id"], "a_tag": a["tag"],
                            "b_edge_id": b["edge_id"], "b_chunk_id": b["chunk_id"],
                            "b_tag": b["tag"],
                            "outcome": "first" if pa > pb else "second",
                            "pair_id": f"{f}-p{i}_{j}", "row_id": f"{f}-r{i}_{j}",
                            "set": "train", "pair_type": "cross", "order": 0, "repeat": 0})
    opt = torch.optim.Adam(m.parameters(), lr=1e-2)
    m.train()
    for _ in range(220):
        opt.zero_grad(set_to_none=True)
        loss = T.comparison_loss(m, tok, obs, texts, MAXLEN, "cpu", 32)
        loss.backward()
        opt.step()
    got = T.agreement(m, tok, obs, texts, MAXLEN, "cpu", 32)
    for f in FACETS:
        assert got["per_facet"][f]["agreement"] > 0.85, (f, got["per_facet"][f])


# ------------------------------------------- no known topic value on the training path

TRAINING_PATH = ["train.py", "data.py", "model.py"]

FORBIDDEN = ("facet_stats", "load_topic", "TopicStream", "topic_reg", "cosine",
             "topic_pair_share", "regression_loss")


def code_without_docstrings(path) -> str:
    """The module's source with every docstring removed, so prose cannot trip the grep."""
    import ast
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                node.body = body[1:] or [ast.Pass()]
    return ast.unparse(ast.fix_missing_locations(tree))


PKG = ROOT / "test" / "graph" / "facet_pairs"


def test_the_training_path_cannot_reach_the_known_topic_values():
    for name in TRAINING_PATH:
        code = code_without_docstrings(PKG / name)
        for word in FORBIDDEN:
            assert word not in code, f"{name} reaches the known topic values via {word!r}"
    # and the one module that IS allowed to read them does
    assert "facet_stats" in (PKG / "map_topic.py").read_text(encoding="utf-8")


def test_the_round_runner_names_the_known_topic_in_one_function_only():
    """`cache_round.py` may read the known topic — for the B control and the comparison
    column — but only inside `known_topic()`; the head it fits must never see it."""
    import ast
    tree = ast.parse((PKG / "cache_round.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name == "known_topic":
            continue
        body = node.body
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            node.body = body[1:] or [ast.Pass()]
        src = ast.unparse(ast.fix_missing_locations(node))
        for word in ("facet_stats", "load_topic", "topic_reg", "cosine"):
            assert word not in src, f"cache_round.{node.name} reaches the known topic"


def test_evaluate_no_longer_reads_the_known_topic():
    code = code_without_docstrings(PKG / "evaluate.py")
    for word in ("facet_stats", "load_topic", "map_topic"):
        assert word not in code


def test_the_data_module_has_no_topic_loader():
    assert not hasattr(D, "load_topic")
    assert not hasattr(D, "TopicStream")


# ------------------------------------------------------------------ the split

def test_the_heldout_rule_is_the_siblings_hash():
    import hashlib
    cid = "000c0db2accef0569116fc2d"
    h = hashlib.sha256(("facet_pairs_split:" + cid).encode("utf-8")).hexdigest()
    assert D.split_fraction(cid) == int(h, 16) / float(1 << 256)
    frac = sum(1 for i in range(4000) if D.is_heldout(f"chunk{i}")) / 4000
    assert 0.12 < frac < 0.18


def held_out_chunk(prefix="c"):
    for i in range(10000):
        if D.is_heldout(f"{prefix}{i}"):
            return f"{prefix}{i}"
    raise AssertionError("no held-out chunk found")


def training_chunk(prefix="c"):
    for i in range(10000):
        if not D.is_heldout(f"{prefix}{i}"):
            return f"{prefix}{i}"
    raise AssertionError("no training chunk found")


def test_the_heldout_assertion_fires():
    h, t = held_out_chunk(), training_chunk()
    ok = [{"facet": "topic", "a_chunk_id": t, "b_chunk_id": training_chunk("d"),
           "row_id": "r0"}]
    bad = ok + [{"facet": "topic", "a_chunk_id": h, "b_chunk_id": t, "row_id": "r1"}]
    assert D.assert_no_heldout(ok) == 1
    with pytest.raises(AssertionError):
        D.assert_no_heldout(bad)
    part = D.partition_observations(bad)
    assert len(part["train"]) == 1 and len(part["heldout"]) == 1


def test_heldout_rows_are_refused_by_their_set_name():
    rows = [{"row_id": "r1", "set": "control"}, {"row_id": "r2", "set": "train"}]
    assert D.assert_no_heldout_set(rows) == 2
    with pytest.raises(AssertionError):
        D.assert_no_heldout_set(rows + [{"row_id": "r3", "set": "heldout"}])


def test_heldout_answers_are_never_trained_on(tmp_path):
    """Both guards, through the real loader: the set name and the chunk hash."""
    h, t, t2 = held_out_chunk(), training_chunk("d"), training_chunk("e")
    rows_export = tmp_path / "rows.jsonl"
    with rows_export.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"header": {"db": "test"}}) + "\n")
        for c in (h, t, t2):
            f.write(json.dumps({"chunk_id": c, "kind": "document", "product": "P",
                                "tags": ["tag a", "tag b"],
                                "text": f"text of {c}"}) + "\n")
    ans = tmp_path / "answers"

    def write(setname, ca, cb, rid):
        d = ans / setname
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{rid}.json").write_text(json.dumps({
            "pair_id": rid, "row_id": rid, "set": setname, "pair_type": "cross",
            "order": "AB", "repeat": 1,
            "a": {"edge_id": D.edge_id(ca, "tag a"), "chunk_id": ca, "tag": "tag a"},
            "b": {"edge_id": D.edge_id(cb, "tag b"), "chunk_id": cb, "tag": "tag b"},
            "answers_canonical": {f: "first" for f in FACETS}}), encoding="utf-8")

    write("train", t, t2, "ok1")
    write("heldout", h, t, "held1")
    mat = T.load_training_observations(str(ans), str(rows_export))
    assert mat["sets"] == ["train"]
    touched = {o["a_chunk_id"] for o in mat["obs"]} | {o["b_chunk_id"] for o in mat["obs"]}
    assert h not in touched
    # asking for the held-out set by name is refused outright
    with pytest.raises(AssertionError):
        T.load_training_observations(str(ans), str(rows_export), ["heldout"])


def test_observations_are_canonical_against_the_sorted_edge_ids(tmp_path):
    d = tmp_path / "answers" / "control"
    d.mkdir(parents=True)
    row = {"pair_id": "p1", "row_id": "r1", "set": "control", "pair_type": "cross",
           "order": 1, "repeat": 0, "extra_key_we_ignore": 7,
           "a": {"edge_id": "zzz::b", "chunk_id": "zzz", "tag": "b"},
           "b": {"edge_id": "aaa::a", "chunk_id": "aaa", "tag": "a"},
           "answers_canonical": {f: "first" for f in FACETS}}
    (d / "r1.json").write_text(json.dumps(row), encoding="utf-8")
    obs = D.observations(D.load_answer_rows(str(tmp_path / "answers")))
    assert len(obs) == len(FACETS)
    for o in obs:
        assert o["a_edge_id"] == "aaa::a" and o["b_edge_id"] == "zzz::b"
        assert o["outcome"] == "first"


def test_a_bad_answer_word_raises():
    rows = [{"pair_id": "p", "row_id": "r", "a": "c1::t", "b": "c2::t",
             "answers_canonical": {"topic": "A"}}]
    with pytest.raises(ValueError):
        D.observations(rows)


# ------------------------------------------------------------------ the scoring shards

def test_the_shards_partition_every_chunk_exactly_once():
    chunks = [{"chunk_id": f"chunk{i}", "tags": ["a"], "text": "t"} for i in range(500)]
    for n in (2, 3, 5):
        seen = []
        for k in range(1, n + 1):
            seen.extend(c["chunk_id"] for c in S.shard_chunks(chunks, k, n))
        assert sorted(seen) == sorted(c["chunk_id"] for c in chunks)
        assert len(seen) == len(set(seen))
    # and two shards are not wildly unbalanced
    half = len(S.shard_chunks(chunks, 1, 2))
    assert 0.4 < half / len(chunks) < 0.6


def test_shard_spec_parsing():
    assert S.parse_shard("") == (1, 1)
    assert S.parse_shard("2/2") == (2, 2)
    for bad in ("0/2", "3/2", "1/0"):
        with pytest.raises(ValueError):
            S.parse_shard(bad)


def test_shard_files_merge_without_duplicates(tmp_path):
    rows = {1: [{"edge_id": "b::t", "topic": 1.0}, {"edge_id": "a::t", "topic": 2.0}],
            2: [{"edge_id": "c::t", "topic": 3.0}]}
    for k, rs in rows.items():
        with S.shard_path(tmp_path, k, 2).open("w", encoding="utf-8") as f:
            for r in rs:
                f.write(json.dumps(r) + "\n")
    merged = S.merge_shards(tmp_path, 2)
    assert [r["edge_id"] for r in merged] == ["a::t", "b::t", "c::t"]


# ------------------------------------------------------------------ the stop rules

def hist(*vals):
    return [{"round": i + 1, "agreement": v} for i, v in enumerate(vals)]


def test_stop_rule_done():
    d = E.stop_decision(hist(0.60, 0.72), se=0.02, self_agreement=0.73)
    assert d["decision"] == "done"


def test_stop_rule_stalled():
    d = E.stop_decision(hist(0.60, 0.605, 0.608), se=0.02, self_agreement=0.90)
    assert d["decision"] == "stalled"


def test_stop_rule_failed():
    d = E.stop_decision(hist(0.50, 0.51, 0.52), se=0.02, self_agreement=0.90)
    assert d["decision"] == "failed"


def test_stop_rule_continue():
    d = E.stop_decision(hist(0.55, 0.62), se=0.02, self_agreement=0.90)
    assert d["decision"] == "continue"
    # gaining, at round 3, and clear of the coin: still continue
    d = E.stop_decision(hist(0.60, 0.66, 0.72), se=0.02, self_agreement=0.90)
    assert d["decision"] == "continue"


def test_previous_rounds_are_read_from_disk(tmp_path):
    for n, v in [(1, 0.55), (2, 0.61)]:
        d = tmp_path / f"round{n}"
        d.mkdir()
        (d / "eval.json").write_text(json.dumps(
            {"round": n, "per_facet": {"why": {"agreement": v}}}), encoding="utf-8")
    got = E.previous_rounds(str(tmp_path), "why", 3)
    assert [r["round"] for r in got] == [1, 2]
    assert got[1]["agreement"] == 0.61
    assert E.previous_rounds(str(tmp_path), "why", 2) == [{"round": 1, "agreement": 0.55}]


def test_first_presentations_drop_repeats_not_orders():
    base = {"facet": "topic", "a_edge_id": "a", "b_edge_id": "b", "a_chunk_id": "ca",
            "b_chunk_id": "cb", "outcome": "first", "pair_id": "p1"}
    obs = [dict(base, order=0, repeat=0, row_id="r1"),
           dict(base, order=0, repeat=1, row_id="r2"),
           dict(base, order=1, repeat=0, row_id="r3")]
    got = E.first_presentations(obs)
    assert sorted(o["row_id"] for o in got) == ["r1", "r3"]
    groups = E.repeat_groups(obs)
    assert len(groups) == 1 and len(groups[0]) == 2


def test_bootstrap_se_is_positive_and_the_point_is_the_share():
    items = [{"correct": i % 3 != 0, "a_chunk_id": f"c{i // 4}", "b_chunk_id": f"c{i // 4}"}
             for i in range(60)]
    point, se, n = E.cluster_bootstrap_se(
        items, lambda it: E.cluster_key(it, "chunkpair"), E._agree_share, 400)
    assert pytest.approx(point, abs=1e-9) == sum(1 for i in items if i["correct"]) / 60
    assert se is not None and se > 0 and n == 15


# ------------------------------------------------------------------ acquisition

def synthetic_scores(n_chunks=60, tags_per=4):
    rows = []
    for i in range(n_chunks):
        for j in range(tags_per):
            cid, tag = f"chunk{i}", f"tag{j}"
            rows.append({"edge_id": D.edge_id(cid, tag), "chunk_id": cid, "tag": tag,
                         **{f: 0.01 * (i + j) + 0.1 * k for k, f in enumerate(FACETS)}})
    return rows


def test_acquisition_never_touches_a_heldout_chunk_and_de_duplicates():
    rows = synthetic_scores()
    assert any(D.is_heldout(r["chunk_id"]) for r in rows)   # the pool does contain some
    deg = {"edge": {}, "chunk": {}, "tag": {}}
    got = A.select(rows, 80, list(FACETS), deg, already=set(), seed=7)
    assert got
    for c in got:
        for eid in (c["a_edge_id"], c["b_edge_id"]):
            assert not D.is_heldout(D.split_edge_id(eid)[0])
        assert c["a_edge_id"] < c["b_edge_id"]
    keys = [(c["a_edge_id"], c["b_edge_id"]) for c in got]
    assert len(keys) == len(set(keys))
    assert {"coverage"} <= {c["reason"].split(":")[0] for c in got}
    assert any(c["reason"].startswith("uncertainty:") for c in got)


def test_acquisition_refuses_pairs_already_asked():
    rows = synthetic_scores()
    first = A.select(rows, 40, list(FACETS), {"edge": {}, "chunk": {}, "tag": {}},
                     already=set(), seed=7)
    already = {(c["a_edge_id"], c["b_edge_id"]) for c in first}
    second = A.select(rows, 40, list(FACETS), {"edge": {}, "chunk": {}, "tag": {}},
                      already=already, seed=7)
    assert second
    assert not ({(c["a_edge_id"], c["b_edge_id"]) for c in second} & already)


def test_only_unstopped_facets_drive_the_uncertainty_half(tmp_path):
    d = tmp_path / "round2"
    d.mkdir()
    (d / "eval.json").write_text(json.dumps({"round": 2, "decisions": {
        "topic": {"decision": "done"}, "temporal": {"decision": "continue"},
        "why": {"decision": "failed"}, "activity": {"decision": "stalled"},
        "concreteness": {"decision": "continue"}}}), encoding="utf-8")
    assert A.active_facets(str(tmp_path)) == ["temporal", "concreteness"]
    assert A.active_facets(str(tmp_path), "topic,why") == [
        "temporal", "activity", "concreteness"]
    rows = synthetic_scores()
    got = A.select(rows, 40, ["temporal"], {"edge": {}, "chunk": {}, "tag": {}},
                   already=set(), seed=3)
    reasons = {c["reason"] for c in got if c["reason"].startswith("uncertainty")}
    assert reasons == {"uncertainty:temporal"}


def test_uncertainty_picks_the_closest_scores():
    rows = [{"edge_id": D.edge_id(training_chunk(f"k{i}"), "t"),
             "chunk_id": training_chunk(f"k{i}"), "tag": "t",
             **{f: float(i) for f in FACETS}} for i in range(12)]
    got = A.select(rows, 4, ["topic"], {"edge": {}, "chunk": {}, "tag": {}},
                   already=set(), seed=5, uncertainty_share=1.0)
    by = {r["edge_id"]: r["topic"] for r in rows}
    gaps = [abs(by[c["a_edge_id"]] - by[c["b_edge_id"]]) for c in got]
    assert max(gaps) <= 3.0


def test_type_quota_sums_to_the_size():
    q = A.type_quota(101, A.PAIR_MIX)
    assert sum(q.values()) == 101 and q["cross"] >= q["same_tag"]


# ------------------------------------------------------------------ diagnostics

def test_flip_rates_and_cycles():
    def o(facet, a, b, outcome, pair, order=0, repeat=0):
        return {"facet": facet, "a_edge_id": a, "b_edge_id": b,
                "a_chunk_id": a.split("::")[0], "b_chunk_id": b.split("::")[0],
                "a_tag": "t", "b_tag": "t", "outcome": outcome, "pair_id": pair,
                "row_id": f"{pair}-{order}-{repeat}", "set": "control",
                "pair_type": "cross", "order": order, "repeat": repeat}
    obs = [
        o("topic", "a::t", "b::t", "first", "p1", order=0),
        o("topic", "a::t", "b::t", "second", "p1", order=1),      # an order flip
        o("topic", "a::t", "b::t", "first", "p1", order=0, repeat=1),   # a repeat, no flip
        o("topic", "b::t", "c::t", "first", "p2"),
        o("topic", "a::t", "c::t", "second", "p3"),               # c beats a -> a cycle
    ]
    r = G.flip_rates(obs)["topic"]
    assert r["order_flips"] == 1 and r["n_order_groups"] == 1
    assert r["repeat_flips"] == 0 and r["n_repeat_groups"] == 1
    assert r["tie_rate"] == 0.0
    g = G.graph_stats(obs, "topic")
    assert g["nodes"] == 3 and g["edges"] == 3 and g["components"] == 1
    assert g["triangles"] == 1 and g["cyclic_triangles"] == 1


# ------------------------------------------------------------------ the numeric mapping

def synthetic_layer(n_chunks=80, tags_per=5, seed=11):
    """Scored rows where topic's score is a monotone function of a planted known value."""
    import math
    import random as _r
    rng = _r.Random(seed)
    rows, known = [], {}
    for i in range(n_chunks):
        cid = f"chunk{i:04d}"
        for j in range(tags_per):
            tag = f"tag {j}"
            eid = D.edge_id(cid, tag)
            latent = rng.random()
            # the known topic value and the judge-derived topic score share an order
            known[eid] = 0.05 + 0.35 * latent
            row = {"edge_id": eid, "chunk_id": cid, "tag": tag,
                   "topic": 4.0 * latent - 2.0}
            for k, f in enumerate(FACETS[1:], start=1):
                row[f] = math.sin(k * (i + 1) + j) + 0.01 * rng.random()
            rows.append(row)
    rows.sort(key=lambda r: r["edge_id"])
    return rows, known


def test_pava_is_the_monotone_fit():
    assert M.pava([1.0, 3.0, 2.0, 4.0]) == pytest.approx([1.0, 2.5, 2.5, 4.0])
    out = M.pava([5.0, 4.0, 3.0])
    assert out == pytest.approx([4.0, 4.0, 4.0])
    y = [0.1, 0.2, 0.3, 0.4]
    assert M.pava(y) == pytest.approx(y)


def test_a_planted_monotone_relation_is_recovered():
    rows, known = synthetic_layer()
    L = M.build_layer(rows, known)
    held = L["transfer"]["heldout"]
    assert held["n"] > 10
    assert held["spearman_score_vs_known"] > 0.95
    # the mapped value is much closer to the known one than a constant is
    assert held["mae_mapped_position_vs_known"] < 0.3 * held["mae_constant_median_baseline"]


def test_the_position_mapping_gives_every_facet_topics_marginal():
    rows, known = synthetic_layer()
    L = M.build_layer(rows, known)
    ladder = sorted(L["mapped_position"]["topic"])
    for f in FACETS:
        assert sorted(L["mapped_position"][f]) == pytest.approx(ladder)
    # and the columns are NOT the same edge-by-edge
    assert L["mapped_position"]["temporal"] != L["mapped_position"]["topic"]


def test_the_two_mappings_are_both_reported_and_differ():
    rows, known = synthetic_layer()
    L = M.build_layer(rows, known)
    assert L["mapped_raw"]["temporal"] != L["mapped_position"]["temporal"]
    # topic's own position mapping is its isotonic mapping, the curve being monotone
    assert L["mapped_position"]["topic"] == pytest.approx(L["mapped_raw"]["topic"])


def test_map_topic_writes_every_output(tmp_path):
    rows, known = synthetic_layer()
    scores = tmp_path / "scores.jsonl"
    with scores.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    stats = tmp_path / "stats.jsonl"
    with stats.open("w", encoding="utf-8") as f:
        for eid, v in known.items():
            cid, tag = D.split_edge_id(eid)
            f.write(json.dumps({"chunk_id": cid, "tag": tag, "topic": v}) + "\n")
    out = tmp_path / "layer"
    assert M.main(["--round", "0", "--scores", str(scores), "--topic", str(stats),
                   "--out", str(out)]) == 0
    for name in ("ranks.jsonl", "numeric.jsonl", "mapping.json", "MAPPING.md"):
        assert (out / name).is_file(), name
    ranks = [json.loads(l) for l in (out / "ranks.jsonl").read_text(
        encoding="utf-8").splitlines()]
    assert len(ranks) == len(rows)
    assert set(ranks[0]["scores"]) == set(FACETS)
    assert set(ranks[0]["positions"]) == set(FACETS)
    num = [json.loads(l) for l in (out / "numeric.jsonl").read_text(
        encoding="utf-8").splitlines()]
    assert len(num) == len(rows)
    assert num[0]["known_topic"] is not None
    assert set(num[0]["mapped_position"]) == set(FACETS)
    assert set(num[0]["mapped_raw"]) == set(FACETS)
    md = (out / "MAPPING.md").read_text(encoding="utf-8")
    assert "topic score quantile" in md and "RAW-score mapping" in md

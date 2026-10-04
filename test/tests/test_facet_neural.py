"""The four-facet neural edge instrument: shapes, the chunk-grouped split, the artifact.

No model download happens in the shape tests — they build the encoder from a tiny config, so
the whole file runs offline in seconds. The one test that touches the real checkpoint is
skipped when it is not already cached.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "test" / "graph" / "facet_neural", ROOT / "test", ROOT / "prod"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

torch = pytest.importorskip("torch")
transformers = pytest.importorskip("transformers")

from model import FACETS, FacetModel  # noqa: E402
import data as D  # noqa: E402
from graph.facet_edits import apply_edits  # noqa: E402


def tiny_encoder():
    from transformers import AutoModel, DebertaV2Config
    cfg = DebertaV2Config(hidden_size=32, num_hidden_layers=3, num_attention_heads=2,
                          intermediate_size=64, vocab_size=128, max_position_embeddings=64)
    return AutoModel.from_config(cfg)


def tiny_model():
    return FacetModel(encoder=tiny_encoder(), proj_dim=16, head_dim=8)


# ------------------------------------------------------------------ architecture

def test_forward_gives_one_value_per_facet():
    m = tiny_model()
    ids = torch.randint(0, 128, (5, 11))
    mask = torch.ones_like(ids)
    out = m(input_ids=ids, attention_mask=mask)
    assert out.shape == (5, len(FACETS)) == (5, 4)


def test_pair_representation_is_two_hidden_sizes_wide():
    m = tiny_model()
    ids = torch.randint(0, 128, (3, 7))
    h = m.pair_representation(ids, torch.ones_like(ids))
    assert h.shape == (3, 2 * m.config.hidden_size)


def test_mean_pooling_ignores_padding():
    m = tiny_model()
    m.eval()
    ids = torch.randint(1, 128, (1, 6))
    full = torch.ones_like(ids)
    padded_ids = torch.cat([ids, torch.zeros(1, 4, dtype=ids.dtype)], dim=1)
    padded_mask = torch.cat([full, torch.zeros(1, 4, dtype=full.dtype)], dim=1)
    with torch.no_grad():
        a = m.pair_representation(ids, full)
        b = m.pair_representation(padded_ids, padded_mask)
    assert torch.allclose(a, b, atol=1e-4)


def test_heads_do_not_share_parameters():
    m = tiny_model()
    names = {f: {id(p) for p in m.heads[f].parameters()} for f in FACETS}
    for i, a in enumerate(FACETS):
        for b in FACETS[i + 1:]:
            assert not (names[a] & names[b])


def test_output_is_linear_and_can_be_negative():
    """Correction 1: the target is a signed relevance loss, so the output must not be squashed."""
    m = tiny_model()
    with torch.no_grad():
        m.heads["why"][-1].bias.fill_(-3.0)
        out = m(input_ids=torch.randint(0, 128, (2, 5)),
                attention_mask=torch.ones(2, 5, dtype=torch.long))
    assert (out[:, FACETS.index("why")] < 0).all()


def test_stage_a_freezes_the_whole_backbone():
    m = tiny_model()
    rec = m.set_stage("A")
    assert all(not p.requires_grad for p in m.encoder.parameters())
    assert all(p.requires_grad for p in m.projection.parameters())
    assert rec["unfrozen_encoder_parameters"] == []


def test_stage_b_unfreezes_exactly_the_last_two_layers():
    m = tiny_model()
    rec = m.set_stage("B")
    layers = m.encoder.encoder.layer
    assert all(not p.requires_grad for p in layers[0].parameters())
    assert all(p.requires_grad for p in layers[-1].parameters())
    assert all(p.requires_grad for p in layers[-2].parameters())
    assert all(not p.requires_grad for p in m.encoder.embeddings.parameters())
    assert rec["unfrozen_encoder_parameters"]


def test_save_and_load_round_trip(tmp_path):
    m = tiny_model()
    m.eval()
    ids = torch.randint(0, 128, (2, 9))
    mask = torch.ones_like(ids)
    with torch.no_grad():
        before = m(input_ids=ids, attention_mask=mask)
    m.save(tmp_path / "art", extra={"max_length": 64})
    again, cfg = FacetModel.load(tmp_path / "art")
    with torch.no_grad():
        after = again(input_ids=ids, attention_mask=mask)
    assert torch.allclose(before, after, atol=1e-6)
    assert cfg["facets"] == list(FACETS)
    assert (tmp_path / "art" / "model.safetensors").is_file()


def test_saved_state_carries_backbone_and_heads(tmp_path):
    m = tiny_model()
    m.save(tmp_path / "art")
    from safetensors.torch import load_file
    keys = set(load_file(str(tmp_path / "art" / "model.safetensors")))
    assert any(k.startswith("encoder.") for k in keys)
    assert any(k.startswith("projection.") for k in keys)
    for f in FACETS:
        assert any(k.startswith(f"heads.{f}.") for k in keys)


# ------------------------------------------------------------------ the split, section 14

def rows(n_chunks=20, per=3):
    return [{"chunk_id": f"c{c:03d}", "tag": f"t{t}", "text": f"text {c}",
             "y": [0.1, 0.2, 0.3, 0.4], "repeats": [1] * 4, "dispersion": [0.0] * 4}
            for c in range(n_chunks) for t in range(per)]


def test_split_is_disjoint_by_chunk():
    s = D.split_by_chunk(rows())
    a, b, c = set(s["train"]), set(s["val"]), set(s["test"])
    assert not (a & b) and not (a & c) and not (b & c)
    assert a | b | c == {r["chunk_id"] for r in rows()}


def test_no_chunk_has_tags_in_two_partitions():
    r = rows()
    parts = D.apply_split(r, D.split_by_chunk(r))
    where = {}
    for name, rs in parts.items():
        for x in rs:
            where.setdefault(x["chunk_id"], set()).add(name)
    assert all(len(v) == 1 for v in where.values())


def test_split_is_stable_under_its_seed():
    r = rows()
    assert D.split_by_chunk(r, seed=7) == D.split_by_chunk(r, seed=7)
    assert D.split_by_chunk(r, seed=7) != D.split_by_chunk(r, seed=8)


def test_split_keeps_every_row():
    r = rows()
    parts = D.apply_split(r, D.split_by_chunk(r))
    assert sum(len(v) for v in parts.values()) == len(r)


# ------------------------------------------------------------------ the table, section 24

def targets(status="kept", value=0.05):
    out = []
    for c in ("cA", "cB"):
        for t in ("t1", "t2"):
            for f in FACETS:
                out.append({"chunk_id": c, "tag": t, "facet": f, "target": value,
                            "status": status, "repeats": 1, "dispersion": 0.0,
                            "kind": "document", "product": "P"})
    return out


def test_table_keeps_only_edges_with_all_four_facets():
    t = targets()
    t = [x for x in t if not (x["chunk_id"] == "cA" and x["tag"] == "t1"
                              and x["facet"] == "why")]
    rows_, counts = D.build_table(t, {"cA": "text A", "cB": "text B"})
    assert counts["incomplete_edges"] == 1
    assert {(r["chunk_id"], r["tag"]) for r in rows_} == {("cA", "t2"), ("cB", "t1"),
                                                         ("cB", "t2")}


def test_table_drops_rejected_targets():
    t = targets(status="rejected_below_noise")
    rows_, counts = D.build_table(t, {"cA": "a", "cB": "b"})
    assert rows_ == []
    assert counts["rejected"] == 16


def test_table_target_order_is_the_facet_order():
    t = targets()
    for x in t:
        x["target"] = {"temporal": 1.0, "why": 2.0, "activity": 3.0,
                       "concreteness": 4.0}[x["facet"]]
    rows_, _ = D.build_table(t, {"cA": "a", "cB": "b"})
    assert rows_[0]["y"] == [1.0, 2.0, 3.0, 4.0]


def test_measured_zero_is_supervision_not_a_hole():
    t = targets(value=0.0)
    rows_, counts = D.build_table(t, {"cA": "a", "cB": "b"})
    assert len(rows_) == 4
    assert all(r["y"] == [0.0] * 4 for r in rows_)


# ------------------------------------------------------------------ the edit reconstruction

def test_apply_edits_leaves_every_untouched_character_alone():
    text = "The migration was postponed until Friday because the review stalled."
    new, problems = apply_edits(text, [{"find": "until Friday ", "replace": ""}])
    assert problems == []
    assert new == "The migration was postponed because the review stalled."


def test_apply_edits_refuses_an_ambiguous_anchor():
    _new, problems = apply_edits("a b a b", [{"find": "a b", "replace": "x"}])
    assert problems and "occurs 2 times" in problems[0]


def test_apply_edits_refuses_an_absent_anchor():
    _new, problems = apply_edits("hello", [{"find": "goodbye", "replace": ""}])
    assert problems and "not in the text" in problems[0]


def test_empty_edit_list_is_the_text_unchanged():
    new, problems = apply_edits("unchanged", [])
    assert new == "unchanged" and problems == []


# ------------------------------------------------------------------ the real checkpoint

def test_real_backbone_pair_is_tag_first_and_truncates_only_the_chunk():
    pytest.importorskip("transformers")
    from model import BACKBONE, encode_pairs, load_tokenizer
    try:
        tok = load_tokenizer(BACKBONE)
    except Exception as exc:                                    # not cached, offline
        pytest.skip(f"backbone tokenizer unavailable: {exc}")
    tag = "database migration schedule"
    chunk = "word " * 4000
    enc = encode_pairs(tok, [tag], [chunk], max_length=64)
    ids = enc["input_ids"][0].tolist()
    assert len(ids) == 64
    tag_ids = tok(tag, add_special_tokens=False)["input_ids"]
    assert ids[1:1 + len(tag_ids)] == tag_ids

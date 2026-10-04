"""The full-cache round runner, on the bake-off's synthetic cache: the split discipline, the
selection, the scores file, the eta-squared arithmetic and the nested subsets.

Nothing here downloads a backbone, opens the graph, calls a model, or reads a benchmark
question. The fixture is the one `test_facet_pairs_bakeoff.py` builds: a planted matrix, a
deterministic judge, a known topic column and an edge list that agree with each other.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "test", ROOT / "prod"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from graph.facet_pairs import data as D                    # noqa: E402
from graph.facet_pairs import cache_probe as P             # noqa: E402
from graph.facet_pairs import cache_round as CR            # noqa: E402

from test_facet_pairs_bakeoff import build_fixture         # noqa: E402

FACETS = D.FACETS
PKG = ROOT / "test" / "graph" / "facet_pairs"


@pytest.fixture(scope="module")
def fx(tmp_path_factory):
    return build_fixture(tmp_path_factory.mktemp("round"))


def _round(fx, out, **kw):
    kw.setdefault("max_epochs", 80)
    kw.setdefault("topic_pairs", 300)
    kw.setdefault("boot", 60)
    kw.setdefault("curve_seeds", 2)
    kw.setdefault("quiet", True)
    return CR.run_round(fx["cache"], str(out), fx["answers"], fx["rows"], fx["stats"],
                        fx["edges"], **kw)


@pytest.fixture(scope="module")
def ran(fx, tmp_path_factory):
    out = tmp_path_factory.mktemp("round1")
    ev = _round(fx, out)
    return {"out": out, "eval": ev}


# ---------------------------------------------------------------- split discipline

def test_no_heldout_chunk_reaches_a_gradient(fx, tmp_path, monkeypatch):
    """Every cache row a fit observation points at, over every fit in the round — the
    selection's and the curve's — belongs to a training chunk."""
    cache = P.Cache(fx["cache"])
    seen, real = [], P.subset

    def spy(encs):
        rows, out = real(encs)
        # encs[0] is always the fit side; its indices are FULL-cache rows
        seen.extend(int(v) for v in encs[0]["a"].tolist() + encs[0]["b"].tolist())
        return rows, out

    monkeypatch.setattr(P, "subset", spy)
    monkeypatch.setattr(CR.P, "subset", spy)
    _round(fx, tmp_path / "guard")
    assert seen, "no fit set was ever built"
    bad = [cache.edge_ids[i] for i in sorted(set(seen))
           if D.is_heldout(D.split_edge_id(cache.edge_ids[i])[0])]
    assert not bad, bad[:5]


def test_the_runner_checks_the_fit_set_against_the_split_rule(fx, tmp_path, monkeypatch):
    """The guard is wired: the runner passes its fit observations through
    `data.assert_no_heldout`, which raises on a held-out chunk."""
    calls = []
    real = D.assert_no_heldout

    def spy(obs, fraction=D.HELDOUT_FRACTION):
        calls.append(len(obs))
        return real(obs, fraction)

    monkeypatch.setattr(D, "assert_no_heldout", spy)
    monkeypatch.setattr(CR.D, "assert_no_heldout", spy)
    _round(fx, tmp_path / "wired")
    assert len(calls) >= 2 and max(calls) > 0
    held = [o for o in D.observations(D.load_answer_rows(fx["answers"], sets=["heldout"]))]
    assert held
    with pytest.raises(AssertionError):
        real(held)


def test_membership_marks_every_cached_edge_by_the_hash_rule(fx, ran):
    cache = P.Cache(fx["cache"])
    rows = [json.loads(l) for l in
            (ran["out"] / "edges.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == len(cache.edge_ids)
    assert [r["edge_id"] for r in rows] == cache.edge_ids
    for r in rows:
        assert r["split"] == ("heldout" if D.is_heldout(r["chunk_id"]) else "train")
        assert r["chunk_id"], r
    assert any(r["split"] == "heldout" for r in rows)
    assert any(r["in_pairs"] for r in rows)


# ---------------------------------------------------------------- selection

def test_selection_is_unaffected_by_permuting_the_heldout_labels(fx, tmp_path):
    base = _round(fx, tmp_path / "a")
    held = Path(fx["answers"]) / "heldout"
    backup = {p: p.read_text(encoding="utf-8") for p in held.glob("*.json")}
    try:
        flip = {"first": "second", "second": "first", "equal": "equal"}
        for p, txt in backup.items():
            r = json.loads(txt)
            r["answers_canonical"] = {k: flip[v] for k, v in r["answers_canonical"].items()}
            p.write_text(json.dumps(r), encoding="utf-8")
        after = _round(fx, tmp_path / "b")
    finally:
        for p, txt in backup.items():
            p.write_text(txt, encoding="utf-8")
    assert (after["probe"]["selected"]["head"], after["probe"]["selected"]["variant"]) == \
           (base["probe"]["selected"]["head"], base["probe"]["selected"]["variant"])
    assert after["probe"]["selected"]["val_agreement"] == pytest.approx(
        base["probe"]["selected"]["val_agreement"])
    # and the held-out reading did move, so the permutation was not a no-op
    assert after["probe"]["A"]["macro"] != pytest.approx(base["probe"]["A"]["macro"])


# ---------------------------------------------------------------- the scores file

def test_scores_file_is_complete_and_positions_are_in_the_unit_interval(fx, ran):
    cache = P.Cache(fx["cache"])
    rows = [json.loads(l) for l in
            (ran["out"] / "scores.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == len(cache.edge_ids)
    assert [r["edge_id"] for r in rows] == cache.edge_ids
    for f in FACETS:
        pos = np.array([r[f + "_pos"] for r in rows])
        val = np.array([r[f] for r in rows])
        assert np.isfinite(val).all()
        assert pos.min() >= 0.0 and pos.max() <= 1.0
        # the position is the value's own rank, so the two orders agree
        assert CR.spearman(val, pos) == pytest.approx(1.0, abs=1e-9)
    for r in rows:
        assert r["chunk_id"] and r["tag"]
        assert "kind" in r
    for name in ("head.pt", "standardisation.npz", "config.json"):
        assert (ran["out"] / "model" / name).is_file()
    cfg = json.loads((ran["out"] / "model" / "config.json").read_text(encoding="utf-8"))
    assert cfg["topic_values_seen_by_this_head"] is False
    assert cfg["variant"] == ran["eval"]["probe"]["selected"]["variant"]
    for name in ("eval.json", "eval.md", "LAYER.md", "CURVE.md"):
        assert (ran["out"] / name).is_file()


# ---------------------------------------------------------------- arithmetic

def test_eta_squared_arithmetic():
    # two groups, means 1 and 3, no spread inside a group: every bit of variance is the label
    assert CR.eta_squared([1, 1, 3, 3], ["a", "a", "b", "b"]) == pytest.approx(1.0)
    # one group: nothing between groups
    assert CR.eta_squared([1, 2, 3, 4], ["a"] * 4) == pytest.approx(0.0)
    # group means equal, spread inside: nothing between groups
    assert CR.eta_squared([1, 3, 1, 3], ["a", "a", "b", "b"]) == pytest.approx(0.0)
    # the textbook identity: eta2 = SSbetween / SStotal
    v = [2.0, 4.0, 9.0, 11.0, 5.0]
    g = ["a", "a", "b", "b", "b"]
    grand = np.mean(v)
    ssb = 2 * (np.mean(v[:2]) - grand) ** 2 + 3 * (np.mean(v[2:]) - grand) ** 2
    sst = sum((x - grand) ** 2 for x in v)
    assert CR.eta_squared(v, g) == pytest.approx(ssb / sst)


def test_pooled_within_sd_matches_the_definition():
    vals = np.array([[1.0], [3.0], [10.0], [14.0]])
    groups = ["a", "a", "b", "b"]
    # each group's SS is 2.0 and 8.0 with 1 df each -> pooled sd = sqrt(10/2)
    assert CR.pooled_within_sd(vals, groups)[0] == pytest.approx(np.sqrt(10.0 / 2.0))
    assert CR.pooled_within_sd(vals, ["a", "b", "c", "d"])[0] is None


def test_nested_subsets_are_nested():
    keys = [f"row{i}" for i in range(97)]
    subs = CR.nested_subsets(keys, (0.25, 0.5, 0.75, 1.0), seed=3)
    sizes = sorted(subs)
    for a, b in zip(sizes, sizes[1:]):
        assert subs[a] <= subs[b], (a, b)
    assert subs[1.0] == set(keys)
    assert len(subs[0.25]) == round(0.25 * len(keys))
    # and the draw is seeded
    assert CR.nested_subsets(keys, (0.25,), seed=3)[0.25] == subs[0.25]


def test_the_curve_is_nested_in_the_run(fx, ran):
    rows = ran["eval"]["curve"]
    assert [r["size"] for r in rows] == list(CR.CURVE_SIZES)
    assert rows[0]["n_rows"] < rows[-1]["n_rows"]
    for r in rows:
        assert 0.0 <= r["macro_mean"] <= 1.0
        for f in FACETS:
            assert 0.0 <= r["per_facet"][f]["mean"] <= 1.0


# ---------------------------------------------------------------- the topic guard

FORBIDDEN = ("facet_stats", "load_topic", "topic_reg", "cosine")
ALLOWED_TOPIC_READER = "known_topic"


def _functions(path):
    import ast
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                node.body = body[1:] or [ast.Pass()]
            out[node.name] = ast.unparse(ast.fix_missing_locations(node))
    return out


def test_the_round_runner_reads_the_known_topic_in_exactly_one_function():
    fns = _functions(PKG / "cache_round.py")
    assert ALLOWED_TOPIC_READER in fns
    assert "load_topic" in fns[ALLOWED_TOPIC_READER]
    for name, src in fns.items():
        if name == ALLOWED_TOPIC_READER:
            continue
        for word in FORBIDDEN:
            assert word not in src, f"{name} reaches the known topic values via {word!r}"


def test_the_training_and_curve_functions_never_mention_the_known_topic():
    fns = _functions(PKG / "cache_round.py")
    for name in ("curve", "nested_subsets", "agreement_per_facet", "membership_rows"):
        src = fns[name]
        for word in FORBIDDEN + ("known_topic",):
            assert word not in src, f"{name} mentions {word!r}"

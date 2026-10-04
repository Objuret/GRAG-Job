"""The backbone bake-off, on synthetic caches: the heads, the split discipline, the frozen
winner rule, the collapse-excess arithmetic and the paired-difference standard error.

Nothing here downloads a backbone, opens the real graph, or reads a benchmark question. The
"cache" is a planted matrix in a small dimension; the "judge" is a deterministic function of
that matrix, so a head that learns the planting is a head that works.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "test", ROOT / "prod"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# Imported as a package: `model`, `data` and `train` are also the names of facet_neural's
# modules, and a plain import would hand whichever test file ran first to whichever ran second.
from graph.facet_pairs import data as D                  # noqa: E402
from graph.facet_pairs import cache_probe as P           # noqa: E402
from graph.facet_pairs import bakeoff_report as R        # noqa: E402
from graph.facet_pairs import bakeoff_edges as BE        # noqa: E402

FACETS = D.FACETS
DIM = 8


# ---------------------------------------------------------------- the fixture

def _chunk_ids(n: int, heldout: bool) -> list:
    out, i = [], 0
    while len(out) < n:
        c = hashlib.sha1(f"synthetic-chunk-{i}".encode()).hexdigest()[:24]
        i += 1
        if D.is_heldout(c) == heldout:
            out.append(c)
    return out


def _planted(rng, n):
    return rng.normal(size=(n, DIM)).astype(np.float32)


def build_fixture(tmp: Path, n_train_chunks=26, n_held_chunks=14, tags_per_chunk=3,
                  seed=7) -> dict:
    """A cache, a judge, a topic column and an edge list that all agree with each other.

    The planted truth: facet f's score of an edge is the dot product of the edge's vector with
    a fixed direction W[f]. The judge answers by the sign of the difference, calling a pair
    equal when the difference is under 0.25. The known topic value is a monotone function of
    facet 0's score, so the topic control has something to recover.
    """
    rng = np.random.default_rng(seed)
    train_c = _chunk_ids(n_train_chunks, False)
    held_c = _chunk_ids(n_held_chunks, True)
    chunks = train_c + held_c
    tags = [f"tag {i}" for i in range(tags_per_chunk * 3)]

    edges, rows = [], []
    for k, c in enumerate(chunks):
        ts = [tags[(k + j) % len(tags)] for j in range(tags_per_chunk)]
        rows.append({"chunk_id": c, "kind": "document", "product": "P",
                     "tags": ts, "text": f"text of chunk {c}"})
        for t in ts:
            edges.append((D.edge_id(c, t), c, t))

    V = _planted(rng, len(edges))
    W = rng.normal(size=(len(FACETS), DIM)).astype(np.float32)
    truth = V @ W.T                                     # n_edges x 5
    eidx = {e: i for i, (e, _, _) in enumerate(edges)}

    # the cache: every saved vector is the planting, the deeper layers noisier
    store = {"edge_id": np.array([e for e, _, _ in edges], dtype=object).astype("U"),
             "n_tokens": np.full(len(edges), 100, dtype=np.int32),
             "truncated": np.zeros(len(edges), dtype=bool)}
    for li in range(1, 5):
        noise = rng.normal(scale=0.05 * li, size=V.shape).astype(np.float32)
        store[f"cls_L-{li}"] = (V + noise).astype(np.float16)
        store[f"mean_L-{li}"] = (V + noise * 0.5).astype(np.float16)
    store["native_logit"] = truth[:, 0].astype(np.float32)
    cache_dir = tmp / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    npz = cache_dir / "synthetic__backbone.npz"
    np.savez(npz, **store)
    (cache_dir / "synthetic__backbone.meta.json").write_text(json.dumps({
        "model": "synthetic/backbone", "hidden_size": DIM, "seconds_per_1000_edges": 1.0,
        "max_length": 128, "truncation_rate": 0.0, "device": "cpu"}), encoding="utf-8")

    # the judge's rows
    ans = tmp / "answers"
    pair_rng = np.random.default_rng(seed + 1)

    def write_row(setname, ea, eb, rid, pair_id, order, repeat, flip=False):
        a_c, a_t = D.split_edge_id(ea)
        b_c, b_t = D.split_edge_id(eb)
        lo, hi = sorted((ea, eb))
        answers = {}
        for fi, f in enumerate(FACETS):
            g = float(truth[eidx[lo], fi] - truth[eidx[hi], fi])
            v = "equal" if abs(g) < 0.25 else ("first" if g > 0 else "second")
            if flip and v != "equal":
                v = "second" if v == "first" else "first"
            answers[f] = v
        d = ans / setname
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{rid}.json").write_text(json.dumps({
            "pair_id": pair_id, "row_id": rid, "set": setname, "order": order,
            "repeat": repeat, "pair_type": "cross",
            "a": {"edge_id": ea, "chunk_id": a_c, "tag": a_t},
            "b": {"edge_id": eb, "chunk_id": b_c, "tag": b_t},
            "answers_canonical": answers}), encoding="utf-8")

    def draw(pool, n, setname, flip=False):
        made = 0
        tries = 0
        while made < n and tries < n * 50:
            tries += 1
            i, j = pair_rng.integers(0, len(pool), 2)
            if i == j:
                continue
            ea, eb = pool[i], pool[j]
            if D.split_edge_id(ea)[0] == D.split_edge_id(eb)[0]:
                continue
            pid = hashlib.sha1(f"{min(ea, eb)}|{max(ea, eb)}".encode()).hexdigest()
            write_row(setname, ea, eb, f"{pid}_AB", pid, "AB", 1, flip)
            made += 1

    # a third of each side is reserved: those edges never appear in a pair, so they are the
    # topic-sample edges the topic control is fitted and read on
    train_all = [e for e, c, _ in edges if not D.is_heldout(c)]
    held_all = [e for e, c, _ in edges if D.is_heldout(c)]
    train_pool = [e for i, e in enumerate(train_all) if i % 3]
    held_pool = [e for i, e in enumerate(held_all) if i % 3]
    draw(train_pool, 260, "train")
    draw(held_pool, 140, "heldout")

    # the corpus export
    rows_path = tmp / "rows_export.jsonl"
    with open(rows_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"header": {"db": "synthetic", "n_chunks": len(rows)}}) + "\n")
        for r in rows:
            f.write(json.dumps(r) + "\n")

    # the known topic column and the bake-off edge list
    stats_path = tmp / "stats.jsonl"
    with open(stats_path, "w", encoding="utf-8") as f:
        for e, c, t in edges:
            f.write(json.dumps({"chunk_id": c, "tag": t,
                                "topic": float(truth[eidx[e], 0]) * 0.1 + 0.2}) + "\n")
    edges_path = tmp / "edges.jsonl"
    judged = set()
    for r in D.load_answer_rows(str(ans)):
        for o in D.observations([r]):
            judged.add(o["a_edge_id"])
            judged.add(o["b_edge_id"])
    with open(edges_path, "w", encoding="utf-8") as f:
        for e, c, t in edges:
            f.write(json.dumps({"edge_id": e, "chunk_id": c, "tag": t,
                                "split": "heldout" if D.is_heldout(c) else "train",
                                "in_pairs": e in judged,
                                "topic_sample": e not in judged}) + "\n")

    return {"cache": str(npz), "cache_dir": str(cache_dir), "answers": str(ans),
            "rows": str(rows_path), "stats": str(stats_path), "edges": str(edges_path),
            "truth": truth, "eidx": eidx}


@pytest.fixture(scope="module")
def fx(tmp_path_factory):
    return build_fixture(tmp_path_factory.mktemp("bakeoff"))


def _run(fx, **kw):
    kw.setdefault("max_epochs", 120)
    kw.setdefault("patience", 25)
    kw.setdefault("topic_n", 400)
    kw.setdefault("quiet", True)
    return P.run(fx["cache"], fx["answers"], fx["rows"], fx["stats"], fx["edges"], **kw)


# ---------------------------------------------------------------- the heads

@pytest.mark.parametrize("kind", list(P.HEADS))
def test_planted_signal_is_recovered_by_each_head(fx, kind):
    r = _run(fx, heads=(kind,), variants=["cls_L-1"])
    assert r["A"]["macro"] > 0.80, (kind, r["A"]["macro"])
    for f in FACETS:
        assert r["A"]["per_facet"][f]["agreement"] > 0.65, (kind, f)


def test_topic_control_recovers_the_known_order(fx):
    r = _run(fx, heads=("linear",), variants=["cls_L-1"])
    assert r["B"]["spearman"] is not None and r["B"]["spearman"] > 0.5, r["B"]


def test_native_logit_path_is_read_when_present(fx):
    r = _run(fx, heads=("linear",), variants=["cls_L-1"])
    assert r["G"] is not None
    assert r["G"]["A_per_facet"]["topic"] > 0.8
    assert r["G"]["B_spearman"] > 0.8


# ---------------------------------------------------------------- split discipline

def test_no_heldout_chunk_reaches_a_gradient(fx, monkeypatch):
    seen = []
    real = P.fit_head

    def spy(X, fit, val, val_obs, kind, seed, *a, **kw):
        seen.extend(int(v) for v in fit["a"].tolist() + fit["b"].tolist())
        return real(X, fit, val, val_obs, kind, seed, *a, **kw)

    monkeypatch.setattr(P, "fit_head", spy)
    r = _run(fx, heads=("linear",), variants=["cls_L-1"])
    cache = P.Cache(fx["cache"])
    bad = [cache.edge_ids[i] for i in set(seen)
           if D.is_heldout(D.split_edge_id(cache.edge_ids[i])[0])]
    # the topic control fits on training-chunk topic-sample edges, so the same guard holds
    assert not bad, bad[:5]
    assert r["counts"]["heldout_obs"] > 0


def test_selection_uses_validation_only(fx, tmp_path):
    """Permuting the held-out labels must not change the chosen (head, variant)."""
    base = _run(fx, heads=("linear", "mlp"), variants=["cls_L-1", "mean_L-1"])
    held = Path(fx["answers"]) / "heldout"
    backup = {p: p.read_text(encoding="utf-8") for p in held.glob("*.json")}
    try:
        flip = {"first": "second", "second": "first", "equal": "equal"}
        for p, txt in backup.items():
            r = json.loads(txt)
            r["answers_canonical"] = {k: flip[v]
                                      for k, v in r["answers_canonical"].items()}
            p.write_text(json.dumps(r), encoding="utf-8")
        after = _run(fx, heads=("linear", "mlp"), variants=["cls_L-1", "mean_L-1"])
    finally:
        for p, txt in backup.items():
            p.write_text(txt, encoding="utf-8")
    assert after["selected"]["head"] == base["selected"]["head"]
    assert after["selected"]["variant"] == base["selected"]["variant"]
    assert after["selected"]["val_agreement"] == pytest.approx(
        base["selected"]["val_agreement"])
    # and the held-out reading did move, so the permutation was not a no-op
    assert after["A"]["macro"] != pytest.approx(base["A"]["macro"])


# ---------------------------------------------------------------- the arithmetic

def test_collapse_excess_arithmetic():
    """C is the student's same-side share minus Opus's own, averaged over the facet pairs."""
    keys = ["a~b", "c~d"]
    clusters = {"k1": 0, "k2": 1}
    items = [
        {"cluster": "k1", "facet_pair": "a~b", "student_same": True, "teacher_same": True},
        {"cluster": "k1", "facet_pair": "a~b", "student_same": True, "teacher_same": False},
        {"cluster": "k2", "facet_pair": "a~b", "student_same": False, "teacher_same": False},
        {"cluster": "k1", "facet_pair": "c~d", "student_same": True, "teacher_same": False},
        {"cluster": "k2", "facet_pair": "c~d", "student_same": True, "teacher_same": True},
    ]
    agg = R.agg_C(items, clusters, keys)
    w = np.ones(2)
    # a~b: student 2/3, teacher 1/3, excess +1/3. c~d: 2/2 - 1/2 = +1/2. mean = 5/12
    assert R.stat_C(agg, w) == pytest.approx(5 / 12)


def test_within_chunk_share_is_between_tags_inside_a_chunk():
    """A column that is constant inside every chunk has D = 0; one that varies only inside a
    chunk has D = 1."""
    clusters = {"c1": 0, "c2": 1}
    const = [{"cluster": "c1", "values": [1.0] * 5}, {"cluster": "c1", "values": [1.0] * 5},
             {"cluster": "c2", "values": [4.0] * 5}, {"cluster": "c2", "values": [4.0] * 5}]
    assert R.stat_D(R.agg_D(const, clusters), np.ones(2))[0] == pytest.approx(0.0)
    inside = [{"cluster": "c1", "values": [1.0] * 5}, {"cluster": "c1", "values": [3.0] * 5},
              {"cluster": "c2", "values": [1.0] * 5}, {"cluster": "c2", "values": [3.0] * 5}]
    assert R.stat_D(R.agg_D(inside, clusters), np.ones(2))[0] == pytest.approx(1.0)


def test_paired_difference_se_is_positive(fx):
    r1 = _run(fx, heads=("linear",), variants=["cls_L-1"])
    r2 = _run(fx, heads=("linear",), variants=["mean_L-4"])
    r2 = dict(r2)
    r2["candidate"] = "synthetic/other"
    boot = R.bootstrap({r1["candidate"]: r1, "synthetic/other": r2}, 200, 1)
    for crit in ("A", "B", "C"):
        s = R.diff_se_of(boot, crit, r1["candidate"], "synthetic/other")
        assert s is not None and s > 0, (crit, s)
    assert boot["clusters"] > 1


# ---------------------------------------------------------------- the frozen rule

def _boot(points: dict, ses: dict, diff: float = 0.001) -> dict:
    """A synthetic diagnostic table. `points[name] = {A, B, C, D}`; every paired difference
    gets the same small SE unless `ses` overrides it."""
    names = list(points)
    diff_se = {}
    for crit in ("A", "B", "C"):
        for i, x in enumerate(names):
            for y in names[i + 1:]:
                diff_se[f"{crit}|{x}|{y}"] = ses.get((crit, x, y), diff)
    return {"clusters": 10, "boot": 10, "seed": 1, "facet_pairs": [],
            "point": points,
            "se": {n: {"A": diff, "B": diff, "C": diff,
                       "D": [diff] * len(FACETS)} for n in names},
            "diff_se": diff_se}


BASE = R.BASELINE
GOOD_D = [0.4] * len(FACETS)
DEAD_D = [0.0] * len(FACETS)


def test_dominated_candidate_is_out_and_the_better_one_wins():
    b = _boot({BASE: {"A": 0.60, "B": 0.30, "C": 0.05, "D": GOOD_D},
               "X": {"A": 0.70, "B": 0.40, "C": 0.02, "D": GOOD_D}}, {})
    v = R.decide(b, {BASE: 10, "X": 10})
    assert v["winner"] == "X"
    assert BASE in v["out"]
    assert str(v["clause"]).startswith("3")


def test_nothing_beats_the_baseline_so_the_baseline_stays():
    b = _boot({BASE: {"A": 0.60, "B": 0.30, "C": 0.05, "D": GOOD_D},
               "X": {"A": 0.6001, "B": 0.3001, "C": 0.0499, "D": GOOD_D}}, {})
    v = R.decide(b, {BASE: 10, "X": 10})
    assert v["winner"] == BASE
    assert v["clause"] == 4


def test_d_not_above_zero_is_out():
    b = _boot({BASE: {"A": 0.60, "B": 0.30, "C": 0.05, "D": GOOD_D},
               "X": {"A": 0.90, "B": 0.90, "C": -0.50, "D": DEAD_D}}, {})
    v = R.decide(b, {BASE: 10, "X": 10})
    assert "X" in v["out"]
    assert v["winner"] == BASE
    assert any("clause 5" in line and "X" in line for line in v["log"])


WIDE = 1.0   # an SE so wide that nothing beats anything on that criterion


def test_tiebreak_falls_through_A_then_C_then_B_then_cache():
    """Clause 3 on its own: each criterion decides only when the one before it is tied."""
    # A separates
    b = _boot({"X": {"A": 0.70, "B": 0.10, "C": 0.30, "D": GOOD_D},
               "Y": {"A": 0.60, "B": 0.90, "C": 0.01, "D": GOOD_D}}, {})
    assert R.tiebreak(b, ["X", "Y"], {"X": 1, "Y": 1})[:2] == ("X", "3A")
    # A tied, C separates
    b = _boot({"X": {"A": 0.70, "B": 0.90, "C": 0.30, "D": GOOD_D},
               "Y": {"A": 0.69, "B": 0.10, "C": 0.01, "D": GOOD_D}},
              {("A", "X", "Y"): WIDE})
    assert R.tiebreak(b, ["X", "Y"], {"X": 1, "Y": 1})[:2] == ("Y", "3C")
    # A and C tied, B separates
    b = _boot({"X": {"A": 0.70, "B": 0.10, "C": 0.30, "D": GOOD_D},
               "Y": {"A": 0.69, "B": 0.90, "C": 0.31, "D": GOOD_D}},
              {("A", "X", "Y"): WIDE, ("C", "X", "Y"): WIDE})
    assert R.tiebreak(b, ["X", "Y"], {"X": 1, "Y": 1})[:2] == ("Y", "3B")
    # all three tied, the smaller cache decides
    b = _boot({"X": {"A": 0.70, "B": 0.90, "C": 0.30, "D": GOOD_D},
               "Y": {"A": 0.69, "B": 0.89, "C": 0.31, "D": GOOD_D}},
              {("A", "X", "Y"): WIDE, ("C", "X", "Y"): WIDE, ("B", "X", "Y"): WIDE})
    assert R.tiebreak(b, ["X", "Y"], {"X": 99, "Y": 1})[:2] == ("Y", "3cache")


def test_a_tie_on_A_falls_to_C_through_the_whole_rule():
    """Both survive clause 2 because each beats the other on something: X on C, the baseline
    on B. A is tied, so clause 3 falls to C and X wins."""
    b = _boot({BASE: {"A": 0.60, "B": 0.40, "C": 0.20, "D": GOOD_D},
               "X": {"A": 0.61, "B": 0.10, "C": 0.02, "D": GOOD_D}},
              {("A", BASE, "X"): WIDE})
    v = R.decide(b, {BASE: 10, "X": 10})
    assert v["out"] == []
    assert v["winner"] == "X" and v["clause"] == "3C"


def test_beats_needs_three_standard_errors():
    b = _boot({BASE: {"A": 0.60, "B": 0.30, "C": 0.05, "D": GOOD_D},
               "X": {"A": 0.62, "B": 0.30, "C": 0.05, "D": GOOD_D}},
              {("A", BASE, "X"): 0.01})       # 3 SE = 0.03 > 0.02
    assert not R.beats(b, "X", BASE, "A")
    b2 = _boot({BASE: {"A": 0.60, "B": 0.30, "C": 0.05, "D": GOOD_D},
                "X": {"A": 0.62, "B": 0.30, "C": 0.05, "D": GOOD_D}},
               {("A", BASE, "X"): 0.001})     # 3 SE = 0.003 < 0.02
    assert R.beats(b2, "X", BASE, "A")
    # C is a collapse EXCESS: lower is better
    b3 = _boot({BASE: {"A": 0.60, "B": 0.30, "C": 0.20, "D": GOOD_D},
                "X": {"A": 0.60, "B": 0.30, "C": 0.02, "D": GOOD_D}}, {})
    assert R.beats(b3, "X", BASE, "C")
    assert not R.beats(b3, BASE, "X", "C")


# ---------------------------------------------------------------- the edge list

def test_edge_list_carries_no_topic_value(tmp_path):
    fx = build_fixture(tmp_path / "e")
    out, meta = BE.build(fx["stats"], fx["rows"], fx["answers"], 5, 5, seed=3)
    assert out and meta["n_edges"] == len(out)
    for r in out:
        assert set(r) == {"edge_id", "chunk_id", "tag", "split", "in_pairs", "topic_sample"}
    assert meta["topic_values_present"] is False
    assert all(r["split"] == ("heldout" if D.is_heldout(r["chunk_id"]) else "train")
               for r in out)
    assert meta["n_in_pairs"] > 0 and meta["n_topic_sample"] == 10

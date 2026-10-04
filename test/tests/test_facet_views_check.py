import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest

from graph import facet_views as fv
from graph import facet_views_check as fc
from graph.facet_edits import FACETS
from graph.facet_views_check import EMBED_MODES

# The scorer named in the planted score tables. The check reads the name off the table and
# carries it into the verdict; it never loads a model.
SCORER = "test/pair-scorer"

SCORER_REV = "0" * 40

# The synthetic corpus below plants cosines exactly: the tag vectors are an orthonormal basis,
# and a view's vector is built as the wanted cosine per tag plus one slack dimension that makes
# its norm 1, so cos(E(tag), E(view)) is the number asked for and nothing else.

CHUNKS = ["c0", "c1", "c2", "c3", "c4", "c5"]

TAGS = {c: [f"phrase alpha {c}", f"phrase beta {c}", f"phrase gamma {c}"] for c in CHUNKS}

BASE = 0.30

PLANT = 0.10

JITTER = 0.005


def all_tags():
    out = []
    for c in CHUNKS:
        out.extend(TAGS[c])
    return out


class Plan:
    """Collects the wanted cosines per view string and writes the npz the check reads."""

    def __init__(self):
        self.tags = all_tags()
        self.index = {t: i for i, t in enumerate(self.tags)}
        self.want: dict = {}
        self.ortho: set = set()

    def view(self, text: str, cosines: dict) -> str:
        self.want[text] = dict(cosines)
        return text

    def orthogonal(self, text: str) -> str:
        """A string whose vector is the last basis direction: orthogonal to every tag and to
        every view, so a residual against it is the view itself and `relative` subtracts 0."""
        self.ortho.add(text)
        return text

    def npz(self, path, extra_strings=(), drop=(), meta=None):
        # tag dimensions, one slack dimension that fixes each view's norm, and one the
        # orthogonal description sits on
        dim = len(self.tags) + 2
        shas, vecs = [], []

        def add(text, vec):
            shas.append(fc.sha256_of(text))
            vecs.append(vec.astype(np.float32))

        for t, i in self.index.items():
            v = np.zeros(dim)
            v[i] = 1.0
            add(t, v)
        for text in sorted(self.ortho):
            v = np.zeros(dim)
            v[-1] = 1.0
            add(text, v)
        for text, cos in self.want.items():
            if text in self.ortho:
                continue
            v = np.zeros(dim)
            for tag, c in cos.items():
                v[self.index[tag]] = c
            rest = 1.0 - float((v ** 2).sum())
            assert rest > 0, f"cosines too large for {text!r}"
            v[-2] = math.sqrt(rest)
            add(text, v)
        for text in extra_strings:
            if text in self.ortho or text in self.want:
                continue
            v = np.zeros(dim)
            v[-2] = 1.0
            add(text, v)
        keep = [i for i, s in enumerate(shas) if s not in {fc.sha256_of(d) for d in drop}]
        np.savez(path, sha=np.array([shas[i] for i in keep], dtype="U64"),
                 vec=np.stack([vecs[i] for i in keep]))
        if meta is not None:
            Path(path).with_suffix(".meta.json").write_text(
                json.dumps(meta), encoding="utf-8")
        return path

    def scores_npz(self, path, extra_strings=(), drop_pairs=(), keep=None,
                   model=SCORER, revision=SCORER_REV):
        """The same planted numbers as `npz`, written as a pair table instead of vectors: the
        score of (tag, text) is the cosine `npz` plants for that pair, so `xenc` and `cos` read
        the same value off the same corpus. `keep` restricts the table to a set of
        (a_sha, b_sha); `drop_pairs` removes named (tag, text) pairs."""
        table: dict = {}
        for text, cos in self.want.items():
            for tag, c in cos.items():
                table[(tag, text)] = float(c)
        for text in sorted(set(self.ortho) | set(extra_strings)):
            for tag in self.tags:
                table.setdefault((tag, text), 0.0)
        for pair in drop_pairs:
            table.pop(tuple(pair), None)
        rows = [(fc.sha256_of(t), fc.sha256_of(x), v) for (t, x), v in table.items()]
        if keep is not None:
            rows = [r for r in rows if (r[0], r[1]) in keep]
        np.savez(path,
                 a_sha=np.array([r[0] for r in rows], dtype="U64"),
                 b_sha=np.array([r[1] for r in rows], dtype="U64"),
                 score=np.array([r[2] for r in rows], dtype=np.float32),
                 model=np.array([model], dtype="U128"),
                 revision=np.array([revision], dtype="U64"))
        return path


def cf_record(text, changed=True, ok=True):
    return {"note": "n", "edits": [], "text": text, "applied": 0, "asked": 0,
            "changed": changed, "problems": [], "reconstruction_ok": ok}


def build_corpus(tmp_path, planted=True, nothing_facet=None, w2=True,
                 w2_offset=JITTER, vary=False, orthogonal_desc=False, desc_facet=None,
                 shared_cf=False, same_across_generations=False,
                 nothing_one_sided=False):
    """Six chunks, three phrases each, one changed counterfactual per (phrase, facet) in each
    of two generations. With `planted`, the targeted facet's own view of C' sits PLANT below
    T's vector while every other facet and every other tag stays inside JITTER. With `vary`
    the size is the relation's own, the same in both generations, so the two generations' Δ
    can agree in rank (§5's condition (e)) instead of differing only by jitter."""
    plan = Plan()
    texts_path = tmp_path / "texts.jsonl"
    views = tmp_path / "views"
    main = tmp_path / "counterfactuals" / "db"
    repeat = tmp_path / "counterfactuals_repeat" / "db"
    for d in (main, repeat):
        d.mkdir(parents=True, exist_ok=True)

    rows = []
    rng = np.random.default_rng(7)

    def jit():
        return float(rng.uniform(-JITTER, JITTER))

    def text_of(chunk, kind):
        return f"original text of {chunk}" if kind == "original" else f"{kind} of {chunk}"

    per_chunk_cf = {}
    for c in CHUNKS:
        rows.append({"sha": fc.sha256_of(text_of(c, "original")),
                     "text": text_of(c, "original"), "chunk_id": c, "kind": "slack",
                     "product": "P", "tags": TAGS[c],
                     "origins": [{"generation": "original"}]})
        per_chunk_cf[c] = {}
        for gen in ("main", "repeat"):
            for tag in TAGS[c]:
                for facet in FACETS:
                    # `shared_cf`: the second phrase's counterfactual IS the first phrase's,
                    # the collision the pilot has on 167 of its texts.
                    who = TAGS[c][0] if (shared_cf and tag == TAGS[c][1]) else tag
                    stamp = "" if same_across_generations else f"{gen} "
                    body = f"cf {stamp}{who} {facet} of {c}"
                    per_chunk_cf[c][(gen, tag, facet)] = body
                    rows.append({"sha": fc.sha256_of(body), "text": body, "chunk_id": c,
                                 "kind": "slack", "product": "P", "tags": TAGS[c],
                                 "origins": [{"generation": gen, "tag": tag,
                                              "facet": facet}]})
    # one line per distinct text, the origins gathered on it, as facet_views_texts writes it
    by_sha = {}
    order = []
    for r in rows:
        if r["sha"] in by_sha:
            by_sha[r["sha"]]["origins"].extend(r["origins"])
            continue
        by_sha[r["sha"]] = r
        order.append(r["sha"])
    with open(texts_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"header": {"ids": len(CHUNKS)}}) + "\n")
        for sha in order:
            f.write(json.dumps(by_sha[sha]) + "\n")

    for gen, directory in (("main", main), ("repeat", repeat)):
        for c in CHUNKS:
            edges = []
            for tag in TAGS[c]:
                edge = {"t": tag, "matched": True}
                for facet in FACETS:
                    edge[facet] = cf_record(per_chunk_cf[c][(gen, tag, facet)])
                edges.append(edge)
            rec = {"chunk_id": c, "kind": "slack", "product": "P", "tags": TAGS[c],
                   "given": len(TAGS[c]), "answered": len(TAGS[c]), "complete": True,
                   "format": "edits", "text": text_of(c, "original"), "edges": edges,
                   "prompt_sha256": "p"}
            (directory / f"{c}__0.json").write_text(json.dumps(rec), encoding="utf-8")

    # Two chunks carry one row each whose planted effect is reversed, so the chunk bootstrap
    # has something to vary over and the SE is not zero.
    hetero = CHUNKS[-2:]
    reversed_rows = {(hetero[i % 2], TAGS[hetero[i % 2]][i % len(TAGS[hetero[i % 2]])], f)
                     for i, f in enumerate(FACETS)}

    def size(chunk, tag, facet):
        if not vary:
            return PLANT
        h = int(hashlib.sha1(f"{chunk}|{tag}|{facet}".encode("utf-8")).hexdigest()[:8], 16)
        return 0.04 + 0.12 * (h % 1000) / 999.0

    def cosines(chunk, body, write, target=None):
        """The wanted cosine of each facet's view on `body`, per tag."""
        out = {}
        for tag in TAGS[chunk]:
            out[tag] = BASE + jit() + (w2_offset if write == 2 else 0.0)
        if target is not None and planted:
            tag, facet, is_target = target
            if is_target:
                sign = -1.0 if (chunk, tag, facet) not in reversed_rows else 1.0
                out[tag] = out[tag] + sign * size(chunk, tag, facet)
        return out

    for write in (1, 2) if w2 else (1,):
        for variant in ("chunk", "edge"):
            run = views / variant / f"w{write}"
            run.mkdir(parents=True, exist_ok=True)
            for c in CHUNKS:
                bodies = [(text_of(c, "original"), None)]
                seen_bodies = set()
                for (gen, tag, facet), body in per_chunk_cf[c].items():
                    if body in seen_bodies:
                        continue
                    seen_bodies.add(body)
                    bodies.append((body, (tag, facet)))
                for body, origin in bodies:
                    if variant == "chunk":
                        payload = {}
                        for facet in FACETS:
                            is_target = origin is not None and origin[1] == facet
                            cos = cosines(c, body, write,
                                          (origin[0], facet, is_target) if origin else None)
                            label = f"{variant} w{write} {facet} view of {body}"
                            if (nothing_facet == facet and origin is not None
                                    and not (nothing_one_sided and write == 2)):
                                payload[facet] = fv.NOTHING_LINE
                                plan.want.setdefault(fv.NOTHING_LINE, {})
                                plan.want[fv.NOTHING_LINE] = {
                                    t: 0.05 for t in plan.tags}
                            else:
                                payload[facet] = plan.view(label, cos)
                        if orthogonal_desc:
                            desc = plan.orthogonal("a description on its own direction")
                        else:
                            desc = f"{variant} w{write} description of {body}"
                            plan.view(desc, {t: BASE + jit() for t in TAGS[c]})
                        payload["description"] = desc
                        if desc_facet is not None:
                            payload[desc_facet] = desc
                        rec = {"sha": fc.sha256_of(body), "chunk_id": c, "kind": "slack",
                               "product": "P", "variant": "chunk", "write": write,
                               "origins": [], "prompt_sha256": "p", "model": "m",
                               "problems": [], "raw": [], "views": payload,
                               "nothing_lines": 0}
                    else:
                        out_rows = []
                        for tag in TAGS[c]:
                            row = {"t": tag, "matched": True}
                            for facet in FACETS:
                                is_target = (origin is not None and origin[1] == facet
                                             and origin[0] == tag)
                                cos = cosines(c, body, write,
                                              (tag, facet, is_target) if origin else None)
                                label = (f"{variant} w{write} {facet} view of {tag} "
                                         f"in {body}")
                                if (nothing_facet == facet and origin is not None
                                    and not (nothing_one_sided and write == 2)):
                                    row[facet] = fv.NOTHING_LINE
                                    plan.want[fv.NOTHING_LINE] = {
                                        t: 0.05 for t in plan.tags}
                                else:
                                    row[facet] = plan.view(label, {tag: cos[tag]})
                            out_rows.append(row)
                        rec = {"sha": fc.sha256_of(body), "chunk_id": c, "kind": "slack",
                               "product": "P", "variant": "edge", "write": write,
                               "origins": [], "prompt_sha256": "p", "model": "m",
                               "problems": [], "raw": [], "tags": TAGS[c],
                               "given": len(TAGS[c]), "answered": len(TAGS[c]),
                               "complete": True, "views": out_rows, "nothing_lines": 0}
                    (run / f"{fc.sha256_of(body)}.json").write_text(
                        json.dumps(rec), encoding="utf-8")
    return {"plan": plan, "texts": texts_path, "views": views,
            "cf_dirs": [main, repeat]}


def stripped_strings(corpus):
    """The edge views with their own phrase struck out — the check needs vectors for those
    too, and the plan must carry them or the npz is incomplete."""
    out = set()
    for variant_dir in sorted((corpus["views"]).glob("edge/w*")):
        for path in sorted(variant_dir.glob("*.json")):
            rec = json.loads(path.read_text(encoding="utf-8"))
            for row in rec["views"]:
                for facet in FACETS:
                    out.add(fc.strip_phrase(row[facet], row["t"])[0])
    return sorted(out)


def run_check(tmp_path, corpus, extra=(), boot=200, drop=(), mode="cos", name="check"):
    npz = tmp_path / "vectors.npz"
    corpus["plan"].npz(npz, extra_strings=stripped_strings(corpus), drop=drop)
    out = tmp_path / name
    argv = ["--texts", str(corpus["texts"]), "--views", str(corpus["views"]),
            "--vectors", str(npz), "--out", str(out), "--boot", str(boot),
            "--seed", "1", "--value-mode", mode]
    for d in corpus["cf_dirs"]:
        argv += ["--cf-dir", str(d)]
    argv += list(extra)
    assert fc.main(argv) == 0
    return out, json.loads((out / "verdict.json").read_text(encoding="utf-8"))


def run_xenc(tmp_path, corpus, extra=(), boot=200, drop_pairs=(), keep=None, name="xenc"):
    npz = tmp_path / f"{name}_scores.npz"
    corpus["plan"].scores_npz(npz, extra_strings=stripped_strings(corpus),
                              drop_pairs=drop_pairs, keep=keep)
    out = tmp_path / name
    argv = ["--texts", str(corpus["texts"]), "--views", str(corpus["views"]),
            "--scores", str(npz), "--out", str(out), "--boot", str(boot),
            "--seed", "1", "--value-mode", "xenc"]
    for d in corpus["cf_dirs"]:
        argv += ["--cf-dir", str(d)]
    argv += list(extra)
    assert fc.main(argv) == 0
    return out, json.loads((out / "verdict.json").read_text(encoding="utf-8"))


def values_of(out):
    return {(v["variant"], v["write"], v["sha"], v["tag"], v["facet"]):
            (v["value"], v["topic_local"], v.get("stripped"))
            for v in (json.loads(l) for l in
                      (out / "values.jsonl").read_text(encoding="utf-8").splitlines())}


# ------------------------------------------------------------------ the small pieces

def test_q_is_nearest_rank():
    assert fc.q([0, 1, 2, 3], 0.0) == 0
    assert fc.q([0, 1, 2, 3], 1.0) == 3
    assert fc.q([0.0, 1.0], 0.95) == 1.0
    assert fc.q([], 0.5) is None


def test_win_counts_a_tie_as_half():
    assert fc.win(1.0, 0.0) == 1.0
    assert fc.win(0.0, 1.0) == 0.0
    assert fc.win(2.0, 2.0) == 0.5
    d = np.array([1.0, 1.0, 0.0, 0.0])
    w = fc.wins_over_columns(d)
    assert w[0] == pytest.approx(2.5)
    assert w[2] == pytest.approx(0.5)
    assert fc.tag_wins(np.array([1.0, 1.0, 0.0]))[0] == pytest.approx(0.75)


def test_position_shares_a_tie():
    col = np.array([0.0, 1.0, 1.0, 2.0])
    assert fc.position(col, -1.0) == pytest.approx(0.0)
    assert fc.position(col, 1.0) == pytest.approx((1 + 0.5 * 2) / 4)
    assert fc.position(col, 3.0) == pytest.approx(1.0)


def test_strip_phrase_counts_removals_and_collapses():
    text = "WebSocket is fast. webSOCKET again, WebSockets stay."
    out, n = fc.strip_phrase(text, "WebSocket")
    assert n == 2
    assert "WebSockets stay" in out
    assert "  " not in out
    assert fc.strip_phrase("nothing here", "absent")[1] == 0


def test_machine_comes_from_the_shard_rule():
    for sha in [fc.sha256_of(f"t{i}") for i in range(30)]:
        shard = fv.shard_of(sha, fc.SHARDS)
        assert fc.machine_of(sha) == ("laptop" if shard in (0, 1) else "desktop")


# ------------------------------------------------------------------ the planted effect

def test_planted_effect_is_found(tmp_path):
    corpus = build_corpus(tmp_path)
    out, res = run_check(tmp_path, corpus)
    for variant in ("chunk", "edge"):
        sec = res["sections"][variant]["all"]["1"]
        for facet in FACETS:
            fac = sec[facet]["a_facet"]
            tag = sec[facet]["a_tag"]
            hit = sec[facet]["hit"]
            # six chunks x three phrases x two generations
            assert fac["n"] == len(CHUNKS) * len(TAGS["c0"]) * 2
            assert fac["value"] > 0.5, (variant, facet, fac)
            assert fac["se_chunk"] > 0
            assert fac["perm_p_chunk"] <= 0.05
            assert tag["value"] > 0.5, (variant, facet, tag)
            assert hit["p_plus"] > 0.5
            assert hit["sign_perm_p"] <= 0.05
            assert hit["r"] > 1.0, (variant, facet, hit["r"])
    assert (out / "values.jsonl").is_file()
    assert (out / "rows.jsonl").is_file()
    assert (out / "report.md").is_file()
    assert (out / "register.md").is_file()


def test_a_relation_sized_effect_reaches_pass(tmp_path):
    """With the planted size the relation's own and the same in both generations, (a)-(e) and
    the §9 guards all clear and the rule reads PASS."""
    corpus = build_corpus(tmp_path, vary=True)
    _out, res = run_check(tmp_path, corpus, boot=2000)
    for variant in ("chunk", "edge"):
        for facet in FACETS:
            s = res["sections"][variant]["all"]["1"][facet]
            v = res["verdict"][variant]["all"][facet]
            assert s["generation"]["rho"] > 0.5, (variant, facet, s["generation"])
            assert v["verdict"] == "PASS", (variant, facet, v["deciding"])
            core = v["core_w1"]
            assert core["b_ok"] and core["c_ok"] and core["e_ok"]
            assert core["d_ok"] is True
            assert all(core["guards"].values())
            assert v["core_w2"]["pass_core"] is True


def test_null_construction_sits_at_chance(tmp_path):
    corpus = build_corpus(tmp_path, planted=False)
    _out, res = run_check(tmp_path, corpus)
    for variant in ("chunk", "edge"):
        sec = res["sections"][variant]["all"]["1"]
        for facet in FACETS:
            fac = sec[facet]["a_facet"]
            assert 0.35 < fac["value"] < 0.75, (variant, facet, fac["value"])
            # the rule's own reading of "A is at chance": (b) fails and the cluster
            # permutation does not clear its bar
            assert (fac["value"] - 0.5) <= 3 * fac["se_chunk"], (variant, facet, fac)
            assert fac["perm_p_chunk"] > fc.PERM_BAR, (variant, facet,
                                                       fac["perm_p_chunk"])
            v = res["verdict"][variant]["all"][facet]
            assert v["verdict"] == "KILL", (variant, facet, v)
            assert "(b)" in v["deciding"]


# ------------------------------------------------------------------ §1 and §5 readings

def test_write_matching_uses_one_write_per_delta(tmp_path):
    """§1: the primary Δ is `v^w(C) − v^w(C')` on one write. With write 2 shifted by a large
    constant, both writes must still read the same Δ, and the crossed Δ must carry the shift."""
    corpus = build_corpus(tmp_path, w2_offset=0.20)
    out, res = run_check(tmp_path, corpus)
    rows = [json.loads(l) for l in (out / "rows.jsonl").read_text(
        encoding="utf-8").splitlines()]
    key = lambda r: (r["chunk_id"], r["tag"], r["facet"], r["generation"])
    w1 = {key(r): r for r in rows if r["variant"] == "chunk" and r["write"] == 1}
    w2 = {key(r): r for r in rows if r["variant"] == "chunk" and r["write"] == 2}
    assert w1 and w2
    for k in w1:
        assert w1[k]["d_target"] == pytest.approx(w2[k]["d_target"], abs=0.03)
    rep = res["delta_repeatability"]["chunk"][FACETS[0]]
    assert abs(rep["median_d1"] - rep["median_d2"]) < 0.03
    assert rep["median_cross"] == pytest.approx(rep["median_d1"] - 0.20, abs=0.03)


def test_shared_minuend_takes_the_two_generations_from_two_writes(tmp_path):
    """§5: Δ_main off write 1, Δ_repeat off write 2, so the two share the relation and not one
    measurement of C. With write 2 offset, Δ_repeat read off write 1 would differ."""
    corpus = build_corpus(tmp_path)
    out, res = run_check(tmp_path, corpus)
    rows = [json.loads(l) for l in (out / "rows.jsonl").read_text(
        encoding="utf-8").splitlines()]
    facet = FACETS[0]
    main1 = {(r["chunk_id"], r["tag"]): r["d_target"] for r in rows
             if r["variant"] == "chunk" and r["write"] == 1 and r["facet"] == facet
             and r["generation"] == "main"}
    rep2 = {(r["chunk_id"], r["tag"]): r["d_target"] for r in rows
            if r["variant"] == "chunk" and r["write"] == 2 and r["facet"] == facet
            and r["generation"] == "repeat"}
    keys = sorted(set(main1) & set(rep2))
    gen = res["sections"]["chunk"]["all"]["1"][facet]["generation"]
    assert gen["n"] == len(keys)
    assert gen["median_main"] == pytest.approx(
        float(np.median([main1[k] for k in keys])), abs=1e-6)
    assert gen["median_abs_diff"] == pytest.approx(
        float(np.median([abs(main1[k] - rep2[k]) for k in keys])), abs=1e-6)


# ------------------------------------------------------------------ subsets and diagnostics

def test_nothing_line_rows_drop_out_of_the_second_subset(tmp_path):
    corpus = build_corpus(tmp_path, nothing_facet=FACETS[1])
    _out, res = run_check(tmp_path, corpus)
    for variant in ("chunk", "edge"):
        all_n = res["sections"][variant]["all"]["1"][FACETS[1]]["a_facet"]["n"]
        cut_n = res["sections"][variant]["no_nothing"]["1"][FACETS[1]]["a_facet"]["n"]
        assert all_n > 0
        assert cut_n == 0, (variant, cut_n)
        keep = res["sections"][variant]["no_nothing"]["1"][FACETS[0]]["a_facet"]["n"]
        assert keep == all_n


def test_stripped_column_records_removals_and_the_zero_share(tmp_path):
    corpus = build_corpus(tmp_path)
    out, res = run_check(tmp_path, corpus)
    vals = [json.loads(l) for l in (out / "values.jsonl").read_text(
        encoding="utf-8").splitlines()]
    edge = [v for v in vals if v["variant"] == "edge"]
    chunk = [v for v in vals if v["variant"] == "chunk"]
    assert edge and chunk
    assert all("removals" in v and "stripped" in v for v in edge)
    assert all("removals" not in v for v in chunk)
    assert all(v["removals"] >= 1 for v in edge), "every edge view names its own phrase"
    lv = res["stripped"]["levels"][FACETS[0]]["1"]
    assert lv["zero_removal_share"] == pytest.approx(0.0)
    assert lv["removals_mean"] >= 1.0
    assert res["stripped"]["facets"][FACETS[0]]["1"]["n"] > 0


def test_positions_land_in_the_originals_only_column(tmp_path):
    corpus = build_corpus(tmp_path)
    out, _res = run_check(tmp_path, corpus)
    vals = [json.loads(l) for l in (out / "values.jsonl").read_text(
        encoding="utf-8").splitlines()]
    rows = [json.loads(l) for l in (out / "rows.jsonl").read_text(
        encoding="utf-8").splitlines()]
    originals = sorted(v["value"] for v in vals
                       if v["variant"] == "chunk" and v["write"] == 1
                       and v["facet"] == FACETS[0] and v["original"])
    assert len(originals) == len(CHUNKS) * len(TAGS["c0"])
    col = np.asarray(originals)
    by = {(v["chunk_id"], v["sha"], v["tag"]): v["value"] for v in vals
          if v["variant"] == "chunk" and v["write"] == 1 and v["facet"] == FACETS[0]}
    r = [x for x in rows if x["variant"] == "chunk" and x["write"] == 1
         and x["facet"] == FACETS[0]][0]
    orig_sha = [v["sha"] for v in vals if v["chunk_id"] == r["chunk_id"] and v["original"]][0]
    expect = (fc.position(col, by[(r["chunk_id"], orig_sha, r["tag"])])
              - fc.position(col, by[(r["chunk_id"], r["cf_sha"], r["tag"])]))
    assert r["pos_target"] == pytest.approx(expect, abs=1e-6)


def test_machine_column_is_carried_and_reported(tmp_path):
    corpus = build_corpus(tmp_path)
    out, res = run_check(tmp_path, corpus)
    vals = [json.loads(l) for l in (out / "values.jsonl").read_text(
        encoding="utf-8").splitlines()]
    rows = [json.loads(l) for l in (out / "rows.jsonl").read_text(
        encoding="utf-8").splitlines()]
    assert all(v["machine"] in fc.MACHINES for v in vals)
    assert all(r["machine_c"] in fc.MACHINES and r["machine_cf"] in fc.MACHINES
               for r in rows)
    assert all(r["same_machine"] == (r["machine_c"] == r["machine_cf"]) for r in rows)
    per_facet = res["machines"]["chunk"][FACETS[0]]
    assert set(per_facet["machines"]) == set(fc.MACHINES)
    assert 0.0 <= per_facet["writes"]["1"]["cross_share"] <= 1.0
    assert "The two writing machines" in (out / "report.md").read_text(encoding="utf-8")


# ------------------------------------------------------------------ the two value modes

def test_reading_matrix_zeroes_a_view_on_the_description_direction():
    d = np.array([1.0, 0.0, 0.0, 0.0])
    tv = np.array([0.0, 1.0, 0.0, 0.0])
    same = d.copy()
    other = np.array([0.6, 0.8, 0.0, 0.0])
    mat = np.stack([same, other])
    read, emptied = fc.reading_matrix(mat, d, "residual")
    assert emptied == 1
    assert np.allclose(read[0], 0.0)
    assert fc.read_values(read, d, tv, "residual")[0] == 0.0
    # the other row keeps its orthogonal part, re-normalised
    assert fc.read_values(read, d, tv, "residual")[1] == pytest.approx(1.0)
    # relative: the same view minus the description's own cosine is 0
    plain, emptied = fc.reading_matrix(mat, d, "relative")
    assert emptied == 0
    assert fc.read_values(plain, d, tv, "relative")[0] == pytest.approx(0.0)
    assert fc.reading_matrix(mat, d, "cos")[0] is mat
    with pytest.raises(SystemExit):
        fc.reading_matrix(mat, d, "nonsense")


def test_a_view_equal_to_the_description_reads_zero_in_both_modes(tmp_path):
    corpus = build_corpus(tmp_path, desc_facet=FACETS[0])
    for mode in ("residual", "relative"):
        out, res = run_check(tmp_path, corpus, mode=mode, name=f"check_{mode}")
        vals = [json.loads(l) for l in (out / "values.jsonl").read_text(
            encoding="utf-8").splitlines()]
        targeted = [v for v in vals if v["variant"] == "chunk" and v["facet"] == FACETS[0]]
        assert targeted
        assert all(v["value"] == pytest.approx(0.0) for v in targeted), mode
        zeros = sum(res["counts"]["residual_zero"].values())
        if mode == "residual":
            assert zeros > 0
        else:
            assert zeros == 0
        assert res["meta"]["value_mode"] == mode
        assert f"Value mode **`{mode}`**" in (out / "report.md").read_text(encoding="utf-8")


def test_both_modes_reach_pass_when_the_view_moves_orthogonally_to_the_description(tmp_path):
    """The planted movement is on the tag directions, the description on its own: `residual`
    leaves the view untouched and `relative` subtracts 0, so a mode must not lose an effect
    that is already orthogonal to the topic direction."""
    corpus = build_corpus(tmp_path, vary=True, orthogonal_desc=True)
    seen = {}
    for mode in EMBED_MODES:
        out, res = run_check(tmp_path, corpus, boot=2000, mode=mode, name=f"pass_{mode}")
        for variant in ("chunk", "edge"):
            for facet in FACETS:
                v = res["verdict"][variant]["all"][facet]
                assert v["verdict"] == "PASS", (mode, variant, facet, v["deciding"])
                seen.setdefault((variant, facet), []).append(
                    res["sections"][variant]["all"]["1"][facet]["a_facet"]["value"])
    for key, values in seen.items():
        assert values[0] == pytest.approx(values[1]), key
        assert values[0] == pytest.approx(values[2]), key


# ------------------------------------------------------------------ the pair-scorer mode

def test_xenc_reads_the_planted_scores(tmp_path):
    """The planted table carries the same numbers as the planted vectors, so every value and
    every topic_local must come out of `xenc` exactly as `cos` reads it off the embedding."""
    corpus = build_corpus(tmp_path)
    cos_out, _ = run_check(tmp_path, corpus, name="cos_ref")
    xenc_out, res = run_xenc(tmp_path, corpus)
    a = values_of(cos_out)
    b = values_of(xenc_out)
    assert set(a) == set(b)
    assert a
    for key, (value, topic, stripped) in a.items():
        assert b[key][0] == pytest.approx(value, abs=1e-5), key
        assert b[key][1] == pytest.approx(topic, abs=1e-5), key
        if stripped is not None:
            assert b[key][2] == pytest.approx(stripped, abs=1e-5), key
    assert res["meta"]["value_mode"] == "xenc"
    assert res["meta"]["scorer"] == {"model": SCORER, "revision": SCORER_REV}
    assert 0 < res["meta"]["pairs_needed"] <= res["meta"]["scores_loaded"]
    assert res["counts"]["residual_zero"] == {k: 0 for k in res["counts"]["residual_zero"]}
    report = (xenc_out / "report.md").read_text(encoding="utf-8")
    assert "Value mode **`xenc`**" in report
    assert SCORER in report


def test_xenc_reaches_pass_on_the_planted_effect(tmp_path):
    corpus = build_corpus(tmp_path, vary=True, orthogonal_desc=True)
    out, res = run_xenc(tmp_path, corpus, boot=2000)
    for variant in ("chunk", "edge"):
        for facet in FACETS:
            v = res["verdict"][variant]["all"][facet]
            assert v["verdict"] == "PASS", (variant, facet, v["deciding"])
    assert (out / "verdict.json").is_file()


def test_pairs_out_lists_every_pair_the_mode_needs(tmp_path):
    corpus = build_corpus(tmp_path)
    target = tmp_path / "pairs.jsonl"
    # no --value-mode: the listing is the same whatever mode a later run reads the views in
    argv = ["--texts", str(corpus["texts"]), "--views", str(corpus["views"]),
            "--out", str(tmp_path / "po"), "--pairs-out", str(target)]
    assert fc.main(argv) == 0
    listed = {}
    for line in target.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        assert fc.sha256_of(rec["a"]) == rec["a_sha"]
        assert fc.sha256_of(rec["b"]) == rec["b_sha"]
        listed[(rec["a_sha"], rec["b_sha"])] = (rec["a"], rec["b"])
    want = set()
    for run in sorted(corpus["views"].glob("*/w*")):
        variant = run.parent.name
        for path in sorted(run.glob("*.json")):
            rec = json.loads(path.read_text(encoding="utf-8"))
            for a, b in fc.file_pairs(rec, variant, TAGS[rec["chunk_id"]]):
                want.add((fc.sha256_of(a), fc.sha256_of(b)))
    assert want <= set(listed), f"{len(want - set(listed))} pairs missing"
    assert set(listed) == want
    # the listing is sufficient: with scores for exactly these pairs and nothing else, the
    # check runs without asking for one more
    out, _res = run_xenc(tmp_path, corpus, keep=set(listed), name="xenc_listed")
    assert (out / "report.md").is_file()


def test_a_missing_pair_raises_without_skip_missing(tmp_path):
    corpus = build_corpus(tmp_path)
    rec = json.loads(next((corpus["views"] / "chunk" / "w1").glob("*.json")).read_text(
        encoding="utf-8"))
    gone = fc.file_pairs(rec, "chunk", TAGS[rec["chunk_id"]])[0]
    npz = tmp_path / "holed.npz"
    corpus["plan"].scores_npz(npz, extra_strings=stripped_strings(corpus),
                              drop_pairs=[gone])
    argv = ["--texts", str(corpus["texts"]), "--views", str(corpus["views"]),
            "--scores", str(npz), "--out", str(tmp_path / "check"), "--boot", "50",
            "--value-mode", "xenc"]
    with pytest.raises(SystemExit) as err:
        fc.main(argv)
    assert "not in the preloaded scores" in str(err.value)


def test_skip_missing_drops_the_file_whose_pair_is_absent(tmp_path):
    corpus = build_corpus(tmp_path)
    path = next((corpus["views"] / "chunk" / "w1").glob("*.json"))
    rec = json.loads(path.read_text(encoding="utf-8"))
    gone = fc.file_pairs(rec, "chunk", TAGS[rec["chunk_id"]])[0]
    out, res = run_xenc(tmp_path, corpus, extra=["--skip-missing"], drop_pairs=[gone],
                        name="xenc_skip")
    assert res["counts"]["view_files"]["chunk/w1"] == len(
        list((corpus["views"] / "chunk" / "w1").glob("*.json"))) - 1
    assert (out / "report.md").is_file()


def test_the_modes_do_not_share_their_inputs(tmp_path):
    corpus = build_corpus(tmp_path)
    base = ["--texts", str(corpus["texts"]), "--views", str(corpus["views"]),
            "--out", str(tmp_path / "bad")]
    with pytest.raises(SystemExit) as err:
        fc.main(base + ["--value-mode", "xenc", "--vectors", str(tmp_path / "v.npz"),
                        "--scores", str(tmp_path / "s.npz")])
    assert "never --vectors" in str(err.value)
    with pytest.raises(SystemExit) as err:
        fc.main(base + ["--value-mode", "xenc"])
    assert "needs --scores" in str(err.value)
    with pytest.raises(SystemExit) as err:
        fc.main(base + ["--scores", str(tmp_path / "s.npz")])
    assert "belongs to --value-mode xenc" in str(err.value)


def test_two_score_tables_from_two_scorers_are_refused(tmp_path):
    corpus = build_corpus(tmp_path)
    one = corpus["plan"].scores_npz(tmp_path / "one.npz",
                                    extra_strings=stripped_strings(corpus))
    two = corpus["plan"].scores_npz(tmp_path / "two.npz",
                                    extra_strings=stripped_strings(corpus),
                                    model="other/scorer")
    argv = ["--texts", str(corpus["texts"]), "--views", str(corpus["views"]),
            "--scores", str(one), "--scores", str(two), "--out", str(tmp_path / "two_out"),
            "--boot", "50", "--value-mode", "xenc"]
    with pytest.raises(SystemExit) as err:
        fc.main(argv)
    assert "other/scorer" in str(err.value)


# ------------------------------------------------------------------ the audit's items

def test_the_column_carries_its_own_base_rate_and_the_position_reading(tmp_path):
    """§2 beside the rule: the target column's win rate on the rows it does NOT target, the
    contrast against it, and the same on the position deltas."""
    corpus = build_corpus(tmp_path, vary=True)
    _out, res = run_check(tmp_path, corpus, boot=2000)
    for variant in ("chunk", "edge"):
        for facet in FACETS:
            s = res["sections"][variant]["all"]["1"][facet]["a_facet"]
            c = s["cos"]
            p = s["pos"]
            assert c["n"] == s["n"]
            assert c["n_base"] == 3 * s["n"], (variant, facet, c["n_base"])
            assert c["value"] == pytest.approx(s["value"])
            assert c["base"] is not None and c["contrast"] is not None
            assert c["contrast"] == pytest.approx(c["value"] - c["base"])
            assert c["contrast_se"] > 0
            assert c["contrast"] > 0, (variant, facet, c)
            assert c["contrast_ci"][0] is not None
            assert p["value"] is not None and p["contrast"] is not None


def test_the_base_rate_contrast_is_flat_under_the_null(tmp_path):
    corpus = build_corpus(tmp_path, planted=False)
    _out, res = run_check(tmp_path, corpus)
    for variant in ("chunk", "edge"):
        for facet in FACETS:
            c = res["sections"][variant]["all"]["1"][facet]["a_facet"]["cos"]
            assert abs(c["contrast"]) < 0.30, (variant, facet, c["contrast"])


def test_a_kill_says_whether_the_rule_or_the_data_decided(tmp_path):
    corpus = build_corpus(tmp_path, planted=False)
    out, res = run_check(tmp_path, corpus)
    lo, hi = fc.RULE_BAND
    for variant in ("chunk", "edge"):
        for facet in FACETS:
            v = res["verdict"][variant]["all"][facet]
            core = v["core_w1"]
            a = res["sections"][variant]["all"]["1"][facet]["a_facet"]["value"]
            expect = v["verdict"] == "KILL" and (lo <= a <= hi
                                                 or core["a_state"] == "inconclusive")
            assert core["by_rule"] is expect, (variant, facet, a, core["a_state"])
    text = (out / "report.md").read_text(encoding="utf-8")
    assert "by the rule" in text and "perm p row" in text


def test_two_vectors_files_naming_two_embedders_are_refused(tmp_path):
    corpus = build_corpus(tmp_path)
    one = tmp_path / "a.npz"
    two = tmp_path / "b.npz"
    strings = stripped_strings(corpus)
    corpus["plan"].npz(one, extra_strings=strings,
                       meta={"model": "m", "revision": "r", "dtype": "float32",
                             "prefix": "passage: "})
    corpus["plan"].npz(two, extra_strings=strings,
                       meta={"model": "m", "revision": "OTHER", "dtype": "float32",
                             "prefix": "passage: "})
    argv = ["--texts", str(corpus["texts"]), "--views", str(corpus["views"]),
            "--vectors", str(one), "--vectors", str(two),
            "--out", str(tmp_path / "two"), "--boot", "50"]
    with pytest.raises(SystemExit) as err:
        fc.main(argv)
    assert "two instruments" in str(err.value)


def test_the_vectors_sidecar_is_recorded_and_its_absence_said(tmp_path):
    corpus = build_corpus(tmp_path)
    meta = {"model": "nvidia/llama-nemotron-embed-1b-v2", "revision": "113abe4a",
            "dtype": "float32", "prefix": "passage: "}
    npz = tmp_path / "vectors.npz"
    corpus["plan"].npz(npz, extra_strings=stripped_strings(corpus), meta=meta)
    argv = ["--texts", str(corpus["texts"]), "--views", str(corpus["views"]),
            "--vectors", str(npz), "--out", str(tmp_path / "withmeta"), "--boot", "50",
            "--seed", "1"]
    assert fc.main(argv) == 0
    res = json.loads((tmp_path / "withmeta" / "verdict.json").read_text(encoding="utf-8"))
    assert res["meta"]["vector_provenance"][0]["meta"]["model"] == meta["model"]
    assert res["meta"]["vectors_without_sidecar"] == []
    assert meta["model"] in (tmp_path / "withmeta" / "report.md").read_text(encoding="utf-8")
    # and with the sidecar removed
    Path(npz).with_suffix(".meta.json").unlink()
    argv[argv.index("--out") + 1] = str(tmp_path / "nometa")
    assert fc.main(argv) == 0
    res = json.loads((tmp_path / "nometa" / "verdict.json").read_text(encoding="utf-8"))
    assert res["meta"]["vectors_without_sidecar"] == ["vectors.npz"]
    assert "No `.meta.json` sidecar" in (tmp_path / "nometa" / "report.md").read_text(
        encoding="utf-8")


def test_a_run_directory_with_two_prompt_shas_is_refused(tmp_path):
    corpus = build_corpus(tmp_path)
    run = corpus["views"] / "chunk" / "w1"
    victim = sorted(run.glob("*.json"))[0]
    rec = json.loads(victim.read_text(encoding="utf-8"))
    rec["prompt_sha256"] = "another prompt entirely"
    victim.write_text(json.dumps(rec), encoding="utf-8")
    with pytest.raises(SystemExit) as err:
        fc.view_files(corpus["views"])
    assert "two prompts in one population" in str(err.value)


def test_the_prompt_sha_is_recorded_per_run_directory(tmp_path):
    corpus = build_corpus(tmp_path)
    _out, res = run_check(tmp_path, corpus)
    shas = res["counts"]["prompt_sha"]
    assert set(shas) == {"chunk/w1", "chunk/w2", "edge/w1", "edge/w2"}
    assert all(v == "p" for v in shas.values()), shas


def test_the_no_nothing_subset_gets_its_own_band(tmp_path):
    corpus = build_corpus(tmp_path, nothing_facet=FACETS[1], nothing_one_sided=True)
    _out, res = run_check(tmp_path, corpus)
    full = res["noise"]["chunk"]["facets"][FACETS[1]]
    cut = res["noise"]["chunk"]["facets_no_nothing"][FACETS[1]]
    assert cut["dropped_one_sided"] > 0
    assert cut["n"] == full["n"] - cut["dropped_one_sided"]
    untouched = res["noise"]["chunk"]["facets_no_nothing"][FACETS[0]]
    assert untouched["dropped_one_sided"] == 0
    assert untouched["n"] == res["noise"]["chunk"]["facets"][FACETS[0]]["n"]


def test_an_other_tag_aimed_at_by_the_same_edit_is_not_a_control(tmp_path):
    corpus = build_corpus(tmp_path, shared_cf=True)
    out, res = run_check(tmp_path, corpus)
    hit = 0
    for variant in ("chunk", "edge"):
        for facet in FACETS:
            s = res["sections"][variant]["all"]["1"][facet]["a_tag"]
            assert s["contaminated_arms"] > 0, (variant, facet)
            assert s["rows_with_contamination"] > 0
            assert s["value_clean"] is not None
            assert s["n_clean"] <= s["n"]
            hit += 1
    assert hit == 8
    rows = [json.loads(l) for l in (out / "rows.jsonl").read_text(
        encoding="utf-8").splitlines()]
    assert any(r["othertag_contaminated"] for r in rows)
    # with no collision there is nothing to drop and the two readings agree
    clean_corpus = build_corpus(tmp_path / "clean")
    _o, clean = run_check(tmp_path / "clean", clean_corpus)
    s = clean["sections"]["chunk"]["all"]["1"][FACETS[0]]["a_tag"]
    assert s["contaminated_arms"] == 0
    assert s["value_clean"] == pytest.approx(s["value"])


def test_two_generations_of_one_text_are_one_measurement(tmp_path):
    corpus = build_corpus(tmp_path, vary=True, same_across_generations=True)
    _out, res = run_check(tmp_path, corpus, boot=500)
    for facet in FACETS:
        s = res["sections"]["chunk"]["all"]["1"][facet]["generation"]
        assert s["n_identical_texts"] == s["n"], (facet, s["n_identical_texts"], s["n"])
        assert s["distinct"]["n"] == 0
        assert s["distinct"]["rho"] is None
    other = build_corpus(tmp_path / "split", vary=True)
    _o, res2 = run_check(tmp_path / "split", other, boot=500)
    for facet in FACETS:
        s = res2["sections"]["chunk"]["all"]["1"][facet]["generation"]
        assert s["n_identical_texts"] == 0
        assert s["distinct"]["n"] == s["n"]
        assert s["distinct"]["rho"] == pytest.approx(s["rho"])


# ------------------------------------------------------------------ the CLI paths

def test_strings_out_lists_every_string_the_check_needs(tmp_path):
    corpus = build_corpus(tmp_path)
    target = tmp_path / "strings.jsonl"
    argv = ["--texts", str(corpus["texts"]), "--views", str(corpus["views"]),
            "--out", str(tmp_path / "so"), "--strings-out", str(target)]
    assert fc.main(argv) == 0
    listed = {}
    for line in target.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        assert fc.sha256_of(rec["text"]) == rec["sha"]
        listed[rec["sha"]] = rec["text"]
    want = set()
    for c in CHUNKS:
        want.update(fc.sha256_of(t) for t in TAGS[c])
    for run in sorted(corpus["views"].glob("*/w*")):
        variant = run.parent.name
        for path in sorted(run.glob("*.json")):
            rec = json.loads(path.read_text(encoding="utf-8"))
            plain, strip = fc.file_strings(rec, variant, TAGS[rec["chunk_id"]])
            want.update(fc.sha256_of(s) for s in plain + strip)
    assert want <= set(listed), f"{len(want - set(listed))} strings missing"
    # and nothing the check does not need
    assert set(listed) == want
    # the listing is sufficient: with vectors for exactly these strings and nothing else, the
    # check runs without asking for one more
    npz = tmp_path / "listed.npz"
    every = set(corpus["plan"].want) | {t for c in CHUNKS for t in TAGS[c]}
    every |= set(stripped_strings(corpus))
    surplus = [s for s in every if fc.sha256_of(s) not in listed]
    corpus["plan"].npz(npz, extra_strings=stripped_strings(corpus), drop=surplus)
    argv = ["--texts", str(corpus["texts"]), "--views", str(corpus["views"]),
            "--vectors", str(npz), "--out", str(tmp_path / "check2"), "--boot", "50",
            "--seed", "1"]
    for d in corpus["cf_dirs"]:
        argv += ["--cf-dir", str(d)]
    assert fc.main(argv) == 0


def test_a_missing_vector_raises_without_embed_cpu(tmp_path):
    corpus = build_corpus(tmp_path)
    npz = tmp_path / "vectors.npz"
    rec = json.loads(next((corpus["views"] / "chunk" / "w1").glob("*.json")).read_text(
        encoding="utf-8"))
    gone = fc.file_strings(rec, "chunk", TAGS[rec["chunk_id"]])[0][1]
    corpus["plan"].npz(npz, extra_strings=stripped_strings(corpus), drop=[gone])
    argv = ["--texts", str(corpus["texts"]), "--views", str(corpus["views"]),
            "--vectors", str(npz), "--out", str(tmp_path / "check"), "--boot", "50"]
    with pytest.raises(SystemExit) as err:
        fc.main(argv)
    assert "not in the preloaded vectors" in str(err.value)


def test_write_one_alone_runs_and_says_not_yet(tmp_path):
    corpus = build_corpus(tmp_path, w2=False)
    out, res = run_check(tmp_path, corpus)
    assert res["noise"]["chunk"]["have"] is False
    for variant in ("chunk", "edge"):
        for facet in FACETS:
            hit = res["sections"][variant]["all"]["1"][facet]["hit"]
            assert hit["r"] is None
            assert hit["hit_rate"] is None
            v = res["verdict"][variant]["all"][facet]
            assert v["verdict"] == "INCONCLUSIVE"
            assert "write 2 absent" in v["deciding"]
    text = (out / "report.md").read_text(encoding="utf-8")
    assert "Write 2 is absent" in text


def test_report_and_verdict_tables_are_written(tmp_path):
    corpus = build_corpus(tmp_path)
    out, res = run_check(tmp_path, corpus)
    text = (out / "report.md").read_text(encoding="utf-8")
    for head in ("## 0. Units, keys, inclusion", "## 1. Writer noise",
                 "## 2. Facet isolation", "## 3. Tag isolation", "## 4. Δ_topic holds",
                 "## 5. Generation agreement", "## 6. Hit rate", "## 7. Distributions",
                 "# 8. The `edge` tag-stripped diagnostic", "## Verdict"):
        assert head in text, head
    assert set(res["verdict"]) == {"chunk", "edge"}
    for variant in ("chunk", "edge"):
        assert set(res["verdict"][variant]) == {"all", "no_nothing"}
        for facet in FACETS:
            assert res["verdict"][variant]["all"][facet]["verdict"] in (
                "PASS", "KILL", "INCONCLUSIVE")
    reg = (out / "register.md").read_text(encoding="utf-8")
    assert "not given" in reg

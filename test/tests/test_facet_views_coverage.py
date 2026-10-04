import json

import pytest

from graph import facet_views_coverage as cv
from graph.facet_edits import FACETS

CHUNK = "cc0"

TAGS = ["alpha phrase", "beta phrase"]

ORIGINAL = ("The migration ran on Friday because the audit finished. "
            "The rollback waited for the sunset window.")


def cf(text, edits, changed=True, ok=True):
    return {"note": "n", "edits": edits, "text": text, "applied": len(edits),
            "asked": len(edits), "changed": changed, "problems": [],
            "reconstruction_ok": ok}


def write_corpus(tmp_path, per_edge):
    """`per_edge` is {tag: {facet: (counterfactual text, edits)}}; the rest read unchanged."""
    texts = tmp_path / "texts.jsonl"
    rows = [{"sha": cv.sha256_of(ORIGINAL), "text": ORIGINAL, "chunk_id": CHUNK,
             "kind": "slack", "product": "P", "tags": TAGS,
             "origins": [{"generation": "original"}]}]
    edges = []
    for tag in TAGS:
        edge = {"t": tag, "matched": True}
        for facet in FACETS:
            got = per_edge.get(tag, {}).get(facet)
            if got is None:
                edge[facet] = cf(ORIGINAL, [], changed=False)
                continue
            body, edits = got
            edge[facet] = cf(body, edits)
            if all(r["sha"] != cv.sha256_of(body) for r in rows):
                rows.append({"sha": cv.sha256_of(body), "text": body, "chunk_id": CHUNK,
                             "kind": "slack", "product": "P", "tags": TAGS,
                             "origins": [{"generation": "main", "tag": tag,
                                          "facet": facet}]})
        edges.append(edge)
    with open(texts, "w", encoding="utf-8") as f:
        f.write(json.dumps({"header": {"ids": 1}}) + "\n")
        for r in rows:
            f.write(json.dumps(r) + "\n")
    cf_dir = tmp_path / "counterfactuals" / "db"
    cf_dir.mkdir(parents=True, exist_ok=True)
    (cf_dir / f"{CHUNK}__0.json").write_text(json.dumps({
        "chunk_id": CHUNK, "kind": "slack", "product": "P", "tags": TAGS,
        "given": len(TAGS), "answered": len(TAGS), "complete": True, "format": "edits",
        "text": ORIGINAL, "edges": edges, "prompt_sha256": "p"}), encoding="utf-8")
    return texts, cf_dir, rows


def write_views(tmp_path, bodies, view_of):
    """`view_of(body, facet, tag) -> str` for every text the run will look at."""
    run = tmp_path / "views" / "chunk" / "w1"
    run.mkdir(parents=True, exist_ok=True)
    for body in bodies:
        views = {"description": f"a description of {body[:20]}"}
        for facet in FACETS:
            views[facet] = view_of(body, facet, None)
        (run / f"{cv.sha256_of(body)}.json").write_text(json.dumps({
            "sha": cv.sha256_of(body), "chunk_id": CHUNK, "kind": "slack", "product": "P",
            "variant": "chunk", "write": 1, "origins": [], "prompt_sha256": "p",
            "model": "m", "problems": [], "raw": [], "views": views,
            "nothing_lines": 0}), encoding="utf-8")
    return tmp_path / "views"


def test_a_word_another_edit_puts_back_is_not_removed(tmp_path):
    """The net rule: edit 1 takes `sunset` out of its span, edit 2's replacement puts it back,
    so the text never lost it and it is not a removed word."""
    body = ORIGINAL.replace("on Friday", "later").replace("audit finished",
                                                          "sunset audit finished")
    edits = [{"find": "on Friday because the sunset", "replace": "later because the"},
             {"find": "audit finished", "replace": "sunset audit finished"}]
    texts, cf_dir, rows = write_corpus(tmp_path, {TAGS[0]: {FACETS[0]: (body, edits)}})
    got = cv.read_rows([cf_dir], cv.read_texts(texts))
    assert len(got) == 1
    removed = set(got[0]["removed"])
    assert "sunset" not in removed, removed
    assert "friday" in removed
    # the per-edit reading would have counted it
    per_edit = set()
    for ed in edits:
        per_edit |= cv.words(ed["find"]) - cv.words(ed["replace"])
    assert "sunset" in per_edit


def test_the_control_is_the_same_facet_and_another_tag(tmp_path, capsys):
    """Under `same-facet` the control row must share the facet and differ in tag; `any` takes
    the first reading back, where the same tag's other facets counted."""
    a_body = ORIGINAL.replace("Friday", "Monday")
    b_body = ORIGINAL.replace("sunset window", "maintenance window")
    other_facet_body = ORIGINAL.replace("audit", "review")
    texts, cf_dir, rows = write_corpus(tmp_path, {
        TAGS[0]: {FACETS[0]: (a_body, [{"find": "Friday", "replace": "Monday"}]),
                  FACETS[1]: (other_facet_body, [{"find": "audit", "replace": "review"}])},
        TAGS[1]: {FACETS[0]: (b_body, [{"find": "sunset window",
                                        "replace": "maintenance window"}])},
    })
    bodies = [r["text"] for r in rows]
    views = write_views(tmp_path, bodies, lambda body, facet, tag: body)
    argv = ["--texts", str(texts), "--views", str(views), "--variant", "chunk",
            "--write", "1", "--cf-dir", str(cf_dir), "--rows-out",
            str(tmp_path / "rows.jsonl")]
    assert cv.main(argv) == 0
    out = capsys.readouterr().out
    assert "control same-facet" in out
    detail = [json.loads(l) for l in (tmp_path / "rows.jsonl").read_text(
        encoding="utf-8").splitlines()]
    f0 = [d for d in detail if d["facet"] == FACETS[0]]
    assert len(f0) == 2
    assert all(d["control_hit"] is not None for d in f0)
    # the facet-1 row is the only row of its facet, so same-facet leaves it no control
    f1 = [d for d in detail if d["facet"] == FACETS[1]]
    assert len(f1) == 1 and f1[0]["control_hit"] is None
    # under `any` it gets one, from another facet's edit
    assert cv.main(argv + ["--control", "any"]) == 0
    assert "control any" in capsys.readouterr().out
    detail = [json.loads(l) for l in (tmp_path / "rows.jsonl").read_text(
        encoding="utf-8").splitlines()]
    f1 = [d for d in detail if d["facet"] == FACETS[1]]
    assert f1[0]["control_hit"] is not None


def test_a_control_never_comes_from_the_same_tag(tmp_path):
    """`same-facet` excludes the row itself by tag, so a chunk whose only other row of that
    facet is the same tag has no control at all."""
    a_body = ORIGINAL.replace("Friday", "Monday")
    other = ORIGINAL.replace("audit", "review")
    texts, cf_dir, rows = write_corpus(tmp_path, {
        TAGS[0]: {FACETS[0]: (a_body, [{"find": "Friday", "replace": "Monday"}]),
                  FACETS[1]: (other, [{"find": "audit", "replace": "review"}])},
    })
    bodies = [r["text"] for r in rows]
    views = write_views(tmp_path, bodies, lambda body, facet, tag: body)
    argv = ["--texts", str(texts), "--views", str(views), "--variant", "chunk",
            "--write", "1", "--cf-dir", str(cf_dir), "--rows-out",
            str(tmp_path / "rows.jsonl")]
    assert cv.main(argv) == 0
    detail = [json.loads(l) for l in (tmp_path / "rows.jsonl").read_text(
        encoding="utf-8").splitlines()]
    assert detail and all(d["control_hit"] is None for d in detail)


def test_coverage_and_following_are_read_off_the_views(tmp_path):
    a_body = ORIGINAL.replace("Friday", "Monday")
    texts, cf_dir, rows = write_corpus(
        tmp_path, {TAGS[0]: {FACETS[0]: (a_body, [{"find": "Friday",
                                                   "replace": "Monday"}])}})
    bodies = [r["text"] for r in rows]

    def view_of(body, facet, _tag):
        return body if facet == FACETS[0] else "a view that names nothing of the text"

    views = write_views(tmp_path, bodies, view_of)
    argv = ["--texts", str(texts), "--views", str(views), "--variant", "chunk",
            "--write", "1", "--cf-dir", str(cf_dir), "--rows-out",
            str(tmp_path / "rows.jsonl")]
    assert cv.main(argv) == 0
    detail = [json.loads(l) for l in (tmp_path / "rows.jsonl").read_text(
        encoding="utf-8").splitlines()]
    row = [d for d in detail if d["facet"] == FACETS[0]][0]
    assert row["removed_in_view_C"] == ["friday"]
    assert row["removed_still_in_view_Cf"] == []

"""Does a facet view even reach the place a counterfactual edited? A text-level diagnostic for
the facet-view pilot (`output/facet_views/PROGRESS.md`), no embedder, no model call.

For every changed, reconstructed counterfactual C' = C^(−F,T) the teacher's edit list says which
span of C was replaced. The content words that the edit REMOVED (in `find`, not in `replace`) are
looked up in the write-1 views of the original C and of C': a view that never carries a word of
the edited span cannot register the edit through cos(tag, view), whatever the embedder does.

Per facet, per variant, over the intervention rows:
  removed>0      rows whose edit removed at least one content word
  covered        rows where the targeted facet's view of C carries >= 1 removed word
  covered-any    ... where ANY of the five views of C (description + four) carries one
  control        the same lookup with the removed words of ANOTHER row of the same chunk
                 under the SAME facet and a different tag (`--control same-facet`, the
                 default) — the chance THIS facet's view carries another phrase's edited
                 span, which is the comparison the covered column needs. `--control any`
                 takes any other row of the chunk, the first reading, where a different
                 facet's edit and the same tag's other facets both counted.
  followed       among covered rows, the share where the targeted view of C' carries NONE of
                 the removed words the view of C carried (the view moved with the edit)
  kept           ... where it still carries all of them

Content words: [a-z0-9]{4,} after lowercasing, minus a short list of function words; words of
time relation (before, after, when, until, next, ...) are content here, since the temporal
edits turn on them. A word is REMOVED only if no edit of the same list puts it back: the set is
the union of the `find` words minus the union of the `replace` words, so a word moved from one
edit's span into another's replacement is not counted as gone from the text. Per-row detail
goes to `--rows-out` as jsonl.

    python test/graph/facet_views_coverage.py --texts output/facet_views/pilot/texts.jsonl \\
        --views output/facet_views/pilot/views --variant chunk --write 1 \\
        --cf-dir output/facet_neural/counterfactuals/herb-eval-volmax \\
        --cf-dir output/facet_neural/counterfactuals_repeat/herb-eval-volmax
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "prod", ROOT / "test"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from graph.facet_edits import FACETS  # noqa: E402

STOP = frozenset("""that with this from have were been they their which what will would about into
than then them there these those also only such some more most very just like being does each
other where while shall might could should still though because since through under between
against without within across during""".split())

WORD = re.compile(r"[a-z0-9]{4,}")


def words(s: str) -> set:
    return {w for w in WORD.findall((s or "").lower()) if w not in STOP}


def sha256_of(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def read_texts(path: Path) -> dict:
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if "header" in r:
                continue
            out[r["sha"]] = r
    return out


def read_views(views_root: Path, variant: str, write: int) -> dict:
    """{text sha: views} — chunk: the five strings; edge: {phrase casefold: four strings}."""
    run = views_root / variant / f"w{write}"
    out = {}
    for p in sorted(run.glob("*.json")):
        if p.name.startswith("manifest.") or p.name.endswith(".failed.json"):
            continue
        rec = json.loads(p.read_text(encoding="utf-8"))
        v = rec.get("views")
        if variant == "chunk":
            if isinstance(v, dict) and all(isinstance(v.get(k), str) for k in
                                           ("description",) + FACETS):
                out[rec["sha"]] = v
        else:
            if isinstance(v, list) and rec.get("complete"):
                out[rec["sha"]] = {str(r.get("t", "")).casefold(): r for r in v
                                   if isinstance(r, dict)}
    return out


def read_rows(cf_dirs: list, texts: dict) -> list:
    rows = []
    for d in cf_dirs:
        gen = "repeat" if "counterfactuals_repeat" in str(d) else "main"
        for p in sorted(Path(d).glob("*.json")):
            if p.name.startswith("manifest.") or p.name.endswith(".failed.json"):
                continue
            rec = json.loads(p.read_text(encoding="utf-8"))
            orig = rec["text"]
            osha = sha256_of(orig)
            for e in rec.get("edges", []):
                for f in FACETS:
                    c = e.get(f) or {}
                    if not c.get("changed") or not c.get("reconstruction_ok"):
                        continue
                    csha = sha256_of(c["text"])
                    if osha not in texts or csha not in texts:
                        continue
                    # net over the whole edit list, not per edit: a word another edit of
                    # the same list reintroduces never left the text
                    finds, replaces = set(), set()
                    for ed in c.get("edits") or []:
                        finds |= words(ed.get("find", ""))
                        replaces |= words(ed.get("replace", ""))
                    removed = finds - replaces
                    added = replaces - finds
                    rows.append({"chunk_id": rec["chunk_id"], "tag": e["t"], "facet": f,
                                 "generation": gen, "orig_sha": osha, "cf_sha": csha,
                                 "removed": sorted(removed), "added": sorted(added)})
    return rows


def view_text(views: dict, variant: str, sha: str, facet: str, tag: str) -> str | None:
    v = views.get(sha)
    if v is None:
        return None
    if variant == "chunk":
        return v.get(facet)
    r = v.get(tag.casefold())
    return r.get(facet) if r else None


def all_views_text(views: dict, variant: str, sha: str, tag: str) -> str | None:
    v = views.get(sha)
    if v is None:
        return None
    if variant == "chunk":
        return " ".join(v[k] for k in ("description",) + FACETS)
    r = v.get(tag.casefold())
    return " ".join(r[k] for k in FACETS) if r else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="does the view reach the edited place")
    ap.add_argument("--texts", required=True)
    ap.add_argument("--views", required=True)
    ap.add_argument("--variant", default="chunk", choices=("chunk", "edge"))
    ap.add_argument("--write", type=int, default=1)
    ap.add_argument("--cf-dir", action="append", default=[], dest="cf_dirs", required=True)
    ap.add_argument("--rows-out", default="")
    ap.add_argument("--control", default="same-facet", choices=("same-facet", "any"),
                    help="which other row lends its removed words as the control: another tag "
                         "of the same chunk under the same facet (the default), or any other "
                         "(tag, facet) of the chunk (the first reading)")
    ap.add_argument("--seed", type=int, default=20260918)
    args = ap.parse_args(argv)

    texts = read_texts(Path(args.texts))
    views = read_views(Path(args.views), args.variant, args.write)
    rows = read_rows([Path(d) for d in args.cf_dirs], texts)
    rng = random.Random(args.seed)
    by_chunk = defaultdict(list)
    for r in rows:
        by_chunk[r["chunk_id"]].append(r)

    stats = {f: defaultdict(int) for f in FACETS}
    detail = []
    for r in rows:
        f = r["facet"]
        vc = view_text(views, args.variant, r["orig_sha"], f, r["tag"])
        vcf = view_text(views, args.variant, r["cf_sha"], f, r["tag"])
        if vc is None or vcf is None:
            stats[f]["unmeasured"] += 1
            continue
        st = stats[f]
        st["rows"] += 1
        removed = set(r["removed"])
        if not removed:
            st["no_removed_words"] += 1
            continue
        st["removed>0"] += 1
        wc, wcf = words(vc), words(vcf)
        hit = removed & wc
        # the control must be the same question asked of a span this view had no reason to
        # carry: the same facet's view, another phrase's edit. `--control any` is the first
        # reading, where another facet's edit and the same tag's other facets both counted.
        if args.control == "same-facet":
            others = [o for o in by_chunk[r["chunk_id"]]
                      if o["facet"] == r["facet"] and o["tag"] != r["tag"] and o["removed"]]
        else:
            others = [o for o in by_chunk[r["chunk_id"]]
                      if (o["tag"], o["facet"]) != (r["tag"], r["facet"]) and o["removed"]]
        ctrl_hit = None
        if others:
            o = rng.choice(others)
            ctrl_hit = bool(set(o["removed"]) & wc)
            st["control_n"] += 1
            st["control_hit"] += int(ctrl_hit)
        wall = words(all_views_text(views, args.variant, r["orig_sha"], r["tag"]) or "")
        st["covered_any"] += int(bool(removed & wall))
        st["view_identical"] += int(vc.strip() == vcf.strip())
        if hit:
            st["covered"] += 1
            still = hit & wcf
            if not still:
                st["followed"] += 1
            elif still == hit:
                st["kept"] += 1
            else:
                st["partly"] += 1
            # did the C' view pick up an added word instead?
            st["added_appears_in_cf"] += int(bool(set(r["added"]) & wcf))
        detail.append({**r, "removed_in_view_C": sorted(hit),
                       "removed_still_in_view_Cf": sorted(hit & wcf),
                       "control_hit": ctrl_hit, "view_C": vc, "view_Cf": vcf})

    print(f"facet_views_coverage | variant {args.variant} w{args.write} | rows {len(rows)} "
          f"| views on file {len(views)} | control {args.control} | removed words net of the "
          f"edit list")
    print("| facet | rows | unmeasured | removed>0 | covered | covered-any | control | "
          "followed | partly | kept | added-word in C' view | view identical |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for f in FACETS:
        st = stats[f]
        n = st["removed>0"] or 1
        cov = st["covered"] or 1
        ctrl = f"{st['control_hit'] / st['control_n']:.3f} (n={st['control_n']})" \
            if st["control_n"] else "—"
        print(f"| {f} | {st['rows']} | {st['unmeasured']} | {st['removed>0']} | "
              f"{st['covered'] / n:.3f} | {st['covered_any'] / n:.3f} | {ctrl} | "
              f"{st['followed'] / cov:.3f} | {st['partly'] / cov:.3f} | {st['kept'] / cov:.3f} | "
              f"{st['added_appears_in_cf'] / cov:.3f} | {st['view_identical']} |")
    if args.rows_out:
        out = Path(args.rows_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            for d in detail:
                fh.write(json.dumps(d, ensure_ascii=False) + "\n")
        print(f"-> {out} ({len(detail)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

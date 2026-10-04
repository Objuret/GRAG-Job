"""The candidate relevance rulers R(T,C), measured on the counterfactual files.

Correction 2 of the specification leaves R unresolved and names three things to compare:
whole-chunk cosine, sentence-max cosine, and at least one sentence-level aggregate that is not
a hard maximum, with a generic cross-encoder reranker as a candidate only. This file computes
every candidate on the same counterfactuals and stores each one's output separately. It picks
nothing; `facet_rulers_report.py` reads what it writes.

The five candidates, all on the tag phrase against the chunk TEXT (not the description — the
counterfactual modifies the text):

  chunk_cos     cos(E(tag), E(text)) — the whole chunk, one vector.
  sent_max      max over the text's sentences of cos(E(tag), E(sentence)).
  sent_mean     the mean of the same cosines — a soft aggregate with no free number.
  changed_span  the same cosine read only on the sentences the counterfactual changed, on each
                side of the intervention: it cannot switch to a sentence the intervention never
                touched. Undefined (null) when the intervention changed nothing.
  xenc          a generic cross-encoder reranker's score for (tag, text). A candidate only.

E is the harness embedder (`prod/harness/embed.py`), with the `passage: ` prefix on both the
tag and the text — the prefix the graph's own `Tag.emb` was built under (docs/ENVIRONMENT.md:
cosine 0.993 against the stored vectors, 0.44 under the query prefix). Sentences are spaCy
`en_core_web_sm`, the splitter `facet_stats` already uses.

Every vector is cached by sha256 of the exact string embedded, so the sentences an intervention
did not touch are embedded once for the whole chunk.

Nothing here is written to the graph.

    python test/graph/facet_rulers.py --in output/facet_neural/smoke/edits \\
        --out output/facet_neural/rulers/smoke_edits
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "prod", ROOT / "test"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from harness import embed as hembed
from graph.facet_edits import FACETS, apply_edits  # noqa: F401

EMBED_RULERS = ("chunk_cos", "sent_max", "sent_mean", "changed_span")

XENC_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

RULERS = EMBED_RULERS + ("xenc",)

_NLP = None
_XENC = None

# Off when the run was given no chunk-sized vectors; `chunk_cos` then reads null everywhere
# and every other ruler is unaffected.
WHOLE_TEXTS = True


def _nlp():
    """`en_core_web_sm` with only what sets a sentence boundary loaded.

    The boundaries come from the parser, which reads tok2vec and nothing else; the tagger,
    attribute ruler, lemmatizer and NER are dead weight here and cost 2.7x the wall time.
    Checked on 30 counterfactual texts of 1,000+ chars: the (text, start, end) triples are
    identical to the full pipeline's on every sentence."""
    global _NLP
    if _NLP is None:
        import spacy
        _NLP = spacy.load("en_core_web_sm",
                          exclude=["ner", "lemmatizer", "attribute_ruler", "tagger"])
    return _NLP


def _xenc():
    global _XENC
    if _XENC is None:
        from sentence_transformers import CrossEncoder
        _XENC = CrossEncoder(XENC_MODEL, device="cpu")
    return _XENC


# ------------------------------------------------------------------ sentences and spans

_SENTS: dict = {}

_SENT_DISK: Path | None = None

_SENT_NEW = 0


def load_sentence_cache(path):
    """Read a previous run's splits. The key is the sha256 of the exact string, so a cache
    written over one counterfactual set is valid for any other."""
    global _SENT_DISK
    _SENT_DISK = Path(path)
    if not _SENT_DISK.is_file():
        return 0
    n = 0
    with _SENT_DISK.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            _SENTS[r["sha"]] = [tuple(x) for x in r["sents"]]
            n += 1
    return n


def save_sentence_cache():
    if _SENT_DISK is None:
        return 0
    _SENT_DISK.parent.mkdir(parents=True, exist_ok=True)
    with _SENT_DISK.open("w", encoding="utf-8") as f:
        for sha, sents in _SENTS.items():
            f.write(json.dumps({"sha": sha, "sents": [list(s) for s in sents]},
                               ensure_ascii=False) + "\n")
    return len(_SENTS)


def sentences(text: str) -> list:
    """(sentence text, start char, end char) for every non-empty sentence.

    Cached on the exact text: the null pass reads one chunk's sentences once per (tag,
    counterfactual) pair, which is thousands of parses of the same few strings. The same cache
    is written to disk so the string-collection pass and the measurement pass do not each pay
    spaCy for the whole counterfactual set."""
    global _SENT_NEW
    key = hashlib.sha256(text.encode("utf-8")).hexdigest()
    hit = _SENTS.get(key)
    if hit is not None:
        return hit
    out = []
    for s in _nlp()(text).sents:
        t = s.text.strip()
        if t:
            out.append((t, s.start_char, s.end_char))
    _SENTS[key] = out
    _SENT_NEW += 1
    return out


def edit_spans(text: str, edits: list) -> tuple:
    """(spans in the original, spans in the counterfactual) for the edits that applied.

    A pure deletion leaves a zero-length span on the counterfactual side; the sentence holding
    that point is the one the intervention emptied into, so `sentences_touching` still finds a
    sentence there. Recomputed from the stored edits and the stored original, never trusted
    from the model."""
    placed = []
    for e in edits or []:
        if not isinstance(e, dict):
            continue
        find, repl = e.get("find"), e.get("replace")
        if not isinstance(find, str) or not isinstance(repl, str) or not find:
            continue
        if text.count(find) != 1:
            continue
        start = text.index(find)
        placed.append((start, start + len(find), repl))
    placed.sort()
    orig, new, cursor, shift = [], [], 0, 0
    for start, end, repl in placed:
        if start < cursor:
            continue
        cursor = end
        orig.append((start, end))
        new.append((start + shift, start + shift + len(repl)))
        shift += len(repl) - (end - start)
    return orig, new


def sentences_touching(sents: list, spans: list) -> list:
    """Every sentence whose character range meets one of the spans. A zero-length span meets
    the sentence it falls inside or at the edge of."""
    hit = []
    for i, (_t, a, b) in enumerate(sents):
        for s, e in spans:
            if s <= b and e >= a:
                hit.append(i)
                break
    return hit


# ------------------------------------------------------------------ the embedding cache

class Vectors:
    """One unit-norm vector per exact string, kept for the life of the run.

    `collect` records what would be embedded and embeds nothing, so the string set can be
    shipped to a machine with a GPU. `preload` fills the cache from what that machine returned;
    with `frozen` set, a string that is not in it is a fault, not a silent CPU embed."""

    def __init__(self):
        self.by_sha: dict = {}
        self.embedded = 0
        self.hits = 0
        self.seconds = 0.0
        self.wanted: dict = {}
        self.collect_only = False
        self.frozen = False

    def preload(self, path) -> int:
        z = np.load(path, allow_pickle=False)
        shas, mat = z["sha"], z["vec"].astype(np.float32)
        for sha, v in zip(shas, mat):
            self.by_sha[str(sha)] = v
        return len(shas)

    def get(self, texts: list) -> np.ndarray:
        shas = [hashlib.sha256(t.encode("utf-8")).hexdigest() for t in texts]
        want, seen = [], set()
        for t, sha in zip(texts, shas):
            if sha not in self.by_sha and sha not in seen:
                seen.add(sha)
                want.append((sha, t))
        if want and self.collect_only:
            for sha, t in want:
                self.wanted[sha] = t
            zero = np.zeros(1, dtype=np.float32)
            for sha, _t in want:
                self.by_sha[sha] = zero
            self.embedded += len(want)
            return np.stack([self.by_sha[s] for s in shas])
        if want and self.frozen:
            raise RuntimeError(
                f"facet_rulers: {len(want)} strings are not in the preloaded vectors "
                f"(first sha {want[0][0][:12]}, {len(want[0][1])} chars). The vector file was "
                f"built from a different counterfactual set.")
        if want:
            t0 = time.perf_counter()
            mat, _c, _ti, _to, _s = hembed._embed([t for _sha, t in want], "passage", bar=False)
            self.seconds += time.perf_counter() - t0
            self.embedded += len(want)
            for (sha, _t), v in zip(want, mat):
                self.by_sha[sha] = np.asarray(v, dtype=np.float32)
        self.hits += len(texts) - len(want)
        return np.stack([self.by_sha[s] for s in shas])


# ------------------------------------------------------------------ the rulers

def embed_rulers(tag: str, text: str, vecs: Vectors, spans: list | None) -> dict:
    """The four embedding rulers for one (tag, text). `spans` are the character ranges the
    intervention touched in THIS text; None or empty makes `changed_span` null."""
    sents = sentences(text)
    if not sents:
        sents = [(text.strip() or " ", 0, len(text))]
    strings = ([tag, text] if WHOLE_TEXTS else [tag]) + [s for s, _a, _b in sents]
    mat = vecs.get(strings)
    if WHOLE_TEXTS:
        tv, cv, sv = mat[0], mat[1], mat[2:]
    else:
        tv, cv, sv = mat[0], None, mat[1:]
    cos = sv @ tv
    out = {
        "chunk_cos": (float(cv @ tv) if cv is not None else None),
        "sent_max": float(cos.max()),
        "sent_mean": float(cos.mean()),
        "changed_span": None,
        "n_sentences": len(sents),
        "argmax_sentence": int(cos.argmax()),
    }
    if spans:
        hit = sentences_touching(sents, spans)
        if hit:
            out["changed_span"] = float(max(cos[i] for i in hit))
            out["changed_sentences"] = len(hit)
    return out


def xenc_scores(pairs: list) -> list:
    if not pairs:
        return []
    return [float(x) for x in _xenc().predict(pairs, show_progress_bar=False)]


# ------------------------------------------------------------------ one chunk file

def warm_chunk(rec: dict, vecs: Vectors, whole_texts: bool = True) -> int:
    """Embed every string this chunk will need in one request.

    Without it each counterfactual embeds its two or three new strings on its own, which on a
    GPU is a batch of three. The set is the same either way; only the batching differs.

    `whole_texts` off drops the chunk-sized strings, which only `chunk_cos` reads. They are
    ~45 texts of ~3,400 chars a chunk and they cost the card more than everything else put
    together (1.7 strings/s against 93 for sentences), so a run whose ruler is sentence-level
    should not pay for them."""
    text = rec["text"]
    strings = ([text] if whole_texts else []) + [s for s, _a, _b in sentences(text)]
    for edge in rec["edges"]:
        strings.append(edge["t"])
        for facet in FACETS:
            new_text = edge[facet]["text"]
            if whole_texts:
                strings.append(new_text)
            if new_text != text:
                strings.extend(s for s, _a, _b in sentences(new_text))
    before = vecs.embedded
    vecs.get(strings)
    return vecs.embedded - before


def measure_chunk(rec: dict, vecs: Vectors, with_xenc: bool) -> dict:
    """Every ruler on every (tag, facet) of one counterfactual file.

    R_original is measured once per (tag, ruler) on the untouched text, exactly as R_remaining
    is measured on the counterfactual — same preprocessing, same model, same scoring. For
    `changed_span` the original side is read on the same sentences the intervention touched, so
    the two sides of the delta are the same reading of the same place."""
    text = rec["text"]
    rows, xpairs, xwhere = [], [], []
    for edge in rec["edges"]:
        tag = edge["t"]
        for facet in FACETS:
            cf = edge[facet]
            new_text = cf["text"]
            if rec.get("format") == "edits":
                o_spans, n_spans = edit_spans(text, cf.get("edits") or [])
            else:
                o_spans = n_spans = ([(0, len(text))] if cf["changed"] else [])
            orig = embed_rulers(tag, text, vecs, o_spans)
            rem = embed_rulers(tag, new_text, vecs, n_spans)
            row = {
                "chunk_id": rec["chunk_id"], "kind": rec.get("kind"),
                "product": rec.get("product"), "tag": tag, "facet": facet,
                "changed": bool(cf["changed"]),
                "reconstruction_ok": bool(cf["reconstruction_ok"]),
                "n_edits": (len(cf["edits"]) if cf.get("edits") is not None else None),
                "note": cf.get("note", ""),
                "cf_sha256": hashlib.sha256(new_text.encode("utf-8")).hexdigest(),
                "R": {}, "R_cf": {}, "delta": {},
            }
            for r in EMBED_RULERS:
                a, b = orig[r], rem[r]
                row["R"][r] = a
                row["R_cf"][r] = b
                if not row["changed"]:
                    # The teacher said this facet contributes nothing to this edge and made no
                    # change. The counterfactual IS the chunk, so R(T,C) - R(T,C) = 0 exactly,
                    # on every ruler, whether or not that ruler could be read here. It is the
                    # target by construction, not a missing measurement. This test comes first:
                    # `changed_span` has no span to read on an unchanged text and would
                    # otherwise report the zero as unmeasured.
                    row["delta"][r] = 0.0
                elif a is None or b is None:
                    row["delta"][r] = None
                else:
                    row["delta"][r] = (None if a is None or b is None else a - b)
            row["n_sentences"] = orig["n_sentences"]
            row["n_sentences_cf"] = rem["n_sentences"]
            row["argmax_moved"] = orig["argmax_sentence"] != rem["argmax_sentence"]
            rows.append(row)
            if with_xenc:
                xwhere.append(len(rows) - 1)
                xpairs.append((tag, text))
                xpairs.append((tag, new_text))
    if with_xenc and xpairs:
        scores = xenc_scores(xpairs)
        for j, i in enumerate(xwhere):
            a, b = scores[2 * j], scores[2 * j + 1]
            rows[i]["R"]["xenc"] = a
            rows[i]["R_cf"]["xenc"] = b
            rows[i]["delta"]["xenc"] = a - b
    return {"chunk_id": rec["chunk_id"], "rows": rows}


# ------------------------------------------------------------------ the null

def null_rows(rec: dict, vecs: Vectors, with_xenc: bool, max_tags: int = 0) -> list:
    """Each ruler's own noise, on its own scale, from this same generative process.

    For tag T, every counterfactual built for a DIFFERENT tag whose changed sentences do not
    meet T's own sentences: the intervention was aimed elsewhere and touched nothing T is read
    on, so a ruler that measures the T-specific relationship should not move. The spread of
    these deltas is that ruler's noise. COS_NOISE is not inherited into any of them."""
    text = rec["text"]
    sents = sentences(text)
    if not sents:
        return []
    strings = [s for s, _a, _b in sents]
    tags = [e["t"] for e in rec["edges"]]
    mat = vecs.get(tags + strings)
    tvecs, svecs = mat[:len(tags)], mat[len(tags):]
    cosmat = svecs @ tvecs.T                      # sentences x tags
    own = {}
    for j, tag in enumerate(tags):
        best = int(cosmat[:, j].argmax())
        own[tag] = {best}

    rows, xpairs, xwhere = [], [], []
    for edge in rec["edges"]:
        src = edge["t"]
        for facet in FACETS:
            cf = edge[facet]
            if not cf["changed"] or not cf["reconstruction_ok"]:
                continue
            if rec.get("format") == "edits":
                o_spans, n_spans = edit_spans(text, cf.get("edits") or [])
            else:
                continue                          # a full rewrite touches the whole text
            touched = set(sentences_touching(sents, o_spans))
            eligible = [t for t in tags if t != src and not (own[t] & touched)]
            if max_tags:
                # A fixed, reproducible slice of the chunk's own tag order, not a sample: the
                # cross-encoder cannot read every pair on a CPU and the paired test needs the
                # same rule on every ruler.
                eligible = eligible[:max_tags]
            for tag in eligible:
                orig = embed_rulers(tag, text, vecs, o_spans)
                rem = embed_rulers(tag, cf["text"], vecs, n_spans)
                row = {"chunk_id": rec["chunk_id"], "tag": tag, "source_tag": src,
                       "facet": facet, "cf_sha256": hashlib.sha256(
                           cf["text"].encode("utf-8")).hexdigest(), "delta": {}}
                for r in EMBED_RULERS:
                    a, b = orig[r], rem[r]
                    row["delta"][r] = None if (a is None or b is None) else a - b
                row["argmax_moved"] = orig["argmax_sentence"] != rem["argmax_sentence"]
                rows.append(row)
                if with_xenc:
                    xwhere.append(len(rows) - 1)
                    xpairs.append((tag, text))
                    xpairs.append((tag, cf["text"]))
    if with_xenc and xpairs:
        scores = xenc_scores(xpairs)
        for j, i in enumerate(xwhere):
            rows[i]["delta"]["xenc"] = scores[2 * j] - scores[2 * j + 1]
    return rows


# ------------------------------------------------------------------ cli

def load_chunks(d: Path) -> list:
    out = []
    for p in sorted(Path(d).glob("*.json")):
        if p.name.startswith("manifest.") or p.name.endswith(".failed.json"):
            continue
        rec = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(rec, dict) and isinstance(rec.get("edges"), list):
            out.append(rec)
    return out


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="every candidate ruler on the counterfactuals")
    ap.add_argument("--in", dest="src", required=True, help="a counterfactual output dir")
    ap.add_argument("--out", required=True, help="where the per-ruler measurements go")
    ap.add_argument("--no-xenc", action="store_true", help="skip the cross-encoder candidate")
    ap.add_argument("--no-null", action="store_true", help="skip the per-ruler noise rows")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--null-tags", type=int, default=0,
                    help="cap the other tags each counterfactual is read against; 0 is every eligible tag")
    ap.add_argument("--device", default="", help="cpu | cuda — the harness embedder's device "
                                                 "for this run; the model, revision, dtype "
                                                 "and prefixes are unchanged")
    ap.add_argument("--batch", type=int, default=0, help="texts per encode call; 1 is the "
                                                         "harness default and is what a CPU "
                                                         "run measured")
    ap.add_argument("--strings-out", default="", help="write every string this run would "
                                                      "embed and stop; nothing is embedded")
    ap.add_argument("--vectors-in", default="", help="an .npz of sha/vec from "
                                                     "facet_embed_gpu.py; no string may be "
                                                     "missing from it")
    ap.add_argument("--no-whole-texts", action="store_true",
                    help="leave the chunk-sized strings out; only chunk_cos reads them and "
                         "they are the bulk of the GPU time")
    ap.add_argument("--sentence-cache", default="", help="a jsonl of sha -> sentence spans, "
                                                         "read at start and rewritten at the "
                                                         "end; spaCy is the slowest part and "
                                                         "this pays it once")
    args = ap.parse_args(argv)

    t0 = time.perf_counter()
    if args.device:
        hembed.EMBED_DEVICE = args.device
    if args.batch:
        hembed.EMBED_BATCH = args.batch
    print(f"facet_rulers | in {args.src} | rulers "
          f"{', '.join(RULERS if not args.no_xenc else EMBED_RULERS)} | device "
          f"{hembed.EMBED_DEVICE} | batch {hembed.EMBED_BATCH}", flush=True)
    chunks = load_chunks(Path(args.src))
    if args.limit:
        chunks = chunks[:args.limit]
    if not chunks:
        raise SystemExit(f"facet_rulers: no counterfactual files under {args.src}")
    print(f"  {len(chunks)} chunks, "
          f"{sum(len(c['edges']) for c in chunks)} tags, "
          f"{sum(len(c['edges']) for c in chunks) * len(FACETS)} counterfactuals",
          flush=True)

    global WHOLE_TEXTS
    WHOLE_TEXTS = not args.no_whole_texts

    if args.sentence_cache:
        print(f"  sentence cache: {load_sentence_cache(args.sentence_cache)} texts read from "
              f"{args.sentence_cache}", flush=True)

    if args.strings_out:
        vecs = Vectors()
        vecs.collect_only = True
        for i, rec in enumerate(chunks, 1):
            warm_chunk(rec, vecs, not args.no_whole_texts)
            if i % 10 == 0 or i == len(chunks):
                print(f"  [{i}/{len(chunks)}] {len(vecs.wanted)} distinct strings", flush=True)
        p = Path(args.strings_out)
        p.parent.mkdir(parents=True, exist_ok=True)
        chars = 0
        with p.open("w", encoding="utf-8") as f:
            for sha, t in vecs.wanted.items():
                chars += len(t)
                f.write(json.dumps({"sha": sha, "text": t}, ensure_ascii=False) + "\n")
        n = save_sentence_cache()
        print(f"strings | {len(vecs.wanted)} distinct | {chars} chars | {_SENT_NEW} texts "
              f"newly split, {n} in the sentence cache | "
              f"{time.perf_counter() - t0:.0f}s -> {p}", flush=True)
        return 0

    out = Path(args.out)
    (out / "by_chunk").mkdir(parents=True, exist_ok=True)
    vecs = Vectors()
    if args.vectors_in:
        n = vecs.preload(args.vectors_in)
        vecs.frozen = True
        print(f"  preloaded {n} vectors from {args.vectors_in}", flush=True)
    rows, nulls, skipped = [], [], []
    for i, rec in enumerate(chunks, 1):
        c0 = time.perf_counter()
        per = out / "by_chunk" / f"{rec['chunk_id']}.json"
        if per.is_file():
            try:
                cached = json.loads(per.read_text(encoding="utf-8"))
                rows.extend(cached["rows"])
                nulls.extend(cached["null"])
                print(f"  [{i}/{len(chunks)}] {rec['chunk_id']} read from disk "
                      f"({len(cached['rows'])} rows)", flush=True)
                continue
            except (ValueError, OSError, KeyError):
                pass
        try:
            fresh = warm_chunk(rec, vecs, not args.no_whole_texts)
            crows = measure_chunk(rec, vecs, not args.no_xenc)["rows"]
            n = ([] if args.no_null else
                 null_rows(rec, vecs, not args.no_xenc, args.null_tags))
        except RuntimeError as err:
            # The vector file was built before this chunk's counterfactuals existed. Skipping is
            # right: the chunk comes back when the vectors are rebuilt, and no other chunk's
            # measurement depends on it.
            skipped.append(rec["chunk_id"])
            print(f"  [{i}/{len(chunks)}] {rec['chunk_id']} SKIPPED — {err}", flush=True)
            continue
        per.write_text(json.dumps({"rows": crows, "null": n}, ensure_ascii=False),
                       encoding="utf-8")
        rows.extend(crows)
        nulls.extend(n)
        print(f"  [{i}/{len(chunks)}] {rec['chunk_id']} tags={len(rec['edges'])} "
              f"rows={len(crows)} null={len(n)} new_texts={fresh} "
              f"embedded={vecs.embedded} cached={vecs.hits} "
              f"{time.perf_counter() - c0:.1f}s", flush=True)

    with (out / "rulers.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with (out / "null.jsonl").open("w", encoding="utf-8") as f:
        for r in nulls:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    meta = {
        "source": str(args.src), "chunks": len(chunks), "rows": len(rows),
        "null_rows": len(nulls), "null_tags_cap": args.null_tags,
        "chunks_measured": len(chunks) - len(skipped),
        "chunks_skipped_no_vectors": skipped, "rulers": list(RULERS if not args.no_xenc else EMBED_RULERS),
        "embed_model": hembed.EMBED_MODEL, "embed_revision": hembed.EMBED_REVISION,
        "embed_prefix": "passage: (tag and text alike)",
        "embed_device": hembed.EMBED_DEVICE, "embed_dtype": hembed.EMBED_DTYPE,
        "embed_batch": hembed.EMBED_BATCH,
        "vectors_in": args.vectors_in or None,
        "whole_texts": not args.no_whole_texts,
        "xenc_model": None if args.no_xenc else XENC_MODEL,
        "sentence_splitter": "spacy en_core_web_sm, exclude=[ner, lemmatizer, "
                             "attribute_ruler, tagger] — boundaries verified identical to the "
                             "full pipeline",
        "texts_embedded": vecs.embedded, "cache_hits": vecs.hits,
        "embed_seconds": round(vecs.seconds, 1),
        "wall_s": round(time.perf_counter() - t0, 1),
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    save_sentence_cache()
    print(f"done | {len(rows)} rows, {len(nulls)} null rows | embedded {vecs.embedded} texts "
          f"in {vecs.seconds:.0f}s | {time.perf_counter() - t0:.0f}s total -> {out}",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

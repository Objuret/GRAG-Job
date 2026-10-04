"""The four text statistics per EDGE: read on the tag's own sentences inside the chunk,
the sentences located by nearness.

THE ORCHESTRATOR'S CONSTRUCTION, 2026-09-13 — not his ruling. What it rests on:
  "NEARNESS, we cant fucking use explicit shit" (09-09) — a tag's sentences are found by
    cosine, never by a string match.
  "embed the entire corpus … is retarded" (09-09) — only the chunks of the question's region
    are split and embedded, at query time, and the vectors are kept on disk.
  "the importance or weight of temporality in the chunk, AND the tag's relevance to the chunk
    and that combo IS the tag's temporality" (09-08 13:02) — the statistic stays the chunk's
    text statistic; what the tag changes is WHICH of the chunk's sentences it is read on.

The four statistics are facet_stats' own functions, imported, never re-implemented; a set of
sentences is aggregated exactly as facet_stats aggregates a chunk — temporal and concreteness
per token, why and activity per sentence.

WHICH SENTENCES ARE THE TAG'S (the orchestrator's construction, 2026-09-13): the sentence
nearest the tag's vector, and every sentence whose cosine to the tag is within COS_NOISE of
that nearest one — the embedder's measured just-noticeable difference (median cosine shift on
re-embedding, 200 tags x 50 probes, 2026-09-06), the arm's own constant, handed in. Nearness
only, one measured constant, on the same scale it is applied on. STRUCK the same day: a
per-chunk band, the median over the chunk's own sentences of |cos(sentence, description) -
cos(sentence, raw question)| — that spread is measured query-to-sentence and was applied
tag-to-sentence, two different comparisons, no basis.

The cache holds vectors and per-sentence statistics only, never the sentence text:
output/sentence_embed_cache/<db>/<chunk_id>.npz
Its meta names what produced every byte in it — facet_stats, the spaCy pipeline, the embedder
and its revision, and the corpus file the chunk was read from (the sha the arm holds); a
disagreement on any of them recomputes the chunk. A file written before a key existed carries
no disagreement: its vectors and rows stand, the file is left exactly as it is, and the read
returns the absent keys as `unverified_keys` — nothing is asserted onto a file, and the caller
counts the chunks it read unchecked. A file written now carries the full meta, written to a
temporary file and moved into place, so a reader never sees a half-written cache.
"""
from __future__ import annotations

import hashlib
import json
import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from graph import facet_stats as fs
from harness.embed import EMBED_MODEL, EMBED_REVISION

ROOT = Path(__file__).resolve().parents[2]
CACHE_ROOT = ROOT / "output" / "sentence_embed_cache"

STATS = ("temporal", "why", "activity", "concreteness")
_COLS = len(STATS) + 1          # the four statistics and the sentence's token count

_NLP = None


def _nlp():
    """the pipeline facet_stats uses"""
    global _NLP
    if _NLP is None:
        import spacy
        _NLP = spacy.load("en_core_web_sm")
    return _NLP


def _spacy_model_version() -> Optional[str]:
    """the pipeline package's version read from its metadata, never by loading the pipeline"""
    try:
        return version("en_core_web_sm")
    except PackageNotFoundError:
        return None


def _meta(sha: Optional[str] = None) -> dict:
    """what produced the cached rows and vectors. Loads nothing."""
    import spacy
    return {"tool": "test/graph/facet_stats.py",
            "tool_sha256": hashlib.sha256(Path(fs.__file__).read_bytes()).hexdigest(),
            "spacy": spacy.__version__, "spacy_model": "en_core_web_sm",
            "spacy_model_version": _spacy_model_version(),
            "embed_model": EMBED_MODEL, "embed_revision": EMBED_REVISION,
            "corpus_sha256": sha}


def split_and_measure(text: str) -> tuple:
    """(sentence texts, rows) — one row per sentence: the four statistics facet_stats computes
    for that sentence alone, and its token count. All-NaN where the sentence holds no token."""
    doc = _nlp()(text)
    sents = list(doc.sents)
    rows = np.full((len(sents), _COLS), np.nan, dtype=np.float64)
    for i, s in enumerate(sents):
        st = fs.facet_stats([s])
        if st:
            rows[i] = [st["temporal"], st["why"], st["activity"], st["concreteness"],
                       st["n_tok"]]
    return [s.text for s in sents], rows


def aggregate(rows: np.ndarray, keep: Optional[np.ndarray] = None) -> Optional[dict]:
    """the four statistics over a set of sentences, aggregated as facet_stats aggregates a
    chunk: temporal and concreteness are (counts / tokens) over the set, why and activity are
    the share of its sentences. None when the set holds no sentence with a token."""
    r = rows if keep is None else rows[keep]
    if r.size == 0:
        return None
    ok = ~np.isnan(r[:, -1]) & (r[:, -1] > 0)
    if not ok.any():
        return None
    r = r[ok]
    n_tok = float(r[:, -1].sum())
    return {"temporal": float((r[:, 0] * r[:, -1]).sum() / n_tok),
            "why": float(r[:, 1].mean()),
            "activity": float(r[:, 2].mean()),
            "concreteness": float((r[:, 3] * r[:, -1]).sum() / n_tok)}


def chunk_sentences(db: str, chunk_id: str, locator: str, relpath: str,
                    embed: Callable, sha: Optional[str] = None) -> Optional[tuple]:
    """(unit sentence vectors, per-sentence rows, read from disk, unverified_keys) for one
    chunk, from the cache when it holds them under this facet_stats, this spaCy, this embedder
    and this corpus file, else computed and written. The third value says whether the vectors
    came off the disk or were computed now; the fourth names the meta keys the cache file does
    not carry, so nothing about them was checked. None where the chunk's text does not resolve
    or splits into no sentence.

    `embed` takes a list of texts and returns their vectors (the arm hands in the harness's
    embedder with the passage prefix); `sha` is the corpus file's sha the arm carries on the
    chunk row."""
    path = CACHE_ROOT / db / f"{chunk_id}.npz"
    meta = _meta(sha)
    if path.is_file():
        try:
            with np.load(path, allow_pickle=False) as z:
                had = json.loads(str(z["meta"]))
                if all(had[key] == val for key, val in meta.items() if key in had):
                    vecs, rows = z["vecs"], z["rows"]
                    # the vectors and the per-sentence rows are what they were; a key the file
                    # predates is neither checked nor written — the file is left alone and the
                    # absent keys are handed back, so the caller can count what it read
                    # unchecked and a stricter pass can re-embed exactly those chunks
                    unverified_keys = sorted(key for key in meta if key not in had)
                    return vecs.astype(np.float64), rows, True, unverified_keys
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            pass
    text = fs.resolve_text(locator, relpath)
    if not text or not text.strip():
        return None
    sents, rows = split_and_measure(text)
    if not sents:
        return None
    vecs = np.asarray(embed(sents), dtype=np.float64)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    # stored and read back at the cache's precision, so a question is sorted the same whether
    # the chunk was embedded now or read from disk
    vecs = (vecs / norms).astype(np.float32)
    _write_cache(path, vecs, rows, meta)
    return vecs.astype(np.float64), rows, False, []


def _write_cache(path: Path, vecs: np.ndarray, rows: np.ndarray, meta: dict) -> None:
    """the file written whole under a temporary name and moved into place, so a reader never
    opens a half-written cache and no reader's file is ever rewritten."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.stem}.{os.getpid()}.tmp.npz")
    np.savez_compressed(tmp, vecs=vecs, rows=rows,
                        meta=np.array(json.dumps(meta, sort_keys=True)))
    os.replace(tmp, path)


def tag_sentence_mask(sims: np.ndarray, noise: float) -> np.ndarray:
    """the tag's sentences: the sentence nearest the tag, and every sentence whose cosine to
    the tag is within `noise` of it — the embedder's measured just-noticeable difference, the
    arm's COS_NOISE. Nearness only; the same scale the cosines are on."""
    best = float(sims.max())
    return sims >= best - float(noise)

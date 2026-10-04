"""The facet-view pilot's check: the pass/kill rule of `output/facet_views/PROGRESS.md`
("The check (pre-registered…)"), estimated as `output/facet_views/CHECK_DESIGN.md` §0-§9
specifies and nowhere else.

Reads the view files `facet_views.py` wrote, the counterfactual files
`facet_counterfactuals` wrote, and one vector per exact string from an npz
`facet_embed_gpu.py` built. Writes the per-value table, the per-intervention rows, the section
tables, the verdict table and the register check under `--out`. No model call of any kind,
nothing to the graph, no benchmark question and no gold. The view directory is read only.

    python test/graph/facet_views_check.py --texts output/facet_views/pilot/texts.jsonl \\
        --views output/facet_views/pilot/views --vectors vectors.npz \\
        --cf-dir output/facet_neural/counterfactuals/herb-eval-volmax \\
        --cf-dir output/facet_neural/counterfactuals_repeat/herb-eval-volmax \\
        --graph-topic output/facet_views/pilot/topic_graph.jsonl \\
        --graph-vectors output/facet_views/pilot/graph_vectors.npz \\
        --out output/facet_views/pilot/check

`--strings-out` writes every string the check needs, stripped views included, in
`facet_embed_gpu.py`'s `{"sha","text"}` shape and reads no vectors, so the GPU pass runs
first. `--pairs-out` does the same for `--value-mode xenc` in `facet_views_xenc_gpu.py`'s
`{"a_sha","a","b_sha","b"}` shape and reads no scores. `--embed-cpu` embeds whatever the
vectors file lacks on this machine's CPU and caches it under `--out`; it is for the smoke and
the tests.

`--value-mode` says what a value reads off a view. `cos` is the pre-registered plain cosine
and the default. `residual` and `relative` are the two readings of the same views that
`output/research/2026-09-18-facet-views-literature.md` §5 (a) names — the view's component
orthogonal to the description of the same text and write, and the cosine minus the
description's own cosine. `xenc` reads a fixed cross-encoder's raw score on the same
(phrase, view) strings from `--scores` tables (§5 (c) in its minimal form), with
`topic_local` the same scorer on (phrase, description). All three beside `cos` are the
orchestrator's constructions measured as candidates, never the default.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
from pathlib import Path
from statistics import NormalDist

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "prod", ROOT / "test"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from graph import facet_views as fv
from graph.facet_edits import FACETS

WRITES = (1, 2)

FI = {f: i for i, f in enumerate(FACETS)}

SUBSETS = ("all", "no_nothing")

# What a vectors file's sidecar must agree on with every other vectors file of one run.
EMBED_KEYS = ("model", "revision", "dtype", "prefix")

POPULATIONS = ("originals", "all")

# CHECK_DESIGN §2: the decision is `A - 0.5 > 3 * SE_chunk`, the one-sided normal tail
# 0.00135; §9 makes that same tail the cluster permutation's bar for a PASS.
SE_BARS = 3.0

PERM_BAR = 0.00135

# §2: "interval 2.5/97.5 percentiles". §9 asks for a bootstrap-t interval and names no width,
# so it takes the same two percentiles.
CI = (2.5, 97.5)

# §3(iii): the chunk-variant control keeps the other tags whose original topic_local is within
# this of T's.
TOPIC_CTRL = 0.02

# §6: the hit rate's reference figure under no effect.
HIT_REF = 0.025

# The three readings that come off an embedding of the view: the plain cosine, the component
# orthogonal to the topic direction, and the cosine minus the cosine to a view of the same chunk
# carrying no angle (`output/research/2026-09-18-facet-views-literature.md` §5 (a); the
# description of the same text and write is that topic view).
EMBED_MODES = ("cos", "residual", "relative")

# `xenc` reads no vector at all: a fixed cross-encoder scores the (phrase, view) pair directly
# (§5 (c) in its minimal form, the same view strings, no new text). Everything beside `cos` is
# the orchestrator's construction, measured as a candidate; `cos` is the default and leaves
# every reading as it was.
VALUE_MODES = EMBED_MODES + ("xenc",)

# CHECK_DESIGN §9: "A KILL where R_F's interval straddles 1, or A sits in 0.52-0.58, is a
# KILL by the rule and not by the data; the script prints which." The band is §9's own.
RULE_BAND = (0.52, 0.58)

# A residual this short is the view lying on the description's own direction: the value is 0 and
# the case is counted. The coordinator's floor, not derived.
RESIDUAL_FLOOR = 1e-6

# The pilot's shard rule is `facet_views.shard_of(text_sha, 5)`; shards 0 and 1 ran on the
# laptop and 2, 3, 4 on the desktop, whose CLI preambles differ in size. The machine is read
# off the text sha, no new input, and is a diagnostic — the verdict reads all rows.
SHARDS = 5

LAPTOP_SHARDS = (0, 1)

MACHINES = ("laptop", "desktop")

# §2, §5, §6: B resamples, and the seed so a rerun gives the same intervals.
DEFAULT_B = 10_000

DEFAULT_SEED = 20260918

_ND = NormalDist()


# ------------------------------------------------------------------ small numerics

def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clean_tag(raw) -> str:
    """Whitespace collapsed and nothing else — `artefact.querytagger.clean_tag`'s definition,
    written here so the check imports no model lane."""
    return re.sub(r"\s+", " ", str(raw)).strip()


def machine_of(text_sha: str) -> str:
    """Which machine wrote this text's views, from `facet_views.shard_of` alone."""
    return "laptop" if fv.shard_of(text_sha, SHARDS) in LAPTOP_SHARDS else "desktop"


def q(xs, p):
    """Nearest rank, `round(p*(n-1))` — §1 names `facet_rulers_report.q` as the method, and it
    is used for every quantile in this file, bootstrap percentiles included."""
    a = np.asarray(xs, dtype=float)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return None
    a = np.sort(a)
    return float(a[min(a.size - 1, max(0, int(round(p * (a.size - 1)))))])


def med(xs):
    a = np.asarray(xs, dtype=float)
    a = a[np.isfinite(a)]
    return float(np.median(a)) if a.size else None


def sd(xs):
    a = np.asarray(xs, dtype=float)
    a = a[np.isfinite(a)]
    return float(np.std(a)) if a.size > 1 else (0.0 if a.size == 1 else None)


def mean(xs):
    a = np.asarray(xs, dtype=float)
    a = a[np.isfinite(a)]
    return float(a.mean()) if a.size else None


def ranks(a) -> np.ndarray:
    """Average ranks, ties shared — `facet_neural/layer_stats.spearman`'s ranking."""
    a = np.asarray(a, dtype=float)
    order = np.argsort(a, kind="stable")
    out = np.empty(a.size, dtype=float)
    s = a[order]
    i = 0
    while i < a.size:
        j = i
        while j + 1 < a.size and s[j + 1] == s[i]:
            j += 1
        out[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return out


def spearman(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.size < 3 or x.size != y.size:
        return None
    rx = ranks(x)
    ry = ranks(y)
    rx = rx - rx.mean()
    ry = ry - ry.mean()
    den = math.sqrt(float((rx ** 2).sum()) * float((ry ** 2).sum()))
    return float((rx * ry).sum() / den) if den else 0.0


def fisher_z_se(n):
    """§5's "naive comparison": the Fisher-z standard error of a Spearman correlation, which
    ignores the chunk clustering."""
    return 1.0 / math.sqrt(n - 3) if n > 3 else None


def fmt(x, n=4) -> str:
    if x is None:
        return "—"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, str):
        return x
    if isinstance(x, (int, np.integer)):
        return f"{int(x):,}"
    x = float(x)
    if not math.isfinite(x):
        return "—"
    return f"{x:.{n}f}"


def iv(pair, n=4) -> str:
    if not pair or pair[0] is None or pair[1] is None:
        return "—"
    return f"[{fmt(pair[0], n)}, {fmt(pair[1], n)}]"


def val_iv(value, pair, n=4) -> str:
    """A point estimate and its interval in one cell, or a single dash when there is none."""
    if value is None:
        return "—"
    return f"{fmt(value, n)} {iv(pair, n)}"


# ------------------------------------------------------------------ the text set

class TextSet:
    """`texts.jsonl` as the check reads it: the texts, which chunk each belongs to, each
    chunk's original text, and each chunk's phrase list in the file's order."""

    def __init__(self, header, rows):
        self.header = header
        self.rows = rows
        self.by_sha = {r["sha"]: i for i, r in enumerate(rows)}
        self.chunk_of = [r["chunk_id"] for r in rows]
        self.machine = [machine_of(r["sha"]) for r in rows]
        self.chunks: list = []
        self.tags: dict = {}
        self.orig: dict = {}
        self.is_original = [False] * len(rows)
        for i, r in enumerate(rows):
            c = r["chunk_id"]
            if c not in self.tags:
                self.chunks.append(c)
                self.tags[c] = [clean_tag(t) for t in (r.get("tags") or [])]
            for o in r.get("origins") or []:
                if o.get("generation") == "original":
                    self.orig[c] = i
                    self.is_original[i] = True
        self.tag_pos = {c: {t: j for j, t in enumerate(ts)} for c, ts in self.tags.items()}
        self.cpos = {c: i for i, c in enumerate(self.chunks)}


def read_ids(path) -> list:
    out, seen = [], set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line in seen:
            continue
        seen.add(line)
        out.append(line)
    return out


def read_texts(path, ids=None) -> TextSet:
    header, rows = None, []
    keep = set(ids) if ids else None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if "sha" not in rec and "header" in rec:
                header = rec["header"]
                continue
            if keep is not None and rec["chunk_id"] not in keep:
                continue
            rows.append(rec)
    if not rows:
        raise SystemExit(f"facet_views_check: no texts in {path}")
    return TextSet(header, rows)


# ------------------------------------------------------------------ the interventions

def gen_label(path) -> str:
    """`facet_views_texts.split_cf_dir`'s rule: a path under `counterfactuals_repeat` is the
    repeat generation, anything else the main one."""
    return "repeat" if "counterfactuals_repeat" in Path(path).as_posix() else "main"


def cf_path(directory, chunk_id: str):
    """The chunk's counterfactual file. `facet_answers.file_stem` names it `<safe id>__<sha1
    head>.json`; the safe spelling is globbed and the hash head is whatever is on disk, so the
    two readings cannot drift on the hash."""
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", chunk_id)[:120]
    hits = [p for p in sorted(Path(directory).glob(f"{safe}__*.json"))
            if not p.name.endswith(".failed.json") and not p.name.startswith("manifest.")]
    return hits[0] if hits else None


def read_interventions(cf_dirs, texts: TextSet) -> tuple:
    """§0: one row per (chunk, tag, facet, generation) with `changed` and `reconstruction_ok`,
    carrying the sha of its counterfactual text."""
    rows = []
    counts = {"files": 0, "missing_files": 0, "pairs": 0, "unchanged": 0, "recon_fail": 0,
              "text_unknown": 0, "tag_unknown": 0}
    for directory in cf_dirs:
        label = gen_label(directory)
        for chunk in texts.chunks:
            path = cf_path(directory, chunk)
            if path is None:
                counts["missing_files"] += 1
                continue
            rec = json.loads(path.read_text(encoding="utf-8"))
            counts["files"] += 1
            for edge in rec.get("edges") or []:
                tag = clean_tag(edge.get("t"))
                known = tag in texts.tag_pos.get(chunk, {})
                for facet in FACETS:
                    cf = edge.get(facet)
                    if not isinstance(cf, dict) or not isinstance(cf.get("text"), str):
                        continue
                    counts["pairs"] += 1
                    if not cf.get("changed"):
                        counts["unchanged"] += 1
                        continue
                    if not cf.get("reconstruction_ok"):
                        counts["recon_fail"] += 1
                        continue
                    if not known:
                        counts["tag_unknown"] += 1
                        continue
                    sha = sha256_of(cf["text"])
                    if sha not in texts.by_sha:
                        counts["text_unknown"] += 1
                        continue
                    rows.append({"chunk": chunk, "tag": tag, "facet": facet, "gen": label,
                                 "cf_sha": sha})
    return rows, counts


# ------------------------------------------------------------------ the view files

def view_files(views_root) -> tuple:
    """({(variant, write): {text sha: path}}, {(variant, write): prompt sha}) over the files
    `facet_views.status_of` calls done. Manifests and `.failed.json` markers are skipped by
    that reading. A run directory holding more than one `prompt_sha256` is two prompts in one
    population and is refused."""
    out, prompts = {}, {}
    root = Path(views_root)
    for run in sorted(root.glob("*/w*")):
        if not run.is_dir():
            continue
        variant = run.parent.name
        if variant not in fv.VARIANTS:
            continue
        m = re.fullmatch(r"w(\d+)", run.name)
        if not m:
            continue
        write = int(m.group(1))
        files = {}
        seen: dict = {}
        for path in sorted(run.glob("*.json")):
            if path.name.startswith("manifest.") or path.name.endswith(".failed.json"):
                continue
            if fv.status_of(path, None, variant) != "done":
                continue
            files[path.stem] = path
            sha = json.loads(path.read_text(encoding="utf-8")).get("prompt_sha256")
            seen.setdefault(str(sha), []).append(path.name)
        if len(seen) > 1:
            named = ", ".join(f"{k[:12]} ({len(v)} files)" for k, v in sorted(seen.items()))
            raise SystemExit(f"facet_views_check: {variant}/w{write} holds {len(seen)} prompt "
                             f"shas — {named}; that is two prompts in one population")
        out[(variant, write)] = files
        prompts[(variant, write)] = next(iter(seen), None)
    return out, prompts


def strip_phrase(text: str, phrase: str) -> tuple:
    """§8: case-insensitive whole-phrase match, the span deleted, whitespace collapsed; the
    number of removals returned beside the string."""
    ph = clean_tag(phrase)
    body = str(text)
    if not ph:
        return re.sub(r"\s+", " ", body).strip(), 0
    pat = re.compile(r"(?<!\w)" + re.escape(ph) + r"(?!\w)", re.IGNORECASE)
    stripped, n = pat.subn("", body)
    return re.sub(r"\s+", " ", stripped).strip(), n


def stripped_views(row: dict, tag: str) -> list:
    """§8's second column, per facet: (the view with the tag phrase struck out, the removals).
    Where the phrase never appeared the design has `v' = v`, so the plain string stands and no
    second vector is needed."""
    out = []
    for facet in FACETS:
        text = row[facet]
        cut, n = strip_phrase(text, tag)
        out.append((text if n == 0 else cut, n))
    return out


def file_strings(rec: dict, variant: str, tags_of_chunk: list) -> tuple:
    """(the view strings the file holds, the stripped strings the edge diagnostic needs)."""
    plain = list(fv.views_strings(rec))
    stripped = []
    if variant == "edge":
        want = {t.casefold(): t for t in tags_of_chunk}
        for row in rec["views"]:
            key = clean_tag(row.get("t", "")).casefold()
            if key not in want:
                continue
            for cut, n in stripped_views(row, want[key]):
                if n:
                    stripped.append(cut)
    return plain, stripped


def file_pairs(rec: dict, variant: str, tags_of_chunk: list) -> list:
    """Every (phrase, string) pair a value of this file reads under `xenc`: the chunk file's
    four views and its description against every phrase of the chunk — the description because
    `topic_local` is the same scorer on it, and for the edge variant too, which reads the chunk
    variant's description — and the edge file's four views, with their stripped forms, against
    the one phrase they were written for."""
    out = []
    if variant == "chunk":
        views = rec["views"]
        strings = [views[f] for f in FACETS] + [views["description"]]
        for tag in tags_of_chunk:
            for s in strings:
                out.append((tag, s))
        return out
    want = {t.casefold(): t for t in tags_of_chunk}
    for row in rec["views"]:
        key = clean_tag(row.get("t", "")).casefold()
        if key not in want:
            continue
        tag = want[key]
        for facet in FACETS:
            out.append((tag, row[facet]))
        for cut, n in stripped_views(row, tag):
            if n:
                out.append((tag, cut))
    return out


def collect_needs(texts: TextSet, files: dict, want_pairs: bool = False) -> dict:
    """What the check must be given before it can read a value.

    `strings`: every exact string it embeds — each chunk's phrases, every view on disk, and
    every edge view with its own phrase struck out. `pairs`: every (phrase, string) pair the
    `xenc` mode scores, keyed by the two sha256s."""
    need: dict = {}
    pairs: dict = {}

    def add(s: str) -> None:
        need.setdefault(sha256_of(s), s)

    for chunk in texts.chunks:
        for tag in texts.tags[chunk]:
            add(tag)
    for (variant, _write), by_sha in sorted(files.items()):
        for sha, path in by_sha.items():
            if sha not in texts.by_sha:
                continue
            rec = json.loads(path.read_text(encoding="utf-8"))
            chunk = texts.chunk_of[texts.by_sha[sha]]
            tags = texts.tags.get(chunk, [])
            plain, stripped = file_strings(rec, variant, tags)
            for s in plain + stripped:
                add(s)
            if want_pairs:
                for a, b in file_pairs(rec, variant, tags):
                    pairs.setdefault((sha256_of(a), sha256_of(b)), (a, b))
    return {"strings": need, "pairs": pairs}


# ------------------------------------------------------------------ the vectors

class Vectors:
    """One unit vector per exact string, keyed by the sha256 of that string. The npz files are
    `facet_embed_gpu.py`'s output; `--embed-cpu` fills what they lack with `harness.embed`."""

    def __init__(self):
        self.by_sha: dict = {}
        self.buffers: list = []
        self.embedded = 0
        self.loaded = 0
        self.dim = None
        self.provenance: list = []
        self.no_sidecar: list = []

    def preload(self, path) -> int:
        """Normalised in place and kept as one buffer; the cache holds row views of it, so a
        pilot-sized file costs its own size in memory and no copy per string.

        `facet_embed_gpu.py` writes `<out>.meta.json` beside each npz; two files naming a
        different model, revision, dtype or prefix are two instruments and are refused, as
        `Scores.preload` refuses two scorers. A file with no sidecar is recorded as such."""
        path = Path(path)
        side = path.with_suffix(".meta.json")
        if side.is_file():
            m = json.loads(side.read_text(encoding="utf-8"))
            key = {k: m.get(k) for k in EMBED_KEYS}
            for prev in self.provenance:
                if {k: prev["meta"].get(k) for k in EMBED_KEYS} != key:
                    raise SystemExit(
                        f"facet_views_check: {path.name} was embedded by "
                        f"{key} and {prev['file']} by "
                        f"{ {k: prev['meta'].get(k) for k in EMBED_KEYS} } — two instruments, "
                        f"not one")
            self.provenance.append({"file": path.name, "sidecar": side.name, "meta": m})
        else:
            self.no_sidecar.append(path.name)
        z = np.load(path, allow_pickle=False)
        shas, mat = z["sha"], np.asarray(z["vec"], dtype=np.float32)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        np.divide(mat, norms, out=mat)
        self.buffers.append(mat)
        for i, sha in enumerate(shas):
            self.by_sha[str(sha)] = mat[i]
        self.loaded += len(shas)
        self.dim = mat.shape[1] if mat.size else self.dim
        return len(shas)

    def missing(self, need: dict) -> list:
        return [sha for sha in need if sha not in self.by_sha]

    def embed_cpu(self, need: dict, shas: list, cache_path) -> int:
        from harness import embed as hembed
        texts = [need[s] for s in shas]
        mat, _c, _ti, _to, _s = hembed._embed(texts, "passage", bar=False)
        mat = np.asarray(mat, dtype=np.float32)
        for sha, v in zip(shas, mat):
            self.by_sha[sha] = v
        self.embedded += len(shas)
        self.dim = mat.shape[1] if mat.size else self.dim
        keys = sorted(self.by_sha)
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        np.savez(cache_path, sha=np.array(keys, dtype="U64"),
                 vec=np.stack([self.by_sha[k] for k in keys]).astype(np.float32))
        Path(cache_path).with_suffix(".meta.json").write_text(json.dumps({
            "model": hembed.EMBED_MODEL, "revision": hembed.EMBED_REVISION,
            "dtype": hembed.EMBED_DTYPE, "prefix": hembed.EMBED_PREFIX["passage"],
            "device": hembed.EMBED_DEVICE, "strings": len(self.by_sha),
            "dim": int(mat.shape[1]) if mat.size else 0,
        }, indent=1), encoding="utf-8")
        return len(shas)

    def get(self, text: str) -> np.ndarray:
        return self.by_sha[sha256_of(text)]

    def stack(self, strings: list) -> np.ndarray:
        return np.stack([self.by_sha[sha256_of(s)] for s in strings])


class Scores:
    """One score per exact (phrase, string) pair, keyed by the two sha256s. The npz files are
    `facet_views_xenc_gpu.py`'s output and carry the scorer's model and revision beside the
    three columns; two files naming different scorers are two instruments and are refused."""

    def __init__(self):
        self.by_pair: dict = {}
        self.model = None
        self.revision = None
        self.loaded = 0

    def preload(self, path) -> int:
        z = np.load(path, allow_pickle=False)
        model = str(np.atleast_1d(z["model"])[0])
        revision = str(np.atleast_1d(z["revision"])[0])
        if self.model is not None and (model, revision) != (self.model, self.revision):
            raise SystemExit(f"facet_views_check: {path} was scored by {model} @ "
                             f"{revision[:12]}, the tables before it by {self.model} @ "
                             f"{str(self.revision)[:12]}")
        self.model, self.revision = model, revision
        a, b, s = z["a_sha"], z["b_sha"], np.asarray(z["score"], dtype=np.float32)
        for i in range(len(s)):
            self.by_pair[(str(a[i]), str(b[i]))] = float(s[i])
        self.loaded += len(s)
        return len(s)

    def missing(self, pairs: dict) -> list:
        return [k for k in pairs if k not in self.by_pair]

    def get(self, a: str, b: str) -> float:
        return self.by_pair[(sha256_of(a), sha256_of(b))]

    def row(self, a: str, strings: list) -> np.ndarray:
        return np.array([self.get(a, s) for s in strings], dtype=float)


# ------------------------------------------------------------------ the values

def reading_matrix(mat: np.ndarray, dvec: np.ndarray, mode: str) -> tuple:
    """(the vectors a value is read off, how many of them the mode emptied).

    `residual` takes each view's component orthogonal to the description of the same text and
    the same write and re-normalises it; a residual shorter than `RESIDUAL_FLOOR` is the view
    lying on the description's own direction and is zeroed. `cos` and `relative` read the view
    vector itself, `relative` subtracting the description's own cosine per tag."""
    if mode not in VALUE_MODES:
        raise SystemExit(f"facet_views_check: --value-mode wants one of {VALUE_MODES}, "
                         f"got {mode!r}")
    if mode != "residual":
        return mat, 0
    res = mat - (mat @ dvec)[:, None] * dvec[None, :]
    norms = np.linalg.norm(res, axis=1, keepdims=True)
    empty = norms[:, 0] < RESIDUAL_FLOOR
    out = res / np.where(norms < RESIDUAL_FLOOR, 1.0, norms)
    out[empty] = 0.0
    return out, int(empty.sum())


def read_values(read_mat: np.ndarray, dvec: np.ndarray, tv: np.ndarray,
                mode: str) -> np.ndarray:
    v = np.asarray(read_mat @ tv, dtype=float)
    if mode == "relative":
        v = v - float(dvec @ tv)
    return v


def build_values(texts: TextSet, files: dict, vecs: Vectors, mode: str = "cos",
                 scores: "Scores | None" = None) -> dict:
    """§0: `v_F^w(X, text)` for every usable view file, tag and facet, plus `topic_local`.

    The chunk variant carries the description, so its `topic_local` is read off it; the edge
    variant has no description of its own and reads the chunk variant's on the same text and
    the same write. Under the three embedding modes `topic_local` is the plain cosine to the
    description and the mode acts on the four facet values and on the stripped column beside
    them; under `xenc` every value, `topic_local` included, is the scorer on that pair."""
    store: dict = {}
    desc: dict = {}
    for (variant, write), by_sha in sorted(files.items()):
        v_map: dict = {}
        no_map: dict = {}
        vs_map: dict = {}
        rm_map: dict = {}
        topic_map: dict = {}
        gaps = 0
        emptied = 0
        no_desc = 0
        for sha, path in by_sha.items():
            if sha not in texts.by_sha:
                continue
            ti = texts.by_sha[sha]
            chunk = texts.chunk_of[ti]
            tags = texts.tags.get(chunk, [])
            rec = json.loads(path.read_text(encoding="utf-8"))
            if variant == "chunk":
                views = rec["views"]
                fstr = [views[f] for f in FACETS]
                flag = np.array([s.strip() == fv.NOTHING_LINE for s in fstr])
                if mode == "xenc":
                    for tag in tags:
                        v_map[(ti, tag)] = scores.row(tag, fstr)
                        no_map[(ti, tag)] = flag
                        topic_map[(ti, tag)] = scores.get(tag, views["description"])
                else:
                    dvec = vecs.get(views["description"])
                    desc[(write, ti)] = dvec
                    read_mat, n_empty = reading_matrix(vecs.stack(fstr), dvec, mode)
                    emptied += n_empty
                    for tag in tags:
                        tv = vecs.get(tag)
                        v_map[(ti, tag)] = read_values(read_mat, dvec, tv, mode)
                        no_map[(ti, tag)] = flag
                        topic_map[(ti, tag)] = float(dvec @ tv)
            else:
                dvec = None
                if mode != "xenc":
                    dvec = desc.get((write, ti))
                    if dvec is None:
                        if mode == "cos":
                            dvec = np.zeros(vecs.dim or 1, dtype=np.float32)
                        else:
                            no_desc += 1
                            continue
                want = {t.casefold(): t for t in tags}
                rows = {}
                for row in rec["views"]:
                    key = clean_tag(row.get("t", "")).casefold()
                    if key in want:
                        rows[want[key]] = row
                for tag in tags:
                    row = rows.get(tag)
                    if row is None:
                        gaps += 1
                        continue
                    fstr = [row[f] for f in FACETS]
                    pairs = stripped_views(row, tag)
                    if mode == "xenc":
                        v_map[(ti, tag)] = scores.row(tag, fstr)
                        vs_map[(ti, tag)] = scores.row(tag, [t for t, _n in pairs])
                    else:
                        tv = vecs.get(tag)
                        read_mat, n_empty = reading_matrix(vecs.stack(fstr), dvec, mode)
                        strip_mat, n_strip = reading_matrix(
                            vecs.stack([t for t, _n in pairs]), dvec, mode)
                        emptied += n_empty + n_strip
                        v_map[(ti, tag)] = read_values(read_mat, dvec, tv, mode)
                        vs_map[(ti, tag)] = read_values(strip_mat, dvec, tv, mode)
                    rm_map[(ti, tag)] = np.array([n for _s, n in pairs], dtype=int)
                    no_map[(ti, tag)] = np.array([s.strip() == fv.NOTHING_LINE for s in fstr])
        store[(variant, write)] = {"v": v_map, "no": no_map, "vs": vs_map, "rm": rm_map,
                                   "topic": topic_map, "gaps": gaps, "files": len(by_sha),
                                   "emptied": emptied, "no_desc": no_desc, "mode": mode}
    for (variant, write), s in store.items():
        if variant != "chunk" and not s["topic"]:
            src = store.get(("chunk", write))
            s["topic_from"] = f"chunk/w{write}"
            s["topic"] = dict(src["topic"]) if src else {}
        else:
            s["topic_from"] = f"{variant}/w{write}"
    return store


def reference_columns(texts: TextSet, store: dict) -> dict:
    """§7: the position reference is the originals-only column of that facet and variant. It is
    taken at the same write as the value placed into it, because §1 makes every reading of the
    rule write-matched."""
    ref: dict = {}
    for (variant, write), s in store.items():
        cols = [[] for _f in FACETS]
        topic = []
        for (ti, tag), vals in s["v"].items():
            if not texts.is_original[ti]:
                continue
            for i in range(len(FACETS)):
                cols[i].append(float(vals[i]))
            t = s["topic"].get((ti, tag))
            if t is not None:
                topic.append(float(t))
        ref[(variant, write)] = {
            "facets": [np.sort(np.asarray(c, dtype=float)) for c in cols],
            "topic": np.sort(np.asarray(topic, dtype=float)),
        }
    return ref


def position(col: np.ndarray, x) -> float:
    """§7: (share of the reference column below) + ½ (share equal), in [0, 1]."""
    if col.size == 0 or x is None or not math.isfinite(float(x)):
        return float("nan")
    lo = int(np.searchsorted(col, x, side="left"))
    hi = int(np.searchsorted(col, x, side="right"))
    return (lo + 0.5 * (hi - lo)) / col.size


def write_values(path, texts: TextSet, store: dict) -> int:
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for (variant, write), s in sorted(store.items()):
            for (ti, tag), vals in s["v"].items():
                row = texts.rows[ti]
                no = s["no"][(ti, tag)]
                vs = s["vs"].get((ti, tag))
                rm = s["rm"].get((ti, tag))
                topic = s["topic"].get((ti, tag))
                for i, facet in enumerate(FACETS):
                    rec = {"variant": variant, "write": write, "chunk_id": row["chunk_id"],
                           "sha": row["sha"], "machine": texts.machine[ti], "tag": tag,
                           "facet": facet,
                           "value": round(float(vals[i]), 6), "nothing": bool(no[i]),
                           "topic_local": None if topic is None else round(float(topic), 6),
                           "original": bool(texts.is_original[ti])}
                    if vs is not None:
                        rec["stripped"] = round(float(vs[i]), 6)
                        rec["removals"] = int(rm[i])
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    n += 1
    return n


# ------------------------------------------------------------------ the rows

def build_rows(texts: TextSet, interventions: list, store: dict, ref: dict,
               variant: str, write: int) -> tuple:
    """§0/§1: one row per intervention per write, write-matched — `Δ = v^w(C) − v^w(C')` on one
    write, never a mean of the two."""
    key = (variant, write)
    if key not in store:
        return [], {"unmeasured": 0, "no_views": True}
    s = store[key]
    v = s["v"]
    topic = s["topic"]
    vs = s["vs"]
    rm = s["rm"]
    no = s["no"]
    cols = ref[key]["facets"]
    tcol = ref[key]["topic"]
    rows = []
    counts = {"unmeasured": 0, "topic_unmeasured": 0, "tag_pairs_dropped": 0, "no_views": False}
    # §3's other-tag arm is a control only where the edit was not aimed at that tag too: 167
    # of the pilot's counterfactuals are one text carrying two relations, and on those the
    # "other" tag's delta is itself a targeted delta.
    targeted: dict = {}
    for ivn in interventions:
        targeted.setdefault((ivn["cf_sha"], ivn["facet"], ivn["gen"]), set()).add(ivn["tag"])
    for ivn in interventions:
        chunk = ivn["chunk"]
        tag = ivn["tag"]
        facet = ivn["facet"]
        fi = FI[facet]
        oi = texts.orig.get(chunk)
        pi = texts.by_sha.get(ivn["cf_sha"])
        if oi is None or pi is None:
            counts["unmeasured"] += 1
            continue
        a = v.get((oi, tag))
        b = v.get((pi, tag))
        if a is None or b is None:
            counts["unmeasured"] += 1
            continue
        d = a - b
        dp = np.array([position(cols[i], a[i]) - position(cols[i], b[i])
                       for i in range(len(FACETS))])
        ta = topic.get((oi, tag))
        tb = topic.get((pi, tag))
        if ta is None or tb is None:
            counts["topic_unmeasured"] += 1
            d_topic = float("nan")
            dp_topic = float("nan")
        else:
            d_topic = float(ta) - float(tb)
            dp_topic = position(tcol, ta) - position(tcol, tb)
        aimed = targeted.get((ivn["cf_sha"], facet, ivn["gen"]), frozenset())
        tag_list, dt, dtp, dts, topic_c, contam = [], [], [], [], [], []
        for x in texts.tags[chunk]:
            xa = v.get((oi, x))
            xb = v.get((pi, x))
            if xa is None or xb is None:
                counts["tag_pairs_dropped"] += 1
                continue
            tag_list.append(x)
            contam.append(bool(x != tag and x in aimed))
            dt.append(float(xa[fi] - xb[fi]))
            dtp.append(position(cols[fi], xa[fi]) - position(cols[fi], xb[fi]))
            if vs:
                sa = vs.get((oi, x))
                sb = vs.get((pi, x))
                dts.append(float(sa[fi] - sb[fi]) if sa is not None and sb is not None
                           else float("nan"))
            tc = topic.get((oi, x))
            topic_c.append(float("nan") if tc is None else float(tc))
        sa = vs.get((oi, tag)) if vs else None
        sb = vs.get((pi, tag)) if vs else None
        ds = (sa - sb) if sa is not None and sb is not None else None
        rm_a = rm.get((oi, tag)) if rm else None
        rm_b = rm.get((pi, tag)) if rm else None
        rows.append({
            "chunk": chunk, "cpos": texts.cpos[chunk], "tag": tag, "facet": facet, "fi": fi,
            "gen": ivn["gen"], "cf_sha": ivn["cf_sha"],
            "d": d, "dp": dp, "ds": ds,
            "d_topic": d_topic, "dp_topic": dp_topic,
            "tags": tag_list, "dt": np.asarray(dt, dtype=float),
            "dtp": np.asarray(dtp, dtype=float),
            "dts": np.asarray(dts, dtype=float) if dts else None,
            "topic_c": np.asarray(topic_c, dtype=float),
            "dt_contam": np.asarray(contam, dtype=bool),
            "t_pos": tag_list.index(tag) if tag in tag_list else -1,
            "machine_c": texts.machine[oi], "machine_cf": texts.machine[pi],
            "same_machine": texts.machine[oi] == texts.machine[pi],
            "nothing": bool(no[(oi, tag)][fi] or no[(pi, tag)][fi]),
            "rm_target": (None if rm_a is None or rm_b is None
                          else int(rm_a[fi]) + int(rm_b[fi])),
        })
    return rows, counts


def write_rows(path, rows_by: dict) -> int:
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for (variant, write), rows in sorted(rows_by.items()):
            for r in rows:
                rec = {"variant": variant, "write": write, "chunk_id": r["chunk"],
                       "tag": r["tag"], "facet": r["facet"], "generation": r["gen"],
                       "cf_sha": r["cf_sha"], "nothing_target": r["nothing"],
                       "machine_c": r["machine_c"], "machine_cf": r["machine_cf"],
                       "same_machine": r["same_machine"],
                       "d_target": round(float(r["d"][r["fi"]]), 6),
                       "d_otherfacet": {g: round(float(r["d"][FI[g]]), 6)
                                        for g in FACETS if g != r["facet"]},
                       "d_topic": None if not math.isfinite(r["d_topic"])
                                  else round(r["d_topic"], 6),
                       "d_othertag": {x: round(float(val), 6)
                                      for x, val in zip(r["tags"], r["dt"]) if x != r["tag"]},
                       "pos_target": round(float(r["dp"][r["fi"]]), 6),
                       "pos_otherfacet": {g: round(float(r["dp"][FI[g]]), 6)
                                          for g in FACETS if g != r["facet"]},
                       "pos_topic": None if not math.isfinite(r["dp_topic"])
                                    else round(r["dp_topic"], 6),
                       "pos_othertag": {x: round(float(val), 6)
                                        for x, val in zip(r["tags"], r["dtp"])
                                        if x != r["tag"]},
                       "othertag_contaminated": [x for x, c in zip(r["tags"], r["dt_contam"])
                                                 if c]}
                if r["ds"] is not None:
                    rec["d_target_stripped"] = round(float(r["ds"][r["fi"]]), 6)
                    rec["d_otherfacet_stripped"] = {g: round(float(r["ds"][FI[g]]), 6)
                                                    for g in FACETS if g != r["facet"]}
                    rec["removals_target"] = r["rm_target"]
                if r["dts"] is not None:
                    rec["d_othertag_stripped"] = {x: round(float(val), 6)
                                                  for x, val in zip(r["tags"], r["dts"])
                                                  if x != r["tag"]}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n += 1
    return n


# ------------------------------------------------------------------ writer noise, §1

def noise_table(texts: TextSet, store: dict, variant: str) -> dict:
    """§1: `|v_F^w1(X,text) − v_F^w2(X,text)|` over every (tag, text) unit of every pilot text,
    with the originals-only subgroup beside it. p95 is the band, the median the rule-(a)
    denominator."""
    a = store.get((variant, 1))
    b = store.get((variant, 2))
    out = {"facets": {}, "facets_no_nothing": {}, "topic": {}, "per_chunk": {},
           "per_chunk_no_nothing": {}, "have": bool(a and b)}
    if not (a and b):
        return out
    shared = [k for k in a["v"] if k in b["v"]]
    for i, facet in enumerate(FACETS):
        vals, orig, per_chunk = [], [], {}
        nn_vals, nn_per_chunk, split = [], {}, 0
        for ti, tag in shared:
            dv = abs(float(a["v"][(ti, tag)][i] - b["v"][(ti, tag)][i]))
            vals.append(dv)
            per_chunk.setdefault(texts.chunk_of[ti], []).append(dv)
            if texts.is_original[ti]:
                orig.append(dv)
            # the no_nothing subset drops the rows whose targeted view is the absence line, so
            # its band must drop the pairs where exactly one write wrote that line
            na = bool(a["no"][(ti, tag)][i])
            nb = bool(b["no"][(ti, tag)][i])
            if na != nb:
                split += 1
                continue
            nn_vals.append(dv)
            nn_per_chunk.setdefault(texts.chunk_of[ti], []).append(dv)
        out["facets"][facet] = {
            "n": len(vals), "median": med(vals), "p95": q(vals, 0.95),
            "max": (max(vals) if vals else None), "sd": sd(vals),
            "n_originals": len(orig), "median_originals": med(orig),
            "p95_originals": q(orig, 0.95),
        }
        out["facets_no_nothing"][facet] = {
            "n": len(nn_vals), "median": med(nn_vals), "p95": q(nn_vals, 0.95),
            "max": (max(nn_vals) if nn_vals else None), "sd": sd(nn_vals),
            "dropped_one_sided": split,
        }
        out["per_chunk"][facet] = {c: np.asarray(v, dtype=float)
                                   for c, v in per_chunk.items()}
        out["per_chunk_no_nothing"][facet] = {c: np.asarray(v, dtype=float)
                                              for c, v in nn_per_chunk.items()}
    tvals, torig = [], []
    for ti, tag in shared:
        ta, tb = a["topic"].get((ti, tag)), b["topic"].get((ti, tag))
        if ta is None or tb is None:
            continue
        dv = abs(float(ta) - float(tb))
        tvals.append(dv)
        if texts.is_original[ti]:
            torig.append(dv)
    out["topic"] = {"n": len(tvals), "median": med(tvals), "p95": q(tvals, 0.95),
                    "max": (max(tvals) if tvals else None), "sd": sd(tvals),
                    "n_originals": len(torig), "median_originals": med(torig)}
    return out


def delta_repeat(rows1: list, rows2: list, cross: dict) -> dict:
    """§1(i)(ii): the same Δ on the two writes — its repeatability, the attenuation, and the
    crossed-write Δ beside it as the independence diagnostic."""
    key = lambda r: (r["chunk"], r["tag"], r["facet"], r["gen"], r["cf_sha"])
    m2 = {key(r): r for r in rows2}
    out = {}
    for facet in FACETS:
        d1, d2, dc = [], [], []
        for r in rows1:
            if r["facet"] != facet:
                continue
            k = key(r)
            if k not in m2:
                continue
            d1.append(float(r["d"][r["fi"]]))
            d2.append(float(m2[k]["d"][m2[k]["fi"]]))
            c = cross.get(k)
            if c is not None:
                dc.append(c)
        n = len(d1)
        diff = [abs(x - y) for x, y in zip(d1, d2)]
        m1 = med(d1)
        rho = None
        if n > 2:
            x = np.asarray(d1)
            y = np.asarray(d2)
            if x.std() > 0 and y.std() > 0:
                rho = float(np.corrcoef(x, y)[0, 1])
        sig_w = (math.sqrt(0.25 * float(np.mean(np.square(np.asarray(d1) - np.asarray(d2)))))
                 if n else None)
        out[facet] = {"n": n, "median_d1": m1, "median_d2": med(d2),
                      "median_abs_diff": med(diff), "p95_abs_diff": q(diff, 0.95),
                      "ratio": (None if not m1 else med(diff) / m1),
                      "pearson": rho, "sigma_w": sig_w,
                      "median_cross": med(dc), "n_cross": len(dc)}
    return out


def crossed_deltas(texts: TextSet, interventions: list, store: dict, variant: str) -> dict:
    """§1: the crossed Δ — `v^w1(C) − v^w2(C')`. Equal variance to the matched Δ under
    independent writes, so a disagreement is evidence the writes are not independent."""
    a = store.get((variant, 1))
    b = store.get((variant, 2))
    out = {}
    if not (a and b):
        return out
    for ivn in interventions:
        oi = texts.orig.get(ivn["chunk"])
        pi = texts.by_sha.get(ivn["cf_sha"])
        if oi is None or pi is None:
            continue
        va = a["v"].get((oi, ivn["tag"]))
        vb = b["v"].get((pi, ivn["tag"]))
        if va is None or vb is None:
            continue
        fi = FI[ivn["facet"]]
        out[(ivn["chunk"], ivn["tag"], ivn["facet"], ivn["gen"], ivn["cf_sha"])] = \
            float(va[fi] - vb[fi])
    return out


# ------------------------------------------------------------------ bootstrap and permutation

def cluster_draws(g: int, b: int, rng) -> np.ndarray:
    """§2: B resamples of the chunk ids with replacement, a chunk drawn twice contributing
    twice."""
    return rng.integers(0, g, size=(b, g))


def ratio_boot(num: np.ndarray, den: np.ndarray, draws: np.ndarray) -> np.ndarray:
    n = num[draws].sum(axis=1)
    d = den[draws].sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(d > 0, n / d, np.nan)
    return out


def ratio_jack(num: np.ndarray, den: np.ndarray) -> tuple:
    """Delete-one-cluster jackknife values and their SE — the acceleration of §2's BCa and the
    within-resample SE of §9's bootstrap-t."""
    g = num.size
    if g < 2:
        return np.array([]), None
    tn, td = num.sum(), den.sum()
    dd = td - den
    with np.errstate(invalid="ignore", divide="ignore"):
        vals = np.where(dd > 0, (tn - num) / dd, np.nan)
    good = vals[np.isfinite(vals)]
    if good.size < 2:
        return vals, None
    se = math.sqrt((g - 1) / g * float(((good - good.mean()) ** 2).sum()))
    return vals, se


def ratio_jack_matrix(num_d: np.ndarray, den_d: np.ndarray) -> np.ndarray:
    tn = num_d.sum(axis=1, keepdims=True)
    td = den_d.sum(axis=1, keepdims=True)
    dd = td - den_d
    with np.errstate(invalid="ignore", divide="ignore"):
        vals = np.where(dd > 0, (tn - num_d) / dd, np.nan)
    g = num_d.shape[1]
    # A resample that drew one distinct chunk leaves no jackknife value at all; its SE is
    # undefined and the bootstrap-t drops it, so it is NaN rather than a zero that reads as a
    # measurement.
    kept = np.isfinite(vals).sum(axis=1, keepdims=True)
    m = np.nansum(vals, axis=1, keepdims=True) / np.maximum(kept, 1)
    se = np.sqrt((g - 1) / g * np.nansum((vals - m) ** 2, axis=1))
    return np.where(kept[:, 0] >= 2, se, np.nan)


def bca_interval(theta, boot: np.ndarray, jack: np.ndarray) -> tuple:
    """§2's BCa, beside the percentile interval. Efron & Tibshirani (1993)."""
    b = boot[np.isfinite(boot)]
    j = jack[np.isfinite(jack)] if jack is not None else np.array([])
    if b.size < 20 or j.size < 2 or theta is None:
        return (None, None)
    share = float(np.mean(b < theta))
    if share <= 0.0 or share >= 1.0:
        return (None, None)
    z0 = _ND.inv_cdf(share)
    jm = j.mean()
    num = float(((jm - j) ** 3).sum())
    den = 6.0 * (float(((jm - j) ** 2).sum()) ** 1.5)
    a = num / den if den else 0.0
    out = []
    for p in (CI[0] / 100.0, CI[1] / 100.0):
        z = _ND.inv_cdf(p)
        denom = 1.0 - a * (z0 + z)
        if denom == 0:
            return (None, None)
        adj = z0 + (z0 + z) / denom
        out.append(q(b, min(max(_ND.cdf(adj), 0.0), 1.0)))
    return (out[0], out[1])


def boot_t_interval(theta, se_hat, boot: np.ndarray, se_boot: np.ndarray) -> tuple:
    """§9's guard: Cameron, Gelbach & Miller (2008) bootstrap-t, the within-resample SE by the
    same delete-one-cluster jackknife, at §2's two percentiles."""
    if theta is None or se_hat in (None, 0) or not math.isfinite(se_hat or 0):
        return (None, None)
    ok = np.isfinite(boot) & np.isfinite(se_boot) & (se_boot > 0)
    if ok.sum() < 20:
        return (None, None)
    t = (boot[ok] - theta) / se_boot[ok]
    hi_t = q(t, CI[1] / 100.0)
    lo_t = q(t, CI[0] / 100.0)
    return (theta - hi_t * se_hat, theta - lo_t * se_hat)


def ratio_estimate(num_by_chunk: np.ndarray, den_by_chunk: np.ndarray,
                   draws: np.ndarray) -> dict:
    tot_d = float(den_by_chunk.sum())
    theta = float(num_by_chunk.sum() / tot_d) if tot_d > 0 else None
    boot = ratio_boot(num_by_chunk, den_by_chunk, draws)
    jack, se_jack = ratio_jack(num_by_chunk, den_by_chunk)
    se = sd(boot)
    num_d = num_by_chunk[draws]
    den_d = den_by_chunk[draws]
    se_boot = ratio_jack_matrix(num_d, den_d)
    return {"value": theta, "se": se, "se_jack": se_jack,
            "ci": (q(boot, CI[0] / 100.0), q(boot, CI[1] / 100.0)),
            "bca": bca_interval(theta, boot, jack),
            "boot_t": boot_t_interval(theta, se_jack, boot, se_boot),
            "boot_samples": boot}


def median_boot(per_chunk: list, draws: np.ndarray) -> np.ndarray:
    out = np.empty(draws.shape[0], dtype=float)
    for i, pick in enumerate(draws):
        parts = [per_chunk[j] for j in pick if per_chunk[j].size]
        out[i] = np.median(np.concatenate(parts)) if parts else np.nan
    return out


def ratio_of_medians_boot(num_chunk: list, den_chunk: list, draws: np.ndarray) -> np.ndarray:
    out = np.empty(draws.shape[0], dtype=float)
    for i, pick in enumerate(draws):
        a = [num_chunk[j] for j in pick if num_chunk[j].size]
        b = [den_chunk[j] for j in pick if den_chunk[j].size]
        if not a or not b:
            out[i] = np.nan
            continue
        d = float(np.median(np.concatenate(b)))
        out[i] = float(np.median(np.concatenate(a))) / d if d else np.nan
    return out


def spearman_boot(x_chunk: list, y_chunk: list, draws: np.ndarray) -> np.ndarray:
    out = np.empty(draws.shape[0], dtype=float)
    for i, pick in enumerate(draws):
        xs = [x_chunk[j] for j in pick if x_chunk[j].size]
        ys = [y_chunk[j] for j in pick if y_chunk[j].size]
        if not xs:
            out[i] = np.nan
            continue
        r = spearman(np.concatenate(xs), np.concatenate(ys))
        out[i] = np.nan if r is None else r
    return out


def win(a, b) -> float:
    if not (math.isfinite(a) and math.isfinite(b)):
        return float("nan")
    if a > b:
        return 1.0
    return 0.5 if a == b else 0.0


def wins_over_columns(d: np.ndarray) -> np.ndarray:
    """§2: for each of the four facet columns, its win count against the other three, a tie
    counting ½ — the row's statistic under any relabelling of which column is the target."""
    gt = (d[:, None] > d[None, :]).astype(float)
    eq = (d[:, None] == d[None, :]).astype(float)
    return gt.sum(axis=1) + 0.5 * (eq.sum(axis=1) - 1.0)


def tag_wins(dt: np.ndarray) -> np.ndarray:
    """§3: for each tag of the chunk, its mean win against the others, a tie counting ½."""
    gt = (dt[:, None] > dt[None, :]).astype(float)
    eq = (dt[:, None] == dt[None, :]).astype(float)
    n = dt.size
    if n < 2:
        return np.full(n, np.nan)
    return (gt.sum(axis=1) + 0.5 * (eq.sum(axis=1) - 1.0)) / (n - 1)


# ------------------------------------------------------------------ the sections

def column_contrast(rows: list, other_rows: list, chunks: list, fi: int, key: str,
                    draws: np.ndarray) -> dict:
    """The target column's own base rate and the contrast against it.

    `A_facet` alone is not read against 0.5: a column that simply moves more than the others on
    every row wins whether or not it was the target. Its base rate is the same win rate on the
    rows where it is NOT the target, and `A_target - base` is the part that the intervention
    accounts for. Both arms are bootstrapped on one chunk resample, so their difference has an
    interval. `key` is `d` for the cosines and `dp` for the position deltas, which are the four
    facets' only commensurable reading (§7)."""
    g = len(chunks)
    cpos = {c: i for i, c in enumerate(chunks)}
    num, den = np.zeros(g), np.zeros(g)
    bnum, bden = np.zeros(g), np.zeros(g)
    for r in rows:
        num[cpos[r["chunk"]]] += wins_over_columns(r[key])[fi]
        den[cpos[r["chunk"]]] += 3.0
    for r in other_rows:
        bnum[cpos[r["chunk"]]] += wins_over_columns(r[key])[fi]
        bden[cpos[r["chunk"]]] += 3.0
    est = ratio_estimate(num, den, draws)
    out = {"value": est["value"], "se": est["se"], "ci": est["ci"], "n": len(rows),
           "base": None, "base_se": None, "n_base": len(other_rows),
           "contrast": None, "contrast_se": None, "contrast_ci": (None, None)}
    if bden.sum() <= 0:
        return out
    base = ratio_estimate(bnum, bden, draws)
    diff = est["boot_samples"] - base["boot_samples"]
    out.update({
        "base": base["value"], "base_se": base["se"],
        "contrast": (None if est["value"] is None or base["value"] is None
                     else est["value"] - base["value"]),
        "contrast_se": sd(diff),
        "contrast_ci": (q(diff, CI[0] / 100.0), q(diff, CI[1] / 100.0)),
    })
    return out


def facet_isolation(rows: list, chunks: list, draws: np.ndarray, rng, b: int,
                    other_rows: list | None = None) -> dict:
    """§2 rule (b): the paired facet-isolation AUC, cluster = chunk primary, cluster = row
    secondary, with the cluster-level relabelling permutation beside. `other_rows` are the same
    subset's rows targeting another facet; they give the column its base rate and the two
    contrasts, which sit beside the pre-registered A and never replace it."""
    if not rows:
        return {"n": 0}
    g = len(chunks)
    cpos = {c: i for i, c in enumerate(chunks)}
    fi = rows[0]["fi"]
    wmat = np.stack([wins_over_columns(r["d"]) for r in rows])
    num = np.zeros(g)
    den = np.zeros(g)
    for r, w in zip(rows, wmat):
        num[cpos[r["chunk"]]] += w[fi]
        den[cpos[r["chunk"]]] += 3.0
    est = ratio_estimate(num, den, draws)
    row_draws = rng.integers(0, len(rows), size=(b, len(rows)))
    row_boot = wmat[row_draws, fi].mean(axis=1) / 3.0
    ties = 0
    total = 0
    for r in rows:
        d = r["d"]
        for j in range(len(FACETS)):
            if j == fi:
                continue
            total += 1
            if d[fi] == d[j]:
                ties += 1
    no_tie = [win(r["d"][fi], r["d"][j]) for r in rows for j in range(len(FACETS))
              if j != fi and r["d"][fi] != r["d"][j]]
    # §2's permutation: one relabelling of the four columns per chunk, applied to all its
    # rows. Every row here carries the same target facet, so only the target column's image
    # under the relabelling enters the statistic, and that image is uniform over the four
    # columns — drawn directly rather than through a full permutation of them.
    s = np.zeros((g, len(FACETS)))
    for r, w in zip(rows, wmat):
        s[cpos[r["chunk"]]] += w
    picked = np.take_along_axis(s[None, :, :],
                                rng.integers(0, len(FACETS), size=(b, g, 1)), axis=2)[:, :, 0]
    perm_a = picked.sum(axis=1) / den.sum()
    row_perm = rng.integers(0, len(FACETS), size=(len(rows), b))
    row_perm_a = np.take_along_axis(wmat, row_perm, axis=1).sum(axis=0) / den.sum()
    return {
        "n": len(rows), "value": est["value"], "se_chunk": est["se"],
        "se_jack": est["se_jack"], "se_row": sd(row_boot), "ci": est["ci"],
        "bca": est["bca"], "boot_t": est["boot_t"],
        "z": (None if not est["se"] else (est["value"] - 0.5) / est["se"]),
        "perm_p_chunk": float(np.mean(perm_a >= est["value"])),
        "perm_p_row": float(np.mean(row_perm_a >= est["value"])),
        "tie_share": (ties / total if total else None),
        "auc_no_ties": mean(no_tie), "n_no_ties": len(no_tie),
        "cos": column_contrast(rows, other_rows or [], chunks, fi, "d", draws),
        "pos": column_contrast(rows, other_rows or [], chunks, fi, "dp", draws),
    }


def tag_isolation(rows: list, chunks: list, draws: np.ndarray, rng, b: int,
                  variant: str) -> dict:
    """§3 rule (c): the paired tag-isolation AUC, weighted equally per row (primary) and per
    pair (beside), with the chunk-variant topic-matched control."""
    usable = [r for r in rows if r["t_pos"] >= 0 and r["dt"].size >= 2]
    if not usable:
        return {"n": 0}
    g = len(chunks)
    cpos = {c: i for i, c in enumerate(chunks)}
    pair_num = np.zeros(g)
    pair_den = np.zeros(g)
    num = np.zeros(g)
    den = np.zeros(g)
    cnum = np.zeros(g)
    cden = np.zeros(g)
    n_contam = 0
    rows_contam = 0
    ctrl = []
    for r in usable:
        aw = tag_wins(r["dt"])
        a_r = float(aw[r["t_pos"]])
        i = cpos[r["chunk"]]
        num[i] += a_r
        den[i] += 1.0
        con = r.get("dt_contam")
        if con is None or not con.any():
            cnum[i] += a_r
            cden[i] += 1.0
        else:
            n_contam += int(con.sum())
            rows_contam += 1
            keep = [j for j in range(r["dt"].size) if j == r["t_pos"] or not con[j]]
            if len(keep) >= 2:
                sub_aw = tag_wins(r["dt"][keep])
                cnum[i] += float(sub_aw[keep.index(r["t_pos"])])
                cden[i] += 1.0
        k = r["dt"].size - 1
        pair_num[i] += a_r * k
        pair_den[i] += k
        if variant == "chunk" and math.isfinite(r["topic_c"][r["t_pos"]]):
            t0 = r["topic_c"][r["t_pos"]]
            keep = [j for j in range(r["dt"].size)
                    if j != r["t_pos"] and math.isfinite(r["topic_c"][j])
                    and abs(r["topic_c"][j] - t0) <= TOPIC_CTRL]
            if keep:
                ctrl.append(mean([win(r["dt"][r["t_pos"]], r["dt"][j]) for j in keep]))
    est = ratio_estimate(num, den, draws)
    pair_est = ratio_estimate(pair_num, pair_den, draws)
    clean_est = (ratio_estimate(cnum, cden, draws) if cden.sum() > 0
                 else {"value": None, "se": None, "ci": (None, None)})
    # §3's permutation: one relabelling of which tag is the target per chunk.
    by_chunk: dict = {}
    for r in usable:
        by_chunk.setdefault(r["chunk"], []).append(r)
    perm_tot = np.zeros(b)
    for chunk, rs in by_chunk.items():
        n_tags = max(r["dt"].size for r in rs)
        order = np.argsort(rng.random((b, n_tags)), axis=1)
        for r in rs:
            aw = tag_wins(r["dt"])
            pick = order[:, r["t_pos"]]
            pick = np.where(pick < aw.size, pick, r["t_pos"])
            perm_tot += np.nan_to_num(aw[pick], nan=0.5)
    perm_a = perm_tot / len(usable)
    return {
        "n": len(usable), "value": est["value"], "se_chunk": est["se"],
        "se_jack": est["se_jack"], "ci": est["ci"], "bca": est["bca"],
        "boot_t": est["boot_t"],
        "z": (None if not est["se"] else (est["value"] - 0.5) / est["se"]),
        "perm_p_chunk": float(np.mean(perm_a >= est["value"])),
        "pair_value": pair_est["value"], "pair_se": pair_est["se"],
        "pairs": int(pair_den.sum()),
        "control": mean(ctrl), "n_control": len(ctrl),
        "value_clean": clean_est["value"], "se_clean": clean_est["se"],
        "ci_clean": clean_est["ci"], "n_clean": int(cden.sum()),
        "contaminated_arms": n_contam, "rows_with_contamination": rows_contam,
    }


def topic_hold(rows: list, chunks: list, draws: np.ndarray, rng, b: int,
               band, noise_f, noise_topic) -> dict:
    """§4 rule (d): the equivalence band test on `median Δ_topic`, and the scale-free paired
    reading beside it."""
    vals = [r for r in rows if math.isfinite(r["d_topic"])]
    if not vals:
        return {"n": 0, "band": band}
    g = len(chunks)
    cpos = {c: i for i, c in enumerate(chunks)}
    per_chunk = [[] for _i in range(g)]
    for r in vals:
        per_chunk[cpos[r["chunk"]]].append(r["d_topic"])
    per_chunk = [np.asarray(v, dtype=float) for v in per_chunk]
    boot = median_boot(per_chunk, draws)
    m = med([r["d_topic"] for r in vals])
    ci = (q(boot, CI[0] / 100.0), q(boot, CI[1] / 100.0))
    held = None
    if band is not None and ci[0] is not None:
        held = bool(ci[0] >= -band and ci[1] <= band)
    scale_f = noise_f if noise_f else None
    scale_t = noise_topic if noise_topic else None
    num = np.zeros(g)
    den = np.zeros(g)
    num_raw = np.zeros(g)
    swapped = np.zeros(g)
    swapped_raw = np.zeros(g)
    for r in vals:
        i = cpos[r["chunk"]]
        a_raw = float(r["d"][r["fi"]])
        b_raw = float(r["d_topic"])
        num_raw[i] += win(a_raw, b_raw)
        swapped_raw[i] += win(b_raw, a_raw)
        if scale_f and scale_t:
            a_s = a_raw / scale_f
            b_s = b_raw / scale_t
        else:
            a_s, b_s = a_raw, b_raw
        num[i] += win(a_s, b_s)
        swapped[i] += win(b_s, a_s)
        den[i] += 1.0
    est = ratio_estimate(num, den, draws)
    raw_est = ratio_estimate(num_raw, den, draws)
    flips = rng.random((b, g)) < 0.5
    tot = float(den.sum())
    perm_a = (np.where(flips, swapped[None, :], num[None, :]).sum(axis=1) / tot
              if tot else np.full(b, np.nan))
    return {
        "n": len(vals), "median": m, "ci": ci, "band": band, "held": held,
        "scale_facet": scale_f, "scale_topic": scale_t,
        "a_topic": est["value"], "a_topic_se": est["se"], "a_topic_ci": est["ci"],
        "a_topic_raw": raw_est["value"], "a_topic_raw_se": raw_est["se"],
        "perm_p_chunk": float(np.mean(perm_a >= est["value"])),
        "z": (None if not est["se"] else (est["value"] - 0.5) / est["se"]),
    }


def generation_agreement(rows_w1: list, rows_w2: list, facet: str, chunks: list,
                         draws: np.ndarray, noise_floor, keep_nothing: bool) -> dict:
    """§5 rule (e): the relation is the unit; the shared minuend is broken by taking the main
    generation's Δ from write 1 and the repeat's from write 2, so what the two share is the
    relation and not one measurement of C."""
    main = {}
    rep = {}
    for r in rows_w1:
        if r["facet"] == facet and r["gen"] == "main":
            if keep_nothing or not r["nothing"]:
                main[(r["chunk"], r["tag"])] = r
    for r in rows_w2:
        if r["facet"] == facet and r["gen"] == "repeat":
            if keep_nothing or not r["nothing"]:
                rep[(r["chunk"], r["tag"])] = r
    keys = [k for k in main if k in rep]
    if len(keys) < 3:
        return {"n": len(keys)}
    g = len(chunks)
    cpos = {c: i for i, c in enumerate(chunks)}
    xs = [[] for _i in range(g)]
    ys = [[] for _i in range(g)]
    dm, dr = [], []
    for k in keys:
        a = float(main[k]["d"][main[k]["fi"]])
        b2 = float(rep[k]["d"][rep[k]["fi"]])
        xs[cpos[k[0]]].append(a)
        ys[cpos[k[0]]].append(b2)
        dm.append(a)
        dr.append(b2)
    xs = [np.asarray(v, dtype=float) for v in xs]
    ys = [np.asarray(v, dtype=float) for v in ys]
    rho = spearman(dm, dr)
    boot = spearman_boot(xs, ys, draws)
    se = sd(boot)
    # A relation whose two generations produced byte-identical counterfactual text is one
    # measurement read twice, not two; the agreement is reported without those as well.
    same = [k for k in keys if main[k]["cf_sha"] == rep[k]["cf_sha"]]
    distinct = {"n": 0, "rho": None, "se_chunk": None, "ci": (None, None)}
    if len(keys) - len(same) >= 3:
        dxs = [[] for _i in range(g)]
        dys = [[] for _i in range(g)]
        ddm, ddr = [], []
        for k in keys:
            if main[k]["cf_sha"] == rep[k]["cf_sha"]:
                continue
            a = float(main[k]["d"][main[k]["fi"]])
            b2 = float(rep[k]["d"][rep[k]["fi"]])
            dxs[cpos[k[0]]].append(a)
            dys[cpos[k[0]]].append(b2)
            ddm.append(a)
            ddr.append(b2)
        dboot = spearman_boot([np.asarray(v) for v in dxs], [np.asarray(v) for v in dys],
                              draws)
        distinct = {"n": len(ddm), "rho": spearman(ddm, ddr), "se_chunk": sd(dboot),
                    "ci": (q(dboot, CI[0] / 100.0), q(dboot, CI[1] / 100.0))}
    diff = [abs(a - b2) for a, b2 in zip(dm, dr)]
    m_main = med(dm)
    return {
        "n": len(keys), "rho": rho, "se_chunk": se,
        "ci": (q(boot, CI[0] / 100.0), q(boot, CI[1] / 100.0)),
        "fisher_se": fisher_z_se(len(keys)),
        "z": (None if not se or rho is None else rho / se),
        "median_abs_diff": med(diff), "median_main": m_main,
        "ratio": (None if not m_main else med(diff) / m_main),
        "write_noise_floor": noise_floor,
        "excess": (None if noise_floor is None or med(diff) is None
                   else med(diff) - noise_floor),
        "n_identical_texts": len(same), "distinct": distinct,
    }


def hit_sign_ratio(rows: list, chunks: list, draws: np.ndarray, rng, b: int,
                   noise_p95, noise_per_chunk) -> dict:
    """§6: the hit rate against its 2.5% reference, the clustered sign-flip test, and rule
    (a)'s ratio `R_F` with its numerator and denominator bootstrapped on one chunk resample."""
    if not rows:
        return {"n": 0}
    g = len(chunks)
    cpos = {c: i for i, c in enumerate(chunks)}
    d = np.asarray([float(r["d"][r["fi"]]) for r in rows])
    hits = (None if noise_p95 is None else float(np.mean(d > noise_p95)))
    nz = d[d != 0]
    zeros = int((d == 0).sum())
    p_plus = float(np.mean(nz > 0)) if nz.size else None
    pos = np.zeros(g)
    neg = np.zeros(g)
    for r, val in zip(rows, d):
        if val == 0:
            continue
        i = cpos[r["chunk"]]
        if val > 0:
            pos[i] += 1
        else:
            neg[i] += 1
    tot = float(pos.sum() + neg.sum())
    flips = rng.random((b, g)) < 0.5
    perm_p = (float(np.mean(
        (np.where(flips, pos[None, :], neg[None, :]).sum(axis=1) / tot) >= p_plus))
        if tot and p_plus is not None else None)
    se_p = (math.sqrt(0.25 / tot) if tot else None)
    num_chunk = [[] for _i in range(g)]
    for r, val in zip(rows, d):
        num_chunk[cpos[r["chunk"]]].append(val)
    num_chunk = [np.asarray(v, dtype=float) for v in num_chunk]
    den_chunk = [np.asarray(noise_per_chunk.get(c, []), dtype=float) for c in chunks]
    r_val = None
    r_ci = (None, None)
    r_se = None
    den_all = np.concatenate([x for x in den_chunk if x.size]) if any(
        x.size for x in den_chunk) else np.array([])
    if den_all.size:
        dm = float(np.median(den_all))
        if dm:
            r_val = float(np.median(d)) / dm
            boot = ratio_of_medians_boot(num_chunk, den_chunk, draws)
            r_se = sd(boot)
            r_ci = (q(boot, CI[0] / 100.0), q(boot, CI[1] / 100.0))
    return {
        "n": len(rows), "median_delta": float(np.median(d)), "hit_rate": hits,
        "hit_ref": HIT_REF, "noise_p95": noise_p95,
        "p_plus": p_plus, "zeros": zeros, "sign_perm_p": perm_p, "se_p_plus": se_p,
        "sign_z": (None if p_plus is None or not se_p else (p_plus - 0.5) / se_p),
        "r": r_val, "r_se": r_se, "r_ci": r_ci,
        "noise_median": (float(np.median(den_all)) if den_all.size else None),
    }


# ------------------------------------------------------------------ §7 distributions

def distribution(texts: TextSet, store: dict, variant: str, write: int,
                 population: str) -> dict:
    """§7: the `output/facet_neural/LAYER.md` columns per facet, and the Spearman matrix over
    the four facets and topic_local."""
    s = store.get((variant, write))
    if not s:
        return {"n": 0}
    cols = {f: [] for f in FACETS}
    topic = []
    by_tag: dict = {}
    by_chunk: dict = {}
    tag_chunks: dict = {}
    n = 0
    for (ti, tag), vals in s["v"].items():
        if population == "originals" and not texts.is_original[ti]:
            continue
        n += 1
        chunk = texts.chunk_of[ti]
        tag_chunks.setdefault(tag, set()).add(chunk)
        for i, f in enumerate(FACETS):
            cols[f].append(float(vals[i]))
            by_tag.setdefault(tag, {}).setdefault(f, []).append(float(vals[i]))
            by_chunk.setdefault(chunk, {}).setdefault(f, []).append(float(vals[i]))
        t = s["topic"].get((ti, tag))
        topic.append(float("nan") if t is None else float(t))
    out = {"n": n, "facets": {}, "spearman": {}}
    for f in FACETS:
        v = cols[f]
        if not v:
            out["facets"][f] = {"n": 0}
            continue
        # §7's eligibility: tags sitting on at least two of the chunks. On the originals
        # population that is one value a chunk; on the all-texts population the spread is
        # over the tag's every (chunk, text) unit, which is stated in the report.
        ts = [sd(by_tag[t][f]) for t in by_tag if len(tag_chunks[t]) > 1]
        cs = [sd(by_chunk[c][f]) for c in by_chunk if len(by_chunk[c][f]) > 1]
        out["facets"][f] = {
            "n": len(v), "min": min(v), "p5": q(v, 0.05), "median": med(v),
            "p95": q(v, 0.95), "max": max(v), "mean": mean(v), "sd": sd(v),
            "distinct": len(set(v)), "within_tag_sd": med(ts), "n_within_tag": len(ts),
            "within_chunk_sd": med(cs), "n_within_chunk": len(cs),
        }
    names = list(FACETS) + ["topic_local"]
    series = {f: cols[f] for f in FACETS}
    series["topic_local"] = topic
    for a in names:
        out["spearman"][a] = {}
        for bname in names:
            xa = np.asarray(series[a], dtype=float)
            xb = np.asarray(series[bname], dtype=float)
            ok = np.isfinite(xa) & np.isfinite(xb)
            out["spearman"][a][bname] = (1.0 if a == bname
                                         else spearman(xa[ok], xb[ok]))
    return out


def position_table(rows_by: dict, store: dict, ref: dict, variant: str) -> dict:
    """§7: `Δ_rank` and its own band `p95(|pos_w1 − pos_w2|)` — the only reading on which the
    four facets are commensurable."""
    out = {}
    a = store.get((variant, 1))
    b = store.get((variant, 2))
    for i, facet in enumerate(FACETS):
        band = None
        if a and b:
            ca = ref[(variant, 1)]["facets"][i]
            cb = ref[(variant, 2)]["facets"][i]
            diffs = []
            for k in a["v"]:
                if k not in b["v"]:
                    continue
                pa = position(ca, a["v"][k][i])
                pb = position(cb, b["v"][k][i])
                if math.isfinite(pa) and math.isfinite(pb):
                    diffs.append(abs(pa - pb))
            band = q(diffs, 0.95)
        per_write = {}
        for write in WRITES:
            rows = [r for r in rows_by.get((variant, write), []) if r["facet"] == facet]
            vals = [float(r["dp"][r["fi"]]) for r in rows
                    if math.isfinite(float(r["dp"][r["fi"]]))]
            per_write[write] = {"n": len(vals), "median": med(vals),
                                "p95": q(vals, 0.95)}
        out[facet] = {"band": band, "writes": per_write}
    return out


# ------------------------------------------------------------------ the machine diagnostic

def machine_table(texts: TextSet, store: dict, rows_by: dict, chunks: list,
                  draws: np.ndarray, rng, b: int, nz: dict, variant: str) -> dict:
    """The two writing machines side by side: the value level and the write-to-write spread per
    machine over every text, how many intervention rows straddle the two, and rule (b) and
    rule (a) recomputed on the rows whose C and C' were written by one machine. Diagnostic; the
    verdict reads all rows."""
    a = store.get((variant, 1))
    b2 = store.get((variant, 2))
    out = {}
    for i, facet in enumerate(FACETS):
        per_machine = {}
        for machine in MACHINES:
            v1, v2, diffs = [], [], []
            for (ti, tag), vals in (a["v"].items() if a else []):
                if texts.machine[ti] != machine:
                    continue
                v1.append(float(vals[i]))
                if b2 and (ti, tag) in b2["v"]:
                    other = float(b2["v"][(ti, tag)][i])
                    v2.append(other)
                    diffs.append(abs(float(vals[i]) - other))
            per_machine[machine] = {"n": len(v1), "median_w1": med(v1),
                                    "median_w2": med(v2), "n_pairs": len(diffs),
                                    "median_abs_diff": med(diffs),
                                    "p95_abs_diff": q(diffs, 0.95)}
        per_write = {}
        for write in WRITES:
            rows = [r for r in rows_by.get((variant, write), []) if r["facet"] == facet]
            if not rows:
                per_write[write] = {"n": 0}
                continue
            same = [r for r in rows if r["same_machine"]]
            nf = (nz["facets"].get(facet) or {})
            per_chunk = (nz["per_chunk"].get(facet) or {})
            fac = facet_isolation(same, chunks, draws, rng, b) if same else {}
            hit = (hit_sign_ratio(same, chunks, draws, rng, b, nf.get("p95"), per_chunk)
                   if same else {})
            per_write[write] = {
                "n": len(rows), "n_same": len(same),
                "cross_share": 1.0 - (len(same) / len(rows)),
                "a_facet_same": fac.get("value"), "a_facet_same_se": fac.get("se_chunk"),
                "r_same": hit.get("r"),
            }
        out[facet] = {"machines": per_machine, "writes": per_write}
    return out


# ------------------------------------------------------------------ §8 stripped

def stripped_diagnostic(store: dict, rows_by: dict, chunks: list, draws: np.ndarray,
                        rng, b: int, mode: str = "cos") -> dict:
    """§8: the edge value with the tag phrase struck from its own view — the level it loses and
    the rule re-run on it, for all rows and for the views the phrase never appeared in.

    §8's "share of the value that is naming" is `1 − median v'/median v`, a share only on a
    scale whose zero means no value. A cosine has one; the `xenc` logit does not, so there the
    column is the level drop `median v − median v'` and the share is not read."""
    out = {"facets": {}, "levels": {}, "share_readable": mode != "xenc"}
    for write in WRITES:
        s = store.get(("edge", write))
        if not s or not s["vs"]:
            continue
        for i, facet in enumerate(FACETS):
            v = [float(val[i]) for val in s["v"].values()]
            vp = [float(val[i]) for val in s["vs"].values()]
            rm = [int(val[i]) for val in s["rm"].values()]
            mv, mvp = med(v), med(vp)
            out["levels"].setdefault(facet, {})[write] = {
                "n": len(v), "median_v": mv, "median_v_stripped": mvp,
                "median_drop": (None if mv is None or mvp is None else mv - mvp),
                "naming_share": (None if not mv or mode == "xenc" else 1.0 - (mvp / mv)),
                "removals_mean": mean(rm),
                "zero_removal_share": (float(np.mean(np.asarray(rm) == 0)) if rm else None),
            }
    for facet in FACETS:
        per_write = {}
        for write in WRITES:
            rows = [r for r in rows_by.get(("edge", write), [])
                    if r["facet"] == facet and r["ds"] is not None]
            if not rows:
                per_write[write] = {"n": 0}
                continue
            swapped = []
            for r in rows:
                q2 = dict(r)
                q2["d"] = r["ds"]
                q2["dt"] = (r["dts"] if r["dts"] is not None else r["dt"])
                swapped.append(q2)
            zero = [r for r in swapped if r["rm_target"] == 0]
            per_write[write] = {
                "n": len(swapped),
                "a_facet": facet_isolation(swapped, chunks, draws, rng, b),
                "a_tag": tag_isolation(swapped, chunks, draws, rng, b, "edge"),
                "n_zero_removal": len(zero),
                "a_facet_zero": (facet_isolation(zero, chunks, draws, rng, b)
                                 if zero else {"n": 0}),
                "a_tag_zero": (tag_isolation(zero, chunks, draws, rng, b, "edge")
                               if zero else {"n": 0}),
                "median_delta": med([float(r["ds"][r["fi"]]) for r in rows]),
            }
        out["facets"][facet] = per_write
    return out


# ------------------------------------------------------------------ the verdict

def core_ok(sec: dict) -> dict:
    """The rule's conditions on one write, as PROGRESS.md states them and §9 guards them."""
    fac = sec.get("a_facet") or {}
    tag = sec.get("a_tag") or {}
    top = sec.get("topic") or {}
    gen = sec.get("generation") or {}
    hit = sec.get("hit") or {}
    a_val = fac.get("value")
    a_se = fac.get("se_chunk")
    t_val = tag.get("value")
    t_se = tag.get("se_chunk")
    r = hit.get("r")
    r_ci = hit.get("r_ci") or (None, None)
    a_state = "not yet"
    a_kill = False
    if r is not None and r_ci[0] is not None:
        if r <= 1.0 and r_ci[1] is not None and r_ci[1] < 1.0:
            a_state, a_kill = "kill", True
        elif r_ci[0] > 1.0:
            a_state = "clear"
        else:
            a_state = "inconclusive"
    b_ok = (a_val is not None and a_se is not None
            and (a_val - 0.5) > SE_BARS * a_se)
    c_ok = (t_val is not None and t_se is not None
            and (t_val - 0.5) > SE_BARS * t_se)
    d_ok = top.get("held")
    rho = gen.get("rho")
    rho_se = gen.get("se_chunk")
    e_ok = (rho is not None and rho_se not in (None, 0) and rho > SE_BARS * rho_se)
    guards = {
        "perm_facet": (None if fac.get("perm_p_chunk") is None
                       else fac["perm_p_chunk"] < PERM_BAR),
        "perm_tag": (None if tag.get("perm_p_chunk") is None
                     else tag["perm_p_chunk"] < PERM_BAR),
        "boot_t_facet": (None if (fac.get("boot_t") or (None, None))[0] is None
                         else fac["boot_t"][0] > 0.5),
        "boot_t_tag": (None if (tag.get("boot_t") or (None, None))[0] is None
                       else tag["boot_t"][0] > 0.5),
    }
    kill = bool(a_kill or not b_ok)
    # §9: a KILL that 24 chunks could not have avoided, whatever the data said
    by_rule = bool(kill and ((a_val is not None and RULE_BAND[0] <= a_val <= RULE_BAND[1])
                             or a_state == "inconclusive"))
    return {"a_state": a_state, "a_kill": a_kill, "b_ok": bool(b_ok), "c_ok": bool(c_ok),
            "by_rule": by_rule,
            "d_ok": (None if d_ok is None else bool(d_ok)), "e_ok": bool(e_ok),
            "guards": guards,
            "kill": bool(a_kill or not b_ok),
            "pass_core": bool(not (a_kill or not b_ok) and b_ok and c_ok
                              and d_ok is True and e_ok
                              and all(v is True for v in guards.values()))}


def verdict_of(sec1: dict, sec2: dict, have_w2: bool, have_noise: bool) -> dict:
    c1 = core_ok(sec1)
    c2 = core_ok(sec2) if have_w2 else None
    reasons = []
    if (sec1.get("a_facet") or {}).get("n", 0) == 0:
        return {"verdict": "INCONCLUSIVE", "deciding": "no rows measured on write 1",
                "core_w1": c1, "core_w2": c2}
    if c1["a_kill"]:
        reasons.append("(a) R_F <= 1, interval excludes 1")
    if not c1["b_ok"]:
        reasons.append("(b) A_facet - 0.5 <= 3 SE_chunk")
    if reasons:
        return {"verdict": "KILL", "deciding": "; ".join(reasons),
                "core_w1": c1, "core_w2": c2}
    if not have_noise:
        reasons.append("write 2 absent: rule (a) and the noise band read not yet")
    if not have_w2:
        reasons.append("write 2 absent: the replication guard of §9 cannot run")
    if c1["a_state"] == "inconclusive":
        reasons.append("(a) interval straddles 1 — inconclusive, verdict rests on (b)")
    if not c1["c_ok"]:
        reasons.append("(c) A_tag - 0.5 <= 3 SE_chunk")
    if c1["d_ok"] is not True:
        reasons.append("(d) Delta_topic not held inside the band"
                       if c1["d_ok"] is False else "(d) not yet")
    if not c1["e_ok"]:
        reasons.append("(e) generation Spearman not above 3 SE")
    for name, ok in c1["guards"].items():
        if ok is not True:
            reasons.append(f"§9 guard {name} {'failed' if ok is False else 'not yet'}")
    if have_w2 and c2 and not c2["pass_core"]:
        reasons.append("§9 guard: write 2 does not give the same verdict")
    if reasons:
        return {"verdict": "INCONCLUSIVE", "deciding": "; ".join(reasons),
                "core_w1": c1, "core_w2": c2}
    return {"verdict": "PASS",
            "deciding": "not-KILL and (c)(d)(e) and the §9 guards on both writes",
            "core_w1": c1, "core_w2": c2}


# ------------------------------------------------------------------ the register

def register(texts: TextSet, store: dict, vecs: Vectors, graph_topic, graph_vectors,
             mode: str = "cos") -> dict:
    """The register check of PROGRESS.md's diagnostics: Haiku's description against the
    tagger's `desc_emb`, and topic_local against the graph's own topic. The description cosine
    needs a vector for the description, which `xenc` never reads; the topic comparison is a
    Spearman and stands on the scorer's scale."""
    out = {"desc_cos": {}, "topic": {}}
    s = store.get(("chunk", 1))
    if not s:
        out["note"] = "no chunk/w1 views"
        return out
    if graph_vectors and mode == "xenc":
        out["desc_cos"]["note"] = ("value mode xenc reads no vectors, so the description "
                                   "cosine is not computed")
    elif graph_vectors:
        z = np.load(graph_vectors, allow_pickle=False)
        ids = [str(x) for x in z["chunk_ids"]]
        desc = np.asarray(z["desc_emb"], dtype=np.float32)
        norms = np.linalg.norm(desc, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        desc = desc / norms
        by_id = {c: desc[i] for i, c in enumerate(ids)}
        cos = {}
        for chunk in texts.chunks:
            ti = texts.orig.get(chunk)
            if ti is None or chunk not in by_id:
                continue
            local = s.get("desc_by_text", {}).get(ti)
            if local is None:
                continue
            if local.shape[0] != by_id[chunk].shape[0]:
                out["desc_cos"]["note"] = (f"dimension mismatch: local {local.shape[0]}, "
                                           f"graph {by_id[chunk].shape[0]}")
                break
            cos[chunk] = float(local @ by_id[chunk])
        vals = list(cos.values())
        out["desc_cos"].update({"n": len(vals), "min": (min(vals) if vals else None),
                                "median": med(vals), "max": (max(vals) if vals else None),
                                "per_chunk": {k: round(v, 6) for k, v in cos.items()}})
    if graph_topic:
        g = {}
        with open(graph_topic, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                g[(rec["chunk_id"], clean_tag(rec["tag"]))] = float(rec["topic_graph"])
        xs, ys = [], []
        for chunk in texts.chunks:
            ti = texts.orig.get(chunk)
            if ti is None:
                continue
            for tag in texts.tags[chunk]:
                a = s["topic"].get((ti, tag))
                b = g.get((chunk, tag))
                if a is None or b is None:
                    continue
                xs.append(float(a))
                ys.append(b)
        out["topic"] = {"n": len(xs), "spearman": spearman(xs, ys),
                        "median_local": med(xs), "median_graph": med(ys),
                        "graph_units": len(g)}
    return out


def chunk_descriptions(texts: TextSet, files: dict, vecs: Vectors) -> dict:
    """The write-1 description vector of each chunk's original text, for the register."""
    out = {}
    for sha, path in (files.get(("chunk", 1)) or {}).items():
        ti = texts.by_sha.get(sha)
        if ti is None or not texts.is_original[ti]:
            continue
        rec = json.loads(Path(path).read_text(encoding="utf-8"))
        out[ti] = vecs.get(rec["views"]["description"])
    return out


# ------------------------------------------------------------------ the report

class Doc:
    def __init__(self):
        self.lines = []

    def __call__(self, s: str = "") -> None:
        self.lines.append(s)

    def text(self) -> str:
        return "\n".join(self.lines) + "\n"


def main(argv: list | None = None) -> int:
    t0 = time.perf_counter()
    ap = argparse.ArgumentParser(description="the facet-view pilot's pre-registered check")
    ap.add_argument("--texts", required=True)
    ap.add_argument("--views", required=True)
    ap.add_argument("--vectors", action="append", default=[],
                    help="an npz of sha/vec from facet_embed_gpu.py; repeatable")
    ap.add_argument("--scores", action="append", default=[],
                    help="an npz of a_sha/b_sha/score from facet_views_xenc_gpu.py; "
                         "repeatable; --value-mode xenc reads these and no vectors")
    ap.add_argument("--cf-dir", action="append", default=[], dest="cf_dirs")
    ap.add_argument("--graph-topic", default="")
    ap.add_argument("--graph-vectors", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--boot", type=int, default=DEFAULT_B)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--embed-cpu", action="store_true",
                    help="embed whatever the vectors lack on this CPU and cache it under "
                         "--out; for the smoke and the tests")
    ap.add_argument("--ids-file", default="")
    ap.add_argument("--value-mode", default="cos", choices=list(VALUE_MODES),
                    help="what a value reads off a view: the plain cosine, the cosine of the "
                         "component orthogonal to that text's description, the cosine minus "
                         "the description's own cosine (section 5 (a) of the literature "
                         "note), or a fixed cross-encoder's score on the (phrase, view) pair "
                         "(xenc, section 5 (c))")
    ap.add_argument("--skip-missing", action="store_true",
                    help="an interim read while the writer runs: a view file whose strings are "
                         "not all in the preloaded vectors is treated as not written yet "
                         "(dropped and counted), instead of refusing the run")
    ap.add_argument("--strings-out", default="",
                    help="write every string the check needs and stop; reads no vectors")
    ap.add_argument("--pairs-out", default="",
                    help="write every (phrase, string) pair --value-mode xenc needs, in "
                         "facet_views_xenc_gpu.py's input shape, and stop; reads no scores, "
                         "and lists the same pairs whatever --value-mode says")
    args = ap.parse_args(argv)

    if args.value_mode == "xenc":
        if args.vectors or args.embed_cpu:
            raise SystemExit("facet_views_check: --value-mode xenc reads --scores, never "
                             "--vectors or --embed-cpu")
        if not (args.scores or args.pairs_out):
            raise SystemExit("facet_views_check: --value-mode xenc needs --scores (or "
                             "--pairs-out to list what to score)")
    elif args.scores:
        raise SystemExit(f"facet_views_check: --scores belongs to --value-mode xenc, not "
                         f"{args.value_mode}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"facet_views_check | texts {args.texts} | views {args.views} | out {out_dir} | "
          f"value-mode {args.value_mode} | B={args.boot:,} seed={args.seed}", flush=True)

    ids = read_ids(args.ids_file) if args.ids_file else None
    texts = read_texts(args.texts, ids)
    print(f"  {len(texts.rows):,} texts over {len(texts.chunks)} chunks, "
          f"{sum(len(v) for v in texts.tags.values())} phrase slots, "
          f"{len(texts.orig)} originals", flush=True)

    files, prompt_shas = view_files(args.views)
    for (variant, write), by_sha in sorted(files.items()):
        sha = prompt_shas.get((variant, write))
        print(f"  views {variant}/w{write}: {len(by_sha):,} done files, prompt "
              f"{(sha or 'none')[:12]}", flush=True)
    if not files:
        print("  no done view files under --views", flush=True)

    xenc = args.value_mode == "xenc"
    needs = collect_needs(texts, files, xenc or bool(args.pairs_out))
    need = needs["strings"]
    pairs = needs["pairs"]
    print(f"  {len(need):,} distinct strings needed (phrases, views, stripped views)",
          flush=True)
    if pairs:
        print(f"  {len(pairs):,} distinct (phrase, string) pairs needed by --value-mode xenc",
              flush=True)

    if args.strings_out:
        target = Path(args.strings_out)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            for sha in sorted(need):
                f.write(json.dumps({"sha": sha, "text": need[sha]},
                                   ensure_ascii=False) + "\n")
        print(f"-> {target} ({len(need):,} strings, "
              f"{sum(len(t) for t in need.values()):,} chars)", flush=True)
        return 0

    if args.pairs_out:
        target = Path(args.pairs_out)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            for a_sha, b_sha in sorted(pairs):
                a, b = pairs[(a_sha, b_sha)]
                f.write(json.dumps({"a_sha": a_sha, "a": a, "b_sha": b_sha, "b": b},
                                   ensure_ascii=False) + "\n")
        print(f"-> {target} ({len(pairs):,} pairs, "
              f"{sum(len(a) + len(b) for a, b in pairs.values()):,} chars)", flush=True)
        return 0

    vecs = Vectors()
    scores = Scores()
    cache = out_dir / "cpu_vectors.npz"
    given = set()
    for path in args.scores:
        n = scores.preload(path)
        print(f"  loaded {n:,} scores from {path}", flush=True)
    if xenc:
        print(f"  scorer {scores.model} @ {str(scores.revision)[:12]}", flush=True)
    for path in args.vectors:
        given.add(Path(path).resolve())
        n = vecs.preload(path)
        print(f"  loaded {n:,} vectors from {path}", flush=True)
    if args.embed_cpu and cache.is_file() and cache.resolve() not in given:
        n = vecs.preload(cache)
        print(f"  loaded {n:,} cached CPU vectors from {cache}", flush=True)
    gap = scores.missing(pairs) if xenc else vecs.missing(need)
    if gap and args.skip_missing and not args.embed_cpu:
        # An interim read: files that finished after the listing have nothing measured on them
        # yet. They are dropped here, counted per run, and read on the next pass; the phrases
        # themselves are always covered, so only view files can be dropped.
        missing = set(gap)
        for (variant, write), by_sha in sorted(files.items()):
            dropped = 0
            for sha in list(by_sha):
                if sha not in texts.by_sha:
                    continue
                rec = json.loads(by_sha[sha].read_text(encoding="utf-8"))
                chunk = texts.chunk_of[texts.by_sha[sha]]
                tags = texts.tags.get(chunk, [])
                if xenc:
                    absent = any((sha256_of(a), sha256_of(b)) in missing
                                 for a, b in file_pairs(rec, variant, tags))
                else:
                    plain, stripped = file_strings(rec, variant, tags)
                    absent = any(sha256_of(x) in missing for x in plain + stripped)
                if absent:
                    del by_sha[sha]
                    dropped += 1
            print(f"  --skip-missing: {variant}/w{write}: {dropped:,} files without "
                  f"{'scores' if xenc else 'vectors'} dropped, {len(by_sha):,} kept",
                  flush=True)
        needs = collect_needs(texts, files, xenc)
        need = needs["strings"]
        pairs = needs["pairs"]
        gap = scores.missing(pairs) if xenc else vecs.missing(need)
    if gap and xenc:
        a, b = pairs[gap[0]]
        raise SystemExit(
            f"facet_views_check: {len(gap):,} pairs are not in the preloaded scores "
            f"(first {gap[0][0][:12]}/{gap[0][1][:12]}, {len(a)}+{len(b)} chars). Run "
            f"--pairs-out and facet_views_xenc_gpu.py, or pass --skip-missing.")
    if gap:
        if not args.embed_cpu:
            raise SystemExit(
                f"facet_views_check: {len(gap):,} strings are not in the preloaded vectors "
                f"(first sha {gap[0][:12]}, {len(need[gap[0]])} chars). Run "
                f"--strings-out and facet_embed_gpu.py, or pass --embed-cpu.")
        print(f"  embedding {len(gap):,} missing strings on this CPU", flush=True)
        vecs.embed_cpu(need, sorted(gap), cache)
        print(f"  embedded {vecs.embedded:,}, cached to {cache}", flush=True)

    store = build_values(texts, files, vecs, args.value_mode, scores)
    ref = reference_columns(texts, store)
    n_values = write_values(out_dir / "values.jsonl", texts, store)
    emptied = sum(v["emptied"] for v in store.values())
    no_desc = sum(v["no_desc"] for v in store.values())
    print(f"  {n_values:,} values -> {out_dir / 'values.jsonl'} "
          f"(mode {args.value_mode}, {emptied:,} views emptied by the residual floor, "
          f"{no_desc:,} texts skipped for want of a description)", flush=True)

    cf_dirs = [Path(p) for p in args.cf_dirs]
    interventions, iv_counts = read_interventions(cf_dirs, texts)
    print(f"  {len(interventions):,} intervention rows over {len(cf_dirs)} generations "
          f"({iv_counts})", flush=True)

    rows_by = {}
    row_counts = {}
    for variant in fv.VARIANTS:
        for write in WRITES:
            if (variant, write) not in store:
                continue
            rows, counts = build_rows(texts, interventions, store, ref, variant, write)
            rows_by[(variant, write)] = rows
            row_counts[f"{variant}/w{write}"] = dict(counts, rows=len(rows))
            print(f"  rows {variant}/w{write}: {len(rows):,} measured, "
                  f"{counts['unmeasured']:,} unmeasured", flush=True)
    n_rows = write_rows(out_dir / "rows.jsonl", rows_by)
    print(f"  {n_rows:,} rows -> {out_dir / 'rows.jsonl'}", flush=True)

    rng = np.random.default_rng(args.seed)
    chunks = texts.chunks
    draws = cluster_draws(len(chunks), args.boot, rng)

    noise = {v: noise_table(texts, store, v) for v in fv.VARIANTS}
    cross = {v: crossed_deltas(texts, interventions, store, v) for v in fv.VARIANTS}
    repeatability = {}
    for variant in fv.VARIANTS:
        r1 = rows_by.get((variant, 1)) or []
        r2 = rows_by.get((variant, 2)) or []
        repeatability[variant] = (delta_repeat(r1, r2, cross.get(variant, {}))
                                 if r1 and r2 else {})

    print("  estimating sections 2-6 per variant, subset, write and facet",
          flush=True)
    sections: dict = {}
    for variant in fv.VARIANTS:
        if not any((variant, w) in store for w in WRITES):
            continue
        sections[variant] = {}
        nz = noise[variant]
        for subset in SUBSETS:
            sections[variant][subset] = {}
            keep_nothing = subset == "all"
            for write in WRITES:
                sections[variant][subset][write] = {}
                rows = rows_by.get((variant, write))
                if rows is None:
                    continue
                kept = [r for r in rows if keep_nothing or not r["nothing"]]
                for facet in FACETS:
                    sel = [r for r in kept if r["facet"] == facet]
                    others = [r for r in kept if r["facet"] != facet]
                    if keep_nothing:
                        nf = (nz["facets"].get(facet) or {})
                        per_chunk = (nz["per_chunk"].get(facet) or {})
                    else:
                        nf = (nz["facets_no_nothing"].get(facet) or {})
                        per_chunk = (nz["per_chunk_no_nothing"].get(facet) or {})
                    sec = {
                        "a_facet": facet_isolation(sel, chunks, draws, rng, args.boot,
                                                   others),
                        "a_tag": tag_isolation(sel, chunks, draws, rng, args.boot, variant),
                        "topic": topic_hold(sel, chunks, draws, rng, args.boot,
                                            nz["topic"].get("p95"), nf.get("p95"),
                                            nz["topic"].get("p95")),
                        "hit": hit_sign_ratio(sel, chunks, draws, rng, args.boot,
                                              nf.get("p95"), per_chunk),
                    }
                    sections[variant][subset][write][facet] = sec
            for write in WRITES:
                if write not in sections[variant][subset]:
                    continue
                for facet in FACETS:
                    if facet not in sections[variant][subset][write]:
                        continue
                    r1 = rows_by.get((variant, 1)) or []
                    r2 = rows_by.get((variant, 2)) or []
                    floor = (repeatability.get(variant, {}).get(facet, {})
                             or {}).get("median_abs_diff")
                    if write == 1:
                        gen = (generation_agreement(r1, r2, facet, chunks, draws, floor,
                                                    keep_nothing) if r1 and r2
                               else {"n": 0})
                    else:
                        gen = (generation_agreement(r2, r1, facet, chunks, draws, floor,
                                                    keep_nothing) if r1 and r2
                               else {"n": 0})
                    sections[variant][subset][write][facet]["generation"] = gen

    print("  section 7 distributions and positions", flush=True)
    dist = {}
    for variant in fv.VARIANTS:
        for write in WRITES:
            if (variant, write) not in store:
                continue
            for population in POPULATIONS:
                dist[(variant, write, population)] = distribution(texts, store, variant,
                                                                  write, population)
    pos_tables = {v: position_table(rows_by, store, ref, v)
                  for v in fv.VARIANTS if any((v, w) in store for w in WRITES)}

    print("  the two writing machines side by side", flush=True)
    machines = {v: machine_table(texts, store, rows_by, chunks, draws, rng, args.boot,
                                 noise[v], v)
                for v in fv.VARIANTS if (v, 1) in store}

    print("  section 8 stripped diagnostic", flush=True)
    stripped = (stripped_diagnostic(store, rows_by, chunks, draws, rng, args.boot,
                                    args.value_mode)
                if any(("edge", w) in store for w in WRITES) else {})

    print("  register check", flush=True)
    chunk_store = store.get(("chunk", 1))
    if chunk_store is not None and not xenc:
        chunk_store["desc_by_text"] = chunk_descriptions(texts, files, vecs)
    reg = register(texts, store, vecs, args.graph_topic, args.graph_vectors, args.value_mode)

    verdicts: dict = {}
    for variant, per_subset in sections.items():
        verdicts[variant] = {}
        for subset, per_write in per_subset.items():
            verdicts[variant][subset] = {}
            have_w2 = bool(rows_by.get((variant, 2)))
            for facet in FACETS:
                s1 = (per_write.get(1) or {}).get(facet) or {}
                s2 = (per_write.get(2) or {}).get(facet) or {}
                verdicts[variant][subset][facet] = verdict_of(
                    s1, s2, have_w2, noise[variant]["have"])

    res = {
        "meta": {
            "texts": args.texts, "views": args.views, "out": str(out_dir),
            "vectors": list(args.vectors), "scores": list(args.scores),
            "vector_provenance": vecs.provenance,
            "vectors_without_sidecar": vecs.no_sidecar,
            "cf_dirs": [str(p) for p in cf_dirs],
            "graph_topic": args.graph_topic or None,
            "graph_vectors": args.graph_vectors or None,
            "value_mode": args.value_mode,
            "scorer": {"model": scores.model, "revision": scores.revision},
            "boot": args.boot, "seed": args.seed, "embed_cpu": bool(args.embed_cpu),
            "embedded_cpu": vecs.embedded, "vectors_loaded": vecs.loaded,
            "scores_loaded": scores.loaded,
            "strings_needed": len(need), "pairs_needed": len(pairs), "dim": vecs.dim,
            "texts_header": texts.header,
            "family_size": f"{len(FACETS)} facets x {len(sections)} variants",
        },
        "counts": {
            "texts": len(texts.rows), "chunks": len(texts.chunks),
            "originals": len(texts.orig), "interventions": len(interventions),
            "intervention_counts": iv_counts, "rows": row_counts,
            "view_files": {f"{v}/w{w}": len(f) for (v, w), f in sorted(files.items())},
            "values": n_values, "row_lines": n_rows,
            "topic_source": {f"{v}/w{w}": s.get("topic_from")
                             for (v, w), s in sorted(store.items())},
            "edge_tag_gaps": {f"{v}/w{w}": s.get("gaps")
                              for (v, w), s in sorted(store.items())},
            "prompt_sha": {f"{v}/w{w}": prompt_shas.get((v, w))
                           for (v, w) in sorted(files)},
            "residual_zero": {f"{v}/w{w}": s.get("emptied")
                              for (v, w), s in sorted(store.items())},
            "no_description": {f"{v}/w{w}": s.get("no_desc")
                               for (v, w), s in sorted(store.items())},
        },
        "noise": {v: {"facets": n["facets"],
                      "facets_no_nothing": n.get("facets_no_nothing", {}),
                      "topic": n["topic"], "have": n["have"]}
                  for v, n in noise.items()},
        "delta_repeatability": repeatability,
        "sections": sections,
        "distributions": {f"{v}/w{w}/{p}": d for (v, w, p), d in dist.items()},
        "positions": pos_tables,
        "machines": machines,
        "stripped": stripped,
        "register": reg,
        "verdict": verdicts,
        "wall_s": None,
    }

    doc = build_report(res, texts, noise, sections, dist, pos_tables, stripped, verdicts,
                       row_counts, iv_counts, files, machines, args)
    (out_dir / "report.md").write_text(doc, encoding="utf-8")
    res["wall_s"] = round(time.perf_counter() - t0, 2)
    (out_dir / "verdict.json").write_text(
        json.dumps(strip_arrays(res), ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "register.md").write_text(build_register(res, reg, args), encoding="utf-8")
    print(f"-> {out_dir / 'report.md'}", flush=True)
    print(f"-> {out_dir / 'verdict.json'}", flush=True)
    print(f"-> {out_dir / 'register.md'}", flush=True)
    print(f"facet_views_check done in {time.perf_counter() - t0:.1f}s", flush=True)
    return 0


def strip_arrays(obj):
    """numpy out of the json, and the bootstrap draws out of it — the report carries the
    numbers, not the resamples."""
    if isinstance(obj, dict):
        return {k: strip_arrays(v) for k, v in obj.items()
                if k not in ("boot_samples", "per_chunk", "desc_by_text")}
    if isinstance(obj, (list, tuple)):
        return [strip_arrays(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [strip_arrays(v) for v in obj.tolist()]
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        return v if math.isfinite(v) else None
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    return obj


def build_register(res, reg, args) -> str:
    doc = Doc()
    doc("# facet_views check — register")
    doc()
    doc("cos(Haiku's write-1 description of the original text, the graph's `desc_emb` of that "
        "chunk) and Spearman(topic_local on write 1, the graph's own `topic_graph`) over the "
        "original chunk-tag units. The local embedder and the graph's NIM build are the same "
        "model at a different serving precision.")
    doc()
    dc = reg.get("desc_cos") or {}
    if not args.graph_vectors:
        doc("`--graph-vectors` not given; the description cosine is not computed.")
    elif dc.get("n"):
        doc("| n chunks | min | median | max |")
        doc("|---|---|---|---|")
        doc(f"| {dc['n']} | {fmt(dc['min'])} | {fmt(dc['median'])} | {fmt(dc['max'])} |")
        if dc.get("note"):
            doc()
            doc(dc["note"])
    else:
        doc(f"No description cosine computed ({dc.get('note', 'no matching chunks')}).")
    doc()
    tp = reg.get("topic") or {}
    if not args.graph_topic:
        doc("`--graph-topic` not given; the topic comparison is not computed.")
    elif tp.get("n"):
        doc("| n units | graph units on file | Spearman(topic_local, topic_graph) | "
            "median topic_local | median topic_graph |")
        doc("|---|---|---|---|---|")
        doc(f"| {tp['n']} | {tp.get('graph_units')} | {fmt(tp.get('spearman'))} | "
            f"{fmt(tp.get('median_local'))} | {fmt(tp.get('median_graph'))} |")
    else:
        doc("No topic units matched.")
    doc()
    return doc.text()


def build_report(res, texts, noise, sections, dist, pos_tables, stripped, verdicts,
                 row_counts, iv_counts, files, machines, args) -> str:
    doc = Doc()
    doc("# facet_views check")
    doc()
    m = res["meta"]
    doc(f"Value mode **`{m['value_mode']}`** — "
        + {"cos": "the plain cosine `cos(E(tag), E(view))`, the pre-registered reading.",
           "residual": "the cosine of the view's component orthogonal to the description of "
                       "the same text and write, re-normalised (the literature note's §5 (a); "
                       "the orchestrator's construction, not the default).",
           "relative": "`cos(E(tag), E(view)) − cos(E(tag), E(description))` on the same text "
                       "and write (the literature note's §5 (a); the orchestrator's "
                       "construction, not the default).",
           "xenc": "a fixed cross-encoder's raw score on the pair (tag, view) — the same view "
                   "strings, no new text, no model-written number (the literature note's §5 "
                   "(c) in its minimal form; the orchestrator's construction, not the "
                   "default)."}[m["value_mode"]])
    doc()
    if m["value_mode"] == "xenc":
        sc = m.get("scorer") or {}
        doc(f"Scorer `{sc.get('model')}` @ `{sc.get('revision')}`, raw logit, no sigmoid. "
            f"`topic_local` is that same scorer on (tag, description). The noise band, rule "
            f"(a) and every interval are on the scorer's own scale (§1 as written).")
    else:
        doc("`topic_local` is the plain cosine to the description under every embedding mode.")
    doc()
    doc(f"Texts `{m['texts']}`, views `{m['views']}`, B={m['boot']:,}, seed {m['seed']}. "
        f"{m['strings_needed']:,} distinct strings, "
        + (f"{m['pairs_needed']:,} distinct pairs needed, {m['scores_loaded']:,} scores "
           f"loaded. "
           if m["value_mode"] == "xenc"
           else f"{m['vectors_loaded']:,} vectors loaded, {m['embedded_cpu']:,} embedded on "
                f"this CPU, dim {m['dim']}. ")
        + f"Family size {m['family_size']}; no multiplicity correction applied (§2).")
    doc()
    doc("Every quantile, the bootstrap percentiles included, is nearest rank "
        "`round(p*(n-1))` (§1). `topic_local` for the edge variant is read from the chunk "
        "variant's description on the same text and the same write — the edge prompt writes "
        "no description of its own.")
    doc()
    prov = m.get("vector_provenance") or []
    if prov:
        one = prov[0]["meta"]
        doc(f"Vectors: {len(prov)} file(s) with a sidecar, all `{one.get('model')}` @ "
            f"`{str(one.get('revision'))[:12]}` {one.get('dtype')}, prefix "
            f"`{one.get('prefix')}` — " + ", ".join(p["file"] for p in prov) + ".")
    miss = m.get("vectors_without_sidecar") or []
    if miss:
        doc(f"**No `.meta.json` sidecar for {', '.join(miss)}** — the embedder behind those "
            f"vectors is not recorded and was not checked against the others.")
    if prov or miss:
        doc()
    shas = (res["counts"].get("prompt_sha") or {})
    if shas:
        doc("Prompt sha per run directory: "
            + ", ".join(f"{k} `{str(v)[:12]}`" for k, v in sorted(shas.items())) + ".")
        doc()

    # ---- §0
    doc("## 0. Units, keys, inclusion")
    doc()
    c = res["counts"]
    doc("| item | n |")
    doc("|---|---|")
    doc(f"| texts | {c['texts']:,} |")
    doc(f"| chunks | {c['chunks']} |")
    doc(f"| original texts | {c['originals']} |")
    doc(f"| intervention rows (changed and reconstruction_ok) | {c['interventions']:,} |")
    for k, v in sorted(c["view_files"].items()):
        doc(f"| done view files {k} | {v:,} |")
    for k, v in sorted(c["rows"].items()):
        doc(f"| rows measured {k} | {v['rows']:,} |")
        doc(f"| rows unmeasured {k} (a view file missing) | {v['unmeasured']:,} |")
        doc(f"| rows without topic_local {k} | {v['topic_unmeasured']:,} |")
    doc(f"| counterfactual pairs read | {iv_counts.get('pairs', 0):,} |")
    doc(f"| unchanged (Δ = 0 by construction, no test) | {iv_counts.get('unchanged', 0):,} |")
    doc(f"| reconstruction failures | {iv_counts.get('recon_fail', 0):,} |")
    doc(f"| counterfactual texts not in the text set | "
        f"{iv_counts.get('text_unknown', 0):,} |")
    doc(f"| values written | {c['values']:,} |")
    for k, v in sorted((c.get("residual_zero") or {}).items()):
        doc(f"| views emptied by the residual floor {k} | {v:,} |")
    for k, v in sorted((c.get("no_description") or {}).items()):
        doc(f"| texts skipped for want of a description {k} | {v:,} |")
    doc(f"| row lines written | {c['row_lines']:,} |")
    doc()

    for variant in sorted(sections):
        doc(f"# variant `{variant}`")
        doc()
        nz = noise[variant]

        # ---- §1
        doc("## 1. Writer noise and the two writes")
        doc()
        if not nz["have"]:
            doc("Write 2 is absent, so the noise band, rule (a) and the hit rate read "
                "**not yet**.")
            doc()
        else:
            doc("| facet | pairs | median \\|Δw\\| | p95 = noise | max | sd | originals n | "
                "originals median | originals p95 |")
            doc("|---|---|---|---|---|---|---|---|---|")
            for f in FACETS:
                r = nz["facets"][f]
                doc(f"| {f} | {r['n']:,} | {fmt(r['median'])} | {fmt(r['p95'])} | "
                    f"{fmt(r['max'])} | {fmt(r['sd'])} | {r['n_originals']:,} | "
                    f"{fmt(r['median_originals'])} | {fmt(r['p95_originals'])} |")
            t = nz["topic"]
            doc(f"| topic_local | {t['n']:,} | {fmt(t['median'])} | {fmt(t['p95'])} | "
                f"{fmt(t['max'])} | {fmt(t['sd'])} | {t['n_originals']:,} | "
                f"{fmt(t['median_originals'])} | — |")
            doc()
            doc("The `no_nothing` subset drops the rows whose targeted view is the absence "
                "line, so its own band drops the pairs where exactly one write wrote that "
                "line. It is the denominator of that subset's `R_F` and the cut of its hit "
                "rate; the `all` subset keeps the full band. §4's scale stays the full band "
                "under both subsets.")
            doc()
            doc("| facet | pairs kept | pairs dropped (one write only) | median \\|Δw\\| | "
                "p95 = the subset's band | max |")
            doc("|---|---|---|---|---|---|")
            for f in FACETS:
                r = (nz.get("facets_no_nothing") or {}).get(f) or {}
                doc(f"| {f} | {r.get('n', 0):,} | {r.get('dropped_one_sided', 0):,} | "
                    f"{fmt(r.get('median'))} | {fmt(r.get('p95'))} | {fmt(r.get('max'))} |")
            doc()
            rep = res["delta_repeatability"].get(variant) or {}
            if rep:
                doc("The same Δ on the two writes (§1(i)(ii)); `Δ_cross` is `v^w1(C) − "
                    "v^w2(C')`, equal in variance to the matched Δ under independent writes.")
                doc()
                doc("| facet | n | median Δ¹ | median Δ² | median \\|Δ¹−Δ²\\| | "
                    "p95 \\|Δ¹−Δ²\\| | ratio to median Δ¹ | Pearson(Δ¹,Δ²) | σ̂_w | "
                    "median Δ_cross |")
                doc("|---|---|---|---|---|---|---|---|---|---|")
                for f in FACETS:
                    r = rep.get(f) or {}
                    doc(f"| {f} | {r.get('n', 0):,} | {fmt(r.get('median_d1'))} | "
                        f"{fmt(r.get('median_d2'))} | {fmt(r.get('median_abs_diff'))} | "
                        f"{fmt(r.get('p95_abs_diff'))} | {fmt(r.get('ratio'))} | "
                        f"{fmt(r.get('pearson'))} | {fmt(r.get('sigma_w'))} | "
                        f"{fmt(r.get('median_cross'))} |")
                doc()

        for subset in SUBSETS:
            per_write = sections[variant].get(subset) or {}
            label = ("all rows" if subset == "all"
                     else "rows whose targeted view is a nothing-line excluded")
            doc(f"## 2. Facet isolation `A_facet` — subset: {label}")
            doc()
            doc("| write | facet | N rows | A | SE chunk | SE jack | SE row | z | "
                "CI pct | CI BCa | CI boot-t | perm p chunk | perm p row | tie share | "
                "A ties excluded |")
            doc("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
            for write in WRITES:
                for f in FACETS:
                    s = ((per_write.get(write) or {}).get(f) or {}).get("a_facet") or {}
                    if not s.get("n"):
                        doc(f"| w{write} | {f} | 0 | — | — | — | — | — | — | — | — | — | — |"
                            f" — | — |")
                        continue
                    doc(f"| w{write} | {f} | {s['n']:,} | {fmt(s['value'])} | "
                        f"{fmt(s['se_chunk'])} | {fmt(s['se_jack'])} | {fmt(s['se_row'])} | "
                        f"{fmt(s['z'])} | {iv(s['ci'])} | {iv(s['bca'])} | "
                        f"{iv(s['boot_t'])} | {fmt(s['perm_p_chunk'], 5)} | "
                        f"{fmt(s['perm_p_row'], 5)} | {fmt(s['tie_share'])} | "
                        f"{fmt(s['auc_no_ties'])} |")
            doc()
            doc("The column's own base rate — the same win rate on the rows where this column "
                "is NOT the target — and the contrast against it, on one chunk resample; and "
                "the same three on the position deltas, the four facets' only commensurable "
                "reading (§7). Beside the rule, which reads the pre-registered `A`.")
            doc()
            doc("| write | facet | N target | N base | A | base | A − base ± SE | CI | "
                "A pos | base pos | A − base (pos) ± SE | CI |")
            doc("|---|---|---|---|---|---|---|---|---|---|---|---|")
            for write in WRITES:
                for f in FACETS:
                    s = ((per_write.get(write) or {}).get(f) or {}).get("a_facet") or {}
                    c = s.get("cos") or {}
                    pz = s.get("pos") or {}
                    if not s.get("n"):
                        continue
                    doc(f"| w{write} | {f} | {c.get('n', 0):,} | {c.get('n_base', 0):,} | "
                        f"{fmt(c.get('value'))} | {fmt(c.get('base'))} | "
                        f"{fmt(c.get('contrast'))} ± {fmt(c.get('contrast_se'))} | "
                        f"{iv(c.get('contrast_ci'))} | {fmt(pz.get('value'))} | "
                        f"{fmt(pz.get('base'))} | {fmt(pz.get('contrast'))} ± "
                        f"{fmt(pz.get('contrast_se'))} | {iv(pz.get('contrast_ci'))} |")
            doc()

            doc(f"## 3. Tag isolation `A_tag` — subset: {label}")
            doc()
            extra = ("own-view noise p95" if variant == "edge" else "control ±0.02")
            doc(f"| write | facet | N rows | A row-weighted | SE chunk | z | CI pct | "
                f"CI BCa | CI boot-t | perm p chunk | A pair-weighted | pairs | {extra} | "
                f"n control |")
            doc("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
            for write in WRITES:
                for f in FACETS:
                    s = ((per_write.get(write) or {}).get(f) or {}).get("a_tag") or {}
                    side = (nz["facets"].get(f, {}).get("p95") if variant == "edge"
                            else s.get("control"))
                    if not s.get("n"):
                        doc(f"| w{write} | {f} | 0 | — | — | — | — | — | — | — | — | — | "
                            f"{fmt(side)} | — |")
                        continue
                    doc(f"| w{write} | {f} | {s['n']:,} | {fmt(s['value'])} | "
                        f"{fmt(s['se_chunk'])} | {fmt(s['z'])} | {iv(s['ci'])} | "
                        f"{iv(s['bca'])} | {iv(s['boot_t'])} | "
                        f"{fmt(s['perm_p_chunk'], 5)} | {fmt(s['pair_value'])} | "
                        f"{s['pairs']:,} | {fmt(side)} | {s['n_control']:,} |")
            doc()
            doc("An other-tag arm whose Δ on this text pair is itself the targeted Δ of "
                "another row (same text, same facet, same generation, another tag) is not a "
                "control; `A_tag clean` drops those arms. The rule reads the pre-registered "
                "`A_tag`, which keeps them.")
            doc()
            doc("| write | facet | rows | contaminated arms | rows touched | A_tag | "
                "A_tag clean ± SE | CI | rows in clean |")
            doc("|---|---|---|---|---|---|---|---|---|")
            for write in WRITES:
                for f in FACETS:
                    s = ((per_write.get(write) or {}).get(f) or {}).get("a_tag") or {}
                    if not s.get("n"):
                        continue
                    doc(f"| w{write} | {f} | {s['n']:,} | "
                        f"{s.get('contaminated_arms', 0):,} | "
                        f"{s.get('rows_with_contamination', 0):,} | {fmt(s['value'])} | "
                        f"{fmt(s.get('value_clean'))} ± {fmt(s.get('se_clean'))} | "
                        f"{iv(s.get('ci_clean'))} | {s.get('n_clean', 0):,} |")
            doc()

            doc(f"## 4. Δ_topic holds — subset: {label}")
            doc()
            doc("| write | facet | n | median Δ_topic | CI pct | band | held | "
                "A_topic scale-free | SE | CI | perm p | A_topic raw |")
            doc("|---|---|---|---|---|---|---|---|---|---|---|---|")
            for write in WRITES:
                for f in FACETS:
                    s = ((per_write.get(write) or {}).get(f) or {}).get("topic") or {}
                    if not s.get("n"):
                        doc(f"| w{write} | {f} | 0 | — | — | {fmt(s.get('band'))} | — | — | "
                            f"— | — | — | — |")
                        continue
                    doc(f"| w{write} | {f} | {s['n']:,} | {fmt(s['median'])} | "
                        f"{iv(s['ci'])} | {fmt(s['band'])} | {fmt(s['held'])} | "
                        f"{fmt(s['a_topic'])} | {fmt(s['a_topic_se'])} | "
                        f"{iv(s['a_topic_ci'])} | {fmt(s['perm_p_chunk'], 5)} | "
                        f"{fmt(s['a_topic_raw'])} |")
            doc()

            doc(f"## 5. Generation agreement — subset: {label}")
            doc()
            doc("Δ_main from write 1, Δ_repeat from write 2 (§5's shared-minuend "
                "correction). The write-2 replication swaps the two writes.")
            doc()
            doc("| write | facet | n relations | ρ | SE chunk | z | CI pct | Fisher-z SE | "
                "median \\|Δm−Δr\\| | median Δm | ratio | write-noise floor | excess |")
            doc("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
            for write in WRITES:
                for f in FACETS:
                    s = ((per_write.get(write) or {}).get(f) or {}).get("generation") or {}
                    if not s.get("n"):
                        doc(f"| w{write} | {f} | {s.get('n', 0)} | — | — | — | — | — | — | "
                            f"— | — | — | — |")
                        continue
                    doc(f"| w{write} | {f} | {s['n']:,} | {fmt(s['rho'])} | "
                        f"{fmt(s['se_chunk'])} | {fmt(s['z'])} | {iv(s['ci'])} | "
                        f"{fmt(s['fisher_se'])} | {fmt(s['median_abs_diff'])} | "
                        f"{fmt(s['median_main'])} | {fmt(s['ratio'])} | "
                        f"{fmt(s['write_noise_floor'])} | {fmt(s['excess'])} |")
            doc()
            doc("A relation whose two generations produced byte-identical counterfactual text "
                "is one measurement read twice; ρ is shown again with those relations out.")
            doc()
            doc("| write | facet | relations | identical texts | ρ all | ρ distinct ± SE | "
                "CI | n distinct |")
            doc("|---|---|---|---|---|---|---|---|")
            for write in WRITES:
                for f in FACETS:
                    s = ((per_write.get(write) or {}).get(f) or {}).get("generation") or {}
                    if not s.get("n"):
                        continue
                    d = s.get("distinct") or {}
                    doc(f"| w{write} | {f} | {s['n']:,} | "
                        f"{s.get('n_identical_texts', 0):,} | {fmt(s.get('rho'))} | "
                        f"{fmt(d.get('rho'))} ± {fmt(d.get('se_chunk'))} | "
                        f"{iv(d.get('ci'))} | {d.get('n', 0):,} |")
            doc()

            doc(f"## 6. Hit rate, sign test, `R_F` — subset: {label}")
            doc()
            doc("| write | facet | n | median Δ_target | noise p95 | hit rate | ref | p₊ | "
                "zeros | sign-flip p | SE(p₊) | sign z | noise median | R_F | SE | CI |")
            doc("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
            for write in WRITES:
                for f in FACETS:
                    s = ((per_write.get(write) or {}).get(f) or {}).get("hit") or {}
                    if not s.get("n"):
                        doc(f"| w{write} | {f} | 0 | — | — | — | {HIT_REF} | — | — | — | — |"
                            f" — | — | — | — | — |")
                        continue
                    doc(f"| w{write} | {f} | {s['n']:,} | {fmt(s['median_delta'])} | "
                        f"{fmt(s['noise_p95'])} | {fmt(s['hit_rate'])} | {HIT_REF} | "
                        f"{fmt(s['p_plus'])} | {s['zeros']} | "
                        f"{fmt(s['sign_perm_p'], 5)} | {fmt(s['se_p_plus'])} | "
                        f"{fmt(s['sign_z'])} | {fmt(s['noise_median'])} | {fmt(s['r'])} | "
                        f"{fmt(s['r_se'])} | {iv(s['r_ci'])} |")
            doc()

        # ---- §7
        for write in WRITES:
            for population in POPULATIONS:
                d = dist.get((variant, write, population))
                if not d or not d.get("n"):
                    continue
                doc(f"## 7. Distributions — w{write}, {population} "
                    f"({d['n']:,} chunk-tag units)")
                doc()
                doc("`within-tag sd` runs over the tags sitting on at least two chunks; "
                    "on the all-texts population its spread is over the tag's every "
                    "(chunk, text) unit, not over chunks alone.")
                doc()
                doc("| facet | min | 5% | median | 95% | max | mean | sd | distinct | "
                    "within-tag sd (median) | n tags | within-chunk sd (median) | n chunks |")
                doc("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
                for f in FACETS:
                    r = d["facets"][f]
                    if not r.get("n"):
                        doc(f"| {f} | — | — | — | — | — | — | — | — | — | — | — | — |")
                        continue
                    wt = (fmt(r["within_tag_sd"]) if r["n_within_tag"] >= 2
                          else f"unreadable (n={r['n_within_tag']})")
                    doc(f"| {f} | {fmt(r['min'])} | {fmt(r['p5'])} | {fmt(r['median'])} | "
                        f"{fmt(r['p95'])} | {fmt(r['max'])} | {fmt(r['mean'])} | "
                        f"{fmt(r['sd'])} | {r['distinct']:,} | {wt} | "
                        f"{r['n_within_tag']} | {fmt(r['within_chunk_sd'])} | "
                        f"{r['n_within_chunk']} |")
                doc()
                names = list(FACETS) + ["topic_local"]
                doc("| Spearman | " + " | ".join(names) + " |")
                doc("|---|" + "---|" * len(names))
                for a in names:
                    cells = [fmt(d["spearman"][a][b2], 3) for b2 in names]
                    doc(f"| {a} | " + " | ".join(cells) + " |")
                doc()
        pt = pos_tables.get(variant) or {}
        if pt:
            doc("## 7. Position in the originals-only column")
            doc()
            doc("| facet | band p95 \\|pos_w1−pos_w2\\| | w1 n | w1 median Δ_rank | "
                "w1 p95 | w2 n | w2 median Δ_rank | w2 p95 |")
            doc("|---|---|---|---|---|---|---|---|")
            for f in FACETS:
                r = pt.get(f) or {}
                w = r.get("writes") or {}
                a = w.get(1) or {}
                b2 = w.get(2) or {}
                doc(f"| {f} | {fmt(r.get('band'))} | {a.get('n', 0):,} | "
                    f"{fmt(a.get('median'))} | {fmt(a.get('p95'))} | {b2.get('n', 0):,} | "
                    f"{fmt(b2.get('median'))} | {fmt(b2.get('p95'))} |")
            doc()

        mt = machines.get(variant) or {}
        if mt:
            doc("## The two writing machines")
            doc()
            doc("Shards 0-1 wrote on the laptop, 2-4 on the desktop "
                "(`facet_views.shard_of(text_sha, 5)`); their CLI preambles differ in size. "
                "Diagnostic; the verdict reads all rows.")
            doc()
            doc("| facet | machine | n values | median v (w1) | median v (w2) | n pairs | "
                "median \\|w1−w2\\| | p95 \\|w1−w2\\| |")
            doc("|---|---|---|---|---|---|---|---|")
            for f in FACETS:
                for machine in MACHINES:
                    r = ((mt.get(f) or {}).get("machines") or {}).get(machine) or {}
                    doc(f"| {f} | {machine} | {r.get('n', 0):,} | {fmt(r.get('median_w1'))} "
                        f"| {fmt(r.get('median_w2'))} | {r.get('n_pairs', 0):,} | "
                        f"{fmt(r.get('median_abs_diff'))} | {fmt(r.get('p95_abs_diff'))} |")
            doc()
            doc("| facet | write | n rows | C and C' on different machines | n same-machine | "
                "A_facet same-machine ± SE | A_facet all rows ± SE | R_F same-machine | "
                "R_F all rows |")
            doc("|---|---|---|---|---|---|---|---|---|")
            for f in FACETS:
                for write in WRITES:
                    r = ((mt.get(f) or {}).get("writes") or {}).get(write) or {}
                    if not r.get("n"):
                        continue
                    allsec = ((sections[variant].get("all", {}).get(write) or {}).get(f)
                              or {})
                    fac = allsec.get("a_facet") or {}
                    hit = allsec.get("hit") or {}
                    doc(f"| {f} | w{write} | {r['n']:,} | {fmt(r['cross_share'])} | "
                        f"{r['n_same']:,} | {fmt(r['a_facet_same'])} ± "
                        f"{fmt(r['a_facet_same_se'])} | {fmt(fac.get('value'))} ± "
                        f"{fmt(fac.get('se_chunk'))} | {fmt(r['r_same'])} | "
                        f"{fmt(hit.get('r'))} |")
            doc()

    # ---- §8
    if stripped:
        doc("# 8. The `edge` tag-stripped diagnostic")
        doc()
        doc("Diagnostic only; no verdict changes on it.")
        doc()
        lv = stripped.get("levels") or {}
        if lv:
            doc("| facet | write | n values | median v | median v' | drop (v − v') | "
                "naming share (1 − v'/v) | mean removals | 0-removal share |")
            doc("|---|---|---|---|---|---|---|---|---|")
            for f in FACETS:
                for write in WRITES:
                    r = (lv.get(f) or {}).get(write)
                    if not r:
                        continue
                    doc(f"| {f} | w{write} | {r['n']:,} | {fmt(r['median_v'])} | "
                        f"{fmt(r['median_v_stripped'])} | {fmt(r['median_drop'])} | "
                        f"{fmt(r['naming_share'])} | "
                        f"{fmt(r['removals_mean'])} | {fmt(r['zero_removal_share'])} |")
            doc()
            if not stripped.get("share_readable"):
                doc("The naming share is a share only on a scale whose zero means no value; "
                    "this mode's is not one, so the column is the drop.")
                doc()
        doc("| facet | write | n | median Δ' | A_facet' | SE | A_tag' | SE | "
            "n 0-removal | A_facet' 0-removal | A_tag' 0-removal |")
        doc("|---|---|---|---|---|---|---|---|---|---|---|")
        for f in FACETS:
            for write in WRITES:
                r = (stripped.get("facets", {}).get(f) or {}).get(write)
                if not r or not r.get("n"):
                    continue
                af = r["a_facet"]
                at = r["a_tag"]
                afz = r["a_facet_zero"]
                atz = r["a_tag_zero"]
                doc(f"| {f} | w{write} | {r['n']:,} | {fmt(r['median_delta'])} | "
                    f"{fmt(af.get('value'))} | {fmt(af.get('se_chunk'))} | "
                    f"{fmt(at.get('value'))} | {fmt(at.get('se_chunk'))} | "
                    f"{r['n_zero_removal']:,} | {fmt(afz.get('value'))} | "
                    f"{fmt(atz.get('value'))} |")
        doc()

    # ---- verdict
    doc("## Verdict")
    doc()
    doc("The rule reads the `all rows` subset on write 1; the nothing-line-excluded subset "
        "sits beside it. KILL on (a) `R_F ≤ 1` with its interval excluding 1, or (b) "
        "`A_facet − 0.5 ≤ 3·SE_chunk`. PASS needs not-KILL, (c), (d), (e) and §9's guards on "
        "both writes.")
    doc()
    doc(f"`by` says whether §9 could have avoided the verdict: a KILL is **by the rule** when "
        f"A sits in [{RULE_BAND[0]}, {RULE_BAND[1]}] or R_F's interval straddles 1, and **by "
        f"the data** otherwise. `perm p` is the chunk-level permutation, `perm p row` the "
        f"row-level one; a facet whose reading turns on that choice shows it here.")
    doc()
    doc("| variant | facet | subset | R_F [CI] | A_facet ± SE | perm p | perm p row | "
        "A − base ± SE | A pos ± SE | A_tag ± SE | Δ_topic median [CI] vs band | ρ_gen ± SE | "
        "hit rate | sign p₊ | verdict | by | deciding | w2 verdict |")
    doc("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for variant in sorted(sections):
        for subset in SUBSETS:
            for f in FACETS:
                s1 = ((sections[variant].get(subset, {}).get(1) or {}).get(f)) or {}
                s2 = ((sections[variant].get(subset, {}).get(2) or {}).get(f)) or {}
                v = (verdicts.get(variant, {}).get(subset, {}).get(f)) or {}
                fac = s1.get("a_facet") or {}
                tag = s1.get("a_tag") or {}
                top = s1.get("topic") or {}
                gen = s1.get("generation") or {}
                hit = s1.get("hit") or {}
                fac2 = s2.get("a_facet") or {}
                w2 = ("not yet" if not fac2.get("n") else
                      ("kill" if (v.get("core_w2") or {}).get("kill")
                       else ("pass core" if (v.get("core_w2") or {}).get("pass_core")
                             else "inconclusive")))
                cc = fac.get("cos") or {}
                pz = fac.get("pos") or {}
                by = ("—" if v.get("verdict") != "KILL"
                      else ("by the rule" if (v.get("core_w1") or {}).get("by_rule")
                            else "by the data"))
                doc(f"| {variant} | {f} | {subset} | "
                    f"{val_iv(hit.get('r'), hit.get('r_ci'))} | "
                    f"{fmt(fac.get('value'))} ± {fmt(fac.get('se_chunk'))} | "
                    f"{fmt(fac.get('perm_p_chunk'), 5)} | "
                    f"{fmt(fac.get('perm_p_row'), 5)} | "
                    f"{fmt(cc.get('contrast'))} ± {fmt(cc.get('contrast_se'))} | "
                    f"{fmt(pz.get('value'))} ± {fmt(pz.get('se'))} | "
                    f"{fmt(tag.get('value'))} ± {fmt(tag.get('se_chunk'))} | "
                    f"{val_iv(top.get('median'), top.get('ci'))} vs "
                    f"±{fmt(top.get('band'))} | "
                    f"{fmt(gen.get('rho'))} ± {fmt(gen.get('se_chunk'))} | "
                    f"{fmt(hit.get('hit_rate'))} | {fmt(hit.get('p_plus'))} | "
                    f"**{v.get('verdict', '—')}** | {by} | {v.get('deciding', '—')} | "
                    f"{w2} |")
    doc()
    return doc.text()


if __name__ == "__main__":
    sys.exit(main())

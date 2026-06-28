"""Stage 4: chunk — form coherent episodes over the recovered structure.

Fully deterministic: no embeddings, no LLM (design §9). One top-down pass
descends each file's content collections and dispatches per content-kind, by
the probe's recovered shape — never by file extension, never by a flat
key-only classifier. The "records vs prose" call is made per position, because
one file mixes kinds (design §9.3):

  - conversation stream (declared `conversation:` in the key): a per-channel
    message stream, segmented into episodes by an adaptive time-gap and day
    boundary (design §9.4), then split at the largest internal gap over the cap.
  - prose-leaf record (a collection whose content leaf is prose per the probe's
    typical-length classification — documents, transcripts): each record is one
    coherent chunk; sibling records are NEVER merged. A record over the cap
    splits its prose leaf on seams (section > sentence > hard cut).
  - short structured record collection (no prose content leaf — prs, urls,
    meeting_chats): pack consecutive records toward the cap on clean record
    boundaries; a single over-cap record splits on prose seams.

A chunk stores REFERENCES into its content leaves in the untouched raw
(json_pointer / char_span), never copies (design §3/§7): the text is resolved
on demand for the tagger. A chunk references the content projection of its
records (the declared content leaves), not the raw bytes between them; the
exact-tiling guarantee is per-leaf — the char-span fragments of an over-cap
leaf tile that leaf exactly (lossless), reproducing it when resolved in order.

The materialized path is integer components (design §9.2): the canonical
source position, with one minted tier appended only where we draw a line the
source doesn't have — an over-cap fragment, or a flat-stream episode. Its
prefix supports context expansion (gather by prefix) and grouping (group by
prefix).
"""

from __future__ import annotations

import json
import re
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

CAP_TOKENS = 3000        # tagger focus span (design §9.1); a seed for the §15 sweep, not a verdict
GAP_FACTOR = 6           # episode break when a gap exceeds 6× the channel's median; firm via the §15 sweep
PROSE_SEAM = re.compile(r"\n\s*\n|(?<=[.!?])\s+")  # prose seams: paragraph, then sentence


def est_tokens(text: str) -> int:
    # char/4 proxy — the cap is a swept guardrail (design §9.1/§15), so the count
    # is an approximate packing guide, not an exact measure: a packed run sums its
    # records' estimates and ignores inter-record separators. Swap a real
    # tokenizer here if the §15 sweep ever needs the precision.
    return max(1, len(text) // 4)


# ---------- references ----------

@dataclass(frozen=True)
class Ref:
    scheme: str          # json_pointer | char_span
    address: object      # pointer str, or (pointer, start, end)


@dataclass(frozen=True)
class Chunk:
    file_id: str
    relpath: str
    sha256: str
    path: tuple          # materialized path — integer components
    kind: str            # conversation | prose | record
    refs: tuple          # tuple[Ref] — references into raw, resolved for the tagger view
    est_tokens: int

    @property
    def chunk_id(self) -> str:
        return f"{self.file_id}:" + ".".join(str(p) for p in self.path)


# ---------- json-pointer helpers ----------
# Minimal local copies; unify with the resolver into one pointers module when
# resolver_prototype.py graduates from prototype.

def _esc(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _unesc(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def _get(doc, pointer: str):
    """RFC 6901 get. Raises (loud) on a miss — used only on known-present pointers."""
    cur = doc
    for raw in pointer.split("/")[1:]:
        tok = _unesc(raw)
        cur = cur[int(tok)] if isinstance(cur, list) else cur[tok]
    return cur


def expand(data, pattern: str):
    """Yield each concrete json-pointer a '*'-pattern matches in `data`.
    Missing/optional fields are skipped (a PR review without a comment is fine)."""
    toks = pattern.strip("/").split("/")

    def rec(node, i, built):
        if i == len(toks):
            yield "/" + "/".join(built)
            return
        tok = toks[i]
        if tok == "*":
            if isinstance(node, list):
                for j, item in enumerate(node):
                    yield from rec(item, i + 1, built + [str(j)])
            elif isinstance(node, dict):
                for k, item in node.items():
                    yield from rec(item, i + 1, built + [_esc(k)])
        else:
            key = _unesc(tok)
            if isinstance(node, dict) and key in node:
                yield from rec(node[key], i + 1, built + [tok])
            elif isinstance(node, list) and key.lstrip("-").isdigit() and 0 <= int(key) < len(node):
                yield from rec(node[int(key)], i + 1, built + [tok])

    yield from rec(data, 0, [])


# ---------- prose splitting (over-cap single leaf) ----------

def split_prose(text: str, cap_chars: int) -> list[tuple[int, int]]:
    """Contiguous char spans tiling `text`, each ≤ cap_chars, cut on the
    strongest seam available (paragraph > sentence > hard cut). The spans tile
    the leaf exactly (lossless), so resolving them in order reproduces it."""
    def cut(lo, hi):
        if hi - lo <= cap_chars:
            return [(lo, hi)]
        best = None
        for m in PROSE_SEAM.finditer(text[lo:hi]):
            pos = lo + m.end()
            if lo < pos <= lo + cap_chars:
                best = pos          # the last seam that still fits the cap
            elif pos > lo + cap_chars:
                break
        if best is None:
            best = lo + cap_chars   # no seam in range — forced cut at a real char boundary
        return cut(lo, best) + cut(best, hi)

    return cut(0, len(text))


def _refs_json(leaves):
    return tuple(Ref("json_pointer", p) for p, _ in leaves)


def _split_leaves(rec_leaves, cap):
    """Over-cap unit → fragments ≤ cap: pack whole leaves; char-span-split a
    single leaf that alone exceeds the cap (its char spans tile it exactly)."""
    frags, cur, cur_tok = [], [], 0
    flush = lambda: frags.append((_refs_json(cur), cur_tok)) if cur else None
    for ptr, text in rec_leaves:
        lt = est_tokens(text)
        if lt > cap:
            flush(); cur, cur_tok = [], 0
            for s, e in split_prose(text, cap * 4):
                frags.append(((Ref("char_span", (ptr, s, e)),), est_tokens(text[s:e])))
        elif cur_tok + lt > cap:
            flush(); cur, cur_tok = [(ptr, text)], lt
        else:
            cur.append((ptr, text)); cur_tok += lt
    flush()
    return frags


# ---------- (b) prose-leaf records: one chunk per record ----------

def _chunk_prose_records(by_rec, c_ord, cap, ident):
    """Each record is one coherent chunk of its content leaves — sibling records
    are NEVER merged (design §9.3: a document/transcript is a coherent unit). A
    record over the cap splits its leaf on prose seams; the fragments share the
    record's path prefix."""
    out = []
    for rec_idx in sorted(by_rec):
        rec_leaves = by_rec[rec_idx]
        rec_tok = est_tokens("\n".join(t for _, t in rec_leaves))
        if rec_tok <= cap:
            out.append(_mk(ident, (c_ord, rec_idx), "prose", _refs_json(rec_leaves), rec_tok))
            continue
        for f_ord, (refs, tok) in enumerate(_split_leaves(rec_leaves, cap)):
            out.append(_mk(ident, (c_ord, rec_idx, f_ord), "prose", refs, tok))
    return out


# ---------- (c) short structured records: pack toward the cap ----------

def _chunk_short_records(by_rec, c_ord, cap, ident):
    """Pack consecutive records (source order) toward the cap on clean record
    boundaries (design §9.4): a run of small records groups into ONE chunk
    (anchored at the run's first record index), closing when the next record
    would exceed the cap — never one micro-chunk per record. A single record
    over the cap splits on prose seams."""
    out, run, run_tok, run_start = [], [], 0, None

    def flush():
        nonlocal run, run_tok, run_start
        if run:
            out.append(_mk(ident, (c_ord, run_start), "record", tuple(run), run_tok))
            run, run_tok, run_start = [], 0, None

    for rec_idx in sorted(by_rec):
        rec_leaves = by_rec[rec_idx]
        rec_tok = est_tokens("\n".join(t for _, t in rec_leaves))
        if rec_tok > cap:
            flush()
            for f_ord, (refs, tok) in enumerate(_split_leaves(rec_leaves, cap)):
                out.append(_mk(ident, (c_ord, rec_idx, f_ord), "record", refs, tok))
            continue
        if run_tok + rec_tok > cap:
            flush()
        if run_start is None:
            run_start = rec_idx
        run.extend(Ref("json_pointer", p) for p, _ in rec_leaves)
        run_tok += rec_tok
    flush()
    return out


# ---------- (a) conversation streams: channel + adaptive time-gap ----------

def _chunk_conversation(data, root, by_rec, conv, c_ord, cap, ident):
    chan_sub = "/" + conv["channel"].strip("/")
    ts_sub = "/" + conv["timestamp"].strip("/")

    msgs = []  # (rec_idx, channel, ts, [(ptr, text), ...])
    for rec_idx in sorted(by_rec):
        rec = data[root][rec_idx]
        ts = datetime.fromisoformat(_get(rec, ts_sub))
        msgs.append((rec_idx, _get(rec, chan_sub), ts, by_rec[rec_idx]))

    out = []
    for ch_ord, ch in enumerate(sorted({m[1] for m in msgs})):
        stream = sorted((m for m in msgs if m[1] == ch), key=lambda m: (m[2], m[0]))
        for ep_ord, episode in enumerate(_segment(stream)):
            frags = _split_episode(episode, cap)
            for f_ord, frag in enumerate(frags):
                path = (c_ord, ch_ord, ep_ord) if len(frags) == 1 else (c_ord, ch_ord, ep_ord, f_ord)
                refs = tuple(Ref("json_pointer", p) for m in frag for p, _ in m[3])
                tok = _ep_tokens(frag)
                if tok > cap:
                    raise RuntimeError(
                        f"single conversation message over cap ({tok}>{cap}) — {ident['relpath']} "
                        f"path={path}; messages are atoms, the seam-finder cannot split one. "
                        f"Widen the cap if this fires."
                    )
                out.append(_mk(ident, path, "conversation", refs, tok))
    return out


def _segment(stream):
    """Split a channel's time-ordered stream into episodes: a new episode on a
    day boundary or a gap much larger than the channel's local median (§9.4)."""
    if len(stream) <= 1:
        return [stream]
    gaps = [(stream[i][2] - stream[i - 1][2]).total_seconds() for i in range(1, len(stream))]
    positive = [g for g in gaps if g > 0]
    threshold = statistics.median(positive) * GAP_FACTOR if positive else 0
    episodes, cur = [], [stream[0]]
    for i in range(1, len(stream)):
        day_change = stream[i][2].date() != stream[i - 1][2].date()
        if day_change or (threshold and gaps[i - 1] > threshold):
            episodes.append(cur); cur = [stream[i]]
        else:
            cur.append(stream[i])
    episodes.append(cur)
    return episodes


def _ep_tokens(episode):
    return est_tokens("\n".join(t for m in episode for _, t in m[3]))


def _split_episode(episode, cap):
    """Over-cap episode → fragments ≤ cap, recursively cutting at the largest
    internal time-gap (the strongest seam), never an arbitrary boundary."""
    if _ep_tokens(episode) <= cap or len(episode) == 1:
        return [episode]
    gaps = [(episode[i][2] - episode[i - 1][2]).total_seconds() for i in range(1, len(episode))]
    cut = max(range(len(gaps)), key=gaps.__getitem__) + 1
    return _split_episode(episode[:cut], cap) + _split_episode(episode[cut:], cap)


# ---------- top-level ----------

def _mk(ident, path, kind, refs, tok):
    return Chunk(ident["file_id"], ident["relpath"], ident["sha256"], path, kind, refs, tok)


def _is_prose_collection(root, prose_leaves):
    """True when this collection's content leaf is prose (its pointer pattern is
    in the probe-derived prose set). Compared on the collection root because the
    prose set carries '*'-patterns (`/documents/*/content`)."""
    prefix = f"/{root}/"
    return any(p.startswith(prefix) for p in prose_leaves)


def chunk_file(data, *, file_id, relpath, sha256, key, prose_leaves=frozenset(), cap_tokens=CAP_TOKENS):
    """Chunk one parsed file. Dispatches each content collection by kind:
    conversation (key-declared) > prose-leaf record (`prose_leaves`) > short
    structured record. Returns [] for files with no content collections (e.g.
    id directories), so it is safe to run over a whole dataset.

    `prose_leaves` is the set of prose content-leaf pointer patterns recovered
    by the probe (`probe.prose_leaf_pointers`); a collection whose content leaf
    is in it holds prose records (one chunk each), otherwise it is short
    structured records (packed toward the cap)."""
    conv = {c["collection"].strip("/"): c for c in key.get("conversation", [])}
    by_collection = defaultdict(lambda: defaultdict(list))  # root -> rec_idx -> [(pointer, text)]
    for pattern in key["content"]:
        for ptr in expand(data, pattern):
            val = _get(data, ptr)
            # An empty string carries no content and no addressable span. A
            # whitespace-only value DOES stay: dropping it would silently remove
            # declared content and shift conversation segmentation (its
            # timestamp is part of the gap series).
            if not isinstance(val, str) or val == "":
                continue
            toks = ptr.strip("/").split("/")
            by_collection[toks[0]][int(toks[1])].append((ptr, val))

    ident = {"file_id": file_id, "relpath": relpath, "sha256": sha256}
    chunks = []
    for c_ord, root in enumerate(sorted(by_collection)):
        by_rec = by_collection[root]
        if root in conv:
            chunks += _chunk_conversation(data, root, by_rec, conv[root], c_ord, cap_tokens, ident)
        elif _is_prose_collection(root, prose_leaves):
            chunks += _chunk_prose_records(by_rec, c_ord, cap_tokens, ident)
        else:
            chunks += _chunk_short_records(by_rec, c_ord, cap_tokens, ident)
    return chunks


def load_key(path: Path) -> dict:
    import yaml
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def chunk_dataset(dataset_dir: Path, data_root: Path, key: dict) -> list[Chunk]:
    """Scan a corpus-view dataset dir and chunk every JSON file in it. The
    prose-vs-short classification is recovered once, by fusing the dataset's
    content files (design §5: a single file under-determines the schema)."""
    from .probe import prose_leaf_pointers
    from .scan import scan_dataset
    records = scan_dataset(dataset_dir, data_root)
    json_paths = [data_root / fr.relpath for fr in records if fr.format == "json"]
    prose_leaves = prose_leaf_pointers(json_paths)
    chunks = []
    for fr in records:
        if fr.format != "json":
            continue
        data = json.loads((data_root / fr.relpath).read_text(encoding="utf-8"))
        chunks += chunk_file(
            data, file_id=fr.file_id, relpath=fr.relpath, sha256=fr.sha256,
            key=key, prose_leaves=prose_leaves,
        )
    return chunks


def write_chunks(chunks: list[Chunk], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")

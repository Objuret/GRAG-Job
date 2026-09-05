
from __future__ import annotations

import json
import re
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

CAP_TOKENS = 3000
GAP_FACTOR = 6
PROSE_SEAM = re.compile(r"\n\s*\n|(?<=[.!?])\s+")


def est_tokens(text: str) -> int:
    return max(1, len(text) // 4)


@dataclass(frozen=True)
class Ref:
    scheme: str
    address: object


@dataclass(frozen=True)
class Chunk:
    file_id: str
    relpath: str
    sha256: str
    path: tuple
    kind: str
    refs: tuple
    est_tokens: int

    @property
    def chunk_id(self) -> str:
        return f"{self.file_id}:" + ".".join(str(p) for p in self.path)


def _esc(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _unesc(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def _get(doc, pointer: str):
    cur = doc
    for raw in pointer.split("/")[1:]:
        tok = _unesc(raw)
        cur = cur[int(tok)] if isinstance(cur, list) else cur[tok]
    return cur


def expand(data, pattern: str):
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


def split_prose(text: str, cap_chars: int) -> list[tuple[int, int]]:
    def cut(lo, hi):
        if hi - lo <= cap_chars:
            return [(lo, hi)]
        best = None
        for m in PROSE_SEAM.finditer(text[lo:hi]):
            pos = lo + m.end()
            if lo < pos <= lo + cap_chars:
                best = pos
            elif pos > lo + cap_chars:
                break
        if best is None:
            best = lo + cap_chars
        return cut(lo, best) + cut(best, hi)

    return cut(0, len(text))


def _refs_json(leaves):
    return tuple(Ref("json_pointer", p) for p, _ in leaves)


def _split_leaves(rec_leaves, cap):
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


def _chunk_prose_records(by_rec, c_ord, cap, ident):
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


def _chunk_short_records(by_rec, c_ord, cap, ident):
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


def _chunk_conversation(data, root, by_rec, conv, c_ord, cap, ident):
    chan_sub = "/" + conv["channel"].strip("/")
    ts_sub = "/" + conv["timestamp"].strip("/")

    msgs = []
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
    if _ep_tokens(episode) <= cap or len(episode) == 1:
        return [episode]
    gaps = [(episode[i][2] - episode[i - 1][2]).total_seconds() for i in range(1, len(episode))]
    cut = max(range(len(gaps)), key=gaps.__getitem__) + 1
    return _split_episode(episode[:cut], cap) + _split_episode(episode[cut:], cap)


def _mk(ident, path, kind, refs, tok):
    return Chunk(ident["file_id"], ident["relpath"], ident["sha256"], path, kind, refs, tok)


def _is_prose_collection(root, prose_leaves):
    prefix = f"/{root}/"
    return any(p.startswith(prefix) for p in prose_leaves)


def chunk_file(data, *, file_id, relpath, sha256, key, prose_leaves=frozenset(), cap_tokens=CAP_TOKENS):
    conv = {c["collection"].strip("/"): c for c in key.get("conversation", [])}
    by_collection = defaultdict(lambda: defaultdict(list))
    for pattern in key["content"]:
        for ptr in expand(data, pattern):
            val = _get(data, ptr)
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

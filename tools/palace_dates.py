"""Re-date the palace to reality: every mined drawer gets the time its content was SAID or
WRITTEN, not the time it was mined.

mempalace stamps ``filed_at`` with the mining clock and ``authored_at`` with the transcript
FILE's last timestamp, and its date filters (``since`` / ``before`` in search and list_drawers)
read ``filed_at``. The whole backlog was mined on 2026-10-04, so "since Thursday" selects nothing
useful. This script writes, per drawer:

  convos drawers   (one exchange: "> his turn" + the answer) -> the timestamp of that turn in its
                   source transcript, found by walking the transcript's user turns forward in
                   chunk order (never backwards, so a repeated "doit" lands on the right one; a
                   continuation chunk of a long answer inherits the exchange's time); a drawer
                   that matches no turn keeps its date and is counted
  sweep drawers    (one message)                              -> their own ``timestamp``
  projects drawers (documents)                                -> mempalace's own ``content_date``
                   (filename / frontmatter / body / mtime, as it recorded it)
  diary and hand-filed drawers                                -> untouched (already real time)

into BOTH ``authored_at`` and ``filed_at``, in mempalace's own local-naive ISO form; the mining
clock is kept in ``mined_at``. Metadata only: no text changes, no re-embedding, ids unchanged.
Idempotent: a drawer that already carries ``mined_at`` is skipped unless ``--force``. Dry run by
default; ``--apply`` writes. Opens the palace through mempalace's own lock, so it refuses to run
while a mine or an MCP server with a write lease holds the palace: close the Claude sessions
first, or run it straight after the ingest script (which does).

    python tools/palace_dates.py            # report what would change
    python tools/palace_dates.py --apply    # write it
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import canon_extract as ce  # noqa: E402

PAGE = 500
ISO_IN_TEXT = re.compile(r'"iso_timestamp":\s*"(\d{4}-\d{2}-\d{2}T[0-9:.]+Z?)"')
KEY_CHARS = 60
MIN_PREFIX = 20
BATCH = 500


def local_naive(ts: str) -> str | None:
    """A transcript's UTC '…Z' timestamp as mempalace writes its own stamps: local, naive, ISO."""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt.isoformat()


def key_of(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()[:KEY_CHARS].lower()


def first_line(text: str) -> str:
    for line in text.split("\n"):
        if line.strip():
            return line
    return ""


def user_turns(path: Path) -> list[tuple[str, tuple[str, str]]]:
    """(timestamp, (raw key, wrapper-stripped key)) for every user record with text, in order."""
    out: list[tuple[str, tuple[str, str]]] = []
    for obj in ce.iter_lines(path):
        if obj.get("type") not in ("user", "human"):
            continue
        content = (obj.get("message") or {}).get("content")
        tool_only = isinstance(content, list) and bool(content) and all(
            isinstance(b, dict) and b.get("type") == "tool_result" for b in content)
        if tool_only:
            continue
        text, _ = ce.message_text(obj)
        if not text.strip():
            continue
        ts = obj.get("timestamp")
        if not isinstance(ts, str):
            continue
        stripped = ce.WRAPPER_RE.sub("", text)
        out.append((ts, (key_of(first_line(text)), key_of(first_line(stripped)))))
    return out


def keys_match(k: str, tk: str) -> bool:
    if not k or not tk:
        return False
    if k == tk:
        return True
    return len(k) >= MIN_PREFIX and len(tk) >= MIN_PREFIX and (tk.startswith(k) or k.startswith(tk))


def align(drawers: list[dict], turns: list[tuple[str, tuple[str, str]]]) -> tuple[dict[str, str], int]:
    """drawer id -> transcript timestamp, drawers in chunk order; returns (mapping, unmatched)."""
    mapping: dict[str, str] = {}
    unmatched = 0
    ptr = 0
    last_ts: str | None = None
    for d in drawers:
        head = first_line(d["document"]).strip()
        if head.startswith(">"):
            k = key_of(head.lstrip(">").strip())
            hit = None
            for j in range(ptr, len(turns)):
                raw_k, clean_k = turns[j][1]
                if keys_match(k, raw_k) or keys_match(k, clean_k):
                    hit = j
                    break
            if hit is None:
                unmatched += 1
                last_ts = None  # its continuation chunks keep their date too, not the previous exchange's
                continue
            ptr = hit + 1
            last_ts = turns[hit][0]
            mapping[d["id"]] = last_ts
        elif last_ts is not None:
            mapping[d["id"]] = last_ts
        else:
            unmatched += 1
    return mapping, unmatched


def classify(meta: dict) -> str:
    mode = meta.get("ingest_mode")
    if mode == "convos":
        return "convos"
    if mode == "sweep":
        return "sweep"
    if "content_date_source" in meta or "line_start" in meta:
        return "projects"
    return "other"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--apply", action="store_true", help="write the dates (default: report only)")
    parser.add_argument("--force", action="store_true", help="re-date drawers that already carry mined_at")
    parser.add_argument("--palace", default=None, help="palace path (default: mempalace's config)")
    parser.add_argument("--sample", type=int, default=8, help="how many re-datings to print as examples")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    from mempalace.config import MempalaceConfig
    from mempalace.palace import MineAlreadyRunning, get_collection

    palace = args.palace or MempalaceConfig().palace_path
    try:
        col = get_collection(palace, create=False, read_only=not args.apply)
    except MineAlreadyRunning as exc:
        print(f"palace busy: {exc}\nclose the Claude sessions (their MCP servers hold the palace) and run again",
              file=sys.stderr)
        return 2
    total = col.count()
    print(f"palace {palace}: {total:,} drawers")

    rows: list[dict] = []
    offset = 0
    while offset < total:
        got = col.get(limit=PAGE, offset=offset, include=["metadatas", "documents"])
        ids = got.get("ids") or []
        if not ids:
            break
        for i, m, d in zip(ids, got.get("metadatas") or [], got.get("documents") or []):
            rows.append({"id": i, "meta": dict(m or {}), "document": d or ""})
        offset += len(ids)

    classes = Counter(classify(r["meta"]) for r in rows)
    print("by class: " + ", ".join(f"{k} {v:,}" for k, v in sorted(classes.items())))

    updates: list[dict] = []          # {"id", "meta", "old", "new"}
    stats: Counter = Counter()
    turns_cache: dict[str, list] = {}

    by_file: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        cls = classify(r["meta"])
        if cls == "other":
            stats["skipped other"] += 1
            continue
        if r["meta"].get("mined_at") and not args.force:
            stats["already re-dated"] += 1
            continue
        if cls == "convos":
            by_file[str(r["meta"].get("source_file") or "")].append(r)
            continue
        new = None
        if cls == "sweep":
            ts = r["meta"].get("timestamp")
            new = local_naive(ts) if isinstance(ts, str) else None
        elif cls == "projects":
            # a chunk of a canon corpus (docs/canon/raw/*.jsonl) carries its turns' own timestamps
            m = ISO_IN_TEXT.search(r["document"])
            if m:
                new = local_naive(m.group(1))
            if new is None:
                cd = r["meta"].get("content_date")
                if isinstance(cd, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", cd):
                    new = f"{cd}T00:00:00"
                else:
                    mt = r["meta"].get("source_mtime")
                    if isinstance(mt, (int, float)):
                        new = datetime.fromtimestamp(mt).isoformat()
            stats[f"projects dated by {'turn timestamp' if m else r['meta'].get('content_date_source', 'mtime')}"] += 1
        if new is None:
            stats[f"{cls} no date found"] += 1
            continue
        updates.append({"id": r["id"], "meta": r["meta"], "old": r["meta"].get("filed_at"), "new": new})
        stats[f"{cls} re-dated"] += 1

    for source, drawers in by_file.items():
        path = Path(source)
        if not path.is_file() or path.suffix != ".jsonl":
            stats["convos source missing or not a transcript"] += len(drawers)
            continue
        if source not in turns_cache:
            turns_cache[source] = user_turns(path)
        drawers.sort(key=lambda r: int(r["meta"].get("chunk_index") or 0))
        mapping, unmatched = align(drawers, turns_cache[source])
        stats["convos unmatched (date kept)"] += unmatched
        for r in drawers:
            ts = mapping.get(r["id"])
            new = local_naive(ts) if ts else None
            if new is None:
                continue
            updates.append({"id": r["id"], "meta": r["meta"], "old": r["meta"].get("filed_at"), "new": new})
            stats["convos re-dated"] += 1

    print("\n".join(f"  {k}: {v:,}" for k, v in sorted(stats.items())))
    docs_by_id = {r["id"]: r["document"] for r in rows}
    half = max(0, args.sample) // 2
    convos_sample = [u for u in updates if classify(u["meta"]) == "convos"][:half]
    other_sample = [u for u in updates if classify(u["meta"]) != "convos"][: max(0, args.sample) - half]
    for u in convos_sample + other_sample:
        head = first_line(docs_by_id.get(u["id"], ""))[:70]
        print(f"  {str(u['old'])[:19]} -> {u['new'][:19]}  {head!r}")

    if not args.apply:
        print(f"\ndry run: {len(updates):,} drawers would be re-dated; add --apply to write")
        return 0

    written = 0
    for start in range(0, len(updates), BATCH):
        batch = updates[start:start + BATCH]
        metas = []
        for u in batch:
            m = dict(u["meta"])
            if "mined_at" not in m and isinstance(m.get("filed_at"), str):
                m["mined_at"] = m["filed_at"]
            m["filed_at"] = u["new"]
            m["authored_at"] = u["new"]
            metas.append(m)
        col.update(ids=[u["id"] for u in batch], metadatas=metas)
        written += len(batch)
        print(f"  written {written:,}/{len(updates):,}", flush=True)
    print(f"\nre-dated {written:,} drawers")
    return 0


if __name__ == "__main__":
    sys.exit(main())

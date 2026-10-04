"""One model answer per chunk: for every phrase on the chunk, four plain-language answers.

The system text is `prompts/facet_answers.txt`, read at runtime and never reformulated here;
its sha256 goes into every chunk file and into the manifest. The user message carries the
tagger's own pass-2 shape (`Text:\\n<text>\\n\\nPhrases:\\n- <phrase>`), so a flattened field dump
still reads as a chunk and its phrase list. The model is asked once per chunk, through the
headless lane in `harness/chat.py`; phrases the payload leaves out are asked once more, alone.

One JSON file per chunk under `output/facet_answers/<db>/` (or `--out`). That file is the unit
of resume: a chunk is re-asked unless its file parses, carries the current prompt sha, and
answers every phrase it was given. A chunk with a `.failed.json` beside it is left alone until
`--retry-failed`. Nothing is written to the graph.

Two machines, one database. The machine that can reach Neo4j writes an export with
`--export`; the other runs `--input` on that file and needs no graph at all. The shards
partition by sha1 of the chunk id, so the two machines never ask for the same chunk, and
`--merge` folds one machine's directory into the other's.

    NEO4J_DATABASE=herb-eval-volmax python test/graph/facet_answers.py --dry-run
    python test/graph/facet_answers.py --input export.jsonl --shard 1/2 --workers 8
    python test/graph/facet_answers.py --input export.jsonl --ids "a::1,b::2" --out smoke/
"""
from __future__ import annotations

import argparse
import concurrent.futures as futures
import hashlib
import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "prod", ROOT / "test"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from harness import abort, chat
from harness.contract import generator_usage_from_chat
from artefact.querytagger import clean_tag, extract_json
from graph.db import EXCLUDED_SECTIONS

MODEL = "claude-haiku-4-5"

# The lane's own ladder sleeps 1+2+4+8+16 = 31 s across its six tries before it raises
# (harness/chat.py: MAX_TRIES = 6, time.sleep(2 ** attempt)), so the outer wait starts at the
# next rung of that same doubling and keeps doubling. The cap is the build order's, stated not
# measured: the only property it carries is that the wait stays bounded, so a usage window that
# reopens hours later is polled a few times an hour instead of never.
BACKOFF_START_S = 32.0
BACKOFF_CAP_S = 1800.0

# A payload that does not parse is asked once more; the second failure is recorded and the run
# moves on — the same two-try rule `artefact/querytagger.py` uses for its own payload.
PARSE_TRIES = 2

# A payload that parses but leaves phrases unanswered keeps its rows and the missing phrases
# are asked once more, alone. One extra ask, never a ladder.
ASK_ROUNDS = 2

# If the first calls of a run all fail for a reason no wait can mend, the lane itself is
# broken and the run stops instead of walking the whole shard into `.failed.json` files.
LANE_BROKEN_N = 3

# The manifest is written by the main thread, at most this often.
MANIFEST_EVERY_S = 1.0

# The four questions the prompt asks of every phrase.
ANSWER_FIELDS = ("temporal", "why", "activity", "concreteness")

RUN_ID = os.environ.get("HERB_TAG_RUN_ID", "pilot_full_herb")

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "facet_answers.txt"

# Text in a lane error that names a wait, not a fault: the run keeps trying.
RETRY_MARKERS = ("rate limit", "rate_limit", "ratelimit", "overloaded", "usage", "429", "529",
                 "timeout", "timed out", "timeoutexpired", "network", "connection",
                 "temporarily", "unavailable", "envelope not json")

# Text in a lane error that no wait mends.
HARD_MARKERS = ("has no backend", "no backend serves")

_STOP = threading.Event()

# Set from --out; empty means the repo's own output tree.
OUT_OVERRIDE: Path | None = None


class _HardFail(Exception):
    """The chunk cannot be answered now. `lane` marks a fault of the lane, not the payload."""

    def __init__(self, message: str, lane: bool = False):
        super().__init__(message)
        self.lane = lane


class _Stopped(Exception):
    pass


# ------------------------------------------------------------------ the prompt

def prompt_text() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def prompt_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def user_message(text: str, tags: list) -> str:
    """The tagger's own pass-2 shape (c301840 `backend/tagging/pipeline.py`):
    `Text:\\n{text}\\n\\nPhrases:\\n- {tag}`. The labels keep a flattened field dump apart from
    the phrase list under it."""
    lines = "\n".join(f"- {t}" for t in tags)
    return f"Text:\n{text.rstrip()}\n\nPhrases:\n{lines}"


# ------------------------------------------------------------------ the plan

def shard_of(chunk_id: str, n: int) -> int:
    return int(hashlib.sha1(chunk_id.encode("utf-8")).hexdigest(), 16) % n


def in_shard(chunk_id: str, k: int, n: int) -> bool:
    return shard_of(chunk_id, n) == k


def file_stem(chunk_id: str) -> str:
    """A file name that survives every filesystem and still names one chunk: the id with
    everything outside [A-Za-z0-9._-] replaced, plus the head of its sha1 so two ids that
    flatten to the same spelling still get two files. The true id is inside the file."""
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", chunk_id)[:120]
    return f"{safe}__{hashlib.sha1(chunk_id.encode('utf-8')).hexdigest()[:12]}"


def out_dir(db: str) -> Path:
    if OUT_OVERRIDE is not None:
        return Path(OUT_OVERRIDE)
    return ROOT / "output" / "facet_answers" / db


def chunk_path(db: str, chunk_id: str) -> Path:
    return out_dir(db) / f"{file_stem(chunk_id)}.json"


def failed_path(db: str, chunk_id: str) -> Path:
    return out_dir(db) / f"{file_stem(chunk_id)}.failed.json"


def manifest_path(db: str, k: int, n: int) -> Path:
    return out_dir(db) / f"manifest.{k}of{n}.json"


def lock_path(db: str, k: int, n: int) -> Path:
    return out_dir(db) / f".lock.{k}of{n}"


def status_of(path: Path, sha: str | None = None) -> str:
    """missing | unreadable | prompt_mismatch | incomplete | done."""
    if not path.is_file():
        return "missing"
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return "unreadable"
    if not isinstance(rec, dict) or not isinstance(rec.get("edges"), list):
        return "unreadable"
    if sha is not None and rec.get("prompt_sha256") != sha:
        return "prompt_mismatch"
    given, answered = rec.get("given"), rec.get("answered")
    if not isinstance(given, int) or not isinstance(answered, int):
        return "incomplete"
    if answered != given or not rec.get("complete"):
        return "incomplete"
    return "done"


def is_done(path: Path, sha: str | None = None) -> bool:
    return status_of(path, sha) == "done"


def write_json(path: Path, payload: dict) -> None:
    """Temp file then rename, so an interrupt never leaves a half file behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def sweep_tmp(directory: Path) -> int:
    n = 0
    for p in Path(directory).glob("*.tmp"):
        try:
            p.unlink()
            n += 1
        except OSError:
            pass
    return n


# ------------------------------------------------------------------ the lock

def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, int(pid))   # QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        kernel32.CloseHandle(handle)
        return bool(ok) and code.value == 259                    # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def take_lock(db: str, k: int, n: int) -> Path:
    path = lock_path(db, k, n)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        try:
            held = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            held = {}
        pid = int(held.get("pid") or 0)
        if _pid_alive(pid):
            raise SystemExit(
                f"facet_answers: shard {k}/{n} is held by pid {pid} since "
                f"{held.get('start')} ({path}) — refusing to run two of the same shard")
        print(f"  stale lock from pid {pid} — taking it over", flush=True)
    write_json(path, {"pid": os.getpid(), "host": socket.gethostname(),
                      "shard": f"{k}/{n}", "start": now_iso()})
    return path


def release_lock(path: Path) -> None:
    try:
        held = json.loads(Path(path).read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return
    if held.get("pid") == os.getpid():
        try:
            Path(path).unlink()
        except OSError:
            pass


# ------------------------------------------------------------------ the rows

_CHUNKS_CYPHER = """
MATCH (c:Chunk)<-[:HAS_CHUNK]-(f:File)
WHERE (c)-[:product]->()
  AND NOT coalesce(c.section, "") IN $excludedSections
MATCH (c)-[r:HAS_TAG]->(t:Tag)
WHERE r.run_id = $runId
WITH c, f, collect(DISTINCT t.name) AS tags
RETURN c.chunk_id AS chunk_id, c.kind AS kind, c.locator_json AS loc,
       f.rel_path AS rel_path, [(c)-[:product]->(p) | p.name] AS products, tags
ORDER BY chunk_id
"""

# The phrase list goes to the model in the order the graph collects it, the order every other
# read of these edges sees; nothing here re-orders it.
TAG_ORDER = "graph collect"


def rows_from_graph(db: str, limit: int | None = None) -> list:
    """Every product-linked chunk of `db` with its tags and its resolved text."""
    from graph import db as graphdb
    from graph.facet_stats import resolve_text

    drv = graphdb._driver()
    try:
        with drv.session(database=db) as s:
            raw = s.run(_CHUNKS_CYPHER, runId=RUN_ID,
                        excludedSections=list(EXCLUDED_SECTIONS)).data()
    finally:
        drv.close()
    rows = []
    for r in raw:
        text = resolve_text(r["loc"], r["rel_path"])
        rows.append({
            "chunk_id": r["chunk_id"],
            "kind": r["kind"],
            "product": (r["products"] or [None])[0],
            "tags": list(r["tags"]),
            "tag_order": TAG_ORDER,
            "text": text,
        })
    rows.sort(key=lambda r: r["chunk_id"])
    if limit:
        rows = rows[:limit]
    return rows


def write_export(path: Path, rows: list, header: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps({"header": header}, ensure_ascii=False) + "\n")
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_export(path: Path) -> tuple:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    if not lines:
        raise SystemExit(f"facet_answers: {path} is empty")
    first = json.loads(lines[0])
    header = first.get("header")
    if not isinstance(header, dict):
        raise SystemExit(f"facet_answers: {path} has no header line")
    rows = [json.loads(line) for line in lines[1:] if line.strip()]
    return header, rows


def read_ids(text: str, path: str) -> list:
    ids = [t.strip() for t in text.split(",") if t.strip()] if text else []
    if path:
        ids += [line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith("#")]
    out, seen = [], set()
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


# ------------------------------------------------------------------ the answer

def parse_answers(raw: dict, tags: list) -> tuple:
    """The model's object -> (rows, problems).

    Every row carries the phrase and the four answers as non-empty text. A row that carries no
    phrase or a field that is not text is dropped and named in `problems`; the phrases it left
    unanswered are asked again. A phrase that is not one of the tags given is kept and marked,
    never mended: what the model answered is what the file records."""
    if not isinstance(raw, dict):
        raise ValueError(f"payload is {type(raw).__name__}, not an object")
    rows = raw.get("edges")
    if not isinstance(rows, list) or not rows:
        raise ValueError("edges is not a non-empty list")
    given = {clean_tag(t).casefold(): t for t in tags}
    out, seen, problems = [], set(), []
    for row in rows:
        if not isinstance(row, dict):
            problems.append(f"edge row is {type(row).__name__}, not an object")
            continue
        t = clean_tag(row.get("t", ""))
        if not t:
            problems.append("an edge row carries no phrase")
            continue
        key = t.casefold()
        if key in seen:
            continue
        answers, bad = {}, None
        for field in ANSWER_FIELDS:
            v = row.get(field)
            if not isinstance(v, str) or not v.strip():
                bad = f"{field!r} of phrase {t!r} is not text: {v!r}"
                break
            answers[field] = v.strip()
        if bad:
            problems.append(bad)
            continue
        seen.add(key)
        out.append({"t": given.get(key, t), "matched": key in given, **answers})
    if not out:
        raise ValueError("no edge row survived: " + ("; ".join(problems) or "empty payload"))
    return out, problems


def retryable(err: BaseException) -> bool:
    """A lane error a wait can mend. Everything else is recorded and the run moves on."""
    if isinstance(err, (abort.Aborted, KeyboardInterrupt)):
        return False
    if isinstance(err, FileNotFoundError):                 # no `claude` on PATH
        return False
    if isinstance(err, subprocess.TimeoutExpired):
        return True
    text = f"{err!r} {err}".lower()
    if any(m in text for m in HARD_MARKERS):               # model slug, no backend
        return False
    if isinstance(err, (RuntimeError, OSError)):
        return any(m in text for m in RETRY_MARKERS)
    return False


def call_once(system: str, user: str, model: str) -> tuple:
    """One call on the lane's own timeout ladder (`harness/chat.py`), nothing added here."""
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    t0 = time.perf_counter()
    resp = chat.post("/chat/completions", payload)
    wall = time.perf_counter() - t0
    choices = resp.get("choices") or []
    content = (choices[0].get("message") or {}).get("content") if choices else None
    tin, tout = generator_usage_from_chat(resp.get("usage"))
    return content, tin, tout, wall


# ------------------------------------------------------------------ the run

class State:
    def __init__(self, total: int, done: int):
        self.lock = threading.Lock()
        self.dirty = threading.Event()
        self.total = total
        self.done = done
        self.calls = 0
        self.lane_tries = 0
        self.retries = 0
        self.parse_failures = 0
        self.incomplete = 0
        self.failures = 0
        self.lane_failures = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self.wall_s = 0.0

    def note_lane_failure(self) -> None:
        with self.lock:
            self.failures += 1
            self.lane_failures += 1
            broken = self.lane_failures >= LANE_BROKEN_N and self.done == 0
        self.dirty.set()
        if broken:
            print(f"facet_answers: the first {LANE_BROKEN_N} chunks all failed for the lane "
                  f"itself — stopping, nothing here is the payload's fault", flush=True)
            _STOP.set()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_manifest(db: str, state: State, meta: dict, k: int, n: int) -> None:
    """Written by the main thread only. A transient filesystem refusal is printed, not fatal."""
    with state.lock:
        payload = dict(meta)
        payload.update({
            "done": state.done,
            "remaining": max(0, state.total - state.done),
            "totals": {
                "calls": state.calls,
                "lane_tries": state.lane_tries,
                "retries": state.retries,
                "parse_failures": state.parse_failures,
                "incomplete": state.incomplete,
                "failures": state.failures,
                "tokens_in": state.tokens_in,
                "tokens_out": state.tokens_out,
                "wall_s": round(state.wall_s, 1),
            },
            "last_update": now_iso(),
        })
    try:
        write_json(manifest_path(db, k, n), payload)
    except OSError as err:
        print(f"    manifest not written this round ({err})", flush=True)


def _call_with_ladder(system: str, user: str, model: str, state: State, chunk_id: str) -> tuple:
    backoff = BACKOFF_START_S
    while not _STOP.is_set():
        chat.reset_timing()
        try:
            content, tin, tout, wall = call_once(system, user, model)
        except Exception as err:
            lane_tries = int(chat.take_timing().get("attempts", 0))
            with state.lock:
                state.lane_tries += lane_tries
            if not retryable(err):
                raise _HardFail(repr(err), lane=True) from err
            with state.lock:
                state.retries += 1
            state.dirty.set()
            nxt = time.strftime("%H:%M:%S", time.localtime(time.time() + backoff))
            print(f"    {chunk_id}: call failed ({err}) — next try {nxt} "
                  f"(+{backoff:.0f}s)", flush=True)
            _STOP.wait(backoff)
            backoff = min(backoff * 2, BACKOFF_CAP_S)
            continue
        lane_tries = int(chat.take_timing().get("attempts", 0))
        with state.lock:
            state.calls += 1
            state.lane_tries += lane_tries
            state.tokens_in += tin
            state.tokens_out += tout
            state.wall_s += wall
        state.dirty.set()
        return content, tin, tout, wall
    raise _Stopped()


def answer_chunk(row: dict, db: str, system: str, sha: str, model: str, state: State) -> None:
    if _STOP.is_set():
        return
    chunk_id = row["chunk_id"]
    given = list(row["tags"])
    given_keys = {clean_tag(t).casefold(): t for t in given}
    kept: dict = {}
    raws: list = []
    problems: list = []
    calls = 0
    tin_total = tout_total = 0
    wall_total = 0.0
    ask = list(given)

    try:
        for round_no in range(1, ASK_ROUNDS + 1):
            parse_tries = 0
            while True:
                user = user_message(row["text"], ask)
                content, tin, tout, wall = _call_with_ladder(system, user, model, state,
                                                             chunk_id)
                calls += 1
                raws.append(content)
                tin_total += tin
                tout_total += tout
                wall_total += wall
                try:
                    if not content:
                        raise ValueError("empty content")
                    new_rows, bad = parse_answers(extract_json(content), ask)
                except ValueError as err:
                    parse_tries += 1
                    with state.lock:
                        state.parse_failures += 1
                    state.dirty.set()
                    if parse_tries < PARSE_TRIES:
                        print(f"    {chunk_id}: payload did not parse ({err}) — "
                              f"asking once more", flush=True)
                        continue
                    raise _HardFail(f"payload did not parse: {err}")
                problems.extend(bad)
                break
            for r in new_rows:
                kept.setdefault(clean_tag(r["t"]).casefold(), r)
            missing = [t for key, t in given_keys.items() if key not in kept]
            if not missing or round_no == ASK_ROUNDS:
                break
            print(f"    {chunk_id}: {len(missing)} of {len(given)} phrases unanswered — "
                  f"asking for those alone", flush=True)
            ask = missing
    except _Stopped:
        return
    except _HardFail as err:
        write_json(failed_path(db, chunk_id), {
            "chunk_id": chunk_id, "kind": row["kind"], "product": row["product"],
            "tags": given, "tag_order": row.get("tag_order", TAG_ORDER),
            "error": str(err), "lane": err.lane, "missing": [t for key, t in given_keys.items()
                                                             if key not in kept],
            "raw": raws, "model": model, "prompt_sha256": sha, "timestamp": now_iso(),
        })
        print(f"    {chunk_id}: FAILED ({err}) — recorded", flush=True)
        if err.lane:
            state.note_lane_failure()
        else:
            with state.lock:
                state.failures += 1
            state.dirty.set()
        return

    edges = [kept[key] for key in given_keys if key in kept]
    edges += [r for key, r in kept.items() if key not in given_keys]
    answered = sum(1 for key in given_keys if key in kept)
    missing = [t for key, t in given_keys.items() if key not in kept]
    complete = not missing

    write_json(chunk_path(db, chunk_id), {
        "chunk_id": chunk_id,
        "kind": row["kind"],
        "product": row["product"],
        "tags": given,
        "tag_order": row.get("tag_order", TAG_ORDER),
        "given": len(given),
        "answered": answered,
        "complete": complete,
        "edges": edges,
        "problems": problems,
        "raw": raws,
        "usage": {"tokens_in": tin_total, "tokens_out": tout_total},
        "wall_s": round(wall_total, 2),
        "tries": calls,
        "model": model,
        "prompt_sha256": sha,
        "timestamp": now_iso(),
    })
    if complete:
        with state.lock:
            state.done += 1
            done, total = state.done, state.total
    else:
        write_json(failed_path(db, chunk_id), {
            "chunk_id": chunk_id, "kind": row["kind"], "product": row["product"],
            "tags": given, "tag_order": row.get("tag_order", TAG_ORDER),
            "error": f"{len(missing)} of {len(given)} phrases unanswered after "
                     f"{ASK_ROUNDS} asks",
            "lane": False, "missing": missing, "problems": problems,
            "model": model, "prompt_sha256": sha, "timestamp": now_iso(),
        })
        with state.lock:
            state.incomplete += 1
            state.failures += 1
            done, total = state.done, state.total
    state.dirty.set()
    print(f"[{done}/{total}] {chunk_id} kind={row['kind']} tags={len(given)} "
          f"answered={answered} complete={complete} in={tin_total} out={tout_total} "
          f"wall={wall_total:.1f}s calls={calls}", flush=True)


# ------------------------------------------------------------------ merge

def merge(db: str, source: Path, sha: str) -> dict:
    """Fold another machine's directory into this one. A file written under a different prompt
    refuses the whole merge — the two halves would not be one layer. A chunk already here is a
    duplicate when the two files say the same thing and a conflict when they do not."""
    src = Path(source)
    if not src.is_dir():
        raise SystemExit(f"facet_answers --merge: {src} is not a directory")
    dest = out_dir(db)
    dest.mkdir(parents=True, exist_ok=True)
    sweep_tmp(dest)
    copied = duplicates = conflicts = skipped = 0
    for path in sorted(src.glob("*.json")):
        if path.name.startswith("manifest.") or path.name.endswith(".failed.json"):
            continue
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            skipped += 1
            continue
        if not isinstance(rec, dict) or not isinstance(rec.get("edges"), list):
            skipped += 1
            continue
        if rec.get("prompt_sha256") != sha:
            raise SystemExit(
                f"facet_answers --merge: {path.name} was written under prompt "
                f"{str(rec.get('prompt_sha256'))[:12]}, this directory is "
                f"{sha[:12]} — refusing")
        target = chunk_path(db, rec["chunk_id"])
        if target.is_file():
            try:
                here = json.loads(target.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                here = None
            if (isinstance(here, dict) and here.get("prompt_sha256") == rec.get("prompt_sha256")
                    and here.get("edges") == rec.get("edges")):
                duplicates += 1
            else:
                conflicts += 1
            continue
        write_json(target, rec)
        copied += 1
    return {"copied": copied, "duplicates": duplicates, "conflicts": conflicts,
            "skipped": skipped}


# ------------------------------------------------------------------ cli

def parse_shard(text: str) -> tuple:
    try:
        k, n = text.split("/")
        k, n = int(k), int(n)
    except ValueError:
        raise SystemExit(f"facet_answers: --shard wants K/N, got {text!r}")
    if n < 1 or not 0 <= k < n:
        raise SystemExit(f"facet_answers: --shard {text} is out of range")
    return k, n


def corpus_sha() -> str | None:
    from harness import provenance
    d = provenance.tree_digest(ROOT / "data" / "corpus")
    return d["sha256"] if d else None


def _on_interrupt(signum, frame) -> None:
    _STOP.set()
    print("\ninterrupted — no new call is started, every finished chunk is on disk",
          flush=True)


def _utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def main(argv: list | None = None) -> int:
    global OUT_OVERRIDE
    _utf8_console()
    ap = argparse.ArgumentParser(description="four plain answers per phrase, one call a chunk")
    ap.add_argument("--db", default=os.environ.get("NEO4J_DATABASE", "herb-eval-volmax"))
    ap.add_argument("--input", default="", help="run from an export file, no graph read")
    ap.add_argument("--export", default="", help="write the export file and stop")
    ap.add_argument("--merge", default="", help="fold another machine's output dir into this")
    ap.add_argument("--out", default="", help="write the chunk files here "
                                              "(default output/facet_answers/<db>/)")
    ap.add_argument("--shard", default="0/1", help="K/N by sha1 of the chunk id")
    ap.add_argument("--ids", default="", help="run exactly these chunk ids, comma separated; "
                                              "the shard rule is not applied")
    ap.add_argument("--ids-file", default="", help="the same, one chunk id per line")
    ap.add_argument("--workers", type=int, default=1,
                    help="parallel chunks (default 1; the harness's judge lane in "
                         "prod/run.py auto-sizes to one worker per question x metric cell)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--retry-failed", action="store_true",
                    help="drop the .failed.json markers of this shard and ask those again")
    ap.add_argument("--allow-prompt-mismatch", action="store_true",
                    help="re-ask chunks whose file was written under another prompt instead "
                         "of refusing the run")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the plan and the counts, call nothing")
    args = ap.parse_args(argv)

    t0 = time.perf_counter()
    print(f"facet_answers starting | db {args.db} | "
          f"{'input ' + args.input if args.input else 'reading the graph'}", flush=True)
    system = prompt_text()
    sha = prompt_sha(system)
    k, n = parse_shard(args.shard)
    db = args.db
    OUT_OVERRIDE = Path(args.out) if args.out else None

    if args.merge:
        print(f"facet_answers merge | db {db} | prompt {sha[:12]}", flush=True)
        print(f"  {merge(db, Path(args.merge), sha)}", flush=True)
        return 0

    if args.input:
        header, rows = read_export(Path(args.input))
        db = header.get("db", db)
        source = f"file {args.input}"
        corpus = header.get("corpus_sha256")
        if header.get("prompt_sha256") != sha:
            print(f"  note: export was written under prompt "
                  f"{str(header.get('prompt_sha256'))[:12]}, this prompt is {sha[:12]}",
                  flush=True)
    else:
        source = f"graph {db}"
        corpus = corpus_sha()
        rows = rows_from_graph(db, None)

    no_text = [r for r in rows if not r.get("text")]
    no_tags = [r for r in rows if not r.get("tags")]
    rows = [r for r in rows if r.get("text") and r.get("tags")]

    if args.export:
        write_export(Path(args.export), rows, {
            "db": db, "prompt_sha256": sha, "corpus_sha256": corpus,
            "model": args.model, "n_chunks": len(rows), "tag_order": TAG_ORDER,
            "written": now_iso(),
        })
        print(f"facet_answers export | {source} | {len(rows)} chunks -> {args.export} "
              f"| prompt {sha[:12]} | corpus {str(corpus)[:12]}", flush=True)
        return 0

    wanted = read_ids(args.ids, args.ids_file)
    if wanted:
        by_id = {r["chunk_id"]: r for r in rows}
        mine = [by_id[i] for i in wanted if i in by_id]
        absent = [i for i in wanted if i not in by_id]
        if absent:
            print(f"  ids not in this source: {', '.join(absent[:10])}"
                  f"{' …' if len(absent) > 10 else ''}", flush=True)
    else:
        mine = [r for r in rows if in_shard(r["chunk_id"], k, n)]
    if args.limit:
        mine = mine[:args.limit]

    if args.retry_failed:
        dropped = 0
        for r in mine:
            p = failed_path(db, r["chunk_id"])
            if p.is_file():
                p.unlink()
                dropped += 1
        print(f"  --retry-failed: dropped {dropped} failure markers", flush=True)

    done_rows, todo, failed_rows, mismatched = [], [], [], []
    for r in mine:
        if failed_path(db, r["chunk_id"]).is_file():
            failed_rows.append(r)
            continue
        state_name = status_of(chunk_path(db, r["chunk_id"]), sha)
        if state_name == "done":
            done_rows.append(r)
        elif state_name == "prompt_mismatch":
            mismatched.append(r)
        else:
            todo.append(r)
    if mismatched and not args.allow_prompt_mismatch:
        for r in mismatched[:10]:
            print(f"  {r['chunk_id']}: file written under another prompt, this prompt is "
                  f"{sha[:12]}", flush=True)
        raise SystemExit(
            f"facet_answers: {len(mismatched)} chunk files were written under another prompt "
            f"— pass --allow-prompt-mismatch to ask them again under {sha[:12]}")
    todo += mismatched

    tags_total = sum(len(r["tags"]) for r in rows)
    tags_mine = sum(len(r["tags"]) for r in todo)

    print(f"facet_answers | {source} | prompt {sha[:12]} | corpus {str(corpus)[:12]} "
          f"| model {args.model}", flush=True)
    print(f"  chunks {len(rows)} (tags {tags_total}, order {TAG_ORDER}) "
          f"| no text {len(no_text)} | no tags {len(no_tags)}", flush=True)
    scope = f"ids {len(mine)}" if wanted else f"shard {k}/{n}: {len(mine)} chunks"
    print(f"  {scope} | done {len(done_rows)} | failed {len(failed_rows)} "
          f"| re-ask on prompt {len(mismatched)} | remaining {len(todo)} "
          f"(tags {tags_mine}) | workers {args.workers}", flush=True)
    two = [sum(1 for r in rows if in_shard(r["chunk_id"], i, 2)) for i in (0, 1)]
    print(f"  two-machine split: 0/2 = {two[0]} chunks, 1/2 = {two[1]} chunks", flush=True)
    print(f"  out {out_dir(db)}", flush=True)
    print(f"  plan in {time.perf_counter() - t0:.1f}s", flush=True)

    if args.dry_run:
        return 0

    swept = sweep_tmp(out_dir(db)) if out_dir(db).is_dir() else 0
    if swept:
        print(f"  swept {swept} stale .tmp files", flush=True)
    lock = take_lock(db, k, n)

    meta = {"db": db, "source": source, "prompt_path": str(PROMPT_PATH),
            "prompt_sha256": sha, "corpus_sha256": corpus, "model": args.model,
            "shard": f"{k}/{n}", "ids": wanted, "tag_order": TAG_ORDER,
            "workers": args.workers, "start": now_iso()}
    state = State(total=len(mine), done=len(done_rows))
    write_manifest(db, state, meta, k, n)

    try:
        previous = signal.signal(signal.SIGINT, _on_interrupt)
    except (ValueError, OSError):
        previous = None
    abort.watch()
    print("running — press q to stop after the running chunks, Ctrl-C to stop now",
          flush=True)

    def work(row):
        answer_chunk(row, db, system, sha, args.model, state)

    pool = ThreadPoolExecutor(max_workers=max(1, args.workers))
    submitted = [pool.submit(work, row) for row in todo]
    pending = set(submitted)
    last_manifest = 0.0
    try:
        while pending:
            if abort.aborted() and not _STOP.is_set():
                _STOP.set()
            if _STOP.is_set():
                pool.shutdown(wait=False, cancel_futures=True)
                break
            _, pending = futures.wait(pending, timeout=MANIFEST_EVERY_S,
                                      return_when=futures.FIRST_COMPLETED)
            if state.dirty.is_set() and time.time() - last_manifest >= MANIFEST_EVERY_S:
                state.dirty.clear()
                write_manifest(db, state, meta, k, n)
                last_manifest = time.time()
    except KeyboardInterrupt:
        _STOP.set()
        pool.shutdown(wait=False, cancel_futures=True)
        print("\ninterrupted — every finished chunk is on disk", flush=True)
    finally:
        pool.shutdown(wait=True)
        if previous is not None:
            try:
                signal.signal(signal.SIGINT, previous)
            except (ValueError, OSError):
                pass
        write_manifest(db, state, meta, k, n)
        release_lock(lock)

    for f in submitted:
        if f.done() and not f.cancelled() and f.exception() is not None:
            print(f"  worker raised: {f.exception()!r}", flush=True)
    print(f"done {state.done}/{state.total} | calls {state.calls} "
          f"| lane tries {state.lane_tries} | retries {state.retries} "
          f"| incomplete {state.incomplete} | failures {state.failures} "
          f"| tokens {state.tokens_in}/{state.tokens_out} "
          f"| {time.perf_counter() - t0:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

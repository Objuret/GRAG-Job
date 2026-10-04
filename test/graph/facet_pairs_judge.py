"""One Opus call per presented pair: five A / B / equal choices, no number.

A row of a pairs file is one presentation of one pair — the two relationships in one order.
The judge sees two phrases and two texts and nothing else: no ids, no pair type, no known
value. The system text is a prompt file read at runtime and never reformulated here; its
sha256 goes into every answer file and into the manifest.

One JSON file per row under `<out>/<set>/<row_id>.json`. That file is the unit of resume: a
row is re-asked unless its file parses, carries the current prompt sha, and carries five valid
answers. A row with a `.failed.json` beside it is left alone until `--retry-failed`. Nothing
is written to the graph.

The plan, the shard rule, the lock, the manifest, the retry ladder, the parse re-ask and the
interrupt handling are `facet_answers`'s; only the prompt, the user message and the payload
shape are this file's.

    python test/graph/facet_pairs_judge.py --pairs output/facet_pairs/pairs/control.jsonl \\
        --out output/facet_pairs/answers --dry-run
    python test/graph/facet_pairs_judge.py --pairs …/control.jsonl --out …/answers --workers 8
"""
from __future__ import annotations

import argparse
import concurrent.futures as futures
import hashlib
import json
import os
import signal
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "prod", ROOT / "test"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

MODEL = "claude-opus-5"

EFFORT = "high"

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"

# The five angles the prompt asks for, in the order it spells them.
FACETS = ("topic", "temporal", "why", "activity", "concreteness")

# The only three things a facet's value may be, case-sensitive.
CHOICES = ("A", "B", "equal")

MANIFEST_EVERY_S = 1.0

# One Opus call can think for minutes; the lane's own default would cut it.
CALL_TIMEOUT_S = 1800.0

# The first calls of a run are measured, and the figure written once.
FIRST_N = 20

_FA = None


def fa():
    """`facet_answers`, imported on first use — it pulls in the lane and the arms' module
    prints, which is seconds of import; the banner goes out before this is touched."""
    global _FA
    if _FA is None:
        from graph import facet_answers as _module
        _FA = _module
    return _FA


# ------------------------------------------------------------------ the prompt

def prompt_path(override: str = "") -> tuple:
    """The reviewed prompt if it is on disk, else the `.v1` draft beside it."""
    if override:
        path = Path(override)
        if not path.is_file():
            raise SystemExit(f"facet_pairs_judge: --prompt {path} is not a file")
        return path, "named"
    final = PROMPT_DIR / "facet_pairs_judge.txt"
    if final.is_file():
        return final, "reviewed"
    draft = PROMPT_DIR / "facet_pairs_judge.v1.txt"
    if not draft.is_file():
        raise SystemExit(f"facet_pairs_judge: neither {final} nor {draft} is on disk")
    return draft, "v1 draft (the reviewed file is not on disk)"


def prompt_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def user_message(tag_a: str, text_a: str, tag_b: str, text_b: str) -> str:
    """The two relationships, labelled. A shared text is printed twice — the judge is never
    told that the two sides stand on one text."""
    return (f"Relationship A\nPhrase A: {tag_a}\nText A:\n{text_a.rstrip()}\n\n"
            f"Relationship B\nPhrase B: {tag_b}\nText B:\n{text_b.rstrip()}")


# ------------------------------------------------------------------ the payload

def parse_choices(raw) -> dict:
    """The model's object -> the five choices, or ValueError.

    The keys are read exactly as the prompt spells them, lowercase; a value is exactly "A",
    "B" or "equal". Anything else is the payload being wrong, never a thing to mend."""
    if not isinstance(raw, dict):
        raise ValueError(f"payload is {type(raw).__name__}, not an object")
    out = {}
    for facet in FACETS:
        value = raw.get(facet)
        if not isinstance(value, str):
            raise ValueError(f"{facet!r} is {type(value).__name__}, not text: {value!r}")
        if value not in CHOICES:
            raise ValueError(f"{facet!r} is {value!r}, not one of {CHOICES}")
        out[facet] = value
    return out


def canonical(answers: dict, order: str) -> dict:
    """The answers as presented, mapped back onto the pair's sorted edge order.

    Under order AB the presented A is the pair's first edge; under BA it is the second."""
    if order not in ("AB", "BA"):
        raise ValueError(f"order is {order!r}, not AB or BA")
    if order == "AB":
        table = {"A": "first", "B": "second", "equal": "equal"}
    else:
        table = {"A": "second", "B": "first", "equal": "equal"}
    return {facet: table[value] for facet, value in answers.items()}


# ------------------------------------------------------------------ paths

def row_dir(out_root, set_name: str) -> Path:
    return Path(out_root) / set_name


def answer_path(out_root, set_name: str, row_id: str) -> Path:
    return row_dir(out_root, set_name) / f"{row_id}.json"


def failed_path(out_root, set_name: str, row_id: str) -> Path:
    return row_dir(out_root, set_name) / f"{row_id}.failed.json"


def manifest_path(out_root, stem: str, k: int, n: int) -> Path:
    return Path(out_root) / f"manifest.{stem}.{k}of{n}.json"


def lock_path(out_root, stem: str, k: int, n: int) -> Path:
    return Path(out_root) / f".lock.{stem}.{k}of{n}"


def take_lock(out_root, stem: str, k: int, n: int) -> Path:
    path = lock_path(out_root, stem, k, n)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        try:
            held = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            held = {}
        pid = int(held.get("pid") or 0)
        if fa()._pid_alive(pid):
            raise SystemExit(
                f"facet_pairs_judge: {stem} shard {k}/{n} is held by pid {pid} since "
                f"{held.get('start')} ({path}) — refusing to run two of the same shard")
        print(f"  stale lock from pid {pid} — taking it over", flush=True)
    fa().write_json(path, {"pid": os.getpid(), "host": socket.gethostname(),
                           "pairs": stem, "shard": f"{k}/{n}", "start": fa().now_iso()})
    return path


def release_lock(path) -> None:
    try:
        held = json.loads(Path(path).read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return
    if held.get("pid") == os.getpid():
        try:
            Path(path).unlink()
        except OSError:
            pass


def shard_of(row_id: str, n: int) -> int:
    """By sha1 of the row id, so two machines never take the same row."""
    return int(hashlib.sha1(row_id.encode("utf-8")).hexdigest(), 16) % n


def in_shard(row_id: str, k: int, n: int) -> bool:
    return shard_of(row_id, n) == k


def status_of(path, sha: str | None) -> str:
    """missing | unreadable | prompt_mismatch | incomplete | done."""
    path = Path(path)
    if not path.is_file():
        return "missing"
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return "unreadable"
    if not isinstance(rec, dict):
        return "unreadable"
    if sha is not None and rec.get("prompt_sha256") != sha:
        return "prompt_mismatch"
    answers = rec.get("answers")
    if not isinstance(answers, dict):
        return "incomplete"
    for facet in FACETS:
        if answers.get(facet) not in CHOICES:
            return "incomplete"
    canon = rec.get("answers_canonical")
    if not isinstance(canon, dict) or any(f not in canon for f in FACETS):
        return "incomplete"
    return "done"


# ------------------------------------------------------------------ the rows

def read_pairs(path) -> list:
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        for field in ("row_id", "pair_id", "set", "order", "a", "b"):
            if field not in r:
                raise SystemExit(f"facet_pairs_judge: a row of {path} has no {field!r}")
        rows.append(r)
    return rows


def read_texts(path) -> dict:
    """chunk_id -> the chunk's text, from the rows export."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    if not lines:
        raise SystemExit(f"facet_pairs_judge: {path} is empty")
    out = {}
    for line in lines[1:]:
        if not line.strip():
            continue
        r = json.loads(line)
        out[r["chunk_id"]] = r.get("text") or ""
    return out


# ------------------------------------------------------------------ the call

def call_once(system: str, user: str, model: str, effort: str) -> tuple:
    """One call on the lane's own timeout ladder (`harness/chat.py`). `join_parts` reads the
    stream and joins every assistant text block, so a reply that runs past one CLI message
    still arrives whole."""
    payload = {
        "model": model,
        "temperature": 0,
        "effort": effort,
        "join_parts": True,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    from harness import chat
    from harness.contract import generator_usage_from_chat
    t0 = time.perf_counter()
    resp = chat.post("/chat/completions", payload, timeout=CALL_TIMEOUT_S)
    wall = time.perf_counter() - t0
    choices = resp.get("choices") or []
    content = (choices[0].get("message") or {}).get("content") if choices else None
    tin, tout = generator_usage_from_chat(resp.get("usage"))
    return content, tin, tout, wall


def _call_with_ladder(system: str, user: str, model: str, effort: str, state,
                      row_id: str) -> tuple:
    from harness import chat
    stop = fa()._STOP
    backoff = fa().BACKOFF_START_S
    while not stop.is_set():
        chat.reset_timing()
        try:
            content, tin, tout, wall = call_once(system, user, model, effort)
        except Exception as err:
            lane_tries = int(chat.take_timing().get("attempts", 0))
            with state.lock:
                state.lane_tries += lane_tries
            if not fa().retryable(err):
                raise fa()._HardFail(repr(err), lane=True) from err
            with state.lock:
                state.retries += 1
            state.dirty.set()
            nxt = time.strftime("%H:%M:%S", time.localtime(time.time() + backoff))
            print(f"    {row_id[:12]}: call failed ({err}) — next try {nxt} (+{backoff:.0f}s)",
                  flush=True)
            stop.wait(backoff)
            backoff = min(backoff * 2, fa().BACKOFF_CAP_S)
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
    raise fa()._Stopped()


# ------------------------------------------------------------------ the run

def note_first(state, out_root, tin: int, tout: int, wall: float) -> None:
    """The first FIRST_N completed calls of a run, printed once and written once."""
    with state.lock:
        first = getattr(state, "first_calls", None)
        if first is None:
            first = state.first_calls = []
        if getattr(state, "first_written", False) or len(first) >= FIRST_N:
            return
        first.append((wall, tin, tout))
        if len(first) < FIRST_N:
            return
        state.first_written = True
        rows = sorted(first)
    walls = sorted(w for w, _, _ in rows)
    tins = sorted(i for _, i, _ in rows)
    touts = sorted(o for _, _, o in rows)
    mid = len(walls) // 2
    p90 = walls[min(len(walls) - 1, int(0.9 * len(walls)))]
    line = (f"FIRST{FIRST_N} median_wall_s={walls[mid]:.1f} median_in={tins[mid]} "
            f"median_out={touts[mid]} p90_wall_s={p90:.1f}")
    print(line, flush=True)
    target = Path(out_root) / f"first{FIRST_N}.json"
    if not target.is_file():
        fa().write_json(target, {"line": line, "n": len(rows),
                                 "median_wall_s": round(walls[mid], 2),
                                 "median_tokens_in": tins[mid],
                                 "median_tokens_out": touts[mid],
                                 "p90_wall_s": round(p90, 2),
                                 "calls": [{"wall_s": round(w, 2), "tokens_in": i,
                                            "tokens_out": o} for w, i, o in rows],
                                 "timestamp": fa().now_iso()})


def judge_row(row: dict, texts: dict, out_root, system: str, sha: str, model: str,
              effort: str, state) -> None:
    stop = fa()._STOP
    if stop.is_set():
        return
    row_id = row["row_id"]
    set_name = row["set"]
    a, b = row["a"], row["b"]
    text_a = texts.get(a["chunk_id"])
    text_b = texts.get(b["chunk_id"])
    if not text_a or not text_b:
        fa().write_json(failed_path(out_root, set_name, row_id), {
            **row, "error": "a chunk of this pair has no text in the rows export",
            "lane": False, "model": model, "effort": effort, "prompt_sha256": sha,
            "timestamp": fa().now_iso()})
        with state.lock:
            state.failures += 1
        state.dirty.set()
        print(f"    {row_id[:12]}: FAILED (no text) — recorded", flush=True)
        return

    user = user_message(a["tag"], text_a, b["tag"], text_b)
    raws: list = []
    calls = 0
    tin_total = tout_total = 0
    wall_total = 0.0
    answers = None
    try:
        parse_tries = 0
        while True:
            content, tin, tout, wall = _call_with_ladder(system, user, model, effort, state,
                                                         row_id)
            calls += 1
            raws.append(content)
            tin_total += tin
            tout_total += tout
            wall_total += wall
            try:
                if not content:
                    raise ValueError("empty content")
                answers = parse_choices(fa().extract_json(content))
            except ValueError as err:
                parse_tries += 1
                with state.lock:
                    state.parse_failures += 1
                state.dirty.set()
                if parse_tries < fa().PARSE_TRIES:
                    print(f"    {row_id[:12]}: payload did not parse ({err}) — asking once "
                          f"more", flush=True)
                    continue
                raise fa()._HardFail(f"payload did not parse: {err}")
            break
    except fa()._Stopped:
        return
    except fa()._HardFail as err:
        fa().write_json(failed_path(out_root, set_name, row_id), {
            **row, "error": str(err), "lane": err.lane, "raw": raws, "model": model,
            "effort": effort, "prompt_sha256": sha, "timestamp": fa().now_iso()})
        print(f"    {row_id[:12]}: FAILED ({err}) — recorded", flush=True)
        if err.lane:
            state.note_lane_failure()
        else:
            with state.lock:
                state.failures += 1
            state.dirty.set()
        return

    record = dict(row)
    record.update({
        "answers": answers,
        "answers_canonical": canonical(answers, row["order"]),
        "prompt_sha256": sha,
        "model": model,
        "effort": effort,
        "raw": raws,
        "usage": {"tokens_in": tin_total, "tokens_out": tout_total},
        "wall_s": round(wall_total, 2),
        "tries": calls,
        "timestamp": fa().now_iso(),
        "host": socket.gethostname(),
    })
    fa().write_json(answer_path(out_root, set_name, row_id), record)
    with state.lock:
        state.done += 1
        done, total = state.done, state.total
    state.dirty.set()
    note_first(state, out_root, tin_total, tout_total, wall_total)
    print(f"[{done}/{total}] {row_id[:12]} {set_name} {row.get('pair_type')} "
          f"{row['order']} r{row.get('repeat')} "
          f"{' '.join(answers[f] for f in FACETS)} in={tin_total} out={tout_total} "
          f"wall={wall_total:.1f}s calls={calls}", flush=True)


def write_manifest(out_root, stem: str, state, meta: dict, k: int, n: int) -> None:
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
                "failures": state.failures,
                "tokens_in": state.tokens_in,
                "tokens_out": state.tokens_out,
                "wall_s": round(state.wall_s, 1),
            },
            "last_update": fa().now_iso(),
        })
    try:
        fa().write_json(manifest_path(out_root, stem, k, n), payload)
    except OSError as err:
        print(f"    manifest not written this round ({err})", flush=True)


# ------------------------------------------------------------------ merge

def merge(out_root, source, sha: str) -> dict:
    """Fold another machine's answers directory into this one. A file written under a different
    prompt refuses the whole merge — the two halves would not be one layer."""
    src = Path(source)
    if not src.is_dir():
        raise SystemExit(f"facet_pairs_judge --merge: {src} is not a directory")
    copied = duplicates = conflicts = skipped = 0
    for path in sorted(src.rglob("*.json")):
        if path.name.startswith("manifest.") or path.name.endswith(".failed.json"):
            continue
        if path.name.startswith("first"):
            continue
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            skipped += 1
            continue
        if not isinstance(rec, dict) or not rec.get("row_id") or not rec.get("answers"):
            skipped += 1
            continue
        if rec.get("prompt_sha256") != sha:
            raise SystemExit(
                f"facet_pairs_judge --merge: {path.name} was written under prompt "
                f"{str(rec.get('prompt_sha256'))[:12]}, this directory is {sha[:12]} "
                f"— refusing")
        target = answer_path(out_root, rec.get("set", "unknown"), rec["row_id"])
        if target.is_file():
            try:
                here = json.loads(target.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                here = None
            if (isinstance(here, dict) and here.get("prompt_sha256") == sha
                    and here.get("answers") == rec.get("answers")):
                duplicates += 1
            else:
                conflicts += 1
            continue
        fa().write_json(target, rec)
        copied += 1
    return {"copied": copied, "duplicates": duplicates, "conflicts": conflicts,
            "skipped": skipped}


# ------------------------------------------------------------------ cli

def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="one Opus call per presented pair")
    ap.add_argument("--pairs", default="", help="a pairs jsonl from facet_pairs_select.py")
    ap.add_argument("--rows", default=str(ROOT / "output" / "facet_neural" /
                                          "rows_export.jsonl"))
    ap.add_argument("--out", required=True, help="files go to <out>/<set>/<row_id>.json")
    ap.add_argument("--prompt", default="", help="the system prompt file; the default is "
                                                 "prompts/facet_pairs_judge.txt, falling back "
                                                 "to the .v1 draft")
    ap.add_argument("--shard", default="0/1", help="K/N by sha1 of the row id")
    ap.add_argument("--ids-file", default="", help="run exactly these row ids, one per line; "
                                                   "the shard rule is not applied")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=1, help="parallel rows; the laptop lane "
                                                           "holds 8")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--effort", default=EFFORT)
    ap.add_argument("--merge", default="", help="fold another machine's answers dir in")
    ap.add_argument("--retry-failed", action="store_true",
                    help="drop the .failed.json markers of this shard and ask those again")
    ap.add_argument("--allow-prompt-mismatch", action="store_true")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the plan and the call count, call nothing")
    args = ap.parse_args(argv)

    t0 = time.perf_counter()
    print(f"facet_pairs_judge starting | pairs {args.pairs or '(merge)'} | out {args.out}",
          flush=True)
    if args.workers > 8:
        raise SystemExit("facet_pairs_judge: --workers above 8 exhausts this laptop's paging "
                         "file (CLAUDE.md, 2026-09-15); pass 8 or fewer")

    fa()._utf8_console()
    ppath, which = prompt_path(args.prompt)
    system = ppath.read_text(encoding="utf-8")
    sha = prompt_sha(system)
    print(f"  prompt {ppath.name} [{which}] sha {sha[:12]}", flush=True)
    k, n = fa().parse_shard(args.shard)
    out_root = Path(args.out)

    if args.merge:
        print(f"  merge | prompt {sha[:12]}", flush=True)
        print(f"  {merge(out_root, Path(args.merge), sha)}", flush=True)
        return 0

    if not args.pairs:
        raise SystemExit("facet_pairs_judge: --pairs is required")
    rows = read_pairs(args.pairs)
    texts = read_texts(args.rows)
    stem = Path(args.pairs).stem

    wanted = fa().read_ids("", args.ids_file)
    if wanted:
        by_id = {r["row_id"]: r for r in rows}
        mine = [by_id[i] for i in wanted if i in by_id]
        absent = [i for i in wanted if i not in by_id]
        if absent:
            print(f"  row ids not in this pairs file: {len(absent)}", flush=True)
    else:
        mine = [r for r in rows if in_shard(r["row_id"], k, n)]
    if args.limit:
        mine = mine[:args.limit]

    if args.retry_failed:
        dropped = 0
        for r in mine:
            p = failed_path(out_root, r["set"], r["row_id"])
            if p.is_file():
                p.unlink()
                dropped += 1
        print(f"  --retry-failed: dropped {dropped} failure markers", flush=True)

    done_rows, todo, failed_rows, mismatched = [], [], [], []
    for r in mine:
        if failed_path(out_root, r["set"], r["row_id"]).is_file():
            failed_rows.append(r)
            continue
        state_name = status_of(answer_path(out_root, r["set"], r["row_id"]), sha)
        if state_name == "done":
            done_rows.append(r)
        elif state_name == "prompt_mismatch":
            mismatched.append(r)
        else:
            todo.append(r)
    if mismatched and not args.allow_prompt_mismatch:
        raise SystemExit(
            f"facet_pairs_judge: {len(mismatched)} answer files were written under another "
            f"prompt — pass --allow-prompt-mismatch to ask them again under {sha[:12]}")
    todo += mismatched

    sets = sorted({r["set"] for r in rows})
    types = sorted({r.get("pair_type") for r in rows})
    print(f"  pairs file {args.pairs} | rows {len(rows)} | sets {sets} | types {types}",
          flush=True)
    print(f"  model {args.model} | effort {args.effort} | texts {len(texts)} chunks",
          flush=True)
    scope = f"ids {len(mine)}" if wanted else f"shard {k}/{n}: {len(mine)} rows"
    print(f"  {scope} | done {len(done_rows)} | failed {len(failed_rows)} "
          f"| re-ask on prompt {len(mismatched)} | remaining {len(todo)} "
          f"| workers {args.workers}", flush=True)
    print(f"  calls: {len(todo)} remaining rows, one call each before any re-ask", flush=True)
    two = [sum(1 for r in rows if in_shard(r["row_id"], i, 2)) for i in (0, 1)]
    print(f"  two-machine split: 0/2 = {two[0]} rows, 1/2 = {two[1]} rows", flush=True)
    print(f"  out {out_root}", flush=True)
    print(f"  plan in {time.perf_counter() - t0:.1f}s", flush=True)

    if args.dry_run:
        return 0

    for s in sorted({r["set"] for r in mine}):
        d = row_dir(out_root, s)
        if d.is_dir():
            swept = fa().sweep_tmp(d)
            if swept:
                print(f"  swept {swept} stale .tmp files in {s}", flush=True)
    out_root.mkdir(parents=True, exist_ok=True)
    lock = take_lock(out_root, stem, k, n)

    meta = {"pairs": str(args.pairs), "rows_export": str(args.rows), "sets": sets,
            "prompt_path": str(ppath), "prompt_sha256": sha, "model": args.model,
            "effort": args.effort, "shard": f"{k}/{n}", "ids": wanted,
            "workers": args.workers, "out": str(out_root), "start": fa().now_iso()}
    state = fa().State(total=len(mine), done=len(done_rows))
    write_manifest(out_root, stem, state, meta, k, n)

    try:
        previous = signal.signal(signal.SIGINT, fa()._on_interrupt)
    except (ValueError, OSError):
        previous = None
    from harness import abort
    abort.watch()
    print("running — press q to stop after the running rows, Ctrl-C to stop now", flush=True)

    def work(row):
        judge_row(row, texts, out_root, system, sha, args.model, args.effort, state)

    stop = fa()._STOP
    pool = ThreadPoolExecutor(max_workers=max(1, args.workers))
    submitted = [pool.submit(work, row) for row in todo]
    pending = set(submitted)
    last_manifest = 0.0
    try:
        while pending:
            if abort.aborted() and not stop.is_set():
                stop.set()
            if stop.is_set():
                pool.shutdown(wait=False, cancel_futures=True)
                break
            _, pending = futures.wait(pending, timeout=MANIFEST_EVERY_S,
                                      return_when=futures.FIRST_COMPLETED)
            if state.dirty.is_set() and time.time() - last_manifest >= MANIFEST_EVERY_S:
                state.dirty.clear()
                write_manifest(out_root, stem, state, meta, k, n)
                last_manifest = time.time()
    except KeyboardInterrupt:
        stop.set()
        pool.shutdown(wait=False, cancel_futures=True)
        print("\ninterrupted — every finished row is on disk", flush=True)
    finally:
        pool.shutdown(wait=True)
        if previous is not None:
            try:
                signal.signal(signal.SIGINT, previous)
            except (ValueError, OSError):
                pass
        write_manifest(out_root, stem, state, meta, k, n)
        release_lock(lock)

    for f in submitted:
        if f.done() and not f.cancelled() and f.exception() is not None:
            print(f"  worker raised: {f.exception()!r}", flush=True)
    print(f"done {state.done}/{state.total} | calls {state.calls} "
          f"| lane tries {state.lane_tries} | retries {state.retries} "
          f"| parse failures {state.parse_failures} | failures {state.failures} "
          f"| tokens {state.tokens_in}/{state.tokens_out} "
          f"| {time.perf_counter() - t0:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

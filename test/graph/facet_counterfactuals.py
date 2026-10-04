"""One teacher call per chunk: for every phrase on the chunk, four facet-conditioned
counterfactual texts.

The prompt is `prompts/facet_counterfactuals_body.txt` (the specification's facet definitions,
intervention rules, batching rule and example) plus one output tail chosen by `--format`:
`edits` returns spans to replace and the text is reconstructed here against a verbatim-anchor
check; `full` returns the whole rewritten text per counterfactual. The joined prompt's sha256
goes into every chunk file and into the manifest.

One JSON file per chunk under `output/facet_neural/counterfactuals/<db>/` (or `--out`). That
file is the unit of resume: a chunk is re-asked unless its file parses, carries the current
prompt sha, and carries four facets for every phrase it was given. A chunk with a
`.failed.json` beside it is left alone until `--retry-failed`. Nothing is written to the graph.

The plan, the graph read, the shard rule, the lock, the manifest, the retry ladder and the
interrupt handling are `facet_answers`'s; only the prompt, the payload shape and the
reconstruction are this file's.

    NEO4J_DATABASE=herb-eval-volmax python test/graph/facet_counterfactuals.py --dry-run
    python test/graph/facet_counterfactuals.py --ids "a::1,b::2" --format edits --workers 2
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

from harness import abort, chat
from harness.contract import generator_usage_from_chat
from artefact.querytagger import clean_tag, extract_json
from graph import facet_answers as fa
from graph.facet_edits import FACETS, apply_edits  # noqa: F401
from graph.facet_answers import (  # noqa: F401  (the shared plan and run machinery)
    ASK_ROUNDS, PARSE_TRIES, State, _HardFail, _Stopped, in_shard, now_iso, parse_shard,
    read_export, read_ids, retryable, sweep_tmp, write_export, write_json,
)

MODEL = "claude-opus-5"

EFFORT = "high"

FORMATS = ("edits", "full")

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"

BODY_PATH = PROMPT_DIR / "facet_counterfactuals_body.txt"

TAIL_PATH = {f: PROMPT_DIR / f"facet_counterfactuals_tail_{f}.txt" for f in FORMATS}

MANIFEST_EVERY_S = 1.0

OUT_OVERRIDE: Path | None = None

_STOP = fa._STOP


# ------------------------------------------------------------------ the prompt

def prompt_text(fmt: str) -> str:
    if fmt not in FORMATS:
        raise SystemExit(f"facet_counterfactuals: --format wants one of {FORMATS}, got {fmt!r}")
    return (BODY_PATH.read_text(encoding="utf-8").rstrip()
            + "\n" + TAIL_PATH[fmt].read_text(encoding="utf-8"))


def prompt_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def user_message(text: str, tags: list, all_tags: list | None = None) -> str:
    """The chunk and the phrases to answer for.

    When the chunk is asked in groups, `all_tags` is the whole list: the model still sees every
    phrase attached to the chunk, because a facet's contribution to one phrase is defined
    against the rest of the chunk's relationships, and answers only its group."""
    lines = "\n".join(f"- {t}" for t in tags)
    body = f"Text:\n{text.rstrip()}\n\nPhrases:\n{lines}"
    if all_tags and len(all_tags) != len(tags):
        others = "\n".join(f"- {t}" for t in all_tags if t not in set(tags))
        body += (f"\n\nAlso attached to this text, for context only — do NOT answer for these:"
                 f"\n{others}")
    return body


# The largest single reply that parsed over the 279 chunks answered in one call was 42,529
# output tokens (26 phrases, 104 counterfactuals); 28 phrases parsed, 31 and 37 did not. The
# 90th percentile of output per counterfactual over those same chunks is 555 tokens. The group
# size is therefore the measured ceiling divided by the measured rate, in counterfactuals, and
# a chunk is only grouped when it is above it.
MAX_PARSED_OUTPUT_TOKENS = 42529

P90_OUTPUT_TOKENS_PER_COUNTERFACTUAL = 555

GROUP_TAGS = MAX_PARSED_OUTPUT_TOKENS // (P90_OUTPUT_TOKENS_PER_COUNTERFACTUAL * len(FACETS))


def tag_groups(tags: list, size: int = 0) -> list:
    """The phrase list split into as few even groups as stay under the measured ceiling."""
    size = size or GROUP_TAGS
    n = len(tags)
    if n <= size:
        return [list(tags)]
    groups = -(-n // size)                                   # ceil, then even them out
    per = -(-n // groups)
    return [list(tags[i:i + per]) for i in range(0, n, per)]


# ------------------------------------------------------------------ paths

def out_dir(db: str) -> Path:
    if OUT_OVERRIDE is not None:
        return Path(OUT_OVERRIDE)
    return ROOT / "output" / "facet_neural" / "counterfactuals" / db


def chunk_path(db: str, chunk_id: str) -> Path:
    return out_dir(db) / f"{fa.file_stem(chunk_id)}.json"


def failed_path(db: str, chunk_id: str) -> Path:
    return out_dir(db) / f"{fa.file_stem(chunk_id)}.failed.json"


def manifest_path(db: str, k: int, n: int) -> Path:
    return out_dir(db) / f"manifest.{k}of{n}.json"


def lock_path(db: str, k: int, n: int) -> Path:
    return out_dir(db) / f".lock.{k}of{n}"


def take_lock(db: str, k: int, n: int) -> Path:
    path = lock_path(db, k, n)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        try:
            held = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            held = {}
        pid = int(held.get("pid") or 0)
        if fa._pid_alive(pid):
            raise SystemExit(
                f"facet_counterfactuals: shard {k}/{n} is held by pid {pid} since "
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
    for edge in rec["edges"]:
        if not isinstance(edge, dict):
            return "incomplete"
        for facet in FACETS:
            cf = edge.get(facet)
            if not isinstance(cf, dict) or not isinstance(cf.get("text"), str):
                return "incomplete"
    return "done"


# ------------------------------------------------------------------ reconstruction

def _facet_payload(raw, text: str, fmt: str) -> tuple:
    """One facet object from the model -> (record, problems)."""
    if not isinstance(raw, dict):
        return None, [f"facet payload is {type(raw).__name__}, not an object"]
    note = raw.get("note")
    note = note.strip() if isinstance(note, str) else ""
    if fmt == "edits":
        edits = raw.get("edits")
        if not isinstance(edits, list):
            return None, [f"`edits` is {type(edits).__name__}, not a list"]
        new_text, problems = apply_edits(text, edits)
        rec = {"note": note, "edits": edits, "text": new_text,
               "applied": len(edits) - len(problems), "asked": len(edits),
               "changed": new_text != text, "problems": problems,
               "reconstruction_ok": not problems}
        return rec, problems
    new_text = raw.get("chunk")
    if not isinstance(new_text, str) or not new_text.strip():
        return None, ["`chunk` is not a non-empty string"]
    rec = {"note": note, "edits": None, "text": new_text,
           "applied": None, "asked": None,
           "changed": new_text != text, "problems": [], "reconstruction_ok": True}
    return rec, []


def parse_counterfactuals(raw: dict, tags: list, text: str, fmt: str) -> tuple:
    """The model's object -> (rows, problems).

    A row survives only with all four facets present and usable. A phrase that is not one of
    the tags given is kept and marked, never mended: what the model answered is what the file
    records. Phrases a row leaves out are asked again."""
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
        facets, bad = {}, None
        for facet in FACETS:
            rec, probs = _facet_payload(row.get(facet), text, fmt)
            if rec is None:
                bad = f"{facet!r} of phrase {t!r}: {probs[0]}"
                break
            facets[facet] = rec
            problems.extend(f"{t!r} {facet}: {p}" for p in probs)
        if bad:
            problems.append(bad)
            continue
        seen.add(key)
        out.append({"t": given.get(key, t), "matched": key in given, **facets})
    if not out:
        raise ValueError("no edge row survived: " + ("; ".join(problems) or "empty payload"))
    return out, problems


# ------------------------------------------------------------------ the call

def call_once(system: str, user: str, model: str, effort: str) -> tuple:
    payload = {
        "model": model,
        "temperature": 0,
        "effort": effort,
        # A long answer runs past one CLI message; the `json` envelope then returns only the
        # tail and the payload arrives beginning mid-object. `join_parts` reads the stream and
        # joins every assistant text block.
        "join_parts": True,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    t0 = time.perf_counter()
    resp = chat.post("/chat/completions", payload, timeout=1800.0)
    wall = time.perf_counter() - t0
    choices = resp.get("choices") or []
    content = (choices[0].get("message") or {}).get("content") if choices else None
    tin, tout = generator_usage_from_chat(resp.get("usage"))
    return content, tin, tout, wall


def _call_with_ladder(system: str, user: str, model: str, effort: str, state: State,
                      chunk_id: str) -> tuple:
    backoff = fa.BACKOFF_START_S
    while not _STOP.is_set():
        chat.reset_timing()
        try:
            content, tin, tout, wall = call_once(system, user, model, effort)
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
            print(f"    {chunk_id}: call failed ({err}) — next try {nxt} (+{backoff:.0f}s)",
                  flush=True)
            _STOP.wait(backoff)
            backoff = min(backoff * 2, fa.BACKOFF_CAP_S)
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


# ------------------------------------------------------------------ the run

def counterfactual_chunk(row: dict, db: str, system: str, sha: str, model: str, effort: str,
                         fmt: str, state: State) -> None:
    if _STOP.is_set():
        return
    chunk_id = row["chunk_id"]
    text = row["text"]
    given = list(row["tags"])
    given_keys = {clean_tag(t).casefold(): t for t in given}
    kept: dict = {}
    raws: list = []
    problems: list = []
    calls = 0
    tin_total = tout_total = 0
    wall_total = 0.0
    ask = list(given)

    groupings: list = []
    try:
        for round_no in range(1, ASK_ROUNDS + 1):
            groups = tag_groups(ask)
            groupings.append({"round": round_no, "asked": len(ask),
                              "groups": [len(g) for g in groups]})
            if len(groups) > 1:
                print(f"    {chunk_id}: {len(ask)} phrases asked in {len(groups)} groups of "
                      f"{[len(g) for g in groups]} (the measured single-reply ceiling is "
                      f"{GROUP_TAGS} phrases)", flush=True)
            for group in groups:
                parse_tries = 0
                while True:
                    user = user_message(text, group, given)
                    content, tin, tout, wall = _call_with_ladder(system, user, model, effort,
                                                                 state, chunk_id)
                    calls += 1
                    raws.append(content)
                    tin_total += tin
                    tout_total += tout
                    wall_total += wall
                    try:
                        if not content:
                            raise ValueError("empty content")
                        new_rows, bad = parse_counterfactuals(extract_json(content), group,
                                                              text, fmt)
                    except ValueError as err:
                        parse_tries += 1
                        with state.lock:
                            state.parse_failures += 1
                        state.dirty.set()
                        if parse_tries < PARSE_TRIES:
                            print(f"    {chunk_id}: payload did not parse ({err}) — asking "
                                  f"once more", flush=True)
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
            "tags": given, "format": fmt, "error": str(err), "lane": err.lane,
            "missing": [t for key, t in given_keys.items() if key not in kept],
            "raw": raws, "model": model, "effort": effort, "prompt_sha256": sha,
            "timestamp": now_iso(),
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
    bad_recon = sum(1 for e in edges for f in FACETS if not e[f]["reconstruction_ok"])
    unchanged = sum(1 for e in edges for f in FACETS if not e[f]["changed"])

    write_json(chunk_path(db, chunk_id), {
        "chunk_id": chunk_id,
        "kind": row["kind"],
        "product": row["product"],
        "tags": given,
        "tag_order": row.get("tag_order", fa.TAG_ORDER),
        "given": len(given),
        "answered": answered,
        "complete": complete,
        "format": fmt,
        "text": text,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "edges": edges,
        "problems": problems,
        "counterfactuals": len(edges) * len(FACETS),
        "reconstruction_failures": bad_recon,
        "unchanged": unchanged,
        "raw": raws,
        "usage": {"tokens_in": tin_total, "tokens_out": tout_total},
        "wall_s": round(wall_total, 2),
        "tries": calls,
        "model": model,
        "effort": effort,
        "prompt_sha256": sha,
        "grouping": groupings,
        "group_tags": GROUP_TAGS,
        "timestamp": now_iso(),
    })
    if complete:
        with state.lock:
            state.done += 1
            done, total = state.done, state.total
    else:
        write_json(failed_path(db, chunk_id), {
            "chunk_id": chunk_id, "kind": row["kind"], "product": row["product"],
            "tags": given, "format": fmt,
            "error": f"{len(missing)} of {len(given)} phrases unanswered after {ASK_ROUNDS} "
                     f"asks",
            "lane": False, "missing": missing, "problems": problems,
            "model": model, "effort": effort, "prompt_sha256": sha, "timestamp": now_iso(),
        })
        with state.lock:
            state.incomplete += 1
            state.failures += 1
            done, total = state.done, state.total
    state.dirty.set()
    print(f"[{done}/{total}] {chunk_id} kind={row['kind']} tags={len(given)} "
          f"answered={answered} cf={len(edges) * len(FACETS)} unchanged={unchanged} "
          f"recon_fail={bad_recon} in={tin_total} out={tout_total} "
          f"wall={wall_total:.1f}s calls={calls}", flush=True)


def write_manifest(db: str, state: State, meta: dict, k: int, n: int) -> None:
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


# ------------------------------------------------------------------ cli

def main(argv: list | None = None) -> int:
    global OUT_OVERRIDE
    fa._utf8_console()
    ap = argparse.ArgumentParser(
        description="four facet counterfactuals per phrase, one teacher call a chunk")
    ap.add_argument("--db", default=os.environ.get("NEO4J_DATABASE", "herb-eval-volmax"))
    ap.add_argument("--input", default="", help="run from an export file, no graph read")
    ap.add_argument("--export", default="", help="write the export file and stop")
    ap.add_argument("--out", default="", help="write the chunk files here")
    ap.add_argument("--format", default="edits", choices=list(FORMATS))
    ap.add_argument("--shard", default="0/1", help="K/N by sha1 of the chunk id")
    ap.add_argument("--ids", default="", help="run exactly these chunk ids, comma separated")
    ap.add_argument("--ids-file", default="", help="the same, one chunk id per line")
    ap.add_argument("--workers", type=int, default=1, help="parallel chunks; the laptop lane "
                                                           "holds 8")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--effort", default=EFFORT, choices=["low", "medium", "high", "xhigh",
                                                         "max"])
    ap.add_argument("--retry-failed", action="store_true")
    ap.add_argument("--allow-prompt-mismatch", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if args.workers > 8:
        raise SystemExit("facet_counterfactuals: --workers above 8 exhausts this laptop's "
                         "paging file (CLAUDE.md, 2026-09-15); pass 8 or fewer")

    t0 = time.perf_counter()
    print(f"facet_counterfactuals starting | db {args.db} | format {args.format} | "
          f"{'input ' + args.input if args.input else 'reading the graph'}", flush=True)
    system = prompt_text(args.format)
    sha = prompt_sha(system)
    k, n = parse_shard(args.shard)
    db = args.db
    OUT_OVERRIDE = Path(args.out) if args.out else None

    if args.input:
        header, rows = read_export(Path(args.input))
        db = header.get("db", db)
        source = f"file {args.input}"
        corpus = header.get("corpus_sha256")
    else:
        source = f"graph {db}"
        corpus = fa.corpus_sha()
        rows = fa.rows_from_graph(db, None)

    no_text = [r for r in rows if not r.get("text")]
    no_tags = [r for r in rows if not r.get("tags")]
    rows = [r for r in rows if r.get("text") and r.get("tags")]

    if args.export:
        write_export(Path(args.export), rows, {
            "db": db, "prompt_sha256": sha, "corpus_sha256": corpus, "model": args.model,
            "n_chunks": len(rows), "tag_order": fa.TAG_ORDER, "written": now_iso(),
        })
        print(f"facet_counterfactuals export | {source} | {len(rows)} chunks -> "
              f"{args.export}", flush=True)
        return 0

    wanted = read_ids(args.ids, args.ids_file)
    if wanted:
        by_id = {r["chunk_id"]: r for r in rows}
        mine = [by_id[i] for i in wanted if i in by_id]
        absent = [i for i in wanted if i not in by_id]
        if absent:
            print(f"  ids not in this source: {', '.join(absent[:10])}", flush=True)
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
        raise SystemExit(
            f"facet_counterfactuals: {len(mismatched)} chunk files were written under another "
            f"prompt — pass --allow-prompt-mismatch to ask them again under {sha[:12]}")
    todo += mismatched

    tags_mine = sum(len(r["tags"]) for r in todo)
    print(f"facet_counterfactuals | {source} | prompt {sha[:12]} | corpus {str(corpus)[:12]} "
          f"| model {args.model} effort {args.effort} | format {args.format}", flush=True)
    print(f"  chunks {len(rows)} | no text {len(no_text)} | no tags {len(no_tags)}",
          flush=True)
    scope = f"ids {len(mine)}" if wanted else f"shard {k}/{n}: {len(mine)} chunks"
    print(f"  {scope} | done {len(done_rows)} | failed {len(failed_rows)} "
          f"| re-ask on prompt {len(mismatched)} | remaining {len(todo)} (tags {tags_mine}, "
          f"counterfactuals {tags_mine * len(FACETS)}) | workers {args.workers}", flush=True)
    print(f"  out {out_dir(db)}", flush=True)
    print(f"  plan in {time.perf_counter() - t0:.1f}s", flush=True)

    if args.dry_run:
        return 0

    swept = sweep_tmp(out_dir(db)) if out_dir(db).is_dir() else 0
    if swept:
        print(f"  swept {swept} stale .tmp files", flush=True)
    lock_file = take_lock(db, k, n)

    meta = {"db": db, "source": source, "body_path": str(BODY_PATH),
            "tail_path": str(TAIL_PATH[args.format]), "prompt_sha256": sha,
            "corpus_sha256": corpus, "model": args.model, "effort": args.effort,
            "format": args.format, "facets": list(FACETS), "shard": f"{k}/{n}",
            "ids": wanted, "tag_order": fa.TAG_ORDER, "workers": args.workers,
            "start": now_iso()}
    state = State(total=len(mine), done=len(done_rows))
    write_manifest(db, state, meta, k, n)

    try:
        previous = signal.signal(signal.SIGINT, fa._on_interrupt)
    except (ValueError, OSError):
        previous = None
    abort.watch()
    print("running — press q to stop after the running chunks, Ctrl-C to stop now", flush=True)

    def work(row):
        counterfactual_chunk(row, db, system, sha, args.model, args.effort, args.format, state)

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
        release_lock(lock_file)

    for f in submitted:
        if f.done() and not f.cancelled() and f.exception() is not None:
            print(f"  worker raised: {f.exception()!r}", flush=True)
    print(f"done {state.done}/{state.total} | calls {state.calls} "
          f"| lane tries {state.lane_tries} | retries {state.retries} "
          f"| parse failures {state.parse_failures} | incomplete {state.incomplete} "
          f"| failures {state.failures} | tokens {state.tokens_in}/{state.tokens_out} "
          f"| {time.perf_counter() - t0:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

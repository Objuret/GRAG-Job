"""One model call per text: the chunk described through each facet — a "view".

Two variants, one call each, both over the texts `facet_views_texts.py` collected:
`chunk` asks for the chunk's own description plus four views of the whole chunk; `edge` asks,
for every phrase attached to the chunk, four views of the chunk as it concerns that phrase.
The system text is a prompt file read at runtime and never reformulated here; its sha256 goes
into every text file and into the manifest. Each text is written twice (`--write 1`, `--write
2`) as two independent calls.

One JSON file per text under `<out>/<variant>/w<write>/`, named by the sha256 of the exact
text. That file is the unit of resume: a text is re-asked unless its file parses, carries the
current prompt sha, and carries a view for everything it was given. A text with a
`.failed.json` beside it is left alone until `--retry-failed`. Nothing is written to the graph.

The plan, the shard rule, the lock, the manifest, the retry ladder, the parse re-ask and the
interrupt handling are `facet_answers`'s; only the prompts, the payload shapes and the string
collection are this file's. The views themselves are embedded later, off this machine, by
`facet_embed_gpu.py`, which takes what `--collect-strings` writes.

    python test/graph/facet_views.py --texts output/facet_views/pilot/texts.jsonl \\
        --variant chunk --write 1 --out output/facet_views/pilot/views --workers 8
    python test/graph/facet_views.py --texts …/texts.jsonl --variant edge --write 1 --dry-run
    python test/graph/facet_views.py --out …/views --collect-strings …/strings.jsonl \\
        --texts …/texts.jsonl
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

MODEL = "claude-haiku-4-5"

VARIANTS = ("chunk", "edge")

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"

# The five keys the `chunk` prompt returns; the four facets are `facet_edits`'s list, with the
# chunk's own description in front of them.
CHUNK_FIELDS = ("description", "temporal", "why", "activity", "concreteness")

# The four keys the `edge` prompt returns per phrase — `facet_answers.parse_answers` reads
# exactly this shape and is reused for it.
EDGE_FIELDS = ("temporal", "why", "activity", "concreteness")

# The one line both prompts give for an angle the chunk says nothing from. It is an ordinary
# view string everywhere — parsed, written and embedded like any other — and counted so the
# run says how much of the layer is that line.
NOTHING_LINE = "The text gives nothing here."

MANIFEST_EVERY_S = 1.0

# Measured on this lane: 47.7M input tokens over 1,646 Haiku calls in the relaunched answer
# pass, 2026-09-15 (CLAUDE.md) — the headless CLI's own preamble plus cache tokens, which
# dwarf the prompt, so the figure does not depend on the variant.
TOKENS_IN_PER_CALL = 29_000

# Output is the reply's own length, and these two are the build order's estimates, stated not
# measured: five short descriptions for `chunk`, four short ones per phrase for `edge`. The
# smoke replaces them.
TOKENS_OUT_CHUNK = 400
TOKENS_OUT_PER_PHRASE = 60

# The build order's allowance for the re-asks (a payload that did not parse, phrases left
# unanswered), stated not measured.
REASK_FACTOR = 1.1

_FA = None


def fa():
    """`facet_answers`, imported on first use. It pulls in the lane, the driver and the arms'
    module prints, which is seconds of import — the banner goes out before this is touched."""
    global _FA
    if _FA is None:
        from graph import facet_answers as _module
        _FA = _module
    return _FA


# ------------------------------------------------------------------ the prompt

def prompt_path(variant: str, override: str = "") -> Path:
    """The reviewed prompt if it is on disk, else the `.v1` draft beside it."""
    if variant not in VARIANTS:
        raise SystemExit(f"facet_views: --variant wants one of {VARIANTS}, got {variant!r}")
    if override:
        path = Path(override)
        if not path.is_file():
            raise SystemExit(f"facet_views: --prompt {path} is not a file")
        return path
    final = PROMPT_DIR / f"facet_views_{variant}.txt"
    if final.is_file():
        return final
    draft = PROMPT_DIR / f"facet_views_{variant}.v1.txt"
    if not draft.is_file():
        raise SystemExit(f"facet_views: neither {final} nor {draft} is on disk")
    return draft


def prompt_text(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def prompt_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def user_message(text: str, tags: list | None = None) -> str:
    """`chunk` gets the text alone; `edge` gets the text and its phrase list, in the tagger's
    own pass-2 shape (`facet_answers.user_message`), so a flattened field dump still reads as a
    chunk with a phrase list under it."""
    body = f"Text:\n{text.rstrip()}"
    if tags is None:
        return body
    lines = "\n".join(f"- {t}" for t in tags)
    return f"{body}\n\nPhrases:\n{lines}"


# ------------------------------------------------------------------ the call

def call_once(system: str, user: str, model: str) -> tuple:
    """One call on the lane's own timeout ladder (`harness/chat.py`). `join_parts` is the only
    thing added: a long reply runs past one CLI message and the `json` envelope then carries
    only the tail, so the payload would arrive beginning mid-object."""
    payload = {
        "model": model,
        "temperature": 0,
        "join_parts": True,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    from harness import chat
    from harness.contract import generator_usage_from_chat
    t0 = time.perf_counter()
    resp = chat.post("/chat/completions", payload)
    wall = time.perf_counter() - t0
    choices = resp.get("choices") or []
    content = (choices[0].get("message") or {}).get("content") if choices else None
    tin, tout = generator_usage_from_chat(resp.get("usage"))
    return content, tin, tout, wall


def _call_with_ladder(system: str, user: str, model: str, state, text_sha: str) -> tuple:
    """`facet_answers`'s ladder around this file's `call_once`: the lane's own six tries first,
    then a doubling outer wait from its last rung, bounded, until the run is stopped."""
    from harness import chat
    stop = fa()._STOP
    backoff = fa().BACKOFF_START_S
    while not stop.is_set():
        chat.reset_timing()
        try:
            content, tin, tout, wall = call_once(system, user, model)
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
            print(f"    {text_sha}: call failed ({err}) — next try {nxt} (+{backoff:.0f}s)",
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


# ------------------------------------------------------------------ paths

def run_dir(out_root, variant: str, write: int) -> Path:
    return Path(out_root) / variant / f"w{write}"


def view_path(out_root, variant: str, write: int, sha: str) -> Path:
    return run_dir(out_root, variant, write) / f"{sha}.json"


def failed_path(out_root, variant: str, write: int, sha: str) -> Path:
    return run_dir(out_root, variant, write) / f"{sha}.failed.json"


def manifest_path(out_root, variant: str, write: int, k: int, n: int) -> Path:
    return run_dir(out_root, variant, write) / f"manifest.{k}of{n}.json"


def lock_path(out_root, variant: str, write: int, k: int, n: int) -> Path:
    return run_dir(out_root, variant, write) / f".lock.{k}of{n}"


def take_lock(out_root, variant: str, write: int, k: int, n: int) -> Path:
    path = lock_path(out_root, variant, write, k, n)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        try:
            held = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            held = {}
        pid = int(held.get("pid") or 0)
        if fa()._pid_alive(pid):
            raise SystemExit(
                f"facet_views: {variant}/w{write} shard {k}/{n} is held by pid {pid} since "
                f"{held.get('start')} ({path}) — refusing to run two of the same shard")
        print(f"  stale lock from pid {pid} — taking it over", flush=True)
    fa().write_json(path, {"pid": os.getpid(), "host": socket.gethostname(),
                           "variant": variant, "write": write, "shard": f"{k}/{n}",
                           "start": fa().now_iso()})
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


def shard_of(text_sha: str, n: int) -> int:
    """By sha1 of the text's sha256, so two machines never take the same text."""
    return int(hashlib.sha1(text_sha.encode("utf-8")).hexdigest(), 16) % n


def in_shard(text_sha: str, k: int, n: int) -> bool:
    return shard_of(text_sha, n) == k


def status_of(path: Path, sha: str | None, variant: str) -> str:
    """missing | unreadable | prompt_mismatch | incomplete | done."""
    if not Path(path).is_file():
        return "missing"
    try:
        rec = json.loads(Path(path).read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return "unreadable"
    if not isinstance(rec, dict):
        return "unreadable"
    views = rec.get("views")
    if variant == "chunk":
        if not isinstance(views, dict):
            return "unreadable"
    elif not isinstance(views, list):
        return "unreadable"
    if sha is not None and rec.get("prompt_sha256") != sha:
        return "prompt_mismatch"
    if variant == "chunk":
        for field in CHUNK_FIELDS:
            v = views.get(field)
            if not isinstance(v, str) or not v.strip():
                return "incomplete"
        return "done"
    given, answered = rec.get("given"), rec.get("answered")
    if not isinstance(given, int) or not isinstance(answered, int):
        return "incomplete"
    if answered != given or not rec.get("complete") or not views:
        return "incomplete"
    for row in views:
        if not isinstance(row, dict) or not str(row.get("t", "")).strip():
            return "incomplete"
        for field in EDGE_FIELDS:
            v = row.get(field)
            if not isinstance(v, str) or not v.strip():
                return "incomplete"
    return "done"


# ------------------------------------------------------------------ the payload

def parse_chunk_views(raw) -> dict:
    """The model's object -> the five strings, or ValueError.

    The five keys are read exactly as the prompt spells them, lowercase; a key in another case
    is a key the prompt did not ask for. A missing or empty field is the payload being wrong,
    not a value to mend. The prompt's absence line is an ordinary string here."""
    if not isinstance(raw, dict):
        raise ValueError(f"payload is {type(raw).__name__}, not an object")
    out = {}
    for field in CHUNK_FIELDS:
        value = raw.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field!r} is not text: {value!r}")
        out[field] = value.strip()
    return out


def parse_edge_views(raw, tags: list) -> tuple:
    """`facet_answers.parse_answers`: rows carrying the phrase and the four views as non-empty
    text, an unasked phrase kept and marked, the phrases a row left out asked again."""
    return fa().parse_answers(raw, tags)


def nothing_lines(strings: list) -> int:
    """How many of a text's view fields are the prompt's absence line."""
    return sum(1 for s in strings if s.strip() == NOTHING_LINE)


def views_strings(rec: dict) -> list:
    """Every string a finished view file holds, in file order — the chunk's description and its
    four views, or the four views of every phrase."""
    views = rec.get("views")
    if rec.get("variant") == "chunk":
        return [views[f] for f in CHUNK_FIELDS]
    return [row[f] for row in views for f in EDGE_FIELDS]


# ------------------------------------------------------------------ the run

def write_views(row: dict, out_root, variant: str, write: int, system: str, sha: str,
                model: str, state) -> None:
    stop = fa()._STOP
    if stop.is_set():
        return
    text_sha = row["sha"]
    tags = list(row.get("tags") or [])
    given_keys = {fa().clean_tag(t).casefold(): t for t in tags} if variant == "edge" else {}
    kept: dict = {}
    chunk_views: dict = {}
    raws: list = []
    problems: list = []
    calls = 0
    tin_total = tout_total = 0
    wall_total = 0.0
    ask = list(tags)
    rounds = fa().ASK_ROUNDS if variant == "edge" else 1

    try:
        for round_no in range(1, rounds + 1):
            parse_tries = 0
            while True:
                user = user_message(row["text"], ask if variant == "edge" else None)
                content, tin, tout, wall = _call_with_ladder(system, user, model, state,
                                                             text_sha[:12])
                calls += 1
                raws.append(content)
                tin_total += tin
                tout_total += tout
                wall_total += wall
                try:
                    if not content:
                        raise ValueError("empty content")
                    payload = fa().extract_json(content)
                    if variant == "chunk":
                        chunk_views = parse_chunk_views(payload)
                        new_rows, bad = [], []
                    else:
                        new_rows, bad = parse_edge_views(payload, ask)
                except ValueError as err:
                    parse_tries += 1
                    with state.lock:
                        state.parse_failures += 1
                    state.dirty.set()
                    if parse_tries < fa().PARSE_TRIES:
                        print(f"    {text_sha[:12]}: payload did not parse ({err}) — asking "
                              f"once more", flush=True)
                        continue
                    raise fa()._HardFail(f"payload did not parse: {err}")
                problems.extend(bad)
                break
            if variant == "chunk":
                break
            for r in new_rows:
                kept.setdefault(fa().clean_tag(r["t"]).casefold(), r)
            missing = [t for key, t in given_keys.items() if key not in kept]
            if not missing or round_no == rounds:
                break
            print(f"    {text_sha[:12]}: {len(missing)} of {len(tags)} phrases unanswered — "
                  f"asking for those alone", flush=True)
            ask = missing
    except fa()._Stopped:
        return
    except fa()._HardFail as err:
        fa().write_json(failed_path(out_root, variant, write, text_sha), {
            "sha": text_sha, "chunk_id": row["chunk_id"], "kind": row.get("kind"),
            "product": row.get("product"), "variant": variant, "write": write,
            "origins": row.get("origins"), "tags": tags, "error": str(err), "lane": err.lane,
            "missing": [t for key, t in given_keys.items() if key not in kept],
            "raw": raws, "model": model, "prompt_sha256": sha, "timestamp": fa().now_iso(),
        })
        print(f"    {text_sha[:12]}: FAILED ({err}) — recorded", flush=True)
        if err.lane:
            state.note_lane_failure()
        else:
            with state.lock:
                state.failures += 1
            state.dirty.set()
        return

    record = {
        "sha": text_sha,
        "chunk_id": row["chunk_id"],
        "kind": row.get("kind"),
        "product": row.get("product"),
        "variant": variant,
        "write": write,
        "origins": row.get("origins"),
        "prompt_sha256": sha,
        "model": model,
        "problems": problems,
        "raw": raws,
        "usage": {"tokens_in": tin_total, "tokens_out": tout_total},
        "wall_s": round(wall_total, 2),
        "tries": calls,
        "timestamp": fa().now_iso(),
    }
    if variant == "chunk":
        record["views"] = chunk_views
        nothing = nothing_lines([chunk_views[f] for f in CHUNK_FIELDS])
        complete = True
        answered = len(CHUNK_FIELDS)
        given = len(CHUNK_FIELDS)
        missing = []
    else:
        edges = [kept[key] for key in given_keys if key in kept]
        edges += [r for key, r in kept.items() if key not in given_keys]
        answered = sum(1 for key in given_keys if key in kept)
        given = len(tags)
        missing = [t for key, t in given_keys.items() if key not in kept]
        complete = not missing
        record["tags"] = tags
        record["given"] = given
        record["answered"] = answered
        record["complete"] = complete
        record["views"] = edges
        nothing = nothing_lines([r[f] for r in edges for f in EDGE_FIELDS])

    record["nothing_lines"] = nothing
    with state.lock:
        state.nothing_lines = getattr(state, "nothing_lines", 0) + nothing

    fa().write_json(view_path(out_root, variant, write, text_sha), record)
    if complete:
        with state.lock:
            state.done += 1
            done, total = state.done, state.total
    else:
        fa().write_json(failed_path(out_root, variant, write, text_sha), {
            "sha": text_sha, "chunk_id": row["chunk_id"], "kind": row.get("kind"),
            "product": row.get("product"), "variant": variant, "write": write,
            "origins": row.get("origins"), "tags": tags,
            "error": f"{len(missing)} of {given} phrases unanswered after {rounds} asks",
            "lane": False, "missing": missing, "problems": problems,
            "model": model, "prompt_sha256": sha, "timestamp": fa().now_iso(),
        })
        with state.lock:
            state.incomplete += 1
            state.failures += 1
            done, total = state.done, state.total
    state.dirty.set()
    print(f"[{done}/{total}] {text_sha[:12]} {row['chunk_id']} kind={row.get('kind')} "
          f"{variant}/w{write} given={given} answered={answered} complete={complete} "
          f"nothing={nothing} in={tin_total} out={tout_total} wall={wall_total:.1f}s "
          f"calls={calls}", flush=True)


def write_manifest(out_root, variant: str, write: int, state, meta: dict, k: int,
                   n: int) -> None:
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
                "nothing_lines": getattr(state, "nothing_lines", 0),
                "wall_s": round(state.wall_s, 1),
            },
            "last_update": fa().now_iso(),
        })
    try:
        fa().write_json(manifest_path(out_root, variant, write, k, n), payload)
    except OSError as err:
        print(f"    manifest not written this round ({err})", flush=True)


# ------------------------------------------------------------------ merge

def merge(out_root, variant: str, write: int, source, sha: str) -> dict:
    """Fold another machine's `<variant>/w<N>` directory into this one. A file written under a
    different prompt refuses the whole merge — the two halves would not be one layer. A text
    already here is a duplicate when the two files say the same thing and a conflict when they
    do not."""
    src = Path(source)
    if not src.is_dir():
        raise SystemExit(f"facet_views --merge: {src} is not a directory")
    dest = run_dir(out_root, variant, write)
    dest.mkdir(parents=True, exist_ok=True)
    fa().sweep_tmp(dest)
    copied = duplicates = conflicts = skipped = 0
    for path in sorted(src.glob("*.json")):
        if path.name.startswith("manifest.") or path.name.endswith(".failed.json"):
            continue
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            skipped += 1
            continue
        if not isinstance(rec, dict) or not rec.get("sha") or rec.get("views") is None:
            skipped += 1
            continue
        if rec.get("prompt_sha256") != sha:
            raise SystemExit(
                f"facet_views --merge: {path.name} was written under prompt "
                f"{str(rec.get('prompt_sha256'))[:12]}, this directory is {sha[:12]} — refusing")
        if rec.get("variant") != variant or rec.get("write") != write:
            skipped += 1
            continue
        target = view_path(out_root, variant, write, rec["sha"])
        if target.is_file():
            try:
                here = json.loads(target.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                here = None
            if (isinstance(here, dict) and here.get("prompt_sha256") == rec.get("prompt_sha256")
                    and here.get("views") == rec.get("views")):
                duplicates += 1
            else:
                conflicts += 1
            continue
        fa().write_json(target, rec)
        copied += 1
    return {"copied": copied, "duplicates": duplicates, "conflicts": conflicts,
            "skipped": skipped}


# ------------------------------------------------------------------ the strings

def collect_strings(out_root, texts_rows: list, target) -> dict:
    """Every view string on disk under `<out>` plus every tag phrase in the texts file, as the
    `{"sha", "text"}` jsonl `facet_embed_gpu.py` takes. The sha is the sha256 of the exact
    string, which that script re-computes and refuses on mismatch."""
    seen: dict = {}
    order: list = []
    per_run: list = []

    def add(text: str) -> None:
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if sha not in seen:
            seen[sha] = text
            order.append(sha)

    for run in sorted(Path(out_root).glob("*/w*")):
        if not run.is_dir():
            continue
        variant = run.parent.name
        if variant not in VARIANTS:
            continue
        files = strings = nothing = 0
        for path in sorted(run.glob("*.json")):
            if path.name.startswith("manifest.") or path.name.endswith(".failed.json"):
                continue
            if status_of(path, None, variant) != "done":
                continue
            rec = json.loads(path.read_text(encoding="utf-8"))
            texts = views_strings(rec)
            files += 1
            strings += len(texts)
            nothing += nothing_lines(texts)
            for t in texts:
                add(t)
        per_run.append({"variant": variant, "write": run.name, "files": files,
                        "strings": strings, "nothing_lines": nothing})

    phrases = 0
    for row in texts_rows:
        for tag in row.get("tags") or []:
            phrases += 1
            add(tag)

    out = Path(target)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for sha in order:
            f.write(json.dumps({"sha": sha, "text": seen[sha]}, ensure_ascii=False) + "\n")
    return {"runs": per_run, "phrases": phrases, "strings": len(order), "out": str(out)}


# ------------------------------------------------------------------ cli

def cost_lines(remaining_rows: list, variant: str) -> list:
    """The build order's estimate, printed as one. `TOKENS_IN_PER_CALL` is measured on this
    lane; the output figures and the re-ask factor are stated, and the smoke replaces them."""
    calls = remaining_rows if isinstance(remaining_rows, int) else len(remaining_rows)
    phrases = 0 if isinstance(remaining_rows, int) else sum(
        len(r.get("tags") or []) for r in remaining_rows)
    with_reask = calls * REASK_FACTOR
    tin = with_reask * TOKENS_IN_PER_CALL
    if variant == "chunk":
        tout = with_reask * TOKENS_OUT_CHUNK
        out_basis = f"{TOKENS_OUT_CHUNK} a call"
    else:
        tout = phrases * REASK_FACTOR * TOKENS_OUT_PER_PHRASE
        out_basis = f"{TOKENS_OUT_PER_PHRASE} x {phrases} phrases"
    return [
        f"  cost estimate: calls {with_reask:,.0f} ({calls} remaining x {REASK_FACTOR} for "
        f"re-asks)",
        f"    tokens in  {tin:,.0f} (calls x {TOKENS_IN_PER_CALL:,}, measured on this lane "
        f"2026-09-15: 47.7M over 1,646 Haiku calls)",
        f"    tokens out {tout:,.0f} ({out_basis}, estimated not measured)",
    ]


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="facet views per text, one call a text")
    ap.add_argument("--texts", default="", help="the texts jsonl from facet_views_texts.py")
    ap.add_argument("--variant", default="chunk", choices=list(VARIANTS))
    ap.add_argument("--write", type=int, default=1, help="which of the two writes this is")
    ap.add_argument("--out", required=True, help="the root; files go to <out>/<variant>/w<N>/")
    ap.add_argument("--prompt", default="", help="the system prompt file; the default is "
                                                 "prompts/facet_views_<variant>.txt, falling "
                                                 "back to the .v1 draft")
    ap.add_argument("--shard", default="0/1", help="K/N by sha1 of the text sha")
    ap.add_argument("--ids-file", default="", help="run exactly these text shas, one per line; "
                                                   "the shard rule is not applied")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=1,
                    help="parallel texts; the laptop lane holds 8")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--merge", default="", help="fold another machine's <variant>/w<N> dir in")
    ap.add_argument("--collect-strings", default="",
                    help="write the {sha, text} jsonl facet_embed_gpu.py takes and stop")
    ap.add_argument("--retry-failed", action="store_true",
                    help="drop the .failed.json markers of this shard and ask those again")
    ap.add_argument("--allow-prompt-mismatch", action="store_true")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the plan and the cost estimate, call nothing")
    args = ap.parse_args(argv)

    t0 = time.perf_counter()
    print(f"facet_views starting | variant {args.variant} | write {args.write} | "
          f"out {args.out}", flush=True)
    if args.workers > 8:
        raise SystemExit("facet_views: --workers above 8 exhausts this laptop's paging file "
                         "(CLAUDE.md, 2026-09-15); pass 8 or fewer")

    fa()._utf8_console()
    from graph.facet_views_texts import read_texts

    ppath = prompt_path(args.variant, args.prompt)
    system = prompt_text(ppath)
    sha = prompt_sha(system)
    k, n = fa().parse_shard(args.shard)
    out_root = Path(args.out)

    if args.collect_strings:
        rows = read_texts(Path(args.texts))[1] if args.texts else []
        result = collect_strings(out_root, rows, args.collect_strings)
        for run in result["runs"]:
            print(f"  {run['variant']}/{run['write']}: {run['files']} texts, "
                  f"{run['strings']} view strings ({run['nothing_lines']} are "
                  f"{NOTHING_LINE!r})", flush=True)
        print(f"  tag phrases {result['phrases']} from {args.texts or '(no texts file)'}",
              flush=True)
        print(f"facet_views strings | {result['strings']} distinct -> {result['out']} "
              f"| {time.perf_counter() - t0:.1f}s", flush=True)
        return 0

    if args.merge:
        print(f"facet_views merge | {args.variant}/w{args.write} | prompt {sha[:12]}",
              flush=True)
        print(f"  {merge(out_root, args.variant, args.write, Path(args.merge), sha)}",
              flush=True)
        return 0

    if not args.texts:
        raise SystemExit("facet_views: --texts is required")
    header, rows = read_texts(Path(args.texts))

    wanted = fa().read_ids("", args.ids_file)
    if wanted:
        by_sha = {r["sha"]: r for r in rows}
        mine = [by_sha[s] for s in wanted if s in by_sha]
        absent = [s for s in wanted if s not in by_sha]
        if absent:
            print(f"  shas not in this texts file: {', '.join(a[:12] for a in absent[:10])}"
                  f"{' …' if len(absent) > 10 else ''}", flush=True)
    else:
        mine = [r for r in rows if in_shard(r["sha"], k, n)]
    if args.limit:
        mine = mine[:args.limit]

    if args.retry_failed:
        dropped = 0
        for r in mine:
            p = failed_path(out_root, args.variant, args.write, r["sha"])
            if p.is_file():
                p.unlink()
                dropped += 1
        print(f"  --retry-failed: dropped {dropped} failure markers", flush=True)

    done_rows, todo, failed_rows, mismatched = [], [], [], []
    for r in mine:
        if failed_path(out_root, args.variant, args.write, r["sha"]).is_file():
            failed_rows.append(r)
            continue
        state_name = status_of(view_path(out_root, args.variant, args.write, r["sha"]), sha,
                               args.variant)
        if state_name == "done":
            done_rows.append(r)
        elif state_name == "prompt_mismatch":
            mismatched.append(r)
        else:
            todo.append(r)
    if mismatched and not args.allow_prompt_mismatch:
        raise SystemExit(
            f"facet_views: {len(mismatched)} text files were written under another prompt — "
            f"pass --allow-prompt-mismatch to ask them again under {sha[:12]}")
    todo += mismatched

    print(f"facet_views | texts {args.texts} | prompt {sha[:12]} ({ppath.name}) "
          f"| model {args.model}", flush=True)
    print(f"  texts {len(rows)} | chunks {header.get('ids')} | phrases "
          f"{sum(len(r.get('tags') or []) for r in rows)}", flush=True)
    scope = f"ids {len(mine)}" if wanted else f"shard {k}/{n}: {len(mine)} texts"
    print(f"  {scope} | done {len(done_rows)} | failed {len(failed_rows)} "
          f"| re-ask on prompt {len(mismatched)} | remaining {len(todo)} | "
          f"workers {args.workers}", flush=True)
    two = [sum(1 for r in rows if in_shard(r["sha"], i, 2)) for i in (0, 1)]
    print(f"  two-machine split: 0/2 = {two[0]} texts, 1/2 = {two[1]} texts", flush=True)
    for line in cost_lines(todo, args.variant):
        print(line, flush=True)
    print(f"  out {run_dir(out_root, args.variant, args.write)}", flush=True)
    print(f"  plan in {time.perf_counter() - t0:.1f}s", flush=True)

    if args.dry_run:
        return 0

    target = run_dir(out_root, args.variant, args.write)
    swept = fa().sweep_tmp(target) if target.is_dir() else 0
    if swept:
        print(f"  swept {swept} stale .tmp files", flush=True)
    lock = take_lock(out_root, args.variant, args.write, k, n)

    meta = {"texts": str(args.texts), "texts_header": header, "variant": args.variant,
            "write": args.write, "prompt_path": str(ppath), "prompt_sha256": sha,
            "model": args.model, "shard": f"{k}/{n}", "ids": wanted,
            "workers": args.workers, "out": str(target), "start": fa().now_iso()}
    state = fa().State(total=len(mine), done=len(done_rows))
    write_manifest(out_root, args.variant, args.write, state, meta, k, n)

    try:
        previous = signal.signal(signal.SIGINT, fa()._on_interrupt)
    except (ValueError, OSError):
        previous = None
    from harness import abort
    abort.watch()
    print("running — press q to stop after the running texts, Ctrl-C to stop now", flush=True)

    def work(row):
        write_views(row, out_root, args.variant, args.write, system, sha, args.model, state)

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
                write_manifest(out_root, args.variant, args.write, state, meta, k, n)
                last_manifest = time.time()
    except KeyboardInterrupt:
        stop.set()
        pool.shutdown(wait=False, cancel_futures=True)
        print("\ninterrupted — every finished text is on disk", flush=True)
    finally:
        pool.shutdown(wait=True)
        if previous is not None:
            try:
                signal.signal(signal.SIGINT, previous)
            except (ValueError, OSError):
                pass
        write_manifest(out_root, args.variant, args.write, state, meta, k, n)
        release_lock(lock)

    for f in submitted:
        if f.done() and not f.cancelled() and f.exception() is not None:
            print(f"  worker raised: {f.exception()!r}", flush=True)
    print(f"done {state.done}/{state.total} | calls {state.calls} "
          f"| lane tries {state.lane_tries} | retries {state.retries} "
          f"| parse failures {state.parse_failures} | incomplete {state.incomplete} "
          f"| nothing lines {getattr(state, 'nothing_lines', 0)} "
          f"| failures {state.failures} | tokens {state.tokens_in}/{state.tokens_out} "
          f"| {time.perf_counter() - t0:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

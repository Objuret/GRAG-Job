"""The querytagger split check: the query side asked in two calls instead of one.

Stage G (GENERATE) reads the question and writes the description and the tags. Stage S (SCORE)
reads that description and that tag list — fixed, never the question — and weighs each tag
against the described content through the five facets of his 09-09 ruling
(topic / temporal / why / activity / concreteness).

Each stage is asked twice on the same input as two independent calls, so generation stability
and scoring stability are measured apart: g1 and g2 differ only by the model, s1 and s2 differ
only by the model with the input held fixed at g1's.

One file per call under `output/querytagger_split/<day>/`, resumable: a call whose file exists
and parses is skipped. The question text is never printed; the per-call files carry it, as the
files under `output/querytagger_stability/` do.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from harness import chat
from harness.contract import generator_usage_from_chat

from artefact.querytagger import (
    GENERATE_SYSTEM, GENERATE_USER_TEMPLATE, SCORE_SYSTEM, SCORE_USER_TEMPLATE, SPLIT_FACETS,
    clean_tag, extract_json,
)
from arms.artefact_v2 import FILLER

ROOT = Path(__file__).resolve().parent.parent.parent
MODEL = "claude-haiku-4-5"
MAX_TOKENS_G = 1536
MAX_TOKENS_S = 4096
TOKEN_GUARD = 45000
DEFAULT_OUT = ROOT / "output" / "querytagger_split" / "2026-09-21"
IDS_FILE = ROOT / "data" / "10smoke.jsonl"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


GENERATE_SHA = sha(GENERATE_SYSTEM)
SCORE_SHA = sha(SCORE_SYSTEM)


class SplitError(RuntimeError):
    pass


# ------------------------------------------------------------------ parse and validate

def parse_generate(raw: dict) -> dict:
    """the GENERATE object -> {description, tags:[str]}, or ValueError.

    Description non-empty. Tags cleaned as the vocabulary writes them, dropped when one
    character, filler, or a repeat of a tag already taken (case-insensitive, first spelling
    kept)."""
    if not isinstance(raw, dict):
        raise ValueError(f"payload is {type(raw).__name__}, not an object")
    description = raw.get("description")
    if not isinstance(description, str) or not description.strip():
        raise ValueError("description is empty")
    rows = raw.get("tags")
    if not isinstance(rows, list) or not rows:
        raise ValueError("tags is not a non-empty list")
    tags, seen = [], set()
    for row in rows:
        if not isinstance(row, str):
            raise ValueError(f"tag is {type(row).__name__}, not a string: {row!r}")
        t = clean_tag(row)
        key = t.casefold()
        if len(t) < 2 or key in FILLER or key in seen:
            continue
        seen.add(key)
        tags.append(t)
    if not tags:
        raise ValueError("no tag survived cleaning")
    return {"description": description.strip(), "tags": tags}


def parse_score(raw: dict, tags: list) -> dict:
    """the SCORE object -> {tags:[{t, facets}]} in the order the tags were given, or ValueError.

    Every given tag is answered exactly once (matched case-insensitively on its cleaned
    spelling); an unknown tag, a missing tag, a repeat, a missing facet, a non-number or a
    value outside [0,1] is the payload being wrong, not a value to mend."""
    if not isinstance(raw, dict):
        raise ValueError(f"payload is {type(raw).__name__}, not an object")
    rows = raw.get("tags")
    if not isinstance(rows, list) or not rows:
        raise ValueError("tags is not a non-empty list")
    want = {t.casefold(): t for t in tags}
    if len(want) != len(tags):
        raise ValueError("the tags given are not distinct")
    got: dict = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"tag row is {type(row).__name__}, not an object")
        t = clean_tag(row.get("t", ""))
        key = t.casefold()
        if key not in want:
            raise ValueError(f"tag {t!r} was not given")
        if key in got:
            raise ValueError(f"tag {t!r} answered twice")
        facets_raw = row.get("facets")
        if not isinstance(facets_raw, dict):
            raise ValueError(f"tag {t!r} carries no facets object")
        facets = {}
        for f in SPLIT_FACETS:
            v = facets_raw.get(f)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError(f"facet {f!r} of tag {t!r} is not a number: {v!r}")
            v = float(v)
            if not 0.0 <= v <= 1.0:
                raise ValueError(f"facet {f!r} of tag {t!r} is outside [0,1]: {v}")
            facets[f] = v
        got[key] = facets
    missing = [want[k] for k in want if k not in got]
    if missing:
        raise ValueError(f"{len(missing)} tag(s) unanswered, e.g. {missing[:3]}")
    return {"tags": [{"t": t, "facets": got[t.casefold()]} for t in tags]}


def generate_prompt(question: str) -> tuple:
    return GENERATE_SYSTEM, GENERATE_USER_TEMPLATE.format(question=question)


def score_prompt(description: str, tags: list) -> tuple:
    body = "\n".join(f"- {t}" for t in tags)
    return SCORE_SYSTEM, SCORE_USER_TEMPLATE.format(description=description, tags=body)


# ------------------------------------------------------------------ the call

def _post(system: str, user: str, model: str, max_tokens: int, post) -> tuple:
    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": max_tokens,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }
    t0 = time.perf_counter()
    resp = post("/chat/completions", payload, timeout=480.0)
    secs = time.perf_counter() - t0
    ti, to = generator_usage_from_chat(resp.get("usage"))
    choices = resp.get("choices") or []
    finish = choices[0].get("finish_reason") if choices else "no choices"
    content = (choices[0].get("message") or {}).get("content") if choices else None
    return content, finish, int(ti), int(to), secs


def ask(system: str, user: str, validate, model: str = MODEL,
        max_tokens: int = MAX_TOKENS_G, post=None) -> dict:
    """one call, re-asked once on a parse or coverage failure and never again. Both calls are
    billed and both are counted."""
    post = post or chat.post
    calls = tok_in = tok_out = 0
    secs = 0.0
    raw = None
    problem = None
    for attempt in (1, 2):
        content, finish, ti, to, s = _post(system, user, model, max_tokens, post)
        calls += 1
        tok_in += ti
        tok_out += to
        secs += s
        raw = content
        if not content:
            problem = f"empty content (finish_reason={finish})"
            continue
        if finish == "length":
            problem = f"truncated at max_tokens={max_tokens}"
            continue
        try:
            parsed = validate(extract_json(content))
        except ValueError as e:
            problem = str(e)
            continue
        return {"ok": True, "parsed": parsed, "raw": raw, "tries": calls,
                "tokens_in": tok_in, "tokens_out": tok_out, "seconds": round(secs, 2)}
    return {"ok": False, "error": problem, "raw": raw, "tries": calls,
            "tokens_in": tok_in, "tokens_out": tok_out, "seconds": round(secs, 2)}


# ------------------------------------------------------------------ the run

def _write(path: Path, body: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(body, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _read_done(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    return body if isinstance(body, dict) and body.get("ok") else None


class Guard:
    """the cost guard: the first call whose input tokens pass the ceiling stops the run."""

    def __init__(self, ceiling: int):
        self.ceiling = ceiling
        self.tripped = None
        self.lock = threading.Lock()

    def check(self, label: str, tokens_in: int, tries: int) -> None:
        per_call = tokens_in / max(1, tries)
        if per_call > self.ceiling:
            with self.lock:
                if self.tripped is None:
                    self.tripped = (f"{label}: {per_call:,.0f} input tokens in one call, "
                                    f"over the {self.ceiling:,} ceiling")

    def stopped(self) -> bool:
        return self.tripped is not None


def run_stage(jobs: list, out_dir: Path, workers: int, guard: Guard, counters: dict,
              post=None) -> dict:
    """jobs: [(qid, stage, askname, system, user, validate, max_tokens)]"""
    results: dict = {}
    lock = threading.Lock()

    def one(job):
        qid, stage, askname, system, user, validate, max_tokens, extra = job
        path = out_dir / f"{qid}.{stage}.{askname}.json"
        done = _read_done(path)
        if done is not None:
            with lock:
                results[(qid, askname)] = done
                counters["skipped"] += 1
                print(f"  {qid} {stage} {askname}  cached", flush=True)
            return
        if guard.stopped():
            return
        got = ask(system, user, validate, MODEL, max_tokens, post)
        body = {
            "question_id": qid, "stage": stage, "ask": askname,
            "system_sha256": sha(system), "model": MODEL,
            "input": extra,
            "raw": got.get("raw"), "parsed": got.get("parsed"),
            "ok": got["ok"], "error": got.get("error"),
            "tokens_in": got["tokens_in"], "tokens_out": got["tokens_out"],
            "seconds": got["seconds"], "tries": got["tries"],
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        _write(path, body)
        with lock:
            results[(qid, askname)] = body
            counters["calls"] += body["tries"]
            counters["reasks"] += body["tries"] - 1
            counters["tokens_in"] += body["tokens_in"]
            counters["tokens_out"] += body["tokens_out"]
            if not body["ok"]:
                counters["failures"] += 1
            state = "ok" if body["ok"] else f"FAILED ({body['error']})"
            print(f"  {qid} {stage} {askname}  {body['seconds']:.1f}s  "
                  f"in {body['tokens_in']:,} out {body['tokens_out']:,}  "
                  f"tries {body['tries']}  {state}", flush=True)
        guard.check(f"{qid} {stage} {askname}", body["tokens_in"], body["tries"])

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, jobs))
    return results


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="the querytagger split check")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dry", action="store_true",
                    help="run the whole shape against a fake chat, call nothing")
    args = ap.parse_args(argv)

    t0 = time.perf_counter()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"querytagger split check | model {MODEL} | workers {args.workers}", flush=True)
    print(f"  GENERATE sha {GENERATE_SHA[:16]}  SCORE sha {SCORE_SHA[:16]}", flush=True)
    print(f"  out {out_dir}", flush=True)

    sys.path.insert(0, str(ROOT / "prod"))
    from harness import orchestrator
    chosen = orchestrator.load_chosen_questions(IDS_FILE)
    ids = [f"q{i:02d}" for i in range(1, len(chosen) + 1)]
    texts = {qid: q.question for qid, q in zip(ids, chosen)}
    real_ids = {qid: q.id for qid, q in zip(ids, chosen)}
    print(f"  {len(ids)} questions loaded: {', '.join(ids)}", flush=True)

    post = _fake_post if args.dry else None
    guard = Guard(TOKEN_GUARD if not args.dry else 10 ** 9)
    counters = {"calls": 0, "reasks": 0, "failures": 0, "skipped": 0,
                "tokens_in": 0, "tokens_out": 0}

    print("stage G — the question read twice", flush=True)
    g_jobs = []
    for qid in ids:
        system, user = generate_prompt(texts[qid])
        for askname in ("g1", "g2"):
            g_jobs.append((qid, "G", askname, system, user, parse_generate, MAX_TOKENS_G,
                           {"question_id_real": real_ids[qid], "question": texts[qid]}))
    g = run_stage(g_jobs, out_dir, args.workers, guard, counters, post)
    if guard.stopped():
        print(f"STOPPED — {guard.tripped}", flush=True)
        return 2

    print("stage S — g1's description and tags weighed twice", flush=True)
    s_jobs = []
    for qid in ids:
        row = g.get((qid, "g1"))
        if not row or not row.get("ok"):
            print(f"  {qid} S  skipped: g1 did not parse", flush=True)
            continue
        plan = row["parsed"]
        system, user = score_prompt(plan["description"], plan["tags"])
        validate = (lambda tags: (lambda raw: parse_score(raw, tags)))(plan["tags"])
        for askname in ("s1", "s2"):
            s_jobs.append((qid, "S", askname, system, user, validate, MAX_TOKENS_S,
                           {"question_id_real": real_ids[qid],
                            "description": plan["description"], "tags": plan["tags"]}))
    run_stage(s_jobs, out_dir, args.workers, guard, counters, post)
    if guard.stopped():
        print(f"STOPPED — {guard.tripped}", flush=True)
        return 2

    wall = round(time.perf_counter() - t0, 1)
    manifest = {
        "day": out_dir.name, "model": MODEL, "workers": args.workers,
        "generate_system_sha256": GENERATE_SHA, "score_system_sha256": SCORE_SHA,
        "facets": list(SPLIT_FACETS), "questions": len(ids),
        "ids": {qid: real_ids[qid] for qid in ids},
        "calls": counters["calls"], "reasks": counters["reasks"],
        "failures": counters["failures"], "skipped_cached": counters["skipped"],
        "tokens_in": counters["tokens_in"], "tokens_out": counters["tokens_out"],
        "wall_seconds": wall,
        "finished": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _write(out_dir / "manifest.json", manifest)
    print(f"done in {wall}s | calls {counters['calls']} (re-asks {counters['reasks']}, "
          f"failures {counters['failures']}, cached {counters['skipped']}) | "
          f"tokens in {counters['tokens_in']:,} out {counters['tokens_out']:,}", flush=True)
    return 0


# ------------------------------------------------------------------ the dry run's fake lane

def _fake_post(path: str, payload: dict, timeout: float = 0.0) -> dict:
    system = "\n\n".join(m["content"] for m in payload["messages"] if m["role"] == "system")
    user = "\n\n".join(m["content"] for m in payload["messages"] if m["role"] != "system")
    if system == GENERATE_SYSTEM:
        body = {"description": "A record of the decisions and the figures behind them.",
                "tags": ["rollout decision", "latency measurement", "migration plan"]}
    else:
        tags = [line[2:] for line in user.splitlines() if line.startswith("- ")]
        body = {"tags": [{"t": t, "facets": {f: 0.5 for f in SPLIT_FACETS}} for t in tags]}
    return {"choices": [{"message": {"content": json.dumps(body)}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1234, "completion_tokens": 56}}


if __name__ == "__main__":
    sys.exit(main())

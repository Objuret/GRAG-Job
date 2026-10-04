"""Per tag, the model orders the tag's chunks per facet into groups; writes an overlay file
(HERB_RANK_OVERLAY) of group index and group count per edge. Tags over --window go through a
RankGPT sliding window per facet (strict positions; only the top window−stride are the
model's). Nothing is written to the graph. Cross-tag comparison of the ranks is unruled.

  python test/graph/order_facet_layer.py --from-run DIR --window 20 [--repeat] --out FILE
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import itertools
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
for _sub in ("test", "prod"):
    _p = str(ROOT / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

BUILD_DATABASE = "herb-eval-volmax"
os.environ.setdefault("NEO4J_DATABASE", BUILD_DATABASE)

from arms.artefact_v2 import _chat_json                                         # noqa: E402
from graph.build_facet_layer import _CHUNKS_CYPHER, _EDGES_CYPHER, read_chunks  # noqa: E402
from graph.db import ALL_FACETS, DATABASE, RUN_ID, _driver                      # noqa: E402
from harness.progress import progress                                           # noqa: E402

CACHE_DIR = ROOT / "output" / "rank_facet_cache"
_FACETS = ", ".join(ALL_FACETS)

_SYSTEM = (
    "You are given one tag and a numbered list of text chunks that carry that tag.\n"
    "For each of five facets — " + _FACETS + " — arrange the chunks in order of how relevant "
    "the tag is to each chunk, according to that facet: the most relevant first.\n"
    "Chunks you cannot separate on a facet go together in one group. Every chunk number must "
    "appear exactly once per facet.\n"
    'Answer with JSON only: {"' + '": [[...], [...]], "'.join(ALL_FACETS) + '": [[...], [...]]}'
    " — for each facet a list of groups, each group a list of chunk numbers, first group most "
    "relevant."
)


# ------------------------------------------------------------------ one call

def _key(model: str, tag: str, chunk_ids: list, texts: list, facets: tuple, draw: int) -> str:
    h = hashlib.sha256()
    for field in (model, _SYSTEM, tag, json.dumps(chunk_ids), json.dumps(texts),
                  json.dumps(list(facets)), str(draw)):
        b = field.encode("utf-8")
        h.update(len(b).to_bytes(8, "big"))
        h.update(b)
    return h.hexdigest()


def _validate(n: int, facets: tuple):
    """every asked facet, every number 1..n exactly once, as groups"""
    def check(obj: dict) -> None:
        for f in facets:
            groups = obj.get(f)
            if not isinstance(groups, list) or not groups:
                raise ValueError(f"{f}: no groups")
            seen: list = []
            for g in groups:
                if not isinstance(g, list) or not g:
                    raise ValueError(f"{f}: a group is not a non-empty list: {g!r}")
                for x in g:
                    try:
                        seen.append(int(x))
                    except (TypeError, ValueError) as exc:
                        raise ValueError(f"{f}: {x!r} is not a chunk number") from exc
            if sorted(seen) != list(range(1, n + 1)):
                raise ValueError(f"{f}: numbers {sorted(seen)} are not 1..{n} exactly once")
    return check


def order_call(model: str, tag: str, chunk_ids: list, texts: list, facets: tuple,
               draw: int = 0) -> tuple:
    """one call: per asked facet, ordered groups of positions (0-based) — (groups, calls, in, out)"""
    key = _key(model, tag, chunk_ids, texts, facets, draw)
    path = CACHE_DIR / f"{key}.json"
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8")), 0, 0, 0
        except (ValueError, OSError):
            pass
    body = "\n\n".join(f"[{i + 1}]\n{t}" for i, t in enumerate(texts))
    user = (f"Tag: {tag}\n\nFacets to order on: {', '.join(facets)}\n\nChunks:\n\n{body}")
    obj, tin, tout, _ = _chat_json(model, _SYSTEM, user, 256 + 12 * len(texts) * len(facets),
                                   validate=_validate(len(texts), facets))
    groups = {f: [[int(x) - 1 for x in g] for g in obj[f]] for f in facets}
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(groups), encoding="utf-8")
    return groups, 1, tin, tout


# ------------------------------------------------------------------ one tag

def groups_to_ranks(groups: list, n: int) -> tuple:
    """group index per position, and the group count"""
    rank = [0] * n
    for gi, g in enumerate(groups):
        for pos in g:
            rank[pos] = gi
    return rank, len(groups)


def flatten(groups: list) -> list:
    return [pos for g in groups for pos in g]


def windows(n: int, window: int) -> list:
    """(start, end) slices from the back of the list to the front, stride window // 2"""
    if n <= window:
        return [(0, n)]
    stride = max(1, window // 2)
    out = []
    end = n
    while True:
        start = end - window
        if start <= 0:                       # the front window is always a full one
            out.append((0, min(n, window)))
            break
        out.append((start, end))
        end -= stride
    return out


def order_tag(model: str, tag: str, chunk_ids: list, texts: list, window: int,
              draw: int = 0) -> tuple:
    """per facet: (rank per chunk, group count); plus calls, tokens in, tokens out"""
    n = len(chunk_ids)
    if n == 1:
        return {f: ([0], 1) for f in ALL_FACETS}, 0, 0, 0
    if n <= window:
        groups, c, i, o = order_call(model, tag, chunk_ids, texts, ALL_FACETS, draw)
        return {f: groups_to_ranks(groups[f], n) for f in ALL_FACETS}, c, i, o

    out, calls, tin, tout = {}, 0, 0, 0
    for f in ALL_FACETS:
        order = list(range(n))                       # positions into chunk_ids, current order
        for start, end in windows(n, window):
            slot = order[start:end]
            groups, c, i, o = order_call(model, tag, [chunk_ids[p] for p in slot],
                                         [texts[p] for p in slot], (f,), draw)
            calls += c
            tin += i
            tout += o
            order[start:end] = [slot[p] for p in flatten(groups[f])]
        rank = [0] * n
        for place, p in enumerate(order):
            rank[p] = place
        out[f] = (rank, n)
    return out, calls, tin, tout


# ------------------------------------------------------------------ what came back

def pair_agreement(a: dict, b: dict) -> dict:
    """per facet, over every pair of chunks of every tag: share of pairs the two draws order
    the same way (both a before b, both b before a, or both a tie)"""
    agree = collections.Counter()
    total = collections.Counter()
    for tag, ranks_a in a.items():
        ranks_b = b.get(tag)
        if ranks_b is None:
            continue
        for f in ALL_FACETS:
            ra, _ = ranks_a[f]
            rb, _ = ranks_b[f]
            for i, j in itertools.combinations(range(len(ra)), 2):
                total[f] += 1
                if np.sign(ra[i] - ra[j]) == np.sign(rb[i] - rb[j]):
                    agree[f] += 1
    return {f: (agree[f] / total[f] if total[f] else float("nan")) for f in ALL_FACETS}


def describe(ranks: dict, label: str) -> None:
    """per facet: how many groups the model made, and how many chunks it left equal"""
    print(f"{label}: {len(ranks)} tags ordered")
    print(f"  {'facet':9s} {'groups/chunks':>13s} {'all-equal tags':>14s} {'strict tags':>11s}")
    for f in ALL_FACETS:
        ratio, flat, strict, n = [], 0, 0, 0
        for tag, per in ranks.items():
            r, g = per[f]
            if len(r) < 2:
                continue
            n += 1
            ratio.append(g / len(r))
            flat += g == 1
            strict += g == len(r)
        if n:
            print(f"  {f:9s} {np.median(ratio):13.2f} {flat / n:14.3f} {strict / n:11.3f}")


# ------------------------------------------------------------------ the pass

def chunk_ids_of_run(run_dir: Path) -> list:
    ids: list = []
    seen: set = set()
    with (run_dir / "arm_outputs.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            for cid in json.loads(line).get("meta", {}).get("ranking", {}).get("chunk_ids", []):
                if cid not in seen:
                    seen.add(cid)
                    ids.append(cid)
    return ids


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-run", metavar="DIR", help="only the chunks this run opened")
    ap.add_argument("--chunks", metavar="FILE", help="only these chunk ids, one per line")
    ap.add_argument("--tags", metavar="FILE", help="only these tags, one per line")
    ap.add_argument("--window", type=int, required=True, help="chunks per call")
    ap.add_argument("--model", default="claude-haiku-4-5")
    ap.add_argument("--workers", type=int, default=16, help="calls in flight on the lane")
    ap.add_argument("--repeat", action="store_true", help="order every tag twice")
    ap.add_argument("--out", metavar="FILE", help="the overlay file; without it nothing is called")
    args = ap.parse_args()
    if DATABASE != BUILD_DATABASE:
        raise SystemExit(f"NEO4J_DATABASE names {DATABASE!r}; this pass reads {BUILD_DATABASE!r}")

    drv = _driver()
    with drv.session(database=DATABASE) as s:
        rows = [dict(r) for r in s.run(_CHUNKS_CYPHER)]
        edges = [dict(r) for r in s.run(_EDGES_CYPHER, runId=RUN_ID)]
    chosen = None
    if args.from_run:
        chosen = set(chunk_ids_of_run(Path(args.from_run)))
    elif args.chunks:
        chosen = {l.strip() for l in Path(args.chunks).read_text(encoding="utf-8").splitlines()
                  if l.strip()}
    if chosen is not None:
        edges = [e for e in edges if e["chunkId"] in chosen]
    if args.tags:
        keep = {l.strip() for l in Path(args.tags).read_text(encoding="utf-8").splitlines()
                if l.strip()}
        edges = [e for e in edges if e["tag"] in keep]
    chunks_of = collections.defaultdict(list)
    for e in edges:
        chunks_of[e["tag"]].append(e["chunkId"])
    need = {c for cs in chunks_of.values() for c in cs}
    rows = [r for r in rows if r["chunkId"] in need]
    facts = read_chunks(rows)
    text_of = {r["chunkId"]: f["text"] for r, f in zip(rows, facts)}

    tags = sorted(chunks_of)
    multi = [t for t in tags if len(chunks_of[t]) > 1]
    calls = sum(1 if len(chunks_of[t]) <= args.window
                else len(windows(len(chunks_of[t]), args.window)) * len(ALL_FACETS)
                for t in multi) * (2 if args.repeat else 1)
    tokens = sum(sum(len(text_of[c]) for c in chunks_of[t]) for t in multi) / 3.3
    print(f"order_facet_layer: {len(tags)} tags, {sum(len(v) for v in chunks_of.values())} edges; "
          f"{len(multi)} tags with 2+ chunks need {calls} calls to {args.model}, window "
          f"{args.window}, {args.workers} in flight; about {tokens / 1e3:.0f}k tokens of chunk "
          f"text per draw", flush=True)
    if not args.out:
        print("  no --out: nothing is called.")
        return

    draws = (0, 1) if args.repeat else (0,)
    t0 = time.perf_counter()

    def one(job: tuple) -> tuple:
        tag, draw = job
        ids = chunks_of[tag]
        per, c, i, o = order_tag(args.model, tag, ids, [text_of[x] for x in ids],
                                 args.window, draw)
        return tag, draw, per, c, i, o

    jobs = [(t, d) for t in tags for d in draws]
    ranks = {d: {} for d in draws}
    n_calls = n_in = n_out = 0
    bar = progress(total=len(jobs), desc="order tags", unit="tag")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for done, (tag, draw, per, c, i, o) in enumerate(pool.map(one, jobs), 1):
            ranks[draw][tag] = per
            n_calls += c
            n_in += i
            n_out += o
            bar.update(1)
            if done % 25 == 0 or done == len(jobs):
                print(f"order_facet_layer: {done}/{len(jobs)} tag-draws, {n_calls} calls, "
                      f"{time.perf_counter() - t0:.0f}s", flush=True)
    bar.close()
    print(f"order_facet_layer: {n_calls} calls, {n_in} tokens in, {n_out} out, "
          f"{time.perf_counter() - t0:.0f}s", flush=True)

    describe(ranks[0], "draw 1")
    agreement = None
    if args.repeat:
        describe(ranks[1], "draw 2")
        agreement = pair_agreement(ranks[0], ranks[1])
        print("repeat: share of chunk pairs the two draws order the same way, per facet")
        for f in ALL_FACETS:
            print(f"  {f:9s} {agreement[f]:.3f}")

    out = []
    for tag in tags:
        per = ranks[0][tag]
        for k, cid in enumerate(chunks_of[tag]):
            out.append({"chunkId": cid, "tag": tag,
                        "rank": [per[f][0][k] for f in ALL_FACETS],
                        "groups": [per[f][1] for f in ALL_FACETS]})
    body = {"database": DATABASE, "run_id": RUN_ID, "model": args.model, "window": args.window,
            "facets": list(ALL_FACETS), "system": _SYSTEM, "tags": len(tags),
            "repeat_agreement": agreement, "edges": out}
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    print(f"order_facet_layer: overlay {path} ({sha[:12]}) — HERB_RANK_OVERLAY={path}", flush=True)


if __name__ == "__main__":
    main()

"""The pairs the Opus judge is asked: control, held-out, and the training rounds.

An edge is one (chunk, tag) relationship, named `<chunk_id>::<tag>`; the pool is every edge of
`output/facet_stats/<db>.jsonl` whose chunk is in `output/facet_neural/rows_export.jsonl` and
which carries a topic value. The chunks are split first, by the sha256 of the chunk id, so a
held-out pair never shares a chunk with a control or a training pair.

The known topic values never reach a pair row. They are written once, beside the files, in
`pairs/topic_key.jsonl`, keyed by pair id, for the judge control alone; the judge runner does
not open it.

Every draw runs off one seeded generator and the seed is recorded in `pairs/meta.json`.

    python test/graph/facet_pairs_select.py --out output/facet_pairs/pairs
    python test/graph/facet_pairs_select.py --out output/facet_pairs/pairs \\
        --acquire requested.jsonl --round 1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "prod", ROOT / "test"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

STATS_DEFAULT = ROOT / "output" / "facet_stats" / "herb-eval-volmax.jsonl"
ROWS_DEFAULT = ROOT / "output" / "facet_neural" / "rows_export.jsonl"

# The split. A stated default of the build order (PROGRESS.md), printed on every run.
HELDOUT_FRAC = 0.15
SPLIT_SALT = "facet_pairs_split:"

SEED = 20260918

# The gap bins of the judge control: near-equal is under the measured write-to-write noise of
# topic (0.03, 2026-09-18); the rest are the terciles of the remaining gaps inside each pair
# type's own candidate population.
NEAR_EQUAL = 0.03
BINS = ("near", "t1", "t2", "t3")

PAIR_TYPES = ("cross", "same_tag", "same_chunk")

# The control set, frozen in PROGRESS.md before any call.
CONTROL_N = {"cross": 120, "same_tag": 30, "same_chunk": 30}
CONTROL_REPEATS = 60

# The held-out set and its self-agreement subset, and the first training round.
HELDOUT_N = 600
HELDOUT_REPEATS = 200
TRAIN_N = 500

# The mix of pair types for the held-out and training draws (a stated default, PROGRESS.md):
# half cross, a quarter same-tag, a quarter same-chunk.
MIX = {"cross": 0.5, "same_tag": 0.25, "same_chunk": 0.25}

# How many candidate pairs per type are drawn to read the tercile edges off. Large enough that
# the edges do not move between runs of the same seed; it costs nothing but time.
CANDIDATES = 40_000

# A draw gives up after this many rejections in one bin; what it got is reported.
MAX_TRIES_PER_PAIR = 4_000

# The two file sizes this pool is: 4,808 chunks in the rows export, 61,018 lines in
# facet_stats. A run against another corpus passes `expect=None`.
EXPECT = (4808, 61018)


# ------------------------------------------------------------------ the pool

def edge_id(chunk_id: str, tag: str) -> str:
    return f"{chunk_id}::{tag}"


def read_rows(path: Path) -> tuple:
    """The rows export: a header line, then one row per chunk."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    if not lines:
        raise SystemExit(f"facet_pairs_select: {path} is empty")
    header = json.loads(lines[0]).get("header")
    if not isinstance(header, dict):
        raise SystemExit(f"facet_pairs_select: {path} has no header line")
    rows = [json.loads(line) for line in lines[1:] if line.strip()]
    return header, rows


def read_stats(path: Path) -> list:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            out.append(r)
    return out


def build_pool(stats_path: Path, rows_path: Path) -> tuple:
    """Every edge with a topic value on a chunk the rows export carries."""
    header, rows = read_rows(rows_path)
    chunks = {r["chunk_id"] for r in rows}
    stats = read_stats(stats_path)
    pool = []
    for r in stats:
        if r.get("chunk_id") not in chunks:
            continue
        topic = r.get("topic")
        if topic is None:
            continue
        pool.append({"chunk_id": r["chunk_id"], "tag": r["tag"], "topic": float(topic)})
    return header, rows, stats, pool


def held_out(chunk_id: str, frac: float = HELDOUT_FRAC) -> bool:
    digest = hashlib.sha256((SPLIT_SALT + chunk_id).encode("utf-8")).hexdigest()
    return int(digest[:16], 16) / float(1 << 64) < frac


# ------------------------------------------------------------------ the index

class Index:
    """One side of the chunk split, indexed for the three pair types."""

    def __init__(self, pool: list):
        self.edges = pool
        self.by_tag: dict = {}
        self.by_chunk: dict = {}
        for i, e in enumerate(pool):
            self.by_tag.setdefault(e["tag"], []).append(i)
            self.by_chunk.setdefault(e["chunk_id"], []).append(i)
        # A same-tag pair needs a tag on two different chunks; a same-chunk pair two tags of
        # one chunk. The draw picks its first edge only from the edges that can carry the type.
        self.same_tag_edges = [i for i, e in enumerate(pool)
                               if len({pool[j]["chunk_id"] for j in self.by_tag[e["tag"]]}) >= 2]
        self.same_chunk_edges = [i for i, e in enumerate(pool)
                                 if len(self.by_chunk[e["chunk_id"]]) >= 2]

    def population(self, pair_type: str) -> int:
        if pair_type == "cross":
            return len(self.edges)
        if pair_type == "same_tag":
            return len(self.same_tag_edges)
        return len(self.same_chunk_edges)

    def draw(self, rng: random.Random, pair_type: str):
        """One unordered pair of edge indices of that type, or None if the draw missed.

        The first edge is uniform over the EDGES that can carry the type, the second uniform
        over its partners — never over tags."""
        if pair_type == "cross":
            if len(self.edges) < 2:
                return None
            i = rng.randrange(len(self.edges))
            j = rng.randrange(len(self.edges))
            a, b = self.edges[i], self.edges[j]
            if i == j or a["chunk_id"] == b["chunk_id"] or a["tag"] == b["tag"]:
                return None
            return (i, j)
        if pair_type == "same_tag":
            if not self.same_tag_edges:
                return None
            i = rng.choice(self.same_tag_edges)
            mates = [j for j in self.by_tag[self.edges[i]["tag"]]
                     if self.edges[j]["chunk_id"] != self.edges[i]["chunk_id"]]
            if not mates:
                return None
            return (i, rng.choice(mates))
        if pair_type == "same_chunk":
            if not self.same_chunk_edges:
                return None
            i = rng.choice(self.same_chunk_edges)
            mates = [j for j in self.by_chunk[self.edges[i]["chunk_id"]] if j != i]
            if not mates:
                return None
            return (i, rng.choice(mates))
        raise ValueError(f"unknown pair type {pair_type!r}")


# ------------------------------------------------------------------ pairs

def pair_id_of(edge_a: str, edge_b: str) -> str:
    first, second = sorted((edge_a, edge_b))
    return hashlib.sha1(f"{first}\x1f{second}".encode("utf-8")).hexdigest()


def sorted_ends(index: Index, i: int, j: int) -> tuple:
    """The pair's canonical ends: the two edges sorted by edge id."""
    a, b = index.edges[i], index.edges[j]
    ea, eb = edge_id(a["chunk_id"], a["tag"]), edge_id(b["chunk_id"], b["tag"])
    if ea <= eb:
        return (a, ea), (b, eb)
    return (b, eb), (a, ea)


def row_of(index: Index, i: int, j: int, set_name: str, round_no: int, pair_type: str,
           order: str, repeat: int) -> dict:
    """One call's row. Nothing here carries a topic value."""
    (first, ef), (second, es) = sorted_ends(index, i, j)
    pid = pair_id_of(ef, es)
    pa, pb = (first, ef), (second, es)
    if order == "BA":
        pa, pb = pb, pa
    return {
        "pair_id": pid,
        "row_id": f"{pid}_{order}_r{repeat}",
        "set": set_name,
        "round": round_no,
        "pair_type": pair_type,
        "order": order,
        "repeat": repeat,
        "a": {"edge_id": pa[1], "chunk_id": pa[0]["chunk_id"], "tag": pa[0]["tag"]},
        "b": {"edge_id": pb[1], "chunk_id": pb[0]["chunk_id"], "tag": pb[0]["tag"]},
    }


def key_of(index: Index, i: int, j: int, pair_type: str, set_name: str, bin_name: str) -> dict:
    (first, ef), (second, es) = sorted_ends(index, i, j)
    return {
        "pair_id": pair_id_of(ef, es),
        "set": set_name,
        "pair_type": pair_type,
        "first": {"edge_id": ef, "topic": first["topic"]},
        "second": {"edge_id": es, "topic": second["topic"]},
        "gap": abs(first["topic"] - second["topic"]),
        "gap_bin": bin_name,
    }


def gap_of(index: Index, i: int, j: int) -> float:
    return abs(index.edges[i]["topic"] - index.edges[j]["topic"])


def tercile_edges(gaps: list) -> tuple:
    """The two cut points of the terciles of the gaps at or above the near-equal width."""
    wide = sorted(g for g in gaps if g >= NEAR_EQUAL)
    if len(wide) < 3:
        return (NEAR_EQUAL, NEAR_EQUAL)
    return (wide[len(wide) // 3], wide[2 * len(wide) // 3])


def bin_of(gap: float, cuts: tuple) -> str:
    if gap < NEAR_EQUAL:
        return "near"
    if gap < cuts[0]:
        return "t1"
    if gap < cuts[1]:
        return "t2"
    return "t3"


def split_counts(total: int, parts: int) -> list:
    """Equal counts, the remainder to the earliest cells."""
    base, rest = divmod(total, parts)
    return [base + (1 if k < rest else 0) for k in range(parts)]


# ------------------------------------------------------------------ the draws

def draw_binned(index: Index, rng: random.Random, pair_type: str, quota: int, cuts: tuple,
                seen: set) -> dict:
    """`quota` pairs of one type, as equally over the four gap bins as the population allows.

    A bin that runs dry is left short; the shortfall is not moved to another bin, it is
    printed."""
    want = dict(zip(BINS, split_counts(quota, len(BINS))))
    got = {b: [] for b in BINS}
    for b in BINS:
        tries = 0
        while len(got[b]) < want[b] and tries < MAX_TRIES_PER_PAIR * max(1, want[b]):
            tries += 1
            drawn = index.draw(rng, pair_type)
            if drawn is None:
                continue
            i, j = drawn
            (_, ef), (_, es) = sorted_ends(index, i, j)
            pid = pair_id_of(ef, es)
            if pid in seen:
                continue
            if bin_of(gap_of(index, i, j), cuts) != b:
                continue
            seen.add(pid)
            got[b].append((i, j))
    return {"want": want, "got": got}


def draw_plain(index: Index, rng: random.Random, pair_type: str, quota: int,
               seen: set) -> list:
    out = []
    tries = 0
    while len(out) < quota and tries < MAX_TRIES_PER_PAIR * max(1, quota):
        tries += 1
        drawn = index.draw(rng, pair_type)
        if drawn is None:
            continue
        i, j = drawn
        (_, ef), (_, es) = sorted_ends(index, i, j)
        pid = pair_id_of(ef, es)
        if pid in seen:
            continue
        seen.add(pid)
        out.append((i, j))
    return out


def draw_mix(index: Index, rng: random.Random, total: int, seen: set) -> tuple:
    """The stated mix, with a type that runs short filled from cross."""
    wanted = {t: int(round(total * MIX[t])) for t in PAIR_TYPES}
    wanted["cross"] = total - wanted["same_tag"] - wanted["same_chunk"]
    drawn = {}
    for t in ("same_tag", "same_chunk", "cross"):
        drawn[t] = draw_plain(index, rng, t, wanted[t], seen)
    short = sum(wanted[t] - len(drawn[t]) for t in PAIR_TYPES)
    filled = 0
    if short > 0:
        extra = draw_plain(index, rng, "cross", short, seen)
        drawn["cross"] += extra
        filled = len(extra)
    return drawn, wanted, filled


def write_jsonl(path: Path, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------ build

def build(out_dir: Path, stats_path: Path, rows_path: Path, seed: int,
          frac: float, expect: tuple | None = EXPECT) -> dict:
    t0 = time.perf_counter()
    header, rows, stats, pool = build_pool(stats_path, rows_path)
    print(f"  rows export: {len(rows)} chunks (header db {header.get('db')})", flush=True)
    print(f"  facet_stats: {len(stats)} lines", flush=True)
    print(f"  pool: {len(pool)} edges with a topic value on those chunks", flush=True)
    if expect is not None:
        assert len(rows) == expect[0], f"rows export has {len(rows)}, expected {expect[0]}"
        assert len(stats) == expect[1], f"facet_stats has {len(stats)}, expected {expect[1]}"
    assert len(pool) == len(stats), (
        f"{len(stats) - len(pool)} stats lines are off the rows export or carry no topic")

    train_pool = [e for e in pool if not held_out(e["chunk_id"], frac)]
    hold_pool = [e for e in pool if held_out(e["chunk_id"], frac)]
    train_chunks = {e["chunk_id"] for e in train_pool}
    hold_chunks = {e["chunk_id"] for e in hold_pool}
    print(f"  split by sha256('{SPLIT_SALT}'+chunk_id) < {frac}: "
          f"held-out {len(hold_chunks)} chunks / {len(hold_pool)} edges, "
          f"training {len(train_chunks)} chunks / {len(train_pool)} edges", flush=True)
    assert not (train_chunks & hold_chunks)

    train_ix, hold_ix = Index(train_pool), Index(hold_pool)
    rng = random.Random(seed)
    seen: set = set()
    report: dict = {"seed": seed, "heldout_frac": frac}

    # ---- the tercile edges, read off each pair type's own candidate population
    cuts = {}
    cand_rng = random.Random(seed + 1)
    print("\n  tercile edges of |topic_A - topic_B| (control candidates, "
          f"{CANDIDATES:,} draws a type, gaps >= {NEAR_EQUAL})", flush=True)
    print(f"    {'pair type':<12} {'candidates':>11} {'>=near':>8} {'t1|t2':>9} {'t2|t3':>9}",
          flush=True)
    for t in PAIR_TYPES:
        gaps = []
        for _ in range(CANDIDATES):
            drawn = train_ix.draw(cand_rng, t)
            if drawn is not None:
                gaps.append(gap_of(train_ix, *drawn))
        cuts[t] = tercile_edges(gaps)
        wide = sum(1 for g in gaps if g >= NEAR_EQUAL)
        print(f"    {t:<12} {len(gaps):>11,} {wide:>8,} {cuts[t][0]:>9.4f} {cuts[t][1]:>9.4f}",
              flush=True)
    report["tercile_edges"] = {t: list(cuts[t]) for t in PAIR_TYPES}

    # ---- control
    control_rows, key_rows = [], []
    control_pairs = []
    print("\n  control draw (both presentation orders on every pair)", flush=True)
    print(f"    {'pair type':<12} {'bin':<6} {'wanted':>7} {'got':>5}", flush=True)
    for t in PAIR_TYPES:
        res = draw_binned(train_ix, rng, t, CONTROL_N[t], cuts[t], seen)
        for b in BINS:
            print(f"    {t:<12} {b:<6} {res['want'][b]:>7} {len(res['got'][b]):>5}", flush=True)
            for (i, j) in res["got"][b]:
                control_pairs.append((t, b, i, j))
    report["control"] = {}
    for t in PAIR_TYPES:
        report["control"][t] = {b: sum(1 for (tt, bb, _, _) in control_pairs
                                       if tt == t and bb == b) for b in BINS}

    # the repeated subset: a third of every (type, bin) cell, seeded, the remainder to the
    # earliest cells so the total is exactly CONTROL_REPEATS where the cells allow it
    rep_rng = random.Random(seed + 2)
    cells = [(t, b) for t in PAIR_TYPES for b in BINS]
    by_cell = {c: [p for p in control_pairs if (p[0], p[1]) == c] for c in cells}
    share = split_counts(CONTROL_REPEATS, len(cells))
    repeated = set()
    for n, c in zip(share, cells):
        pick = rep_rng.sample(by_cell[c], min(n, len(by_cell[c])))
        for p in pick:
            (_, ef), (_, es) = sorted_ends(train_ix, p[2], p[3])
            repeated.add(pair_id_of(ef, es))
    short = CONTROL_REPEATS - len(repeated)
    if short > 0:
        def _pid(p):
            (_, ef), (_, es) = sorted_ends(train_ix, p[2], p[3])
            return pair_id_of(ef, es)

        rest = [p for p in control_pairs if _pid(p) not in repeated]
        for p in rep_rng.sample(rest, min(short, len(rest))):
            (_, ef), (_, es) = sorted_ends(train_ix, p[2], p[3])
            repeated.add(pair_id_of(ef, es))
    print(f"    repeated a third time (AB again): {len(repeated)} of {len(control_pairs)} pairs",
          flush=True)

    for (t, b, i, j) in control_pairs:
        (_, ef), (_, es) = sorted_ends(train_ix, i, j)
        pid = pair_id_of(ef, es)
        control_rows.append(row_of(train_ix, i, j, "control", 0, t, "AB", 1))
        control_rows.append(row_of(train_ix, i, j, "control", 0, t, "BA", 1))
        if pid in repeated:
            control_rows.append(row_of(train_ix, i, j, "control", 0, t, "AB", 2))
        key_rows.append(key_of(train_ix, i, j, t, "control", b))
    report["control_pairs"] = len(control_pairs)
    report["control_rows"] = len(control_rows)
    report["control_repeats"] = len(repeated)

    # ---- held-out
    hold_rng = random.Random(seed + 3)
    drawn, wanted, filled = draw_mix(hold_ix, hold_rng, HELDOUT_N, seen)
    print("\n  held-out draw (order drawn per pair)", flush=True)
    for t in PAIR_TYPES:
        print(f"    {t:<12} wanted {wanted[t]:>4} got {len(drawn[t]):>4}", flush=True)
    if filled:
        print(f"    filled from cross: {filled}", flush=True)
    hold_pairs = [(t, i, j) for t in PAIR_TYPES for (i, j) in drawn[t]]
    orders = {}
    hold_rows = []
    for (t, i, j) in hold_pairs:
        (_, ef), (_, es) = sorted_ends(hold_ix, i, j)
        pid = pair_id_of(ef, es)
        orders[pid] = hold_rng.choice(("AB", "BA"))
        hold_rows.append(row_of(hold_ix, i, j, "heldout", 0, t, orders[pid], 1))
    rep2_rng = random.Random(seed + 4)
    rep_want = {t: int(round(HELDOUT_REPEATS * MIX[t])) for t in PAIR_TYPES}
    rep_want["cross"] = HELDOUT_REPEATS - rep_want["same_tag"] - rep_want["same_chunk"]
    hold_repeated = set()
    for t in PAIR_TYPES:
        pool_t = [p for p in hold_pairs if p[0] == t]
        for p in rep2_rng.sample(pool_t, min(rep_want[t], len(pool_t))):
            (_, ef), (_, es) = sorted_ends(hold_ix, p[1], p[2])
            hold_repeated.add(pair_id_of(ef, es))
    for (t, i, j) in hold_pairs:
        (_, ef), (_, es) = sorted_ends(hold_ix, i, j)
        pid = pair_id_of(ef, es)
        if pid in hold_repeated:
            hold_rows.append(row_of(hold_ix, i, j, "heldout", 0, t, orders[pid], 2))
        key_rows.append(key_of(hold_ix, i, j, t, "heldout",
                               bin_of(gap_of(hold_ix, i, j), cuts[t])))
    print(f"    self-agreement subset (identical order again): {len(hold_repeated)}",
          flush=True)
    report["heldout_pairs"] = len(hold_pairs)
    report["heldout_rows"] = len(hold_rows)
    report["heldout_repeats"] = len(hold_repeated)
    report["heldout_filled_from_cross"] = filled

    # ---- training round 0
    train_rng = random.Random(seed + 5)
    tdrawn, twanted, tfilled = draw_mix(train_ix, train_rng, TRAIN_N, seen)
    print("\n  training round 0 draw (order drawn per pair)", flush=True)
    for t in PAIR_TYPES:
        print(f"    {t:<12} wanted {twanted[t]:>4} got {len(tdrawn[t]):>4}", flush=True)
    if tfilled:
        print(f"    filled from cross: {tfilled}", flush=True)
    train_rows = []
    for t in PAIR_TYPES:
        for (i, j) in tdrawn[t]:
            order = train_rng.choice(("AB", "BA"))
            train_rows.append(row_of(train_ix, i, j, "train", 0, t, order, 1))
            key_rows.append(key_of(train_ix, i, j, t, "train",
                                   bin_of(gap_of(train_ix, i, j), cuts[t])))
    report["train_pairs"] = sum(len(tdrawn[t]) for t in PAIR_TYPES)
    report["train_rows"] = len(train_rows)
    report["train_filled_from_cross"] = tfilled

    out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(out_dir / "control.jsonl", control_rows)
    write_jsonl(out_dir / "heldout.jsonl", hold_rows)
    write_jsonl(out_dir / "train_round0.jsonl", train_rows)
    write_jsonl(out_dir / "topic_key.jsonl", key_rows)

    # the chunk-disjointness the split promises, checked on what was actually written
    hold_touched = {r[s]["chunk_id"] for r in hold_rows for s in ("a", "b")}
    other_touched = {r[s]["chunk_id"] for r in (control_rows + train_rows) for s in ("a", "b")}
    assert not (hold_touched & other_touched), "a held-out pair shares a chunk with another set"

    meta = {
        "seed": seed, "heldout_frac": frac, "near_equal": NEAR_EQUAL,
        "split_salt": SPLIT_SALT, "mix": MIX,
        "stats": str(stats_path), "rows": str(rows_path),
        "rows_header": header, "pool_edges": len(pool),
        "chunks_heldout": len(hold_chunks), "chunks_train": len(train_chunks),
        "tercile_edges": report["tercile_edges"],
        "counts": report,
        "written": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                       encoding="utf-8")

    print(f"\n  written: control.jsonl {len(control_rows)} rows "
          f"({len(control_pairs)} pairs), heldout.jsonl {len(hold_rows)} rows "
          f"({len(hold_pairs)} pairs), train_round0.jsonl {len(train_rows)} rows, "
          f"topic_key.jsonl {len(key_rows)} pairs", flush=True)
    print(f"  out {out_dir} | {time.perf_counter() - t0:.1f}s", flush=True)
    return meta


# ------------------------------------------------------------------ acquisition

def acquire(out_dir: Path, request_path: Path, round_no: int, stats_path: Path,
            rows_path: Path, seed: int, frac: float) -> dict:
    """A later round's pairs, named by the ranker elsewhere as edge-id pairs.

    Every pair is refused if it touches a held-out chunk or if any earlier file already holds
    it. The type is read off the two edges, the order drawn from this round's own stream."""
    t0 = time.perf_counter()
    _, _, _, pool = build_pool(stats_path, rows_path)
    train_pool = [e for e in pool if not held_out(e["chunk_id"], frac)]
    index = Index(train_pool)
    where = {edge_id(e["chunk_id"], e["tag"]): i for i, e in enumerate(index.edges)}
    hold_chunks = {e["chunk_id"] for e in pool if held_out(e["chunk_id"], frac)}

    earlier = set()
    for name in ["control.jsonl", "heldout.jsonl"] + sorted(
            p.name for p in out_dir.glob("train_round*.jsonl")):
        path = out_dir / name
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                earlier.add(json.loads(line)["pair_id"])

    rng = random.Random(seed + 1000 + round_no)
    rows, keys = [], []
    taken = set()
    refused = {"held_out": 0, "unknown_edge": 0, "duplicate": 0, "same_edge": 0}
    asked = 0
    for line in Path(request_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        req = json.loads(line)
        asked += 1
        ea, eb = req["a"], req["b"]
        if ea == eb:
            refused["same_edge"] += 1
            continue
        if any(e.split("::", 1)[0] in hold_chunks for e in (ea, eb)):
            refused["held_out"] += 1
            continue
        if ea not in where or eb not in where:
            refused["unknown_edge"] += 1
            continue
        pid = pair_id_of(ea, eb)
        if pid in earlier or pid in taken:
            refused["duplicate"] += 1
            continue
        taken.add(pid)
        i, j = where[ea], where[eb]
        A, B = index.edges[i], index.edges[j]
        if A["chunk_id"] == B["chunk_id"]:
            pair_type = "same_chunk"
        elif A["tag"] == B["tag"]:
            pair_type = "same_tag"
        else:
            pair_type = "cross"
        order = rng.choice(("AB", "BA"))
        rows.append(row_of(index, i, j, "train", round_no, pair_type, order, 1))
        keys.append(key_of(index, i, j, pair_type, "train", "unbinned"))

    target = out_dir / f"train_round{round_no}.jsonl"
    write_jsonl(target, rows)
    with open(out_dir / "topic_key.jsonl", "a", encoding="utf-8") as f:
        for k in keys:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")
    print(f"  asked {asked} | written {len(rows)} | refused {refused}", flush=True)
    print(f"  out {target} | {time.perf_counter() - t0:.1f}s", flush=True)
    return {"asked": asked, "written": len(rows), "refused": refused, "out": str(target)}


# ------------------------------------------------------------------ cli

def main(argv: list | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass
    ap = argparse.ArgumentParser(description="the pairs the Opus judge is asked")
    ap.add_argument("--out", default=str(ROOT / "output" / "facet_pairs" / "pairs"))
    ap.add_argument("--stats", default=str(STATS_DEFAULT))
    ap.add_argument("--rows", default=str(ROWS_DEFAULT))
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--heldout-frac", type=float, default=HELDOUT_FRAC)
    ap.add_argument("--acquire", default="", help="a jsonl of {a, b} edge-id pairs to add")
    ap.add_argument("--round", type=int, default=0)
    args = ap.parse_args(argv)

    print(f"facet_pairs_select starting | out {args.out} | seed {args.seed} | "
          f"held-out fraction {args.heldout_frac}", flush=True)
    out_dir = Path(args.out)
    if args.acquire:
        if args.round < 1:
            raise SystemExit("facet_pairs_select: --acquire wants --round 1 or above")
        acquire(out_dir, Path(args.acquire), args.round, Path(args.stats), Path(args.rows),
                args.seed, args.heldout_frac)
        return 0
    build(out_dir, Path(args.stats), Path(args.rows), args.seed, args.heldout_frac)
    return 0


if __name__ == "__main__":
    sys.exit(main())

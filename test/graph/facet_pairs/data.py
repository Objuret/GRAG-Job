"""What the ranker is fitted to: the judge's comparisons, and nothing else.

ONE source. The judge's comparisons — one answer file per row under
`output/facet_pairs/answers/<set>/<row_id>.json`, each carrying the pair row and
`answers_canonical`: per facet one of "first" / "second" / "equal", stated against the pair's
two edge ids in SORTED order, so "first" always means the lexicographically smaller edge id
won. Every judgement is its own observation: a pair asked in both presentation orders, or asked
twice, contributes two rows. Disagreements are what the tie model is for; dropping them would
hide the judge's own dispersion, which is the ceiling the stop rule reads.

**The known topic numbers are not here.** His correction, 2026-09-18: the point of carrying
topic through the judge is not to test the judge. All five latent scales are learned from the
judge's choices ALONE; only afterwards are the existing numeric topic values revealed, the
mapping from the judge-derived topic scale to those numbers is read off, and the same mapping
is applied to the other four scales. A topic scale trained on the known values would make that
mapping circular, so this module — and every module on the training path — never opens
`output/facet_stats/*.jsonl`. It is opened in exactly one place, `map_topic.py`, after scoring.

The held-out rule is the sibling's and is recomputed here rather than trusted:
`sha256('facet_pairs_split:' + chunk_id)` as a fraction of 2**256, below 0.15 = held out. Every
loader that builds training material asserts that no observation touches a held-out chunk, and
separately that no answer row carries the `heldout` set name.

Nothing here reads gold, calls a model, or touches the graph.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

FACETS = ("topic", "temporal", "why", "activity", "concreteness")

# The sibling's split salt and fraction. Written here as constants so a change on either side
# shows up as a failed assertion rather than as silent leakage.
SPLIT_SALT = "facet_pairs_split:"
HELDOUT_FRACTION = 0.15

# The training-chunk validation carve-out. A different salt, so it is a split of the training
# chunks and not a second reading of the held-out rule. 0.15 mirrors the held-out fraction —
# a stated default, not a measurement.
VAL_SALT = "facet_pairs_trainval:"
VAL_FRACTION = 0.15

# The scoring shard rule. A third salt, so a shard is not a second reading of either split.
# `score_all.py --shard K/N` takes the chunks whose `shard_of` is K-1; the shards partition the
# corpus because each chunk id hashes to exactly one residue. The standalone Colab scorer
# carries this function verbatim.
SHARD_SALT = "facet_pairs_shard:"

# The name of the answer set that must never reach a gradient.
HELDOUT_SET = "heldout"

OUTCOMES = ("first", "second", "equal")


# ---------------------------------------------------------------- the chunk split

def split_fraction(chunk_id: str, salt: str = SPLIT_SALT) -> float:
    h = hashlib.sha256((salt + str(chunk_id)).encode("utf-8")).hexdigest()
    return int(h, 16) / float(1 << 256)


def is_heldout(chunk_id: str, fraction: float = HELDOUT_FRACTION) -> bool:
    return split_fraction(chunk_id, SPLIT_SALT) < fraction


def is_train_val(chunk_id: str, fraction: float = VAL_FRACTION) -> bool:
    """A training chunk reserved for checkpoint selection. Held-out chunks are not training
    chunks at all and this says nothing about them."""
    return split_fraction(chunk_id, VAL_SALT) < fraction


def shard_of(chunk_id: str, n_shards: int) -> int:
    """Which of `n_shards` scoring shards a chunk belongs to, 0-based."""
    h = hashlib.sha256((SHARD_SALT + str(chunk_id)).encode("utf-8")).hexdigest()
    return int(h, 16) % int(n_shards)


def edge_id(chunk_id: str, tag: str) -> str:
    return f"{chunk_id}::{tag}"


def split_edge_id(eid: str) -> tuple:
    chunk_id, _, tag = eid.partition("::")
    return chunk_id, tag


# ---------------------------------------------------------------- the corpus side

def load_texts(rows_export: str) -> dict:
    """chunk_id -> the chunk text. The export's first line is a header and carries no text."""
    out = {}
    with open(rows_export, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("chunk_id") and r.get("text"):
                out[r["chunk_id"]] = r["text"]
    return out


def load_chunks(rows_export: str) -> list:
    """The export's chunk records (chunk_id, kind, product, tags, text), header dropped."""
    out = []
    with open(rows_export, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("chunk_id") and r.get("text") and r.get("tags"):
                r["tags"] = [t if isinstance(t, str) else t.get("name") for t in r["tags"]]
                r["tags"] = [t for t in r["tags"] if t]
                out.append(r)
    return out


# ---------------------------------------------------------------- the judge side

def load_answer_rows(answers_dir: str, sets: list | None = None) -> list:
    """Every answer file under `answers_dir`, one dict per row, extra keys kept."""
    root = Path(answers_dir)
    if not root.is_dir():
        return []
    rows = []
    for sub in sorted(p for p in root.iterdir() if p.is_dir()):
        if sets is not None and sub.name not in sets:
            continue
        for path in sorted(sub.glob("*.json")):
            r = json.loads(path.read_text(encoding="utf-8"))
            r.setdefault("set", sub.name)
            r.setdefault("row_id", path.stem)
            rows.append(r)
    return rows


def _edge_of(side) -> tuple:
    """(edge_id, chunk_id, tag) from a pair side, whichever of the two shapes it carries."""
    if isinstance(side, str):
        cid, tag = split_edge_id(side)
        return side, cid, tag
    eid = side.get("edge_id")
    cid, tag = side.get("chunk_id"), side.get("tag")
    if eid and (cid is None or tag is None):
        cid, tag = split_edge_id(eid)
    if not eid:
        eid = edge_id(cid, tag)
    return eid, cid, tag


def observations(rows: list) -> list:
    """One observation per (answer row, facet) with a stated outcome.

    Each observation is keyed on the two edge ids in SORTED order — `a` is the lexicographically
    smaller — so "first" is always a win for `a` whatever order the judge was shown. Rows whose
    `answers_canonical` is missing a facet contribute nothing for that facet and are not an
    error: the sibling may judge fewer facets on a row.
    """
    out = []
    for r in rows:
        ans = r.get("answers_canonical") or {}
        if not isinstance(ans, dict):
            continue
        ea, ca, ta = _edge_of(r["a"])
        eb, cb, tb = _edge_of(r["b"])
        (lo, lo_c, lo_t), (hi, hi_c, hi_t) = sorted(
            [(ea, ca, ta), (eb, cb, tb)], key=lambda x: x[0])
        for facet in FACETS:
            v = ans.get(facet)
            if v is None:
                continue
            v = str(v).strip().lower()
            if v not in OUTCOMES:
                raise ValueError(f"row {r.get('row_id')!r} facet {facet}: "
                                 f"answer {v!r} is not one of {OUTCOMES}")
            out.append({
                "facet": facet,
                "a_edge_id": lo, "a_chunk_id": lo_c, "a_tag": lo_t,
                "b_edge_id": hi, "b_chunk_id": hi_c, "b_tag": hi_t,
                "outcome": v,
                "pair_id": r.get("pair_id"), "row_id": r.get("row_id"),
                "set": r.get("set"), "pair_type": r.get("pair_type"),
                "order": r.get("order"), "repeat": r.get("repeat"),
            })
    return out


def assert_no_heldout(obs: list, fraction: float = HELDOUT_FRACTION) -> int:
    """Raise if any training observation touches a held-out chunk. Returns the count checked."""
    bad = [o for o in obs
           if is_heldout(o["a_chunk_id"], fraction) or is_heldout(o["b_chunk_id"], fraction)]
    if bad:
        eg = bad[0]
        raise AssertionError(
            f"held-out leakage: {len(bad)} of {len(obs)} training observations touch a "
            f"held-out chunk, e.g. row {eg['row_id']!r} "
            f"({eg['a_chunk_id']} / {eg['b_chunk_id']})")
    return len(obs)


def assert_no_heldout_set(rows: list) -> int:
    """Raise if any answer row is labelled with the held-out set name.

    The chunk-hash rule and the `set` field are two independent statements of the same fact;
    the training path checks both, so a mislabelled file and a mis-drawn pair are each caught.
    """
    bad = [r for r in rows if str(r.get("set") or "") == HELDOUT_SET]
    if bad:
        raise AssertionError(
            f"held-out leakage: {len(bad)} of {len(rows)} answer rows carry set "
            f"{HELDOUT_SET!r}, e.g. {bad[0].get('row_id')!r}")
    return len(rows)


def partition_observations(obs: list, fraction: float = HELDOUT_FRACTION) -> dict:
    """Split observations into the ones that may be trained on and the ones that may not."""
    train, held = [], []
    for o in obs:
        if is_heldout(o["a_chunk_id"], fraction) or is_heldout(o["b_chunk_id"], fraction):
            held.append(o)
        else:
            train.append(o)
    return {"train": train, "heldout": held}


def training_val_split(obs: list) -> dict:
    """Checkpoint-selection split INSIDE the training observations: an observation goes to the
    validation side when either of its chunks is a training-validation chunk, so no chunk's
    text is on both sides."""
    fit, val = [], []
    for o in obs:
        if is_train_val(o["a_chunk_id"]) or is_train_val(o["b_chunk_id"]):
            val.append(o)
        else:
            fit.append(o)
    return {"fit": fit, "val": val}


def edges_of(obs: list) -> list:
    """The distinct (edge_id, chunk_id, tag) an observation list touches."""
    seen = {}
    for o in obs:
        seen.setdefault(o["a_edge_id"], (o["a_chunk_id"], o["a_tag"]))
        seen.setdefault(o["b_edge_id"], (o["b_chunk_id"], o["b_tag"]))
    return [(e, c, t) for e, (c, t) in sorted(seen.items())]


def attach_texts(obs: list, texts: dict) -> list:
    """Drop observations whose chunk text is not in the export, and count them."""
    keep = [o for o in obs if o["a_chunk_id"] in texts and o["b_chunk_id"] in texts]
    return keep


def main(argv: list | None = None) -> int:
    """Print what the judge's answers hold right now. No training, no model."""
    import argparse
    ap = argparse.ArgumentParser(description="the pairwise facet data, counted")
    ap.add_argument("--answers", default="output/facet_pairs/answers")
    ap.add_argument("--rows", default="output/facet_neural/rows_export.jsonl")
    a = ap.parse_args(argv)

    print("facet pairs data", flush=True)
    texts = load_texts(a.rows)
    held = sum(1 for c in texts if is_heldout(c))
    print(f"  chunks with text {len(texts)} | held-out {held} "
          f"({held / max(len(texts), 1):.3f}) | training {len(texts) - held}", flush=True)
    rows = load_answer_rows(a.answers)
    obs = observations(rows)
    print(f"  answer rows {len(rows)} | observations {len(obs)}", flush=True)
    if obs:
        part = partition_observations(obs)
        for f in FACETS:
            n = [o for o in obs if o["facet"] == f]
            ties = sum(1 for o in n if o["outcome"] == "equal")
            print(f"    {f:<13} {len(n):>6} observations | ties {ties}", flush=True)
        print(f"  training {len(part['train'])} | held-out {len(part['heldout'])}", flush=True)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

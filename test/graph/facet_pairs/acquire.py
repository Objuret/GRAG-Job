"""Choose the next round's pairs: half where the ranker is unsure, half where it has not looked.

Two halves, a stated 50/50 default — the uncertainty half sharpens the order the ranker already
has, the coverage half keeps the comparison graph from collapsing onto the edges it has already
asked about, and neither alone is a sound design (pure uncertainty sampling concentrates on one
region and leaves the graph disconnected; pure coverage never resolves a close call).

**Uncertainty.** Under Davidson's tie model the probability that `a` wins GIVEN the judge does
not call it a tie is sigmoid(s_a - s_b), so it is nearest 0.5 exactly where the two scores are
equal — which is also where Davidson's tie probability is at its maximum. The uncertainty half
therefore takes the candidate pairs with the smallest |score gap|, per facet, and only facets
that have not stopped drive it.

**Coverage.** The comparison graph's nodes are the edges that have been compared, and its
degree is how many comparisons each one has. A pair drawn between two low-degree nodes joins
poorly covered parts of the graph. Degree is counted per edge, per chunk and per tag, and the
candidate's cost is the sum of the four, ascending.

Scores come from the round's `scores.jsonl` — every edge is already scored there, and a pair's
gap is the difference of two edge scores, so choosing pairs costs no forward pass.

Only TRAINING chunks are drawn from: the held-out rule is recomputed here and every candidate
touching a held-out chunk is refused. Pairs already asked (in the pairs dir or the answers dir)
are excluded, and the output is de-duplicated on the unordered edge pair.

Output: `{a_edge_id, b_edge_id, pair_type, reason}` per line, for the sibling's
`facet_pairs_select.py --acquire`.

    python test/graph/facet_pairs/acquire.py --scores output/facet_pairs/rounds/round1/scores.jsonl \\
        --size 1000 --round 2 --out output/facet_pairs/acquired/round2.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for _p in (str(HERE), str(HERE.parent)):
    if _p not in sys.path:
        sys.path.insert(0, str(_p))

try:  # package first: the plain name collides with facet_neural's own data.py
    from . import data as D
except ImportError:  # run as a script on the desktop
    import data as D  # noqa: E402

FACETS = D.FACETS

# The two halves. A stated default: neither criterion has a measured claim on more than half.
UNCERTAINTY_SHARE = 0.5

# The pair-type mix, the same stated default the judge's draws use (PROGRESS.md).
PAIR_MIX = {"cross": 0.50, "same_tag": 0.25, "same_chunk": 0.25}

# Candidate pairs drawn per requested pair before ranking. 40 is a stated default: it makes the
# selected pairs roughly the most extreme 2.5% of a random draw, far enough into the tail to
# matter and cheap enough to draw in memory.
CANDIDATE_FACTOR = 40

STOPPED = ("done", "stalled", "failed")


def load_scores(path: str) -> list:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def asked_pairs(pairs_dir: str, answers_dir: str) -> set:
    """Every unordered edge pair already asked, from the pair files and the answer files."""
    seen = set()

    def _add(r):
        try:
            a = r["a"]["edge_id"] if isinstance(r["a"], dict) else r["a"]
            b = r["b"]["edge_id"] if isinstance(r["b"], dict) else r["b"]
        except (KeyError, TypeError):
            return
        seen.add(tuple(sorted((a, b))))

    p = Path(pairs_dir)
    if p.is_dir():
        for f in sorted(p.glob("*.jsonl")):
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    _add(json.loads(line))
    for r in D.load_answer_rows(answers_dir):
        _add(r)
    return seen


def comparison_degrees(pairs_dir: str, answers_dir: str) -> dict:
    """How many comparisons each edge, chunk and tag has been in so far."""
    deg = {"edge": {}, "chunk": {}, "tag": {}}

    def _bump(eid):
        cid, tag = D.split_edge_id(eid)
        deg["edge"][eid] = deg["edge"].get(eid, 0) + 1
        deg["chunk"][cid] = deg["chunk"].get(cid, 0) + 1
        deg["tag"][tag] = deg["tag"].get(tag, 0) + 1

    for a, b in asked_pairs(pairs_dir, answers_dir):
        _bump(a)
        _bump(b)
    return deg


def active_facets(rounds_dir: str, stopped_arg: str = "") -> list:
    """Facets that have not stopped, read from the newest round's eval.json."""
    if stopped_arg:
        stopped = {s for s in stopped_arg.split(",") if s}
        return [f for f in FACETS if f not in stopped]
    root, newest = Path(rounds_dir), None
    if root.is_dir():
        for p in root.glob("round*/eval.json"):
            try:
                n = int(p.parent.name.replace("round", ""))
            except ValueError:
                continue
            if newest is None or n > newest[0]:
                newest = (n, p)
    if newest is None:
        return list(FACETS)
    r = json.loads(newest[1].read_text(encoding="utf-8"))
    dec = r.get("decisions") or {}
    return [f for f in FACETS if (dec.get(f) or {}).get("decision") not in STOPPED]


class Candidates:
    """Draws unordered pairs of TRAINING-chunk edges under the pair-type mix."""

    def __init__(self, rows: list, seed: int):
        self.rnd = random.Random(seed)
        self.rows = [r for r in rows if not D.is_heldout(r["chunk_id"])]
        self.by_chunk, self.by_tag = {}, {}
        for i, r in enumerate(self.rows):
            self.by_chunk.setdefault(r["chunk_id"], []).append(i)
            self.by_tag.setdefault(r["tag"], []).append(i)
        self.chunk_keys = sorted(c for c, v in self.by_chunk.items() if len(v) > 1)
        self.tag_keys = sorted(t for t, v in self.by_tag.items() if len(v) > 1)

    def draw(self, kind: str):
        if kind == "same_chunk" and self.chunk_keys:
            pool = self.by_chunk[self.chunk_keys[self.rnd.randrange(len(self.chunk_keys))]]
        elif kind == "same_tag" and self.tag_keys:
            pool = self.by_tag[self.tag_keys[self.rnd.randrange(len(self.tag_keys))]]
        else:
            kind, pool = "cross", None
        if pool is None:
            i, j = self.rnd.randrange(len(self.rows)), self.rnd.randrange(len(self.rows))
        else:
            i, j = pool[self.rnd.randrange(len(pool))], pool[self.rnd.randrange(len(pool))]
        if i == j:
            return None
        a, b = self.rows[i], self.rows[j]
        if kind == "cross" and (a["chunk_id"] == b["chunk_id"] or a["tag"] == b["tag"]):
            return None
        if a["edge_id"] > b["edge_id"]:
            a, b = b, a
        return a, b, kind


def type_quota(n: int, mix: dict) -> dict:
    """Integer counts per pair type, the remainder going to the largest share."""
    out, used = {}, 0
    keys = sorted(mix, key=lambda k: -mix[k])
    for k in keys[1:]:
        out[k] = int(n * mix[k])
        used += out[k]
    out[keys[0]] = n - used
    return out


def select(rows: list, size: int, facets: list, deg: dict, already: set,
           seed: int = 20260918, uncertainty_share: float = UNCERTAINTY_SHARE,
           mix: dict | None = None, candidate_factor: int = CANDIDATE_FACTOR) -> list:
    mix = dict(mix or PAIR_MIX)
    cand = Candidates(rows, seed)
    if len(cand.rows) < 2:
        return []
    chosen, taken = [], set(already)

    def _take(a, b, kind, reason):
        key = (a["edge_id"], b["edge_id"])
        if key in taken:
            return False
        taken.add(key)
        chosen.append({"a_edge_id": a["edge_id"], "b_edge_id": b["edge_id"],
                       "pair_type": kind, "reason": reason})
        return True

    n_unc = int(round(size * uncertainty_share)) if facets else 0
    n_cov = size - n_unc

    # --- uncertainty: the smallest |score gap| per facet, the budget split evenly
    if n_unc and facets:
        per_facet = type_quota(n_unc, {f: 1.0 / len(facets) for f in facets})
        for facet in facets:
            want = per_facet[facet]
            quota = type_quota(want, mix)
            for kind, k_want in quota.items():
                pool = []
                for _ in range(max(k_want, 1) * candidate_factor):
                    d = cand.draw(kind)
                    if d is None:
                        continue
                    a, b, real = d
                    if (a["edge_id"], b["edge_id"]) in taken:
                        continue
                    pool.append((abs(a[facet] - b[facet]), a, b, real))
                pool.sort(key=lambda x: x[0])
                got = 0
                for gap, a, b, real in pool:
                    if got >= k_want:
                        break
                    if _take(a, b, real, f"uncertainty:{facet}"):
                        got += 1

    # --- coverage: the lowest summed degree over edge, chunk and tag
    if n_cov:
        quota = type_quota(n_cov, mix)
        for kind, k_want in quota.items():
            pool = []
            for _ in range(max(k_want, 1) * candidate_factor):
                d = cand.draw(kind)
                if d is None:
                    continue
                a, b, real = d
                if (a["edge_id"], b["edge_id"]) in taken:
                    continue
                cost = sum(deg["edge"].get(x["edge_id"], 0)
                           + deg["chunk"].get(x["chunk_id"], 0)
                           + deg["tag"].get(x["tag"], 0) for x in (a, b))
                pool.append((cost, a, b, real))
            pool.sort(key=lambda x: x[0])
            got = 0
            for cost, a, b, real in pool:
                if got >= k_want:
                    break
                if _take(a, b, real, "coverage"):
                    got += 1
    return chosen


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="the next round's pairs")
    ap.add_argument("--scores", required=True, help="a round's scores.jsonl")
    ap.add_argument("--size", type=int, required=True, help="the round's increment")
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--pairs-dir", default="output/facet_pairs/pairs")
    ap.add_argument("--answers", default="output/facet_pairs/answers")
    ap.add_argument("--rounds-dir", default="output/facet_pairs/rounds")
    ap.add_argument("--stopped", default="", help="comma-separated facets to exclude from the "
                                                  "uncertainty half; default read from the "
                                                  "newest eval.json")
    ap.add_argument("--uncertainty-share", type=float, default=UNCERTAINTY_SHARE)
    ap.add_argument("--seed", type=int, default=20260918)
    a = ap.parse_args(argv)

    out = Path(a.out or f"output/facet_pairs/acquired/round{a.round}.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = load_scores(a.scores)
    facets = active_facets(a.rounds_dir, a.stopped)
    deg = comparison_degrees(a.pairs_dir, a.answers)
    already = asked_pairs(a.pairs_dir, a.answers)
    print(f"facet pairs acquire | round {a.round} | size {a.size} | scored edges {len(rows)} "
          f"| active facets {','.join(facets) or '(none)'} | already asked {len(already)}",
          flush=True)

    chosen = select(rows, a.size, facets, deg, already, seed=a.seed,
                    uncertainty_share=a.uncertainty_share)
    with out.open("w", encoding="utf-8") as f:
        for c in chosen:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    by_reason, by_type = {}, {}
    for c in chosen:
        by_reason[c["reason"]] = by_reason.get(c["reason"], 0) + 1
        by_type[c["pair_type"]] = by_type.get(c["pair_type"], 0) + 1
    print(f"  chosen {len(chosen)} | by reason {by_reason} | by type {by_type}", flush=True)
    print(f"done | -> {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

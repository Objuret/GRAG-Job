"""What the row stamp `answered_at` is, in numbers: its distance to the question's own finish
stamp where one exists (rows of the changed harness), and the steps between rows (A)."""
import hashlib
import json
import statistics
import sys
from datetime import datetime

from folders import ALL, PROOF

sys.stdout.reconfigure(encoding="utf-8")


def rows(p):
    with open(p, encoding="utf-8") as fh:
        return [json.loads(x) for x in fh if x.strip()]


def t(s):
    return datetime.fromisoformat(s)


def q3(xs):
    xs = sorted(xs)
    return tuple(round(x, 3) for x in (xs[0], statistics.median(xs), xs[-1]))


rs = rows(ALL["D.v4_10"] / "arm_outputs.jsonl")
gap = [(t(r["answered_at"]) - t(r["timing"]["finished_at"])).total_seconds() for r in rs]
fin = [t(r["timing"]["finished_at"]) for r in rs]
print(f"D.v4_10 (6 workers): answered_at - timing.finished_at, seconds, min/median/max {q3(gap)}; rows where it is > 0: {sum(1 for g in gap if g > 0)}/{len(rs)}")
print(f"   timing.finished_at non-decreasing in file order: {sum(1 for a, b in zip(fin, fin[1:]) if b >= a)}/{len(rs) - 1} steps; answered_at non-decreasing: {sum(1 for a, b in zip(rs, rs[1:]) if t(b['answered_at']) >= t(a['answered_at']))}/{len(rs) - 1}")
for name in ("A.luc", "A.vec"):
    rs = rows(ALL[name] / "arm_outputs.jsonl")
    at = [t(r["answered_at"]) for r in rs]
    steps = [(b - a).total_seconds() for a, b in zip(at, at[1:])]
    least = min(r["generator"]["time_s"] for r in rs)
    print(f"{name}: steps between consecutive answered_at, seconds, min/median/max {q3(steps)}; steps shorter than the folder's shortest generator.time_s ({least:.2f} s): {sum(1 for s in steps if s < least)}/{len(steps)}")

print()
print("C: the two input files on disk against the manifests' hashes")
for f, key in (("madeup_question.jsonl", "questions_sha256"), ("madeup_ids.jsonl", "ids_sha256")):
    h = hashlib.sha256((PROOF / f).read_bytes()).hexdigest()
    same = {n: json.loads((ALL[n] / "run_manifest.json").read_text(encoding="utf-8"))["inputs"][key] == h for n in ALL if n.startswith("C.")}
    print(f"   {f}: sha256 {h[:16]}   equals inputs.{key} in {same}")

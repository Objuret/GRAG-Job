"""What changed inside the 72,000 between the clouds' order and the 4-combo (his 2026-10-17 "why did i tget
worse?"). From the two run folders of the hundred and the citation ids only; no question text, no model call.

Per question, the chunks delivered only before and only after: how many, how often they hold a cited
record, and for the ones delivered only after, how they are tied to the chosen chunks.

    .venv/Scripts/python.exe output/research/2026-10-17-4combo-why/what_the_cut_changed.py <before> <after>
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
from harness import questions as HQ  # noqa: E402

cites = {q.id: {str(c) for c in q.citations} for q in HQ.load_questions()}


def rows(folder):
    out = {}
    for line in (Path(folder) / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            rk = r["meta"]["ranking"]
            delivered = rk["delivered_chunk_ids"]
            ids = r["meta"]["chunk_ids"][:len(delivered)]
            out[r["id"]] = {"delivered": delivered, "ids": dict(zip(delivered, ids)), "rk": rk,
                            "context": set(map(str, r["context_ids"])),
                            "order": rk["ordered_chunk_ids"]}
    return out


before, after = rows(sys.argv[1]), rows(sys.argv[2])
recall = lambda r, q: len(r["context"] & cites[q]) / len(cites[q])  # noqa: E731
up = sum(recall(after[q], q) > recall(before[q], q) for q in after)
down = sum(recall(after[q], q) < recall(before[q], q) for q in after)
print(f"questions: recall higher after {up}, lower {down}, the same {len(after) - up - down}")
print(f"cited records delivered: before {sum(len(before[q]['context'] & cites[q]) for q in before)}, "
      f"after {sum(len(after[q]['context'] & cites[q]) for q in after)}")
gone_n = gone_cited = new_n = new_cited = 0
gone_step, new_ways, new_strength_cited, new_strength_not = Counter(), Counter(), [], []
first_cited_before = first_cited_after = 0
for q in after:
    b, a = before[q], after[q]
    held = lambda r, c: bool(set(map(str, r["ids"][c])) & cites[q])  # noqa: E731
    first_cited_before += held(b, b["delivered"][0]) if b["delivered"] else 0
    first_cited_after += held(a, a["delivered"][0]) if a["delivered"] else 0
    only_b = [c for c in b["delivered"] if c not in set(a["delivered"])]
    only_a = [c for c in a["delivered"] if c not in set(b["delivered"])]
    steps = dict(zip(b["delivered"], b["rk"]["delivered_step"]))
    for c in only_b:
        gone_n += 1
        gone_cited += held(b, c)
        gone_step[steps[c]] += 1
    at = {c: k for k, c in enumerate(a["delivered"])}
    for c in only_a:
        new_n += 1
        k = at[c]
        hit = held(a, c)
        new_cited += hit
        s = a["rk"]["delivered_storyline_strength"][k]
        (new_strength_cited if hit else new_strength_not).append(s)
        for w, counts in a["rk"]["delivered_storyline_ways"].items():
            new_ways[w] += counts[k] > 0
pct = lambda a, n: f"{a}/{n} ({100 * a / n:.1f}%)" if n else "-"  # noqa: E731
print(f"chunks delivered only before: {gone_n}, holding a cited record {pct(gone_cited, gone_n)}; their step in the "
      f"clouds: " + ", ".join(f"{s}: {n}" for s, n in sorted(gone_step.items())))
print(f"chunks delivered only after: {new_n}, holding a cited record {pct(new_cited, new_n)}; tied to a chosen chunk by "
      + ", ".join(f"{w} {pct(n, new_n)}" for w, n in new_ways.items()))
print(f"   their strength, middle: those holding a cited record {np.median(new_strength_cited):.0f}, the others "
      f"{np.median(new_strength_not):.0f}")
print(f"the first delivered text holds a cited record: before {first_cited_before}, after {first_cited_after}")

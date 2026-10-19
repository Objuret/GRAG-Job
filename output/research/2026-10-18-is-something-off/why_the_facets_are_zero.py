"""Why the facet weights come out zero (found 2026-10-18: every facet weight is 0 on 96 of the hundred). The
facet levels over the graph's edges, read off the knees (`v4_walk.facet_levels`), against the readings the facet
instrument gave each question's query tags (kept in each row of the run). No question text, no model call.

    .venv/Scripts/python.exe output/research/2026-10-18-is-something-off/why_the_facets_are_zero.py <run folder>
"""
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"
from arms import artefact_v4 as V  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402

p = V.prepare_over_corpus("why the facets are zero")
values = p.layer["raw"][:, 1:]
floors = WK.facet_levels(values)
names = ("temporal", "why", "activity", "concreteness")
print("per facet over the graph's eligible edges: middle value, the lowest value of each level (level 1 first)")
for f, name in enumerate(names):
    print(f"   {name}: middle {np.median(values[:, f]):.3f}, quartiles {np.percentile(values[:, f], 25):.3f}-"
          f"{np.percentile(values[:, f], 75):.3f}, max {values[:, f].max():.3f}; levels from "
          + ", ".join(f"{x:.3f}" for x in floors[f]))
rows = [json.loads(l) for l in (Path(sys.argv[1]) / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()]
middles = np.array([np.median(np.array(list(r["meta"]["scope"]["facets"]["readings"].values())), axis=0)
                    for r in rows])
every = np.concatenate([np.array(list(r["meta"]["scope"]["facets"]["readings"].values())) for r in rows])
print("\nthe query tags' readings (the facet instrument on query tag against question and description):")
for f, name in enumerate(names):
    print(f"   {name}: every query tag middle {np.median(every[:, f]):.3f} (quartiles {np.percentile(every[:, f], 25):.3f}-"
          f"{np.percentile(every[:, f], 75):.3f}, max {every[:, f].max():.3f}); the question's middle reading, middle "
          f"{np.median(middles[:, f]):.3f}, max {middles[:, f].max():.3f}; questions whose middle reading reaches a "
          f"level: {int((middles[:, f] >= floors[f][-1]).sum()) if floors[f] else 0}")

"""Does the CLI transcript's span from the prompt entry to the reply entry give the server's time? For
the laptop's final-run calls that have both, compare that span with the reply's own duration_api_ms.
Reads files only; makes no model call; prints numbers only."""
import json
import statistics as st
from datetime import datetime
from pathlib import Path

import numpy as np

REPO = Path("C:/Coding/exjobbet/GRAG-Job")
LANE = Path("C:/Users/jocke/.claude-herb-lane/projects/C--Users-jocke-AppData-Local-Temp-herb-claude-lane")
T = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()  # noqa: E731
RUNS = {"lucene100 answers": ("lucene__gold100__cb72000__20261008T234209Z", "answer"),
        "vector100 answers": ("vector__gold100__cb72000__20261017T061242Z", "answer"),
        "artefact 20261020 first calls": ("artefact_v4__gold100__cb72000__20261020T041923Z", None),
        "artefact 20261020 answers": ("artefact_v4__gold100__cb72000__20261020T041923Z", "answer")}

for label, (run, role) in RUNS.items():
    diffs, found, missing, multi = [], 0, 0, 0
    for line in open(REPO / "output/k=chars" / run / "arm_outputs.jsonl", encoding="utf-8"):
        r = json.loads(line)
        for c in r["calls"]:
            if c.get("kind") != "chat" or not c.get("ok") or c.get("role") != role:
                continue
            env = c.get("envelope") or {}
            sid, api = env.get("session_id"), (env.get("duration_api_ms") or 0) / 1000
            p = LANE / f"{sid}.jsonl"
            if not sid or not p.exists() or not api:
                missing += 1
                continue
            user = asst = None
            n_asst = 0
            for x in p.read_text(encoding="utf-8").splitlines():
                d = json.loads(x)
                if d.get("type") == "user" and user is None:
                    user = d.get("timestamp")
                if d.get("type") == "assistant":
                    asst = d.get("timestamp")
                    n_asst += 1
            if not (user and asst):
                missing += 1
                continue
            multi += n_asst > 1
            found += 1
            diffs.append((T(asst) - T(user)) - api)
    if diffs:
        a = np.array(diffs)
        print(f"{label:32} calls {found} (no transcript {missing}, several replies {multi}) | transcript span minus duration_api_ms: "
              f"median {np.median(a):+.3f} s, 5% {np.percentile(a, 5):+.3f}, 95% {np.percentile(a, 95):+.3f}")
    else:
        print(f"{label:32} no call with a transcript (missing {missing})")

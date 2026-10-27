"""Compare, text by text, the query vectors a run made again with the vectors the run it stands for
made: the evidence that the run of EMBEDDED_IN (tools/export_finished_data.py) embedded the same texts.

    python tools/check_query_vectors.py <run folder> <desktop json> <its vectors folder> <vector folder> [...]

<desktop json> is the comparison made on the desktop, where most of the first run's vectors are:
{"per_key": {key: {"question_ids", "cosine", "found_in"}}}. The keys it found no vector for are
compared here: the run's vector (in <its vectors folder>, the cache that run wrote) against the one
in a <vector folder> of this machine (the first run's cache). A key is sha256(prefix + text), the
name the embedder gives a text's file. Writes query_vectors_against_the_run.json into the run
folder: per question, its texts, how many were compared and the lowest cosine. Nothing is sent to a
model; no other file is written.
"""
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "prod")]
MIN_COSINE = 0.9999
OUT = "query_vectors_against_the_run.json"


def cosine(a, b):
    a, b = np.asarray(a, dtype=np.float64).ravel(), np.asarray(b, dtype=np.float64).ravel()
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


def main():
    from harness import embed
    run, desktop, own_root = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    folders = [Path(p) for p in sys.argv[4:]]
    by_key = json.loads(desktop.read_text(encoding="utf-8"))["per_key"]
    own = {p.stem: p for p in own_root.rglob("*.npy")}
    keys_of = {}
    for line in (run / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        # the key as the embedder names a text's file: the record's own prefix and the text
        keys_of[r["id"]] = [hashlib.sha256(((c["prefix"] if c.get("prefix") is not None
                                             else embed.EMBED_PREFIX[c["input_type"]]) + (t or " ")).encode("utf-8")).hexdigest()
                            for c in r["calls"] if c.get("kind") == "embed" for t in c.get("texts") or []]
    result, here = {}, 0
    for key in sorted({k for ks in keys_of.values() for k in ks}):
        d = by_key.get(key) or {}
        if d.get("cosine") is not None:
            result[key] = (d["cosine"], f"desktop {d.get('found_in')}")
            continue
        theirs = next((f / f"{key}.npy" for f in folders if (f / f"{key}.npy").is_file()), None)
        if theirs is None or key not in own:
            result[key] = (None, None)
            continue
        result[key] = (cosine(np.load(own[key]), np.load(theirs)), "laptop")
        here += 1
    per_question = {}
    for qid, ks in keys_of.items():
        cs = [result[k][0] for k in ks if result[k][0] is not None]
        per_question[qid] = {"texts": len(ks), "compared": len(cs), "min_cosine": min(cs) if cs else None}
    found = [c for c, _ in result.values() if c is not None]
    out = {
        "made_at": datetime.now(timezone.utc).isoformat(),
        "how": ("each text the run embedded, by its key, against the vector of the same key that the run it "
                "stands for made (its cache on the desktop, cpu and cuda, the laptop's CPU vectors copied to "
                "the desktop, and the laptop's own cache), by cosine in float64; no model call"),
        "min_cosine_required": MIN_COSINE,
        "texts": len(result), "compared": len(found), "compared_on_the_laptop": here,
        "min_cosine": min(found) if found else None,
        "below": sorted(k for k, (c, _) in result.items() if c is not None and c < MIN_COSINE),
        "not_found": sorted(k for k, (c, _) in result.items() if c is None),
        "per_question": per_question,
    }
    (run / OUT).write_text(json.dumps(out, indent=1), encoding="utf-8")
    shutil.copy2(desktop, run / "query_vectors_desktop.json")
    if Path(__file__).resolve() != (run / Path(__file__).name).resolve():
        shutil.copy2(__file__, run / Path(__file__).name)
    print(f"texts {out['texts']}; compared {out['compared']} (here {here}); lowest cosine {out['min_cosine']}; "
          f"below {MIN_COSINE}: {len(out['below'])}; no vector to compare with: {len(out['not_found'])}; "
          f"questions with every text compared: {sum(1 for v in per_question.values() if v['compared'] == v['texts'])} "
          f"of {len(per_question)}")


if __name__ == "__main__":
    main()

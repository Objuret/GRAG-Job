"""Four blinded, tool-free model readings of the invented facet controls.

Default writes the exact prompts only. --run executes the four calls once, with
no automatic retry. No corpus, benchmark, graph, or saved head scores are sent.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "prod"), str(ROOT / "test")]
from harness.chat import _CLAUDE_EXE


def prompts():
    # Fixtures already published before this reader experiment; no model scores read.
    import ast
    tree = ast.parse((ROOT / "tools/facet_semantic_controls.py").read_text())
    cases = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == "CASES" for t in n.targets))
    old = (ROOT / "test/graph/prompts/facet_pairs_judge.txt").read_text(encoding="utf-8")
    # Keep the substantive old instructions; adapt only single-case JSON packaging.
    old = old.split("Your entire reply is one JSON object")[0].strip()
    revised = """Compare the relevance of each phrase to its own text, seen through five facets.
The facet is the perspective through which you consider relevance to the content.
Judge the phrase-to-content relationship, not the phrase's type or the facet's importance.
Use only the given texts, without importing facts. For each facet choose A, B, or equal.
topic — looking at what that content is about: how relevant is the phrase to that content?
temporal — looking at that content's time relations (before and after, now and then,
done, pending, due; never a date): how relevant is the phrase to that content, seen that way?
why — looking at that content's reasons, its causes and purposes: how relevant is the
phrase to that content, seen that way?
activity — looking at what is actually going on in that content, as against what is only
described, referenced or discussed: how relevant is the phrase to that content, seen that way?
concreteness — looking at that content's specifics, as against its general talk: how
relevant is the phrase to that content, seen that way?
Choose equal if neither relationship is clearly stronger, including when both have none
of that facet or the texts do not provide enough information to distinguish them."""
    wrapper = """\n\nEvaluate each numbered case independently. Return only JSON:
{"cases":{"c0":{"topic":"A|B|equal","temporal":"A|B|equal",
"why":"A|B|equal","activity":"A|B|equal","concreteness":"A|B|equal"}, ...}}.
Include every supplied case and every facet. No explanations or tool use."""
    jobs = []
    rng = random.Random(220922)
    orientation = [rng.choice([False, True]) for _ in cases]
    for variant, system in [("old", old), ("revised", revised)]:
        for reverse in (False, True):
            ids = list(range(len(cases)))
            random.Random(220922 + int(reverse)).shuffle(ids)
            parts, expected = [], {}
            for i in ids:
                tag, text = cases[i]
                other = cases[(i+4) % len(cases)][0]
                swapped = orientation[i] ^ reverse
                a, b = (other, tag) if swapped else (tag, other)
                expected[f"c{i}"] = "B" if swapped else "A"
                parts.append(f"Case c{i}\nRelationship A\nPhrase A: {a}\nText A:\n{text}\n\nRelationship B\nPhrase B: {b}\nText B:\n{text}")
            jobs.append({"id": f"{variant}_{'reversed' if reverse else 'forward'}",
                         "variant": variant, "system": system + wrapper,
                         "user": "\n\n".join(parts), "related_side_not_sent": expected})
    return jobs


def run(job, out, model):
    path = out / f"{job['id']}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    cmd = [_CLAUDE_EXE, "-p", "--model", model, "--effort", "high",
           "--output-format", "json", "--tools", "", "--setting-sources", "",
           "--no-session-persistence", "--system-prompt", job["system"]]
    start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="facet-control-reader-") as cwd:
        result = subprocess.run(cmd, input=job["user"], cwd=cwd, capture_output=True,
                                text=True, encoding="utf-8", timeout=180)
    if result.returncode:
        raise RuntimeError(f"{job['id']}: exit {result.returncode}: {result.stderr[:300]}")
    envelope = json.loads(result.stdout)
    if envelope.get("is_error"):
        raise RuntimeError(f"{job['id']}: {envelope.get('result')}")
    raw = envelope["result"].strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    answer = json.loads(raw)
    facets = ("topic", "temporal", "why", "activity", "concreteness")
    if set(answer["cases"]) != set(job["related_side_not_sent"]):
        raise ValueError("reader omitted or added a case")
    for values in answer["cases"].values():
        if set(values) != set(facets) or not all(v in ("A", "B", "equal") for v in values.values()):
            raise ValueError("invalid reader choices")
    body = {"id": job["id"], "model_requested": model,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "system_sha256": hashlib.sha256(job["system"].encode()).hexdigest(),
            "user_sha256": hashlib.sha256(job["user"].encode()).hexdigest(),
            "answer": answer, "usage": envelope.get("usage"),
            "model_usage": envelope.get("modelUsage"),
            "cost_usd_reported": envelope.get("total_cost_usd"),
            "seconds": time.perf_counter()-start,
            "related_direction_counts": {f: sum(values[f] == job["related_side_not_sent"][cid]
                 for cid, values in answer["cases"].items()) for f in facets}}
    path.write_text(json.dumps(body, indent=2)+"\n", encoding="utf-8")
    return body


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model", default="claude-opus-5")
    ap.add_argument("--run", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    jobs = prompts()
    manifest = args.out / "prompts.json"
    body = {"protocol": __doc__, "model": args.model, "jobs": jobs}
    if manifest.exists() and json.loads(manifest.read_text()) != body:
        raise RuntimeError("existing experiment has different prompts or model")
    manifest.write_text(json.dumps(body, indent=2)+"\n", encoding="utf-8")
    print(f"Four exact prompts saved to {manifest}", flush=True)
    if args.run:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run, job, args.out, args.model) for job in jobs]
            for f in as_completed(futures):
                r = f.result()
                print(r["id"], r["related_direction_counts"], flush=True)


if __name__ == "__main__":
    main()

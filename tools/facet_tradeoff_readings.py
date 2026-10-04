"""Collect a synthetic trade-off function screen, with scores and labels separated.

The exact input manifest is written before any call. Four domains each have one
fixed tag, four sought-content descriptions and four relevant content alternatives.
All six candidate pairs are read under each description, then read again with
A/B reversed. Numeric query and graph facet readings are collected separately;
the preference reader sees neither facet names, scores, expected ranks nor split.
All calls are tool-free. This is a small model-based screen, not human validation.
"""
from __future__ import annotations

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import itertools
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

FACETS = ("topic", "temporal", "why", "activity", "concreteness")
PREFERENCE = """For each case you are given a description of sought content and two candidate
passages. Judge which passage would be more useful to retrieve for that described
content, using only what each passage actually says. Do not invent missing facts.
Use A, B, or equal; use equal when neither has a clear advantage for this request.
Cases are independent. Return only JSON: {"cases":{"case_id":"A|B|equal",...}}.
Include every supplied case. Do not use tools or provide explanations."""


def jobs(cases):
    tree = ast.parse((ROOT / "test/artefact/querytagger.py").read_text(encoding="utf-8"))
    query_prompt = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "SCORE_SYSTEM" for t in n.targets))
    query_prompt = query_prompt.split("Return ONLY valid JSON:")[0]
    # Graph-side probe uses the same perspective definitions, judging supplied
    # content directly instead of inferring the content characterised by a description.
    definitions = query_prompt.split("## Facets", 1)[1].split("## Weights", 1)[0]
    graph_prompt = """For each case, judge how relevant the supplied tag is to the supplied
text through each facet. Use only the actual text. Judge the tag-to-content
relationship, not the tag's type or the facet's importance. Give values from 0
(not relevant through that facet) to 1 (could not be more relevant through it).
Several values may be high or all low. Never force a top value.
""" + definitions
    wrapper = '\nTreat cases independently. Return only JSON: {"cases":{"case_id":{"topic":0.0,"temporal":0.0,"why":0.0,"activity":0.0,"concreteness":0.0},...}}. Include every supplied case and all five facets. No tools or explanations.'
    result = []
    for role, system, field, label in [("query", query_prompt, "descriptions", "Description"),
                                       ("graph", graph_prompt, "texts", "Text")]:
        for repeat in range(2):
            items = [(f"{d['id']}_{i}", d["tag"], s) for d in cases["domains"]
                     for i, s in enumerate(d[field])]
            random.Random(220922+repeat).shuffle(items)
            result.append({"id": f"{role}_{repeat}", "role": role, "repeat": repeat,
                "system": system+wrapper,
                "user": '\n\n'.join(f"Case {cid}\nTag: {tag}\n{label}:\n{s}" for cid, tag, s in items),
                "case_ids": [cid for cid, _, _ in items]})
    for d in cases["domains"]:
        for reverse in (False, True):
            items, orientation = [], {}
            rng = random.Random(220922)
            for qi, description in enumerate(d["descriptions"]):
                for a, b in itertools.combinations(range(len(d["texts"])), 2):
                    cid = f"{d['id']}_{qi}_{a}_{b}"
                    swap = rng.choice([False, True]) ^ reverse
                    ai, bi = (b, a) if swap else (a, b)
                    orientation[cid] = [ai, bi]
                    items.append((cid, f"Case {cid}\nSought content: {description}\n\nPassage A:\n{d['texts'][ai]}\n\nPassage B:\n{d['texts'][bi]}"))
            random.Random(220922+int(reverse)).shuffle(items)
            result.append({"id": f"preference_{d['id']}_{int(reverse)}", "role": "preference",
                "repeat": int(reverse), "system": PREFERENCE,
                "user": '\n\n'.join(v for _, v in items),
                "case_ids": [cid for cid, _ in items], "orientation_not_sent": orientation})
    return result


def run(job, out, model):
    path = out / (job["id"]+".json")
    signatures = {k+"_sha256": hashlib.sha256(job[k].encode()).hexdigest() for k in ("system", "user")}
    if path.exists():
        saved = json.loads(path.read_text())
        if saved["model_requested"] != model or any(saved[k] != v for k, v in signatures.items()):
            raise ValueError("existing response belongs to different input")
        return saved
    start = time.perf_counter()
    raw_path = out / (job["id"]+".raw.json")
    recovered_raw = raw_path.exists()
    if recovered_raw:
        prior = json.loads(raw_path.read_text())
        if prior["model_requested"] != model or any(prior[k] != v for k,v in signatures.items()):
            raise ValueError("raw response signature differs")
        envelope = prior["envelope"]
    else:
        with tempfile.TemporaryDirectory(prefix="facet-tradeoff-reader-") as cwd:
            r = subprocess.run([_CLAUDE_EXE, "-p", "--model", model, "--effort", "high",
                "--output-format", "json", "--tools", "", "--setting-sources", "",
                "--no-session-persistence", "--system-prompt", job["system"]], input=job["user"],
                cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=240)
        if r.returncode:
            raise RuntimeError(f"{job['id']} exited {r.returncode}: {r.stderr[:300]}")
        envelope = json.loads(r.stdout)
    # Retain transport output even when schema validation fails. Invalid readings
    # must remain inspectable instead of disappearing or becoming silent retries.
    raw_path.write_text(json.dumps({"envelope": envelope, **signatures,
        "model_requested": model}, indent=2)+"\n", encoding="utf-8")
    if envelope.get("is_error"):
        raise RuntimeError(str(envelope.get("result")))
    raw = envelope["result"].strip()
    if raw.startswith("```"):
        raw = raw.split('\n', 1)[1].rsplit('```', 1)[0].strip()
    answer = json.loads(raw)["cases"]
    missing = sorted(set(job["case_ids"])-set(answer))
    if set(answer)-set(job["case_ids"]):
        raise ValueError("unexpected case IDs")
    if job["role"] == "preference":
        if not all(v in ("A", "B", "equal") for v in answer.values()):
            raise ValueError("invalid preference")
    else:
        for v in answer.values():
            if set(v) != set(FACETS) or not all(type(x) in (int, float) and 0 <= x <= 1 for x in v.values()):
                raise ValueError("invalid facet values")
    result = {"id": job["id"], "role": job["role"], "model_requested": model,
        "created_utc": datetime.now(timezone.utc).isoformat(), **signatures,
        "answer": answer, "usage": envelope.get("usage"), "model_usage": envelope.get("modelUsage"),
        "missing_cases": missing, "recovered_raw_without_new_call": recovered_raw,
        "cost_usd_reported": envelope.get("total_cost_usd"), "seconds": time.perf_counter()-start}
    path.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model", default="claude-opus-5")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--only", help="Execute only this job ID; manifest remains complete")
    args = ap.parse_args()
    cases = json.loads((ROOT / "tools/facet_tradeoff_cases.json").read_text(encoding="utf-8"))
    manifest = {"protocol": __doc__, "model": args.model, "cases": cases, "jobs": jobs(cases),
        "analysis_prespecified": {
            "split": "leave one of four subject domains out; all its descriptions and passages excluded from fitting",
            "methods": ["topic only", "query-independent nonnegative weighted facets", "equal query-times-edge products", "fitted nonnegative query-times-edge products", "query ordered lexicographic facets"],
            "numeric_fit": "three-way Davidson likelihood with tie logit and L2 penalty; choose penalty by inner leave-one-domain-out log loss from [0.001,0.01,0.1,1]; report outer predictions only",
            "score_sources": ["separate direct readings", "original frozen graph head mapped to prior fixed references"],
            "repeats": "retain both preference readings, average numeric readings; repeats are not independent samples",
            "limits": "four invented domains, common comparison structure, one model reading all roles; screen only, no production promotion"}}
    args.out.mkdir(parents=True, exist_ok=True)
    p = args.out / "manifest.json"
    if p.exists() and json.loads(p.read_text()) != manifest:
        raise RuntimeError("manifest changed")
    p.write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(f"Saved {len(manifest['jobs'])} exact call inputs before execution", flush=True)
    if args.run:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run, job, args.out, args.model) for job in manifest["jobs"]
                       if args.only is None or job["id"] == args.only]
            for f in as_completed(futures):
                r = f.result()
                print(r["id"], len(r["answer"]), f"{r['seconds']:.1f}s", flush=True)


if __name__ == "__main__":
    main()
